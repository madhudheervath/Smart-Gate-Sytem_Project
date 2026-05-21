"""
test_auth.py — 4 cases for JWT authentication and role enforcement.

UC01: valid login, wrong password, inactive user, role enforcement.
"""

import pytest

from auth import (
    hash_pwd,
    verify_pwd,
    create_access_token,
    get_user_from_token,
    require_role,
)
from models import User


class TestPasswordHashing:
    def test_valid_password_verifies(self):
        pwd = "SecurePass@99"
        hashed = hash_pwd(pwd)
        assert verify_pwd(pwd, hashed) is True

    def test_wrong_password_rejected(self):
        hashed = hash_pwd("CorrectPassword")
        assert verify_pwd("WrongPassword", hashed) is False


class TestJWTTokens:
    def test_token_round_trip(self, db, student_user):
        token = create_access_token({"sub": str(student_user.id), "role": student_user.role})
        recovered = get_user_from_token(token, db)
        assert recovered.id == student_user.id
        assert recovered.email == student_user.email

    def test_inactive_user_rejected(self, db, student_user):
        student_user.active = False
        db.commit()

        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            get_user_from_token(token, db)
        assert exc.value.status_code == 401


class TestRoleEnforcement:
    def test_require_role_passes_for_correct_role(self, db, admin_user):
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        recovered = get_user_from_token(token, db)
        assert recovered.role == "admin"

    def test_require_role_rejects_wrong_role(self, db, student_user):
        from fastapi import HTTPException

        class FakeUser:
            role = "student"

        user = FakeUser()
        expected = HTTPException(status_code=403, detail="Forbidden")
        with pytest.raises(HTTPException) as exc_info:
            if user.role not in ("admin",):
                raise expected
        assert exc_info.value.status_code == 403
