# SecureGate Complete End-to-End Test Flow

This document lists the implemented features and a practical end-to-end test plan for the complete SecureGate app. Use it as a QA checklist before demo, submission, or deployment.

## Read This First

Use this file in two passes:

1. **Quick demo pass:** follow the table below to confirm the main story works end to end.
2. **Full QA pass:** use the detailed sections after the feature inventory when you want to test every edge case.

## Quick Demo Pass

| Step | Portal | Action | Pass condition |
|---|---|---|---|
| 1 | Portal selector | Open `/frontend/` | All portal links are visible. |
| 2 | Admin | Log in as `admin@uni.edu` | Dashboard loads. |
| 3 | Student | Log in as `alice@uni.edu` | Student dashboard loads with no JS crash. |
| 4 | Admin | Create an active slot | Slot appears in Slots tab. |
| 5 | Student | Book that slot | Pending slot-bound pass is created. |
| 6 | Admin | Approve the pending pass | QR is generated. |
| 7 | Guard | Scan or manually verify QR | First scan is granted. |
| 8 | Guard | Scan same QR again | Replay is rejected. |
| 9 | Student | Generate daily entry with GPS allowed | Daily QR is created. |
| 10 | Admin | Create visitor pass | Visitor QR is shown. |
| 11 | Guard | Verify visitor QR | First scan is granted. |
| 12 | Guardian | Open signed guardian link | Link validates and history loads. |

Run the automated checks before manual testing:

```bash
cd "/home/madhu/Smart Gate/Smart-Gate-Sytem_Project"
backend/.venv/bin/python -m pytest -q backend/tests
find frontend -name '*.js' -print0 | xargs -0 -n1 node --check
npm run build
```

Expected quick result:

- Backend tests pass.
- JavaScript syntax checks pass.
- Frontend build passes.
- Camera, GPS, browser notifications, and face matching still need manual browser testing because they depend on real device permissions and image quality.

## 1. Implemented Feature Inventory

### Core Platform

- Multi-portal frontend:
  - Portal selector: `/frontend/`
  - Student/personnel portal: `/frontend/student/`
  - Admin portal: `/frontend/admin/`
  - Guard portal: `/frontend/guard/`
  - Guardian signed-link portal: `/frontend/parent/`
- FastAPI backend with OpenAPI docs at `/docs`.
- SQLite local database support and PostgreSQL-ready configuration.
- Docker/Render deployment support.
- Health endpoint: `GET /healthz`.

### Authentication And Roles

- JWT login through `/auth/login`.
- Current user profile through `/auth/me`.
- Role-gated portals:
  - `student`
  - `admin`
  - `guard`
- Account request flow:
  - Student/personnel or guard submits registration request.
  - Admin views pending requests.
  - Admin approves or rejects requests.
  - Approved request creates an active user.
- Admin user management:
  - List users.
  - Create user.
  - Edit user.
  - Activate/deactivate user.
  - Delete user.
  - Reset user face enrollment.

### Pass And QR Access

- Regular pass request:
  - Student submits entry/exit pass with reason.
  - Optional GPS coordinates are stored when available.
  - Admin approves or rejects.
  - Approved pass gets an HMAC-signed QR token.
- Daily instant entry/exit:
  - Student generates immediate QR pass.
  - GPS is required when geofencing is enabled.
  - Existing approved daily QR is reused only while active, unused, and unexpired.
- QR security:
  - HMAC signature validation.
  - Expiry validation.
  - Token user id must match pass owner.
  - Pass must be approved.
  - One-time use prevents replay.
- Guard verification:
  - Camera QR scanning.
  - Manual token verification.
  - Scan logs are recorded for success and failures.

### Slot Scheduling

- Admin creates time-windowed slots.
- Slot fields:
  - label
  - gate
  - start time
  - end time
  - capacity
  - active/inactive
  - GPS-required policy
  - face-check-required policy
- Student views available slots.
- Student books a slot.
- Booking automatically creates a slot-bound pass request.
- Backend validates:
  - slot exists and is active
  - slot has not ended
  - capacity is available
  - student has a confirmed booking
  - booking is not already linked to another pass
- Admin approves slot-bound pass.
- QR expiry is capped at the slot end time.
- Guard verification enforces the slot window.
- Face-required slots require successful face verification at the gate.

### Face Authentication

- OpenCV-based face authentication backend is the default.
- Student can upload/register a face image.
- Face status is shown in the student portal.
- Guard can perform QR plus face verification.
- Face-required pass behavior:
  - Missing face image is rejected.
  - Unregistered face is rejected.
  - Invalid image is rejected.
  - Mismatch is rejected.
  - Match is accepted.

### GPS And Location Policy

- Campus geofence validation with geopy/Shapely.
- Admin location settings UI.
- Public location settings endpoint for portals.
- Daily entry/exit requires GPS when geofence is enabled.
- Slot policy may require GPS before creating a slot-bound pass request.

### Guardian / Parent Access

- Student saves guardian contact details.
- Student generates signed guardian link.
- Guardian portal validates `student_id` and signed `access_token`.
- Guardian can see recent successful entry/exit history.
- Guardian can enable local browser alerts.
- Firebase/Twilio are optional and disabled unless configured.

### Visitor Pass

- Admin issues visitor pass.
- Visitor pass can be entry or exit.
- Visitor QR is rendered in the admin portal.
- Visitor pass may be slot-bound.
- Visitor pass is rejected for face-required slots.
- Guard verifies visitor QR like other QR passes.

### Realtime Logs And Analytics

- Admin live logs dashboard.
- WebSocket log updates.
- Recent scans.
- Scan statistics.
- Hourly activity.
- Daily activity.
- Top active students.
- Log search.
- Analytics endpoints:
  - peak hours
  - trends
  - compliance
  - CSV export
  - slot utilization

### Emergency Exit

- Student can request emergency exit from backend/API flow.
- Emergency scan log is created without a normal pass.
- Optional admin notification is attempted if notifications are configured.

### Production Hardening

- Debug endpoints disabled by default with `ENABLE_DEBUG_ENDPOINTS=false`.
- `/debug/check_password` no longer returns the submitted password or hash prefix.
- Production mode validates:
  - non-default `SECRET_KEY`
  - non-default `JWT_SECRET`
  - non-wildcard CORS origins
  - non-SQLite production database
- Notification failures do not block core access-control flows.

## 2. Test Environment Setup

### 2.1 Start The App

From the repository root:

```bash
cd "/home/madhu/Smart Gate/Smart-Gate-Sytem_Project"
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python bootstrap.py
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

Expected:

- Server starts without traceback.
- `http://localhost:8080/healthz` returns `{"status":"ok"}`.
- `http://localhost:8080/frontend/` opens the portal selector.
- `http://localhost:8080/docs` opens FastAPI docs.

### 2.2 Demo Accounts

These are seeded by `backend/seed.py` when the database is empty:

| Role | Email | Password | Portal |
|---|---|---|---|
| Admin | `admin@uni.edu` | `admin123` | `/frontend/admin/` |
| Guard | `guard@uni.edu` | `guard123` | `/frontend/guard/` |
| Guard | `scanner@uni.edu` | `scanner123` | `/frontend/guard/` |
| Student | `alice@uni.edu` | `alice123` | `/frontend/student/` |
| Student | `bob@uni.edu` | `bob123` | `/frontend/student/` |
| Student | `carol@uni.edu` | `carol123` | `/frontend/student/` |
| Student | `david@uni.edu` | `david123` | `/frontend/student/` |

If login fails because the local database is old or different:

```bash
cd backend
python seed.py
python add_students_with_parents.py
```

### 2.3 Browser Setup

Use three browser sessions:

- Normal window: Admin.
- Incognito/private window: Student.
- Second incognito/private window or different browser: Guard.

For GPS tests, either:

- Test while physically inside the configured campus radius, or
- In Chrome DevTools, use Sensors to emulate latitude/longitude inside the configured geofence, or
- First use Admin Location Settings to set the campus center near your current location.

## 3. Automated Smoke Checks

Run these before manual testing:

```bash
cd "/home/madhu/Smart Gate/Smart-Gate-Sytem_Project"
backend/.venv/bin/python -m py_compile $(find backend -name '*.py' -not -path '*/__pycache__/*' -not -path '*/.venv/*')
backend/.venv/bin/python -m pytest -q backend/tests
find frontend -name '*.js' -print0 | xargs -0 -n1 node --check
npm run build
```

Expected:

- Python compile succeeds.
- Pytest passes. Current expected result: `35 passed, 3 skipped`.
- JavaScript syntax check succeeds.
- `npm run build` succeeds.

## 4. Complete Manual End-To-End Flow

Follow the sections in order. Each section builds data used later.

## 4.1 Portal Selector

1. Open `http://localhost:8080/frontend/`.
2. Click Student/Personnel portal.
3. Return to selector.
4. Click Admin portal.
5. Return to selector.
6. Click Guard portal.
7. Return to selector.
8. Click Guardian portal only with a generated guardian link later.

Expected:

- Portal selector loads.
- Each portal route opens without 404.
- Browser console has no blocking JavaScript errors.

## 4.2 Authentication And Role Boundaries

### Admin Login

1. Open `/frontend/admin/`.
2. Log in with `admin@uni.edu` / `admin123`.

Expected:

- Admin dashboard opens.
- Registration requests and pass queues load.
- User is not redirected back to login.

### Student Login

1. Open `/frontend/student/`.
2. Log in with `alice@uni.edu` / `alice123`.

Expected:

- Student dashboard opens.
- Current pass, request pass, slot booking, biometrics, contact, and history panels are visible.

### Guard Login

1. Open `/frontend/guard/`.
2. Log in with `guard@uni.edu` / `guard123`.

Expected:

- Guard dashboard opens.
- Scanner/manual verification UI appears.
- Recent scan stats load.

### Negative Role Tests

1. Try admin credentials in Student portal.
2. Try student credentials in Guard portal.
3. Try guard credentials in Admin portal.

Expected:

- Each wrong portal rejects the login or shows a role-specific error.
- No wrong-role dashboard opens.

## 4.3 Account Request Flow

Use a new email that is not already in the database.

### Student/Personnel Request

1. Open Student portal.
2. Click "Request access".
3. Enter:
   - name: `Test Personnel`
   - email: `test.personnel@example.com`
   - password: `TestPass123`
   - personnel type: Student or Faculty/staff
   - optional ID/class/phone
4. Submit request.

Expected:

- Success/info message says request was submitted.
- User is returned to login form.

### Admin Approval

1. Log in as admin.
2. Open account requests/clearances.
3. Find `test.personnel@example.com`.
4. Approve it.

Expected:

- Request status changes to approved.
- New user appears in Users.
- New user can log in through Student portal.

### Rejection Test

1. Submit another request with a different email.
2. Reject it as admin.

Expected:

- Request status becomes rejected.
- Rejected user cannot log in.

## 4.4 Admin User Management

1. Log in as admin.
2. Open Users tab.
3. Search for an existing student.
4. Edit the user name or phone.
5. Save.
6. Deactivate the user.
7. Try logging in as that user.
8. Reactivate the user.
9. Reset face enrollment for the user.

Expected:

- Search filters work.
- Edit persists after refresh.
- Inactive user cannot log in.
- Reactivated user can log in again.
- Reset face clears biometric status.

## 4.5 Guardian Contact And Signed Parent Link

1. Log in as student `alice@uni.edu`.
2. In Emergency contact, fill:
   - Your phone: `+12025550100`
   - Guardian name: `QA Guardian`
   - Guardian phone: `+12025550200`
3. Save contact info.
4. Copy the generated guardian share link.
5. Open the link in a separate incognito window.

Expected:

- Contact save succeeds.
- Guardian link is generated with `student_id`, `student_name`, `parent_name`, `parent_phone`, and `access_token`.
- Guardian portal auto-validates the link.
- Guardian confirmation page appears.
- Clicking "Establish Guardian Link" completes setup.
- Current status and audit log sections load.

Negative guardian tests:

1. Remove `access_token` from URL and reload.
2. Change `student_id` in URL and reload.

Expected:

- Missing token shows link failure.
- Mismatched student/token shows link failure.

## 4.6 Daily GPS Entry/Exit

Before this test, ensure GPS is inside the configured campus geofence.

Option A: Use browser GPS if physically on campus.

Option B: Admin sets campus center:

1. Log in as admin.
2. Open Location Settings page if available from Admin portal, or open `/frontend/admin/location.html`.
3. Set latitude/longitude near your current test device location.
4. Set a radius such as `2.0 km`.
5. Save.

Test daily entry:

1. Log in as student.
2. Allow browser location permission.
3. Click daily Entry.

Expected:

- QR pass is generated immediately.
- Current pass panel shows approved entry pass.
- QR code is visible.
- Expiry time is shown.

Test daily exit:

1. Click daily Exit.

Expected:

- QR pass is generated immediately for exit.

Negative GPS test:

1. Block location permission in browser.
2. Click daily Entry or Exit.

Expected:

- App refuses to generate daily pass.
- Error says GPS/location is required.

Negative outside-geofence test:

1. Use DevTools Sensors to set a location outside campus radius.
2. Click daily Entry.

Expected:

- Backend rejects with location verification failure.

## 4.7 Regular Pass Request And Admin Approval

1. Log in as student.
2. Enter reason: `Library access test`.
3. Click Regular entry.

Expected:

- Pending pass request is created.
- Student dashboard shows pending approval.

Admin approval:

1. Log in as admin.
2. Open Passes or Requests tab.
3. Find the pending `Library access test` pass.
4. Approve it.

Expected:

- Pass status becomes approved.
- QR token is generated.
- Student refresh shows approved QR.

Admin rejection:

1. Student submits another regular pass with reason `Reject test`.
2. Admin rejects it.

Expected:

- Student history shows rejected status.
- No QR is shown for rejected pass.

## 4.8 Guard QR Verification

Use the approved QR from the student daily or regular pass.

Camera scan path:

1. Log in as guard.
2. Start camera scanner.
3. Show the student QR on another screen/window.
4. Scan it.

Expected:

- Guard sees `GRANTED`.
- Student name and ID are shown.
- Pass becomes used.
- Scan log is created.

Replay negative test:

1. Scan the same QR again.

Expected:

- Guard sees rejection.
- Backend reason is replay or not-approved/used.
- Failure log is created.

Manual token path:

If you need the raw QR token, fetch it through API:

```bash
STUDENT_TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@uni.edu&password=alice123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8080/passes \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  | python3 -m json.tool
```

Copy an approved `qr_token`, paste it in Guard manual verification, and verify.

Expected:

- Valid unused approved token is granted.
- Used/expired/tampered token is rejected.

## 4.9 Slot Scheduling End-To-End

### Create Normal Slot

1. Log in as admin.
2. Open Slots tab.
3. Create slot:
   - label: `QA Entry Slot`
   - gate: `Main Gate`
   - start: now minus 5 minutes or a near-future time
   - end: now plus 30 minutes
   - capacity: `2`
   - GPS required: off
   - Face check required: off
4. Save.

Expected:

- Slot appears in list.
- Remaining capacity shows `2`.
- Slot is active.

### Book Slot And Create Slot-Bound Pass

1. Log in as student.
2. Open Access slot booking.
3. Find `QA Entry Slot`.
4. Select pass type by clicking Regular entry or Regular exit if needed.
5. Click Book Slot.

Expected:

- Booking succeeds.
- Slot-bound pass request is created automatically.
- Student sees reservation.
- Student sees pending pass request.

### Approve Slot-Bound Pass

1. Log in as admin.
2. Open pass requests.
3. Approve the slot-bound pass.

Expected:

- Pass becomes approved.
- QR expiry is not later than slot end time.

### Verify Inside Slot Window

1. Log in as guard.
2. Scan the slot-bound QR during the slot window.

Expected:

- Access granted.
- Scan log created.
- Pass becomes used.

### Negative Slot Tests

Capacity:

1. Create a slot with capacity `1`.
2. Book it with student A.
3. Try booking with student B.

Expected:

- Student B cannot book once capacity is full.

Duplicate booking:

1. Same student books a slot.
2. Same student attempts booking same slot again.

Expected:

- Duplicate booking is rejected.

Expired slot:

1. Create a slot that ends soon.
2. Approve pass.
3. Wait until slot end.
4. Guard scans QR.

Expected:

- Verification rejects with outside slot window or expired token.

Inactive slot:

1. Admin deactivates a slot.
2. Student tries to book.

Expected:

- Booking is blocked.

## 4.10 Face Enrollment And Face-Required Slot

This test needs a usable face image and camera access.

### Enroll Face

1. Log in as student.
2. Open Biometrics.
3. Upload a clear face photo.
4. Click Enroll biometrics.

Expected:

- Face registration succeeds, or a clear image-quality/no-face error appears.
- Face status changes to enrolled if successful.

### Create Face-Required Slot

1. Log in as admin.
2. Create a slot:
   - label: `QA Face Slot`
   - capacity: `1`
   - face check required: on
   - GPS required: off unless you want to test GPS too
   - current active time window
3. Student books slot.
4. Admin approves slot-bound pass.

### Guard Verify Without Face

1. Log in as guard.
2. Try manual QR verification without face image, or turn off face capture if available.

Expected:

- Verification is rejected with face-required reason.

### Guard Verify With Face

1. Use guard QR plus face capture flow.
2. Scan QR.
3. Capture matching live face.

Expected:

- Verification grants only if face matches.
- Response includes face verification details.

Negative face tests:

- Use unregistered student with face-required slot: rejected.
- Upload too-small or invalid face image: rejected.
- Use different person for face capture: rejected.

## 4.11 Visitor Pass Flow

### Visitor Without Slot

1. Log in as admin.
2. Open Visitors tab.
3. Generate visitor pass:
   - name: `QA Visitor`
   - phone: optional
   - reason: `Campus meeting`
   - type: entry
   - TTL: `60`
4. Submit.

Expected:

- Visitor pass is issued.
- QR code is rendered in admin portal.
- Expiry is shown.

Guard test:

1. Log in as guard.
2. Scan visitor QR.

Expected:

- Access granted if QR is unused and unexpired.
- Replay scan is rejected.

### Visitor With Slot

1. Create a normal slot with face check off.
2. Generate visitor pass with that slot if UI/API supports slot selection.

Expected:

- Visitor QR is issued.
- Guard enforces slot window.

Negative visitor face-required slot:

1. Create a face-required slot.
2. Try issuing visitor pass for that slot through API or UI if slot selection exists.

Expected:

- Backend rejects visitor pass for face-required slot.

## 4.12 Emergency Exit

If the student UI exposes the emergency action, test from the UI. If not, test through API:

```bash
STUDENT_TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@uni.edu&password=alice123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8080/api/emergency_exit \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"QA emergency exit test"}' \
  | python3 -m json.tool
```

Expected:

- Emergency exit succeeds.
- Scan log is created with emergency flag/details.
- Admin logs show the emergency event.
- Notifications are attempted only if configured.

## 4.13 Admin Logs And Analytics

### Realtime Logs

1. Log in as admin.
2. Open logs dashboard: `/frontend/admin/logs.html`.
3. In another browser, guard verifies a QR.

Expected:

- Recent log appears.
- Statistics update or refresh correctly.
- No WebSocket crash in console.

### Search And Filters

1. Search logs by student ID.
2. Filter by entry/exit if controls exist.
3. Export CSV if available.

Expected:

- Search results match student.
- Export downloads or returns CSV.

### Analytics API

Use admin token:

```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@uni.edu&password=admin123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8080/api/analytics/peak-hours \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

curl -s http://localhost:8080/api/analytics/trend \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

curl -s http://localhost:8080/api/analytics/compliance \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

curl -s http://localhost:8080/api/analytics/slot-utilization \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Expected:

- Each endpoint returns JSON.
- Slot utilization includes created slots.
- Compliance endpoint handles empty data gracefully.

## 4.14 Location Settings

1. Log in as admin.
2. Open `/frontend/admin/location.html`.
3. Check current campus settings.
4. Change campus name, latitude, longitude, and radius.
5. Save.
6. Open student portal and generate daily entry with GPS inside new radius.
7. Generate daily entry with GPS outside radius.

Expected:

- Location settings persist.
- Inside radius is accepted.
- Outside radius is rejected.

## 4.15 Security Negative Tests

### Debug Endpoints Disabled

```bash
curl -i http://localhost:8080/debug/users
curl -i "http://localhost:8080/debug/check_password?email=admin@uni.edu&password=admin123"
```

Expected:

- Both return `404` unless `ENABLE_DEBUG_ENDPOINTS=true`.

### Tampered QR Token

1. Get a valid token.
2. Change one digit in pass id, user id, expiry, or signature.
3. Submit in Guard manual verify.

Expected:

- Rejected with invalid/signature mismatch.
- No access granted.

### Token User Mismatch

This is easiest through a direct generated/tampered token in tests, but manual tampering of user id should also fail.

Expected:

- Rejected with user mismatch or signature mismatch.

### Expired Token

1. Use an old approved QR after expiry.
2. Or create a short TTL visitor pass and wait until expiry.

Expected:

- Rejected as expired.

### Replay Token

1. Scan a valid QR once.
2. Scan it again.

Expected:

- First scan grants.
- Second scan rejects.

## 4.16 Production Settings Check

Do not run production mode with defaults. To test validation intentionally:

```bash
cd backend
APP_ENV=production \
SECRET_KEY=change_me_32+_random_secret_key_here \
JWT_SECRET=change_me_jwt_secret_key_here \
ALLOWED_ORIGINS="*" \
.venv/bin/python -c "import app"
```

Expected:

- App refuses to start because production settings are unsafe.

Then test safe-style production configuration:

```bash
APP_ENV=production \
SECRET_KEY="replace_with_a_long_random_secret_123456" \
JWT_SECRET="replace_with_another_long_random_secret_123456" \
ALLOWED_ORIGINS="https://example.com" \
DATABASE_URL="postgresql://user:password@localhost:5432/smartgate" \
.venv/bin/python -c "from settings import settings; print(settings.APP_ENV)"
```

Expected:

- Settings load. Full app import still needs a reachable PostgreSQL database.

## 5. Final Demo Script Order

For a clean live demonstration, use this order:

1. Open portal selector.
2. Admin login.
3. Student login.
4. Student saves guardian contact and opens guardian link.
5. Admin creates normal slot.
6. Student books slot and creates slot-bound pass.
7. Admin approves pass.
8. Guard scans slot-bound QR inside slot window.
9. Admin opens realtime logs and shows scan.
10. Student generates daily GPS pass.
11. Guard scans daily QR.
12. Admin creates visitor pass and shows visitor QR.
13. Guard scans visitor QR.
14. Show negative replay scan.
15. Show README/docs/API docs briefly.

## 6. Pass/Fail Checklist

Mark each item before final submission:

- [ ] Server starts.
- [ ] `/healthz` returns ok.
- [ ] Portal selector loads.
- [ ] Admin login works.
- [ ] Student login works.
- [ ] Guard login works.
- [ ] Wrong-role portal login is blocked.
- [ ] Account request submit works.
- [ ] Admin approve account works.
- [ ] Admin reject account works.
- [ ] Admin user create/edit/deactivate/reactivate works.
- [ ] Guardian contact save works.
- [ ] Guardian signed link validates.
- [ ] Guardian history loads.
- [ ] Daily GPS entry works inside geofence.
- [ ] Daily GPS entry rejects missing/outside GPS.
- [ ] Regular pass request works.
- [ ] Admin pass approval generates QR.
- [ ] Admin pass rejection works.
- [ ] Guard QR scan grants valid pass.
- [ ] Guard replay scan rejects used pass.
- [ ] Admin slot creation works.
- [ ] Student slot booking works.
- [ ] Slot booking creates pending slot-bound pass.
- [ ] Admin approval of slot-bound pass works.
- [ ] Guard enforces slot window.
- [ ] Slot capacity rejection works.
- [ ] Duplicate slot booking rejection works.
- [ ] Face enrollment works or gives clear image-quality error.
- [ ] Face-required slot rejects missing/unregistered face.
- [ ] Face-required slot grants matching face.
- [ ] Visitor QR generation works.
- [ ] Visitor QR guard verification works.
- [ ] Visitor face-required slot is rejected.
- [ ] Emergency exit API/UI works.
- [ ] Admin logs show scan events.
- [ ] Analytics endpoints return valid JSON.
- [ ] Location settings persist.
- [ ] Debug endpoints are disabled.
- [ ] Automated tests pass.
- [ ] README matches actual behavior.

## 7. Known Testing Notes

- Browser GPS must be allowed and inside the configured geofence for daily passes.
- Face testing depends on image quality, lighting, and camera permissions.
- Browser-local notifications work only on the current device/browser.
- Firebase/Twilio require real credentials and are not part of the default demo path.
- Existing local databases may contain old records; run seed scripts or start with a fresh local DB for the cleanest demo.
