"""
US-02 Follow-up audit – Q6:
Verify that add_user_skill() sets embedding_stale = True on every write.
"""
import os
import tempfile
import pytest

from skillswap_ledger import (
    init_db,
    register_or_login_campus_user,
    add_user_skill,
    get_profile_data,
)


@pytest.fixture()
def test_db(tmp_path):
    db_path = str(tmp_path / "stale_test.db")
    init_db(db_path)
    return db_path


def test_add_skill_sets_embedding_stale_true(test_db):
    """After add_user_skill(), embedding_stale must be True for the saved skill."""
    user = register_or_login_campus_user(
        "stale_tester@campus.edu", "Stale Tester", db_path=test_db
    )

    profile = add_user_skill(
        user_id=user["id"],
        skill_name="Machine Learning",
        kind="offered",
        level="intermediate",
        db_path=test_db,
    )

    offered = profile["offered_skills"]
    assert len(offered) == 1, "Expected exactly one offered skill"
    skill = offered[0]
    assert skill.get("embedding_stale") is True, (
        f"embedding_stale must be True after add_user_skill(); got: {skill.get('embedding_stale')}"
    )


def test_update_skill_keeps_embedding_stale_true(test_db):
    """Updating an existing skill via add_user_skill() must reset embedding_stale = True."""
    user = register_or_login_campus_user(
        "stale_updater@campus.edu", "Stale Updater", db_path=test_db
    )

    # First add
    add_user_skill(
        user_id=user["id"],
        skill_name="Docker",
        kind="offered",
        level="beginner",
        db_path=test_db,
    )

    # Update (same skill name, same kind → upsert)
    profile = add_user_skill(
        user_id=user["id"],
        skill_name="Docker",
        kind="offered",
        level="advanced",
        db_path=test_db,
    )

    offered = profile["offered_skills"]
    assert len(offered) == 1, "Upsert should not duplicate the skill row"
    assert offered[0]["level"] == "advanced", "Level must be updated"
    assert offered[0].get("embedding_stale") is True, (
        "embedding_stale must remain True after skill update"
    )


def test_get_profile_data_returns_embedding_stale(test_db):
    """get_profile_data() must include embedding_stale in the returned skill dict."""
    user = register_or_login_campus_user(
        "stale_read@campus.edu", "Stale Reader", db_path=test_db
    )
    add_user_skill(
        user_id=user["id"],
        skill_name="Rust",
        kind="desired",
        level="beginner",
        db_path=test_db,
    )

    profile = get_profile_data(user["id"], db_path=test_db)
    desired = profile["desired_skills"]
    assert len(desired) == 1
    assert "embedding_stale" in desired[0], (
        "get_profile_data() must return embedding_stale field on each skill"
    )
    assert desired[0]["embedding_stale"] is True
