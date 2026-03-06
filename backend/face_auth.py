"""
Face Authentication Module

Production default uses a lightweight OpenCV-based face pipeline so registration
and verification can run on smaller Render instances. A heavier
`face_recognition` backend can still be selected explicitly with
`FACE_AUTH_BACKEND=face_recognition`.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import importlib
import io
import json
import os
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

MAX_FACE_IMAGE_DIMENSION = 960
DEFAULT_FACE_BACKEND = (os.getenv("FACE_AUTH_BACKEND", "opencv") or "opencv").strip().lower()

_cv2_module = None
_face_recognition_module = None
_backend_name = None
_backend_error = None
_haar_classifier = None


def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)


def get_backend_name() -> Optional[str]:
    backend, _ = _resolve_backend()
    return backend


def get_backend_error() -> Optional[str]:
    _, error = _resolve_backend()
    return error


def _import_cv2():
    global _cv2_module
    if _cv2_module is None:
        _cv2_module = importlib.import_module("cv2")
    return _cv2_module


def _import_face_recognition():
    global _face_recognition_module
    if _face_recognition_module is None:
        _face_recognition_module = importlib.import_module("face_recognition")
    return _face_recognition_module


def _resolve_backend() -> Tuple[Optional[str], Optional[str]]:
    global _backend_name, _backend_error

    if _backend_name is not None or _backend_error is not None:
        return _backend_name, _backend_error

    requested = DEFAULT_FACE_BACKEND

    if requested == "face_recognition":
        try:
            _import_face_recognition()
            _backend_name = "face_recognition"
            return _backend_name, None
        except Exception as e:
            _backend_error = f"face_recognition backend unavailable: {e}"
            return None, _backend_error

    if requested == "auto":
        try:
            _import_face_recognition()
            _backend_name = "face_recognition"
            return _backend_name, None
        except Exception:
            pass

    try:
        _import_cv2()
        _backend_name = "opencv"
        return _backend_name, None
    except Exception as e:
        _backend_error = f"opencv backend unavailable: {e}"
        return None, _backend_error


def _load_normalized_image(image_bytes: bytes) -> Tuple[Image.Image, Optional[str]]:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        detected_format = image.format.upper() if image.format else None
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        return image, detected_format
    except Exception as e:
        raise ValueError(f"Invalid image file: {str(e)}") from e


def _resize_for_face_processing(image: Image.Image, max_dimension: int = MAX_FACE_IMAGE_DIMENSION) -> Image.Image:
    processed = image.copy()
    if max(processed.size) > max_dimension:
        processed.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return processed


def _get_haar_classifier():
    global _haar_classifier

    if _haar_classifier is not None:
        return _haar_classifier

    cv2 = _import_cv2()
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    classifier = cv2.CascadeClassifier(cascade_path)
    if classifier.empty():
        raise RuntimeError(f"Failed to load Haar cascade at {cascade_path}")

    _haar_classifier = classifier
    return _haar_classifier


def _detect_largest_face(gray_image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    cv2 = _import_cv2()
    classifier = _get_haar_classifier()

    detection_attempts = [
        gray_image,
        cv2.equalizeHist(gray_image),
    ]

    best_face = None
    best_area = -1

    for candidate in detection_attempts:
        faces = classifier.detectMultiScale(
            candidate,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )
        if len(faces) == 0:
            faces = classifier.detectMultiScale(
                candidate,
                scaleFactor=1.05,
                minNeighbors=4,
                minSize=(60, 60),
            )

        for (x, y, w, h) in faces:
            area = int(w) * int(h)
            if area > best_area:
                best_face = (int(x), int(y), int(w), int(h))
                best_area = area

    return best_face


def _crop_face(gray_image: np.ndarray, face_box: Tuple[int, int, int, int]) -> np.ndarray:
    cv2 = _import_cv2()
    x, y, w, h = face_box
    pad = int(max(w, h) * 0.18)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(gray_image.shape[1], x + w + pad)
    y2 = min(gray_image.shape[0], y + h + pad)
    face_region = gray_image[y1:y2, x1:x2]
    face_region = cv2.equalizeHist(face_region)
    face_region = cv2.resize(face_region, (160, 160), interpolation=cv2.INTER_AREA)
    return face_region


def _rotated_gray_candidates(gray_image: np.ndarray) -> list[np.ndarray]:
    cv2 = _import_cv2()
    height, width = gray_image.shape[:2]
    center = (width / 2.0, height / 2.0)

    candidates = [gray_image]

    for angle in (-18, 18, -32, 32):
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            gray_image,
            rotation_matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        candidates.append(rotated)

    candidates.append(cv2.rotate(gray_image, cv2.ROTATE_90_CLOCKWISE))
    candidates.append(cv2.rotate(gray_image, cv2.ROTATE_90_COUNTERCLOCKWISE))
    return candidates


def _lbp_histogram(face_region: np.ndarray) -> np.ndarray:
    center = face_region[1:-1, 1:-1]
    lbp = np.zeros(center.shape, dtype=np.uint8)

    neighbors = [
        face_region[:-2, :-2],
        face_region[:-2, 1:-1],
        face_region[:-2, 2:],
        face_region[1:-1, 2:],
        face_region[2:, 2:],
        face_region[2:, 1:-1],
        face_region[2:, :-2],
        face_region[1:-1, :-2],
    ]

    for index, neighbor in enumerate(neighbors):
        lbp |= ((neighbor >= center).astype(np.uint8) << index)

    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(np.float32)
    hist /= hist.sum() + 1e-7
    return hist


def _intensity_histogram(face_region: np.ndarray) -> np.ndarray:
    cv2 = _import_cv2()
    hist = cv2.calcHist([face_region], [0], None, [64], [0, 256]).flatten().astype(np.float32)
    hist /= hist.sum() + 1e-7
    return hist


def _template_vector(face_region: np.ndarray) -> np.ndarray:
    cv2 = _import_cv2()
    template = cv2.resize(face_region, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    template /= 255.0
    return template.flatten()


def _extract_opencv_encoding(image_bytes: bytes) -> Optional[dict]:
    cv2 = _import_cv2()

    try:
        image, _ = _load_normalized_image(image_bytes)
        image = _resize_for_face_processing(image)
        gray_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        for candidate in _rotated_gray_candidates(gray_image):
            face_box = _detect_largest_face(candidate)
            if face_box is None:
                continue

            face_region = _crop_face(candidate, face_box)
            return {
                "backend": "opencv_lbp_v1",
                "lbp_hist": _lbp_histogram(face_region).tolist(),
                "intensity_hist": _intensity_histogram(face_region).tolist(),
                "template": _template_vector(face_region).tolist(),
            }

        return None
    except Exception as e:
        print(f"Error extracting OpenCV face encoding: {e}")
        return None


def _extract_face_recognition_encoding(image_bytes: bytes) -> Optional[list]:
    try:
        face_recognition = _import_face_recognition()
        image, _ = _load_normalized_image(image_bytes)
        image = _resize_for_face_processing(image)
        img_array = np.array(image)

        face_locations = face_recognition.face_locations(
            img_array,
            number_of_times_to_upsample=0,
            model="hog",
        )
        if len(face_locations) == 0:
            face_locations = face_recognition.face_locations(
                img_array,
                number_of_times_to_upsample=1,
                model="hog",
            )

        if len(face_locations) == 0:
            return None

        if len(face_locations) > 1:
            areas = [(bottom - top) * (right - left) for top, right, bottom, left in face_locations]
            largest_idx = areas.index(max(areas))
            face_locations = [face_locations[largest_idx]]

        encodings = face_recognition.face_encodings(img_array, face_locations)
        if len(encodings) == 0:
            return None

        return encodings[0].tolist()
    except Exception as e:
        print(f"Error extracting face_recognition encoding: {e}")
        return None


def extract_face_encoding(image_bytes: bytes) -> Optional[object]:
    """
    Extract a face encoding from image bytes.

    Returns either an OpenCV feature dictionary or a 128-D float list from the
    heavier face_recognition backend, depending on configuration.
    """
    backend, error = _resolve_backend()
    if backend is None:
        print(f"Face backend unavailable: {error}")
        return None

    if backend == "face_recognition":
        return _extract_face_recognition_encoding(image_bytes)

    return _extract_opencv_encoding(image_bytes)


def _compare_opencv_encodings(known_encoding: dict, check_encoding: dict, tolerance: float) -> Tuple[bool, float]:
    cv2 = _import_cv2()

    known_lbp = np.array(known_encoding["lbp_hist"], dtype=np.float32)
    check_lbp = np.array(check_encoding["lbp_hist"], dtype=np.float32)
    lbp_distance = float(cv2.compareHist(known_lbp, check_lbp, cv2.HISTCMP_BHATTACHARYYA))

    known_intensity = np.array(known_encoding["intensity_hist"], dtype=np.float32)
    check_intensity = np.array(check_encoding["intensity_hist"], dtype=np.float32)
    intensity_distance = float(
        cv2.compareHist(known_intensity, check_intensity, cv2.HISTCMP_BHATTACHARYYA)
    )

    known_template = np.array(known_encoding["template"], dtype=np.float32)
    check_template = np.array(check_encoding["template"], dtype=np.float32)
    template_distance = float(np.mean(np.abs(known_template - check_template)))

    distance = min(
        max(0.55 * lbp_distance + 0.15 * intensity_distance + 0.30 * template_distance, 0.0),
        1.0,
    )
    is_match = distance <= tolerance
    return is_match, distance


def _compare_face_recognition_encodings(known_encoding: list, check_encoding: list, tolerance: float) -> Tuple[bool, float]:
    try:
        face_recognition = _import_face_recognition()
        known = np.array(known_encoding, dtype=np.float32)
        check = np.array(check_encoding, dtype=np.float32)
        distance = float(face_recognition.face_distance([known], check)[0])
        return distance <= tolerance, distance
    except Exception as e:
        print(f"Error comparing face_recognition encodings: {e}")
        return False, 1.0


def compare_faces(known_encoding: object, check_encoding: object, tolerance: float = 0.6) -> Tuple[bool, float]:
    """
    Compare two stored encodings.

    Supports both the lightweight OpenCV feature dictionary and the original
    128-D float vector format.
    """
    try:
        if isinstance(known_encoding, dict) and isinstance(check_encoding, dict):
            if known_encoding.get("backend") == "opencv_lbp_v1" and check_encoding.get("backend") == "opencv_lbp_v1":
                return _compare_opencv_encodings(known_encoding, check_encoding, tolerance)

        if isinstance(known_encoding, list) and isinstance(check_encoding, list):
            return _compare_face_recognition_encodings(known_encoding, check_encoding, tolerance)

        return False, 1.0
    except Exception as e:
        print(f"Error comparing faces: {e}")
        return False, 1.0


def encoding_to_json(encoding: object) -> str:
    """Convert face encoding to JSON string for storage."""
    return json.dumps(encoding)


def json_to_encoding(json_str: str) -> object:
    """Convert JSON string back to a face encoding structure."""
    return json.loads(json_str)


def validate_image(image_bytes: bytes, max_size_mb: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded image.
    """
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"Image too large ({size_mb:.1f}MB). Maximum {max_size_mb}MB allowed."

    try:
        image, detected_format = _load_normalized_image(image_bytes)

        if detected_format and detected_format not in ["JPEG", "JPG", "PNG", "WEBP"]:
            return False, f"Invalid image format: {detected_format}. Only JPEG, PNG, or WEBP allowed."

        width, height = image.size
        if width < 200 or height < 200:
            return False, f"Image too small ({width}x{height}). Minimum 200x200 required."

        if width > 6000 or height > 6000:
            return False, f"Image too large ({width}x{height}). Maximum 6000x6000 allowed."

        return True, None
    except ValueError as e:
        return False, str(e)


# Face matching confidence levels
CONFIDENCE_LEVELS = {
    "high": (0.0, 0.35, "High confidence match"),
    "medium": (0.35, 0.5, "Medium confidence match"),
    "low": (0.5, 0.65, "Low confidence match"),
    "no_match": (0.65, 1.01, "No match"),
}


def get_confidence_level(distance: float) -> dict:
    """Get confidence level description for a face distance."""
    for level, (min_d, max_d, desc) in CONFIDENCE_LEVELS.items():
        if min_d <= distance < max_d:
            confidence = max(0, min(100, int((1 - distance) * 100)))
            return {
                "level": level,
                "description": desc,
                "confidence_percent": confidence,
                "distance": round(distance, 3),
            }
    return {
        "level": "no_match",
        "description": "No match",
        "confidence_percent": 0,
        "distance": round(distance, 3),
    }
