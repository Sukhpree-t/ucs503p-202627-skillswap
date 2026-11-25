"""
SkillSwap RPC Client & Distributed Lock Engine
Interfaces with Supabase PostgreSQL stored procedures (book_slot, post_transfer, audit_ledger)
and manages Redis distributed locking for zero-sum concurrent booking operations.
"""

import os
import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.error
import redis

logger = logging.getLogger("skillswap_rpc")

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fuaxsnqlwbcdkzgmredt.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1YXhzbnFsd2JjZGt6Z21yZWR0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUyNDg5MTUsImV4cCI6MjExMDgyNDkxNX0.NkaPQGZOCA_QMNs2seqw1yTUsmfxLEbephC631EXCvY"
)
REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Exceptions
class LedgerRPCError(Exception):
    pass

class SlotConflictError(LedgerRPCError):
    """Raised when a slot is already booked, locked by another client, or unavailable."""
    pass

class InsufficientBalanceRPCError(LedgerRPCError):
    """Raised when learner has insufficient balance to complete escrow lock."""
    def __init__(self, message: str, required: int = 0, current: int = 0):
        super().__init__(message)
        self.required = required
        self.current = current
        self.shortfall = max(0, required - current)

# Redis Connection
_redis_client = None

def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis_client


class SlotDistributedLock:
    """
    Distributed Redis Mutex for serializing booking attempts.
    Uses SET ... NX EX 30 with Lua atomic check-and-delete on release.
    """
    def __init__(self, slot_id: str, timeout_seconds: int = 30, client: Optional[redis.Redis] = None):
        self.slot_id = str(slot_id)
        self.lock_key = f"lock:slot:{self.slot_id}"
        self.timeout = timeout_seconds
        self.client = client or get_redis_client()
        self.token = str(uuid.uuid4())
        self.acquired = False

    def acquire(self) -> bool:
        try:
            res = self.client.set(self.lock_key, self.token, nx=True, ex=self.timeout)
            self.acquired = bool(res)
            return self.acquired
        except Exception as e:
            logger.warning(f"Redis lock error: {e}")
            return False

    def release(self) -> bool:
        if not self.acquired:
            return False
        lua_release = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            res = self.client.eval(lua_release, 1, self.lock_key, self.token)
            self.acquired = False
            return bool(res)
        except Exception as e:
            logger.warning(f"Redis release error: {e}")
            return False

    def __enter__(self):
        if not self.acquire():
            raise SlotConflictError(f"Slot {self.slot_id} is currently locked by another booking attempt.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def call_postgres_rpc(function_name: str, payload: Dict[str, Any]) -> Any:
    """
    Calls a PostgreSQL RPC function via Supabase PostgREST endpoint.
    Translates PostgreSQL errors into typed Python exceptions.
    """
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(error_body)
            msg = err_json.get("message", error_body)
            details = err_json.get("details", "")
        except Exception:
            msg = error_body
            details = ""

        if "SLOT_UNAVAILABLE" in msg or "already booked" in msg.lower() or "exclusion" in msg.lower():
            raise SlotConflictError(f"Slot unavailable: {msg}")
        elif "INSUFFICIENT_BALANCE" in msg:
            raise InsufficientBalanceRPCError("Insufficient credit balance to book this session.")
        elif "OWN_SLOT" in msg:
            raise LedgerRPCError("Mentors cannot book their own slots.")
        else:
            raise LedgerRPCError(f"PostgreSQL RPC {function_name} failed: {msg} {details}")


def book_slot_rpc(slot_id: str, learner_id: str, objectives: Optional[str] = None) -> str:
    """
    US-10: Distributed slot booking with Redis Mutex + PostgreSQL ACID RPC.
    Returns booking_id (UUID string).
    """
    # 1. Distributed mutex check
    with SlotDistributedLock(slot_id=slot_id):
        # 2. PostgreSQL ACID transaction execution
        booking_id = call_postgres_rpc("book_slot", {
            "p_slot_id": str(slot_id),
            "p_learner_id": str(learner_id),
            "p_objectives": objectives or "Peer mentoring session"
        })
        return str(booking_id)


def audit_ledger_rpc() -> Dict[str, Any]:
    """
    Verifies zero-sum double-entry ledger health across real PostgreSQL.
    """
    return call_postgres_rpc("audit_ledger", {"p_auto": False})


def post_transfer_rpc(
    from_acc_id: str,
    to_acc_id: str,
    amount: int,
    tx_type: str,
    booking_id: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """
    Calls public.post_transfer RPC in PostgreSQL.
    """
    return str(call_postgres_rpc("post_transfer", {
        "p_from": str(from_acc_id),
        "p_to": str(to_acc_id),
        "p_amount": amount,
        "p_type": tx_type,
        "p_booking": str(booking_id) if booking_id else None,
        "p_desc": description or "Credit transfer"
    }))
