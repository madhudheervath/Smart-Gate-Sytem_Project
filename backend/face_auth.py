"""
Face Authentication Module
Handles face registration and verification for gate pass system
"""
import face_recognition
import numpy as np
from PIL import Image
import io
import json
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)

def extract_face_encoding(image_bytes: bytes) -> Optional[list]:
    """
    Extract 128-D face encoding from image bytes
    
    Args:
        image_bytes: Raw image file bytes
        
    Returns:
        List of 128 floats representing face encoding, or None if no face detected
    """
    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert PIL Image to numpy array
        img_array = np.array(image)
        
        # Detect faces and get encodings
        face_locations = face_recognition.face_locations(img_array)
        
        if len(face_locations) == 0:
            return None  # No face detected
        
        if len(face_locations) > 1:
            # Multiple faces detected, use the largest one
            areas = [(bottom - top) * (right - left) for top, right, bottom, left in face_locations]
            largest_idx = areas.index(max(areas))
            face_locations = [face_locations[largest_idx]]
        
        # Get face encodings
        encodings = face_recognition.face_encodings(img_array, face_locations)
        
        if len(encodings) == 0:
            return None
        
        # Return first encoding as list (128-D vector)
        return encodings[0].tolist()
        
    except Exception as e:
        print(f"Error extracting face encoding: {e}")
        return None

def compare_faces(known_encoding: list, check_encoding: list, tolerance: float = 0.6) -> Tuple[bool, float]:
    """
    Compare two face encodings
    
    Args:
        known_encoding: Stored face encoding (128-D list)
        check_encoding: New face encoding to verify (128-D list)
        tolerance: Threshold for match (default 0.6, lower is stricter)
        
    Returns:
        Tuple of (is_match: bool, distance: float)
    """
    try:
        # Convert to numpy arrays
        known = np.array(known_encoding)
        check = np.array(check_encoding)
        
        # Calculate face distance (Euclidean distance)
        distance = face_recognition.face_distance([known], check)[0]
        
        # Match if distance is below tolerance
        is_match = distance <= tolerance
        
        return is_match, float(distance)
        
    except Exception as e:
        print(f"Error comparing faces: {e}")
        return False, 1.0

def encoding_to_json(encoding: list) -> str:
    """Convert face encoding list to JSON string for storage"""
    return json.dumps(encoding)

def json_to_encoding(json_str: str) -> list:
    """Convert JSON string back to face encoding list"""
    return json.loads(json_str)

def validate_image(image_bytes: bytes, max_size_mb: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded image
    
    Args:
        image_bytes: Raw image bytes
        max_size_mb: Maximum allowed file size in MB
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    # Check file size
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"Image too large ({size_mb:.1f}MB). Maximum {max_size_mb}MB allowed."
    
    # Check if valid image
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Check format
        if image.format not in ['JPEG', 'PNG', 'JPG']:
            return False, f"Invalid image format: {image.format}. Only JPEG/PNG allowed."
        
        # Check dimensions
        width, height = image.size
        if width < 200 or height < 200:
            return False, f"Image too small ({width}x{height}). Minimum 200x200 required."
        
        if width > 4000 or height > 4000:
            return False, f"Image too large ({width}x{height}). Maximum 4000x4000 allowed."
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

# Face matching confidence levels
CONFIDENCE_LEVELS = {
    "high": (0.0, 0.4, "High confidence match"),
    "medium": (0.4, 0.6, "Medium confidence match"),
    "low": (0.6, 0.8, "Low confidence match"),
    "no_match": (0.8, 1.0, "No match")
}

def get_confidence_level(distance: float) -> dict:
    """Get confidence level description for a face distance"""
    for level, (min_d, max_d, desc) in CONFIDENCE_LEVELS.items():
        if min_d <= distance < max_d:
            confidence = max(0, min(100, int((1 - distance) * 100)))
            return {
                "level": level,
                "description": desc,
                "confidence_percent": confidence,
                "distance": round(distance, 3)
            }
    return {
        "level": "no_match",
        "description": "No match",
        "confidence_percent": 0,
        "distance": round(distance, 3)
    }
