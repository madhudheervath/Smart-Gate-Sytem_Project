const API_BASE = CONFIG.API_BASE;
let token = localStorage.getItem('adminToken');
let currentUser = null;
let currentFilter = 'pending';
let allPasses = [];

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
        localStorage.setItem('adminToken', token);

        if (data.role !== 'admin') {
            errorDiv.textContent = 'This portal is for admins only';
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
        document.getElementById('userName').textContent = currentUser.name;
    } catch (err) {
        console.error('Failed to load user info', err);
    }
}

// Logout
function logout() {
    localStorage.removeItem('adminToken');
    token = null;
    currentUser = null;
    showPage('loginPage');
}

// Load passes
async function loadPasses() {
    try {
        const res = await fetch(`${API_BASE}/passes`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        allPasses = await res.json();

        updateStats();
        displayPasses();
    } catch (err) {
        console.error('Failed to load passes', err);
    }
}

// Update statistics
function updateStats() {
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
        pending: pending,
        approvedToday: approvedToday,
        totalApproved: totalApproved,
        used: used,
        today: today
    });
}

// Filter passes
function filterPasses(status) {
    currentFilter = status;

    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
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
    const filtered = currentFilter ? allPasses.filter(p => p.status === currentFilter) : allPasses;

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">No passes found</div>';
        return;
    }

    container.innerHTML = filtered.map(pass => createPassCard(pass)).join('');
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
    const studentName = pass.student_name || 'Unknown';
    const studentCode = pass.student_code || `ID: ${pass.student_id}`;
    const studentClass = pass.student_class || 'N/A';

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
                    <strong>Reason:</strong> ${pass.reason}
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
        const res = await fetch(`${API_BASE}/passes/${passId}/approve`, {
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
        const res = await fetch(`${API_BASE}/passes/${passId}/reject`, {
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

// Check if already logged in
if (token) {
    loadUserInfo().then(() => {
        showPage('dashboardPage');
        loadPasses();
    });
}

// Auto-refresh every 15 seconds
setInterval(() => {
    if (token && document.getElementById('dashboardPage').classList.contains('active')) {
        loadPasses();
    }
}, 15000);

