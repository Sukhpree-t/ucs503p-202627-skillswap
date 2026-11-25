"""
Unit tests for US-08: Mentor Availability Slots & Rate Publishing.
Acceptance criteria:
- Valid future slot creation succeeds with status 'open'.
- End time <= start time rejected.
- Past slots rejected.
- Conflicting/overlapping slots rejected (exclusion check).
- Rate credits > 0 enforced.
- Slot cancellation updates status to 'cancelled'.
"""
import pytest
from datetime import datetime, timedelta, timezone
from skillswap_ledger import (
    init_db,
    register_or_login_campus_user,
    create_availability_slot,
    get_mentor_slots,
    cancel_availability_slot,
)


@pytest.fixture()
def test_db(tmp_path):
    db_path = str(tmp_path / "slots_test.db")
    init_db(db_path)
    return db_path


def test_create_and_fetch_slot_success(test_db):
    user = register_or_login_campus_user("mentor.slot@campus.edu", "Slot Mentor", db_path=test_db)
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1, hours=2)).isoformat()
    end = (now + timedelta(days=1, hours=3)).isoformat()

    slot = create_availability_slot(
        mentor_id=user["id"],
        start_time=start,
        end_time=end,
        rate_credits=2,
        db_path=test_db,
    )

    assert slot["mentor_id"] == user["id"]
    assert slot["rate_credits"] == 2
    assert slot["status"] == "open"

    slots = get_mentor_slots(user["id"], db_path=test_db)
    assert len(slots) == 1
    assert slots[0]["id"] == slot["id"]


def test_reject_slot_in_past(test_db):
    user = register_or_login_campus_user("past.mentor@campus.edu", "Past Mentor", db_path=test_db)
    now = datetime.now(timezone.utc)
    past_start = (now - timedelta(hours=2)).isoformat()
    past_end = (now - timedelta(hours=1)).isoformat()

    with pytest.raises(ValueError, match="Cannot create availability slots in the past"):
        create_availability_slot(
            mentor_id=user["id"],
            start_time=past_start,
            end_time=past_end,
            rate_credits=1,
            db_path=test_db,
        )


def test_reject_invalid_time_interval(test_db):
    user = register_or_login_campus_user("interval@campus.edu", "Interval Mentor", db_path=test_db)
    now = datetime.now(timezone.utc)
    future_time = (now + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError, match="End time must be after start time"):
        create_availability_slot(
            mentor_id=user["id"],
            start_time=future_time,
            end_time=future_time,  # Equal start and end
            rate_credits=1,
            db_path=test_db,
        )


def test_reject_overlapping_slots(test_db):
    user = register_or_login_campus_user("overlap@campus.edu", "Overlap Mentor", db_path=test_db)
    now = datetime.now(timezone.utc)
    base = now + timedelta(days=2)

    # Slot 1: 10:00 to 12:00
    s1_start = (base.replace(hour=10, minute=0, second=0)).isoformat()
    s1_end = (base.replace(hour=12, minute=0, second=0)).isoformat()
    create_availability_slot(user["id"], s1_start, s1_end, 2, db_path=test_db)

    # Slot 2 (Overlapping: 11:00 to 13:00)
    s2_start = (base.replace(hour=11, minute=0, second=0)).isoformat()
    s2_end = (base.replace(hour=13, minute=0, second=0)).isoformat()
    with pytest.raises(ValueError, match="Slot overlaps with an existing slot"):
        create_availability_slot(user["id"], s2_start, s2_end, 2, db_path=test_db)


def test_cancel_slot(test_db):
    user = register_or_login_campus_user("cancel@campus.edu", "Cancel Mentor", db_path=test_db)
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).isoformat()
    end = (now + timedelta(days=1, hours=1)).isoformat()

    slot = create_availability_slot(user["id"], start, end, 1, db_path=test_db)
    cancelled = cancel_availability_slot(user["id"], slot["id"], db_path=test_db)

    assert cancelled["status"] == "cancelled"
    open_slots = get_mentor_slots(user["id"], status_filter="open", db_path=test_db)
    assert len(open_slots) == 0
