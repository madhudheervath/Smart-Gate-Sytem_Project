"""
Policy-level tests for production hardening and slot-bound pass behavior.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import _issue_qr_for_pass, _validate_slot_for_pass, auto_daily_entry
from crypto import parse_token
from models import PassRequest, Slot, SlotBooking
from schemas import DailyEntryCreate


def make_future_slot(db, *, capacity=3, gps_required=False, face_required=False):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    slot = Slot(
        label="Policy Slot",
        gate="Main Gate",
        start_time=now - timedelta(minutes=5),
        end_time=now + timedelta(minutes=30),
        capacity=capacity,
        active=True,
        gps_required=gps_required,
        face_check_required=face_required,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def test_slot_bound_pass_requires_confirmed_booking(db, student_user):
    slot = make_future_slot(db)

    with pytest.raises(HTTPException) as exc:
        _validate_slot_for_pass(db, student_user, slot.id, None, None)

    assert exc.value.status_code == 409


def test_slot_bound_pass_links_booking_and_policy_flags(db, student_user):
    slot = make_future_slot(db, face_required=True)
    booking = SlotBooking(slot_id=slot.id, user_id=student_user.id, booking_status="confirmed")
    db.add(booking)
    db.commit()
    db.refresh(booking)

    resolved_slot, resolved_booking, location_verified, _ = _validate_slot_for_pass(
        db, student_user, slot.id, None, None
    )
    pr = PassRequest(
        student_id=student_user.id,
        reason="Slot access request",
        pass_type="entry",
        status="pending",
        slot_id=resolved_slot.id,
        access_mode="slot-bound",
        requires_face_check=resolved_slot.face_check_required,
        location_verified=location_verified,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    resolved_booking.pass_id = pr.id
    db.commit()

    assert resolved_booking.pass_id == pr.id
    assert pr.access_mode == "slot-bound"
    assert pr.requires_face_check is True


def test_slot_bound_qr_expiry_does_not_exceed_slot_end(db, student_user):
    slot = make_future_slot(db)
    pr = PassRequest(
        student_id=student_user.id,
        reason="Slot access request",
        pass_type="entry",
        status="approved",
        slot_id=slot.id,
        access_mode="slot-bound",
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)

    token, exp = _issue_qr_for_pass(db, pr)
    _, uid, parsed_exp, _ = parse_token(token)
    slot_end_exp = int(slot.end_time.replace(tzinfo=timezone.utc).timestamp())

    assert uid == student_user.id
    assert parsed_exp == exp
    assert exp <= slot_end_exp


def test_daily_entry_requires_gps_when_geofence_enabled(db, student_user, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "GEOFENCE_ENABLED", True)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auto_daily_entry(DailyEntryCreate(pass_type="entry"), user=student_user, db=db))

    assert exc.value.status_code == 400
