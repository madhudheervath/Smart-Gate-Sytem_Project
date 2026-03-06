
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from database import Base, engine, get_db, SessionLocal
from models import User, RegistrationRequest, PassRequest, ScanLog
from schemas import *
from schemas import UserRegister
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
from crypto import make_qr_token, parse_token
from settings import settings
from crud import log_scan, mark_used
from fastapi.security import OAuth2PasswordRequestForm
import hmac
import hashlib
import importlib
import os

# Optional imports - disable if not installed or explicitly turned off via env
FACE_AUTH_ENABLED = settings.FACE_AUTH_ENABLED
_face_auth_module = None
_face_auth_import_error = None

if FACE_AUTH_ENABLED:
    print("✅ Face authentication enabled by configuration; face stack will load on demand")
else:
    print("⚠️  Face authentication disabled by configuration")

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
        print("✅ Face authentication module loaded successfully")
        return _face_auth_module
    except Exception as e:
        _face_auth_import_error = str(e)
        print(f"⚠️  Face authentication unavailable: {e}")
        return None

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)

app = FastAPI(title="GatePass QR Prototype")

@app.get("/debug/users")
def list_users(
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
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
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"status": "error", "message": "User not found"}
    
    is_valid = verify_pwd(password, user.pwd_hash)
    return {
        "status": "success" if is_valid else "failed",
        "email": user.email,
        "password_provided": password,
        "is_valid": is_valid,
        "hash_prefix": user.pwd_hash[:10] if user.pwd_hash else "None"
    }

# CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# create tables
Base.metadata.create_all(bind=engine)

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
    current_year = now_ist().year
    return datetime(current_year + 1, 6, 30, tzinfo=IST)


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
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
        latest_request.created_at = now_ist()
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
    registration_request.reviewed_at = now_ist()
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
    registration_request.reviewed_at = now_ist()
    registration_request.reviewed_by = admin.id
    registration_request.review_notes = _normalize_optional_text(review.review_notes)
    registration_request.created_user_id = None

    db.commit()
    db.refresh(registration_request)
    return _serialize_registration_request(db, registration_request)

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
    user.last_notification_at = datetime.now(IST)
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
    print(f"DEBUG: Creating pass with pass_type={p.pass_type}, reason={p.reason}")
    
    # GPS Geofencing validation (optional but logged)
    location_verified = False
    location_distance = None
    if GEOFENCE_ENABLED and p.latitude is not None and p.longitude is not None:
        is_valid, message, details = geofence.validate_student_location(p.latitude, p.longitude)
        location_verified = is_valid
        location_distance = str(details.get('distance_km', ''))
        print(f"GPS: {message} - Lat: {p.latitude}, Lon: {p.longitude}")
        
        # Optional: Reject if outside campus (uncomment to enforce)
        # if not is_valid:
        #     raise HTTPException(status_code=403, detail=f"Location denied: {message}")
    
    pr = PassRequest(
        student_id=user.id, 
        reason=p.reason, 
        status="pending", 
        pass_type=p.pass_type,
        request_latitude=str(p.latitude) if p.latitude else None,
        request_longitude=str(p.longitude) if p.longitude else None,
        location_verified=location_verified,
        location_distance_km=location_distance
    )
    db.add(pr)
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
    
    print(f"DEBUG: Created pass ID {pr.id} with pass_type={pr.pass_type}, GPS verified={location_verified}")
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
        pass_dict = {
            "id": p.id,
            "student_id": p.student_id,
            "reason": p.reason,
            "status": p.status,
            "pass_type": p.pass_type or "entry",
            "request_time": p.request_time,
            "approved_time": p.approved_time,
            "expiry_time": p.expiry_time,
            "qr_token": p.qr_token,
            "used_time": p.used_time,
        }
        # get student info
        student = db.get(User, p.student_id)
        if student:
            pass_dict["student_name"] = student.name
            pass_dict["student_code"] = student.student_id
            pass_dict["student_class"] = student.student_class
        result.append(pass_dict)
    
    return result

# --- Admin: approve/reject ---
@app.post("/passes/{pass_id}/approve", response_model=PassOut)
def approve(pass_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    pr = db.get(PassRequest, pass_id)
    if not pr:
        raise HTTPException(404, "Not found")
    if pr.status != "pending":
        raise HTTPException(400, "Already decided")
    token, exp = make_qr_token(pr.id, pr.student_id)
    pr.status = "approved"
    pr.approved_by = user.id
    pr.approved_time = now_ist()
    pr.expiry_time = datetime.fromtimestamp(exp, tz=IST)
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

    now = int(now_ist().timestamp())

    if sig_recv != expected:
        return _fail(db, pid, uid, guard.id, "invalid", "sig-mismatch")
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
    
    print(f"DEBUG: Face image received: {face_image is not None}")
    print(f"DEBUG: Face auth enabled: {FACE_AUTH_ENABLED}")
    print(f"DEBUG: Student from pass: {student.name if student else 'None'} (ID: {student.student_id if student else 'None'})")
    print(f"DEBUG: Pass belongs to student_id: {pr.student_id}")
    
    if FACE_AUTH_ENABLED and face_image and student:
        try:
            face_auth_module = get_face_auth_module()
            if face_auth_module is None:
                return _fail(db, pid, uid, guard.id, "invalid", "face-service-unavailable")

            print(f"DEBUG: Verifying face for: {student.name} ({student.student_id})")
            print(f"DEBUG: Student face registered: {student.face_registered}")
            # Check if student has registered face
            if student.face_registered and student.face_encoding:
                print("DEBUG: Reading face image bytes...")
                # Read uploaded face image
                image_bytes = await face_image.read()
                print(f"DEBUG: Face image size: {len(image_bytes)} bytes")
                
                # Validate image
                is_valid, error_msg = face_auth_module.validate_image(image_bytes)
                print(f"DEBUG: Image validation: {is_valid}, {error_msg}")
                if is_valid:
                    print("DEBUG: Extracting face encoding from captured image...")
                    # Extract face encoding from uploaded image
                    check_encoding = face_auth_module.extract_face_encoding(image_bytes)
                    print(f"DEBUG: Face encoding extracted: {check_encoding is not None}")
                    
                    if check_encoding is not None:
                        # Get stored encoding for THIS specific student
                        stored_encoding = face_auth_module.json_to_encoding(student.face_encoding)
                        print(f"DEBUG: Comparing captured face with {student.name}'s registered face")
                        
                        # Compare faces with stricter tolerance (0.5 instead of 0.6)
                        is_match, distance = face_auth_module.compare_faces(stored_encoding, check_encoding, tolerance=0.5)
                        print(f"DEBUG: Face comparison result:")
                        print(f"       - Student: {student.name} ({student.student_id})")
                        print(f"       - Match: {is_match}")
                        print(f"       - Distance: {distance:.4f}")
                        print(f"       - Tolerance: 0.5")
                        
                        # Get confidence
                        confidence_info = face_auth_module.get_confidence_level(distance)
                        
                        # Convert numpy types to Python native types for JSON serialization
                        face_verified = bool(is_match)
                        face_confidence = int(confidence_info["confidence_percent"])
                        face_distance = float(distance)
                        
                        if is_match:
                            face_message = f"Face matches {student.name} - {confidence_info['description']}"
                        else:
                            face_message = f"Face does NOT match {student.name} (distance: {distance:.3f})"
                        
                        print(f"DEBUG: Final result - Match: {is_match}, Confidence: {face_confidence}%, Message: {face_message}")
                    else:
                        return _fail(db, pid, uid, guard.id, "invalid", "face-not-detected")
                else:
                    return _fail(db, pid, uid, guard.id, "invalid", f"face-invalid-image:{error_msg}")
            else:
                face_message = f"{student.name} has not registered face"
                print(f"DEBUG: {face_message}")
        except Exception as e:
            print(f"Face verification error: {e}")
            import traceback
            traceback.print_exc()
            return _fail(db, pid, uid, guard.id, "invalid", "face-verification-error")

    if face_verified is False:
        return _fail(db, pid, uid, guard.id, "invalid", "face-mismatch")

    mark_used(db, pr, guard.id)
    log_scan(db, pid, pr.student_id, guard.id, "success", "verified", pass_type=pr.pass_type or "entry")
    
    # Send entry/exit notification to parents
    if NOTIFICATIONS_ENABLED and student:
        try:
            timestamp = now_ist().strftime("%I:%M %p")
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
        print(f"DEBUG: Response includes face verification data")
    else:
        print(f"DEBUG: No face verification data in response - face_verified is None")
    
    print(f"DEBUG: Final response: {response}")
    return response

def _fail(db, pid, uid, gid, result, details):
    try:
        # For failed scans, try to get pass_type from the pass if it exists
        pass_type = "entry"  # default
        if pid:
            pr = db.get(PassRequest, pid)
            if pr:
                pass_type = pr.pass_type or "entry"
        log_scan(db, pid or 0, uid or 0, gid, result, details, pass_type=pass_type)
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
    
    print(f"DEBUG: Received pass_type={pass_type}, data={data}")
    
    # GPS Geofencing validation
    location_verified = False
    location_distance = None
    if GEOFENCE_ENABLED and data.latitude is not None and data.longitude is not None:
        is_valid, message, details = geofence.validate_student_location(data.latitude, data.longitude)
        location_verified = is_valid
        location_distance = str(details.get('distance_km', ''))
        print(f"GPS: {message} - Lat: {data.latitude}, Lon: {data.longitude}")
        
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
            # Make it timezone-aware (assume it was stored as IST)
            valid_until = valid_until.replace(tzinfo=IST)
        if now_ist() > valid_until:
            raise HTTPException(status_code=403, detail="Student validity expired. Please contact an Access Control Administrator.")
    
    # Check if student already has an active pass of this type for today (IST)
    now_ist_time = now_ist()
    today_ist = now_ist_time.date()
    today_start_ist = datetime.combine(today_ist, datetime.min.time()).replace(tzinfo=IST)
    
    existing = db.query(PassRequest).filter(
        PassRequest.student_id == user.id,
        PassRequest.status.in_(["approved", "pending"]),
        PassRequest.request_time >= today_start_ist,
        PassRequest.pass_type == pass_type,
        PassRequest.reason.like(f"Daily {pass_label}%")
    ).first()
    
    if existing and existing.status == "approved":
        # Return existing QR if already generated today
        return existing
    
    if existing and existing.status == "pending":
        # Auto-approve if pending
        token, exp = make_qr_token(existing.id, user.id)
        existing.status = "approved"
        existing.approved_by = user.id  # Self-approved
        existing.approved_time = now_ist()
        existing.expiry_time = datetime.fromtimestamp(exp, tz=IST)
        existing.qr_token = token
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new auto-approved pass (use IST date)
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
        location_distance_km=location_distance
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    
    # Auto-approve and generate QR
    token, exp = make_qr_token(pr.id, user.id)
    pr.status = "approved"
    pr.approved_by = user.id  # Self-approved
    pr.approved_time = now_ist()
    pr.expiry_time = datetime.fromtimestamp(exp, tz=IST)
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
    # Get IST timezone info
    now = now_ist()
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
        
        # Store encoding
        user.face_encoding = face_auth_module.encoding_to_json(encoding)
        user.face_registered = True
        user.face_registered_at = now_ist()
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
        stored_encoding = face_auth_module.json_to_encoding(student.face_encoding)
        
        # Compare faces
        is_match, distance = face_auth_module.compare_faces(stored_encoding, check_encoding, tolerance=0.6)
        
        # Get confidence level
        confidence_info = face_auth_module.get_confidence_level(distance)
        
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
        return {
            "face_registered": user.face_registered,
            "face_registered_at": user.face_registered_at,
            "can_register": user.role == "student"
        }
else:
    # Provide stub endpoints when face auth is disabled
    @app.get("/api/face_status")
    def get_face_status_disabled(user: User = Depends(get_current_user)):
        """Get face registration status (disabled)"""
        return {
            "face_registered": False,
            "face_registered_at": None,
            "can_register": False,
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
    
    # Create emergency scan log immediately
    from sqlalchemy import text
    
    now = datetime.now(IST)
    
    # Insert emergency exit log
    db.execute(text("""
        INSERT INTO scan_logs (student_id, scanner_id, pass_id, scan_time, result, pass_type, emergency, details)
        VALUES (:student_id, :scanner_id, :pass_id, :scan_time, :result, :pass_type, :emergency, :details)
    """), {
        "student_id": user.id,
        "scanner_id": user.id,  # Self-scan
        "pass_id": 0,  # No pass required for emergency
        "scan_time": now,
        "result": "success",
        "pass_type": "exit",
        "emergency": True,
        "details": f"Emergency Exit: {request_data.reason}"
    })
    
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
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(realtime_logs.broadcast_new_scan(scan_data))
                else:
                    loop.run_until_complete(realtime_logs.broadcast_new_scan(scan_data))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(realtime_logs.broadcast_new_scan(scan_data))
                loop.close()
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

# Mount static files (frontend)
# Get the parent directory (smart Gate folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Mount frontend directory with HTML mode so directory URLs resolve to index.html
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
