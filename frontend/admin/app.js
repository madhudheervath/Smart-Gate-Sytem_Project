let token = localStorage.getItem('adminToken');
let currentUser = null;
let currentPassFilter = 'pending';
let currentRegistrationFilter = 'pending';
let allPasses = [];
let registrationRequests = [];
let pendingRegistrationRequests = [];
const apiClient = CONFIG.createApiClient();
const REGISTRATION_ALERT_STORAGE_KEY = 'adminLastSeenRegistrationRequestId';
let registrationRequestsInitialized = false;
let lastSeenRegistrationRequestId = Number(localStorage.getItem(REGISTRATION_ALERT_STORAGE_KEY) || '0');
let notificationHideTimer = null;

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

async function apiFetch(path, options = {}) {
    return apiClient.fetch(path, options);
}

// Page navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
}

function clearAdminSession(showLoginPage = true) {
    localStorage.removeItem('adminToken');
    token = null;
    currentUser = null;
    registrationRequests = [];
    pendingRegistrationRequests = [];
    registrationRequestsInitialized = false;
    if (showLoginPage) {
        showPage('loginPage');
    }
}

// Login
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    const submitButton = e.target.querySelector('button[type="submit"]');
    errorDiv.textContent = '';

    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Signing In...';
    }

    try {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await apiFetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });

        if (!res.ok) {
            let errorMessage = 'Login failed';
            try {
                const errorData = await res.json();
                errorMessage = errorData.detail || errorData.message || 'Invalid credentials';
            } catch (e) {
                errorMessage = `Server Error (${res.status})`;
            }
            throw new Error(errorMessage);
        }

        const data = await res.json();

        if (data.role !== 'admin') {
            clearAdminSession(false);
            errorDiv.textContent = 'This portal is for Access Control Administrators only';
            return;
        }

        token = data.access_token;
        localStorage.setItem('adminToken', token);

        const loaded = await loadUserInfo();
        if (!loaded) {
            throw new Error('Failed to load admin profile');
        }
        showPage('dashboardPage');
        updateNotificationPreferenceUI();
        await Promise.all([loadPasses(), loadRegistrationRequests({ notify: false })]);
    } catch (err) {
        errorDiv.textContent = err.message || 'Login failed';
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = 'Login';
        }
    }
});

// Load user info
async function loadUserInfo() {
    try {
        const res = await apiFetch('/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            throw new Error('Failed to authenticate admin session');
        }
        currentUser = await res.json();
        if (currentUser.role !== 'admin') {
            throw new Error('Admin access required');
        }
        document.getElementById('userName').textContent = currentUser.name;
        return true;
    } catch (err) {
        console.error('Failed to load user info', err);
        clearAdminSession();
        return false;
    }
}

// Logout
function logout() {
    clearAdminSession();
}

// Load passes
async function loadPasses() {
    try {
        const res = await apiFetch('/passes', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            throw new Error('Failed to load passes');
        }
        allPasses = await res.json();

        updateStats();
        displayPasses();
    } catch (err) {
        console.error('Failed to load passes', err);
    }
}

async function fetchRegistrationRequests(status = 'pending') {
    const res = await apiFetch(`/admin/registration-requests?status=${encodeURIComponent(status)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) {
        throw new Error('Failed to load account requests');
    }
    return res.json();
}

function updateRegistrationFilterButtons() {
    document.querySelectorAll('.request-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-request-status') === currentRegistrationFilter);
    });
}

function updateNotificationPreferenceUI() {
    const statusEl = document.getElementById('requestAlertStatus');
    const buttonEl = document.getElementById('enableAdminAlertsBtn');

    if (!statusEl || !buttonEl) return;

    if (!('Notification' in window)) {
        statusEl.textContent = 'Browser alerts are not supported in this browser.';
        buttonEl.disabled = true;
        return;
    }

    if (Notification.permission === 'granted') {
        statusEl.textContent = 'Browser alerts are enabled for new account requests.';
        buttonEl.disabled = true;
        buttonEl.textContent = '🔔 Browser Alerts Enabled';
        return;
    }

    if (Notification.permission === 'denied') {
        statusEl.textContent = 'Browser alerts are blocked in this browser. In-app alerts will still appear here.';
        buttonEl.disabled = true;
        buttonEl.textContent = '🔕 Browser Alerts Blocked';
        return;
    }

    statusEl.textContent = 'Enable browser alerts to get a desktop notification when a new access request arrives.';
    buttonEl.disabled = false;
    buttonEl.textContent = '🔔 Enable Browser Alerts';
}

function showRequestNotification(message, tone = 'info') {
    const banner = document.getElementById('requestNotificationBanner');
    const content = document.getElementById('requestNotificationMessage');
    if (!banner || !content) return;

    const tones = {
        info: {
            background: '#eef6ff',
            border: '#4f7cff',
            color: '#1f4f8f',
        },
        success: {
            background: '#edf9f1',
            border: '#2e8b57',
            color: '#1f6b44',
        },
        warning: {
            background: '#fff7e6',
            border: '#f0ad4e',
            color: '#8a5a00',
        },
    };
    const activeTone = tones[tone] || tones.info;

    banner.style.display = 'block';
    banner.style.background = activeTone.background;
    banner.style.borderLeft = `5px solid ${activeTone.border}`;
    content.style.color = activeTone.color;
    content.textContent = message;

    window.clearTimeout(notificationHideTimer);
    notificationHideTimer = window.setTimeout(() => {
        banner.style.display = 'none';
    }, 8000);
}

function maybeNotifyAboutNewRegistrationRequests(pendingRequests, { notify = false } = {}) {
    const latestPendingId = pendingRequests.reduce((maxId, request) => Math.max(maxId, request.id || 0), 0);

    if (!registrationRequestsInitialized) {
        lastSeenRegistrationRequestId = Math.max(lastSeenRegistrationRequestId, latestPendingId);
        localStorage.setItem(REGISTRATION_ALERT_STORAGE_KEY, String(lastSeenRegistrationRequestId));
        registrationRequestsInitialized = true;
        return;
    }

    const newRequests = pendingRequests.filter(request => request.id > lastSeenRegistrationRequestId);
    if (!newRequests.length) {
        lastSeenRegistrationRequestId = Math.max(lastSeenRegistrationRequestId, latestPendingId);
        localStorage.setItem(REGISTRATION_ALERT_STORAGE_KEY, String(lastSeenRegistrationRequestId));
        return;
    }

    lastSeenRegistrationRequestId = Math.max(lastSeenRegistrationRequestId, latestPendingId);
    localStorage.setItem(REGISTRATION_ALERT_STORAGE_KEY, String(lastSeenRegistrationRequestId));

    const names = newRequests.slice(0, 2).map(request => request.name).join(', ');
    const extraText = newRequests.length > 2 ? ` and ${newRequests.length - 2} more` : '';
    const message = `New account request${newRequests.length > 1 ? 's' : ''} from ${names}${extraText}.`;
    showRequestNotification(message, 'info');

    if (notify && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('New Account Request', {
            body: message,
            tag: 'registration-request',
        });
    }
}

async function enableAdminBrowserAlerts() {
    if (!('Notification' in window)) {
        showRequestNotification('Browser alerts are not supported in this browser. In-app alerts will still appear here.', 'warning');
        return;
    }

    const permission = await Notification.requestPermission();
    updateNotificationPreferenceUI();

    if (permission === 'granted') {
        showRequestNotification('Browser alerts enabled. You will be notified when new account requests arrive.', 'success');
        return;
    }

    showRequestNotification('Browser alert permission was not granted. In-app alerts will still appear here.', 'warning');
}

async function loadRegistrationRequests({ status = currentRegistrationFilter, notify = false } = {}) {
    try {
        currentRegistrationFilter = status;
        updateRegistrationFilterButtons();

        const filteredPromise = fetchRegistrationRequests(currentRegistrationFilter);
        const pendingPromise = currentRegistrationFilter === 'pending'
            ? filteredPromise
            : fetchRegistrationRequests('pending');

        const [filteredRequests, pendingRequests] = await Promise.all([filteredPromise, pendingPromise]);
        registrationRequests = filteredRequests;
        pendingRegistrationRequests = pendingRequests;
        updateStats();
        displayRegistrationRequests();
        maybeNotifyAboutNewRegistrationRequests(pendingRegistrationRequests, { notify });
    } catch (err) {
        console.error('Failed to load registration requests', err);
        const container = document.getElementById('registrationRequestsContainer');
        if (container) {
            container.innerHTML = '<div class="empty-state">Failed to load account requests</div>';
        }
    }
}

// Update statistics
function updateStats() {
    const registrationPending = Array.isArray(pendingRegistrationRequests) ? pendingRegistrationRequests.length : 0;
    document.getElementById('registrationPendingCount').textContent = registrationPending;

    if (!allPasses || allPasses.length === 0) {
        document.getElementById('pendingCount').textContent = '0';
        document.getElementById('approvedCount').textContent = '0';
        document.getElementById('totalApprovedCount').textContent = '0';
        document.getElementById('usedCount').textContent = '0';
        console.log('No passes data available');
        return;
    }

    // Get current date in IST (India Standard Time)
    const now = new Date();
    const istOffset = 5.5 * 60; // IST is UTC+5:30
    const istTime = new Date(now.getTime() + (istOffset * 60 * 1000) + (now.getTimezoneOffset() * 60 * 1000));
    const today = istTime.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });

    console.log('Current IST date:', today);
    console.log('Total passes:', allPasses.length);

    const pending = allPasses.filter(p => p.status === 'pending').length;

    // Total approved (all time)
    const totalApproved = allPasses.filter(p => p.status === 'approved' || p.status === 'used').length;

    // Approved today only (in IST)
    const approvedToday = allPasses.filter(p => {
        if (p.status !== 'approved' && p.status !== 'used') return false;
        if (!p.approved_time) {
            console.log('Pass', p.id, 'has no approved_time');
            return false;
        }
        // Convert approved time to IST date string
        const approvedDate = new Date(p.approved_time);
        const approvedIST = approvedDate.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
        const isToday = approvedIST === today;
        if (isToday) {
            console.log('Pass', p.id, 'approved today (IST):', p.approved_time, '→', approvedIST);
        }
        return isToday;
    }).length;

    const used = allPasses.filter(p => p.status === 'used').length;

    // Update counts
    document.getElementById('pendingCount').textContent = pending;
    document.getElementById('approvedCount').textContent = approvedToday;
    document.getElementById('totalApprovedCount').textContent = totalApproved;
    document.getElementById('usedCount').textContent = used;

    console.log('Stats updated (IST):', {
        registrationPending: registrationPending,
        pending: pending,
        approvedToday: approvedToday,
        totalApproved: totalApproved,
        used: used,
        today: today
    });
}

// Filter passes
function filterPasses(status) {
    currentPassFilter = status;

    // Update active button
    document.querySelectorAll('.pass-filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-status') === status) {
            btn.classList.add('active');
        }
    });

    displayPasses();
}

// Display passes
function displayPasses() {
    const container = document.getElementById('passesContainer');
    const filtered = currentPassFilter ? allPasses.filter(p => p.status === currentPassFilter) : allPasses;

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">No passes found</div>';
        return;
    }

    container.innerHTML = filtered.map(pass => createPassCard(pass)).join('');
}

function formatRequestedRole(role) {
    return role === 'guard' ? 'Security Guard' : 'Authorized Personnel';
}

function refreshRegistrationRequests() {
    return loadRegistrationRequests({ status: currentRegistrationFilter, notify: false });
}

function filterRegistrationRequests(status) {
    return loadRegistrationRequests({ status, notify: false });
}

function displayRegistrationRequests() {
    const container = document.getElementById('registrationRequestsContainer');
    if (!container) return;

    if (!registrationRequests.length) {
        const emptyMessage = {
            pending: 'No pending account requests',
            approved: 'No approved account requests',
            rejected: 'No rejected account requests',
            all: 'No account requests found'
        }[currentRegistrationFilter] || 'No account requests found';
        container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
        return;
    }

    container.innerHTML = registrationRequests.map(request => createRegistrationCard(request)).join('');
}

function createRegistrationCard(request) {
    const createdDate = new Date(request.created_at).toLocaleString();
    const reviewedDate = request.reviewed_at ? new Date(request.reviewed_at).toLocaleString() : '';
    const name = escapeHtml(request.name);
    const email = escapeHtml(request.email);
    const studentId = escapeHtml(request.student_id || 'N/A');
    const studentClass = escapeHtml(request.student_class || 'N/A');
    const phone = escapeHtml(request.phone || 'N/A');
    const requestReason = escapeHtml(request.request_reason || '');
    const reviewNotes = escapeHtml(request.review_notes || '');
    const reviewedBy = escapeHtml(request.reviewed_by_name || 'Administrator');
    const approvedRole = request.approved_role ? formatRequestedRole(request.approved_role) : '';
    const requestedRole = formatRequestedRole(request.requested_role);
    const cardBorder = request.status === 'approved'
        ? '#28a745'
        : request.status === 'rejected'
            ? '#dc3545'
            : '#9c27b0';
    return `
        <div class="pass-item" style="border-left: 4px solid ${cardBorder};">
            <div class="pass-header">
                <span class="pass-id">👤 Request #${request.id}</span>
                <span class="status-badge status-${request.status}">${request.status.toUpperCase()}</span>
            </div>
            <div class="pass-details">
                <div style="background:#f8f9fa; padding:12px; border-radius:6px; margin-bottom:12px;">
                    <p style="margin:4px 0;"><strong>Name:</strong> ${name}</p>
                    <p style="margin:4px 0;"><strong>Email:</strong> ${email}</p>
                    <p style="margin:4px 0;"><strong>Requested Access:</strong> ${requestedRole}</p>
                    <p style="margin:4px 0;"><strong>Personnel ID:</strong> ${studentId}</p>
                    <p style="margin:4px 0;"><strong>Department / Class:</strong> ${studentClass}</p>
                    <p style="margin:4px 0;"><strong>Phone:</strong> ${phone}</p>
                </div>
                <p><strong>Requested:</strong> ${createdDate}</p>
                ${request.status === 'approved' && approvedRole ? `
                    <p><strong>Approved As:</strong> ${approvedRole}</p>
                ` : ''}
                ${request.status !== 'pending' ? `
                    <p><strong>Reviewed:</strong> ${reviewedDate || 'N/A'}${reviewedBy ? ` by ${reviewedBy}` : ''}</p>
                ` : ''}
                ${request.request_reason ? `
                    <div class="pass-reason">
                        <strong>Reason:</strong> ${requestReason}
                    </div>
                ` : ''}
                ${reviewNotes ? `
                    <div class="pass-reason">
                        <strong>Review Notes:</strong> ${reviewNotes}
                    </div>
                ` : ''}
            </div>
            ${request.status === 'pending' ? `
                <div class="pass-actions" style="align-items:center; gap:10px; flex-wrap:wrap;">
                    <label for="approvalRole-${request.id}" style="font-weight:600; color:#555;">Create account as</label>
                    <select id="approvalRole-${request.id}" style="padding:10px 12px; border-radius:8px; border:1px solid #d0d7de;">
                        <option value="personnel" ${request.requested_role === 'guard' ? '' : 'selected'}>Authorized Personnel</option>
                        <option value="guard" ${request.requested_role === 'guard' ? 'selected' : ''}>Security Guard</option>
                    </select>
                    <button class="btn btn-success" onclick="approveRegistrationRequest(${request.id})">
                        ✅ Approve Account
                    </button>
                    <button class="btn btn-danger" onclick="rejectRegistrationRequest(${request.id})">
                        ❌ Reject
                    </button>
                </div>
            ` : ''}
        </div>
    `;
}

// Create pass card HTML
function createPassCard(pass) {
    const requestDate = new Date(pass.request_time).toLocaleString();
    const approvedDate = pass.approved_time ? new Date(pass.approved_time).toLocaleString() : 'N/A';
    const expiryDate = pass.expiry_time ? new Date(pass.expiry_time).toLocaleString() : 'N/A';
    const usedDate = pass.used_time ? new Date(pass.used_time).toLocaleString() : 'N/A';

    // Check if it's a daily entry pass
    const isDailyEntry = pass.reason.includes('Daily Entry');
    const passTypeIcon = isDailyEntry ? '🚪' : '🚶';
    const passTypeLabel = isDailyEntry ? '<span style="background:#4facfe;color:white;padding:4px 8px;border-radius:4px;font-size:12px;margin-left:8px;">DAILY ENTRY</span>' : '';

    // student info display
    const studentName = escapeHtml(pass.student_name || 'Unknown');
    const studentCode = escapeHtml(pass.student_code || `ID: ${pass.student_id}`);
    const studentClass = escapeHtml(pass.student_class || 'N/A');
    const reason = escapeHtml(pass.reason);

    return `
        <div class="pass-item" style="${isDailyEntry ? 'border-left: 4px solid #4facfe;' : ''}">
            <div class="pass-header">
                <span class="pass-id">${passTypeIcon} Pass #${pass.id} ${passTypeLabel}</span>
                <span class="status-badge status-${pass.status}">${pass.status.toUpperCase()}</span>
            </div>
            <div class="pass-details">
                <div style="background:#f8f9fa; padding:12px; border-radius:6px; margin-bottom:12px;">
                    <p style="margin:4px 0;"><strong>👤 Student:</strong> ${studentName}</p>
                    <p style="margin:4px 0;"><strong>🎓 ID:</strong> ${studentCode}</p>
                    <p style="margin:4px 0;"><strong>📚 Class:</strong> ${studentClass}</p>
                </div>
                <p><strong>Requested:</strong> ${requestDate}</p>
                ${pass.approved_time ? `<p><strong>Approved:</strong> ${approvedDate}</p>` : ''}
                ${pass.expiry_time ? `<p><strong>Expires:</strong> ${expiryDate}</p>` : ''}
                ${pass.used_time ? `<p><strong>Used:</strong> ${usedDate}</p>` : ''}
                <div class="pass-reason">
                    <strong>Reason:</strong> ${reason}
                </div>
            </div>
            ${pass.status === 'pending' ? `
                <div class="pass-actions">
                    <button class="btn btn-success" onclick="approvePass(${pass.id})">
                        ✅ Approve ${isDailyEntry ? 'Entry' : ''}
                    </button>
                    <button class="btn btn-danger" onclick="rejectPass(${pass.id})">
                        ❌ Reject
                    </button>
                </div>
            ` : ''}
        </div>
    `;
}

// Approve pass
async function approvePass(passId) {
    if (!confirm('Approve this pass request?')) return;

    try {
        const res = await apiFetch(`/passes/${passId}/approve`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) throw new Error('Failed to approve');

        // Reload passes to update stats
        await loadPasses();
        alert('Pass approved successfully!');
    } catch (err) {
        alert('Failed to approve: ' + err.message);
    }
}

// Reject pass
async function rejectPass(passId) {
    if (!confirm('Reject this pass request?')) return;

    try {
        const res = await apiFetch(`/passes/${passId}/reject`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) throw new Error('Failed to reject');

        // Reload passes to update stats
        await loadPasses();
        alert('Pass rejected');
    } catch (err) {
        alert('Failed to reject: ' + err.message);
    }
}

async function approveRegistrationRequest(requestId) {
    const approvedRole = document.getElementById(`approvalRole-${requestId}`)?.value || 'personnel';
    const roleLabel = formatRequestedRole(approvedRole);
    if (!confirm(`Approve this account request and create the user account as ${roleLabel}?`)) return;

    try {
        const res = await apiFetch(`/admin/registration-requests/${requestId}/approve`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ approved_role: approvedRole })
        });

        const payload = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(payload.detail || 'Failed to approve account request');
        }

        await Promise.all([loadRegistrationRequests({ status: currentRegistrationFilter, notify: false }), loadPasses()]);
        showRequestNotification(`Account request approved as ${roleLabel}. The user can now log in.`, 'success');
    } catch (err) {
        alert('Failed to approve account request: ' + err.message);
    }
}

async function rejectRegistrationRequest(requestId) {
    const reviewNotes = prompt('Reason for rejection (optional):', '');
    if (reviewNotes === null) return;

    try {
        const res = await apiFetch(`/admin/registration-requests/${requestId}/reject`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ review_notes: reviewNotes })
        });

        const payload = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(payload.detail || 'Failed to reject account request');
        }

        await loadRegistrationRequests({ status: currentRegistrationFilter, notify: false });
        showRequestNotification('Account request rejected.', 'warning');
    } catch (err) {
        alert('Failed to reject account request: ' + err.message);
    }
}

// Check if already logged in
if (token) {
    loadUserInfo().then((loaded) => {
        if (!loaded) return;
        showPage('dashboardPage');
        updateNotificationPreferenceUI();
        Promise.all([loadPasses(), loadRegistrationRequests({ notify: false })]);
    });
}

// Auto-refresh every 15 seconds
setInterval(() => {
    if (
        token &&
        document.visibilityState === 'visible' &&
        document.getElementById('dashboardPage').classList.contains('active')
    ) {
        loadPasses();
        loadRegistrationRequests({ status: currentRegistrationFilter, notify: true });
    }
}, 15000);
