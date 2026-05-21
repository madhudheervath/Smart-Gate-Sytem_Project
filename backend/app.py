
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from database import Base, engine, get_db, SessionLocal
from models import User, RegistrationRequest, PassRequest, ScanLog
from schemas import *
from schemas import UserRegister, AdminUserCreate, AdminUserUpdate, AdminUserOut
from models import Slot, SlotBooking
from runtime_schema import ensure_runtime_schema
from auth import (
    hash_pwd,
    verify_pwd,
    create_access_token,
    create_parent_access_token,
    get_current_user,
    get_user_from_token,
    require_role,
    verify_parent_access_token,
)
from crypto import make_qr_token, make_qr_token_until, parse_token
from settings import settings
from crud import log_scan, mark_used
from fastapi.security import OAuth2PasswordRequestForm
import hmac
import hashlib
import importlib
import io
import os

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

# Rate limiting (OWASP A7 - brute force protection)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING_ENABLED = True
except ImportError:
    RATE_LIMITING_ENABLED = False
    limiter = None

# Optional imports - disable if not installed or explicitly turned off via env
FACE_AUTH_ENABLED = settings.FACE_AUTH_ENABLED
_face_auth_module = None
_face_auth_import_error = None
FACE_PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "face_previews")
# Pre-create directory at startup so enrollment thumbnails are never lost silently
os.makedirs(FACE_PREVIEW_DIR, exist_ok=True)

if FACE_AUTH_ENABLED:
    print(f"✅ Face authentication enabled by configuration (backend={settings.FACE_AUTH_BACKEND}); face stack will load on demand")
else:
    print("⚠️  Face authentication disabled by configuration")


def _face_preview_path(user_id: int) -> str:
    return os.path.join(FACE_PREVIEW_DIR, f"user_{int(user_id)}.jpg")


def _save_face_preview(user_id: int, image_bytes: bytes) -> None:
    """Persist a small display-only enrollment thumbnail."""
    if Image is None or ImageOps is None:
        return
    try:
        os.makedirs(FACE_PREVIEW_DIR, exist_ok=True)
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((512, 512))
        image.save(_face_preview_path(user_id), format="JPEG", quality=82, optimize=True)
    except Exception as e:
        print(f"⚠️  Could not save face preview for user {user_id}: {e}")


def _delete_face_preview(user_id: int) -> None:
    try:
        path = _face_preview_path(user_id)
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"⚠️  Could not delete face preview for user {user_id}: {e}")

if settings.NOTIFICATIONS_ENABLED:
    try:
        import notifications_v2 as notifications
        NOTIFICATIONS_ENABLED = True
        print("✅ Notifications module loaded successfully")
    except Exception as e:
        NOTIFICATIONS_ENABLED = False
        print(f"⚠️  Notifications disabled: {e}")
else:
    NOTIFICATIONS_ENABLED = False
    print("⚠️  Notifications disabled by configuration")

try:
    import realtime_logs
    REALTIME_LOGS_ENABLED = True
    print("✅ Real-time logs module loaded successfully")
except Exception as e:
    REALTIME_LOGS_ENABLED = False
    print(f"⚠️  Real-time logs disabled: {e}")

if settings.GEOFENCE_ENABLED:
    try:
        import geofence
        import location_settings
        GEOFENCE_ENABLED = True
    except ImportError:
        GEOFENCE_ENABLED = False
        print("⚠️  GPS geofencing disabled - install shapely and geopy to enable")
        print("    Run: pip install shapely geopy")
else:
    GEOFENCE_ENABLED = False
    print("⚠️  GPS geofencing disabled by configuration")


def get_face_auth_module():
    global _face_auth_module, _face_auth_import_error

    if not FACE_AUTH_ENABLED:
        return None

    if _face_auth_module is not None:
        return _face_auth_module

    if _face_auth_import_error is not None:
        return None

    try:
        _face_auth_module = importlib.import_module("face_auth")
        backend_name = getattr(_face_auth_module, "get_backend_name", lambda: settings.FACE_AUTH_BACKEND)()
        backend_error = getattr(_face_auth_module, "get_backend_error", lambda: None)()
        if backend_name:
            print(f"✅ Face authentication module loaded successfully (backend={backend_name})")
        elif backend_error:
            _face_auth_import_error = backend_error
            print(f"⚠️  Face authentication backend unavailable: {backend_error}")
            return None
        return _face_auth_module
    except Exception as e:
        _face_auth_import_error = str(e)
        print(f"⚠️  Face authentication unavailable: {e}")
        return None


def _decode_face_encoding(face_auth_module, encoding_json: Optional[str]):
    if not encoding_json:
        return None

    try:
        return face_auth_module.json_to_encoding(encoding_json)
    except Exception as e:
        print(f"⚠️  Failed to decode stored face encoding: {e}")
        return None


def _find_duplicate_face_registration(db: Session, user: User, encoding: object, face_auth_module):
    duplicate_tolerance = getattr(face_auth_module, "get_duplicate_tolerance", lambda _=None: 0.18)(encoding)
    candidates = db.query(User).filter(
        User.id != user.id,
        User.face_registered == True,
        User.face_encoding.isnot(None),
    ).all()

    for candidate in candidates:
        candidate_encoding = _decode_face_encoding(face_auth_module, candidate.face_encoding)
        if candidate_encoding is None:
            continue

        if getattr(face_auth_module, "requires_reenrollment", lambda _: False)(candidate_encoding):
            continue

        is_match, distance = face_auth_module.compare_faces(
            candidate_encoding,
            encoding,
            tolerance=duplicate_tolerance,
        )
        if is_match:
            print(
                f"⚠️  Duplicate face registration blocked for {user.email}; "
                f"matched existing user #{candidate.id} at distance {distance:.3f}"
            )
            return candidate, distance

    return None, None

# Campus local timezone — configurable via CAMPUS_TZ_OFFSET_HOURS env var (default UTC)
CAMPUS_TZ = timezone(timedelta(seconds=int(settings.CAMPUS_TZ_OFFSET_HOURS * 3600)))

def now_local():
    """Get current time in campus local timezone"""
    return datetime.now(CAMPUS_TZ)

app = FastAPI(title="Smart Gate System")

# Register rate limit exceeded handler
if RATE_LIMITING_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/debug/users")
def list_users(
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if not settings.ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")
    users = db.query(User).all()
    return [
        {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "student_id": u.student_id, "active": u.active}
        for u in users
    ]

@app.get("/debug/check_password")
def debug_check_password(
    email: str,
    password: str,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if not settings.ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"status": "error", "message": "User not found"}
    
    is_valid = verify_pwd(password, user.pwd_hash)
    return {
        "status": "success" if is_valid else "failed",
        "email": user.email,
        "is_valid": is_valid,
    }

# CORS middleware for web frontend
# Allow all origins for development; tighten in production via ALLOWED_ORIGINS env var
_ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
if settings.APP_ENV.lower() in {"production", "prod"}:
    default_secret_values = {
        "change_me_32+_random_secret_key_here",
        "change_me_jwt_secret_key_here",
    }
    if settings.SECRET_KEY in default_secret_values or settings.JWT_SECRET in default_secret_values:
        raise RuntimeError("Production requires non-default SECRET_KEY and JWT_SECRET")
    if "*" in _ALLOWED_ORIGINS:
        raise RuntimeError("Production requires explicit ALLOWED_ORIGINS; '*' is not allowed")
    if settings.DB_URL.startswith("sqlite:///"):
        raise RuntimeError("Production should use PostgreSQL via DATABASE_URL/DB_URL")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# create tables
Base.metadata.create_all(bind=engine)
ensure_runtime_schema(engine)

ALLOWED_ACCOUNT_REQUEST_ROLES = {"personnel", "student", "guard"}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_account_request_role(role: Optional[str]) -> str:
    normalized = (role or "personnel").strip().lower()
    if normalized == "student":
        return "personnel"
    return normalized


def _account_request_role_to_user_role(role: Optional[str]) -> str:
    normalized = _normalize_account_request_role(role)
    return "guard" if normalized == "guard" else "student"


def _user_role_to_account_request_role(role: Optional[str]) -> Optional[str]:
    if role is None:
        return None
    normalized = role.strip().lower()
    if normalized == "student":
        return "personnel"
    return normalized


def _account_request_role_label(role: Optional[str], *, title_case: bool = False) -> str:
    normalized = _normalize_account_request_role(role)
    label = "security guard" if normalized == "guard" else "authorized personnel"
    return label.title() if title_case else label


def _build_valid_until(role: str) -> Optional[datetime]:
    if role != "student":
        return None
    current_year = now_local().year
    return datetime(current_year + 1, 6, 30, tzinfo=CAMPUS_TZ)


def _to_utc_naive(value: datetime) -> datetime:
    """Normalize stored slot times for reliable SQLite/PostgreSQL comparisons."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slot_reserved_count(db: Session, slot_id: int) -> int:
    booking_count = db.query(SlotBooking).filter(
        SlotBooking.slot_id == slot_id,
        SlotBooking.booking_status == "confirmed",
    ).count()
    visitor_count = db.query(PassRequest).filter(
        PassRequest.slot_id == slot_id,
        PassRequest.access_mode == "visitor",
        PassRequest.status.in_(["pending", "approved"]),
    ).count()
    return booking_count + visitor_count


def _confirmed_booking_for_slot(db: Session, user_id: int, slot_id: int) -> Optional[SlotBooking]:
    return db.query(SlotBooking).filter(
        SlotBooking.slot_id == slot_id,
        SlotBooking.user_id == user_id,
        SlotBooking.booking_status == "confirmed",
    ).first()


def _validate_slot_for_booking(db: Session, slot_id: int) -> Slot:
    slot = db.get(Slot, slot_id)
    if not slot or not slot.active:
        raise HTTPException(404, "Slot not found or inactive")
    if _to_utc_naive(slot.end_time) <= _now_utc_naive():
        raise HTTPException(400, "Slot window has already ended")
    return slot


def _validate_slot_for_pass(
    db: Session,
    user: User,
    slot_id: int,
    latitude: Optional[float],
    longitude: Optional[float],
) -> tuple[Slot, SlotBooking, bool, Optional[str]]:
    slot = _validate_slot_for_booking(db, slot_id)
    booking = _confirmed_booking_for_slot(db, user.id, slot_id)
    if not booking:
        raise HTTPException(409, "Book this slot before requesting a slot-bound pass")
    if booking.pass_id:
        raise HTTPException(409, "This slot booking is already linked to a pass")

    if _slot_reserved_count(db, slot_id) > slot.capacity:
        raise HTTPException(409, "Slot is over capacity. Please choose another slot.")

    location_verified = False
    location_distance = None
    if slot.gps_required:
        if not GEOFENCE_ENABLED:
            raise HTTPException(503, "GPS policy is unavailable")
        if latitude is None or longitude is None:
            raise HTTPException(400, "This slot requires GPS location verification")
        is_valid, message, details = geofence.validate_student_location(latitude, longitude)
        location_verified = is_valid
        location_distance = str(details.get("distance_km", ""))
        if not is_valid:
            raise HTTPException(403, f"Location verification failed: {message}")

    return slot, booking, location_verified, location_distance


def _pass_expiry_is_active(pass_obj: PassRequest) -> bool:
    if not pass_obj.expiry_time:
        return False
    expiry = pass_obj.expiry_time
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=CAMPUS_TZ)
    return expiry > now_local()


def _issue_qr_for_pass(db: Session, pass_obj: PassRequest) -> tuple[str, int]:
    if pass_obj.slot_id:
        slot = db.get(Slot, pass_obj.slot_id)
        if not slot:
            raise HTTPException(400, "Slot-bound pass references a missing slot")
        slot_end = _to_utc_naive(slot.end_time).replace(tzinfo=timezone.utc)
        exp = min(
            int((datetime.now(timezone.utc) + timedelta(minutes=settings.QR_TTL_MINUTES)).timestamp()),
            int(slot_end.timestamp()),
        )
        if exp <= int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(400, "Slot window has already ended")
        return make_qr_token_until(pass_obj.id, pass_obj.student_id, exp)
    return make_qr_token(pass_obj.id, pass_obj.student_id)


def _pass_to_out_dict(db: Session, pass_obj: PassRequest) -> dict:
    pass_dict = {
        "id": pass_obj.id,
        "student_id": pass_obj.student_id,
        "reason": pass_obj.reason,
        "status": pass_obj.status,
        "pass_type": pass_obj.pass_type or "entry",
        "request_time": pass_obj.request_time,
        "approved_time": pass_obj.approved_time,
        "expiry_time": pass_obj.expiry_time,
        "qr_token": pass_obj.qr_token,
        "used_time": pass_obj.used_time,
        "slot_id": pass_obj.slot_id,
        "access_mode": pass_obj.access_mode,
        "requires_face_check": bool(pass_obj.requires_face_check),
    }
    student = db.get(User, pass_obj.student_id)
    if student:
        pass_dict["student_name"] = student.name
        pass_dict["student_code"] = student.student_id
        pass_dict["student_class"] = student.student_class
    if pass_obj.slot_id:
        slot = db.get(Slot, pass_obj.slot_id)
        if slot:
            pass_dict["slot_label"] = slot.label
            pass_dict["slot_start_time"] = slot.start_time
            pass_dict["slot_end_time"] = slot.end_time
    return pass_dict


def _get_latest_registration_request(db: Session, email: str) -> Optional[RegistrationRequest]:
    return (
        db.query(RegistrationRequest)
        .filter(RegistrationRequest.email == email)
        .order_by(RegistrationRequest.created_at.desc(), RegistrationRequest.id.desc())
        .first()
    )


def _notify_admins_of_registration_request(db: Session, request: RegistrationRequest) -> None:
    if not NOTIFICATIONS_ENABLED:
        return

    try:
        admin_users = db.query(User).filter(User.role == "admin", User.fcm_token.isnot(None)).all()
        admin_tokens = [admin.fcm_token for admin in admin_users if admin.fcm_token]
        if admin_tokens:
            notifications.notify_admin_registration_request(
                admin_tokens,
                request.name,
                request.email,
                _normalize_account_request_role(request.requested_role),
            )
            print(f"✅ Notified {len(admin_tokens)} admin(s) of registration request #{request.id}")
    except Exception as e:
        print(f"⚠️  Registration notification error: {e}")


def _serialize_registration_request(db: Session, request: RegistrationRequest) -> RegistrationRequestOut:
    reviewer_name = None
    approved_role = None

    if request.reviewed_by:
        reviewer = db.get(User, request.reviewed_by)
        reviewer_name = reviewer.name if reviewer else None

    if request.created_user_id:
        created_user = db.get(User, request.created_user_id)
        approved_role = _user_role_to_account_request_role(created_user.role) if created_user else None

    return RegistrationRequestOut(
        id=request.id,
        name=request.name,
        email=request.email,
        requested_role=_normalize_account_request_role(request.requested_role),
        approved_role=approved_role,
        student_id=request.student_id,
        student_class=request.student_class,
        phone=request.phone,
        request_reason=request.request_reason,
        status=request.status,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
        reviewed_by=request.reviewed_by,
        reviewed_by_name=reviewer_name,
        review_notes=request.review_notes,
        created_user_id=request.created_user_id,
    )

# --- Auth ---
@app.post("/auth/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = _normalize_email(form.username)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        existing_request = _get_latest_registration_request(db, email)
        if existing_request:
            if existing_request.status == "pending":
                raise HTTPException(
                    status_code=403,
                    detail="Your access request is pending admin approval.",
                )
            if existing_request.status == "rejected":
                detail = "Your access request was rejected by an administrator."
                if existing_request.review_notes:
                    detail = f"{detail} {existing_request.review_notes}"
                raise HTTPException(status_code=403, detail=detail)
            if existing_request.status == "approved" and not existing_request.created_user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Your access request was approved, but the account is not ready yet.",
                )
        raise HTTPException(status_code=401, detail="Bad credentials")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account inactive")
    if not verify_pwd(form.password, user.pwd_hash):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return Token(access_token=token, role=user.role, name=user.name)

# --- Get current user info ---
@app.post("/auth/register", response_model=RegistrationRequestAck)
def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    """Submit an access request for admin approval."""
    if not settings.ACCOUNT_REQUESTS_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="New access requests are currently disabled. Contact an administrator.",
        )

    email = _normalize_email(user_in.email)
    requested_role = _normalize_account_request_role(user_in.requested_role)
    if requested_role not in ALLOWED_ACCOUNT_REQUEST_ROLES:
        raise HTTPException(status_code=400, detail="Only authorized personnel and guard access can be requested")

    student_id = _normalize_optional_text(user_in.student_id)
    student_class = _normalize_optional_text(user_in.student_class)
    phone = _normalize_optional_text(user_in.phone)
    request_reason = _normalize_optional_text(user_in.request_reason)

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if student_id:
        existing_person = db.query(User).filter(User.student_id == student_id).first()
        if existing_person:
            raise HTTPException(status_code=400, detail=f"Personnel ID {student_id} is already in use")

    existing_pending = (
        db.query(RegistrationRequest)
        .filter(RegistrationRequest.email == email, RegistrationRequest.status == "pending")
        .first()
    )
    if existing_pending:
        raise HTTPException(status_code=400, detail="An access request for this email is already pending approval")

    if student_id:
        existing_pending_id = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.student_id == student_id, RegistrationRequest.status == "pending")
            .first()
        )
        if existing_pending_id:
            raise HTTPException(status_code=400, detail=f"Personnel ID {student_id} already has a pending request")

    latest_request = _get_latest_registration_request(db, email)
    if latest_request and latest_request.status == "rejected" and not latest_request.created_user_id:
        latest_request.name = user_in.name.strip()
        latest_request.email = email
        latest_request.pwd_hash = hash_pwd(user_in.password)
        latest_request.requested_role = requested_role
        latest_request.student_id = student_id
        latest_request.student_class = student_class
        latest_request.phone = phone
        latest_request.request_reason = request_reason
        latest_request.status = "pending"
        latest_request.created_at = now_local()
        latest_request.reviewed_at = None
        latest_request.reviewed_by = None
        latest_request.review_notes = None
        latest_request.created_user_id = None
        registration_request = latest_request
    else:
        registration_request = RegistrationRequest(
            name=user_in.name.strip(),
            email=email,
            pwd_hash=hash_pwd(user_in.password),
            requested_role=requested_role,
            student_id=student_id,
            student_class=student_class,
            phone=phone,
            request_reason=request_reason,
            status="pending",
        )
        db.add(registration_request)

    db.commit()
    db.refresh(registration_request)

    _notify_admins_of_registration_request(db, registration_request)

    role_label = _account_request_role_label(requested_role)
    print(f"✅ New access request submitted: {registration_request.name} ({registration_request.email})")
    return RegistrationRequestAck(
        request_id=registration_request.id,
        status=registration_request.status,
        message=f"Your {role_label} access request has been submitted for admin approval.",
    )

@app.get("/auth/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@app.get("/admin/registration-requests", response_model=List[RegistrationRequestOut])
def list_registration_requests(
    request_status: str = Query(default="pending", alias="status"),
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    q = db.query(RegistrationRequest)
    if request_status != "all":
        if request_status not in {"pending", "approved", "rejected"}:
            raise HTTPException(status_code=400, detail="Invalid registration request status")
        q = q.filter(RegistrationRequest.status == request_status)
    requests = q.order_by(RegistrationRequest.created_at.desc(), RegistrationRequest.id.desc()).all()
    return [_serialize_registration_request(db, request) for request in requests]


@app.post("/admin/registration-requests/{request_id}/approve", response_model=RegistrationRequestOut)
def approve_registration_request(
    request_id: int,
    review: RegistrationRequestReview,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    registration_request = db.get(RegistrationRequest, request_id)
    if not registration_request:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if registration_request.status != "pending":
        raise HTTPException(status_code=400, detail="Registration request has already been reviewed")

    approved_role = _normalize_account_request_role(review.approved_role or registration_request.requested_role)
    if approved_role not in ALLOWED_ACCOUNT_REQUEST_ROLES:
        raise HTTPException(status_code=400, detail="Invalid approved role")

    existing_user = db.query(User).filter(User.email == registration_request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="A user account with this email already exists")

    if registration_request.student_id:
        existing_person = db.query(User).filter(User.student_id == registration_request.student_id).first()
        if existing_person:
            raise HTTPException(status_code=400, detail="Personnel ID is already assigned to another user")

    new_user = User(
        name=registration_request.name,
        email=registration_request.email,
        pwd_hash=registration_request.pwd_hash,
        role=_account_request_role_to_user_role(approved_role),
        student_id=registration_request.student_id,
        student_class=registration_request.student_class,
        phone=registration_request.phone,
        active=True,
        valid_until=_build_valid_until(_account_request_role_to_user_role(approved_role)),
    )
    db.add(new_user)
    db.flush()

    registration_request.status = "approved"
    registration_request.requested_role = _normalize_account_request_role(registration_request.requested_role)
    registration_request.reviewed_at = now_local()
    registration_request.reviewed_by = admin.id
    registration_request.review_notes = _normalize_optional_text(review.review_notes)
    registration_request.created_user_id = new_user.id

    db.commit()
    db.refresh(registration_request)
    return _serialize_registration_request(db, registration_request)


@app.post("/admin/registration-requests/{request_id}/reject", response_model=RegistrationRequestOut)
def reject_registration_request(
    request_id: int,
    review: RegistrationRequestReview,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    registration_request = db.get(RegistrationRequest, request_id)
    if not registration_request:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if registration_request.status != "pending":
        raise HTTPException(status_code=400, detail="Registration request has already been reviewed")

    registration_request.status = "rejected"
    registration_request.requested_role = _normalize_account_request_role(registration_request.requested_role)
    registration_request.reviewed_at = now_local()
    registration_request.reviewed_by = admin.id
    registration_request.review_notes = _normalize_optional_text(review.review_notes)
    registration_request.created_user_id = None

    db.commit()
    db.refresh(registration_request)
    return _serialize_registration_request(db, registration_request)

# =====================
# Admin User Management
# =====================

@app.get("/api/admin/users", response_model=List[AdminUserOut])
def admin_list_users(
    role: Optional[str] = None,
    active: Optional[bool] = None,
    search: Optional[str] = None,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all users with optional filters by role, active status, or name/email/ID search."""
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if active is not None:
        q = q.filter(User.active == active)
    if search:
        term = f"%{search}%"
        from sqlalchemy import or_
        q = q.filter(or_(User.name.ilike(term), User.email.ilike(term), User.student_id.ilike(term)))
    return q.order_by(User.name).all()


@app.post("/api/admin/users", response_model=AdminUserOut, status_code=201)
def admin_create_user(
    user_in: AdminUserCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Create a user account directly (admin only)."""
    email = _normalize_email(user_in.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already registered")
    if user_in.student_id:
        sid = _normalize_optional_text(user_in.student_id)
        if db.query(User).filter(User.student_id == sid).first():
            raise HTTPException(400, f"Personnel ID {sid} is already in use")
    new_user = User(
        name=user_in.name.strip(),
        email=email,
        pwd_hash=hash_pwd(user_in.password),
        role=user_in.role,
        student_id=_normalize_optional_text(user_in.student_id),
        student_class=_normalize_optional_text(user_in.student_class),
        phone=_normalize_optional_text(user_in.phone),
        guardian_name=_normalize_optional_text(user_in.guardian_name),
        active=user_in.active,
        valid_until=_build_valid_until(user_in.role),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"✅ Admin {admin.email} created user {new_user.email} (role={new_user.role})")
    return new_user


@app.get("/api/admin/users/{user_id}", response_model=AdminUserOut)
def admin_get_user(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get a single user by ID."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


@app.patch("/api/admin/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(
    user_id: int,
    update: AdminUserUpdate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a user's profile/role/status (admin only)."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if update.name is not None:
        u.name = update.name.strip()
    if update.role is not None:
        u.role = update.role
    if update.student_id is not None:
        new_sid = _normalize_optional_text(update.student_id)
        if new_sid and new_sid != u.student_id:
            if db.query(User).filter(User.student_id == new_sid, User.id != u.id).first():
                raise HTTPException(400, f"Personnel ID {new_sid} is already in use")
        u.student_id = new_sid
    if update.student_class is not None:
        u.student_class = _normalize_optional_text(update.student_class)
    if update.phone is not None:
        u.phone = _normalize_optional_text(update.phone)
    if update.guardian_name is not None:
        u.guardian_name = _normalize_optional_text(update.guardian_name)
    if update.active is not None:
        u.active = update.active
    if update.valid_until is not None:
        u.valid_until = update.valid_until
    db.commit()
    db.refresh(u)
    return u


@app.delete("/api/admin/users/{user_id}", status_code=204)
def admin_deactivate_user(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Deactivate (soft-delete) a user account."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "Cannot deactivate your own account")
    u.active = False
    db.commit()


@app.post("/api/admin/users/{user_id}/reset-face", status_code=200)
def admin_reset_face(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Clear a user's face registration so they can re-enroll."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.face_encoding = None
    u.face_registered = False
    u.face_registered_at = None
    _delete_face_preview(u.id)
    db.commit()
    return {"message": f"Face registration cleared for {u.name}"}


# =====================
# Notification Endpoints
# =====================

@app.post("/api/register_fcm_token")
def register_fcm_token(
    payload: FCMTokenRegister,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register FCM token for push notifications"""
    user.fcm_token = payload.fcm_token
    user.last_notification_at = datetime.now(CAMPUS_TZ)
    db.commit()
    return {"message": "FCM token registered successfully", "enabled": NOTIFICATIONS_ENABLED}

@app.post("/api/update_contact")
def update_contact(
    payload: ContactUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update student and parent contact information"""
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.parent_name is not None:
        user.parent_name = payload.parent_name
    if payload.parent_phone is not None:
        user.parent_phone = payload.parent_phone
    
    db.commit()
    return {"message": "Contact information updated successfully"}

@app.get("/api/notification_status")
def get_notification_status(user: User = Depends(get_current_user)):
    """Get notification system status"""
    if NOTIFICATIONS_ENABLED:
        return notifications.get_notification_status()
    else:
        return {"enabled": False, "message": "Notifications not configured"}

@app.get("/api/parent/access-token")
def get_parent_access_token(user: User = Depends(require_role("student"))):
    """Create a signed parent portal token tied to the current student"""
    if not user.student_id:
        raise HTTPException(400, "Student ID is required before sharing parent access")

    return {
        "student_id": user.student_id,
        "access_token": create_parent_access_token(user.student_id),
    }

def _require_parent_access(student_id: str, access_token: str) -> None:
    token_student_id = verify_parent_access_token(access_token)
    if token_student_id != student_id:
        raise HTTPException(403, "Parent access token does not match the requested student")

@app.post("/api/register_parent_fcm")
def register_parent_fcm(
    data: ParentFCMRegister,
    db: Session = Depends(get_db)
):
    """Register parent contact details and optional FCM token for a student"""
    _require_parent_access(data.student_id, data.access_token)

    # Find student by student_id (not database id)
    student = db.query(User).filter(
        User.student_id == data.student_id,
        User.role == "student"
    ).first()
    
    if not student:
        raise HTTPException(404, f"Student with ID {data.student_id} not found")
    
    # Update parent information
    student.parent_name = data.parent_name
    if data.parent_phone:
        student.parent_phone = data.parent_phone
    if data.parent_fcm_token:
        student.parent_fcm_token = data.parent_fcm_token
    
    db.commit()
    
    return {
        "message": "Parent contact registered successfully",
        "student_name": student.name,
        "student_id": student.student_id,
        "parent_name": data.parent_name
    }

@app.get("/api/parent/student_history/{student_id}")
def get_student_history_for_parent(
    student_id: str,
    access_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get entry/exit history for a student (for parents)"""
    _require_parent_access(student_id, access_token)

    # Find student
    student = db.query(User).filter(
        User.student_id == student_id,
        User.role == "student"
    ).first()
    
    if not student:
        raise HTTPException(404, f"Student with ID {student_id} not found")
    
    # Get scan logs for this student (last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    scans = db.query(ScanLog).filter(
        ScanLog.student_id == student.id,
        ScanLog.scan_time >= thirty_days_ago,
        ScanLog.result == "success"  # Only show successful scans
    ).order_by(ScanLog.scan_time.desc()).limit(50).all()
    
    # Format the response
    history = []
    for scan in scans:
        history.append({
            "id": scan.id,
            "timestamp": scan.scan_time.isoformat(),
            "scan_type": scan.pass_type,  # 'entry' or 'exit'
            "location": "Main Gate",  # Default location
            "verified_by": "Guard System",
            "date": scan.scan_time.strftime("%B %d, %Y"),
            "time": scan.scan_time.strftime("%I:%M %p")
        })
    
    return {
        "student_name": student.name,
        "student_id": student.student_id,
        "student_class": student.student_class,
        "history": history,
        "total_scans": len(history)
    }

# --- Student: create & list passes ---
@app.post("/passes", response_model=PassOut)
def create_pass(p: PassCreate, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    slot = None
    booking = None
    location_verified = False
    location_distance = None

    if p.slot_id:
        slot, booking, location_verified, location_distance = _validate_slot_for_pass(
            db, user, p.slot_id, p.latitude, p.longitude
        )
    elif GEOFENCE_ENABLED and p.latitude is not None and p.longitude is not None:
        is_valid, message, details = geofence.validate_student_location(p.latitude, p.longitude)
        location_verified = is_valid
        location_distance = str(details.get('distance_km', ''))
    
    pr = PassRequest(
        student_id=user.id, 
        reason=p.reason, 
        status="pending", 
        pass_type=p.pass_type,
        request_latitude=str(p.latitude) if p.latitude else None,
        request_longitude=str(p.longitude) if p.longitude else None,
        location_verified=location_verified,
        location_distance_km=location_distance,
        slot_id=slot.id if slot else None,
        access_mode="slot-bound" if slot else "standard",
        requires_face_check=bool(slot.face_check_required) if slot else False,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)

    if booking:
        booking.pass_id = pr.id
        db.commit()
        db.refresh(pr)
    
    # Notify admins of new pass request
    if NOTIFICATIONS_ENABLED:
        try:
            admin_users = db.query(User).filter(User.role == "admin", User.fcm_token.isnot(None)).all()
            admin_tokens = [admin.fcm_token for admin in admin_users if admin.fcm_token]
            if admin_tokens:
                notifications.notify_admin_new_request(admin_tokens, user.name, pr.id)
                print(f"✅ Notified {len(admin_tokens)} admin(s) of new pass request #{pr.id}")
        except Exception as e:
            print(f"⚠️  Admin notification error: {e}")
    
    return pr

@app.get("/passes", response_model=List[PassOut])
def list_passes(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PassRequest)
    if user.role == "student":
        q = q.filter(PassRequest.student_id == user.id)
    if status:
        q = q.filter(PassRequest.status == status)
    passes = q.order_by(PassRequest.request_time.desc()).all()
    
    # add student details to each pass
    result = []
    for p in passes:
        result.append(_pass_to_out_dict(db, p))
    
    return result

# --- Admin: approve/reject ---
@app.post("/passes/{pass_id}/approve", response_model=PassOut)
def approve(pass_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    pr = db.get(PassRequest, pass_id)
    if not pr:
        raise HTTPException(404, "Not found")
    if pr.status != "pending":
        raise HTTPException(400, "Already decided")
    if pr.slot_id:
        slot = _validate_slot_for_booking(db, pr.slot_id)
        if _slot_reserved_count(db, pr.slot_id) > slot.capacity:
            raise HTTPException(409, "Slot is over capacity. Approval is blocked.")

    token, exp = _issue_qr_for_pass(db, pr)
    pr.status = "approved"
    pr.approved_by = user.id
    pr.approved_time = now_local()
    pr.expiry_time = datetime.fromtimestamp(exp, tz=CAMPUS_TZ)
    pr.qr_token = token
    db.commit()
    db.refresh(pr)
    
    # Send notification to student
    if NOTIFICATIONS_ENABLED:
        student = db.get(User, pr.student_id)
        if student:
            try:
                notifications.notify_pass_approved(
                    student.name, pr.id, student.fcm_token, student.phone
                )
                print(f"✅ Sent approval notification for pass #{pr.id} to {student.name}")
            except Exception as e:
                print(f"⚠️ Notification error: {e}")
    
    return pr

@app.post("/passes/{pass_id}/reject", response_model=PassOut)
def reject(pass_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    pr = db.get(PassRequest, pass_id)
    if not pr:
        raise HTTPException(404)
    if pr.status != "pending":
        raise HTTPException(400, "Already decided")
    pr.status = "rejected"
    db.commit()
    db.refresh(pr)
    
    # Send rejection notification to student
    if NOTIFICATIONS_ENABLED:
        student = db.get(User, pr.student_id)
        if student:
            try:
                notifications.notify_pass_rejected(
                    student.name, pr.id, student.fcm_token, student.phone
                )
                print(f"✅ Sent rejection notification for pass #{pr.id} to {student.name}")
            except Exception as e:
                print(f"⚠️ Notification error: {e}")
    
    return pr

# --- Guard: verify ---
@app.post("/verify", response_model=dict)
async def verify(
    token: str = Form(...),
    face_image: Optional[UploadFile] = File(None),
    guard: User = Depends(require_role("guard")), 
    db: Session = Depends(get_db)
):
    parsed = parse_token(token)
    if not parsed:
        return _fail(db, None, None, guard.id, "invalid", "malformed")
    pid, uid, exp, sig_recv = parsed

    pr = db.get(PassRequest, pid)
    if not pr:
        return _fail(db, pid, uid, guard.id, "invalid", "no-pass")
    
    # recompute HMAC
    data = f"{pid}.{uid}.{exp}"
    expected = hmac.new(settings.SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]

    now = int(now_local().timestamp())

    if sig_recv != expected:
        return _fail(db, pid, uid, guard.id, "invalid", "sig-mismatch")
    if uid != pr.student_id:
        return _fail(db, pid, uid, guard.id, "invalid", "user-mismatch")
    if now > int(exp):
        return _fail(db, pid, uid, guard.id, "expired", "past-expiry")
    if pr.status not in ("approved",):  # used/rejected/pending not allowed
        return _fail(db, pid, uid, guard.id, "not-approved", pr.status)

    # atomic "use" (simple version: check again then update)
    if pr.used_time:
        return _fail(db, pid, uid, guard.id, "replay", "already-used")
    
    # get student details
    student = db.get(User, pr.student_id)
    student_name = student.name if student else "Unknown"
    student_code = student.student_id if student else f"ID:{pr.student_id}"
    
    # Face verification (optional)
    face_verified = None
    face_confidence = None
    face_distance = None
    face_message = None
    face_required = bool(pr.requires_face_check)
    
    if face_required and not face_image:
        return _fail(db, pid, uid, guard.id, "invalid", "face-required")
    if face_required and not FACE_AUTH_ENABLED:
        return _fail(db, pid, uid, guard.id, "invalid", "face-service-unavailable")
    if face_required and (not student or not student.face_registered or not student.face_encoding):
        return _fail(db, pid, uid, guard.id, "invalid", "face-not-registered")

    if FACE_AUTH_ENABLED and face_image and student:
        try:
            face_auth_module = get_face_auth_module()
            if face_auth_module is None:
                return _fail(db, pid, uid, guard.id, "invalid", "face-service-unavailable")

            # Check if student has registered face
            if student.face_registered and student.face_encoding:
                # Read uploaded face image
                image_bytes = await face_image.read()
                
                # Validate image
                is_valid, error_msg = face_auth_module.validate_image(image_bytes)
                if is_valid:
                    # Extract face encoding from uploaded image
                    check_encoding = face_auth_module.extract_face_encoding(image_bytes)
                    
                    if check_encoding is not None:
                        # Get stored encoding for THIS specific student
                        stored_encoding = _decode_face_encoding(face_auth_module, student.face_encoding)
                        if stored_encoding is None:
                            return _fail(db, pid, uid, guard.id, "invalid", "face-registration-outdated")
                        if getattr(face_auth_module, "requires_reenrollment", lambda _: False)(stored_encoding):
                            return _fail(db, pid, uid, guard.id, "invalid", "face-registration-outdated")
                        tolerance = getattr(face_auth_module, "get_match_tolerance", lambda _=None: 0.5)(stored_encoding)
                        is_match, distance = face_auth_module.compare_faces(stored_encoding, check_encoding, tolerance=tolerance)
                        
                        # Get confidence
                        confidence_info = face_auth_module.get_confidence_level(distance, stored_encoding)
                        
                        # Convert numpy types to Python native types for JSON serialization
                        face_verified = bool(is_match)
                        face_confidence = int(confidence_info["confidence_percent"])
                        face_distance = float(distance)
                        
                        if is_match:
                            face_message = f"Face matches {student.name} - {confidence_info['description']}"
                        else:
                            face_message = f"Face does NOT match {student.name} (distance: {distance:.3f})"
                        
                    else:
                        return _fail(db, pid, uid, guard.id, "invalid", "face-not-detected")
                else:
                    return _fail(db, pid, uid, guard.id, "invalid", f"face-invalid-image:{error_msg}")
            else:
                face_message = f"{student.name} has not registered face"
                if face_required:
                    return _fail(db, pid, uid, guard.id, "invalid", "face-not-registered")
        except Exception as e:
            print(f"Face verification error: {e}")
            return _fail(db, pid, uid, guard.id, "invalid", "face-verification-error")

    if face_verified is False:
        return _fail(db, pid, uid, guard.id, "invalid", "face-mismatch")
    if face_required and face_verified is not True:
        return _fail(db, pid, uid, guard.id, "invalid", "face-required")

    # Slot window enforcement
    if pr.slot_id:
        slot = db.get(Slot, pr.slot_id)
        if not slot or not slot.active:
            return _fail(db, pid, uid, guard.id, "invalid", "slot-inactive")
        now_ts = _now_utc_naive()
        if not (_to_utc_naive(slot.start_time) <= now_ts <= _to_utc_naive(slot.end_time)):
            return _fail(db, pid, uid, guard.id, "invalid", f"outside-slot-window:{slot.label}")

    mark_used(db, pr, guard.id)
    log_scan(db, pid, pr.student_id, guard.id, "success", "verified", pass_type=pr.pass_type or "entry")
    
    # Send entry/exit notification to parents
    if NOTIFICATIONS_ENABLED and student:
        try:
            timestamp = now_local().strftime("%I:%M %p")
            parent_fcm_tokens = [student.parent_fcm_token] if student.parent_fcm_token else []
            parent_phones = [student.parent_phone] if student.parent_phone else []
            
            if pr.pass_type == "entry":
                notifications.notify_entry_scan(
                    student.name, student_code, timestamp, parent_fcm_tokens, parent_phones
                )
                print(f"✅ Sent entry notification to parents of {student.name}")
            elif pr.pass_type == "exit":
                notifications.notify_exit_scan(
                    student.name, student_code, timestamp, parent_fcm_tokens, parent_phones
                )
                print(f"✅ Sent exit notification to parents of {student.name}")
        except Exception as e:
            print(f"⚠️  Parent notification error: {e}")
    
    response = {
        "result": "success", 
        "pass_id": pr.id, 
        "student_id": pr.student_id,
        "student_name": student_name,
        "student_code": student_code,
        "message": "GRANTED"
    }
    
    # Add face verification results if performed
    if face_verified is not None:
        response["face_verified"] = face_verified
        response["face_confidence"] = face_confidence
        response["face_distance"] = face_distance
        response["face_message"] = face_message
    elif face_message:
        response["face_message"] = face_message

    if pr.slot_id:
        response["slot_id"] = pr.slot_id
        response["access_mode"] = pr.access_mode
    return response

def _fail(db, pid, uid, gid, result, details):
    try:
        # For failed scans, try to get pass_type from the pass if it exists
        pass_type = "entry"  # default
        student_id = uid
        if pid:
            pr = db.get(PassRequest, pid)
            if pr:
                pass_type = pr.pass_type or "entry"
                student_id = pr.student_id
        log_scan(db, pid, student_id, gid, result, details, pass_type=pass_type)
    except Exception:
        pass
    raise HTTPException(status_code=400, detail=f"{result}: {details}")

# --- Auto Daily Entry (No Admin Approval Needed) ---
@app.post("/passes/daily-entry", response_model=PassOut)
async def auto_daily_entry(
    data: DailyEntryCreate,
    user: User = Depends(require_role("student")), 
    db: Session = Depends(get_db)
):
    """Auto-generate daily entry/exit pass without admin approval"""
    
    # Get pass_type from request (defaults to "entry" if not provided)
    pass_type = data.pass_type
    pass_label = "Entry" if pass_type == "entry" else "Exit"
    
    # GPS Geofencing validation
    location_verified = False
    location_distance = None
    if GEOFENCE_ENABLED:
        if data.latitude is None or data.longitude is None:
            raise HTTPException(
                status_code=400,
                detail=f"GPS location is required to generate a daily {pass_label.lower()} pass."
            )
        is_valid, message, details = geofence.validate_student_location(data.latitude, data.longitude)
        location_verified = is_valid
        location_distance = str(details.get('distance_km', ''))
        
        # Enforce location check for daily passes (stricter than regular passes)
        if not is_valid:
            raise HTTPException(
                status_code=403, 
                detail=f"Location verification failed: {message}. You must be on campus to generate a daily {pass_label.lower()} pass."
            )
    
    # Check if student is still valid
    if user.valid_until:
        # Handle both timezone-aware and naive datetimes
        valid_until = user.valid_until
        if valid_until.tzinfo is None:
            # Make it timezone-aware (assume it was stored as CAMPUS_TZ)
            valid_until = valid_until.replace(tzinfo=CAMPUS_TZ)
        if now_local() > valid_until:
            raise HTTPException(status_code=403, detail="Student validity expired. Please contact an Access Control Administrator.")
    
    # Check if student already has an active pass of this type for today (CAMPUS_TZ)
    now_ist_time = now_local()
    today_ist = now_ist_time.date()
    today_start_ist = datetime.combine(today_ist, datetime.min.time()).replace(tzinfo=CAMPUS_TZ)
    
    existing = db.query(PassRequest).filter(
        PassRequest.student_id == user.id,
        PassRequest.status.in_(["approved", "pending"]),
        PassRequest.request_time >= today_start_ist,
        PassRequest.pass_type == pass_type,
        PassRequest.reason.like(f"Daily {pass_label}%")
    ).first()
    
    if existing and existing.status == "approved" and not existing.used_time and _pass_expiry_is_active(existing):
        # Return existing QR if already generated today
        return existing
    
    if existing and existing.status == "pending":
        # Auto-approve if pending
        token, exp = _issue_qr_for_pass(db, existing)
        existing.status = "approved"
        existing.approved_by = user.id  # Self-approved
        existing.approved_time = now_local()
        existing.expiry_time = datetime.fromtimestamp(exp, tz=CAMPUS_TZ)
        existing.qr_token = token
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new auto-approved pass (use CAMPUS_TZ date)
    today_str = today_ist.strftime("%d/%m/%Y")
    reason = f"Daily {pass_label} - {today_str}"
    
    pr = PassRequest(
        student_id=user.id,
        reason=reason,
        pass_type=pass_type,
        status="pending",
        request_latitude=str(data.latitude) if data.latitude else None,
        request_longitude=str(data.longitude) if data.longitude else None,
        location_verified=location_verified,
        location_distance_km=location_distance,
        access_mode="instant",
        requires_face_check=False,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    
    # Auto-approve and generate QR
    token, exp = _issue_qr_for_pass(db, pr)
    pr.status = "approved"
    pr.approved_by = user.id  # Self-approved
    pr.approved_time = now_local()
    pr.expiry_time = datetime.fromtimestamp(exp, tz=CAMPUS_TZ)
    pr.qr_token = token
    db.commit()
    db.refresh(pr)
    
    return pr

# Get recent scans (guards only)
@app.get("/scans", response_model=List[ScanLogOut])
def get_recent_scans(
    limit: int = 50,
    guard: User = Depends(require_role("guard")),
    db: Session = Depends(get_db)
):
    scans = db.query(ScanLog).order_by(ScanLog.scan_time.desc()).limit(limit).all()
    
    # Enrich with student and scanner names
    result = []
    for scan in scans:
        scan_dict = {
            "id": scan.id,
            "pass_id": scan.pass_id,
            "student_id": scan.student_id,
            "scanner_id": scan.scanner_id,
            "scan_time": scan.scan_time,
            "result": scan.result,
            "pass_type": scan.pass_type or "entry",
            "emergency": bool(getattr(scan, "emergency", False)),
            "details": scan.details,
            "student_name": None,
            "student_code": None,
            "scanner_name": None
        }
        
        # Get student info
        student = db.query(User).filter(User.id == scan.student_id).first()
        if student:
            scan_dict["student_name"] = student.name
            scan_dict["student_code"] = student.student_id
        
        # Get scanner info
        scanner = db.query(User).filter(User.id == scan.scanner_id).first()
        if scanner:
            scan_dict["scanner_name"] = scanner.name
        
        result.append(scan_dict)
    
    return result

# Get guard statistics
@app.get("/scans/stats")
def get_scan_stats(
    guard: User = Depends(require_role("guard")),
    db: Session = Depends(get_db)
):
    # Get CAMPUS_TZ timezone info
    now = now_local()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Total scans today
    total_today = db.query(ScanLog).filter(
        ScanLog.scan_time >= today_start
    ).count()
    
    # Successful scans today
    success_today = db.query(ScanLog).filter(
        ScanLog.scan_time >= today_start,
        ScanLog.result == "success"
    ).count()
    
    # Failed scans today
    failed_today = db.query(ScanLog).filter(
        ScanLog.scan_time >= today_start,
        ScanLog.result != "success"
    ).count()
    
    # Entry scans today (successful)
    entry_today = db.query(ScanLog).filter(
        ScanLog.scan_time >= today_start,
        ScanLog.result == "success",
        ScanLog.pass_type == "entry"
    ).count()
    
    # Exit scans today (successful)
    exit_today = db.query(ScanLog).filter(
        ScanLog.scan_time >= today_start,
        ScanLog.result == "success",
        ScanLog.pass_type == "exit"
    ).count()
    
    # All time stats
    total_all_time = db.query(ScanLog).count()
    
    return {
        "total_today": total_today,
        "success_today": success_today,
        "failed_today": failed_today,
        "entry_today": entry_today,
        "exit_today": exit_today,
        "total_all_time": total_all_time
    }

# === FACE AUTHENTICATION ENDPOINTS ===

if FACE_AUTH_ENABLED:
    @app.post("/api/register_face", response_model=FaceRegistrationResponse)
    async def register_face(
        file: UploadFile = File(...),
        user: User = Depends(require_role("student", "admin")),
        db: Session = Depends(get_db)
    ):
        """
        Register a student's face for authentication.
        Students can register their own face, admins can register any student's face.
        """
        face_auth_module = get_face_auth_module()
        if face_auth_module is None:
            message = "Face registration is not available on this deployment."
            if _face_auth_import_error:
                message = f"{message} Import error: {_face_auth_import_error}"
            raise HTTPException(status_code=503, detail=message)

        # Read image bytes
        image_bytes = await file.read()
        print(f"📷 Face registration attempt by {user.email} with file {file.filename!r} ({len(image_bytes)} bytes)")
        
        # Validate image
        is_valid, error_msg = face_auth_module.validate_image(image_bytes)
        if not is_valid:
            print(f"❌ Face registration validation failed for {user.email}: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Extract face encoding
        encoding = face_auth_module.extract_face_encoding(image_bytes)
        if encoding is None:
            print(f"❌ No face detected for {user.email}")
            raise HTTPException(
                status_code=400,
                detail="No clear face detected. Use a bright, upright photo with only one face visible and try again."
            )

        duplicate_user, duplicate_distance = _find_duplicate_face_registration(db, user, encoding, face_auth_module)
        if duplicate_user is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This face is too similar to another registered account. "
                    "Use your own face image or contact an administrator."
                ),
            )
        
        # Store encoding
        user.face_encoding = face_auth_module.encoding_to_json(encoding)
        user.face_registered = True
        user.face_registered_at = now_local()
        _save_face_preview(user.id, image_bytes)
        db.commit()
        db.refresh(user)
        print(f"✅ Face registered successfully for {user.email}")
        
        return FaceRegistrationResponse(
            status="success",
            message="Face registered successfully",
            face_registered=True,
            registered_at=user.face_registered_at
        )

    @app.post("/api/verify_face", response_model=FaceVerificationResponse)
    async def verify_face(
        file: UploadFile = File(...),
        student_id: int = Form(...),
        user: User = Depends(require_role("guard", "admin")),
        db: Session = Depends(get_db)
    ):
        """
        Verify a face against stored encoding.
        Used by guards at gate or by admins for testing.
        """
        face_auth_module = get_face_auth_module()
        if face_auth_module is None:
            message = "Face verification is not available on this deployment."
            if _face_auth_import_error:
                message = f"{message} Import error: {_face_auth_import_error}"
            raise HTTPException(status_code=503, detail=message)

        # Get student to verify
        student = db.get(User, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        if not student.face_registered or not student.face_encoding:
            raise HTTPException(
                status_code=400,
                detail="Student has not registered their face"
            )
        
        # Read uploaded image
        image_bytes = await file.read()
        
        # Validate image
        is_valid, error_msg = face_auth_module.validate_image(image_bytes)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Extract face encoding from uploaded image
        check_encoding = face_auth_module.extract_face_encoding(image_bytes)
        if check_encoding is None:
            return FaceVerificationResponse(
                verified=False,
                confidence_level="no_match",
                confidence_percent=0,
                distance=1.0,
                message="No face detected in uploaded image"
            )
        
        # Get stored encoding
        stored_encoding = _decode_face_encoding(face_auth_module, student.face_encoding)
        if stored_encoding is None or getattr(face_auth_module, "requires_reenrollment", lambda _: False)(stored_encoding):
            raise HTTPException(
                status_code=409,
                detail="Student must re-register face with the updated verification model"
            )
        
        # Compare faces
        tolerance = getattr(face_auth_module, "get_match_tolerance", lambda _=None: 0.6)(stored_encoding)
        is_match, distance = face_auth_module.compare_faces(stored_encoding, check_encoding, tolerance=tolerance)
        
        # Get confidence level
        confidence_info = face_auth_module.get_confidence_level(distance, stored_encoding)
        
        return FaceVerificationResponse(
            verified=is_match,
            confidence_level=confidence_info["level"],
            confidence_percent=confidence_info["confidence_percent"],
            distance=distance,
            message=f"{student.name} - {confidence_info['description']}" if is_match else "Face does not match"
        )

    @app.get("/api/face_status")
    def get_face_status(user: User = Depends(get_current_user)):
        """Get face registration status for current user"""
        face_auth_module = get_face_auth_module()
        backend = settings.FACE_AUTH_BACKEND
        backend_error = _face_auth_import_error
        service_available = False

        if face_auth_module is not None:
            backend = getattr(face_auth_module, "get_backend_name", lambda: settings.FACE_AUTH_BACKEND)() or backend
            backend_error = getattr(face_auth_module, "get_backend_error", lambda: backend_error)()
            service_available = backend_error is None

        stored_encoding = None
        registration_backend = None
        requires_refresh = False
        if face_auth_module is not None and user.face_encoding:
            stored_encoding = _decode_face_encoding(face_auth_module, user.face_encoding)
            if stored_encoding is None:
                requires_refresh = True
            else:
                registration_backend = getattr(face_auth_module, "get_encoding_backend", lambda _: None)(stored_encoding)
                requires_refresh = getattr(face_auth_module, "requires_reenrollment", lambda _: False)(stored_encoding)

        return {
            "face_registered": user.face_registered,
            "face_registered_at": user.face_registered_at,
            "can_register": user.role == "student",
            "service_available": service_available,
            "backend": backend,
            "backend_error": backend_error,
            "registration_backend": registration_backend,
            "requires_refresh": requires_refresh,
            "face_preview_available": bool(user.face_registered and os.path.exists(_face_preview_path(user.id))),
        }

    @app.get("/api/face_preview")
    def get_face_preview(user: User = Depends(get_current_user)):
        """Return the current user's display-only enrolled face thumbnail."""
        if not user.face_registered:
            raise HTTPException(status_code=404, detail="Face is not registered")

        path = _face_preview_path(user.id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="No enrolled photo preview is stored")

        return FileResponse(
            path,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, no-store"},
        )
else:
    # Provide stub endpoints when face auth is disabled
    @app.get("/api/face_status")
    def get_face_status_disabled(user: User = Depends(get_current_user)):
        """Get face registration status (disabled)"""
        return {
            "face_registered": False,
            "face_registered_at": None,
            "can_register": False,
            "service_available": False,
            "backend": settings.FACE_AUTH_BACKEND,
            "face_preview_available": False,
            "error": "Face authentication is disabled. Install face-recognition package to enable."
        }

# === GPS GEOFENCING ENDPOINTS ===

if GEOFENCE_ENABLED:
    @app.post("/api/validate_location")
    def validate_location(
        latitude: float,
        longitude: float,
        user: User = Depends(get_current_user)
    ):
        """
        Validate if a GPS location is within campus boundaries.
        Available to all authenticated users for testing.
        """
        is_valid, message, details = geofence.validate_student_location(latitude, longitude)
        
        return {
            "valid": is_valid,
            "message": message,
            "latitude": latitude,
            "longitude": longitude,
            "inside_campus": details.get("inside", False),
            "distance_km": details.get("distance_km"),
            "distance_meters": details.get("distance_meters")
        }

    @app.get("/api/geofence_config")
    def get_geofence_config(user: User = Depends(require_role("admin"))):
        """Get current geofence configuration (admin only)"""
        return {
            "type": "circular" if not geofence.campus_geofence.use_polygon else "polygon",
            "center": geofence.CAMPUS_CENTER if hasattr(geofence, 'CAMPUS_CENTER') else None,
            "radius_km": geofence.CAMPUS_RADIUS_KM if hasattr(geofence, 'CAMPUS_RADIUS_KM') else None,
            "polygon": geofence.DEFAULT_CAMPUS_POLYGON if hasattr(geofence, 'DEFAULT_CAMPUS_POLYGON') else None
        }

# ============================================================================
# REAL-TIME LOGS & ANALYTICS ENDPOINTS
# ============================================================================

if REALTIME_LOGS_ENABLED:
    @app.get("/api/logs/recent")
    def get_recent_logs_api(
        limit: int = 100,
        offset: int = 0,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Get recent scan logs"""
        logs = realtime_logs.get_recent_logs(db, limit=limit, offset=offset)
        return {"logs": logs, "count": len(logs)}
    
    @app.get("/api/logs/statistics")
    def get_log_statistics_api(
        days: int = 7,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Get scan statistics"""
        return realtime_logs.get_log_statistics(db, days=days)
    
    @app.get("/api/logs/hourly")
    def get_hourly_stats_api(
        date: Optional[str] = None,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Get hourly statistics for a specific day"""
        date_obj = datetime.fromisoformat(date) if date else None
        return realtime_logs.get_hourly_stats(db, date=date_obj)
    
    @app.get("/api/logs/daily")
    def get_daily_stats_api(
        days: int = 7,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Get daily statistics for last N days"""
        return realtime_logs.get_daily_stats(db, days=days)
    
    @app.get("/api/logs/top_students")
    def get_top_active_students_api(
        days: int = 7,
        limit: int = 10,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Get most active students"""
        return {
            "students": realtime_logs.get_top_active_students(db, days=days, limit=limit),
            "period_days": days
        }
    
    @app.get("/api/logs/search")
    def search_logs_api(
        student_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        scan_type: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 100,
        admin: User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
    ):
        """Search logs with filters"""
        date_from_obj = datetime.fromisoformat(date_from) if date_from else None
        date_to_obj = datetime.fromisoformat(date_to) if date_to else None
        
        logs = realtime_logs.search_logs(
            db,
            student_id=student_id,
            date_from=date_from_obj,
            date_to=date_to_obj,
            scan_type=scan_type,
            result=result,
            limit=limit
        )
        
        return {"logs": logs, "count": len(logs)}

    def _authenticate_admin_websocket(token: Optional[str], db: Session) -> User:
        if not token:
            raise HTTPException(status_code=401, detail="Missing WebSocket token")

        user = get_user_from_token(token, db)
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    
    @app.websocket("/ws/logs")
    async def websocket_logs_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time log updates (Admin only)"""
        db = SessionLocal()
        try:
            token = websocket.query_params.get("token")
            _authenticate_admin_websocket(token, db)

            await realtime_logs.manager.connect(websocket)

            # Send initial recent logs
            recent = realtime_logs.get_recent_logs(db, limit=10)
            await websocket.send_json({
                "type": "initial",
                "data": recent
            })
            
            # Keep connection alive and listen for messages
            while True:
                data = await websocket.receive_text()
                # Echo back or handle commands if needed
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            realtime_logs.manager.disconnect(websocket)
        except HTTPException as e:
            await websocket.close(code=1008, reason=e.detail)
        except Exception as e:
            print(f"WebSocket error: {e}")
            realtime_logs.manager.disconnect(websocket)
        finally:
            db.close()

# ============================================================================
# EMERGENCY EXIT FEATURE
# ============================================================================

class EmergencyExitRequest(BaseModel):
    reason: Optional[str] = "Emergency exit"

@app.post("/api/emergency_exit")
def request_emergency_exit(
    request_data: EmergencyExitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request emergency exit (Student only)"""
    
    if user.role != "student":
        raise HTTPException(403, "Only students can request emergency exit")
    
    now = datetime.now(CAMPUS_TZ)

    # Use ORM so FK constraints are respected (pass_id is nullable)
    emergency_log = ScanLog(
        student_id=user.id,
        scanner_id=user.id,
        pass_id=None,
        scan_time=now,
        result="success",
        pass_type="exit",
        emergency=True,
        details=f"Emergency Exit: {request_data.reason}",
    )
    db.add(emergency_log)
    db.commit()
    
    # Send notifications
    if NOTIFICATIONS_ENABLED:
        try:
            if user.fcm_token:
                notifications.send_push_notification(
                    user.fcm_token,
                    "Emergency Exit Granted",
                    f"Emergency exit approved at {now.strftime('%I:%M %p')}. Stay safe!",
                    {"type": "emergency_exit", "timestamp": now.isoformat()},
                )
            if user.phone:
                notifications.send_sms(
                    user.phone,
                    f"Campus GatePass: Emergency exit approved at {now.strftime('%I:%M %p')}. Stay safe!",
                )
            
            # Notify all admins
            admins = db.query(User).filter(User.role == "admin").all()
            for admin in admins:
                if admin.fcm_token:
                    notifications.send_push_notification(
                        admin.fcm_token,
                        "Emergency Exit Alert",
                        f"{user.name} ({user.student_id}) requested emergency exit",
                        {"type": "emergency_exit", "student_id": user.student_id or "", "timestamp": now.isoformat()},
                    )
                if admin.phone:
                    notifications.send_sms(
                        admin.phone,
                        f"Emergency exit alert: {user.name} ({user.student_id}) requested emergency exit",
                    )
        except Exception as e:
            print(f"Failed to send emergency notifications: {e}")
    
    # Broadcast to real-time logs
    if REALTIME_LOGS_ENABLED:
        try:
            import realtime_logs
            scan_data = {
                "student_id": user.student_id,
                "student_name": user.name,
                "timestamp": now.isoformat(),
                "time": now.strftime("%I:%M %p"),
                "date": now.strftime("%B %d, %Y"),
                "scan_type": "exit",
                "result": "success",
                "gate": "Emergency Exit",
                "details": request_data.reason,
                "emergency": True
            }
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(realtime_logs.broadcast_new_scan(scan_data))
            except RuntimeError:
                asyncio.run(realtime_logs.broadcast_new_scan(scan_data))
        except Exception as e:
            print(f"Failed to broadcast emergency exit: {e}")
    
    return {
        "status": "exit_granted",
        "message": "Emergency exit approved. Please leave campus safely.",
        "timestamp": now.isoformat(),
        "student_name": user.name,
        "student_id": user.student_id
    }

# API info endpoint
@app.get("/api")
def api_root():
    return {"message": "GatePass QR System API", "version": "1.0"}


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root():
    return RedirectResponse(url="/frontend/", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

# Serve Firebase service worker
@app.get("/firebase-messaging-sw.js")
async def firebase_service_worker():
    from fastapi.responses import FileResponse
    sw_path = os.path.join(os.path.dirname(__file__), "firebase-messaging-sw.js")
    return FileResponse(sw_path, media_type="application/javascript")

# ============================================================================
# LOCATION SETTINGS (Admin only)
# ============================================================================

class LocationSettings(BaseModel):
    campus_name: str
    latitude: float
    longitude: float
    radius_km: float
    enabled: bool

@app.get("/api/admin/location")
def get_location_settings_admin(user: User = Depends(require_role("admin"))):
    """Get current location settings (Admin only)"""
    print(f"📍 Admin {user.name} (role: {user.role}) accessing location settings")
    
    if not GEOFENCE_ENABLED:
        raise HTTPException(503, "Geofencing is not enabled")
    
    settings = location_settings.get_location_settings()
    return settings

@app.post("/api/admin/location")
def update_location_settings(
    settings: LocationSettings,
    user: User = Depends(require_role("admin"))
):
    """Update location settings (Admin only)"""
    print(f"📝 Admin {user.name} (role: {user.role}) updating location settings")
    
    if not GEOFENCE_ENABLED:
        raise HTTPException(503, "Geofencing is not enabled")
    
    try:
        updated = location_settings.update_location(
            latitude=settings.latitude,
            longitude=settings.longitude,
            radius_km=settings.radius_km,
            campus_name=settings.campus_name,
            enabled=settings.enabled
        )
        print(f"✅ Location settings updated successfully by {user.name}")
        return {"message": "Location settings updated successfully", "settings": updated}
    except Exception as e:
        print(f"❌ Error updating location settings: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to update location settings: {str(e)}")

@app.get("/api/location")
def get_public_location_settings():
    """Get location settings for students (public endpoint)"""
    if not GEOFENCE_ENABLED:
        return {"enabled": False, "message": "Geofencing disabled"}
    
    settings = location_settings.get_location_settings()
    # Return only necessary info for students
    return {
        "enabled": settings.get("enabled", True),
        "campus_name": settings.get("campus_name", "Campus"),
        "latitude": settings.get("latitude"),
        "longitude": settings.get("longitude"),
        "radius_km": settings.get("radius_km", 2.0)
    }

# ============================================================================
# SLOT-BASED ACCESS SCHEDULING  (UC03 / UC04)
# ============================================================================

@app.post("/api/slots", response_model=SlotOut)
def create_slot(
    slot_in: SlotCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin creates a time-windowed access slot with capacity and policy flags."""
    start_time = _to_utc_naive(slot_in.start_time)
    end_time = _to_utc_naive(slot_in.end_time)
    if end_time <= start_time:
        raise HTTPException(400, "end_time must be after start_time")
    slot = Slot(
        label=slot_in.label,
        gate=slot_in.gate,
        start_time=start_time,
        end_time=end_time,
        capacity=slot_in.capacity,
        active=slot_in.active,
        gps_required=slot_in.gps_required,
        face_check_required=slot_in.face_check_required,
        created_by=admin.id,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    booked = _slot_reserved_count(db, slot.id)
    out = SlotOut.model_validate(slot)
    out.booked_count = booked
    out.remaining = slot.capacity - booked
    return out


@app.get("/api/slots", response_model=List[SlotOut])
def list_slots(
    active_only: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List slots.

    Personnel should only see bookable windows. Admins can request the full
    schedule with active_only=false for review and cleanup.
    """
    q = db.query(Slot)
    now = _now_utc_naive()
    if user.role != "admin":
        q = q.filter(Slot.active == True, Slot.end_time > now)
    elif active_only:
        q = q.filter(Slot.active == True, Slot.end_time > now)
    slots = q.order_by(Slot.start_time.asc()).all()
    result = []
    for s in slots:
        booked = _slot_reserved_count(db, s.id)
        out = SlotOut.model_validate(s)
        out.booked_count = booked
        out.remaining = s.capacity - booked
        result.append(out)
    return result


@app.get("/api/slots/{slot_id}", response_model=SlotOut)
def get_slot(
    slot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(404, "Slot not found")
    booked = _slot_reserved_count(db, slot_id)
    out = SlotOut.model_validate(slot)
    out.booked_count = booked
    out.remaining = slot.capacity - booked
    return out


@app.put("/api/slots/{slot_id}", response_model=SlotOut)
def update_slot(
    slot_id: int,
    slot_in: SlotCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(404, "Slot not found")
    start_time = _to_utc_naive(slot_in.start_time)
    end_time = _to_utc_naive(slot_in.end_time)
    if end_time <= start_time:
        raise HTTPException(400, "end_time must be after start_time")
    slot.label = slot_in.label
    slot.gate = slot_in.gate
    slot.start_time = start_time
    slot.end_time = end_time
    slot.capacity = slot_in.capacity
    slot.active = slot_in.active
    slot.gps_required = slot_in.gps_required
    slot.face_check_required = slot_in.face_check_required
    db.commit()
    db.refresh(slot)
    booked = _slot_reserved_count(db, slot.id)
    out = SlotOut.model_validate(slot)
    out.booked_count = booked
    out.remaining = slot.capacity - booked
    return out


@app.delete("/api/slots/{slot_id}")
def delete_slot(
    slot_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    slot = db.get(Slot, slot_id)
    if not slot:
        raise HTTPException(404, "Slot not found")
    slot.active = False
    db.commit()
    return {"message": "Slot deactivated"}


@app.post("/api/slots/{slot_id}/book", response_model=SlotBookingOut)
def book_slot(
    slot_id: int,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Member reserves a slot. Checks capacity and duplicate booking."""
    slot = _validate_slot_for_booking(db, slot_id)

    # Duplicate booking check
    existing = db.query(SlotBooking).filter(
        SlotBooking.slot_id == slot_id,
        SlotBooking.user_id == user.id,
        SlotBooking.booking_status == "confirmed",
    ).first()
    if existing:
        raise HTTPException(409, "You already have a booking for this slot")

    # Capacity check
    if _slot_reserved_count(db, slot_id) >= slot.capacity:
        raise HTTPException(409, "Slot is fully booked. Please choose another slot.")

    booking = SlotBooking(
        slot_id=slot_id,
        user_id=user.id,
        booking_status="confirmed",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/api/slots/my/bookings", response_model=List[SlotBookingOut])
def my_slot_bookings(
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    bookings = db.query(SlotBooking).filter(
        SlotBooking.user_id == user.id,
        SlotBooking.booking_status == "confirmed",
    ).order_by(SlotBooking.booked_at.desc()).all()
    return bookings


@app.delete("/api/slots/bookings/{booking_id}")
def cancel_booking(
    booking_id: int,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    booking = db.get(SlotBooking, booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    booking.booking_status = "cancelled"
    db.commit()
    return {"message": "Booking cancelled"}


# ============================================================================
# VISITOR PASS  (UC07)
# ============================================================================

@app.post("/api/admin/visitor-pass", response_model=PassOut)
def create_visitor_pass(
    data: VisitorPassCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin issues a one-time, short-validity pass for an external visitor."""
    slot = None
    if data.slot_id:
        slot = _validate_slot_for_booking(db, data.slot_id)
        if slot.face_check_required:
            raise HTTPException(400, "Visitor passes cannot use face-required slots")
        if _slot_reserved_count(db, slot.id) >= slot.capacity:
            raise HTTPException(409, "Slot is fully booked. Please choose another slot.")

    # Visitors are created as a transient pass tied to admin (no real user)
    pr = PassRequest(
        student_id=admin.id,  # Admin is the issuer; visitor has no account
        reason=f"Visitor: {data.visitor_name} - {data.reason}",
        pass_type=data.pass_type,
        status="pending",
        access_mode="visitor",
        slot_id=slot.id if slot else None,
        requires_face_check=False,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)

    # Auto-approve and generate token with custom TTL
    if slot:
        slot_end_exp = int(_to_utc_naive(slot.end_time).replace(tzinfo=timezone.utc).timestamp())
        requested_exp = int((datetime.now(timezone.utc) + timedelta(minutes=data.ttl_minutes)).timestamp())
        token, exp = make_qr_token_until(pr.id, admin.id, min(slot_end_exp, requested_exp))
    else:
        token, exp = make_qr_token(pr.id, admin.id, ttl_minutes=data.ttl_minutes)
    if exp <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(400, "Visitor pass expiry would be in the past")
    pr.status = "approved"
    pr.approved_by = admin.id
    pr.approved_time = now_local()
    pr.expiry_time = datetime.fromtimestamp(exp, tz=CAMPUS_TZ)
    pr.qr_token = token
    db.commit()
    db.refresh(pr)

    print(f"✅ Visitor pass #{pr.id} issued by {admin.name} for '{data.visitor_name}'")
    return pr


# ============================================================================
# ANALYTICS ENDPOINTS  (Pandas-backed)
# ============================================================================

@app.get("/api/analytics/peak-hours")
def analytics_peak_hours(
    days: int = 30,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Return peak access hours computed over the last N days."""
    try:
        import analytics as analytics_mod
        return analytics_mod.peak_hours(db, days=days)
    except ImportError:
        # Fallback without pandas
        return realtime_logs.get_hourly_stats(db)


@app.get("/api/analytics/trend")
def analytics_trend(
    days: int = 30,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Return 30-day daily entry/exit trend."""
    try:
        import analytics as analytics_mod
        return analytics_mod.daily_trend(db, days=days)
    except ImportError:
        return realtime_logs.get_daily_stats(db, days=days)


@app.get("/api/analytics/compliance")
def analytics_compliance(
    days: int = 30,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """GPS compliance rate and entry/exit ratio analytics."""
    try:
        import analytics as analytics_mod
        return analytics_mod.compliance_summary(db, days=days)
    except ImportError:
        stats = realtime_logs.get_log_statistics(db, days=days)
        entries = stats.get("entries", 0)
        exits = stats.get("exits", 0)
        total = entries + exits
        return {
            "entry_exit_ratio": round(entries / exits, 2) if exits > 0 else None,
            "entries": entries,
            "exits": exits,
            "success_rate": stats.get("success_rate", 0),
        }


@app.get("/api/analytics/export")
def analytics_export(
    days: int = 30,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Export scan log analytics as CSV."""
    from fastapi.responses import StreamingResponse
    import io

    try:
        import analytics as analytics_mod
        csv_content = analytics_mod.export_csv(db, days=days)
    except ImportError:
        # Basic CSV fallback
        from datetime import timedelta
        since = datetime.now() - timedelta(days=days)
        scans = db.query(ScanLog).filter(ScanLog.scan_time >= since).order_by(ScanLog.scan_time.desc()).all()
        lines = ["timestamp,pass_type,result,details"]
        for s in scans:
            lines.append(f"{s.scan_time.isoformat()},{s.pass_type},{s.result},{s.details or ''}")
        csv_content = "\n".join(lines)

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=securegate-analytics-{days}d.csv"},
    )


@app.get("/api/analytics/slot-utilization")
def analytics_slot_utilization(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Return slot utilization percentages for all slots."""
    slots = db.query(Slot).all()
    result = []
    for s in slots:
        booked = db.query(SlotBooking).filter(
            SlotBooking.slot_id == s.id,
            SlotBooking.booking_status == "confirmed",
        ).count()
        utilization = round(booked / s.capacity * 100, 1) if s.capacity > 0 else 0
        result.append({
            "slot_id": s.id,
            "label": s.label,
            "gate": s.gate,
            "capacity": s.capacity,
            "booked": booked,
            "utilization_pct": utilization,
            "active": s.active,
        })
    return {"slots": result}


# Mount static files (frontend)
# Get the parent directory (smart Gate folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Mount frontend directory with HTML mode so directory URLs resolve to index.html
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
