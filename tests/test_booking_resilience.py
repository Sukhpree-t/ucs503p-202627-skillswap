"""
Booking Resilience and Failure Recovery Tests (Sprint 3 Follow-ups).
Verifies:
1. Booking failure midway causes zero credit loss, slot remains open, ledger remains balanced.
2. Low-balance learner racing releases the Redis distributed lock immediately, allowing eligible learner to book.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import httpx
import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skillswap_rpc
from skillswap_rpc import (
    SUPABASE_URL,
    SUPABASE_KEY,
    post_transfer_rpc,
    audit_ledger_rpc,
    book_slot_rpc,
    InsufficientBalanceRPCError,
    SlotConflictError,
)

JWT_SECRET = os.environ.get("JWT_SECRET", "skillswap-dev-secret-ucs503-2026")
API_BASE = "http://127.0.0.1:8001"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


@pytest.mark.asyncio
async def test_booking_fails_midway_no_credits_lost_and_slot_open():
    """
    Test 1: If a booking fails midway (e.g. insufficient learner balance),
    transaction rolls back: no credits are lost, slot remains open, and zero-sum invariant holds.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Create mentor and 2-credit slot
        mentor_id = str(uuid.uuid4())
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": mentor_id,
            "campus_email": f"mentor_resilience_{mentor_id[:6]}@thapar.edu",
            "full_name": "Resilience Mentor",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        now = datetime.now(timezone.utc)
        slot_resp = await client.post(f"{SUPABASE_URL}/rest/v1/availability_slots", json={
            "mentor_id": mentor_id,
            "start_time": (now + timedelta(days=4)).isoformat(),
            "end_time": (now + timedelta(days=4, hours=1)).isoformat(),
            "rate_credits": 2,
            "status": "open"
        }, headers=headers)
        slot_id = slot_resp.json()[0]["id"]

        # 2. Create learner with balance 0 (insufficient for 2 credits)
        learner_id = str(uuid.uuid4())
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": learner_id,
            "campus_email": f"learner_resilience_{learner_id[:6]}@thapar.edu",
            "full_name": "Low Balance Student",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        await client.post(f"{SUPABASE_URL}/rest/v1/accounts", json={
            "kind": "user",
            "owner_id": learner_id,
            "balance": 0
        }, headers=headers)

        # Record pre-failure ledger debits/credits
        pre_audit = audit_ledger_rpc()

        # 3. Attempt booking via RPC -> Must raise InsufficientBalanceRPCError
        with pytest.raises(InsufficientBalanceRPCError):
            book_slot_rpc(slot_id, learner_id, "Attempting booking with 0 credits")

        # 4. Verify Slot is STILL open
        slot_check = await client.get(f"{SUPABASE_URL}/rest/v1/availability_slots?id=eq.{slot_id}", headers=headers)
        assert slot_check.json()[0]["status"] == "open", "Slot must remain open after failed booking"

        # 5. Verify Learner balance is STILL 0 (no credits lost)
        acc_check = await client.get(f"{SUPABASE_URL}/rest/v1/accounts?owner_id=eq.{learner_id}&kind=eq.user", headers=headers)
        assert acc_check.json()[0]["balance"] == 0, "Learner balance must be unchanged"

        # 6. Verify zero bookings created for this slot
        b_check = await client.get(f"{SUPABASE_URL}/rest/v1/bookings?slot_id=eq.{slot_id}", headers=headers)
        assert len(b_check.json()) == 0, "No booking row should exist"

        # 7. Verify zero-sum ledger audit still passes
        post_audit = audit_ledger_rpc()
        assert post_audit["details"]["unbalanced_tx"] == []
        assert post_audit["total_debits"] == pre_audit["total_debits"]
        assert post_audit["total_credits"] == pre_audit["total_credits"]


@pytest.mark.asyncio
async def test_low_balance_learner_racing_lock_released():
    """
    Test 2: When an ineligible learner with low balance races for a slot,
    the Redis distributed lock is released immediately upon rejection,
    allowing an eligible learner to immediately book the slot without waiting for TTL expiry.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Mint account
        mint_resp = await client.get(f"{SUPABASE_URL}/rest/v1/accounts?kind=eq.mint", headers=headers)
        mint_id = mint_resp.json()[0]["id"]

        # Mentor & Slot (Cost = 2 credits)
        mentor_id = str(uuid.uuid4())
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": mentor_id,
            "campus_email": f"mentor_race_{mentor_id[:6]}@thapar.edu",
            "full_name": "Racing Mentor",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        now = datetime.now(timezone.utc)
        slot_resp = await client.post(f"{SUPABASE_URL}/rest/v1/availability_slots", json={
            "mentor_id": mentor_id,
            "start_time": (now + timedelta(days=5)).isoformat(),
            "end_time": (now + timedelta(days=5, hours=1)).isoformat(),
            "rate_credits": 2,
            "status": "open"
        }, headers=headers)
        slot_id = slot_resp.json()[0]["id"]

        # Learner A: 0 credits
        learner_a_id = str(uuid.uuid4())
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": learner_a_id,
            "campus_email": f"learner_a_{learner_a_id[:6]}@thapar.edu",
            "full_name": "Learner A Broke",
            "role": "peer",
            "status": "active"
        }, headers=headers)
        await client.post(f"{SUPABASE_URL}/rest/v1/accounts", json={
            "kind": "user",
            "owner_id": learner_a_id,
            "balance": 0
        }, headers=headers)

        # Learner B: 3 credits
        learner_b_id = str(uuid.uuid4())
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": learner_b_id,
            "campus_email": f"learner_b_{learner_b_id[:6]}@thapar.edu",
            "full_name": "Learner B Funded",
            "role": "peer",
            "status": "active"
        }, headers=headers)
        acc_b = await client.post(f"{SUPABASE_URL}/rest/v1/accounts", json={
            "kind": "user",
            "owner_id": learner_b_id,
            "balance": 0
        }, headers=headers)
        acc_b_id = acc_b.json()[0]["id"]
        post_transfer_rpc(mint_id, acc_b_id, 3, "starter_grant", description="Starter funds")

        # 1. Learner A races and attempts booking -> fails with InsufficientBalance
        with pytest.raises(InsufficientBalanceRPCError):
            book_slot_rpc(slot_id, learner_a_id, "Ineligible attempt")

        # 2. Learner B immediately attempts booking -> MUST SUCCEED (proving lock was released!)
        booking_id = book_slot_rpc(slot_id, learner_b_id, "Eligible instant booking")
        assert booking_id is not None, "Learner B must succeed immediately"

        # 3. Verify Slot is now booked
        slot_check = await client.get(f"{SUPABASE_URL}/rest/v1/availability_slots?id=eq.{slot_id}", headers=headers)
        assert slot_check.json()[0]["status"] == "booked"

        # 4. Verify Learner B balance reduced from 3 to 1
        acc_b_check = await client.get(f"{SUPABASE_URL}/rest/v1/accounts?id=eq.{acc_b_id}", headers=headers)
        assert acc_b_check.json()[0]["balance"] == 1

        # 5. Ledger audit passes (double-entry zero-sum invariant holds)
        audit = audit_ledger_rpc()
        assert audit["details"]["unbalanced_tx"] == []
