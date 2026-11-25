"""
100-Concurrent Booking Verification Test against Real PostgreSQL and Real Redis.
Acceptance Criterion:
- Exactly 1 succeeds (HTTP 201)
- Exactly 99 get a clean conflict error (HTTP 409)
- SUM(debits) == SUM(credits) verified via public.audit_ledger()
"""

import asyncio
import os
import sys
import uuid
import json
import time
from datetime import datetime, timedelta, timezone
import httpx
import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skillswap_rpc
from skillswap_rpc import (
    SUPABASE_URL,
    SUPABASE_KEY,
    post_transfer_rpc,
    audit_ledger_rpc,
)

JWT_SECRET = os.environ.get("JWT_SECRET", "skillswap-dev-secret-ucs503-2026")
API_BASE = "http://127.0.0.1:8001"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


async def setup_concurrency_fixture():
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch mint account
        mint_resp = await client.get(f"{SUPABASE_URL}/rest/v1/accounts?kind=eq.mint", headers=headers)
        mint_acc = mint_resp.json()[0]
        mint_id = mint_acc["id"]

        # 2. Create Mentor Profile
        mentor_id = str(uuid.uuid4())
        mentor_email = f"mentor_{mentor_id[:8]}@thapar.edu"
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": mentor_id,
            "campus_email": mentor_email,
            "full_name": "Prof. Distributed Systems",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        # 3. Create single availability slot
        start_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=3, hours=1)).isoformat()
        slot_resp = await client.post(f"{SUPABASE_URL}/rest/v1/availability_slots", json={
            "mentor_id": mentor_id,
            "start_time": start_time,
            "end_time": end_time,
            "rate_credits": 1,
            "status": "open"
        }, headers=headers)
        slot_id = slot_resp.json()[0]["id"]

        # 4. Create 100 learners in batch
        learners = []
        profiles_batch = []
        accounts_batch = []

        for i in range(100):
            lid = str(uuid.uuid4())
            token = jwt.encode({"sub": lid, "email": f"learner_{i}_{lid[:6]}@thapar.edu", "role": "peer"}, JWT_SECRET, algorithm="HS256")
            learners.append({"id": lid, "token": token})
            profiles_batch.append({
                "id": lid,
                "campus_email": f"learner_{i}_{lid[:6]}@thapar.edu",
                "full_name": f"Concurrent Student {i+1}",
                "role": "peer",
                "status": "active"
            })
            accounts_batch.append({
                "kind": "user",
                "owner_id": lid,
                "balance": 0
            })

        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json=profiles_batch, headers=headers)
        acc_resp = await client.post(f"{SUPABASE_URL}/rest/v1/accounts", json=accounts_batch, headers=headers)
        created_accounts = acc_resp.json()

        # Mint starter credits for learners
        # Update balance directly or via post_transfer
        acc_ids = [a["id"] for a in created_accounts]
        loop = asyncio.get_running_loop()
        await asyncio.gather(*[
            loop.run_in_executor(None, post_transfer_rpc, mint_id, acc_id, 3, "starter_grant", None, "Starter credits")
            for acc_id in acc_ids
        ])

        return slot_id, learners


@pytest.mark.asyncio
async def test_100_concurrent_bookings_on_single_slot():
    print("\n[Setup] Provisioning mentor, single slot, and 100 learners...")
    slot_id, learners = await setup_concurrency_fixture()
    print(f"[Setup] Target slot {slot_id} ready. 100 learners provisioned.")

    # Concurrency execution
    async def attempt_booking(learner, client):
        req_headers = {
            "Authorization": f"Bearer {learner['token']}",
            "Content-Type": "application/json"
        }
        try:
            r = await client.post(
                f"{API_BASE}/booking",
                json={"slot_id": slot_id, "objectives": "Concurrency Test Session"},
                headers=req_headers
            )
            return r.status_code, r.text
        except Exception as e:
            return 500, str(e)

    print(f"[Execution] Firing 100 simultaneous POST /booking requests...")
    start_time = time.time()
    async with httpx.AsyncClient(timeout=20, limits=httpx.Limits(max_connections=120, max_keepalive_connections=50)) as client:
        tasks = [attempt_booking(l, client) for l in learners]
        results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    status_codes = [code for code, _ in results]
    successes = [res for code, res in results if code == 201]
    conflicts = [res for code, res in results if code == 409]
    others = [(code, res) for code, res in results if code not in (201, 409)]

    print(f"\n[Results in {elapsed:.2f}s]")
    print(f"Total Requests: {len(results)}")
    print(f"HTTP 201 Success: {len(successes)}")
    print(f"HTTP 409 Conflict: {len(conflicts)}")
    if others:
        print(f"Other Responses: {others[:5]}")

    # Acceptance Invariants
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 99, f"Expected exactly 99 conflicts, got {len(conflicts)}"
    assert len(others) == 0, f"Expected 0 unexpected errors, got {len(others)}"

    # Zero-Sum Ledger Invariant Verification
    audit = audit_ledger_rpc()
    print(f"\n[Post-Test Ledger Audit]")
    print(f"Audit Passed: {audit['passed']}")
    print(f"Total Debits: {audit['total_debits']}")
    print(f"Total Credits: {audit['total_credits']}")
    print(f"Held Bookings: {audit['details']['held_bookings']}")
    print(f"Unbalanced Transactions: {audit['details']['unbalanced_tx']}")

    assert audit["passed"] is True, "Audit report must pass"
    assert audit["total_debits"] == audit["total_credits"], "SUM(debits) must equal SUM(credits)"
    assert audit["details"]["unbalanced_tx"] == [], "There must be zero unbalanced transactions"
    print("ALL CONCURRENCY AND ZERO-SUM INVARIANTS SATISFIED!")


if __name__ == "__main__":
    asyncio.run(test_100_concurrent_bookings_on_single_slot())
