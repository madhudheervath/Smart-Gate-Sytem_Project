const API_BASE = CONFIG.API_BASE;
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

function formatAdminDateTime(value, options = {}) {
    if (window.DateTimeHelper) return DateTimeHelper.formatLocal(value, options);
    if (!value) return 'N/A';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleString();
}

function formatAdminTime(value, options = {}) {
    if (window.DateTimeHelper) return DateTimeHelper.formatTime(value, options);
    if (!value) return 'N/A';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleTimeString();
}

function parseAdminDate(value) {
    if (window.DateTimeHelper) return DateTimeHelper.parseBackendDate(value);
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
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
        const approvedDate = parseAdminDate(p.approved_time);
        if (!approvedDate) return false;
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
    const createdDate = formatAdminDateTime(request.created_at);
    const reviewedDate = request.reviewed_at ? formatAdminDateTime(request.reviewed_at) : '';
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
        ? 'var(--success)'
        : request.status === 'rejected'
            ? 'var(--danger)'
            : 'var(--accent-h)';
    return `
        <div class="pass-item" style="border-left: 4px solid ${cardBorder};">
            <div class="pass-header">
                <span class="pass-id">Request #${request.id}</span>
                <span class="status-badge status-${request.status}">${request.status.toUpperCase()}</span>
            </div>
            <div class="pass-details">
                <div style="background:var(--bg-raised); padding:12px; border-radius:6px; margin-bottom:12px; border:1px solid var(--border);">
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Name:</strong> ${name}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Email:</strong> ${email}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Requested Access:</strong> ${requestedRole}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Personnel ID:</strong> ${studentId}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Dept / Class:</strong> ${studentClass}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Phone:</strong> ${phone}</p>
                </div>
                <p style="color:var(--text-2);"><strong style="color:var(--text-3);">Requested:</strong> ${createdDate}</p>
                ${request.status === 'approved' && approvedRole ? `
                    <p style="color:var(--text-2);"><strong style="color:var(--text-3);">Approved As:</strong> ${approvedRole}</p>
                ` : ''}
                ${request.status !== 'pending' ? `
                    <p style="color:var(--text-2);"><strong style="color:var(--text-3);">Reviewed:</strong> ${reviewedDate || 'N/A'}${reviewedBy ? ` by ${reviewedBy}` : ''}</p>
                ` : ''}
                ${request.request_reason ? `
                    <div class="pass-reason">
                        <strong style="color:var(--text-3);">Reason:</strong> ${requestReason}
                    </div>
                ` : ''}
                ${reviewNotes ? `
                    <div class="pass-reason">
                        <strong style="color:var(--text-3);">Review Notes:</strong> ${reviewNotes}
                    </div>
                ` : ''}
            </div>
            ${request.status === 'pending' ? `
                <div class="pass-actions" style="align-items:center; gap:10px; flex-wrap:wrap;">
                    <label for="approvalRole-${request.id}" style="font-weight:500;color:var(--text-2);">Create account as</label>
                    <select id="approvalRole-${request.id}">
                        <option value="personnel" ${request.requested_role === 'guard' ? '' : 'selected'}>Authorized Personnel</option>
                        <option value="guard" ${request.requested_role === 'guard' ? 'selected' : ''}>Security Guard</option>
                    </select>
                    <button class="btn btn-success btn-sm" onclick="approveRegistrationRequest(${request.id})">
                        Approve Account
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="rejectRegistrationRequest(${request.id})">
                        Reject
                    </button>
                </div>
            ` : ''}
        </div>
    `;
}

// Create pass card HTML
function createPassCard(pass) {
    const requestDate = formatAdminDateTime(pass.request_time);
    const approvedDate = pass.approved_time ? formatAdminDateTime(pass.approved_time) : 'N/A';
    const expiryDate = pass.expiry_time ? formatAdminDateTime(pass.expiry_time) : 'N/A';
    const usedDate = pass.used_time ? formatAdminDateTime(pass.used_time) : 'N/A';

    // Check if it's a daily entry pass
    const isDailyEntry = pass.reason.includes('Daily Entry');
    const passTypeLabel = isDailyEntry ? '<span class="badge badge-info" style="margin-left:8px;font-size:.68rem;">DAILY ENTRY</span>' : '';

    // student info display
    const studentName = escapeHtml(pass.student_name || 'Unknown');
    const studentCode = escapeHtml(pass.student_code || `ID: ${pass.student_id}`);
    const studentClass = escapeHtml(pass.student_class || 'N/A');
    const reason = escapeHtml(pass.reason);

    return `
        <div class="pass-item" style="${isDailyEntry ? 'border-left: 4px solid var(--info);' : ''}">
            <div class="pass-header">
                <span class="pass-id">Pass #${pass.id} ${passTypeLabel}</span>
                <span class="status-badge status-${pass.status}">${pass.status.toUpperCase()}</span>
            </div>
            <div class="pass-details">
                <div style="background:var(--bg-raised); padding:12px; border-radius:6px; margin-bottom:12px; border:1px solid var(--border);">
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Student:</strong> ${studentName}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">ID:</strong> ${studentCode}</p>
                    <p style="margin:4px 0;color:var(--text-2);"><strong style="color:var(--text-3);">Class:</strong> ${studentClass}</p>
                </div>
                <p style="color:var(--text-2);"><strong style="color:var(--text-3);">Requested:</strong> ${requestDate}</p>
                ${pass.approved_time ? `<p style="color:var(--text-2);"><strong style="color:var(--text-3);">Approved:</strong> ${approvedDate}</p>` : ''}
                ${pass.expiry_time ? `<p style="color:var(--text-2);"><strong style="color:var(--text-3);">Expires:</strong> ${expiryDate}</p>` : ''}
                ${pass.used_time ? `<p style="color:var(--text-2);"><strong style="color:var(--text-3);">Used:</strong> ${usedDate}</p>` : ''}
                <div class="pass-reason">
                    <strong style="color:var(--text-3);">Reason:</strong> ${reason}
                </div>
            </div>
            ${pass.status === 'pending' ? `
                <div class="pass-actions">
                    <button class="btn btn-success btn-sm" onclick="approvePass(${pass.id})">
                        Approve ${isDailyEntry ? 'Entry' : ''}
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="rejectPass(${pass.id})">
                        Reject
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

// ============================================================================
// SLOT MANAGEMENT
// ============================================================================

let slotPanelOpen = false;

function toggleSlotPanel() {
    const panel = document.getElementById('slotPanel');
    slotPanelOpen = !slotPanelOpen;
    panel.style.display = slotPanelOpen ? 'block' : 'none';
    if (slotPanelOpen) loadSlots();
}

function showSlotError(message) {
    const errEl = document.getElementById('slotError');
    if (!errEl) return;
    errEl.textContent = message || '';
    errEl.style.display = message ? 'block' : 'none';
}

function slotInputValue(date) {
    return window.DateTimeHelper
        ? DateTimeHelper.toLocalInputValue(date)
        : new Date(date).toISOString().slice(0, 16);
}

function slotInputDate(id) {
    const value = document.getElementById(id)?.value;
    if (window.DateTimeHelper) return DateTimeHelper.fromLocalInputValue(value);
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
}

function setSlotInputs(start, end) {
    const startInput = document.getElementById('slotStart');
    const endInput = document.getElementById('slotEnd');
    if (startInput) startInput.value = slotInputValue(start);
    if (endInput) endInput.value = slotInputValue(end);
    updateSlotWindowPreview();
}

function defaultSlotStart() {
    const base = new Date(Date.now() + 15 * 60 * 1000);
    return window.DateTimeHelper ? DateTimeHelper.roundUpMinutes(base, 15) : base;
}

function setSlotPreset(kind) {
    const now = new Date();
    let start;
    let end;

    if (kind === 'morning') {
        start = new Date(now);
        start.setDate(start.getDate() + 1);
        start.setHours(9, 0, 0, 0);
        end = new Date(start);
        end.setHours(11, 0, 0, 0);
    } else if (kind === 'evening') {
        start = new Date(now);
        start.setHours(16, 0, 0, 0);
        if (start <= now) start.setDate(start.getDate() + 1);
        end = new Date(start);
        end.setHours(18, 0, 0, 0);
    } else {
        start = defaultSlotStart();
        end = new Date(start.getTime() + 60 * 60 * 1000);
    }

    setSlotInputs(start, end);
}

function extendSlotDuration(minutes) {
    const start = slotInputDate('slotStart') || defaultSlotStart();
    const currentEnd = slotInputDate('slotEnd') || start;
    const end = new Date(currentEnd.getTime() + minutes * 60 * 1000);
    setSlotInputs(start, end);
}

function updateSlotWindowPreview() {
    const preview = document.getElementById('slotWindowPreview');
    const startHint = document.getElementById('slotStartHint');
    const endHint = document.getElementById('slotEndHint');
    const endInput = document.getElementById('slotEnd');
    if (!preview) return;

    const start = slotInputDate('slotStart');
    const end = slotInputDate('slotEnd');

    if (endInput && start) {
        endInput.min = slotInputValue(start);
    }

    if (startHint) startHint.textContent = start ? `Local: ${formatAdminDateTime(start)}` : '';
    if (endHint) endHint.textContent = end ? `Local: ${formatAdminDateTime(end)}` : '';

    preview.classList.remove('error');
    if (!start || !end) {
        preview.textContent = 'Select a start and end time to preview the slot window.';
        return;
    }
    if (end <= start) {
        preview.classList.add('error');
        preview.textContent = 'End time must be after start time.';
        return;
    }

    const durationMinutes = Math.round((end - start) / 60000);
    const hours = Math.floor(durationMinutes / 60);
    const minutes = durationMinutes % 60;
    const duration = [
        hours ? `${hours} hr${hours === 1 ? '' : 's'}` : '',
        minutes ? `${minutes} min` : ''
    ].filter(Boolean).join(' ') || '0 min';
    const windowLabel = window.DateTimeHelper
        ? DateTimeHelper.formatSlotWindow(start, end)
        : `${start.toLocaleString()} to ${end.toLocaleString()}`;

    preview.innerHTML = `
        <strong>${escapeHtml(windowLabel)}</strong>
        Duration: ${escapeHtml(duration)}. QR tokens for this slot cannot be valid after the end time.
    `;
}

function initSlotTimeControls() {
    const timezoneLabel = document.getElementById('slotTimezoneLabel');
    if (timezoneLabel) {
        timezoneLabel.textContent = window.DateTimeHelper ? DateTimeHelper.zoneLabel() : 'Browser local time';
    }

    const startInput = document.getElementById('slotStart');
    const endInput = document.getElementById('slotEnd');
    if (!startInput || !endInput) return;

    if (!startInput.value || !endInput.value) {
        const start = defaultSlotStart();
        const end = new Date(start.getTime() + 60 * 60 * 1000);
        setSlotInputs(start, end);
    }

    startInput.addEventListener('input', updateSlotWindowPreview);
    startInput.addEventListener('change', updateSlotWindowPreview);
    endInput.addEventListener('input', updateSlotWindowPreview);
    endInput.addEventListener('change', updateSlotWindowPreview);
    updateSlotWindowPreview();
}

async function loadSlots() {
    const container = document.getElementById('slotsListContainer');
    try {
        const res = await apiFetch('/api/slots?active_only=false', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed to load slots');
        const slots = await res.json();

        if (!slots.length) {
            container.innerHTML = '<p style="color:var(--text-3); text-align:center;padding:20px;">No slots defined yet.</p>';
            return;
        }

        container.innerHTML = `
            <div style="overflow-x:auto;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Label</th>
                        <th>Gate</th>
                        <th>Window <span style="display:block;font-size:.68rem;font-weight:500;color:var(--text-3);">${escapeHtml(window.DateTimeHelper ? DateTimeHelper.zoneLabel() : 'Local time')}</span></th>
                        <th style="text-align:center;">Cap.</th>
                        <th style="text-align:center;">Booked</th>
                        <th style="text-align:center;">GPS</th>
                        <th style="text-align:center;">Face</th>
                        <th style="text-align:center;">Status</th>
                        <th style="text-align:center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${slots.map(s => `
                        <tr>
                            <td style="color:var(--text-1);">${escapeHtml(s.label)}</td>
                            <td>${escapeHtml(s.gate)}</td>
                            <td style="font-size:.78rem;line-height:1.45;">
                                <strong style="color:var(--text-1);font-weight:600;">${escapeHtml(window.DateTimeHelper ? DateTimeHelper.formatSlotWindow(s.start_time, s.end_time) : `${formatAdminDateTime(s.start_time)} to ${formatAdminDateTime(s.end_time)}`)}</strong>
                            </td>
                            <td style="text-align:center;">${s.capacity}</td>
                            <td style="text-align:center;">
                                ${s.booked_count}
                                <div style="font-size:.7rem; color:var(--text-3);">${s.remaining} left</div>
                            </td>
                            <td style="text-align:center;">${s.gps_required ? '<span style="color:var(--success);">Yes</span>' : '—'}</td>
                            <td style="text-align:center;">${s.face_check_required ? '<span style="color:var(--success);">Yes</span>' : '—'}</td>
                            <td style="text-align:center;">
                                <span class="badge ${s.active ? 'badge-success' : 'badge-danger'}">
                                    ${s.active ? 'Active' : 'Inactive'}
                                </span>
                            </td>
                            <td style="text-align:center;">
                                <button onclick="deactivateSlot(${s.id})" class="btn btn-danger btn-sm" ${!s.active ? 'disabled' : ''}>
                                    Deactivate
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            </div>`;
    } catch (err) {
        container.innerHTML = `<p style="color:var(--danger);">Failed to load slots: ${escapeHtml(err.message)}</p>`;
    }
}

async function createSlot(e) {
    if (e) e.preventDefault();
    showSlotError('');

    const label = document.getElementById('slotLabel').value.trim();
    const gate = document.getElementById('slotGate').value.trim() || 'Main Gate';
    const start = slotInputDate('slotStart');
    const end = slotInputDate('slotEnd');
    const capacity = parseInt(document.getElementById('slotCapacity').value) || 50;
    const gpsReq = document.getElementById('slotGpsReq').checked;
    const faceReq = document.getElementById('slotFaceReq').checked;

    if (!label) { showSlotError('Label is required.'); return; }
    if (!start || !end) { showSlotError('Start and end times are required.'); return; }
    if (end <= start) { showSlotError('End time must be after start time.'); return; }

    try {
        const res = await apiFetch('/api/slots', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                label, gate, capacity,
                start_time: start.toISOString(),
                end_time: end.toISOString(),
                active: true,
                gps_required: gpsReq,
                face_check_required: faceReq,
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to create slot');
        // Clear form
        document.getElementById('slotLabel').value = '';
        document.getElementById('slotCapacity').value = '50';
        document.getElementById('slotGpsReq').checked = false;
        document.getElementById('slotFaceReq').checked = false;
        setSlotPreset('next-hour');
        await loadSlots();
    } catch (err) {
        showSlotError(err.message);
    }
}

async function deactivateSlot(slotId) {
    if (!confirm('Deactivate this slot? All future bookings will be blocked.')) return;
    try {
        const res = await apiFetch(`/api/slots/${slotId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Failed to deactivate');
        await loadSlots();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ============================================================================
// VISITOR PASS
// ============================================================================

function showVisitorPassModal() {
    document.getElementById('visitorPassModal').style.display = 'flex';
    document.getElementById('vpResult').style.display = 'none';
    document.getElementById('vpError').textContent = '';
    const qrEl = document.getElementById('vpQrCode');
    if (qrEl) qrEl.innerHTML = '';
}

function closeVisitorPassModal() {
    document.getElementById('visitorPassModal').style.display = 'none';
    document.getElementById('vpName').value = '';
    document.getElementById('vpPhone').value = '';
    document.getElementById('vpReason').value = '';
    document.getElementById('vpTtl').value = '60';
}

async function issueVisitorPass() {
    const errEl = document.getElementById('vpError');
    errEl.textContent = '';

    const name = document.getElementById('vpName').value.trim();
    const phone = document.getElementById('vpPhone').value.trim();
    const reason = document.getElementById('vpReason').value.trim();
    const passType = document.getElementById('vpType').value;
    const ttl = parseInt(document.getElementById('vpTtl').value) || 60;

    if (!name) { errEl.textContent = 'Visitor name is required.'; return; }
    if (!reason) { errEl.textContent = 'Reason is required.'; return; }

    try {
        const res = await apiFetch('/api/admin/visitor-pass', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ visitor_name: name, visitor_phone: phone || null, reason, pass_type: passType, ttl_minutes: ttl })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to issue pass');

        const expiry = data.expiry_time ? formatAdminTime(data.expiry_time) : 'N/A';
        document.getElementById('vpResultText').textContent =
            `Pass #${data.id} issued. Valid until ${expiry}. Present this QR at the guard checkpoint.`;
        const qrEl = document.getElementById('vpQrCode');
        if (qrEl) {
            qrEl.innerHTML = '';
            if (data.qr_token && typeof QRCode !== 'undefined') {
                new QRCode(qrEl, {
                    text: data.qr_token,
                    width: 180,
                    height: 180,
                    colorDark: '#000000',
                    colorLight: '#ffffff',
                    correctLevel: QRCode.CorrectLevel.H,
                });
            } else {
                qrEl.textContent = data.qr_token || 'QR token unavailable';
            }
        }
        document.getElementById('vpResult').style.display = 'block';
    } catch (err) {
        errEl.textContent = err.message;
    }
}

// ============================================================================
// Check if already logged in
// ============================================================================

// Check if already logged in
initSlotTimeControls();

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

// =====================================================================
// User Management
// =====================================================================

let _editingUserId = null;

function toggleUsersPanel() {
    const panel = document.getElementById('usersPanel');
    const visible = panel.style.display !== 'none';
    panel.style.display = visible ? 'none' : 'block';
    if (!visible) loadUsers();
}

async function loadUsers() {
    const search = document.getElementById('userSearchInput').value.trim();
    const role = document.getElementById('userRoleFilter').value;
    const active = document.getElementById('userActiveFilter').value;

    let url = `${API_BASE}/api/admin/users?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (role) url += `role=${encodeURIComponent(role)}&`;
    if (active !== '') url += `active=${active}&`;

    const container = document.getElementById('usersTableContainer');
    container.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:20px;">Loading…</p>';

    try {
        const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
        if (!res.ok) throw new Error(await res.text());
        const users = await res.json();

        if (!users.length) {
            container.innerHTML = '<p style="text-align:center;color:var(--text-3);padding:20px;">No users found.</p>';
            return;
        }

        const roleColors = {
            admin:   'background:rgba(99,102,241,.15);color:#818cf8;',
            guard:   'background:rgba(52,211,153,.12);color:#34d399;',
            student: 'background:rgba(96,165,250,.12);color:#60a5fa;'
        };
        const rows = users.map(u => `
            <tr>
                <td>${u.id}</td>
                <td style="font-weight:600;color:var(--text-1);">${escHtml(u.name)}</td>
                <td style="font-size:.8rem;">${escHtml(u.email)}</td>
                <td>
                    <span style="${roleColors[u.role] || 'background:var(--bg-raised);color:var(--text-2);'}padding:2px 8px;border-radius:12px;font-size:.72rem;">${u.role}</span>
                </td>
                <td style="font-size:.8rem;">${escHtml(u.student_id || '—')}</td>
                <td>
                    <span style="color:${u.active ? 'var(--success)' : 'var(--danger)'};font-size:.8rem;">${u.active ? 'Active' : 'Inactive'}</span>
                </td>
                <td style="font-size:.8rem;">${u.face_registered ? '<span style="color:var(--success);">Enrolled</span>' : '<span style="color:var(--text-3);">None</span>'}</td>
                <td style="white-space:nowrap;">
                    <button onclick="openEditUser(${u.id})" class="btn btn-secondary btn-sm" style="margin-right:4px;">Edit</button>
                    ${u.active
                        ? `<button onclick="deactivateUser(${u.id},'${escHtml(u.name)}')" class="btn btn-danger btn-sm">Deactivate</button>`
                        : `<button onclick="reactivateUser(${u.id})" class="btn btn-success btn-sm">Reactivate</button>`
                    }
                    ${u.face_registered
                        ? `<button onclick="resetFace(${u.id},'${escHtml(u.name)}')" class="btn btn-ghost btn-sm" style="margin-top:4px;">Reset Face</button>`
                        : ''
                    }
                </td>
            </tr>`).join('');

        container.innerHTML = `
            <div style="overflow-x:auto;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Student ID</th>
                            <th>Status</th>
                            <th>Face</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
                <p style="font-size:.72rem;color:var(--text-3);margin-top:8px;text-align:right;">${users.length} user(s)</p>
            </div>`;
    } catch (err) {
        container.innerHTML = `<p style="color:var(--danger);text-align:center;padding:16px;">Error: ${err.message}</p>`;
    }
}

function escHtml(str) {
    if (str == null) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showCreateUserModal() {
    _editingUserId = null;
    document.getElementById('userModalTitle').textContent = 'Create User';
    document.getElementById('umSubmitBtn').textContent = 'Create';
    document.getElementById('umPasswordGroup').style.display = 'block';
    document.getElementById('umActiveGroup').style.display = 'none';
    ['umName','umEmail','umPassword','umStudentId','umClass','umPhone','umGuardian'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('umRole').value = 'student';
    document.getElementById('umError').textContent = '';
    document.getElementById('userModal').style.display = 'flex';
}

async function openEditUser(userId) {
    try {
        const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(await res.text());
        const u = await res.json();

        _editingUserId = userId;
        document.getElementById('userModalTitle').textContent = `Edit User — ${u.name}`;
        document.getElementById('umSubmitBtn').textContent = 'Save Changes';
        document.getElementById('umPasswordGroup').style.display = 'none';
        document.getElementById('umActiveGroup').style.display = 'flex';

        document.getElementById('umName').value = u.name || '';
        document.getElementById('umEmail').value = u.email || '';
        document.getElementById('umRole').value = u.role || 'student';
        document.getElementById('umStudentId').value = u.student_id || '';
        document.getElementById('umClass').value = u.student_class || '';
        document.getElementById('umPhone').value = u.phone || '';
        document.getElementById('umGuardian').value = u.guardian_name || '';
        document.getElementById('umActive').checked = u.active;
        document.getElementById('umError').textContent = '';
        document.getElementById('userModal').style.display = 'flex';
    } catch (err) {
        alert('Failed to load user: ' + err.message);
    }
}

function closeUserModal() {
    document.getElementById('userModal').style.display = 'none';
}

async function submitUserModal() {
    const errEl = document.getElementById('umError');
    errEl.textContent = '';

    const name = document.getElementById('umName').value.trim();
    const email = document.getElementById('umEmail').value.trim();
    const role = document.getElementById('umRole').value;

    if (!name || !email) { errEl.textContent = 'Name and Email are required.'; return; }

    const btn = document.getElementById('umSubmitBtn');
    btn.disabled = true;

    try {
        if (_editingUserId == null) {
            // Create
            const password = document.getElementById('umPassword').value;
            if (!password || password.length < 8) { errEl.textContent = 'Password must be at least 8 characters.'; btn.disabled=false; return; }
            const body = {
                name, email, password, role,
                student_id: document.getElementById('umStudentId').value.trim() || null,
                student_class: document.getElementById('umClass').value.trim() || null,
                phone: document.getElementById('umPhone').value.trim() || null,
                guardian_name: document.getElementById('umGuardian').value.trim() || null,
                active: true,
            };
            const res = await fetch(`${API_BASE}/api/admin/users`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Failed'); }
            closeUserModal();
            loadUsers();
        } else {
            // Update
            const body = {
                name, role,
                student_id: document.getElementById('umStudentId').value.trim() || null,
                student_class: document.getElementById('umClass').value.trim() || null,
                phone: document.getElementById('umPhone').value.trim() || null,
                guardian_name: document.getElementById('umGuardian').value.trim() || null,
                active: document.getElementById('umActive').checked,
            };
            const res = await fetch(`${API_BASE}/api/admin/users/${_editingUserId}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Failed'); }
            closeUserModal();
            loadUsers();
        }
    } catch (err) {
        errEl.textContent = err.message;
    } finally {
        btn.disabled = false;
    }
}

async function deactivateUser(userId, name) {
    if (!confirm(`Deactivate account for "${name}"? They will not be able to log in.`)) return;
    try {
        const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok && res.status !== 204) { const d = await res.json(); throw new Error(d.detail || 'Failed'); }
        loadUsers();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function reactivateUser(userId) {
    try {
        const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
            method: 'PATCH',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: true }),
        });
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Failed'); }
        loadUsers();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function resetFace(userId, name) {
    if (!confirm(`Reset face registration for "${name}"? They will need to re-enroll.`)) return;
    try {
        const res = await fetch(`${API_BASE}/api/admin/users/${userId}/reset-face`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Failed'); }
        loadUsers();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ── HTML call-site aliases (HTML uses these names) ──────────────────────
function openUserModal()               { showCreateUserModal(); }
function handleUserSubmit(e)           { if(e) e.preventDefault(); submitUserModal(); }
function generateVisitorPass(e)        { if(e) e.preventDefault(); issueVisitorPass(); }
function fetchUsers()                  { loadUsers(); }
function loadAdminData()               { loadPasses(); loadRegistrationRequests({ notify: false }); }
