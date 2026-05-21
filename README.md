# SecureGate / Smart Gate System

SecureGate is a campus access-control prototype with production-oriented hardening. It replaces manual gate passes with authenticated portals, admin approval, HMAC-signed QR passes, guard verification, optional face checks, GPS policy checks, slot scheduling, realtime logs, and signed guardian history links.

The project is designed for a course-level demonstration and for a cautious production-style deployment path. Firebase and Twilio are optional integrations; the reliable default demo path uses browser-local alerts and signed parent links.

## Current Capabilities

- JWT login with role-based portals for students, admins, guards, and guardians.
- Admin-reviewed account requests and pass requests.
- HMAC-SHA256 QR tokens with expiry, one-time use, and tamper detection.
- Instant daily entry/exit passes with required GPS validation when geofencing is enabled.
- Slot-based access scheduling with capacity, bookings, slot-bound pass requests, and guard-side time-window enforcement.
- Optional face verification using the lightweight OpenCV backend by default.
- Admin visitor passes with QR rendering and optional slot binding.
- Guard QR scanning, optional live face capture, recent scans, and daily statistics.
- Admin realtime logs, statistics, analytics endpoints, geofence settings, users, slots, and visitor pass management.
- Guardian signed links for recent student entry/exit history.
- Docker and Render-oriented deployment files.

## Technology Stack

Backend:

- Python 3.11+
- FastAPI and Uvicorn
- SQLAlchemy
- SQLite for local demo, PostgreSQL recommended for production
- Pydantic v2 and pydantic-settings
- PyJWT, Passlib, bcrypt
- OpenCV headless and Pillow for default face-image processing
- geopy and Shapely for GPS/geofence policy
- pandas for analytics endpoints
- optional firebase-admin and Twilio

Frontend:

- HTML, CSS, vanilla JavaScript
- jsQR for in-browser guard QR scanning
- QRCode.js for QR rendering
- Chart.js for dashboards
- Leaflet for admin geofence configuration

## Project Layout

```text
backend/
  app.py                 FastAPI routes and application wiring
  auth.py                Password hashing, JWT auth, guardian link tokens
  crypto.py              QR HMAC token generation and parsing
  models.py              SQLAlchemy tables
  schemas.py             Pydantic request/response models
  runtime_schema.py      Safe additive schema updates for older DBs
  face_auth.py           OpenCV-first face authentication backend
  geofence.py            GPS/geofence validation
  realtime_logs.py       Admin log/statistics helpers
  analytics.py           pandas-backed analytics helpers
  tests/                 pytest test suite

frontend/
  index.html             Portal selector
  student/               Student/personnel portal
  admin/                 Admin dashboard, logs, location settings
  guard/                 Guard scanner portal
  parent/                Guardian signed-link portal
  common/                Shared config, API client, styles, utilities

Dockerfile
render.yaml
backend/requirements.txt
.env.example
```

## Local Setup

From the repository root:

```bash
cd "/home/madhu/Smart Gate/Smart-Gate-Sytem_Project"
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
cd backend
python bootstrap.py
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

Then open:

- Portal selector: `http://localhost:8080/frontend/`
- Student portal: `http://localhost:8080/frontend/student/`
- Admin portal: `http://localhost:8080/frontend/admin/`
- Guard portal: `http://localhost:8080/frontend/guard/`
- API docs: `http://localhost:8080/docs`

The helper script `START_SERVER.sh` performs the same local setup flow.

## Demo Accounts

The seed script creates demo accounts when `SMARTGATE_SEED_MODE=if_empty` and the database has no users.

Common demo admin:

```text
Email: admin@uni.edu
Password: admin123
Portal: /frontend/admin/
```

For any live demo, verify the seeded users in the Admin portal or `/docs` instead of assuming an old local database still has the same records.

## Environment Configuration

Copy `.env.example` to `backend/.env` for local development, or set equivalent variables in Render.

Important variables:

```env
DATABASE_URL=postgresql://user:password@host:5432/smartgate
SECRET_KEY=replace_with_random_32_plus_character_secret
JWT_SECRET=replace_with_another_random_secret
ALLOWED_ORIGINS=https://your-app.example.com
APP_ENV=development
ENABLE_DEBUG_ENDPOINTS=false
FACE_AUTH_ENABLED=true
FACE_AUTH_BACKEND=opencv
GEOFENCE_ENABLED=true
NOTIFICATIONS_ENABLED=false
```

Production mode is enabled with `APP_ENV=production`. In production, the app refuses default secrets, wildcard CORS, and SQLite.

## Core Workflows

### Student / Personnel

1. Sign in or submit an account request.
2. Save guardian contact information and share the generated guardian link.
3. Generate an instant daily entry/exit QR while on campus.
4. Request a regular admin-approved pass.
5. Book an access slot; the portal automatically submits a slot-bound pass request for approval.
6. Optionally enroll a face sample for face-required policies.

### Admin

1. Review account requests.
2. Approve or reject pass requests.
3. Manage users and reset biometric enrollment.
4. Create/deactivate slots with capacity, GPS policy, and face-check policy.
5. Issue visitor passes and render visitor QR codes.
6. Monitor logs, statistics, analytics, and geofence settings.

### Guard

1. Sign in to the guard portal.
2. Scan QR codes with the camera or paste a token manually.
3. For face-required passes, capture the live face image before verification.
4. The backend validates token signature, token owner, expiry, pass state, slot window, one-time use, and face policy.

### Guardian

1. Open the signed link generated by the student portal.
2. The portal validates the link automatically.
3. Browser alerts may be enabled locally.
4. Recent successful entry/exit history is shown from the signed history API.

## Slot-Bound Access Flow

Slot scheduling is implemented as part of the access flow, not only as a calendar feature.

1. Admin creates a slot with gate, start time, end time, capacity, and optional GPS/face requirements.
2. Student books a confirmed slot while capacity is available.
3. Student portal creates a pass request with `slot_id`.
4. Backend verifies the confirmed booking and links `slot_bookings.pass_id` to the pass.
5. Admin approves the pass.
6. QR expiry is capped so it cannot exceed the slot end time.
7. Guard verification enforces the slot window.
8. Face-required slot passes require a registered face and a successful live match.

## Security Notes

- QR token format: `pass_id.user_id.expiry.hmac_signature`.
- Tokens are signed with `SECRET_KEY` and checked server-side.
- `/verify` rejects malformed, tampered, expired, already-used, not-approved, and token-owner-mismatch passes.
- Daily entry/exit requires GPS when geofencing is enabled.
- Debug endpoints are disabled by default with `ENABLE_DEBUG_ENDPOINTS=false`.
- Face auth stores feature data, not raw uploaded images.
- OpenCV is the default face backend; heavier `face_recognition`/dlib behavior should be described only as an optional alternate backend if separately enabled and tested.

## Main API Surface

Authentication:

- `POST /auth/login`
- `POST /auth/register`
- `GET /auth/me`

Passes and verification:

- `POST /passes`
- `GET /passes`
- `POST /passes/{pass_id}/approve`
- `POST /passes/{pass_id}/reject`
- `POST /passes/daily-entry`
- `POST /verify`
- `GET /scans`
- `GET /scans/stats`

Slots and visitors:

- `POST /api/slots`
- `GET /api/slots`
- `POST /api/slots/{slot_id}/book`
- `GET /api/slots/my/bookings`
- `DELETE /api/slots/bookings/{booking_id}`
- `POST /api/admin/visitor-pass`

Guardian and notifications:

- `POST /api/update_contact`
- `GET /api/parent/access-token`
- `POST /api/register_parent_fcm`
- `GET /api/parent/student_history/{student_id}`

Admin operations:

- `GET /admin/registration-requests`
- `POST /admin/registration-requests/{request_id}/approve`
- `POST /admin/registration-requests/{request_id}/reject`
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PATCH /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`
- `GET /api/logs/recent`
- `GET /api/analytics/peak-hours`
- `GET /api/analytics/trend`
- `GET /api/analytics/compliance`
- `GET /api/analytics/export`
- `GET /api/analytics/slot-utilization`

## Verification

Recommended checks:

```bash
python3 -m py_compile $(find backend -name '*.py' -not -path '*/__pycache__/*')
python3 -m pytest -q backend/tests
find frontend -name '*.js' -print0 | xargs -0 -n1 node --check
npm run build
```

Also do a browser walkthrough of all four portals before a final demo.

## Deployment

Render deployment is supported through `Dockerfile` and `render.yaml`.

Use PostgreSQL for production:

```env
APP_ENV=production
DATABASE_URL=postgresql://...
SECRET_KEY=<strong random value>
JWT_SECRET=<strong random value>
ALLOWED_ORIGINS=https://your-render-domain.onrender.com
SMARTGATE_SEED_MODE=never
ENABLE_DEBUG_ENDPOINTS=false
```

Keep `NOTIFICATIONS_ENABLED=false` unless Firebase/Twilio credentials are configured and tested.

## Known Boundaries

- The default face backend is lightweight and demo-oriented; it should not be marketed as dlib/LFW-grade production biometrics.
- Visitor passes are QR-based and may be slot-bound, but face-required visitor slots are intentionally rejected.
- SQLite is acceptable for local demos only.
- Browser-local notifications depend on the current browser/device and are not a substitute for Firebase/Twilio push delivery.
