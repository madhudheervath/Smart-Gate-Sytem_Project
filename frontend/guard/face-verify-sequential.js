/**
 * Sequential Face Verification for Guard Portal
 * Step 1: Scan QR Code
 * Step 2: Prompt for Face
 * Step 3: Capture Face
 * Step 4: Verify Both
 * Step 5: Grant/Deny
 */

(function() {
    // Scoped variables to avoid conflicts
    let video = null;
    let canvas = null;
    let canvasContext = null;
    let scanning = false;
    let scanCooldown = false;
    let faceVerificationEnabled = true;
    let currentMode = 'qr'; // 'qr' or 'face'
    let scannedToken = null;

// Update status display
function updateStatus(message, className = '') {
    const statusDiv = document.getElementById('scanStatus');
    const labelDiv = document.getElementById('cameraLabel');
    
    if (statusDiv) {
        statusDiv.textContent = message;
        statusDiv.className = 'scan-status ' + className;
    }
    
    if (labelDiv) {
        if (currentMode === 'face') {
            labelDiv.textContent = '👤 Show Your Face';
        } else {
            labelDiv.textContent = '📷 Scan QR Code';
        }
    }
}

// Initialize
function initSequentialScanner() {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    if (canvas) {
        canvasContext = canvas.getContext('2d');
    }
    
    // Listen to face verification toggle
    const toggle = document.getElementById('faceVerifyToggle');
    if (toggle) {
        faceVerificationEnabled = toggle.checked;
        toggle.addEventListener('change', (e) => {
            faceVerificationEnabled = e.target.checked;
            console.log('Face verification:', faceVerificationEnabled ? 'Enabled' : 'Disabled');
        });
    }
}

// Start camera
async function startSequentialCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'user',  // Front camera for both QR and face
                width: { ideal: 1280 },
                height: { ideal: 720 }
            } 
        });
        video.srcObject = stream;
        video.setAttribute('playsinline', true);
        await video.play();
        
        currentMode = 'qr';
        scanning = true;
        updateStatus('Ready to scan QR', 'qr-scanning');
        
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'block';
        
        requestAnimationFrame(scanLoop);
        return true;
    } catch (err) {
        console.error('Camera error:', err);
        alert('Unable to access camera: ' + err.message);
        return false;
    }
}

// Stop camera
function stopSequentialCamera() {
    scanning = false;
    currentMode = 'qr';
    scannedToken = null;
    
    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
    
    updateStatus('Camera stopped');
    document.getElementById('startBtn').style.display = 'block';
    document.getElementById('stopBtn').style.display = 'none';
}

// Main scanning loop
function scanLoop() {
    if (!scanning) return;
    
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        if (currentMode === 'qr' && !scanCooldown) {
            // Scan for QR code
            const imageData = canvasContext.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
            });
            
            if (code) {
                onQRDetected(code.data);
            }
        }
    }
    
    requestAnimationFrame(scanLoop);
}

// QR Code detected
function onQRDetected(qrToken) {
    console.log('QR detected:', qrToken.substring(0, 20) + '...');
    scanCooldown = true;
    scannedToken = qrToken;
    
    updateStatus('✅ QR Detected!', 'qr-detected');
    playSound('success');
    
    // Check if face verification is enabled
    if (faceVerificationEnabled) {
        // Prompt for face
        setTimeout(() => {
            currentMode = 'face';
            updateStatus('👤 Now show your FACE to camera', 'face-prompt');
            playSound('beep');
            
            // Wait 2 seconds, then capture face
            setTimeout(() => {
                captureFaceAndVerify();
            }, 2000);
        }, 1000);
    } else {
        // No face verification, verify QR only
        setTimeout(() => {
            verifyQROnly(scannedToken);
        }, 1000);
    }
}

// Capture face and verify
async function captureFaceAndVerify() {
    try {
        updateStatus('📸 Capturing face...', 'face-capturing');
        
        // Capture current frame
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to blob
        const faceBlob = await new Promise((resolve) => {
            canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.85);
        });
        
        console.log('Face captured:', faceBlob ? `${faceBlob.size} bytes` : 'null');
        
        if (!faceBlob) {
            throw new Error('Failed to capture face image');
        }
        
        // Now verify both QR + Face
        updateStatus('🔍 Verifying QR + Face...', 'verifying');
        await verifyQRAndFace(scannedToken, faceBlob);
        
    } catch (err) {
        console.error('Face capture error:', err);
        showResult('error', '❌ FACE CAPTURE FAILED', err.message);
        playSound('error');
        resetToQRMode();
    }
}

// Verify QR + Face
async function verifyQRAndFace(qrToken, faceBlob) {
    try {
        const formData = new FormData();
        formData.append('token', qrToken);
        formData.append('face_image', faceBlob, 'face.jpg');
        
        console.log('Sending verification: QR + Face');
        
        const res = await fetch(`${API_BASE}/verify`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await res.json();
        console.log('Verification response:', data);
        
        if (res.ok) {
            // Check if face was verified
            if (data.face_verified === false) {
                // Face didn't match - DENY
                showResult('error', '❌ ACCESS DENIED', 
                    `Face verification FAILED<br>${data.face_message || 'Face does not match'}<br><br>QR was valid but face mismatch`);
                playSound('error');
            } else if (data.face_verified === true) {
                // Both QR and Face verified - GRANT
                const confidence = data.face_confidence || 0;
                const studentInfo = data.student_name ? 
                    `${data.student_name} (${data.student_code})` : 
                    `Student #${data.student_id}`;
                
                showResult('success', '✅ ACCESS GRANTED', 
                    `Pass #${data.pass_id}<br>${studentInfo}<br><br>` +
                    `<div style="background: rgba(76,175,80,0.2); padding: 10px; border-radius: 8px; margin-top: 10px;">` +
                    `<strong>✅ QR Verified</strong><br>` +
                    `<strong>✅ Face Verified</strong> (${confidence.toFixed(1)}% match)<br>` +
                    `Distance: ${data.face_distance?.toFixed(3) || 'N/A'}` +
                    `</div>`);
                playSound('success');
            } else {
                // Face verification not performed (student hasn't registered)
                showResult('success', '✅ ACCESS GRANTED', 
                    `Pass #${data.pass_id}<br>${data.student_name || ''}<br><br>` +
                    `<div style="background: rgba(255,193,7,0.2); padding: 10px; border-radius: 8px; margin-top: 10px;">` +
                    `<strong>✅ QR Verified</strong><br>` +
                    `<strong>ℹ️ Face not registered</strong><br>` +
                    `Student hasn't registered face photo` +
                    `</div>`);
                playSound('success');
            }
            
            // Reload stats
            setTimeout(() => {
                if (typeof loadRecentScans === 'function') loadRecentScans();
                if (typeof loadStats === 'function') loadStats();
            }, 500);
        } else {
            throw new Error(data.detail || 'Verification failed');
        }
        
        // Reset after 5 seconds
        setTimeout(() => {
            resetToQRMode();
        }, 5000);
        
    } catch (err) {
        console.error('Verification error:', err);
        showResult('error', '❌ VERIFICATION FAILED', err.message);
        playSound('error');
        setTimeout(() => resetToQRMode(), 3000);
    }
}

// Verify QR only (face verification disabled)
async function verifyQROnly(qrToken) {
    try {
        updateStatus('🔍 Verifying QR...', 'verifying');
        
        const formData = new FormData();
        formData.append('token', qrToken);
        
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
            
            showResult('success', '✅ ACCESS GRANTED', 
                `Pass #${data.pass_id}<br>${studentInfo}<br><br>✅ QR Verified`);
            playSound('success');
            
            setTimeout(() => {
                if (typeof loadRecentScans === 'function') loadRecentScans();
                if (typeof loadStats === 'function') loadStats();
            }, 500);
        } else {
            throw new Error(data.detail || 'QR verification failed');
        }
        
        setTimeout(() => resetToQRMode(), 5000);
        
    } catch (err) {
        showResult('error', '❌ DENIED', err.message);
        playSound('error');
        setTimeout(() => resetToQRMode(), 3000);
    }
}

// Reset to QR scanning mode
function resetToQRMode() {
    currentMode = 'qr';
    scannedToken = null;
    scanCooldown = false;
    updateStatus('Ready to scan QR', 'qr-scanning');
}

// Show result (reuse existing function)
function showResult(type, title, message) {
    const resultDiv = document.getElementById('resultDisplay');
    if (!resultDiv) return;
    
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

// Play sound (reuse existing function)
function playSound(type) {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        if (type === 'success') {
            oscillator.frequency.value = 800;
        } else if (type === 'beep') {
            oscillator.frequency.value = 600;
        } else {
            oscillator.frequency.value = 400;
        }
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.5);
    } catch (err) {
        // Audio not supported
    }
}

    // Export for use in main app
    window.sequentialScanner = {
        init: initSequentialScanner,
        start: startSequentialCamera,
        stop: stopSequentialCamera
    };
})(); // Close IIFE
