"""
Unit tests for US-05 (Search mentors by learning goal) and US-07 (View mentor profile).
Acceptance criteria:
- Searching for a skill keyword or learning goal returns relevant mentors.
- Max rate and min rating filters filter results correctly.
- Empty query returns empty results.
- Viewing mentor public profile returns full bio, offered skills, and open slots.
"""
import pytest
from datetime import datetime, timedelta, timezone
from skillswap_ledger import (
    init_db,
    register_or_login_campus_user,
    add_user_skill,
    create_availability_slot,
    search_mentors_by_goal,
    get_mentor_public_profile,
)


@pytest.fixture()
def test_db(tmp_path):
    db_path = str(tmp_path / "search_test.db")
    init_db(db_path)
    return db_path


def test_semantic_mentor_search_and_filtering(test_db):
    # Mentor 1: Python & Backend (rate 2)
    m1 = register_or_login_campus_user("py.mentor@campus.edu", "Python Pro", db_path=test_db)
    add_user_skill(m1["id"], "Python & Backend", "offered", "advanced", hourly_rate_credits=2, db_path=test_db)

    # Mentor 2: React & Frontend (rate 4)
    m2 = register_or_login_campus_user("react.mentor@campus.edu", "React Guru", db_path=test_db)
    add_user_skill(m2["id"], "React & Frontend", "offered", "intermediate", hourly_rate_credits=4, db_path=test_db)

    # Add slot for m1
    now = datetime.now(timezone.utc)
    slot_start = (now + timedelta(days=1, hours=3)).isoformat()
    slot_end = (now + timedelta(days=1, hours=4)).isoformat()
    create_availability_slot(m1["id"], slot_start, slot_end, 2, db_path=test_db)

    # Search for "I want to build backend APIs with Python"
    results = search_mentors_by_goal("I want to build backend APIs with Python", db_path=test_db)
    assert len(results) >= 1
    assert results[0]["mentor_id"] == m1["id"]
    assert results[0]["matched_skill"] == "Python & Backend"
    assert results[0]["next_slot"] is not None

    # Filter by max_rate: max 2 should include m1, exclude m2
    results_filtered = search_mentors_by_goal("frontend react", max_rate=2, db_path=test_db)
    # m2 offers React at 4 credits, so should be filtered out
    assert not any(r["mentor_id"] == m2["id"] for r in results_filtered)


def test_mentor_public_profile_view(test_db):
    m = register_or_login_campus_user("profile.view@campus.edu", "Public Mentor", db_path=test_db)
    add_user_skill(m["id"], "System Design", "offered", "advanced", hourly_rate_credits=3, db_path=test_db)

    now = datetime.now(timezone.utc)
    s_start = (now + timedelta(days=2)).isoformat()
    s_end = (now + timedelta(days=2, hours=1)).isoformat()
    create_availability_slot(m["id"], s_start, s_end, 3, db_path=test_db)

    profile = get_mentor_public_profile(m["id"], db_path=test_db)
    assert profile["id"] == m["id"]
    assert profile["full_name"] == "Public Mentor"
    assert len(profile["offered_skills"]) == 1
    assert profile["offered_skills"][0]["skill_name"] == "System Design"
    assert len(profile["open_slots"]) == 1
    assert profile["open_slots"][0]["rate_credits"] == 3


def test_search_empty_query(test_db):
    results = search_mentors_by_goal("   ", db_path=test_db)
    assert results == []
