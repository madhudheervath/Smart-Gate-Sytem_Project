const API_BASE = CONFIG.API_BASE;
let token = localStorage.getItem('token');
let currentUser = null;
let selectedPassType = 'entry'; // Default to entry
let currentLocation = null; // GPS coordinates

function showLoginInfo(message) {
    const infoDiv = document.getElementById('loginInfo');
    if (!infoDiv) return;
    infoDiv.textContent = message || '';
    infoDiv.style.display = message ? 'block' : 'none';
}

function clearAuthMessages() {
    const loginError = document.getElementById('loginError');
    const registerError = document.getElementById('registerError');
    if (loginError) loginError.textContent = '';
    if (registerError) registerError.textContent = '';
    showLoginInfo('');
}

// Page navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
}

// Toggle Auth Form (Login / Register)
function toggleAuthForm(formType) {
    const title = document.getElementById('authFormTitle');
    clearAuthMessages();
    if (formType === 'register') {
        if (!CONFIG.FEATURES.ACCOUNT_REQUESTS) {
            alert('New access requests are disabled. Contact an administrator.');
            return;
        }
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'block';
        if (title) title.textContent = 'Request Access';
    } else {
        document.getElementById('registerForm').style.display = 'none';
        document.getElementById('loginForm').style.display = 'block';
        if (title) title.textContent = 'Login';
    }
}

function updateAuthAvailability() {
    const registerPrompt = document.getElementById('registerPrompt');
    if (registerPrompt && !CONFIG.FEATURES.ACCOUNT_REQUESTS) {
        registerPrompt.textContent = 'Accounts are provisioned by administrators. Use your assigned credentials.';
    }
}

function clearStudentSession(showLoginPage = true) {
    localStorage.removeItem('token');
    token = null;
    currentUser = null;
    if (showLoginPage) {
        showPage('loginPage');
    }
}

// Login
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    showLoginInfo('');
    errorDiv.textContent = '';

    try {
        const data = await AuthAPI.login(email, password);

        if (data.role !== 'student') {
            clearStudentSession(false);
            errorDiv.textContent = data.role === 'guard'
                ? 'This account is approved for the Guard Portal. Please use the guard login page.'
                : 'This portal is for authorized personnel only';
            return;
        }

        token = data.access_token;
        localStorage.setItem('token', token);

        const loaded = await loadUserInfo();
        if (!loaded) {
            throw new Error('Failed to load user profile');
        }
        showPage('dashboardPage');
        loadPasses();
    } catch (err) {
        errorDiv.textContent = err.message || 'Login failed';
    }
});

// Registration
document.getElementById('registerForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!CONFIG.FEATURES.ACCOUNT_REQUESTS) {
        document.getElementById('registerError').textContent = 'New access requests are disabled. Contact an administrator.';
        return;
    }
    const name = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;
    const requested_role = document.getElementById('regAccessType').value;
    const student_id = document.getElementById('regStudentId').value.trim();
    const student_class = document.getElementById('regClass').value.trim();
    const phone = document.getElementById('regPhone').value.trim();
    const request_reason = document.getElementById('regReason').value.trim();
    const errorDiv = document.getElementById('registerError');
    errorDiv.textContent = '';

    try {
        const userData = {
            name,
            email,
            password,
            requested_role,
            student_id,
            student_class,
            phone,
            request_reason
        };
        // Clean empty fields
        Object.keys(userData).forEach(k => !userData[k] && delete userData[k]);

        const result = await AuthAPI.register(userData);
        e.target.reset();
        toggleAuthForm('login');
        document.getElementById('email').value = email;
        document.getElementById('password').value = '';
        showLoginInfo(
            requested_role === 'guard'
                ? `${result.message} After approval, sign in through the Guard Portal.`
                : result.message
        );
    } catch (err) {
        errorDiv.textContent = err.message || 'Registration failed';
    }
});

// Load user info
async function loadUserInfo() {
    try {
        currentUser = await AuthAPI.getMe();
        if (currentUser.role !== 'student') {
            throw new Error('Authorized personnel access required');
        }

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
                <p><strong>Personnel ID:</strong> ${currentUser.student_id}</p>
                <p><strong>Class:</strong> ${currentUser.student_class || 'N/A'}</p>
                <p><strong>Valid Until:</strong> ${validUntil}</p>
            `;
            document.getElementById('studentInfo').style.display = 'block';
        }

        // Load face authentication status
        loadFaceStatus();

        // Initialize notification card
        initializeNotificationCard();
        return true;
    } catch (err) {
        console.error('Failed to load user info', err);
        clearStudentSession();
        return false;
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
let selectedFacePreviewUrl = null;

function revokeSelectedFacePreview() {
    if (selectedFacePreviewUrl) {
        URL.revokeObjectURL(selectedFacePreviewUrl);
        selectedFacePreviewUrl = null;
    }
}

async function optimizeFaceImage(file) {
    if (!file) {
        throw new Error('Please choose an image file');
    }

    const supportedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (file.type && !supportedTypes.includes(file.type)) {
        throw new Error('Please choose a JPEG, PNG, or WEBP image');
    }

    const sourceUrl = URL.createObjectURL(file);
    try {
        const image = await new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Unable to read the selected image'));
            img.src = sourceUrl;
        });

        const maxDimension = 960;
        const scale = Math.min(1, maxDimension / Math.max(image.naturalWidth, image.naturalHeight));
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const context = canvas.getContext('2d');
        if (!context) {
            throw new Error('Image processing is not supported in this browser');
        }

        context.drawImage(image, 0, 0, width, height);

        const blob = await new Promise((resolve, reject) => {
            canvas.toBlob(
                (result) => result ? resolve(result) : reject(new Error('Failed to prepare the image')),
                'image/jpeg',
                0.82
            );
        });

        const optimizedFile = new File([blob], `face-${Date.now()}.jpg`, { type: 'image/jpeg' });
        return {
            file: optimizedFile,
            previewUrl: URL.createObjectURL(blob)
        };
    } finally {
        URL.revokeObjectURL(sourceUrl);
    }
}

async function loadFaceStatus() {
    try {
        const status = await FaceAPI.getStatus();

        const faceStatusDiv = document.getElementById('faceStatus');
        const faceRegForm = document.getElementById('faceRegForm');

        if (status.service_available === false) {
            const reason = status.backend_error || 'Face service is not ready on this deployment.';
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,255,255,0.15); padding:15px; border-radius:12px;">
                    <p style="font-size:16px; font-weight:700;">⚠️ Face Service Unavailable</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">Backend: ${status.backend || 'unknown'}</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">${reason}</p>
                </div>
            `;
            faceRegForm.style.display = 'none';
            document.getElementById('faceRegCard').style.display = 'block';
            return;
        }

        if (status.requires_refresh) {
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,193,7,0.18); padding:15px; border-radius:12px;">
                    <p style="font-size:18px; font-weight:700; margin-bottom:8px;">⚠️ Face Re-Registration Required</p>
                    <p style="opacity:0.95;">Your earlier face registration used an older verification model.</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">Current backend: ${status.backend || 'default'}</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">Previous registration: ${status.registration_backend || 'legacy'}</p>
                    <p style="opacity:0.9; font-size:13px; margin-top:8px;">Please upload a fresh face photo so gate verification uses the stricter model.</p>
                </div>
            `;
            faceRegForm.style.display = 'block';
        } else if (status.face_registered) {
            const regDate = new Date(status.face_registered_at).toLocaleDateString();
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,255,255,0.2); padding:15px; border-radius:12px;">
                    <p style="font-size:18px; font-weight:700; margin-bottom:8px;">✅ Face Registered</p>
                    <p style="opacity:0.9;">Registered on: ${regDate}</p>
                    <p style="opacity:0.9;">Backend: ${status.registration_backend || status.backend || 'default'}</p>
                    <p style="opacity:0.9; font-size:13px; margin-top:8px;">Your face is verified at gate entry for enhanced security.</p>
                </div>
            `;
            faceRegForm.style.display = 'none';
        } else {
            faceStatusDiv.innerHTML = `
                <div style="background:rgba(255,255,255,0.15); padding:15px; border-radius:12px;">
                    <p style="font-size:16px; font-weight:600;">⚠️ Face Not Registered</p>
                    <p style="opacity:0.9; font-size:14px; margin-top:5px;">Backend: ${status.backend || 'default'}</p>
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

async function handleFaceImage(input) {
    if (!(input.files && input.files[0])) {
        return;
    }

    try {
        const optimized = await optimizeFaceImage(input.files[0]);
        revokeSelectedFacePreview();
        selectedFaceFile = optimized.file;
        selectedFacePreviewUrl = optimized.previewUrl;
        document.getElementById('previewImg').src = selectedFacePreviewUrl;
        document.getElementById('imagePreview').style.display = 'block';
    } catch (err) {
        selectedFaceFile = null;
        revokeSelectedFacePreview();
        input.value = '';
        alert('❌ ' + (err.message || 'Failed to prepare the selected image'));
    }
}

async function uploadFace() {
    if (!selectedFaceFile) {
        alert('Please select a photo first');
        return;
    }

    const registerButton = document.getElementById('registerFaceBtn');
    const originalLabel = registerButton ? registerButton.textContent : '';

    try {
        if (registerButton) {
            registerButton.disabled = true;
            registerButton.textContent = '⏳ Registering Face...';
        }
        const result = await FaceAPI.register(selectedFaceFile);
        alert('✅ ' + result.message);

        // Reset form and reload status
        document.getElementById('faceImage').value = '';
        document.getElementById('imagePreview').style.display = 'none';
        selectedFaceFile = null;
        revokeSelectedFacePreview();

        loadFaceStatus();

    } catch (err) {
        alert('❌ ' + err.message);
    } finally {
        if (registerButton) {
            registerButton.disabled = false;
            registerButton.textContent = originalLabel || '✅ Register Face';
        }
    }
}

// Logout
function logout() {
    clearStudentSession(false);

    // Clear contact form fields to prevent data persistence
    document.getElementById('studentPhone').value = '';
    document.getElementById('parentName').value = '';
    document.getElementById('parentPhone').value = '';

    // Clear login form
    document.getElementById('email').value = '';
    document.getElementById('password').value = '';

    showPage('loginPage');
}

// Quick Daily Entry Pass - AUTO GENERATED (No Access Control Administrator Approval)
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

// Regular Pass Type Selection (for Access Control Administrator-approved passes)
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

        const pass = await PassAPI.dailyEntry(selectedPassType, location);

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
        await PassAPI.request(selectedRegularPassType, reason, location);

        alert(`✅ ${passLabel} Pass request submitted!\n\nPass Type: ${selectedRegularPassType}\nWaiting for Access Control Administrator approval.`);
        document.getElementById('reason').value = '';
        loadPasses();
    } catch (err) {
        alert('❌ ' + err.message);
    }
});

// Load passes
async function loadPasses() {
    try {
        const passes = await PassAPI.list();

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
    loadUserInfo().then((loaded) => {
        if (!loaded) return;
        showPage('dashboardPage');
        loadPasses();
    });
}

// Auto-refresh passes every 10 seconds
setInterval(() => {
    if (
        token &&
        document.visibilityState === 'visible' &&
        document.getElementById('dashboardPage').classList.contains('active')
    ) {
        loadPasses();
    }
}, 10000);

// =====================
// Notification Functions
// =====================

function hasBrowserNotifications() {
    return typeof Notification !== 'undefined';
}

function hasConfiguredWebPush() {
    return Boolean(CONFIG.FEATURES.REAL_PUSH_NOTIFICATIONS);
}

// Enable notifications for student
async function enableStudentNotifications() {
    try {
        // Check browser support
        if (!hasBrowserNotifications()) {
            alert('This browser does not support notifications');
            return;
        }

        if (hasConfiguredWebPush() && !('serviceWorker' in navigator)) {
            alert('This browser does not support service workers');
            return;
        }

        // Request permission
        const permission = await Notification.requestPermission();

        if (permission !== 'granted') {
            alert('Please enable notifications in your browser settings to receive pass updates');
            return;
        }

        updateNotificationStatus(hasConfiguredWebPush() ? 'enabled' : 'browser_only');
        document.getElementById('enableNotifBtn').style.display = 'none';

        await generateParentPortalLink();

        if (!hasConfiguredWebPush()) {
            alert('Browser alerts are enabled on this device. Secure parent links and SMS backup still work, but Firebase web push is not configured in this build.');
        }

        // Send test notification
        setTimeout(() => {
            const message = hasConfiguredWebPush()
                ? '✅ Notifications enabled! You will receive updates about your gate passes.'
                : '✅ Browser alerts enabled on this device. Server push is not configured in this build.';
            sendTestNotification(message);
        }, 1000);

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
        await NotificationAPI.saveContact(studentPhone, parentName, parentPhone);

        alert('✅ Contact information saved. Share the secure parent link below to let your parent view activity history. SMS backup can be used if the backend is configured for it.');

        // Update parent portal link with student info
        generateParentPortalLink();

    } catch (error) {
        console.error('Save contact error:', error);
        alert('Failed to save contact information: ' + error.message);
    }
}

// Generate parent portal link
async function generateParentPortalLink() {
    if (!currentUser || !currentUser.student_id) {
        return;
    }

    try {
        const access = await ParentAPI.getAccessToken();
        const baseUrl = window.location.origin;
        const parentUrl = `${baseUrl}/frontend/parent/index.html?student_id=${encodeURIComponent(currentUser.student_id || '')}&student_name=${encodeURIComponent(currentUser.name || '')}&access_token=${encodeURIComponent(access.access_token || '')}`;

        document.getElementById('parentLinkInput').value = parentUrl;
        document.getElementById('parentPortalLink').style.display = 'block';

        console.log('Generated parent portal link:', parentUrl);
    } catch (error) {
        console.error('Failed to generate parent portal link:', error);
    }
}

// Copy parent portal link
function copyParentLink() {
    const linkInput = document.getElementById('parentLinkInput');
    linkInput.select();
    linkInput.setSelectionRange(0, 99999); // For mobile devices

    try {
        document.execCommand('copy');
        alert('✅ Link copied. Share this with your parent to open the secure activity portal.');
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
    } else if (status === 'browser_only') {
        statusDiv.innerHTML = `
            <div style="padding:15px; background:rgba(255,255,255,0.2); border-radius:12px; backdrop-filter:blur(10px);">
                <p style="margin:0; font-weight:600;">✅ Browser Alerts Enabled</p>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">Alerts work on this device only. Real web push is not configured in this build.</p>
            </div>
        `;
    } else if (status === 'disabled') {
        statusDiv.innerHTML = `
            <div style="padding:15px; background:rgba(255,255,255,0.2); border-radius:12px; backdrop-filter:blur(10px);">
                <p style="margin:0; font-weight:600;">🔕 Notifications Disabled</p>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">Enable browser alerts on this device. Secure parent links work without this step.</p>
            </div>
        `;
    } else if (status === 'unsupported') {
        statusDiv.innerHTML = `
            <div style="padding:15px; background:rgba(255,255,255,0.2); border-radius:12px; backdrop-filter:blur(10px);">
                <p style="margin:0; font-weight:600;">ℹ️ Browser Alerts Unavailable</p>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">This device does not support browser notifications. Contact details and the parent portal still work.</p>
            </div>
        `;
    }
}

// Send test notification
function sendTestNotification(message) {
    if (hasBrowserNotifications() && Notification.permission === 'granted') {
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

        document.getElementById('contactForm').style.display = 'block';
        generateParentPortalLink();

        if (!hasBrowserNotifications()) {
            updateNotificationStatus('unsupported');
            document.getElementById('enableNotifBtn').style.display = 'none';
            return;
        }

        // Check if notifications are already enabled
        if (hasBrowserNotifications() && Notification.permission === 'granted') {
            updateNotificationStatus(hasConfiguredWebPush() ? 'enabled' : 'browser_only');
            document.getElementById('enableNotifBtn').style.display = 'none';
        } else {
            updateNotificationStatus('disabled');
        }
    }
}

// ============================================================================
// EMERGENCY EXIT FEATURE
// ============================================================================

async function requestEmergencyExit(buttonEl) {
    // Confirmation dialog with reason input
    const confirmed = confirm(
        "🚨 EMERGENCY EXIT REQUEST\n\n" +
        "Are you sure you need to leave campus immediately?\n\n" +
        "This will:\n" +
        "• Grant you instant exit permission\n" +
        "• Notify all Access Control Administrators\n" +
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
        const originalBtn = buttonEl;
        originalBtn.disabled = true;
        originalBtn.textContent = '⏳ Processing Emergency Exit...';

        const data = await PassAPI.emergencyExit(reason.trim());

        // Show success message
        alert(
            "✅ EMERGENCY EXIT GRANTED\n\n" +
            `Time: ${new Date().toLocaleTimeString()}\n` +
            `Personnel: ${data.student_name}\n` +
            `ID: ${data.student_id}\n\n` +
            "You may now leave campus immediately.\n" +
            "Access Control Administrators have been notified.\n\n" +
            "Stay safe!"
        );

        // Show success notification
        if (hasBrowserNotifications() && Notification.permission === 'granted') {
            new Notification('🚨 Emergency Exit Granted', {
                body: 'You may now leave campus. Stay safe!',
                icon: '/icon-192x192.png',
                badge: '/badge-72x72.png',
                tag: 'emergency-exit'
            });
        }

        // Reset button
        originalBtn.disabled = false;
        originalBtn.textContent = '🚨 Request Emergency Exit Now';

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
        if (buttonEl) {
            buttonEl.disabled = false;
            buttonEl.textContent = '🚨 Request Emergency Exit Now';
        }
    }
}

updateAuthAvailability();
