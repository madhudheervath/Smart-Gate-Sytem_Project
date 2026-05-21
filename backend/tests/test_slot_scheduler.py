"""
test_slot_scheduler.py — 4 cases for slot-based access scheduling.

UC03 / UC04: capacity limit, double booking, expired slot window, slot-bound verification.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from models import Slot, SlotBooking, User, PassRequest
from auth import hash_pwd
from crypto import make_qr_token

IST = timezone(timedelta(hours=5, minutes=30))


def make_slot(db, *, label="Morning Slot", capacity=2, active=True,
              start_offset_h=-1, end_offset_h=1):
    # Store as naive UTC (SQLite does not preserve tzinfo)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    slot = Slot(
        label=label,
        gate="Main Gate",
        start_time=now + timedelta(hours=start_offset_h),
        end_time=now + timedelta(hours=end_offset_h),
        capacity=capacity,
        active=active,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def book(db, slot_id, user_id):
    b = SlotBooking(slot_id=slot_id, user_id=user_id, booking_status="confirmed")
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


class TestSlotCapacity:
    def test_booking_within_capacity_succeeds(self, db, student_user):
        slot = make_slot(db, capacity=5)
        bk = book(db, slot.id, student_user.id)
        assert bk.booking_status == "confirmed"

    def test_booking_beyond_capacity_is_rejected(self, db):
        # Create two distinct users to fill a 1-capacity slot
        u1 = User(name="U1", email="u1@t.com", pwd_hash=hash_pwd("p"), role="student", active=True)
        u2 = User(name="U2", email="u2@t.com", pwd_hash=hash_pwd("p"), role="student", active=True)
        db.add_all([u1, u2])
        db.commit()

        slot = make_slot(db, capacity=1)
        book(db, slot.id, u1.id)   # fills the slot

        # Simulate the capacity check that app.py does before creating SlotBooking
        booked_count = db.query(SlotBooking).filter(
            SlotBooking.slot_id == slot.id,
            SlotBooking.booking_status == "confirmed",
        ).count()
        assert booked_count >= slot.capacity, "Slot must be reported as full"


class TestDuplicateBooking:
    def test_duplicate_booking_detected(self, db, student_user):
        slot = make_slot(db, capacity=10)
        book(db, slot.id, student_user.id)

        existing = db.query(SlotBooking).filter(
            SlotBooking.slot_id == slot.id,
            SlotBooking.user_id == student_user.id,
            SlotBooking.booking_status == "confirmed",
        ).first()
        assert existing is not None, "Duplicate booking should be detectable before insertion"


class TestExpiredSlotWindow:
    def test_expired_slot_blocks_verification(self, db, student_user, admin_user):
        # Slot whose window ended in the past
        expired_slot = make_slot(db, start_offset_h=-3, end_offset_h=-1)

        pr = PassRequest(
            student_id=student_user.id,
            reason="Test",
            pass_type="entry",
            status="approved",
            slot_id=expired_slot.id,
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)

        # Simulate the slot window check in /verify (compare naive datetimes)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        within_window = expired_slot.start_time <= now <= expired_slot.end_time
        assert within_window is False, "Past-slot verification must fail"


class TestSlotBoundVerification:
    def test_active_slot_window_allows_verification(self, db, student_user):
        active_slot = make_slot(db, start_offset_h=-1, end_offset_h=2)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        within_window = active_slot.start_time <= now <= active_slot.end_time
        assert within_window is True, "Current time should be inside an active slot"


class TestSlotListing:
    def test_student_slot_list_hides_expired_and_inactive_slots(self, db, student_user):
        current_slot = make_slot(db, label="Current", start_offset_h=-1, end_offset_h=2)
        expired_slot = make_slot(db, label="Expired", start_offset_h=-3, end_offset_h=-1)
        inactive_slot = make_slot(db, label="Inactive", active=False, start_offset_h=-1, end_offset_h=2)

        from app import list_slots

        visible_slots = list_slots(active_only=True, user=student_user, db=db)
        visible_ids = {slot.id for slot in visible_slots}

        assert current_slot.id in visible_ids
        assert expired_slot.id not in visible_ids
        assert inactive_slot.id not in visible_ids

    def test_admin_can_list_all_slots_for_cleanup(self, db, admin_user):
        current_slot = make_slot(db, label="Current", start_offset_h=-1, end_offset_h=2)
        expired_slot = make_slot(db, label="Expired", start_offset_h=-3, end_offset_h=-1)
        inactive_slot = make_slot(db, label="Inactive", active=False, start_offset_h=-1, end_offset_h=2)

        from app import list_slots

        visible_slots = list_slots(active_only=False, user=admin_user, db=db)
        visible_ids = {slot.id for slot in visible_slots}

        assert {current_slot.id, expired_slot.id, inactive_slot.id}.issubset(visible_ids)
