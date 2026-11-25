"""
Unit Tests for SkillSwap Zero-Sum Double-Entry Ledger Engine
Verifies >= 70% coverage on the ledger module and money rules.
"""
import os
import pytest
import sqlite3
import uuid

import skillswap_ledger
from skillswap_ledger import (
    init_db,
    post_transfer,
    register_or_login_campus_user,
    get_wallet_summary,
    get_profile_data,
    update_profile,
    add_user_skill,
    delete_user_skill,
    audit_ledger,
    LedgerError,
    InsufficientBalanceError,
)

TEST_DB = "test_ledger_suite.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_zero_sum_invariant_on_init():
    """Initial ledger with mint and escrow accounts must sum to zero."""
    audit = audit_ledger(TEST_DB)
    assert audit["passed"] is True
    assert audit["zero_sum_delta"] == 0
    assert audit["total_debits"] == 0
    assert audit["total_credits"] == 0


def test_starter_credit_minting():
    """New campus student signup allocates starter credits from mint; maintains zero-sum."""
    user = register_or_login_campus_user(
        campus_email="student1@thapar.edu",
        full_name="Rohan Verma",
        department="Computer Science",
        study_year=3,
        starter_credits=3,
        db_path=TEST_DB,
    )
    assert user["balance"] == 3

    wallet = get_wallet_summary(user["id"], db_path=TEST_DB)
    assert wallet["available_balance"] == 3
    assert wallet["escrow_balance"] == 0
    assert len(wallet["history"]) == 1
    assert wallet["history"][0]["type"] == "starter_grant"
    assert wallet["history"][0]["direction"] == "credit"
    assert wallet["history"][0]["amount"] == 3

    audit = audit_ledger(TEST_DB)
    assert audit["passed"] is True
    assert audit["zero_sum_delta"] == 0
    assert audit["total_debits"] == 3
    assert audit["total_credits"] == 3
    assert audit["total_issued"] == 3


def test_transfer_between_peers():
    """Transferring credits from Learner to Mentor updates balances while zero-sum remains 0."""
    learner = register_or_login_campus_user("learner@thapar.edu", "Learner One", db_path=TEST_DB)
    mentor = register_or_login_campus_user("mentor@thapar.edu", "Mentor One", db_path=TEST_DB)

    learner_wallet = get_wallet_summary(learner["id"], db_path=TEST_DB)
    mentor_wallet = get_wallet_summary(mentor["id"], db_path=TEST_DB)

    # Transfer 2 credits
    tx_id = post_transfer(
        from_acc_id=learner_wallet["account_id"],
        to_acc_id=mentor_wallet["account_id"],
        amount=2,
        tx_type="settlement",
        description="Completed 1-hr Python tutoring session",
        db_path=TEST_DB,
    )
    assert tx_id is not None

    updated_learner = get_wallet_summary(learner["id"], db_path=TEST_DB)
    updated_mentor = get_wallet_summary(mentor["id"], db_path=TEST_DB)

    assert updated_learner["available_balance"] == 1
    assert updated_mentor["available_balance"] == 5

    audit = audit_ledger(TEST_DB)
    assert audit["passed"] is True
    assert audit["zero_sum_delta"] == 0
    assert audit["total_debits"] == audit["total_credits"]


def test_insufficient_balance_rejection():
    """User cannot spend more credits than available. Balances must not go negative."""
    user1 = register_or_login_campus_user("u1@thapar.edu", "User 1", db_path=TEST_DB)
    user2 = register_or_login_campus_user("u2@thapar.edu", "User 2", db_path=TEST_DB)

    w1 = get_wallet_summary(user1["id"], db_path=TEST_DB)
    w2 = get_wallet_summary(user2["id"], db_path=TEST_DB)

    # Attempt to transfer 10 credits when user has 3
    with pytest.raises(InsufficientBalanceError):
        post_transfer(
            from_acc_id=w1["account_id"],
            to_acc_id=w2["account_id"],
            amount=10,
            tx_type="settlement",
            db_path=TEST_DB,
        )

    # Balance must remain intact
    w1_after = get_wallet_summary(user1["id"], db_path=TEST_DB)
    assert w1_after["available_balance"] == 3


def test_invalid_transfer_arguments():
    """Negative or zero amounts and invalid accounts must raise LedgerError."""
    user = register_or_login_campus_user("user@thapar.edu", "User", db_path=TEST_DB)
    w = get_wallet_summary(user["id"], db_path=TEST_DB)

    with pytest.raises(LedgerError, match="strictly greater than 0"):
        post_transfer(w["account_id"], str(uuid.uuid4()), 0, "settlement", db_path=TEST_DB)

    with pytest.raises(LedgerError, match="strictly greater than 0"):
        post_transfer(w["account_id"], str(uuid.uuid4()), -5, "settlement", db_path=TEST_DB)

    with pytest.raises(LedgerError, match="Source account.*does not exist"):
        post_transfer(str(uuid.uuid4()), w["account_id"], 1, "settlement", db_path=TEST_DB)

    with pytest.raises(LedgerError, match="Destination account.*does not exist"):
        post_transfer(w["account_id"], str(uuid.uuid4()), 1, "settlement", db_path=TEST_DB)


def test_profile_and_skills_lifecycle():
    """US-02: Manage skill profile (teach/learn skills, update profile, remove skill)."""
    user = register_or_login_campus_user("coder@thapar.edu", "Alice Dev", db_path=TEST_DB)

    # Update profile info
    updated = update_profile(
        user_id=user["id"],
        bio="Full-stack enthusiast",
        department="Software Engineering",
        study_year=4,
        db_path=TEST_DB,
    )
    assert updated["bio"] == "Full-stack enthusiast"
    assert updated["department"] == "Software Engineering"
    assert updated["study_year"] == 4

    # Add offered skill (teach)
    profile = add_user_skill(
        user_id=user["id"],
        skill_name="Python & FastAPI",
        kind="offered",
        level="advanced",
        hourly_rate_credits=2,
        description="Async web development",
        db_path=TEST_DB,
    )
    assert len(profile["offered_skills"]) == 1
    assert profile["offered_skills"][0]["name"] == "Python & FastAPI"
    assert profile["offered_skills"][0]["level"] == "advanced"

    # Add desired skill (learn)
    profile = add_user_skill(
        user_id=user["id"],
        skill_name="Kubernetes & Cloud",
        kind="desired",
        level="beginner",
        db_path=TEST_DB,
    )
    assert len(profile["desired_skills"]) == 1
    assert profile["desired_skills"][0]["name"] == "Kubernetes & Cloud"

    # Remove skill
    skill_id_to_delete = profile["desired_skills"][0]["id"]
    profile_after_delete = delete_user_skill(user["id"], skill_id_to_delete, db_path=TEST_DB)
    assert len(profile_after_delete["desired_skills"]) == 0
    assert len(profile_after_delete["offered_skills"]) == 1


def test_validation_rules():
    """Empty skill names or invalid kinds/levels are rejected with validation errors."""
    user = register_or_login_campus_user("val@thapar.edu", "Val", db_path=TEST_DB)

    with pytest.raises(ValueError, match="Skill name cannot be empty"):
        add_user_skill(user["id"], "  ", "offered", "beginner", db_path=TEST_DB)

    with pytest.raises(ValueError, match="Kind must be 'offered' or 'desired'"):
        add_user_skill(user["id"], "Rust", "invalid_kind", "beginner", db_path=TEST_DB)

    with pytest.raises(ValueError, match="Level must be"):
        add_user_skill(user["id"], "Rust", "offered", "expert", db_path=TEST_DB)
