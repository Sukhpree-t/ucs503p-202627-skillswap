"""
100-Concurrent Booking Verification Suite against Real PostgreSQL and Real Redis.
Follow-up Coverage:
- Test 1: Standard Distributed Concurrency (Redis Lock Enabled).
- Test 2: Pure PostgreSQL Row Locking Variant (Redis Lock Disabled via X-Disable-Redis-Lock).
- Clean fixture teardown: isolates test users and leaves demo data untouched.
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


async def setup_concurrency_fixture(test_prefix: str = "conc"):
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch mint account
        mint_resp = await client.get(f"{SUPABASE_URL}/rest/v1/accounts?kind=eq.mint", headers=headers)
        mint_acc = mint_resp.json()[0]
        mint_id = mint_acc["id"]

        # 2. Create Mentor Profile
        mentor_id = str(uuid.uuid4())
        mentor_email = f"mentor_{test_prefix}_{mentor_id[:6]}@thapar.edu"
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": mentor_id,
            "campus_email": mentor_email,
            "full_name": f"Prof. Concurrency {test_prefix.upper()}",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        # 3. Create single availability slot
        start_time = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=6, hours=1)).isoformat()
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
            token = jwt.encode({"sub": lid, "email": f"learner_{test_prefix}_{i}_{lid[:6]}@thapar.edu", "role": "peer"}, JWT_SECRET, algorithm="HS256")
            learners.append({"id": lid, "token": token})
            profiles_batch.append({
                "id": lid,
                "campus_email": f"learner_{test_prefix}_{i}_{lid[:6]}@thapar.edu",
                "full_name": f"Student {test_prefix.upper()} {i+1}",
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

        # Concurrent starter credit distribution
        acc_ids = [a["id"] for a in created_accounts]
        loop = asyncio.get_running_loop()
        await asyncio.gather(*[
            loop.run_in_executor(None, post_transfer_rpc, mint_id, acc_id, 3, "starter_grant", None, f"Grant {test_prefix}")
            for acc_id in acc_ids
        ])

        return slot_id, learners, mentor_id


async def cleanup_concurrency_fixture(mentor_id: str, learners: list):
    """
    Cleans up isolated test users, avoiding any disruption to demo personas.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Delete mentor's slots and bookings
        await client.delete(f"{SUPABASE_URL}/rest/v1/availability_slots?mentor_id=eq.{mentor_id}", headers=headers)
        # Delete mentor profile
        await client.delete(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{mentor_id}", headers=headers)


@pytest.mark.asyncio
async def test_100_concurrent_bookings_on_single_slot():
    """
    Test 1: 100 simultaneous bookings with Redis Distributed Lock ENABLED.
    """
    print("\n[Test 1] Provisioning mentor, single slot, and 100 learners (Redis Lock Enabled)...")
    slot_id, learners, mentor_id = await setup_concurrency_fixture("redis_on")

    async def attempt_booking(learner, client):
        req_headers = {
            "Authorization": f"Bearer {learner['token']}",
            "Content-Type": "application/json"
        }
        try:
            r = await client.post(
                f"{API_BASE}/booking",
                json={"slot_id": slot_id, "objectives": "Redis Distributed Concurrency Test"},
                headers=req_headers
            )
            return r.status_code, r.text
        except Exception as e:
            return 500, str(e)

    start_time = time.time()
    async with httpx.AsyncClient(timeout=20, limits=httpx.Limits(max_connections=120, max_keepalive_connections=50)) as client:
        tasks = [attempt_booking(l, client) for l in learners]
        results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    successes = [res for code, res in results if code == 201]
    conflicts = [res for code, res in results if code == 409]

    print(f"\n[Redis Lock Results in {elapsed:.2f}s]")
    print(f"HTTP 201 Success: {len(successes)} | HTTP 409 Conflict: {len(conflicts)}")

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(conflicts) == 99, f"Expected 99 conflicts, got {len(conflicts)}"

    audit = audit_ledger_rpc()
    assert audit["details"]["unbalanced_tx"] == [], f"Found unbalanced transactions: {audit['details']['unbalanced_tx']}"

    await cleanup_concurrency_fixture(mentor_id, learners)


@pytest.mark.asyncio
async def test_100_concurrent_bookings_pure_postgres_no_redis():
    """
    Test 2: Variant with Redis Lock DISABLED (pure PostgreSQL row lock serialization).
    100 simultaneous requests hit PostgreSQL SELECT ... FOR UPDATE directly.
    Acceptance: Exactly 1 succeeds, 99 receive clean 409 conflict, audit passes.
    """
    print("\n[Test 2] Provisioning mentor, single slot, and 100 learners (Redis Lock DISABLED)...")
    slot_id, learners, mentor_id = await setup_concurrency_fixture("pg_pure")

    async def attempt_booking_pure_pg(learner, client):
        req_headers = {
            "Authorization": f"Bearer {learner['token']}",
            "Content-Type": "application/json",
            "X-Disable-Redis-Lock": "true"  # Bypasses Redis distributed lock
        }
        try:
            r = await client.post(
                f"{API_BASE}/booking",
                json={"slot_id": slot_id, "objectives": "Pure PostgreSQL Row Lock Concurrency Test"},
                headers=req_headers
            )
            return r.status_code, r.text
        except Exception as e:
            return 500, str(e)

    start_time = time.time()
    async with httpx.AsyncClient(timeout=25, limits=httpx.Limits(max_connections=120, max_keepalive_connections=50)) as client:
        tasks = [attempt_booking_pure_pg(l, client) for l in learners]
        results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    successes = [res for code, res in results if code == 201]
    conflicts = [res for code, res in results if code == 409]

    print(f"\n[Pure PostgreSQL Results in {elapsed:.2f}s]")
    print(f"HTTP 201 Success: {len(successes)} | HTTP 409 Conflict: {len(conflicts)}")

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(conflicts) == 99, f"Expected 99 conflicts, got {len(conflicts)}"

    audit = audit_ledger_rpc()
    assert audit["details"]["unbalanced_tx"] == [], f"Found unbalanced transactions: {audit['details']['unbalanced_tx']}"

    await cleanup_concurrency_fixture(mentor_id, learners)


if __name__ == "__main__":
    asyncio.run(test_100_concurrent_bookings_on_single_slot())
    asyncio.run(test_100_concurrent_bookings_pure_postgres_no_redis())
