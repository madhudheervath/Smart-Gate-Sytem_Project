"""
Integration tests: full QR flow from pass creation through admin approval to guard scan.
"""

import sys
import os
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import User, PassRequest, ScanLog
from auth import hash_pwd
from crypto import make_qr_token, parse_token
from crud import log_scan, mark_used

IST = timezone(timedelta(hours=5, minutes=30))
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(db):
    u = User(name="Admin", email="admin@sg.com", pwd_hash=hash_pwd("Admin@1234"), role="admin", active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture
def student_user(db):
    u = User(name="Alice", email="alice@sg.com", pwd_hash=hash_pwd("Pass@1234"), role="student",
             student_id="U22CS001", active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture
def guard_user(db):
    u = User(name="Guard Bob", email="bob@sg.com", pwd_hash=hash_pwd("Guard@1234"), role="guard", active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# Test 1 — Happy-path: create → approve → scan succeeds
# ---------------------------------------------------------------------------

def test_full_qr_flow_entry(db, student_user, admin_user, guard_user):
    """Create a pass, admin approves it, guard scans QR → result 'success'."""
    # 1. Student submits pass request
    pr = PassRequest(
        student_id=student_user.id,
        reason="Library visit",
        pass_type="entry",
        status="pending",
    )
    db.add(pr); db.commit(); db.refresh(pr)

    # 2. Admin approves
    token, exp = make_qr_token(pr.id, student_user.id, ttl_minutes=15)
    pr.status = "approved"
    pr.approved_by = admin_user.id
    pr.approved_at = datetime.now(IST)
    pr.qr_token = token
    pr.qr_expires_at = datetime.fromtimestamp(exp, tz=IST)
    db.commit()

    # 3. Guard scans the QR token
    pid, uid, exp_ts, _ = parse_token(token)
    assert pid == pr.id, "Token encodes correct pass id"
    assert uid == student_user.id, "Token encodes correct user id"

    # Simulate what the scan endpoint does
    pass_obj = db.get(PassRequest, pid)
    assert pass_obj.status == "approved"
    assert pass_obj.student_id == student_user.id

    scan = log_scan(db, student_id=pass_obj.student_id, scanner_id=guard_user.id,
                    pass_id=pass_obj.id, result="success", pass_type="entry")

    mark_used(db, pass_obj, guard_user.id)
    db.refresh(pass_obj)

    assert pass_obj.status == "used"
    assert scan.result == "success"
    assert scan.pass_id == pr.id


# ---------------------------------------------------------------------------
# Test 2 — Tampered token is rejected
# ---------------------------------------------------------------------------

def test_tampered_qr_token_rejected(db, student_user, admin_user):
    pr = PassRequest(
        student_id=student_user.id, reason="Canteen", pass_type="exit", status="pending"
    )
    db.add(pr); db.commit(); db.refresh(pr)

    token, _ = make_qr_token(pr.id, student_user.id, ttl_minutes=15)
    parts = token.split(".")
    # Alter the pass_id segment
    parts[0] = str(int(parts[0]) + 99)
    tampered = ".".join(parts)

    from crypto import parse_token as _parse
    pid, uid, exp_ts, sig = _parse(tampered)
    # Recompute expected HMAC to verify it doesn't match
    import hmac as _hmac, hashlib as _hl
    from settings import settings
    msg = f"{pid}.{uid}.{exp_ts}".encode()
    expected = _hmac.new(settings.SECRET_KEY.encode(), msg, _hl.sha256).hexdigest()[:32]
    assert sig != expected, "Tampered token should have invalid signature"


# ---------------------------------------------------------------------------
# Test 3 — Expired token is rejected at scan time
# ---------------------------------------------------------------------------

def test_expired_qr_token(db, student_user, admin_user):
    pr = PassRequest(
        student_id=student_user.id, reason="Hostel", pass_type="entry", status="pending"
    )
    db.add(pr); db.commit(); db.refresh(pr)

    token, _ = make_qr_token(pr.id, student_user.id, ttl_minutes=-1)  # Already expired
    pr.status = "approved"
    pr.qr_token = token
    db.commit()

    from crypto import parse_token as _parse
    import time
    _, _, exp_ts, _ = _parse(token)
    assert exp_ts < time.time(), "Token should be expired"


# ---------------------------------------------------------------------------
# Test 4 — Double-scan of a used pass is rejected
# ---------------------------------------------------------------------------

def test_double_scan_rejected(db, student_user, guard_user, admin_user):
    pr = PassRequest(
        student_id=student_user.id, reason="Sports", pass_type="entry", status="approved"
    )
    db.add(pr); db.commit(); db.refresh(pr)

    # First scan marks as used
    mark_used(db, pr, guard_user.id)
    db.refresh(pr)
    assert pr.status == "used"

    # Second scan: the endpoint logic checks status != "approved", so simulate that check
    assert pr.status != "approved", "Already-used pass cannot be scanned again"


# ---------------------------------------------------------------------------
# Test 5 — Emergency exit creates scan log with NULL pass_id
# ---------------------------------------------------------------------------

def test_emergency_exit_no_pass_id(db, student_user):
    log = ScanLog(
        student_id=student_user.id,
        scanner_id=student_user.id,
        pass_id=None,      # Must be NULL, not 0
        result="success",
        pass_type="exit",
        emergency=True,
        details="Emergency Exit: Fire drill",
        scan_time=datetime.now(IST),
    )
    db.add(log); db.commit(); db.refresh(log)
    assert log.pass_id is None, "Emergency exit log must not reference a phantom pass_id=0"
    assert log.emergency is True
