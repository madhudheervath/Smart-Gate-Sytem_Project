from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "student"
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    phone: Optional[str] = None

class RegistrationRequestCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    requested_role: str = Field(default="personnel", pattern="^(personnel|student|guard)$")
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    phone: Optional[str] = None
    request_reason: Optional[str] = Field(default=None, max_length=500)

class UserRegister(RegistrationRequestCreate):
    pass

class RegistrationRequestAck(BaseModel):
    request_id: int
    status: str
    message: str

class RegistrationRequestReview(BaseModel):
    approved_role: Optional[str] = Field(default=None, pattern="^(personnel|student|guard)$")
    review_notes: Optional[str] = Field(default=None, max_length=500)

class RegistrationRequestOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    requested_role: str
    approved_role: Optional[str] = None
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    phone: Optional[str] = None
    request_reason: Optional[str] = None
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    review_notes: Optional[str] = None
    created_user_id: Optional[int] = None

    class Config:
        from_attributes = True

class FCMTokenRegister(BaseModel):
    fcm_token: str

class ContactUpdate(BaseModel):
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None

class ParentFCMRegister(BaseModel):
    student_id: str
    parent_name: str
    parent_phone: Optional[str] = None
    parent_fcm_token: Optional[str] = None
    access_token: str

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
    pass_id: Optional[int] = None
    student_id: int
    scanner_id: Optional[int] = None
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
