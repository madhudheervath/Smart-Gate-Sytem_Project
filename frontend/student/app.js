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

function formatStudentDateTime(value, options = {}) {
    if (window.DateTimeHelper) return DateTimeHelper.formatLocal(value, options);
    if (!value) return 'N/A';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleString();
}

function formatStudentTime(value, options = {}) {
    if (window.DateTimeHelper) return DateTimeHelper.formatTime(value, options);
    if (!value) return 'N/A';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleTimeString();
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
        loadSlotSection();
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
                <span class="meta-chip"><strong>ID</strong> ${escapeHtml(currentUser.student_id)}</span>
                <span class="meta-chip"><strong>Class</strong> ${escapeHtml(currentUser.student_class || 'N/A')}</span>
                <span class="meta-chip"><strong>Valid until</strong> ${escapeHtml(validUntil)}</span>
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
let selectedFacePreviewDataUrl = null;
let enrolledFacePreviewUrl = null;

function getFacePreviewStorageKey() {
    const identity = currentUser?.student_id || currentUser?.email || 'current';
    return `securegate.facePreview.${identity}`;
}

function revokeSelectedFacePreview() {
    if (selectedFacePreviewUrl) {
        URL.revokeObjectURL(selectedFacePreviewUrl);
        selectedFacePreviewUrl = null;
    }
}

function revokeEnrolledFacePreview() {
    if (enrolledFacePreviewUrl) {
        URL.revokeObjectURL(enrolledFacePreviewUrl);
        enrolledFacePreviewUrl = null;
    }
}

function saveEnrolledFacePreview(dataUrl) {
    if (!dataUrl) return;
    try {
        localStorage.setItem(getFacePreviewStorageKey(), dataUrl);
    } catch (err) {
        console.warn('Could not save local face preview', err);
    }
}

function getEnrolledFacePreview() {
    try {
        return localStorage.getItem(getFacePreviewStorageKey());
    } catch (err) {
        return null;
    }
}

function clearEnrolledFacePreview() {
    try {
        localStorage.removeItem(getFacePreviewStorageKey());
    } catch (err) {
        console.warn('Could not clear local face preview', err);
    }
}

function showFaceEnrollmentForm() {
    const faceRegForm = document.getElementById('faceRegForm');
    const faceImage = document.getElementById('faceImage');
    const registerButton = document.getElementById('registerFaceBtn');
    if (faceRegForm) faceRegForm.style.display = 'block';
    if (faceImage) faceImage.value = '';
    if (registerButton) registerButton.textContent = 'Update biometrics';
    selectedFaceFile = null;
    selectedFacePreviewDataUrl = null;
    revokeSelectedFacePreview();
    const imagePreview = document.getElementById('imagePreview');
    if (imagePreview) imagePreview.style.display = 'none';
}

async function renderEnrolledFacePreview(status) {
    const previewWrap = document.getElementById('enrolledFacePreview');
    if (!previewWrap) return;

    if (!status?.face_registered || status.requires_refresh) {
        revokeEnrolledFacePreview();
        previewWrap.style.display = 'none';
        previewWrap.innerHTML = '';
        if (!status?.face_registered) clearEnrolledFacePreview();
        return;
    }

    revokeEnrolledFacePreview();
    let storedPreview = null;
    if (status.face_preview_available) {
        try {
            storedPreview = await FaceAPI.getPreviewUrl();
            enrolledFacePreviewUrl = storedPreview;
        } catch (err) {
            console.warn('Could not load server face preview', err);
        }
    }
    if (!storedPreview) {
        storedPreview = getEnrolledFacePreview();
    }

    const regDate = status.face_registered_at ? formatStudentDateTime(status.face_registered_at) : 'Recently';
    const backend = status.registration_backend || status.backend || 'default';
    const thumb = storedPreview
        ? `<img src="${storedPreview}" alt="Enrolled biometric photo sample">`
        : `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0.35rem;color:var(--text-3);">
             <svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.45"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
             <span style="font-size:0.72rem;text-align:center;line-height:1.4;">Preview not<br>available</span>
           </div>`;

    const previewNote = storedPreview
        ? 'Gate verification uses the stored biometric template.'
        : 'Biometric data is enrolled and active. Re-upload your photo to enable the preview.';

    previewWrap.innerHTML = `
        <div class="enrolled-face-card">
            <div class="enrolled-face-thumb">${thumb}</div>
            <div class="enrolled-face-meta">
                <h4>Enrolled photo sample</h4>
                <p>${escapeHtml(regDate)} · ${escapeHtml(backend)}</p>
                <p style="margin-top:0.35rem;">${previewNote}</p>
                <div class="enrolled-face-actions">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="showFaceEnrollmentForm()">${storedPreview ? 'Replace photo' : 'Upload preview photo'}</button>
                </div>
            </div>
        </div>
    `;
    previewWrap.style.display = 'block';
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

        const thumbMax = 360;
        const thumbScale = Math.min(1, thumbMax / Math.max(image.naturalWidth, image.naturalHeight));
        const thumbWidth = Math.max(1, Math.round(image.naturalWidth * thumbScale));
        const thumbHeight = Math.max(1, Math.round(image.naturalHeight * thumbScale));
        const thumbCanvas = document.createElement('canvas');
        thumbCanvas.width = thumbWidth;
        thumbCanvas.height = thumbHeight;
        const thumbContext = thumbCanvas.getContext('2d');
        if (thumbContext) {
            thumbContext.drawImage(image, 0, 0, thumbWidth, thumbHeight);
        }

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
            previewUrl: URL.createObjectURL(blob),
            previewDataUrl: thumbContext ? thumbCanvas.toDataURL('image/jpeg', 0.78) : null
        };
    } finally {
        URL.revokeObjectURL(sourceUrl);
    }
}

async function loadFaceStatus() {
    const faceStatusDiv = document.getElementById('faceStatus');
    const faceRegForm = document.getElementById('faceRegForm');

    const statusBox = (color, icon, title, detail) => `
        <div style="display:flex;align-items:flex-start;gap:0.6rem;padding:0.6rem 0.8rem;
            background:rgba(${color},0.08);border:1px solid rgba(${color},0.3);
            border-radius:6px;font-size:0.82rem;">
            <span style="flex-shrink:0;">${icon}</span>
            <div>
                <div style="font-weight:600;color:rgba(${color},1);line-height:1.3;">${title}</div>
                ${detail ? `<div style="color:#8b9cb3;font-size:0.74rem;margin-top:0.2rem;">${detail}</div>` : ''}
            </div>
        </div>`;

    try {
        const status = await FaceAPI.getStatus();

        if (status.service_available === false) {
            const reason = status.backend_error || 'Service not ready on this deployment.';
            faceStatusDiv.innerHTML = statusBox('255,59,48', '⚠', 'Service Unavailable', `${status.backend || 'unknown'} · ${reason}`);
            await renderEnrolledFacePreview({ face_registered: false });
            faceRegForm.style.display = 'none';
            document.getElementById('faceRegCard').style.display = 'block';
            return;
        }

        if (status.requires_refresh) {
            faceStatusDiv.innerHTML = statusBox('255,204,0', '⚠', 'Re-Registration Required',
                `Backend switched to ${status.backend || 'new model'}. Upload a fresh photo.`);
            await renderEnrolledFacePreview(status);
            faceRegForm.style.display = 'block';
        } else if (status.face_registered) {
            const regDate = status.face_registered_at
                ? formatStudentDateTime(status.face_registered_at, { hour: undefined, minute: undefined })
                : 'Recently';
            faceStatusDiv.innerHTML = statusBox('52,199,89', '✓', 'Face Enrolled',
                `Registered ${regDate} · ${status.registration_backend || status.backend || 'default'}`);
            await renderEnrolledFacePreview(status);
            faceRegForm.style.display = 'none';
        } else {
            faceStatusDiv.innerHTML = statusBox('255,204,0', '⚠', 'Not Enrolled',
                `Backend: ${status.backend || 'default'} · Upload a photo to enable biometric access.`);
            await renderEnrolledFacePreview(status);
            faceRegForm.style.display = 'block';
        }

        document.getElementById('faceRegCard').style.display = 'block';

    } catch (err) {
        if (faceStatusDiv) faceStatusDiv.innerHTML = statusBox('255,59,48', '⚠', 'Status Unavailable', 'Could not reach face service.');
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
        selectedFacePreviewDataUrl = optimized.previewDataUrl;
        document.getElementById('previewImg').src = selectedFacePreviewUrl;
        document.getElementById('imagePreview').style.display = 'block';
    } catch (err) {
        selectedFaceFile = null;
        selectedFacePreviewDataUrl = null;
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
        saveEnrolledFacePreview(selectedFacePreviewDataUrl);
        alert('✅ ' + result.message);

        // Reset form and reload status
        document.getElementById('faceImage').value = '';
        document.getElementById('imagePreview').style.display = 'none';
        selectedFaceFile = null;
        selectedFacePreviewDataUrl = null;
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

        // Get GPS location
        let location = null;
        try {
            location = await getCurrentLocation();
        } catch (gpsErr) {
            console.warn('GPS unavailable:', gpsErr);
            alert('GPS location is required for daily entry/exit passes. Please allow location access and try again.');
            return;
        }

        const pass = await PassAPI.dailyEntry(selectedPassType, location);

        // Show success message with QR immediately
        alert(`✅ Daily ${passLabel} Pass Generated!\n\n${pass.reason}\n\nYour QR code is ready to use.\nValid until: ` + formatStudentTime(pass.expiry_time));

        // Refresh to show QR
        loadPasses();
    } catch (err) {
        alert('❌ ' + err.message);
    }
}

// Request pass
document.getElementById('passForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const reason = document.getElementById('reason').value.trim();
    const passLabel = selectedRegularPassType === 'entry' ? 'Entry' : 'Exit';

    if (reason.length < 3) {
        alert('Please enter a reason of at least 3 characters.');
        return;
    }

    // Get GPS location (optional for regular passes)
    let location = null;
    try {
        location = await getCurrentLocation();
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

document.getElementById('entryBtn')?.addEventListener('click', () => {
    selectPassType('entry');
    requestDailyEntry();
});

document.getElementById('exitBtn')?.addEventListener('click', () => {
    selectPassType('exit');
    requestDailyEntry();
});

document.getElementById('regularEntryBtn')?.addEventListener('click', () => {
    selectRegularPassType('entry');
    document.getElementById('passForm')?.requestSubmit();
});

document.getElementById('regularExitBtn')?.addEventListener('click', () => {
    selectRegularPassType('exit');
    document.getElementById('passForm')?.requestSubmit();
});

document.getElementById('faceImage')?.addEventListener('change', (e) => {
    handleFaceImage(e.target);
});

document.getElementById('faceRegForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    uploadFace();
});

document.getElementById('contactForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    saveContactInfo();
});

document.getElementById('enableNotifBtn')?.addEventListener('click', () => {
    enableStudentNotifications();
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

        // Show/hide no-pass placeholder
        const noPassCard = document.getElementById('noPassCard');
        if (noPassCard) {
            noPassCard.style.display = (approved.length === 0 && pending.length === 0) ? 'block' : 'none';
        }

        // Show history
        showPassHistory(passes);
    } catch (err) {
        console.error('Failed to load passes', err);
    }
}

function showApprovedPass(pass) {
    document.getElementById('currentPassCard').style.display = 'block';
    document.getElementById('passReason').textContent = pass.reason;
    document.getElementById('passExpiry').textContent = formatStudentDateTime(pass.expiry_time);

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
    document.getElementById('pendingTime').textContent = formatStudentDateTime(pass.request_time);
}

function showPassHistory(passes) {
    const historyDiv = document.getElementById('passHistory');

    if (passes.length === 0) {
        historyDiv.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--color-text-muted);padding:2rem;">No pass requests yet</td></tr>';
        return;
    }

    const statusClass = { approved: 'badge-success', pending: 'badge-warning', rejected: 'badge-danger', used: '' };
    const statusStyle = { used: 'background:rgba(0,212,255,0.1);color:var(--color-cyan);border:1px solid var(--color-cyan);', '': '' };

    historyDiv.innerHTML = passes.map(pass => {
        const cls = statusClass[pass.status] || '';
        const extraStyle = statusStyle[pass.status] || '';
        return `<tr>
            <td style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:var(--color-text-muted);white-space:nowrap;">${formatStudentDateTime(pass.request_time)}</td>
            <td><span style="font-size:0.72rem;text-transform:uppercase;font-weight:700;letter-spacing:0.5px;color:${pass.pass_type === 'exit' ? 'var(--color-yellow)' : 'var(--color-cyan)'};">${(pass.pass_type || 'entry').toUpperCase()}</span></td>
            <td>${pass.reason || '—'}</td>
            <td><span class="badge ${cls}" style="font-size:0.68rem;${extraStyle}">${pass.status.toUpperCase()}</span></td>
            <td style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--color-text-muted);white-space:nowrap;">${pass.used_time ? formatStudentDateTime(pass.used_time) : '—'}</td>
        </tr>`;
    }).join('');
}

// Check if already logged in
if (token) {
    loadUserInfo().then((loaded) => {
        if (!loaded) return;
        showPage('dashboardPage');
        loadPasses();
        loadSlotSection();
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
        const enableBtn = document.getElementById('enableNotifBtn');
        if (enableBtn) enableBtn.style.display = 'none';

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
        currentUser.phone = studentPhone;
        currentUser.parent_name = parentName;
        currentUser.parent_phone = parentPhone;

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
        const parentName = document.getElementById('parentName')?.value || currentUser.parent_name || 'Guardian';
        const parentPhone = document.getElementById('parentPhone')?.value || currentUser.parent_phone || '';
        const parentUrl = `${baseUrl}/frontend/parent/index.html?student_id=${encodeURIComponent(currentUser.student_id || '')}&student_name=${encodeURIComponent(currentUser.name || '')}&parent_name=${encodeURIComponent(parentName)}&parent_phone=${encodeURIComponent(parentPhone)}&access_token=${encodeURIComponent(access.access_token || '')}`;

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
    if (!statusDiv) return;

    const row = (color, icon, title, detail) => `
        <div style="display:flex;align-items:flex-start;gap:0.6rem;padding:0.6rem 0.8rem;
            background:rgba(${color},0.08);border:1px solid rgba(${color},0.3);border-radius:6px;">
            <span style="flex-shrink:0;">${icon}</span>
            <div>
                <div style="font-size:0.82rem;font-weight:600;color:rgba(${color},1);line-height:1.3;">${title}</div>
                ${detail ? `<div style="font-size:0.74rem;color:#8b9cb3;margin-top:0.2rem;">${detail}</div>` : ''}
            </div>
        </div>`;

    if (status === 'enabled') {
        statusDiv.innerHTML = row('52,199,89', '✓', 'Notifications Enabled', 'Gate pass alerts will be delivered to this device.');
    } else if (status === 'browser_only') {
        statusDiv.innerHTML = row('52,199,89', '✓', 'Browser Alerts Active', 'Alerts work on this device only. Real web push is not configured.');
    } else if (status === 'disabled') {
        statusDiv.innerHTML = row('255,204,0', '🔕', 'Notifications Disabled', 'Enable browser alerts on this device. Parent links work without this.');
    } else if (status === 'unsupported') {
        statusDiv.innerHTML = row('139,156,179', 'ℹ', 'Alerts Unavailable', 'This device does not support browser notifications.');
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
            const enableBtn = document.getElementById('enableNotifBtn');
            if (enableBtn) enableBtn.style.display = 'none';
            return;
        }

        // Check if notifications are already enabled
        if (hasBrowserNotifications() && Notification.permission === 'granted') {
            updateNotificationStatus(hasConfiguredWebPush() ? 'enabled' : 'browser_only');
            const enableBtn = document.getElementById('enableNotifBtn');
            if (enableBtn) enableBtn.style.display = 'none';
        } else {
            updateNotificationStatus('disabled');
            const enableBtn = document.getElementById('enableNotifBtn');
            if (enableBtn) enableBtn.style.display = 'block';
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

// ============================================================================
// SLOT BOOKING  (UC04)
// ============================================================================

function escapeHtml(v) {
    return String(v ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function loadSlotSection() {
    const card = document.getElementById('slotBookingCard');
    if (!card) return;
    card.style.display = 'block';
    await Promise.all([loadAvailableSlots(), loadMyBookings()]);
}

async function loadAvailableSlots() {
    const container = document.getElementById('availableSlotsContainer');
    if (!container) return;
    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${CONFIG.API_BASE}/api/slots?active_only=true`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed to load slots');
        const slots = (await res.json()).filter((slot) => {
            if (!slot.active) return false;
            const end = window.DateTimeHelper
                ? DateTimeHelper.parseBackendDate(slot.end_time)
                : new Date(slot.end_time);
            return end && !Number.isNaN(end.getTime()) && end > new Date();
        });

        if (!slots.length) {
            container.innerHTML = '<p class="slot-empty">No bookable slots available right now.</p>';
            return;
        }

        const zoneLabel = window.DateTimeHelper ? DateTimeHelper.zoneLabel() : 'Local time';
        container.innerHTML = `
            <div class="slot-local-time-note">Showing windows in ${escapeHtml(zoneLabel)}</div>
            ${slots.map(s => {
            const windowStr = window.DateTimeHelper
                ? DateTimeHelper.formatSlotWindow(s.start_time, s.end_time)
                : `${formatStudentDateTime(s.start_time)} to ${formatStudentDateTime(s.end_time)}`;
            const isFull = s.remaining <= 0;
            const encodedLabel = encodeURIComponent(s.label || 'selected slot');
            return `
                <div class="slot-card">
                    <div>
                        <div class="slot-card-title">${escapeHtml(s.label)}</div>
                        <div class="slot-meta">
                            <span>Gate: ${escapeHtml(s.gate)}</span>
                            <span>${escapeHtml(windowStr)}</span>
                        </div>
                        <div class="slot-badges">
                            ${s.gps_required ? '<span class="slot-badge gps">GPS required</span>' : ''}
                            ${s.face_check_required ? '<span class="slot-badge">Face check</span>' : ''}
                        </div>
                    </div>
                    <div class="slot-card-side">
                        <div class="slot-capacity ${isFull ? 'full' : ''}">${isFull ? 'Full' : `${s.remaining} left`}</div>
                        <div class="slot-booked">${s.booked_count}/${s.capacity} booked</div>
                        <button
                            onclick="bookSlot(${s.id}, decodeURIComponent('${encodedLabel}'), ${s.gps_required ? 'true' : 'false'})"
                            class="btn btn-primary btn-sm"
                            ${isFull ? 'disabled' : ''}>
                            ${isFull ? 'Full' : 'Book slot'}
                        </button>
                    </div>
                </div>`;
        }).join('')}`;
    } catch (err) {
        container.innerHTML = `<p class="slot-error">Error: ${escapeHtml(err.message)}</p>`;
    }
}

async function loadMyBookings() {
    const container = document.getElementById('myBookingsContainer');
    if (!container) return;
    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${CONFIG.API_BASE}/api/slots/my/bookings`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed to load bookings');
        const bookings = await res.json();

        if (!bookings.length) {
            container.innerHTML = '<p class="slot-empty">You have no active slot bookings.</p>';
            return;
        }

        container.innerHTML = bookings.map(b => {
            const title = b.slot_label || b.slot?.label || `Booking #${b.id}`;
            return `
            <div class="booking-card">
                <div>
                    <div class="booking-title">${escapeHtml(title)}</div>
                    <div class="booking-meta">Booked ${escapeHtml(formatStudentDateTime(b.booked_at))}</div>
                    <span class="booking-status">${escapeHtml(b.booking_status)}</span>
                </div>
                <button onclick="cancelBooking(${b.id})" class="btn btn-danger btn-sm">
                    Cancel
                </button>
            </div>`;
        }).join('');
    } catch (err) {
        container.innerHTML = `<p class="slot-error">Error: ${escapeHtml(err.message)}</p>`;
    }
}

async function bookSlot(slotId, slotLabel = 'selected slot', gpsRequired = false) {
    const passLabel = selectedRegularPassType === 'entry' ? 'entry' : 'exit';
    if (!confirm(`Reserve this access slot and submit a ${passLabel} pass request?`)) return;

    // GPS is enforced at gate verification time, not at booking time.
    // Try to capture coordinates for the pass request, but never block booking on GPS failure.
    let location = null;
    if (gpsRequired) {
        try {
            location = await getCurrentLocation();
        } catch (gpsErr) {
            console.warn('GPS unavailable at booking time — will be enforced at gate:', gpsErr.message);
        }
    }

    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${CONFIG.API_BASE}/api/slots/${slotId}/book`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Booking failed');

        try {
            await PassAPI.request(
                selectedRegularPassType,
                `Slot access request: ${slotLabel}`,
                location,
                { slot_id: slotId }
            );
            alert('✅ Slot booked and pass request submitted for admin approval.');
            await loadPasses();
        } catch (passErr) {
            alert('⚠️ Slot booked, but pass request was not created: ' + passErr.message);
        }
        await loadSlotSection();
    } catch (err) {
        alert('❌ ' + err.message);
    }
}

async function cancelBooking(bookingId) {
    if (!confirm('Cancel this booking?')) return;
    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${CONFIG.API_BASE}/api/slots/bookings/${bookingId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed to cancel');
        await loadSlotSection();
    } catch (err) {
        alert('❌ ' + err.message);
    }
}
