"""
PostgreSQL Ledger RPC Test Suite.
Verifies zero-sum double-entry ledger operations against real PostgreSQL RPC functions.
"""

import os
import sys
import uuid
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skillswap_rpc
from skillswap_rpc import (
    SUPABASE_URL,
    SUPABASE_KEY,
    post_transfer_rpc,
    audit_ledger_rpc,
    book_slot_rpc,
    SlotConflictError,
    InsufficientBalanceRPCError,
)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def test_real_postgres_audit_ledger():
    audit = audit_ledger_rpc()
    assert audit["passed"] is True
    assert audit["total_debits"] == audit["total_credits"]
    assert audit["details"]["unbalanced_tx"] == []


def test_real_postgres_post_transfer_atomic():
    # 1. Fetch mint account
    with httpx.Client(timeout=10) as client:
        mint_resp = client.get(f"{SUPABASE_URL}/rest/v1/accounts?kind=eq.mint", headers=headers)
        mint_id = mint_resp.json()[0]["id"]

        # 2. Create test user
        uid = str(uuid.uuid4())
        client.post(f"{SUPABASE_URL}/rest/v1/profiles", json={
            "id": uid,
            "campus_email": f"user_{uid[:8]}@thapar.edu",
            "full_name": "PG Transfer User",
            "role": "peer",
            "status": "active"
        }, headers=headers)

        acc_resp = client.post(f"{SUPABASE_URL}/rest/v1/accounts", json={
            "kind": "user",
            "owner_id": uid,
            "balance": 0
        }, headers=headers)
        user_acc_id = acc_resp.json()[0]["id"]

    # 3. Mint 5 credits via post_transfer_rpc
    tx_id = post_transfer_rpc(mint_id, user_acc_id, 5, "starter_grant", description="RPC Grant")
    assert tx_id is not None

    # 4. Check audit
    audit = audit_ledger_rpc()
    assert audit["passed"] is True
    assert audit["total_debits"] == audit["total_credits"]
