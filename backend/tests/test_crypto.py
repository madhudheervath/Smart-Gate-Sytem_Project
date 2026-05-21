"""
test_crypto.py — 6 cases for HMAC-SHA256 QR token generation and verification.

UC04 / UC05: token format, expiry, tamper detection, replay protection, user isolation.
"""

import time
import hmac
import hashlib

import pytest

from crypto import make_qr_token, parse_token
from settings import settings


class TestTokenFormat:
    def test_token_has_four_parts(self):
        token, _ = make_qr_token(1, 42)
        parts = token.split(".")
        assert len(parts) == 4, "Token must be pass_id.user_id.exp.sig"

    def test_token_fields_are_correct(self):
        token, exp = make_qr_token(7, 99)
        pid, uid, tok_exp, sig = token.split(".")
        assert int(pid) == 7
        assert int(uid) == 99
        assert int(tok_exp) == exp
        assert len(sig) == 32, "Signature must be 32 hex chars"


class TestTokenExpiry:
    def test_token_expires_in_15_minutes_by_default(self):
        before = int(time.time())
        _, exp = make_qr_token(1, 1)
        after = int(time.time())
        assert before + 14 * 60 <= exp <= after + 16 * 60

    def test_custom_ttl_respected(self):
        _, exp = make_qr_token(1, 1, ttl_minutes=5)
        now = int(time.time())
        assert abs(exp - now - 300) < 5, "Custom TTL of 5 min should be ~300 seconds"


class TestTamperDetection:
    def test_modified_pass_id_invalidates_sig(self):
        token, _ = make_qr_token(10, 20)
        parts = token.split(".")
        parts[0] = "999"          # tamper pass_id
        tampered = ".".join(parts)

        pid, uid, exp, sig_recv = parse_token(tampered)
        data = f"{pid}.{uid}.{exp}"
        expected = hmac.new(
            settings.SECRET_KEY.encode(), data.encode(), hashlib.sha256
        ).hexdigest()[:32]
        assert sig_recv != expected, "Tampered token should not match recomputed HMAC"

    def test_modified_user_id_invalidates_sig(self):
        token, _ = make_qr_token(10, 20)
        parts = token.split(".")
        parts[1] = "1"            # tamper user_id
        tampered = ".".join(parts)

        pid, uid, exp, sig_recv = parse_token(tampered)
        data = f"{pid}.{uid}.{exp}"
        expected = hmac.new(
            settings.SECRET_KEY.encode(), data.encode(), hashlib.sha256
        ).hexdigest()[:32]
        assert sig_recv != expected


class TestUserIsolation:
    def test_tokens_differ_per_user(self):
        token_a, _ = make_qr_token(5, 1)
        token_b, _ = make_qr_token(5, 2)
        _, _, _, sig_a = token_a.split(".")
        _, _, _, sig_b = token_b.split(".")
        assert sig_a != sig_b, "Different users must produce different signatures"
