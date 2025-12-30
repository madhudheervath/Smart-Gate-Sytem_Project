from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    guardian_name: Optional[str] = None
    valid_until: Optional[datetime] = None
    face_registered: bool = False
    face_registered_at: Optional[datetime] = None
    # Contact information for notifications
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    fcm_token: Optional[str] = None
    parent_fcm_token: Optional[str] = None
    class Config:
        from_attributes = True

class PassCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    pass_type: str = Field(default="entry", pattern="^(entry|exit)$")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class DailyEntryCreate(BaseModel):
    pass_type: str = Field(default="entry", pattern="^(entry|exit)$")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class PassOut(BaseModel):
    id: int
    student_id: int
    reason: str
    status: str
    pass_type: str = "entry"
    request_time: datetime
    approved_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    qr_token: Optional[str] = None
    used_time: Optional[datetime] = None
    # student details
    student_name: Optional[str] = None
    student_code: Optional[str] = None  # like U22CN361
    student_class: Optional[str] = None
    class Config:
        from_attributes = True

class VerifyIn(BaseModel):
    token: str

class ScanLogOut(BaseModel):
    id: int
    pass_id: int
    student_id: int
    scanner_id: int
    scan_time: datetime
    result: str
    details: Optional[str] = None
    # additional info
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    scanner_name: Optional[str] = None
    class Config:
        from_attributes = True

# Face Authentication Schemas
class FaceRegistrationResponse(BaseModel):
    status: str
    message: str
    face_registered: bool
    registered_at: Optional[datetime] = None

class FaceVerificationRequest(BaseModel):
    student_id: int

class FaceVerificationResponse(BaseModel):
    verified: bool
    confidence_level: str
    confidence_percent: int
    distance: float
    message: str

