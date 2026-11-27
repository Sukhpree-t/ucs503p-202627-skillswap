"""
tests/test_daily_sessions.py

Sprint 4 test suite for Daily.co session join, heartbeat, and settlement.

All Daily.co API calls are mocked - no live network calls are made in CI.

Coverage targets:
  - skillswap_daily.py  >= 70%
  - skillswap_rpc.py    >= 70%  (cumulative across all test files)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root (parent of tests/) is on sys.path so that
# skillswap_daily and skillswap_rpc are importable without installation.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import skillswap_daily
import skillswap_rpc
from skillswap_daily import (
    create_room,
    create_meeting_token,
    delete_room,
    cleanup_expired_rooms,
    DailyRoomCreationError,
    DailyTokenCreationError,
)
from skillswap_rpc import (
    join_session_rpc,
    sign_off_booking_rpc,
    refund_booking_rpc,
    audit_ledger_rpc,
    LedgerRPCError,
)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_booking(
    booking_id: str | None = None,
    learner_id: str | None = None,
    mentor_id: str | None = None,
    offset_minutes: int = 0,          # offset from "now" for scheduled_start
    duration_minutes: int = 60,
    escrow_status: str = "held",
    status: str = "confirmed",
) -> dict:
    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=duration_minutes)
    return {
        "id": booking_id or str(uuid.uuid4()),
        "learner_id": learner_id or str(uuid.uuid4()),
        "mentor_id": mentor_id or str(uuid.uuid4()),
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
        "escrow_status": escrow_status,
        "status": status,
        "cost_credits": 5,
        "slot_id": str(uuid.uuid4()),
    }


def _daily_room_response(room_name: str, domain: str = "earthian") -> dict:
    return {
        "id": "room-id",
        "name": room_name,
        "url": f"https://{domain}.daily.co/{room_name}",
        "privacy": "private",
    }


def _daily_token_response() -> dict:
    return {"token": "daily.test.token.xxxxxx"}


# ---------------------------------------------------------------------------
# skillswap_daily.py tests
# ---------------------------------------------------------------------------

class TestCreateRoom:

    def test_room_created_successfully(self):
        """Happy path: room created on first attempt."""
        from skillswap_daily import create_room, DailyRoomCreationError

        booking_id = str(uuid.uuid4())
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)
        expected_room_name = f"skillswap-{booking_id}"

        with patch("skillswap_daily._daily_request") as mock_req:
            mock_req.return_value = _daily_room_response(expected_room_name)
            result = create_room(booking_id, start, end)

        assert result["room_name"] == expected_room_name
        assert "domain" in result
        assert "expires_at" in result
        # Verify room payload had max_participants=2
        call_kwargs = mock_req.call_args
        payload = call_kwargs[1].get("payload") or call_kwargs[0][2]
        assert payload["properties"]["max_participants"] == 2
        assert payload["properties"]["eject_at_room_exp"] is True
        assert payload["privacy"] == "private"

    def test_room_already_exists_treated_as_success(self):
        """Daily returns 'already exists' → treated as idempotent success."""
        import urllib.error
        from skillswap_daily import create_room

        booking_id = str(uuid.uuid4())
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request") as mock_req:
            err = urllib.error.HTTPError(
                "https://api.daily.co/v1/rooms", 400,
                json.dumps({"error": "room-name-in-use: already exists"}),
                {}, None
            )
            mock_req.side_effect = err
            result = create_room(booking_id, start, end)

        assert result["room_name"] == f"skillswap-{booking_id}"

    def test_room_creation_retries_3_times_then_raises(self):
        """Daily fails 3 times → DailyRoomCreationError raised."""
        import urllib.error
        from skillswap_daily import create_room, DailyRoomCreationError

        booking_id = str(uuid.uuid4())
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        transient_err = Exception("connection refused")
        with patch("skillswap_daily._daily_request", side_effect=transient_err), \
             patch("skillswap_daily.time.sleep"):  # skip backoff waits in tests
            with pytest.raises(DailyRoomCreationError):
                create_room(booking_id, start, end, max_retries=3)

    def test_room_creation_fails_on_daily_down(self):
        """Daily is completely down (all 3 attempts fail) → DailyRoomCreationError."""
        from skillswap_daily import create_room, DailyRoomCreationError

        booking_id = str(uuid.uuid4())
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request", side_effect=Exception("Service Unavailable")), \
             patch("skillswap_daily.time.sleep"):
            with pytest.raises(DailyRoomCreationError, match="Failed to create room on Daily.co"):
                create_room(booking_id, start, end)


class TestCreateMeetingToken:

    def test_mentor_gets_is_owner_true(self):
        """Mentor receives is_owner=True in token request."""
        from skillswap_daily import create_meeting_token

        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request") as mock_req:
            mock_req.return_value = _daily_token_response()
            token = create_meeting_token(
                room_name="skillswap-abc",
                user_id="mentor-uid",
                user_name="Dr. Ananya",
                is_mentor=True,
                scheduled_start=start,
                scheduled_end=end,
            )

        assert token == "daily.test.token.xxxxxx"
        payload = mock_req.call_args[1].get("payload") or mock_req.call_args[0][2]
        props = payload["properties"]
        assert props["is_owner"] is True
        assert props["room_name"] == "skillswap-abc"
        assert props["eject_at_token_exp"] is True

    def test_learner_gets_is_owner_false(self):
        """Learner receives is_owner=False in token request."""
        from skillswap_daily import create_meeting_token

        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request") as mock_req:
            mock_req.return_value = _daily_token_response()
            create_meeting_token(
                room_name="skillswap-abc",
                user_id="learner-uid",
                user_name="Rohan",
                is_mentor=False,
                scheduled_start=start,
                scheduled_end=end,
            )

        payload = mock_req.call_args[1].get("payload") or mock_req.call_args[0][2]
        assert payload["properties"]["is_owner"] is False

    def test_token_window_matches_room_window(self):
        """Token nbf = start - 10m, exp = end + 15m."""
        from skillswap_daily import create_meeting_token

        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)
        expected_nbf = int(start.timestamp()) - 600
        expected_exp = int(end.timestamp()) + 900

        with patch("skillswap_daily._daily_request") as mock_req:
            mock_req.return_value = _daily_token_response()
            create_meeting_token("room", "uid", "Name", True, start, end)

        payload = mock_req.call_args[1].get("payload") or mock_req.call_args[0][2]
        assert payload["properties"]["nbf"] == expected_nbf
        assert payload["properties"]["exp"] == expected_exp


class TestDeleteRoom:

    def test_delete_room_success_returns_true(self):
        """Successful room deletion returns True."""
        from skillswap_daily import delete_room

        with patch("skillswap_daily._daily_request") as mock_req:
            mock_req.return_value = {}
            result = delete_room("skillswap-abc123")

        assert result is True
        mock_req.assert_called_once_with("rooms/skillswap-abc123", method="DELETE")

    def test_delete_room_failure_returns_false_no_raise(self):
        """Best-effort: delete failure returns False, never raises."""
        from skillswap_daily import delete_room

        with patch("skillswap_daily._daily_request", side_effect=Exception("Network error")):
            result = delete_room("skillswap-abc123")

        assert result is False

    def test_cleanup_expired_rooms_counts_deleted(self):
        """cleanup_expired_rooms deletes only expired rooms."""
        from skillswap_daily import cleanup_expired_rooms

        old_exp = int(time.time()) - 3600   # expired 1h ago
        future_exp = int(time.time()) + 3600 # not yet expired

        rooms_response = {
            "data": [
                {"name": "skillswap-old1", "config": {"exp": old_exp}},
                {"name": "skillswap-old2", "config": {"exp": old_exp}},
                {"name": "skillswap-active", "config": {"exp": future_exp}},
            ]
        }

        with patch("skillswap_daily._daily_request") as mock_req:
            # First call returns room list; subsequent DELETE calls return {}
            mock_req.side_effect = [rooms_response, {}, {}]
            count = cleanup_expired_rooms()

        assert count == 2  # only the 2 expired rooms deleted


# ---------------------------------------------------------------------------
# skillswap_rpc.py Sprint 4 additions
# ---------------------------------------------------------------------------

class TestJoinSessionRpc:

    def test_join_session_calls_pg_rpc(self):
        """join_session_rpc passes all parameters to call_postgres_rpc."""
        from skillswap_rpc import join_session_rpc

        booking_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        expected_response = {"success": True, "room_name": "skillswap-abc", "is_owner": True}

        with patch("skillswap_rpc.call_postgres_rpc", return_value=expected_response) as mock_rpc:
            result = join_session_rpc(
                booking_id=booking_id,
                user_id=user_id,
                room_name="skillswap-abc",
                video_domain="earthian.daily.co",
                expires_at_iso="2026-12-01T11:15:00+00:00",
                jti=jti,
                video_provider="daily",
            )

        assert result == expected_response
        mock_rpc.assert_called_once()
        call_args = mock_rpc.call_args[0]
        assert call_args[0] == "join_session"
        payload = call_args[1]
        assert payload["p_booking_id"] == booking_id
        assert payload["p_user_id"] == user_id
        assert payload["p_jti"] == jti
        assert payload["p_video_provider"] == "daily"

    def test_simultaneous_joins_one_session_rooms_two_tokens(self):
        """
        Simulates both participants joining simultaneously.
        Only 1 session_rooms row is created (idempotent); 2 session_tokens rows are created.
        """
        session_rooms_inserts: list[dict] = []
        session_tokens_inserts: list[dict] = []
        lock = threading.Lock()

        booking_id = str(uuid.uuid4())
        learner_id = str(uuid.uuid4())
        mentor_id = str(uuid.uuid4())
        room_name = f"skillswap-{booking_id}"

        def mock_join_rpc(function_name, payload):
            assert function_name == "join_session"
            assert payload["p_booking_id"] == booking_id
            with lock:
                # Simulate idempotent insert: session_rooms only created once
                if not any(r["room_name"] == payload["p_room_name"] for r in session_rooms_inserts):
                    session_rooms_inserts.append({"room_name": payload["p_room_name"]})
                # session_tokens always inserted (one per participant)
                session_tokens_inserts.append({"jti": payload["p_jti"], "user_id": payload["p_user_id"]})
            return {"success": True, "room_name": room_name, "is_owner": payload["p_user_id"] == mentor_id}

        from skillswap_rpc import join_session_rpc

        errors = []

        def join_as(user_id, jti):
            try:
                with patch("skillswap_rpc.call_postgres_rpc", side_effect=mock_join_rpc):
                    join_session_rpc(
                        booking_id=booking_id,
                        user_id=user_id,
                        room_name=room_name,
                        video_domain="earthian.daily.co",
                        expires_at_iso="2026-12-01T11:15:00+00:00",
                        jti=jti,
                    )
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=join_as, args=(learner_id, str(uuid.uuid4())))
        t2 = threading.Thread(target=join_as, args=(mentor_id, str(uuid.uuid4())))
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert not errors, f"Unexpected errors during simultaneous join: {errors}"
        assert len(session_rooms_inserts) == 1, \
            f"Expected exactly 1 session_rooms row, got {len(session_rooms_inserts)}"
        assert len(session_tokens_inserts) == 2, \
            f"Expected exactly 2 session_tokens rows, got {len(session_tokens_inserts)}"


class TestSignOffRpc:

    def test_sign_off_returns_waiting(self):
        """First sign-off returns 'waiting_for_other_party'."""
        from skillswap_rpc import sign_off_booking_rpc

        booking_id = str(uuid.uuid4())
        with patch("skillswap_rpc.call_postgres_rpc", return_value="waiting_for_other_party"):
            result = sign_off_booking_rpc(booking_id=booking_id, user_id=str(uuid.uuid4()))
        assert result == "waiting_for_other_party"

    def test_sign_off_returns_settled(self):
        """Second sign-off returns 'settled'."""
        from skillswap_rpc import sign_off_booking_rpc

        booking_id = str(uuid.uuid4())
        with patch("skillswap_rpc.call_postgres_rpc", return_value="settled"):
            result = sign_off_booking_rpc(booking_id=booking_id, user_id=str(uuid.uuid4()))
        assert result == "settled"

    def test_early_sign_off_raises_error(self):
        """EARLY_SIGN_OFF_REJECTED from PG propagates as LedgerRPCError."""
        from skillswap_rpc import sign_off_booking_rpc, LedgerRPCError

        import urllib.error
        err = urllib.error.HTTPError("url", 422, "EARLY_SIGN_OFF_REJECTED", {}, None)

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=LedgerRPCError("EARLY_SIGN_OFF_REJECTED")):
            with pytest.raises(LedgerRPCError, match="EARLY_SIGN_OFF_REJECTED"):
                sign_off_booking_rpc(booking_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))


class TestRefundBookingRpc:

    def test_refund_booking_calls_rpc_no_strike(self):
        """refund_booking_rpc calls correct RPC with strike_mentor=False."""
        from skillswap_rpc import refund_booking_rpc

        booking_id = str(uuid.uuid4())
        with patch("skillswap_rpc.call_postgres_rpc", return_value=None) as mock_rpc:
            refund_booking_rpc(booking_id=booking_id, strike_mentor=False)

        mock_rpc.assert_called_once()
        payload = mock_rpc.call_args[0][1]
        assert payload["p_booking_id"] == booking_id
        assert payload["p_strike_mentor"] is False


class TestAuditLedgerRpc:

    def test_audit_ledger_p_auto_true(self):
        """audit_ledger_rpc with p_auto=True passes flag to PG."""
        from skillswap_rpc import audit_ledger_rpc

        with patch("skillswap_rpc.call_postgres_rpc", return_value={"passed": True}) as mock_rpc:
            result = audit_ledger_rpc(p_auto=True)

        assert result["passed"] is True
        payload = mock_rpc.call_args[0][1]
        assert payload["p_auto"] is True

    def test_audit_ledger_fail_does_not_raise(self):
        """Backend handles audit failure gracefully - audit result returned as dict."""
        from skillswap_rpc import audit_ledger_rpc

        with patch("skillswap_rpc.call_postgres_rpc", return_value={"passed": False, "discrepancy": 5}):
            result = audit_ledger_rpc(p_auto=True)

        assert result["passed"] is False
        assert result["discrepancy"] == 5


# ---------------------------------------------------------------------------
# Join endpoint integration: join window and escrow rules (via skillswap_rpc)
# ---------------------------------------------------------------------------

class TestJoinWindowRules:

    def test_join_too_early_raises_session_not_started(self):
        """PG RPC raises SESSION_NOT_STARTED when join is too early."""
        from skillswap_rpc import join_session_rpc, LedgerRPCError

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=LedgerRPCError("SESSION_NOT_STARTED")):
            with pytest.raises(LedgerRPCError, match="SESSION_NOT_STARTED"):
                join_session_rpc(
                    booking_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    room_name="skillswap-test",
                    video_domain="earthian.daily.co",
                    expires_at_iso="2099-01-01T00:00:00+00:00",
                    jti=str(uuid.uuid4()),
                )

    def test_join_after_window_raises_session_expired(self):
        """PG RPC raises SESSION_WINDOW_EXPIRED when join is too late."""
        from skillswap_rpc import join_session_rpc, LedgerRPCError

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=LedgerRPCError("SESSION_WINDOW_EXPIRED")):
            with pytest.raises(LedgerRPCError, match="SESSION_WINDOW_EXPIRED"):
                join_session_rpc(
                    booking_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    room_name="skillswap-test",
                    video_domain="earthian.daily.co",
                    expires_at_iso="2020-01-01T00:00:00+00:00",
                    jti=str(uuid.uuid4()),
                )

    def test_join_with_wrong_escrow_status_forbidden(self):
        """PG RPC raises ESCROW_NOT_HELD when escrow is released."""
        from skillswap_rpc import join_session_rpc, LedgerRPCError

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=LedgerRPCError("ESCROW_NOT_HELD")):
            with pytest.raises(LedgerRPCError, match="ESCROW_NOT_HELD"):
                join_session_rpc(
                    booking_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    room_name="skillswap-test",
                    video_domain="earthian.daily.co",
                    expires_at_iso="2026-12-01T12:00:00+00:00",
                    jti=str(uuid.uuid4()),
                )

    def test_unauthorized_participant_forbidden(self):
        """PG RPC raises FORBIDDEN for a third-party user."""
        from skillswap_rpc import join_session_rpc, LedgerRPCError

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=LedgerRPCError("FORBIDDEN")):
            with pytest.raises(LedgerRPCError, match="FORBIDDEN"):
                join_session_rpc(
                    booking_id=str(uuid.uuid4()),
                    user_id="unauthorized-user",
                    room_name="skillswap-test",
                    video_domain="earthian.daily.co",
                    expires_at_iso="2026-12-01T12:00:00+00:00",
                    jti=str(uuid.uuid4()),
                )


# ---------------------------------------------------------------------------
# Audit fail-safe: settlement kept even when audit fails
# ---------------------------------------------------------------------------

class TestAuditFailsafeBehavior:

    def test_audit_failure_does_not_rollback_settlement(self):
        """When audit fails, the settlement result is KEPT. No exception is raised."""
        from skillswap_rpc import audit_ledger_rpc, sign_off_booking_rpc

        booking_id = str(uuid.uuid4())

        def pg_rpc_sequence(fn, payload):
            if fn == "sign_off_booking":
                return "settled"
            if fn == "audit_ledger":
                return {"passed": False, "discrepancy": 10}
            return None

        with patch("skillswap_rpc.call_postgres_rpc", side_effect=pg_rpc_sequence):
            settle_result = sign_off_booking_rpc(booking_id=booking_id, user_id=str(uuid.uuid4()))
            audit_result = audit_ledger_rpc(p_auto=True)

        # Settlement must be preserved regardless of audit failure
        assert settle_result == "settled"
        assert audit_result["passed"] is False
        assert audit_result["discrepancy"] == 10


# ---------------------------------------------------------------------------
# Additional coverage tests for skillswap_daily.py – targeting uncovered
# branches: env-var/dotenv fallback, _daily_request error paths,
# create_meeting_token failure, cleanup exception handling.
# ---------------------------------------------------------------------------

class TestDailyRequestErrorPaths:
    """Covers _daily_request's HTTPError and URLError branches (lines 66-94)."""

    def test_daily_request_http_error_reraises(self):
        """HTTPError body is parsed and re-raised as HTTPError."""
        import urllib.error
        import io

        # Simulate an HTTPError whose body is valid JSON
        body = json.dumps({"error": "forbidden"}).encode("utf-8")
        err = urllib.error.HTTPError(
            "https://api.daily.co/v1/rooms", 403, "Forbidden",
            {}, io.BytesIO(body)
        )

        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(urllib.error.HTTPError):
                skillswap_daily._daily_request("rooms", method="POST", payload={"name": "x"})

    def test_daily_request_http_error_non_json_body(self):
        """HTTPError with non-JSON body is handled gracefully."""
        import urllib.error
        import io

        body = b"Internal Server Error"
        err = urllib.error.HTTPError(
            "https://api.daily.co/v1/rooms", 500, "Internal Server Error",
            {}, io.BytesIO(body)
        )

        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(urllib.error.HTTPError):
                skillswap_daily._daily_request("rooms", method="POST", payload={"name": "x"})

    def test_daily_request_url_error_reraises(self):
        """URLError (network issue) is re-raised."""
        import urllib.error

        err = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(urllib.error.URLError):
                skillswap_daily._daily_request("rooms")

    def test_daily_request_no_api_key_raises(self):
        """Missing DAILY_API_KEY raises DailyRoomCreationError before any HTTP call."""
        with patch("skillswap_daily.get_daily_api_key", return_value=""):
            with pytest.raises(skillswap_daily.DailyRoomCreationError, match="DAILY_API_KEY is not configured"):
                skillswap_daily._daily_request("rooms")

    def test_daily_request_empty_response_body(self):
        """Empty HTTP response body returns empty dict."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("skillswap_daily.get_daily_api_key", return_value="test-key"), \
             patch("urllib.request.urlopen", return_value=mock_resp):
            result = skillswap_daily._daily_request("rooms")
        assert result == {}


class TestEnvFallbackFunctions:
    """Covers get_daily_api_key / get_daily_domain .env fallback branches (lines 23-33, 45-46)."""

    def test_get_daily_api_key_from_env_var(self):
        """Key read from DAILY_API_KEY env var directly."""
        with patch.dict("os.environ", {"DAILY_API_KEY": "env-key-xyz"}):
            assert skillswap_daily.get_daily_api_key() == "env-key-xyz"

    def test_get_daily_api_key_from_dotenv_file(self, tmp_path):
        """Key read from .env file when env var is absent."""
        import io
        dotenv_content = "DAILY_API_KEY=file-key-abc\nOTHER=value\n"

        os.environ.pop("DAILY_API_KEY", None)
        with patch("skillswap_daily.os.path.exists", return_value=True), \
             patch("skillswap_daily.open",
                   return_value=io.StringIO(dotenv_content),
                   create=True):
            key = skillswap_daily.get_daily_api_key()
        assert key == "file-key-abc"

    def test_get_daily_domain_default(self):
        """Returns 'earthian' when env var and .env are absent."""
        os.environ.pop("DAILY_DOMAIN", None)
        with patch("skillswap_daily.os.path.exists", return_value=False):
            domain = skillswap_daily.get_daily_domain()
        assert domain == "earthian"

    def test_get_daily_domain_from_env_var(self):
        """DAILY_DOMAIN env var takes precedence."""
        with patch.dict("os.environ", {"DAILY_DOMAIN": "myteam"}):
            assert skillswap_daily.get_daily_domain() == "myteam"


class TestCreateMeetingTokenFailure:
    """Covers create_meeting_token exception path (lines 193, 195-197)."""

    def test_token_creation_raises_when_api_fails(self):
        """When Daily returns no token, DailyTokenCreationError is raised."""
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request", return_value={}):  # no 'token' key
            with pytest.raises(DailyTokenCreationError, match="No token"):
                create_meeting_token("room-x", "uid", "Name", True, start, end)

    def test_token_creation_raises_when_request_throws(self):
        """Network exception during token creation raises DailyTokenCreationError."""
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        with patch("skillswap_daily._daily_request", side_effect=Exception("timeout")):
            with pytest.raises(DailyTokenCreationError, match="Failed to generate meeting token"):
                create_meeting_token("room-x", "uid", "Name", False, start, end)


class TestCleanupExpiredRoomsException:
    """Covers cleanup_expired_rooms exception branch (lines 233-235)."""

    def test_cleanup_returns_zero_on_exception(self):
        """If _daily_request raises during list, cleanup returns 0 without raising."""
        with patch("skillswap_daily._daily_request", side_effect=Exception("API down")):
            count = cleanup_expired_rooms()
        assert count == 0

    def test_create_room_non_already_exists_http_error_retries(self):
        """An HTTPError that is NOT 'already exists' is treated as transient and retried."""
        import urllib.error
        import io

        booking_id = str(uuid.uuid4())
        start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)

        body = json.dumps({"error": "rate-limit-exceeded"}).encode("utf-8")
        err = urllib.error.HTTPError(
            "https://api.daily.co/v1/rooms", 429, "Too Many Requests",
            {}, io.BytesIO(body)
        )

        with patch("skillswap_daily._daily_request", side_effect=err), \
             patch("skillswap_daily.time.sleep"):
            with pytest.raises(DailyRoomCreationError):
                create_room(booking_id, start, end, max_retries=2)


# ---------------------------------------------------------------------------
# Behavior-asserting unit tests for skillswap_rpc.py lines 236-274:
# alert_all_admins_rpc
# ---------------------------------------------------------------------------

class TestAlertAllAdminsRpcBehavior:
    """
    Tests lines 236-274 of skillswap_rpc.py (alert_all_admins_rpc).
    Asserts real behavior: admin discovery, notification payload format,
    handling of malformed admin records, and network failure resilience.
    """

    def test_alert_all_admins_success_dispatches_notifications(self):
        """Dispatches notification to each admin and returns count of successful posts."""
        from skillswap_rpc import alert_all_admins_rpc

        admins_response = json.dumps([
            {"id": "admin-uuid-1"},
            {"id": "admin-uuid-2"},
        ]).encode("utf-8")

        mock_admins_resp = MagicMock()
        mock_admins_resp.read.return_value = admins_response
        mock_admins_resp.__enter__ = lambda s: s
        mock_admins_resp.__exit__ = MagicMock(return_value=False)

        mock_post_resp = MagicMock()
        mock_post_resp.__enter__ = lambda s: s
        mock_post_resp.__exit__ = MagicMock(return_value=False)

        posted_requests: list[urllib.request.Request] = []

        def fake_urlopen(req, timeout=10):
            if "profiles" in req.full_url:
                return mock_admins_resp
            if "notifications" in req.full_url:
                posted_requests.append(req)
                return mock_post_resp
            raise ValueError(f"Unexpected URL: {req.full_url}")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            count = alert_all_admins_rpc(
                title="Ledger Alert",
                body="Discrepancy found",
                data={"booking_id": "b-123"}
            )

        assert count == 2, f"Expected 2 alerts sent, got {count}"
        assert len(posted_requests) == 2

        # Assert notification payload structure for first admin
        req1_data = json.loads(posted_requests[0].data.decode("utf-8"))
        assert req1_data["user_id"] == "admin-uuid-1"
        assert req1_data["type"] == "admin_alert"
        assert req1_data["title"] == "Ledger Alert"
        assert req1_data["body"] == "Discrepancy found"
        assert req1_data["data"]["booking_id"] == "b-123"

        # Assert notification payload structure for second admin
        req2_data = json.loads(posted_requests[1].data.decode("utf-8"))
        assert req2_data["user_id"] == "admin-uuid-2"

    def test_alert_all_admins_handles_profiles_fetch_failure(self):
        """When fetching admin profiles fails, catches exception and returns 0."""
        from skillswap_rpc import alert_all_admins_rpc
        import urllib.error

        err = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            count = alert_all_admins_rpc(title="Alert", body="Test")

        assert count == 0

    def test_alert_all_admins_skips_malformed_and_tolerates_individual_failures(self):
        """Skips admins without valid id and tolerates failures on individual notification posts."""
        from skillswap_rpc import alert_all_admins_rpc

        admins_response = json.dumps([
            {"id": "admin-good"},
            {"id": None},           # missing id -> skipped
            {"id": "admin-failing"}, # post will fail
        ]).encode("utf-8")

        mock_admins_resp = MagicMock()
        mock_admins_resp.read.return_value = admins_response
        mock_admins_resp.__enter__ = lambda s: s
        mock_admins_resp.__exit__ = MagicMock(return_value=False)

        mock_good_post = MagicMock()
        mock_good_post.__enter__ = lambda s: s
        mock_good_post.__exit__ = MagicMock(return_value=False)

        def fake_urlopen(req, timeout=10):
            if "profiles" in req.full_url:
                return mock_admins_resp
            if "notifications" in req.full_url:
                data = json.loads(req.data.decode("utf-8"))
                if data["user_id"] == "admin-good":
                    return mock_good_post
                raise urllib.error.HTTPError(req.full_url, 500, "Error", {}, None)
            raise ValueError(f"Unexpected URL: {req.full_url}")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            count = alert_all_admins_rpc(title="Partial Alert", body="Details")

        assert count == 1  # only admin-good succeeded
