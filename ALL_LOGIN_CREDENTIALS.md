# 🔐 Complete Login Credentials & Database Info

## 📊 Database Schema

### **User Table Fields:**
```
- id (Primary Key)
- name
- email (Unique)
- pwd_hash (Encrypted password)
- role (student | admin | guard)
- active (Boolean)

Student-specific fields:
- student_id (e.g., U22CN361)
- student_class (e.g., CSE-B)
- guardian_name
- valid_until
- face_encoding (for face auth)
- face_registered
- fcm_token (for notifications)
- phone
- parent_name
- parent_phone
- parent_fcm_token
```

---

## 🎓 STUDENT CREDENTIALS

### **Student 1 - Madhavi**
```
Email:       u22cn361@cmrtc.ac.in
Password:    madhavi123
Student ID:  U22CN361
Class:       CSE-B
Phone:       +919876543211
Parent:      Rajesh Kumar
Parent Phone: +919876543210
```

### **Student 2 - Dhanush**
```
Email:       u22cn362@cmrtc.ac.in
Password:    dhanush123
Student ID:  U22CN362
Class:       CSE-B
Phone:       +919876543213
Parent:      Suresh Reddy
Parent Phone: +919876543212
```

### **Student 3 - Gowrishankar**
```
Email:       u22cn414@cmrtc.ac.in
Password:    gowri123
Student ID:  U22CN414
Class:       CSE-A
Phone:       +919876543215
Parent:      Venkata Rao
Parent Phone: +919876543214
```

### **Student 4 - Tharun**
```
Email:       u22cn421@cmrtc.ac.in
Password:    tharun123
Student ID:  U22CN421
Class:       CSE-A
Phone:       +919876543217
Parent:      Ramesh Naidu
Parent Phone: +919876543216
```

### **Student 5 - Student One (Test)**
```
Email:       student1@uni.edu
Password:    s123456
Student ID:  (Not set)
Class:       (Not set)
```

### **Student 6 - Student Two (Test)**
```
Email:       student2@uni.edu
Password:    s123456
Student ID:  (Not set)
Class:       (Not set)
```

---

## 👨‍💼 ADMIN CREDENTIALS

### **Admin - Admin Warden**
```
Email:       admin@uni.edu
Password:    admin123
Role:        admin
```

---

## 🚪 GUARD CREDENTIALS

### **Guard - Gate Scanner**
```
Email:       scanner@uni.edu
Password:    scanner123
Role:        guard
```

### **Guard 2**
```
Email:       guard@uni.edu
Password:    guard123
Role:        guard
```

---

## 🌐 Portal Access URLs

### **Student Portal:**
```
URL: http://localhost:8080/frontend/student/index.html

Test with any student credentials above
```

### **Admin Portal:**
```
URL: http://localhost:8080/frontend/admin/index.html

Login: admin@uni.edu / admin123
```

### **Parent Portal:**
```
URL: http://localhost:8080/frontend/parent/index.html

Use Student ID to setup notifications
Example: U22CN361 for Madhavi
```

### **Guard Portal:**
```
URL: http://localhost:8080/frontend/guard/index.html

Login: guard@uni.edu / guard123
OR scanner@uni.edu / scanner123
```

---

## 🔗 Parent Portal Direct Links

### **For Madhavi's Parent:**
```
http://localhost:8080/frontend/parent/index.html?student_id=U22CN361&student_name=Madhavi
```

### **For Dhanush's Parent:**
```
http://localhost:8080/frontend/parent/index.html?student_id=U22CN362&student_name=Dhanush
```

### **For Gowrishankar's Parent:**
```
http://localhost:8080/frontend/parent/index.html?student_id=U22CN414&student_name=Gowrishankar
```

### **For Tharun's Parent:**
```
http://localhost:8080/frontend/parent/index.html?student_id=U22CN421&student_name=Tharun
```

---

## 📊 Database File Location

```
Database: /home/madhu/smart Gate/backend/gatepass.db
Type: SQLite
```

---

## 🔧 Database Management

### **View Database Contents:**
```bash
cd "/home/madhu/smart Gate/backend"
sqlite3 gatepass.db

# View all users
SELECT id, name, email, role, student_id FROM users;

# View all passes
SELECT * FROM passes;

# View scan logs
SELECT * FROM scan_logs;
```

### **Add New Student:**
```bash
cd "/home/madhu/smart Gate/backend"
python3 add_students_with_parents.py
```

### **Reset Database:**
```bash
cd "/home/madhu/smart Gate/backend"
rm gatepass.db
python3 init_db.py
```

---

## 🧪 Quick Test Scenarios

### **Test 1: Student Login**
```
1. Go to: http://localhost:8080/frontend/student/index.html
2. Login: u22cn361@cmrtc.ac.in / madhavi123
3. Request a pass
4. Generate daily QR code
```

### **Test 2: Admin Approval**
```
1. Go to: http://localhost:8080/frontend/admin/index.html
2. Login: admin@uni.edu / admin123
3. View pending passes
4. Approve/reject passes
```

### **Test 3: Guard Scan**
```
1. Go to: http://localhost:8080/frontend/guard/index.html
2. Login: guard@uni.edu / guard123
3. Scan student's QR code
4. Verify entry/exit
```

### **Test 4: Parent Notifications**
```
1. Student generates pass
2. Admin approves
3. Student gets notification
4. Student scans at gate
5. Parent gets notification
```

---

## 📝 Student Database Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) UNIQUE,
    pwd_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT 1,
    
    -- Student fields
    student_id VARCHAR(50) UNIQUE,
    student_class VARCHAR(100),
    guardian_name VARCHAR(120),
    valid_until DATETIME,
    
    -- Face auth
    face_encoding TEXT,
    face_registered BOOLEAN DEFAULT 0,
    face_registered_at DATETIME,
    
    -- Notifications
    fcm_token TEXT,
    phone VARCHAR(20),
    parent_name VARCHAR(120),
    parent_phone VARCHAR(20),
    parent_fcm_token TEXT,
    notification_preferences TEXT DEFAULT '{}',
    last_notification_at DATETIME
);
```

---

## 🎯 Summary Table

| Role | Email | Password | Name |
|------|-------|----------|------|
| **Admin** | admin@uni.edu | admin123 | Admin Warden |
| **Guard** | guard@uni.edu | guard123 | Guard |
| **Guard** | scanner@uni.edu | scanner123 | Gate Scanner |
| **Student** | u22cn361@cmrtc.ac.in | madhavi123 | Madhavi |
| **Student** | u22cn362@cmrtc.ac.in | dhanush123 | Dhanush |
| **Student** | u22cn414@cmrtc.ac.in | gowri123 | Gowrishankar |
| **Student** | u22cn421@cmrtc.ac.in | tharun123 | Tharun |
| **Student** | student1@uni.edu | s123456 | Student One |
| **Student** | student2@uni.edu | s123456 | Student Two |

---

## 🔒 Security Notes

- **Production Deployment**: Change all default passwords!
- **Password Format**: All passwords are hashed using bcrypt
- **Token Storage**: JWT tokens stored in localStorage
- **Session Expiry**: Tokens expire after set duration

---

## 📞 Parent Information

| Student | Parent Name | Parent Phone |
|---------|------------|--------------|
| Madhavi (U22CN361) | Rajesh Kumar | +919876543210 |
| Dhanush (U22CN362) | Suresh Reddy | +919876543212 |
| Gowrishankar (U22CN414) | Venkata Rao | +919876543214 |
| Tharun (U22CN421) | Ramesh Naidu | +919876543216 |

---

**All credentials are for testing purposes only. Change them in production!** 🔐
