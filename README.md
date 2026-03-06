# 🎓 Smart Gate System - Complete Documentation

![Version](https://img.shields.io/badge/version-2.2-blue) ![Python](https://img.shields.io/badge/python-3.11+-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal)

**A comprehensive AI-powered campus gate management system** with QR authentication, face recognition, GPS geofencing, and real-time notifications.

---

## 📑 Table of Contents

1. [Overview](#-overview)
2. [Key Features](#-key-features)
3. [Technology Stack](#-technology-stack)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Usage Guide](#-usage-guide)
7. [API Documentation](#-api-documentation)
8. [Database Schema](#-database-schema)
9. [Security](#-security)
10. [Troubleshooting](#-troubleshooting)

---

## 🌟 Overview

The **Smart Gate System** replaces traditional paper-based gate passes with a secure, efficient digital solution combining:

- ✅ **Digital QR Codes** - HMAC-signed, time-limited passes
- ✅ **Face Recognition** - 128-D encoding with 99.38% accuracy
- ✅ **GPS Geofencing** - Location-based access control
- ✅ **Notifications & Parent Access** - Browser alerts, SMS backup, secure parent portal links
- ✅ **Multi-Portal Architecture** - Student, Admin, Guard, Parent interfaces
- ✅ **Admin Location Control** - Configure campus via web UI

### Architecture

```
┌─────────────────────────────────────────────────────┐
│          CLIENT LAYER (4 Portals)                   │
│  Student │ Admin │ Guard │ Parent                   │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│           FastAPI Backend (Python)                   │
│  Auth │ Pass Mgmt │ QR Verify │ Face │ GPS │ Notif  │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  SQLite DB │ dlib/face_rec │ Firebase │ Twilio     │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features

### 1. **Authentication & Security**

#### HMAC-SHA256 QR Codes
- **Format**: `{pass_id}.{user_id}.{expiry}.{hmac_sig}`
- Tamper-proof cryptographic signatures
- Time-limited (default: 15 min)
- One-time use (replay prevention)

#### Face Recognition
- **Tech**: dlib + face_recognition
- 128-D face encoding
- One-time registration
- 99.38% accuracy (LFW benchmark)
- No images stored (only encodings)

#### Role-Based Access
- **Student**: Request passes, generate QR, daily entry
- **Admin**: Approve passes, analytics, location config
- **Guard**: Scan QR, verify faces
- **Parent**: View activity with a signed link (no separate login)

### 2. **GPS Geofencing**

- Circular geofence around campus
- Admin configurable via web UI
- Interactive map with Leaflet.js
- Real-time distance calculation
- Auto-detect location feature

**Configuration:**
```json
{
  "campus_name": "Campus",
  "latitude": 31.7768,
  "longitude": 77.0144,
  "radius_km": 2.0,
  "enabled": true
}
```

### 3. **Pass Types**

#### Outing Pass
- Request → Admin approval → QR generation
- Time-limited
- Entry/Exit tracking

#### Daily Entry Pass
- Instant generation
- GPS verification required
- 24-hour validity
- No admin approval

### 4. **Notifications**

- **Browser Alerts**: Local browser notifications on the current device
- **Twilio SMS**: Text alerts when backend credentials are configured
- **Parent Portal**: Signed-link access to recent student activity
- **Events**: Approval, rejection, entry/exit, expiry

### 5. **Analytics**

- Real-time dashboard
- Pass statistics
- Entry/exit trends
- Scan logs
- Audit trails

---

## 💻 Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.11+** | Core language |
| **FastAPI** | Web framework |
| **SQLAlchemy** | ORM |
| **SQLite/PostgreSQL** | Database |
| **PyJWT** | Token auth |
| **Passlib** | Password hashing |
| **dlib** | Face detection |
| **face-recognition** | Face encoding |
| **Shapely** | Geofencing |
| **geopy** | Distance calc |
| **firebase-admin** | Push notifications |

### Frontend
- HTML5, CSS3, JavaScript (ES6+)
- QRCode.js (generation)
- html5-qrcode (scanning)
- Leaflet.js (maps)
- Fetch API

---

## 🚀 Installation

### Quick Setup (Ubuntu - RECOMMENDED)

```bash
cd "/home/madhu/smart Gate"
bash UBUNTU_SETUP.sh
```

This installs everything automatically (10-15 minutes).

### Manual Installation

#### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3-dev python3-pip build-essential cmake
sudo apt install -y libboost-all-dev libopenblas-dev liblapack-dev
```

#### 2. Install Python Packages

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Initialize Database

```bash
python bootstrap.py
python add_students_with_parents.py
```

Tables are created automatically by the backend and bootstrap flow using SQLAlchemy metadata. Alembic is included for a safe baseline migration. Demo users are seeded only when the database is empty by default.

---

## ⚙️ Configuration

### Environment Variables

Create `backend/.env`:

```bash
# Security
SECRET_KEY=your-super-secret-key-32-chars-min
JWT_SECRET=your-jwt-secret

# Database
DB_URL=sqlite:///./gatepass.db
# Production: DATABASE_URL=postgresql://user:pass@host:5432/gatepass

# Token Expiry
ACCESS_TOKEN_EXPIRE_MINUTES=720
QR_TTL_MINUTES=15
SMARTGATE_SEED_MODE=if_empty
SELF_REGISTRATION_ENABLED=false
ACCOUNT_REQUESTS_ENABLED=true

# Firebase (optional)
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}

# Twilio SMS (optional)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Feature toggles
FACE_AUTH_ENABLED=true
FACE_AUTH_BACKEND=opencv
NOTIFICATIONS_ENABLED=false
GEOFENCE_ENABLED=true
```

### Location Settings

**Via Admin Portal:**
1. Login as admin → Location Settings
2. Use interactive map or auto-detect
3. Set radius and save

**Via JSON File:** `backend/location_settings.json`

### Production Deployment

Render is the recommended production target for this project because the backend depends on heavy native Python packages for face recognition and computer vision.

- Render deployment guide: [RENDER_DEPLOYMENT.md](/home/madhu/smart%20Gate/RENDER_DEPLOYMENT.md)
- Render blueprint: [render.yaml](/home/madhu/smart%20Gate/render.yaml)

If you already have a stable Render PostgreSQL database, keep it and point `DATABASE_URL` at it. Use Supabase only if you need a new managed Postgres instance.
For an exact step-by-step setup, including Supabase fallback and what to expect on Render free vs paid, use [RENDER_DEPLOYMENT.md](/home/madhu/smart%20Gate/RENDER_DEPLOYMENT.md).

---

## 🎮 Usage Guide

### Start Server

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

Or use restart script:
```bash
./RESTART_SERVER.sh
```

**Access:**
- Landing page: http://localhost:8080/
- API info: http://localhost:8080/api
- Docs: http://localhost:8080/docs

### Portals

| Portal | URL | Purpose |
|--------|-----|---------|
| **Student** | `/frontend/student/` | Request passes, view QR |
| **Admin** | `/frontend/admin/` | Approve passes, analytics |
| **Guard** | `/frontend/guard/` | Scan QR, verify faces |
| **Parent** | `/frontend/parent/` | View child activity |

### Default Credentials

#### Admin
```
Email: admin@uni.edu
Password: admin123
```

#### Students
| Name | Email | Password | ID |
|------|-------|----------|-----|
| Madhavi | u22cn361@cmrtc.ac.in | madhavi123 | U22CN361 |
| Dhanush | u22cn362@cmrtc.ac.in | dhanush123 | U22CN362 |
| Gowrishankar | u22cn414@cmrtc.ac.in | gowri123 | U22CN414 |
| Tharun | u22cn421@cmrtc.ac.in | tharun123 | U22CN421 |

#### Guards
```
Email: guard@uni.edu / scanner@uni.edu
Password: guard123 / scanner123
```

### Complete Workflow

#### Outing Pass Flow

1. **Student** → Login → Request Pass → Enter reason → Submit
2. **Admin** → View pending → Review → Approve
3. **System** → Generate QR (HMAC-signed)
4. **Student** → View QR code
5. **Guard** → Scan QR → System verifies → Grant access
6. **Parent** → Receives notification

#### Daily Entry Flow

1. **Student** → Login → Generate Daily QR
2. **Browser** → Request GPS location
3. **System** → Verify within radius → Generate QR
4. **Guard** → Scan at gate → Log entry

#### Face Registration

1. **Student** → Upload photo
2. **System** → Extract 128-D encoding → Save
3. **Guard** → Capture face at gate
4. **System** → Compare encodings → Verify

---

## 📡 API Documentation

### Authentication

#### POST /auth/login
```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=u22cn361@cmrtc.ac.in&password=madhavi123"
```

Response:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "name": "Madhavi",
  "role": "student"
}
```

### Pass Management

#### POST /passes (Create Pass)
```bash
curl -X POST http://localhost:8080/passes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Going home","pass_type":"exit"}'
```

#### GET /passes (List Passes)
```bash
curl http://localhost:8080/passes \
  -H "Authorization: Bearer <token>"
```

#### POST /passes/{id}/approve (Admin)
```bash
curl -X POST http://localhost:8080/passes/1/approve \
  -H "Authorization: Bearer <admin_token>"
```

### QR Verification

#### POST /verify
```bash
curl -X POST http://localhost:8080/verify \
  -H "Authorization: Bearer <guard_token>" \
  -F "token=1.5.1697789234.a3f2b8c9d4e5..."
```

### Face Recognition

#### POST /api/register_face
```bash
curl -X POST http://localhost:8080/api/register_face \
  -H "Authorization: Bearer <token>" \
  -F "file=@photo.jpg"
```

#### POST /api/verify_face
```bash
curl -X POST http://localhost:8080/api/verify_face \
  -H "Authorization: Bearer <guard_token>" \
  -F "file=@live_photo.jpg" \
  -F "student_id=2"
```

### Location Settings

#### GET /api/admin/location (Admin)
```bash
curl http://localhost:8080/api/admin/location \
  -H "Authorization: Bearer <admin_token>"
```

#### POST /api/admin/location (Admin)
```bash
curl -X POST http://localhost:8080/api/admin/location \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "campus_name":"Main Campus",
    "latitude":31.7768,
    "longitude":77.0144,
    "radius_km":2.5,
    "enabled":true
  }'
```

### Daily Entry

#### POST /passes/daily-entry
```bash
curl -X POST http://localhost:8080/passes/daily-entry \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude":31.7768,
    "longitude":77.0144,
    "pass_type":"entry"
  }'
```

### Parent Portal

#### GET /api/parent/access-token
```bash
curl http://localhost:8080/api/parent/access-token \
  -H "Authorization: Bearer <student_token>"
```

#### GET /api/parent/student_history/{student_id}?access_token=...
```bash
curl "http://localhost:8080/api/parent/student_history/U22CN361?access_token=<signed_parent_token>"
```

**Full API Docs:** http://localhost:8080/docs

---

## 🗄️ Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) UNIQUE,
    pwd_hash VARCHAR(255),
    role VARCHAR(20),  -- student/admin/guard
    
    -- Student fields
    student_id VARCHAR(50) UNIQUE,
    student_class VARCHAR(100),
    parent_name VARCHAR(120),
    parent_phone VARCHAR(20),
    
    -- Face auth
    face_encoding TEXT,  -- 128-D vector
    face_registered BOOLEAN,
    
    -- Notifications
    fcm_token TEXT,
    phone VARCHAR(20)
);
```

### Passes Table
```sql
CREATE TABLE passes (
    id INTEGER PRIMARY KEY,
    student_id INTEGER,
    reason TEXT,
    pass_type VARCHAR(10),  -- entry/exit
    status VARCHAR(16),  -- pending/approved/rejected/used
    request_time DATETIME,
    approved_by INTEGER,
    expiry_time DATETIME,
    qr_token TEXT,
    
    -- GPS
    request_latitude TEXT,
    request_longitude TEXT,
    location_verified BOOLEAN,
    
    FOREIGN KEY (student_id) REFERENCES users(id)
);
```

### Scan Logs Table
```sql
CREATE TABLE scan_logs (
    id INTEGER PRIMARY KEY,
    pass_id INTEGER,
    student_id INTEGER,
    scanner_id INTEGER,
    scan_time DATETIME,
    result VARCHAR(32),  -- success/expired/invalid
    details TEXT
);
```

**View Database:**
```bash
sqlite3 backend/gatepass.db
.tables
SELECT * FROM users;
```

---

## 🔐 Security Features

### 1. **QR Code Security**
- HMAC-SHA256 signatures
- Time-based expiry
- One-time use tokens
- Tamper detection

### 2. **Password Security**
- Bcrypt hashing (cost: 12)
- No plaintext storage
- Salted hashes

### 3. **Token Security**
- JWT with HS256
- Role-based claims
- Configurable expiry
- Secure secret keys

### 4. **Face Recognition Security**
- Store encodings only (no images)
- 128-D vectors (encrypted at rest)
- Threshold-based matching
- One registration per student

### 5. **GPS Security**
- Server-side verification
- Distance calculation
- Spoofing prevention
- Location logging

### 6. **API Security**
- Role-based access control
- Protected endpoints
- Request validation
- CORS configuration

---

## 🧪 Testing

### Manual Testing

#### Test Pass Flow
```bash
# 1. Student login
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -d "username=u22cn361@cmrtc.ac.in&password=madhavi123" | jq -r .access_token)

# 2. Create pass
PASS_ID=$(curl -s -X POST http://localhost:8080/passes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Test"}' | jq -r .id)

# 3. Admin approve (use admin token)
curl -X POST http://localhost:8080/passes/$PASS_ID/approve \
  -H "Authorization: Bearer <admin_token>"

# 4. Verify QR (use guard token)
curl -X POST http://localhost:8080/verify \
  -H "Authorization: Bearer <guard_token>" \
  -F "token=..."
```

### Test Scenarios

| Scenario | Expected Result |
|----------|----------------|
| Valid QR scan | ✅ Access granted |
| Expired QR | ❌ Denied (expired) |
| Used QR (replay) | ❌ Denied (already used) |
| Tampered QR | ❌ Denied (invalid signature) |
| Outside geofence | ❌ Daily entry denied |
| Face mismatch | ❌ Verification failed |

---

## 🛠️ Troubleshooting

### Common Issues

#### **Backend won't start**
```bash
# Check Python version
python3 --version  # Must be 3.11+

# Reinstall dependencies
pip install -r requirements.txt

# Check database
sqlite3 backend/gatepass.db ".tables"
```

#### **dlib installation fails**
```bash
# Install system dependencies first
sudo apt install build-essential cmake libboost-all-dev

# Try pre-built wheel
pip install --no-cache-dir dlib
```

#### **Camera not working (Guard portal)**
- Use HTTPS (browsers require it for camera)
- Grant camera permissions
- Try different browser (Chrome recommended)
- Use manual QR entry as fallback

#### **GPS not working (Daily entry)**
- Grant location permissions
- Use HTTPS
- Check browser console for errors
- Verify geofencing is enabled

#### **Notifications not received**
- Check browser notification permissions first
- Real web push is disabled by default in this repository
- SMS delivery requires valid Twilio credentials on the backend
- Parent activity history still works through the signed parent link

#### **"Forbidden" error on location page**
- You must login as **admin** (not student)
- Use: admin@uni.edu / admin123
- Or click "Fill Admin Credentials" button

#### **QR code has border (want to remove)**
- Already fixed in latest version
- If still present, check `frontend/student/style.css`
- Lines 446, 502 should have no `border` property

---

## 📂 Project Structure

```
smart Gate/
├── backend/
│   ├── app.py                    # Main FastAPI application
│   ├── auth.py                   # Authentication logic
│   ├── models.py                 # Database models
│   ├── database.py               # DB connection
│   ├── settings.py               # Configuration
│   ├── geofence.py              # GPS geofencing
│   ├── location_settings.py     # Location management
│   ├── notifications_v2.py      # Firebase Admin / SMS notification backend
│   ├── face_recognition_api.py  # Face recognition
│   ├── alembic/                 # Safe schema migration baseline
│   ├── bootstrap.py             # DB bootstrap + optional demo seed
│   ├── seed.py                  # Seed demo data
│   ├── add_students_with_parents.py
│   ├── requirements.txt         # Python dependencies
│   ├── gatepass.db             # SQLite database
│   └── location_settings.json  # Location config
│
├── frontend/
│   ├── student/
│   │   ├── index.html          # Student portal UI
│   │   ├── app.js              # Student logic
│   │   └── style.css           # Student styles
│   ├── admin/
│   │   ├── index.html          # Admin dashboard
│   │   ├── location.html       # Location settings
│   │   ├── logs.html           # Real-time logs
│   │   ├── app.js              # Admin logic
│   │   └── style.css           # Admin styles
│   ├── guard/
│   │   ├── index.html          # Guard scanner UI
│   │   ├── app.js              # Scanner logic
│   │   └── style.css           # Guard styles
│   └── parent/
│       ├── index.html          # Parent portal
│       ├── app.js              # Parent logic
│       └── style.css           # Parent styles
│
├── UBUNTU_SETUP.sh             # One-click setup script
├── RESTART_SERVER.sh           # Server restart script
├── requirements.txt            # Dependencies
├── README.md                   # This file
├── ALL_LOGIN_CREDENTIALS.md   # Login credentials
├── LOCATION_SETTINGS_GUIDE.md # Location setup guide
└── PROJECT_DOCUMENTATION.md   # Additional docs
```

---

## 📝 What We Built & Used

### **Core Components**

1. **Authentication System**
   - JWT token-based authentication
   - bcrypt password hashing
   - Role-based access control
   - Session management

2. **QR Code System**
   - HMAC-SHA256 signing
   - Time-based expiry
   - QRCode.js for generation
   - html5-qrcode for scanning
   - Replay attack prevention

3. **Face Recognition**
   - dlib face detection
   - 128-dimensional face encoding
   - face_recognition library
   - Threshold-based matching
   - OpenCV for image processing

4. **GPS Geofencing**
   - Shapely for geometric operations
   - geopy for distance calculations
   - Leaflet.js for interactive maps
   - Circular geofence implementation
   - Admin configurable locations

5. **Notification System**
   - Browser alerts
   - Optional Firebase Cloud Messaging (requires real web config)
   - Parent portal updates
   - Twilio SMS integration (optional)
   - Real-time event notifications

6. **Database System**
   - SQLite for development
   - PostgreSQL support for production
   - SQLAlchemy ORM
   - Relationship mapping
   - Indexed queries

7. **Multi-Portal UI**
   - Student portal (pass requests, QR display)
   - Admin portal (approvals, analytics)
   - Guard portal (QR scanning, face verification)
   - Parent portal (notifications, activity view)
   - Responsive design
   - Modern gradient styling

### **What We Did**

#### **Phase 1: Core System**
- ✅ Set up FastAPI backend
- ✅ Created database schema
- ✅ Implemented authentication
- ✅ Built QR generation/verification
- ✅ Created basic portals

#### **Phase 2: Advanced Features**
- ✅ Added face recognition
- ✅ Implemented GPS geofencing
- ✅ Created daily entry system
- ✅ Added notification system
- ✅ Built parent portal

#### **Phase 3: Admin Features**
- ✅ Real-time analytics dashboard
- ✅ Location configuration UI
- ✅ Interactive map with Leaflet
- ✅ Auto-detect location
- ✅ Comprehensive logging

#### **Phase 4: Polish & Fixes**
- ✅ Removed QR code borders
- ✅ Fixed authentication issues
- ✅ Added login form to location page
- ✅ Improved error messages
- ✅ Created setup scripts
- ✅ Replaced "IIT Mandi" with "Campus"
- ✅ Added complete documentation

### **Technologies Configured**

- **Python 3.11+**: Core backend language
- **FastAPI**: Web framework
- **dlib**: Face detection library
- **face_recognition**: Face encoding
- **Shapely**: Geospatial operations
- **geopy**: Distance calculations
- **Firebase Admin SDK**: Push notifications
- **SQLAlchemy**: Database ORM
- **Leaflet.js**: Interactive maps
- **OpenStreetMap**: Map tiles
- **QRCode.js**: QR generation
- **html5-qrcode**: QR scanning

---

## 🚀 Deployment

### Development
```bash
uvicorn app:app --reload --port 8080
```

### Production

#### Using Gunicorn
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8080
```

#### Using Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Using Systemd
```ini
[Unit]
Description=Smart Gate System
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/smart-gate/backend
ExecStart=/usr/bin/uvicorn app:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🎓 Use Cases

### For Students
- Request exit passes with reasons
- Generate daily entry QR codes
- View pass history
- Register face (one-time)
- Enable browser alerts on the current device
- Share a secure parent portal link

### For Admins
- Approve/reject pass requests
- View real-time statistics
- Access comprehensive logs
- Configure campus location
- Manage user accounts
- Export reports

### For Guards
- Scan QR codes instantly
- Verify student faces
- Log entries/exits
- View scan history
- Manual token verification
- Entry/Exit mode toggle

### For Parents
- View child's activity through a signed link
- Receive SMS alerts if the backend is configured
- Enable browser alerts on the current device
- Track movement history
- No separate login required

---

## 📞 Support & Resources

### Documentation Files
- `README.md` - This complete guide
- `ALL_LOGIN_CREDENTIALS.md` - All login details
- `LOCATION_SETTINGS_GUIDE.md` - Location setup
- `QUICK_LOGIN_REFERENCE.txt` - Quick credentials
- `PROJECT_DOCUMENTATION.md` - Technical docs

### API Documentation
- Interactive docs: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

### Setup Scripts
- `UBUNTU_SETUP.sh` - One-click installation
- `RESTART_SERVER.sh` - Server restart
- `check_installation.py` - Verify installation

### Database Scripts
- `bootstrap.py` - Create tables and seed demo users when needed
- `seed.py` - Force demo user seed/update
- `add_students_with_parents.py` - Add students

---

## 🎉 Summary

This Smart Gate System is a **working campus access prototype** featuring:

✅ **4 Different Portals** - Student, Admin, Guard, Parent  
✅ **3 Authentication Methods** - Password, QR Code, Face  
✅ **GPS Geofencing** - Location-based access  
✅ **Notifications & Parent Access** - Browser alerts, secure links, optional SMS/FCM  
✅ **Admin Configuration** - No code changes needed  
✅ **Comprehensive Logging** - Full audit trail  
✅ **Beautiful UI** - Modern, responsive design  
✅ **Security First** - HMAC, JWT, Bcrypt, HTTPS  
✅ **Easy Setup** - One-click installation script  
✅ **Complete Documentation** - This README + guides  

## 📜 License

This is an educational/prototype project. Customize as needed for your institution.

**For Production Use:**
- Change all default passwords
- Use PostgreSQL database
- Enable HTTPS
- Configure Firebase properly
- Set up proper backup systems
- Review security settings

---

## 👥 Contributors

This project was built and documented comprehensively to serve as a complete campus gate management solution.

---

**Version:** 2.2  
**Last Updated:** March 6, 2026  
**Status:** Prototype / needs production hardening

---

**Review the implementation details before any production deployment.**
