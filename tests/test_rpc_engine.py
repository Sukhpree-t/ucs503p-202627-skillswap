"""
Unit and Integration Tests for skillswap_rpc.py
Ensures >= 70% branch and statement coverage on:
- Insufficient balance calculation and error model
- Redis distributed mutex lifecycle, timeout, and exception recovery
- PostgREST RPC error mapping and payload parsing
"""

import io
import json
import os
import sys
import uuid
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skillswap_rpc
from skillswap_rpc import (
    InsufficientBalanceRPCError,
    SlotConflictError,
    LedgerRPCError,
    SlotDistributedLock,
    call_postgres_rpc,
    get_redis_client,
    book_slot_rpc,
    book_slot_pure_pg,
    post_transfer_rpc,
    audit_ledger_rpc,
)


def test_insufficient_balance_error_model():
    err = InsufficientBalanceRPCError("Insufficient funds", required=10, current=3)
    assert str(err) == "Insufficient funds"
    assert err.required == 10
    assert err.current == 3
    assert err.shortfall == 7

    # When current > required
    err2 = InsufficientBalanceRPCError("Surplus", required=2, current=5)
    assert err2.shortfall == 0


def test_redis_client_singleton():
    r1 = get_redis_client()
    r2 = get_redis_client()
    assert r1 is r2
    assert r1.ping() is True


def test_slot_distributed_lock_lifecycle():
    slot_id = str(uuid.uuid4())
    lock1 = SlotDistributedLock(slot_id, timeout_seconds=10)
    assert lock1.acquire() is True
    assert lock1.acquired is True

    # Lock already acquired, second instance cannot acquire
    lock2 = SlotDistributedLock(slot_id, timeout_seconds=10)
    assert lock2.acquire() is False
    assert lock2.acquired is False

    # Release lock1
    assert lock1.release() is True
    assert lock1.acquired is False

    # Calling release again on unacquired lock returns False
    assert lock1.release() is False

    # Now lock2 can acquire
    assert lock2.acquire() is True
    assert lock2.release() is True


def test_slot_distributed_lock_context_manager():
    slot_id = str(uuid.uuid4())
    with SlotDistributedLock(slot_id, timeout_seconds=10) as lock:
        assert lock.acquired is True
        # Contending context manager inside active lock must raise SlotConflictError
        with pytest.raises(SlotConflictError):
            with SlotDistributedLock(slot_id, timeout_seconds=10):
                pass

    # Outside context manager, lock was cleanly released
    with SlotDistributedLock(slot_id, timeout_seconds=10) as lock3:
        assert lock3.acquired is True


def test_slot_distributed_lock_redis_exceptions():
    mock_redis = MagicMock()
    mock_redis.set.side_effect = Exception("Redis connection timed out")
    mock_redis.eval.side_effect = Exception("Redis connection dropped")

    lock = SlotDistributedLock("fault-slot", timeout_seconds=5, client=mock_redis)
    # acquire handles exception gracefully
    assert lock.acquire() is False

    # simulate acquired then eval exception
    lock.acquired = True
    assert lock.release() is False


def test_call_postgres_rpc_success_json():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"passed": True, "total_debits": 5}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = call_postgres_rpc("audit_ledger", {"p_auto": False})
        assert res == {"passed": True, "total_debits": 5}


def test_call_postgres_rpc_success_plain_text_and_empty():
    # Plain string response
    mock_resp_text = MagicMock()
    mock_resp_text.read.return_value = b'"settled"'
    mock_cm_text = MagicMock()
    mock_cm_text.__enter__.return_value = mock_resp_text
    with patch("urllib.request.urlopen", return_value=mock_cm_text):
        res = call_postgres_rpc("sign_off_booking", {"p_booking_id": "123"})
        assert res == "settled"

    # Empty response
    mock_resp_empty = MagicMock()
    mock_resp_empty.read.return_value = b""
    mock_cm_empty = MagicMock()
    mock_cm_empty.__enter__.return_value = mock_resp_empty
    with patch("urllib.request.urlopen", return_value=mock_cm_empty):
        res = call_postgres_rpc("refund_booking", {"p_booking_id": "123"})
        assert res is None


def test_call_postgres_rpc_error_mappings():
    # 1. SLOT_UNAVAILABLE -> SlotConflictError
    err_body_slot = json.dumps({"message": "SLOT_UNAVAILABLE", "details": "Slot is already booked"}).encode("utf-8")
    http_err_slot = urllib.error.HTTPError("http://test", 400, "Bad Request", {}, io.BytesIO(err_body_slot))
    with patch("urllib.request.urlopen", side_effect=http_err_slot):
        with pytest.raises(SlotConflictError) as exc_info:
            call_postgres_rpc("book_slot", {})
        assert "Slot unavailable" in str(exc_info.value)

    # 2. INSUFFICIENT_BALANCE -> InsufficientBalanceRPCError
    err_body_bal = json.dumps({"message": "INSUFFICIENT_BALANCE"}).encode("utf-8")
    http_err_bal = urllib.error.HTTPError("http://test", 400, "Bad Request", {}, io.BytesIO(err_body_bal))
    with patch("urllib.request.urlopen", side_effect=http_err_bal):
        with pytest.raises(InsufficientBalanceRPCError):
            call_postgres_rpc("book_slot", {})

    # 3. OWN_SLOT -> LedgerRPCError
    err_body_own = json.dumps({"message": "OWN_SLOT"}).encode("utf-8")
    http_err_own = urllib.error.HTTPError("http://test", 400, "Bad Request", {}, io.BytesIO(err_body_own))
    with patch("urllib.request.urlopen", side_effect=http_err_own):
        with pytest.raises(LedgerRPCError) as exc_info:
            call_postgres_rpc("book_slot", {})
        assert "Mentors cannot book their own slots" in str(exc_info.value)

    # 4. Other error with non-json body -> LedgerRPCError
    http_err_raw = urllib.error.HTTPError("http://test", 500, "Internal Server Error", {}, io.BytesIO(b"PostgreSQL connection reset"))
    with patch("urllib.request.urlopen", side_effect=http_err_raw):
        with pytest.raises(LedgerRPCError) as exc_info:
            call_postgres_rpc("book_slot", {})
        assert "PostgreSQL connection reset" in str(exc_info.value)


def test_book_slot_pure_pg_wrapper():
    with patch("skillswap_rpc.call_postgres_rpc", return_value="mock-booking-uuid-pure"):
        b_id = book_slot_pure_pg("slot-1", "learner-1", "Test Pure")
        assert b_id == "mock-booking-uuid-pure"


def test_book_slot_rpc_wrapper():
    with patch("skillswap_rpc.call_postgres_rpc", return_value="mock-booking-uuid-dist"):
        b_id = book_slot_rpc(str(uuid.uuid4()), "learner-dist-1", "Test Distributed")
        assert b_id == "mock-booking-uuid-dist"
