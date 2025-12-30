const API_BASE = CONFIG.API_BASE;
let token = localStorage.getItem('token');
let currentUser = null;
let selectedPassType = 'entry'; // Default to entry
let currentLocation = null; // GPS coordinates

// Page navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
}

// Login
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');

    try {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });

        if (!res.ok) throw new Error('Invalid credentials');

        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('token', token);

        if (data.role !== 'student') {
            errorDiv.textContent = 'This portal is for students only';
            return;
        }

        await loadUserInfo();
        showPage('dashboardPage');
        loadPasses();
    } catch (err) {
        errorDiv.textContent = err.message || 'Login failed';
    }
});

// Load user info
async function loadUserInfo() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        currentUser = await res.json();

        // Display user name and student ID if available
        let displayText = currentUser.name;
        if (currentUser.student_id) {
            displayText += ` (${currentUser.student_id})`;
        }
        document.getElementById('userName').textContent = displayText;

        // Show student details if available
        if (currentUser.student_id && document.getElementById('studentInfo')) {
            const validUntil = currentUser.valid_until ? new Date(currentUser.valid_until).toLocaleDateString() : 'N/A';
            document.getElementById('studentInfo').innerHTML = `
                <p><strong>Student ID:</strong> ${currentUser.student_id}</p>
                <p><strong>Class:</strong> ${currentUser.student_class || 'N/A'}</p>
                <p><strong>Valid Until:</strong> ${validUntil}</p>
            `;
            document.getElementById('studentInfo').style.display = 'block';
        }

        // Load face authentication status
        loadFaceStatus();

        // Initialize notification card
        initializeNotificationCard();
    } catch (err) {
        console.error('Failed to load user info', err);
    }
}

// === GPS GEOFENCING FUNCTIONS ===
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation not supported'));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                currentLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                resolve(currentLocation);
            },
            (error) => {
                console.error('GPS error:', error);
                reject(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

// === FACE AUTHENTICATION FUNCTIONS ===
let selectedFaceFile = null;

async function loadFaceStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/face_status`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const status = await res.json();

        const faceStatusDiv = document.getElementById('faceStatus');
        const faceRegForm = document.getElementById('faceRegForm');

        if (status.face_registered) {
            const regDate = new Date(status.face_registered_at).toLocaleDateString();
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,255,255,0.2); padding:15px; border-radius:12px;">
                    <p style="font-size:18px; font-weight:700; margin-bottom:8px;">✅ Face Registered</p>
                    <p style="opacity:0.9;">Registered on: ${regDate}</p>
                    <p style="opacity:0.9; font-size:13px; margin-top:8px;">Your face is verified at gate entry for enhanced security.</p>
                </div>
            `;
            faceRegForm.style.display = 'none';
        } else {
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,255,255,0.15); padding:15px; border-radius:12px;">
                    <p style="font-size:16px; font-weight:600;">⚠️ Face Not Registered</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">Register your face for faster gate verification</p>
                </div>
            `;
            faceRegForm.style.display = 'block';
        }

        document.getElementById('faceRegCard').style.display = 'block';

    } catch (err) {
        console.error('Failed to load face status', err);
    }
}

function handleFaceImage(input) {
    if (input.files && input.files[0]) {
        selectedFaceFile = input.files[0];
        const reader = new FileReader();

        reader.onload = function (e) {
            document.getElementById('previewImg').src = e.target.result;
            document.getElementById('imagePreview').style.display = 'block';
        };

        reader.readAsDataURL(input.files[0]);
    }
}

async function uploadFace() {
    if (!selectedFaceFile) {
        alert('Please select a photo first');
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFaceFile);

    try {
        const res = await fetch(`${API_BASE}/api/register_face`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || 'Failed to register face');
        }

        const result = await res.json();
        alert('✅ ' + result.message);

        // Reset form and reload status
        document.getElementById('faceImage').value = '';
        document.getElementById('imagePreview').style.display = 'none';
        selectedFaceFile = null;

        loadFaceStatus();

    } catch (err) {
        alert('❌ ' + err.message);
    }
}

// Logout
function logout() {
    localStorage.removeItem('token');
    token = null;
    currentUser = null;

    // Clear contact form fields to prevent data persistence
    document.getElementById('studentPhone').value = '';
    document.getElementById('parentName').value = '';
    document.getElementById('parentPhone').value = '';

    // Clear login form
    document.getElementById('email').value = '';
    document.getElementById('password').value = '';

    showPage('loginPage');
}

// Quick Daily Entry Pass - AUTO GENERATED (No Admin Approval)
// Select pass type (entry/exit)
let selectedRegularPassType = 'entry'; // For regular pass requests

function selectPassType(type) {
    selectedPassType = type;
    const entryBtn = document.getElementById('entryBtn');
    const exitBtn = document.getElementById('exitBtn');

    if (type === 'entry') {
        entryBtn.style.background = 'white';
        entryBtn.style.color = '#667eea';
        entryBtn.style.borderColor = 'white';
        exitBtn.style.background = 'transparent';
        exitBtn.style.color = 'white';
        exitBtn.style.borderColor = 'rgba(255,255,255,0.5)';
    } else {
        exitBtn.style.background = 'white';
        exitBtn.style.color = '#667eea';
        exitBtn.style.borderColor = 'white';
        entryBtn.style.background = 'transparent';
        entryBtn.style.color = 'white';
        entryBtn.style.borderColor = 'rgba(255,255,255,0.5)';
    }
}

// Regular Pass Type Selection (for admin-approved passes)
function selectRegularPassType(type) {
    selectedRegularPassType = type;

    const entryBtn = document.getElementById('regularEntryBtn');
    const exitBtn = document.getElementById('regularExitBtn');

    if (type === 'entry') {
        entryBtn.style.background = '#667eea';
        entryBtn.style.color = 'white';
        entryBtn.style.borderColor = '#667eea';
        exitBtn.style.background = 'white';
        exitBtn.style.color = '#666';
        exitBtn.style.borderColor = '#ddd';
    } else {
        exitBtn.style.background = '#667eea';
        exitBtn.style.color = 'white';
        exitBtn.style.borderColor = '#667eea';
        entryBtn.style.background = 'white';
        entryBtn.style.color = '#666';
        entryBtn.style.borderColor = '#ddd';
    }
}

async function requestDailyEntry() {
    try {
        const passLabel = selectedPassType === 'entry' ? 'Entry' : 'Exit';

        console.log('=== GENERATING DAILY PASS ===');
        console.log('Selected pass type:', selectedPassType);
        console.log('Pass label:', passLabel);

        // Get GPS location
        let location = null;
        try {
            location = await getCurrentLocation();
            console.log('GPS Location:', location);
        } catch (gpsErr) {
            console.warn('GPS unavailable:', gpsErr);
            if (!confirm(`⚠️ Unable to get GPS location. Continue without location verification?\n\nNote: Location verification may be required for security.`)) {
                return;
            }
        }

        const requestBody = {
            pass_type: selectedPassType,
            latitude: location ? location.latitude : null,
            longitude: location ? location.longitude : null
        };
        console.log('Request body:', JSON.stringify(requestBody));

        const res = await fetch(`${API_BASE}/passes/daily-entry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || `Failed to generate daily ${passLabel.toLowerCase()} pass`);
        }

        const pass = await res.json();

        console.log('Pass created:', pass);
        console.log('Pass type in response:', pass.pass_type);
        console.log('Pass reason:', pass.reason);

        // Show success message with QR immediately
        alert(`✅ Daily ${passLabel} Pass Generated!\n\n${pass.reason}\n\nYour QR code is ready to use.\nValid until: ` + new Date(pass.expiry_time).toLocaleTimeString());

        // Refresh to show QR
        loadPasses();
    } catch (err) {
        alert('❌ ' + err.message);
    }
}

// Request pass
document.getElementById('passForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const reason = document.getElementById('reason').value;
    const passLabel = selectedRegularPassType === 'entry' ? 'Entry' : 'Exit';

    console.log('=== SUBMITTING REGULAR PASS REQUEST ===');
    console.log('Pass type:', selectedRegularPassType);
    console.log('Reason:', reason);

    // Get GPS location (optional for regular passes)
    let location = null;
    try {
        location = await getCurrentLocation();
        console.log('GPS Location:', location);
    } catch (gpsErr) {
        console.warn('GPS unavailable:', gpsErr);
        // Continue without GPS for regular passes (location is optional)
    }

    try {
        const res = await fetch(`${API_BASE}/passes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                reason: reason,
                pass_type: selectedRegularPassType,
                latitude: location ? location.latitude : null,
                longitude: location ? location.longitude : null
            })
        });

        if (!res.ok) throw new Error('Failed to create pass request');

        alert(`✅ ${passLabel} Pass request submitted!\n\nPass Type: ${selectedRegularPassType}\nWaiting for admin approval.`);
        document.getElementById('reason').value = '';
        loadPasses();
    } catch (err) {
        alert('❌ ' + err.message);
    }
});

// Load passes
async function loadPasses() {
    try {
        const res = await fetch(`${API_BASE}/passes`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const passes = await res.json();

        // Find latest approved pass
        const approved = passes.filter(p => p.status === 'approved');
        if (approved.length > 0) {
            const latest = approved[0];
            showApprovedPass(latest);
        } else {
            document.getElementById('currentPassCard').style.display = 'none';
        }

        // Find pending pass
        const pending = passes.filter(p => p.status === 'pending');
        if (pending.length > 0) {
            const latest = pending[0];
            showPendingPass(latest);
        } else {
            document.getElementById('pendingPassCard').style.display = 'none';
        }

        // Show history
        showPassHistory(passes);
    } catch (err) {
        console.error('Failed to load passes', err);
    }
}

function showApprovedPass(pass) {
    document.getElementById('currentPassCard').style.display = 'flex';
    document.getElementById('passReason').textContent = pass.reason;
    document.getElementById('passExpiry').textContent = new Date(pass.expiry_time).toLocaleString();

    // generate QR code
    const qrDiv = document.getElementById('qrCode');
    qrDiv.innerHTML = '';
    new QRCode(qrDiv, {
        text: pass.qr_token,
        width: 220,
        height: 220,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.H
    });
}

function showPendingPass(pass) {
    document.getElementById('pendingPassCard').style.display = 'block';
    document.getElementById('pendingReason').textContent = pass.reason;
    document.getElementById('pendingTime').textContent = new Date(pass.request_time).toLocaleString();
}

function showPassHistory(passes) {
    const historyDiv = document.getElementById('passHistory');

    if (passes.length === 0) {
        historyDiv.innerHTML = '<div class="empty-state">No pass requests yet</div>';
        return;
    }

    historyDiv.innerHTML = passes.map(pass => `
        <div class="pass-item">
            <p><strong>Reason:</strong> ${pass.reason}</p>
            <p><strong>Requested:</strong> ${new Date(pass.request_time).toLocaleString()}</p>
            <p class="status-badge status-${pass.status}">Status: ${pass.status.toUpperCase()}</p>
            ${pass.used_time ? `<p><strong>Used:</strong> ${new Date(pass.used_time).toLocaleString()}</p>` : ''}
        </div>
    `).join('');
}

// Check if already logged in
if (token) {
    loadUserInfo().then(() => {
        showPage('dashboardPage');
        loadPasses();
    });
}

// Auto-refresh passes every 10 seconds
setInterval(() => {
    if (token && document.getElementById('dashboardPage').classList.contains('active')) {
        loadPasses();
    }
}, 10000);

// =====================
// Notification Functions
// =====================

let studentFCMToken = null;

// Enable notifications for student
async function enableStudentNotifications() {
    try {
        // Check browser support
        if (!('Notification' in window)) {
            alert('This browser does not support notifications');
            return;
        }

        if (!('serviceWorker' in navigator)) {
            alert('This browser does not support service workers');
            return;
        }

        // Request permission
        const permission = await Notification.requestPermission();

        if (permission !== 'granted') {
            alert('Please enable notifications in your browser settings to receive pass updates');
            return;
        }

        // Generate simulated FCM token (in production, use Firebase SDK)
        studentFCMToken = generateSimulatedFCMToken();

        // Register token with backend
        const response = await fetch(`${API_BASE}/api/register_fcm_token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ fcm_token: studentFCMToken })
        });

        if (response.ok) {
            updateNotificationStatus('enabled');

            // Show contact form
            document.getElementById('contactForm').style.display = 'block';
            document.getElementById('enableNotifBtn').style.display = 'none';

            // Show parent portal link
            generateParentPortalLink();

            // Send test notification
            setTimeout(() => {
                sendTestNotification('✅ Notifications enabled! You will receive updates about your gate passes.');
            }, 1000);

        } else {
            throw new Error('Failed to register for notifications');
        }

    } catch (error) {
        console.error('Notification setup error:', error);
        alert('Failed to enable notifications: ' + error.message);
    }
}

// Save contact information
async function saveContactInfo() {
    const studentPhone = document.getElementById('studentPhone').value.trim();
    const parentName = document.getElementById('parentName').value.trim();
    const parentPhone = document.getElementById('parentPhone').value.trim();

    if (!parentName || !parentPhone) {
        alert('Please enter parent name and phone number');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/update_contact`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                phone: studentPhone,
                parent_name: parentName,
                parent_phone: parentPhone
            })
        });

        if (response.ok) {
            alert('✅ Contact information saved! Your parents will now receive notifications when you enter/exit campus.');

            // Update parent portal link with student info
            generateParentPortalLink();

        } else {
            throw new Error('Failed to save contact information');
        }

    } catch (error) {
        console.error('Save contact error:', error);
        alert('Failed to save contact information: ' + error.message);
    }
}

// Generate parent portal link
function generateParentPortalLink() {
    if (currentUser) {
        const baseUrl = window.location.origin;
        // Make sure to include index.html in the URL
        const parentUrl = `${baseUrl}/frontend/parent/index.html?student_id=${encodeURIComponent(currentUser.student_id || '')}&student_name=${encodeURIComponent(currentUser.name || '')}`;

        document.getElementById('parentLinkInput').value = parentUrl;
        document.getElementById('parentPortalLink').style.display = 'block';

        console.log('Generated parent portal link:', parentUrl);
    }
}

// Copy parent portal link
function copyParentLink() {
    const linkInput = document.getElementById('parentLinkInput');
    linkInput.select();
    linkInput.setSelectionRange(0, 99999); // For mobile devices

    try {
        document.execCommand('copy');
        alert('✅ Link copied! Share this with your parent to setup their notifications.');
    } catch (err) {
        alert('Failed to copy link. Please copy it manually.');
    }
}

// Update notification status display
function updateNotificationStatus(status) {
    const statusDiv = document.getElementById('notificationStatus');

    if (status === 'enabled') {
        statusDiv.innerHTML = `
            <div style="padding:15px; background:rgba(255,255,255,0.2); border-radius:12px; backdrop-filter:blur(10px);">
                <p style="margin:0; font-weight:600;">✅ Notifications Enabled</p>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">You will receive alerts when your passes are approved/rejected</p>
            </div>
        `;
    } else if (status === 'disabled') {
        statusDiv.innerHTML = `
            <div style="padding:15px; background:rgba(255,255,255,0.2); border-radius:12px; backdrop-filter:blur(10px);">
                <p style="margin:0; font-weight:600;">🔕 Notifications Disabled</p>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">Enable notifications to get instant updates</p>
            </div>
        `;
    }
}

// Generate simulated FCM token
function generateSimulatedFCMToken() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    let token = '';
    for (let i = 0; i < 152; i++) {
        token += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return token;
}

// Send test notification
function sendTestNotification(message) {
    if (Notification.permission === 'granted') {
        const notification = new Notification('🎓 Campus GatePass', {
            body: message,
            icon: '/icon-192x192.png',
            badge: '/badge-72x72.png',
            tag: 'test-notification'
        });

        notification.onclick = function () {
            window.focus();
            notification.close();
        };

        // Auto-close after 5 seconds
        setTimeout(() => {
            notification.close();
        }, 5000);
    }
}

// Initialize notification card
function initializeNotificationCard() {
    if (currentUser) {
        document.getElementById('notificationCard').style.display = 'block';

        // Clear all fields first to prevent old data from showing
        document.getElementById('studentPhone').value = '';
        document.getElementById('parentName').value = '';
        document.getElementById('parentPhone').value = '';

        // Pre-fill contact form with CURRENT user's data ONLY if they exist
        if (currentUser.phone) {
            document.getElementById('studentPhone').value = currentUser.phone;
        }
        if (currentUser.parent_name) {
            document.getElementById('parentName').value = currentUser.parent_name;
        }
        if (currentUser.parent_phone) {
            document.getElementById('parentPhone').value = currentUser.parent_phone;
        }

        console.log('Contact form initialized for:', currentUser.name);
        console.log('Phone:', currentUser.phone || 'Not set');
        console.log('Parent Name:', currentUser.parent_name || 'Not set');
        console.log('Parent Phone:', currentUser.parent_phone || 'Not set');

        // Check if notifications are already enabled
        if (Notification.permission === 'granted') {
            updateNotificationStatus('enabled');
            document.getElementById('contactForm').style.display = 'block';
            document.getElementById('enableNotifBtn').style.display = 'none';
            generateParentPortalLink();
        } else {
            updateNotificationStatus('disabled');
        }
    }
}

// ============================================================================
// EMERGENCY EXIT FEATURE
// ============================================================================

async function requestEmergencyExit() {
    // Confirmation dialog with reason input
    const confirmed = confirm(
        "🚨 EMERGENCY EXIT REQUEST\n\n" +
        "Are you sure you need to leave campus immediately?\n\n" +
        "This will:\n" +
        "• Grant you instant exit permission\n" +
        "• Notify all administrators\n" +
        "• Create an emergency log entry\n\n" +
        "Click OK to proceed with emergency exit."
    );

    if (!confirmed) {
        return;
    }

    // Ask for reason
    const reason = prompt(
        "Please briefly describe the emergency:\n" +
        "(e.g., Medical emergency, Family emergency, Urgent situation)",
        "Emergency situation"
    );

    if (!reason || reason.trim() === '') {
        alert("❌ Emergency exit cancelled - reason required");
        return;
    }

    try {
        // Show loading
        const originalBtn = event.target;
        originalBtn.disabled = true;
        originalBtn.textContent = '⏳ Processing Emergency Exit...';

        const response = await fetch(`${API_BASE}/api/emergency_exit`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                reason: reason.trim()
            })
        });

        if (!response.ok) {
            throw new Error('Emergency exit request failed');
        }

        const data = await response.json();

        // Show success message
        alert(
            "✅ EMERGENCY EXIT GRANTED\n\n" +
            `Time: ${new Date().toLocaleTimeString()}\n` +
            `Student: ${data.student_name}\n` +
            `ID: ${data.student_id}\n\n` +
            "You may now leave campus immediately.\n" +
            "Admins have been notified.\n\n" +
            "Stay safe!"
        );

        // Show success notification
        if (Notification.permission === 'granted') {
            new Notification('🚨 Emergency Exit Granted', {
                body: 'You may now leave campus. Stay safe!',
                icon: '/icon-192x192.png',
                badge: '/badge-72x72.png',
                tag: 'emergency-exit'
            });
        }

        // Reset button
        originalBtn.disabled = false;
        originalBtn.textContent = '🚨 Request Emergency Exit';

        // Optionally reload passes to show the emergency exit log
        setTimeout(() => {
            loadPasses();
        }, 1000);

    } catch (error) {
        console.error('Emergency exit error:', error);
        alert(
            "❌ Emergency Exit Failed\n\n" +
            "Unable to process emergency exit request.\n" +
            "Please contact security immediately or proceed to the gate.\n\n" +
            "Error: " + error.message
        );

        // Reset button
        if (event && event.target) {
            event.target.disabled = false;
            event.target.textContent = '🚨 Request Emergency Exit';
        }
    }
}

