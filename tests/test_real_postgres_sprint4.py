"""
tests/test_real_postgres_sprint4.py

Real PostgreSQL tests (NO MOCKS) verifying Sprint 4 database operations against Supabase:
1. Both sign-offs move cost_credits from escrow to the mentor and audit_ledger passes.
2. Early sign-off is rejected before scheduled_start.
3. refund_booking releases escrow back to learner, cancels slot, creates notification, and audit passes.
4. Two simultaneous join_session calls create exactly one session_rooms row and two session_tokens rows.
"""
from __future__ import annotations

import os
import sys
import uuid
import time
import threading
from datetime import datetime, timezone, timedelta
import urllib.request
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skillswap_rpc import (
    SUPABASE_URL,
    SUPABASE_KEY,
    book_slot_pure_pg,
    post_transfer_rpc,
    audit_ledger_rpc,
    join_session_rpc,
    sign_off_booking_rpc,
    refund_booking_rpc,
    LedgerRPCError,
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _http_get(endpoint: str) -> list | dict:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{endpoint}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post(endpoint: str, data: dict | list) -> list | dict:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}


def _http_delete(endpoint: str) -> None:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{endpoint}", headers=HEADERS, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass


def _http_patch(endpoint: str, data: dict) -> None:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers=HEADERS,
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=15):
        pass


def _create_real_fixture(start_offset_minutes: int = 2, duration_minutes: int = 60, cost: int = 2):
    """
    Provisions real test entities: mentor profile + account, learner profile + account (funded),
    and an availability slot. Returns all IDs.
    """
    prefix = uuid.uuid4().hex[:8]

    # 1. Fetch mint account
    mint_rows = _http_get("accounts?kind=eq.mint")
    mint_id = mint_rows[0]["id"]

    # 2. Mentor profile + account
    mentor_id = str(uuid.uuid4())
    _http_post("profiles", {
        "id": mentor_id,
        "campus_email": f"mentor_{prefix}@thapar.edu",
        "full_name": f"Mentor {prefix}",
        "role": "peer",
        "status": "active"
    })
    m_acc_rows = _http_post("accounts", {
        "kind": "user",
        "owner_id": mentor_id,
        "balance": 0
    })
    mentor_acc_id = m_acc_rows[0]["id"] if isinstance(m_acc_rows, list) else m_acc_rows["id"]

    # 3. Learner profile + account
    learner_id = str(uuid.uuid4())
    _http_post("profiles", {
        "id": learner_id,
        "campus_email": f"learner_{prefix}@thapar.edu",
        "full_name": f"Learner {prefix}",
        "role": "peer",
        "status": "active"
    })
    l_acc_rows = _http_post("accounts", {
        "kind": "user",
        "owner_id": learner_id,
        "balance": 0
    })
    learner_acc_id = l_acc_rows[0]["id"] if isinstance(l_acc_rows, list) else l_acc_rows["id"]

    # 4. Fund learner with 10 starter credits from mint
    post_transfer_rpc(mint_id, learner_acc_id, 10, "starter_grant", None, f"Real test fund {prefix}")

    # 5. Create availability slot
    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(minutes=start_offset_minutes)).isoformat()
    end_time = (now + timedelta(minutes=start_offset_minutes + duration_minutes)).isoformat()
    slot_rows = _http_post("availability_slots", {
        "mentor_id": mentor_id,
        "start_time": start_time,
        "end_time": end_time,
        "rate_credits": cost,
        "status": "open"
    })
    slot_id = slot_rows[0]["id"] if isinstance(slot_rows, list) else slot_rows["id"]

    return {
        "mentor_id": mentor_id,
        "mentor_acc_id": mentor_acc_id,
        "learner_id": learner_id,
        "learner_acc_id": learner_acc_id,
        "slot_id": slot_id,
        "cost": cost,
    }


def _cleanup_fixture(fixture: dict):
    m_id = fixture["mentor_id"]
    l_id = fixture["learner_id"]
    s_id = fixture["slot_id"]
    _http_delete(f"session_tokens?booking_id=in.(select id from bookings where slot_id=eq.{s_id})")
    _http_delete(f"session_rooms?booking_id=in.(select id from bookings where slot_id=eq.{s_id})")
    _http_delete(f"session_events?booking_id=in.(select id from bookings where slot_id=eq.{s_id})")
    _http_delete(f"bookings?slot_id=eq.{s_id}")
    _http_delete(f"availability_slots?id=eq.{s_id}")
    _http_delete(f"notifications?user_id=in.({m_id},{l_id})")


# ---------------------------------------------------------------------------
# Test 1: Both sign-offs move cost_credits to mentor & audit_ledger passes
# ---------------------------------------------------------------------------

def test_real_pg_sign_off_settles_and_audit_passes():
    """
    Verifies against real Supabase PostgreSQL:
    1. Learner books slot -> escrow holds cost_credits.
    2. Learner signs off -> returns 'waiting_for_other_party'.
    3. Mentor signs off -> returns 'settled'.
    4. Mentor balance increases by cost_credits.
    5. Booking is marked completed and escrow released.
    6. audit_ledger passes with zero discrepancy.
    """
    fix = _create_real_fixture(start_offset_minutes=2, duration_minutes=60, cost=3)
    try:
        # Book slot (scheduled 2 min in future so slot is open & available)
        booking_id = book_slot_pure_pg(fix["slot_id"], fix["learner_id"], "Real PG Sign-off Test")
        assert booking_id is not None

        # Fast-forward booking's scheduled_start to 5 min in past so sign-off is permitted
        past_start = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        _http_patch(f"bookings?id=eq.{booking_id}", {"scheduled_start": past_start})

        # Check mentor balance before sign-off
        m_acc = _http_get(f"accounts?id=eq.{fix['mentor_acc_id']}")[0]
        assert m_acc["balance"] == 0

        # Step 1: Learner signs off
        res1 = sign_off_booking_rpc(booking_id=booking_id, user_id=fix["learner_id"])
        assert res1 == "waiting_for_other_party", f"Expected waiting_for_other_party, got {res1}"

        # Mentor balance should still be 0
        m_acc = _http_get(f"accounts?id=eq.{fix['mentor_acc_id']}")[0]
        assert m_acc["balance"] == 0

        # Step 2: Mentor signs off -> settlement triggers
        res2 = sign_off_booking_rpc(booking_id=booking_id, user_id=fix["mentor_id"])
        assert res2 == "settled", f"Expected settled, got {res2}"

        # Mentor balance must now equal cost_credits (3)
        m_acc = _http_get(f"accounts?id=eq.{fix['mentor_acc_id']}")[0]
        assert m_acc["balance"] == 3, f"Expected mentor balance 3, got {m_acc['balance']}"

        # Booking state verified
        b_row = _http_get(f"bookings?id=eq.{booking_id}")[0]
        assert b_row["status"] == "completed"
        assert b_row["escrow_status"] == "released"
        assert b_row["settled_at"] is not None

        # Ledger audit check: verify double-entry invariant holds across transactions
        audit = audit_ledger_rpc(p_auto=False)
        assert audit["details"]["unbalanced_tx"] == [], f"Found unbalanced transactions: {audit['details']['unbalanced_tx']}"
    finally:
        _cleanup_fixture(fix)


# ---------------------------------------------------------------------------
# Test 2: Early sign-off is rejected before scheduled_start
# ---------------------------------------------------------------------------

def test_real_pg_early_sign_off_rejected():
    """
    Verifies that calling sign_off_booking before scheduled_start raises
    EARLY_SIGN_OFF_REJECTED in real PostgreSQL.
    """
    # Start 2 hours in the future
    fix = _create_real_fixture(start_offset_minutes=120, duration_minutes=60, cost=2)
    try:
        booking_id = book_slot_pure_pg(fix["slot_id"], fix["learner_id"], "Early Sign-off Test")

        with pytest.raises(LedgerRPCError) as exc_info:
            sign_off_booking_rpc(booking_id=booking_id, user_id=fix["learner_id"])

        assert "EARLY_SIGN_OFF_REJECTED" in str(exc_info.value), \
            f"Expected EARLY_SIGN_OFF_REJECTED, got: {exc_info.value}"

        # Verify booking status remains untouched
        b_row = _http_get(f"bookings?id=eq.{booking_id}")[0]
        assert b_row["status"] == "confirmed"
        assert b_row["escrow_status"] == "held"
        assert b_row["learner_signed_off"] is False
    finally:
        _cleanup_fixture(fix)


# ---------------------------------------------------------------------------
# Test 3: refund_booking releases escrow back to learner and cancels slot
# ---------------------------------------------------------------------------

def test_real_pg_refund_booking_works():
    """
    Verifies that refund_booking restores learner credits, cancels slot,
    marks booking refunded, creates notification, and preserves zero-sum ledger.
    """
    fix = _create_real_fixture(start_offset_minutes=2, duration_minutes=60, cost=4)
    try:
        booking_id = book_slot_pure_pg(fix["slot_id"], fix["learner_id"], "Refund Booking Test")

        # Learner balance after booking 10 - 4 = 6
        l_acc = _http_get(f"accounts?id=eq.{fix['learner_acc_id']}")[0]
        assert l_acc["balance"] == 6

        # Call refund_booking (no strike)
        refund_booking_rpc(booking_id=booking_id, strike_mentor=False)

        # Learner balance restored to 10
        l_acc_after = _http_get(f"accounts?id=eq.{fix['learner_acc_id']}")[0]
        assert l_acc_after["balance"] == 10, f"Expected 10, got {l_acc_after['balance']}"

        # Booking status is refunded
        b_row = _http_get(f"bookings?id=eq.{booking_id}")[0]
        assert b_row["status"] == "refunded"
        assert b_row["escrow_status"] == "refunded"

        # Slot cancelled
        s_row = _http_get(f"availability_slots?id=eq.{fix['slot_id']}")[0]
        assert s_row["status"] == "cancelled"

        # In-app notification created for learner
        notifs = _http_get(f"notifications?user_id=eq.{fix['learner_id']}&type=eq.refund")
        assert len(notifs) >= 1

        # Ledger audit check: verify double-entry invariant holds across transactions
        audit = audit_ledger_rpc(p_auto=False)
        assert audit["details"]["unbalanced_tx"] == [], f"Found unbalanced transactions: {audit['details']['unbalanced_tx']}"
    finally:
        _cleanup_fixture(fix)


# ---------------------------------------------------------------------------
# Test 4: Simultaneous join_session calls create 1 room and 2 tokens
# ---------------------------------------------------------------------------

def test_real_pg_simultaneous_join_session_idempotent():
    """
    Verifies against real Supabase PostgreSQL that when learner and mentor
    call join_session simultaneously:
    - Exactly 1 session_rooms row is created (ON CONFLICT DO NOTHING).
    - Exactly 2 session_tokens rows are created.
    - Exactly 2 session_events ('joined') rows are created.
    """
    fix = _create_real_fixture(start_offset_minutes=2, duration_minutes=60, cost=2)
    try:
        booking_id = book_slot_pure_pg(fix["slot_id"], fix["learner_id"], "Simultaneous Join Test")

        room_name = f"skillswap-{booking_id}"
        expires_at_iso = (datetime.now(timezone.utc) + timedelta(minutes=75)).isoformat()
        jti_learner = str(uuid.uuid4())
        jti_mentor = str(uuid.uuid4())

        results = []
        errors = []

        def join_as(uid, jti):
            try:
                res = join_session_rpc(
                    booking_id=booking_id,
                    user_id=uid,
                    room_name=room_name,
                    video_domain="earthian.daily.co",
                    expires_at_iso=expires_at_iso,
                    jti=jti,
                    video_provider="daily",
                )
                results.append(res)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=join_as, args=(fix["learner_id"], jti_learner))
        t2 = threading.Thread(target=join_as, args=(fix["mentor_id"], jti_mentor))
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert not errors, f"Unexpected errors during simultaneous join: {errors}"
        assert len(results) == 2, f"Expected 2 responses, got {len(results)}"

        # Query database tables directly
        rooms = _http_get(f"session_rooms?booking_id=eq.{booking_id}")
        assert len(rooms) == 1, f"Expected exactly 1 session_rooms row, got {len(rooms)}"
        assert rooms[0]["room_name"] == room_name
        assert rooms[0]["video_provider"] == "daily"

        tokens = _http_get(f"session_tokens?booking_id=eq.{booking_id}")
        assert len(tokens) == 2, f"Expected exactly 2 session_tokens rows, got {len(tokens)}"

        events = _http_get(f"session_events?booking_id=eq.{booking_id}&event_type=eq.joined")
        assert len(events) == 2, f"Expected 2 joined session_events rows, got {len(events)}"
    finally:
        _cleanup_fixture(fix)
