"""
Integration & API Tests for Sprint 1 Endpoints
Validates US-01 (Campus SSO), US-02 (Skill Profile), and US-04 (Wallet Ledger).
"""
import pytest
from fastapi.testclient import TestClient
from skillswap_backend import app

client = TestClient(app)


def test_campus_sso_flow():
    """US-01: First-time Campus SSO sign-in provisions profile and grants 3 starter credits."""
    payload = {
        "email": "test.learner@thapar.edu",
        "full_name": "Test Learner",
        "department": "Computer Science & Engineering",
        "study_year": 3,
    }
    res = client.post("/auth/campus-sso", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["campus_email"] == "test.learner@thapar.edu"
    assert data["user"]["full_name"] == "Test Learner"
    assert data["user"]["balance"] == 3


def test_campus_sso_invalid_email():
    """US-01: Missing or invalid email returns 400 Bad Request."""
    res = client.post("/auth/campus-sso", json={"email": "invalidemail", "full_name": "Bad"})
    assert res.status_code == 400
    assert "valid campus email" in res.json()["detail"].lower()


def test_auth_me_endpoint():
    """US-01: /auth/me returns the authenticated student profile."""
    # Login
    login_res = client.post("/auth/campus-sso", json={"email": "alice@thapar.edu", "full_name": "Alice"})
    token = login_res.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.json()
    assert me["campus_email"] == "alice@thapar.edu"
    assert me["full_name"] == "Alice"
    assert me["balance"] == 3


def test_profile_skills_management():
    """US-02: Manage skill profile (add teach, add learn, update bio, remove skill)."""
    # 1. Login
    login_res = client.post("/auth/campus-sso", json={"email": "bob@thapar.edu", "full_name": "Bob Dev"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Update bio & department
    update_res = client.put(
        "/profile/me",
        json={"bio": "Passionate about algorithms and web dev", "department": "ECE", "study_year": 4},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["bio"] == "Passionate about algorithms and web dev"
    assert update_res.json()["department"] == "ECE"
    assert update_res.json()["study_year"] == 4

    # 3. Add teaching skill
    add_teach = client.post(
        "/profile/skills",
        json={
            "skill_name": "Data Structures & Algorithms",
            "kind": "offered",
            "level": "advanced",
            "hourly_rate_credits": 2,
            "description": "Graph theory and DP problems",
        },
        headers=headers,
    )
    assert add_teach.status_code == 200
    prof = add_teach.json()
    assert any(s["name"] == "Data Structures & Algorithms" for s in prof["offered_skills"])

    # 4. Add learning skill
    add_learn = client.post(
        "/profile/skills",
        json={
            "skill_name": "Cloud & DevOps",
            "kind": "desired",
            "level": "beginner",
        },
        headers=headers,
    )
    assert add_learn.status_code == 200
    prof = add_learn.json()
    assert any(s["name"] == "Cloud & DevOps" for s in prof["desired_skills"])

    # 5. Delete a skill
    skill_to_remove = [s for s in prof["desired_skills"] if s["name"] == "Cloud & DevOps"][0]
    del_res = client.delete(f"/profile/skills/{skill_to_remove['id']}", headers=headers)
    assert del_res.status_code == 200
    prof_after_del = del_res.json()
    assert not any(s["name"] == "Cloud & DevOps" for s in prof_after_del["desired_skills"])


def test_wallet_and_ledger_endpoints():
    """US-04: View wallet balances and double-entry transaction history."""
    login_res = client.post("/auth/campus-sso", json={"email": "charlie@thapar.edu", "full_name": "Charlie"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    wallet_res = client.get("/wallet/me", headers=headers)
    assert wallet_res.status_code == 200
    wallet = wallet_res.json()
    assert wallet["available_balance"] == 3
    assert wallet["escrow_balance"] == 0
    assert len(wallet["history"]) >= 1
    assert wallet["history"][0]["type"] == "starter_grant"
    assert wallet["history"][0]["delta"] == 3

    # Direct ledger route
    ledger_res = client.get("/wallet/ledger", headers=headers)
    assert ledger_res.status_code == 200
    assert len(ledger_res.json()) >= 1


def test_ledger_audit_endpoint():
    """Zero-Sum Invariant Audit Endpoint Verification."""
    login_res = client.post("/auth/campus-sso", json={"email": "auditor@thapar.edu", "full_name": "Auditor"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    audit_res = client.get("/wallet/audit", headers=headers)
    assert audit_res.status_code == 200
    audit = audit_res.json()
    assert audit["passed"] is True
    assert audit["zero_sum_delta"] == 0
    assert audit["total_debits"] == audit["total_credits"]


def test_unauthorized_access():
    """Protected endpoints reject requests without valid Bearer tokens."""
    res = client.get("/wallet/me")
    assert res.status_code == 401
