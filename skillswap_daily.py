"""
SkillSwap Daily.co Video Service Client
Handles WebRTC private room provisioning, room-scoped meeting tokens,
quota-preserving room deletion, and automatic expired room cleanup.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("skillswap.daily")

DAILY_API_BASE = os.environ.get("DAILY_API_BASE", "https://api.daily.co/v1")


def get_daily_api_key() -> str:
    key = os.environ.get("DAILY_API_KEY", "")
    if not key and os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("DAILY_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return key


def get_daily_domain() -> str:
    domain = os.environ.get("DAILY_DOMAIN", "")
    if not domain and os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("DAILY_DOMAIN="):
                        domain = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return domain or "earthian"


class DailyRoomCreationError(Exception):
    """Raised when room creation fails after retries."""
    pass


class DailyTokenCreationError(Exception):
    """Raised when meeting token creation fails."""
    pass


def _daily_request(
    endpoint: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    api_key = get_daily_api_key()
    if not api_key:
        raise DailyRoomCreationError("DAILY_API_KEY is not configured.")

    url = f"{DAILY_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"error": err_body}
        logger.warning("Daily API HTTP error %d on %s: %s", e.code, endpoint, parsed)
        raise urllib.error.HTTPError(
            e.url, e.code, json.dumps(parsed), e.headers, None
        ) from e
    except urllib.error.URLError as e:
        logger.error("Daily API network error on %s: %s", endpoint, e)
        raise


def create_room(
    booking_id: str,
    scheduled_start: datetime,
    scheduled_end: datetime,
    max_retries: int = 3,
    backoff_factor: float = 0.2,
) -> Dict[str, Any]:
    """
    Creates a private Daily.co room for a booking with retries.
    Enforces max_participants: 2, eject_at_room_exp: true.
    Treats 'room already exists' as success.
    """
    room_name = f"skillswap-{booking_id}"
    domain = get_daily_domain()

    # Time boundaries
    nbf_ts = int(scheduled_start.replace(tzinfo=timezone.utc).timestamp()) - 600
    exp_ts = int(scheduled_end.replace(tzinfo=timezone.utc).timestamp()) + 900

    payload = {
        "name": room_name,
        "privacy": "private",
        "properties": {
            "max_participants": 2,
            "nbf": nbf_ts,
            "exp": exp_ts,
            "eject_at_room_exp": True,
            "enable_chat": True,
            "enable_screenshare": True,
        },
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            res = _daily_request("rooms", method="POST", payload=payload)
            logger.info("Created Daily room %s on attempt %d", room_name, attempt)
            return {
                "room_name": room_name,
                "url": res.get("url") or f"https://{domain}.daily.co/{room_name}",
                "domain": f"{domain}.daily.co",
                "expires_at": exp_ts,
            }
        except urllib.error.HTTPError as e:
            # Check for 400 with "already exists" or 409 conflict
            err_str = str(e)
            if "already exists" in err_str.lower() or e.code == 409:
                logger.info("Room %s already exists on Daily.co, treating as success", room_name)
                return {
                    "room_name": room_name,
                    "url": f"https://{domain}.daily.co/{room_name}",
                    "domain": f"{domain}.daily.co",
                    "expires_at": exp_ts,
                }
            last_error = e
        except Exception as e:
            last_error = e

        if attempt < max_retries:
            time.sleep(backoff_factor * (2 ** (attempt - 1)))

    logger.error("Failed to create Daily room %s after %d attempts: %s", room_name, max_retries, last_error)
    raise DailyRoomCreationError(f"Failed to create room on Daily.co: {last_error}")


def create_meeting_token(
    room_name: str,
    user_id: str,
    user_name: str,
    is_mentor: bool,
    scheduled_start: datetime,
    scheduled_end: datetime,
) -> str:
    """
    Generates a room-scoped, short-lived meeting token with eject_at_token_exp: true.
    Mentor gets is_owner: true.
    """
    nbf_ts = int(scheduled_start.replace(tzinfo=timezone.utc).timestamp()) - 600
    exp_ts = int(scheduled_end.replace(tzinfo=timezone.utc).timestamp()) + 900

    payload = {
        "properties": {
            "room_name": room_name,
            "user_name": user_name,
            "user_id": str(user_id),
            "is_owner": bool(is_mentor),
            "nbf": nbf_ts,
            "exp": exp_ts,
            "eject_at_token_exp": True,
        }
    }

    try:
        res = _daily_request("meeting-tokens", method="POST", payload=payload)
        token = res.get("token")
        if not token:
            raise DailyTokenCreationError("No token in Daily API response.")
        return token
    except Exception as e:
        logger.error("Error creating meeting token for room %s: %s", room_name, e)
        raise DailyTokenCreationError(f"Failed to generate meeting token: {e}") from e


def delete_room(room_name: str) -> bool:
    """
    Best-effort deletion of a Daily room to preserve the 50-room free plan limit.
    Never raises an exception.
    """
    try:
        _daily_request(f"rooms/{room_name}", method="DELETE")
        logger.info("Successfully deleted Daily room: %s", room_name)
        return True
    except Exception as e:
        logger.warning("Best-effort delete failed for room %s: %s", room_name, e)
        return False


def cleanup_expired_rooms() -> int:
    """
    Finds and deletes expired rooms on Daily.co to stay well below the 50-room limit.
    """
    try:
        res = _daily_request("rooms", method="GET")
        rooms = res.get("data", [])
        now_ts = int(time.time())
        deleted_count = 0

        for room in rooms:
            name = room.get("name", "")
            exp = (room.get("config") or {}).get("exp") or room.get("exp")
            if exp and exp <= now_ts:
                if delete_room(name):
                    deleted_count += 1

        logger.info("Cleaned up %d expired rooms on Daily.co", deleted_count)
        return deleted_count
    except Exception as e:
        logger.warning("Expired rooms cleanup encountered an error: %s", e)
        return 0
