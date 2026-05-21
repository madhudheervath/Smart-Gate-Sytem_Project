from pydantic import BaseModel, EmailStr, Field, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

class PassCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    pass_type: str = Field(default="entry", pattern="^(entry|exit)$")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    slot_id: Optional[int] = None

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
    slot_id: Optional[int] = None
    access_mode: Optional[str] = None
    requires_face_check: Optional[bool] = False
    # student details
    student_name: Optional[str] = None
    student_code: Optional[str] = None  # like U22CN361
    student_class: Optional[str] = None
    slot_label: Optional[str] = None
    slot_start_time: Optional[datetime] = None
    slot_end_time: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class VerifyIn(BaseModel):
    token: str

class ScanLogOut(BaseModel):
    id: int
    pass_id: Optional[int] = None
    student_id: int
    scanner_id: Optional[int] = None
    scan_time: datetime
    result: str
    pass_type: Optional[str] = "entry"
    emergency: Optional[bool] = False
    details: Optional[str] = None
    # additional info
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    scanner_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

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


# ── Slot scheduling schemas ───────────────────────────────────────────────────

class SlotCreate(BaseModel):
    label: str = Field(min_length=3, max_length=200)
    gate: str = Field(default="Main Gate", max_length=100)
    start_time: datetime
    end_time: datetime
    capacity: int = Field(default=50, ge=1, le=10000)
    active: bool = True
    gps_required: bool = False
    face_check_required: bool = False

class SlotOut(BaseModel):
    id: int
    label: str
    gate: str
    start_time: datetime
    end_time: datetime
    capacity: int
    active: bool
    gps_required: bool
    face_check_required: bool
    created_at: datetime
    booked_count: Optional[int] = 0
    remaining: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SlotBookingOut(BaseModel):
    id: int
    slot_id: int
    user_id: int
    pass_id: Optional[int] = None
    booking_status: str
    booked_at: datetime
    slot: Optional[SlotOut] = None

    model_config = ConfigDict(from_attributes=True)

class VisitorPassCreate(BaseModel):
    visitor_name: str = Field(min_length=2, max_length=120)
    visitor_phone: Optional[str] = None
    reason: str = Field(min_length=3, max_length=300)
    pass_type: str = Field(default="entry", pattern="^(entry|exit)$")
    slot_id: Optional[int] = None
    ttl_minutes: int = Field(default=60, ge=5, le=1440)


# ── Admin User Management Schemas ─────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(student|guard|admin)$")
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    phone: Optional[str] = None
    guardian_name: Optional[str] = None
    active: bool = True

class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    role: Optional[str] = Field(default=None, pattern="^(student|guard|admin)$")
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    phone: Optional[str] = None
    guardian_name: Optional[str] = None
    active: Optional[bool] = None
    valid_until: Optional[datetime] = None

class AdminUserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    student_id: Optional[str] = None
    student_class: Optional[str] = None
    guardian_name: Optional[str] = None
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    active: bool
    face_registered: bool = False
    face_registered_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    fcm_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
