"""
PostgreSQL Range Exclusion Constraint Verification Test.
Verifies that overlapping availability slots for the same mentor are rejected
by the database engine's EXCLUDE USING gist constraint (SQLSTATE 23P01).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skillswap_rpc
from skillswap_rpc import SUPABASE_URL, SUPABASE_KEY

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


@pytest.mark.asyncio
async def test_slot_overlap_exclusion_constraint():
    async with httpx.AsyncClient(timeout=10) as client:
        # 1. Create a test mentor
        mentor_id = str(uuid.uuid4())
        mentor_email = f"mentor_gist_{mentor_id[:8]}@thapar.edu"
        await client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": mentor_id,
            "campus_email": mentor_email,
            "full_name": "Dr. GiST Index Verifier",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        now = datetime.now(timezone.utc)
        slot1_start = (now + timedelta(days=5, hours=2)).isoformat()
        slot1_end = (now + timedelta(days=5, hours=3)).isoformat()

        # Slot 2 overlaps by 30 minutes
        slot2_start = (now + timedelta(days=5, hours=2, minutes=30)).isoformat()
        slot2_end = (now + timedelta(days=5, hours=3, minutes=30)).isoformat()

        # 2. Insert slot 1 (Must Succeed)
        res1 = await client.post(f"{SUPABASE_URL}/rest/v1/availability_slots", json={
            "mentor_id": mentor_id,
            "start_time": slot1_start,
            "end_time": slot1_end,
            "rate_credits": 2,
            "status": "open"
        }, headers=headers)
        assert res1.status_code == 201, f"First slot insert failed: {res1.text}"

        # 3. Insert overlapping slot 2 (Must be rejected by PostgreSQL EXCLUDE USING gist)
        res2 = await client.post(f"{SUPABASE_URL}/rest/v1/availability_slots", json={
            "mentor_id": mentor_id,
            "start_time": slot2_start,
            "end_time": slot2_end,
            "rate_credits": 2,
            "status": "open"
        }, headers=headers)

        assert res2.status_code == 400 or res2.status_code == 409, f"Expected constraint rejection, got {res2.status_code}"
        error_payload = res2.text.lower()
        assert "exclusion" in error_payload or "conflicts" in error_payload or "23p01" in error_payload or "duplicate" in error_payload, (
            f"Expected PostgreSQL GiST exclusion error message, got: {res2.text}"
        )
        print("\nPostgreSQL EXCLUDE USING gist correctly rejected overlapping slot!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_slot_overlap_exclusion_constraint())
