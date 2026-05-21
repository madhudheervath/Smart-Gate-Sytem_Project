"""
Shared pytest fixtures for SecureGate test suite.
Uses an in-memory SQLite database so tests never touch production data.
"""

import sys
import os

# Make sure backend/ is on the import path when running pytest from any cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import User, PassRequest, ScanLog, Slot, SlotBooking
from auth import hash_pwd


TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db():
    """Isolated in-memory SQLite session, rolled back after each test."""
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
    user = User(
        name="Test Admin",
        email="admin@test.com",
        pwd_hash=hash_pwd("Admin@1234"),
        role="admin",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def student_user(db):
    user = User(
        name="Test Student",
        email="student@test.com",
        pwd_hash=hash_pwd("Student@1234"),
        role="student",
        student_id="U22CS001",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def guard_user(db):
    user = User(
        name="Test Guard",
        email="guard@test.com",
        pwd_hash=hash_pwd("Guard@1234"),
        role="guard",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def approved_pass(db, student_user, admin_user):
    from crypto import make_qr_token
    pr = PassRequest(
        student_id=student_user.id,
        reason="Test pass",
        pass_type="entry",
        status="pending",
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    token, exp = make_qr_token(pr.id, student_user.id, ttl_minutes=15)
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    pr.status = "approved"
    pr.approved_by = admin_user.id
    pr.qr_token = token
    pr.expiry_time = datetime.fromtimestamp(exp, tz=IST)
    db.commit()
    db.refresh(pr)
    return pr
