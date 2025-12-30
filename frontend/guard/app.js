const API_BASE = CONFIG.API_BASE;
let token = localStorage.getItem('scannerToken');
let currentUser = null;
let video = null;
let canvas = null;
let canvasContext = null;
let scanning = false;
let scanCooldown = false;

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
        localStorage.setItem('scannerToken', token);

        if (data.role !== 'guard') {
            errorDiv.textContent = 'This portal is for gate scanners only';
            return;
        }

        await loadUserInfo();
        showPage('scannerPage');
        initializeScanner();
        loadStats();
        loadRecentScans();
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

// Load statistics
async function loadStats() {
    try {
        console.log('Loading stats...');
        const res = await fetch(`${API_BASE}/scans/stats`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) {
            throw new Error(`Stats API returned ${res.status}`);
        }

        const stats = await res.json();
        console.log('Stats loaded:', stats);

        document.getElementById('totalTodayCount').textContent = stats.total_today || 0;
        document.getElementById('entryTodayCount').textContent = stats.entry_today || 0;
        document.getElementById('exitTodayCount').textContent = stats.exit_today || 0;
        document.getElementById('successTodayCount').textContent = stats.success_today || 0;
        document.getElementById('failedTodayCount').textContent = stats.failed_today || 0;
        document.getElementById('totalAllTimeCount').textContent = stats.total_all_time || 0;

        console.log('Stats updated in UI');
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

// Logout
function logout() {
    stopCamera();
    localStorage.removeItem('scannerToken');
    token = null;
    currentUser = null;
    showPage('loginPage');
}

// Initialize scanner
function initializeScanner() {
    // Initialize sequential scanner (QR then Face)
    if (window.sequentialScanner) {
        window.sequentialScanner.init();
    } else {
        // Fallback to old method
        video = document.getElementById('video');
        canvas = document.getElementById('canvas');
        canvasContext = canvas.getContext('2d');
    }
}

// Switch mode
function switchMode(mode) {
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.scanner-mode').forEach(m => m.classList.remove('active'));

    if (mode === 'camera') {
        document.getElementById('cameraBtn').classList.add('active');
        document.getElementById('cameraMode').classList.add('active');
    } else {
        document.getElementById('manualBtn').classList.add('active');
        document.getElementById('manualMode').classList.add('active');
        stopCamera();
    }

    hideResult();
}

// Start camera
async function startCamera() {
    // Use sequential scanner if available
    if (window.sequentialScanner) {
        return await window.sequentialScanner.start();
    }

    // Fallback to old method
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });
        video.srcObject = stream;
        video.setAttribute('playsinline', true);
        video.play();

        scanning = true;
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'block';

        requestAnimationFrame(scanFrame);
    } catch (err) {
        alert('Unable to access camera: ' + err.message);
    }
}

// Stop camera
function stopCamera() {
    // Use sequential scanner if available
    if (window.sequentialScanner) {
        return window.sequentialScanner.stop();
    }

    // Fallback to old method
    scanning = false;
    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }

    document.getElementById('startBtn').style.display = 'block';
    document.getElementById('stopBtn').style.display = 'none';
}

// Scan frame
function scanFrame() {
    if (!scanning) return;

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.height = video.videoHeight;
        canvas.width = video.videoWidth;
        canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);

        const imageData = canvasContext.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert",
        });

        if (code && !scanCooldown) {
            scanCooldown = true;
            // Use face verification if available
            if (window.faceVerify && window.faceVerify.verifyWithFace) {
                window.faceVerify.verifyWithFace(code.data);
            } else {
                verifyToken(code.data);
            }
            setTimeout(() => { scanCooldown = false; }, 3000);
        }
    }

    requestAnimationFrame(scanFrame);
}

// Verify token
async function verifyToken(token_str) {
    try {
        // Use FormData to match backend expectations
        const formData = new FormData();
        formData.append('token', token_str);

        const res = await fetch(`${API_BASE}/verify`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            const studentInfo = data.student_name ?
                `${data.student_name} (${data.student_code})` :
                `Student #${data.student_id}`;
            showResult('success', '✅ GRANTED',
                `Pass #${data.pass_id}<br>${studentInfo}`);
            playSound('success');
            // Reload recent scans and stats
            setTimeout(() => {
                loadRecentScans();
                loadStats();
            }, 500);
        } else {
            throw new Error(data.detail || 'Verification failed');
        }
    } catch (err) {
        showResult('error', '❌ DENIED', err.message);
        playSound('error');
        // Reload recent scans and stats even on error
        setTimeout(() => {
            loadRecentScans();
            loadStats();
        }, 500);
    }
}

// Manual verification
async function verifyManual() {
    const token_str = document.getElementById('manualToken').value.trim();
    if (!token_str) {
        alert('Please enter a token');
        return;
    }

    await verifyToken(token_str);
    document.getElementById('manualToken').value = '';
}

// Show result
function showResult(type, title, message) {
    const resultDiv = document.getElementById('resultDisplay');
    resultDiv.className = `result-display show result-${type}`;
    resultDiv.innerHTML = `
        <div class="result-icon">${type === 'success' ? '✅' : '❌'}</div>
        <div style="font-size:32px; margin-bottom:10px;">${title}</div>
        <div style="font-size:16px; font-weight:normal;">${message}</div>
    `;

    setTimeout(() => {
        resultDiv.classList.remove('show');
    }, 5000);
}

// Hide result
function hideResult() {
    document.getElementById('resultDisplay').classList.remove('show');
}

// Play sound (simple beep using Web Audio API)
function playSound(type) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        oscillator.frequency.value = type === 'success' ? 800 : 400;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);

        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.5);
    } catch (err) {
        // Audio not supported
    }
}

// Load recent scans
async function loadRecentScans() {
    const container = document.getElementById('recentScans');

    try {
        const res = await fetch(`${API_BASE}/scans?limit=20`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) throw new Error('Failed to load scans');

        const scans = await res.json();

        if (scans.length === 0) {
            container.innerHTML = '<div class="empty-state">No scans yet</div>';
            return;
        }

        container.innerHTML = scans.map(scan => {
            const timeStr = new Date(scan.scan_time).toLocaleString();
            const studentInfo = scan.student_name ?
                `${scan.student_name} (${scan.student_code})` :
                `Student #${scan.student_id}`;
            const resultClass = scan.result === 'success' ? 'success' : 'error';
            const resultIcon = scan.result === 'success' ? '✅' : '❌';

            return `
                <div class="scan-item scan-${resultClass}">
                    <div class="scan-header">
                        <span class="scan-result">${resultIcon} ${scan.result.toUpperCase()}</span>
                        <span class="scan-time">${timeStr}</span>
                    </div>
                    <div class="scan-details">
                        <div><strong>Student:</strong> ${studentInfo}</div>
                        <div><strong>Pass ID:</strong> #${scan.pass_id}</div>
                        ${scan.details ? `<div><strong>Details:</strong> ${scan.details}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        container.innerHTML = '<div class="empty-state">Failed to load scans</div>';
        console.error('Error loading scans:', err);
    }
}

// Check if already logged in
if (token) {
    loadUserInfo().then(() => {
        showPage('scannerPage');
        initializeScanner();
        loadStats();
        loadRecentScans();
    });
}

// Initialize recent scans on load (legacy fallback)
if (document.getElementById('recentScans') && !token) {
    loadRecentScans();
}

