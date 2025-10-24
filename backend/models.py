from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
from database import Base

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True)
    pwd_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # 'student'|'admin'|'guard'
    active = Column(Boolean, default=True)
    
    # Additional student fields
    student_id = Column(String(50), unique=True, nullable=True, index=True)  # e.g., U22CN361
    student_class = Column(String(100), nullable=True)  # e.g., CSE 4 Year
    guardian_name = Column(String(120), nullable=True)
    valid_until = Column(DateTime, nullable=True)  # Student validity period
    
    # Face Authentication fields
    face_encoding = Column(Text, nullable=True)  # JSON string of 128-D face vector
    face_registered = Column(Boolean, default=False)  # Flag if face is registered
    face_registered_at = Column(DateTime, nullable=True)  # When face was registered
    
    # Notification fields
    fcm_token = Column(Text, nullable=True)  # Firebase Cloud Messaging token
    phone = Column(String(20), nullable=True)  # Student phone number
    parent_name = Column(String(120), nullable=True)  # Parent/guardian name
    parent_phone = Column(String(20), nullable=True)  # Parent/guardian phone
    parent_fcm_token = Column(Text, nullable=True)  # Parent FCM token if they have app
    notification_preferences = Column(Text, default='{}')  # JSON preferences
    last_notification_at = Column(DateTime, nullable=True)  # Last notification timestamp

class PassRequest(Base):
    __tablename__ = "passes"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    pass_type = Column(String(10), default="entry")  # entry|exit
    status = Column(String(16), default="pending")  # pending|approved|rejected|used
    request_time = Column(DateTime, default=now_ist)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_time = Column(DateTime, nullable=True)
    expiry_time = Column(DateTime, nullable=True)
    qr_token = Column(Text, nullable=True)  # issued token string
    used_time = Column(DateTime, nullable=True)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # GPS Geofencing fields
    request_latitude = Column(Text, nullable=True)  # GPS lat when requested
    request_longitude = Column(Text, nullable=True)  # GPS lon when requested
    location_verified = Column(Boolean, default=False)  # If location was inside campus
    location_distance_km = Column(Text, nullable=True)  # Distance from campus center

class ScanLog(Base):
    __tablename__ = "scan_logs"
    id = Column(Integer, primary_key=True)
    pass_id = Column(Integer, ForeignKey("passes.id"), index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    scanner_id = Column(Integer, ForeignKey("users.id"))
    scan_time = Column(DateTime, default=now_ist)
    result = Column(String(32))   # success | expired | invalid | replay | not-approved
    pass_type = Column(String(10), default="entry")  # entry|exit
    details = Column(Text, nullable=True)

