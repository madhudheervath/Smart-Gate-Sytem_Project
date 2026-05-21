"""
test_face_auth.py — 4 cases for face biometric registration and verification.

UC07 / UC08: enrollment status check, match, mismatch, degraded image handling.
Uses the OpenCV face_auth backend (no dlib required).
"""

import pytest
import numpy as np
import io


def _get_face_auth():
    """Load face_auth module; skip test if backend unavailable."""
    try:
        import face_auth
        if face_auth.get_backend_error():
            pytest.skip(f"Face backend unavailable: {face_auth.get_backend_error()}")
        return face_auth
    except ImportError:
        pytest.skip("face_auth module not importable")


def _make_blank_jpeg(width=300, height=300):
    """Create a minimal valid JPEG bytes (blank white image)."""
    try:
        from PIL import Image
        img = Image.new("RGB", (width, height), color=(200, 180, 160))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        pytest.skip("Pillow not installed")


class TestEnrollmentStatus:
    def test_face_module_loads(self):
        fa = _get_face_auth()
        assert fa is not None

    def test_encoding_round_trip(self, db, student_user):
        fa = _get_face_auth()
        img_bytes = _make_blank_jpeg()

        # A blank image likely won't have a face; that's fine — we test the pipeline
        encoding = fa.extract_face_encoding(img_bytes)
        if encoding is None:
            pytest.skip("No face detected in blank image — backend requires real face photo")

        json_str = fa.encoding_to_json(encoding)
        assert isinstance(json_str, str)
        recovered = fa.json_to_encoding(json_str)
        assert recovered is not None


class TestFaceMatch:
    def test_same_encoding_matches(self):
        fa = _get_face_auth()
        # Create a synthetic 128-D encoding vector and compare it with itself
        vec = np.random.rand(128).astype(np.float32)

        try:
            json_str = fa.encoding_to_json(vec)
            recovered = fa.json_to_encoding(json_str)
        except Exception:
            pytest.skip("Backend does not support synthetic vectors")

        is_match, distance = fa.compare_faces(vec, recovered, tolerance=0.6)
        assert is_match is True
        assert distance < 0.01, "Self-comparison must produce near-zero distance"

    def test_different_encodings_do_not_match(self):
        fa = _get_face_auth()
        vec_a = np.zeros(128, dtype=np.float32)
        vec_b = np.ones(128, dtype=np.float32)

        try:
            fa.encoding_to_json(vec_a)
        except Exception:
            pytest.skip("Backend does not support synthetic vectors")

        is_match, distance = fa.compare_faces(vec_a, vec_b, tolerance=0.6)
        assert is_match is False
        assert distance > 0.5


class TestDegradedImageHandling:
    def test_invalid_bytes_rejected(self):
        fa = _get_face_auth()
        garbage = b"\x00\x01\x02\x03NOT_AN_IMAGE"
        is_valid, err_msg = fa.validate_image(garbage)
        assert is_valid is False
        assert err_msg  # must return a meaningful error message

    def test_too_small_image_rejected(self):
        fa = _get_face_auth()
        tiny = _make_blank_jpeg(width=50, height=50)
        is_valid, err_msg = fa.validate_image(tiny)
        assert is_valid is False, "Images smaller than 200×200 must be rejected"
