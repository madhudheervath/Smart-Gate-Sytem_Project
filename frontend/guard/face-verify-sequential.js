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

function getGuardApiClient() {
    if (window.__guardFaceApiClient) {
        return window.__guardFaceApiClient;
    }

    if (window.CONFIG && typeof window.CONFIG.createApiClient === 'function') {
        window.__guardFaceApiClient = window.CONFIG.createApiClient();
        return window.__guardFaceApiClient;
    }

    return null;
}

async function guardApiFetch(path, options = {}) {
    if (typeof apiFetch === 'function') {
        return apiFetch(path, options);
    }

    const apiClient = getGuardApiClient();
    if (apiClient) {
        return apiClient.fetch(path, options);
    }

    return fetch(`${window.location.origin}${path}`, options);
}

function blobFromDataUrl(dataUrl) {
    const [header, data] = dataUrl.split(',');
    const mimeMatch = header.match(/data:(.*?);base64/);
    const mimeType = mimeMatch ? mimeMatch[1] : 'image/jpeg';
    const binary = atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return new Blob([bytes], { type: mimeType });
}

async function waitForVideoFrame(maxWaitMs = 2500) {
    const start = Date.now();

    while (Date.now() - start < maxWaitMs) {
        if (video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0 && video.videoHeight > 0) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    return false;
}

function getActiveVideoTrack() {
    if (!video || !video.srcObject || typeof video.srcObject.getVideoTracks !== 'function') {
        return null;
    }

    const [track] = video.srcObject.getVideoTracks();
    return track || null;
}

async function captureFrameViaImageCapture() {
    const track = getActiveVideoTrack();
    if (!track || typeof ImageCapture === 'undefined') {
        return null;
    }

    try {
        const imageCapture = new ImageCapture(track);
        const frame = await imageCapture.grabFrame();
        const tempCanvas = document.createElement('canvas');
        const tempContext = tempCanvas.getContext('2d');
        if (!tempContext) {
            return null;
        }

        tempCanvas.width = frame.width;
        tempCanvas.height = frame.height;
        tempContext.drawImage(frame, 0, 0, frame.width, frame.height);

        const blob = await new Promise((resolve) => {
            tempCanvas.toBlob((result) => resolve(result), 'image/jpeg', 0.84);
        });

        if (blob) {
            return blob;
        }

        const fallbackDataUrl = tempCanvas.toDataURL('image/jpeg', 0.84);
        if (!fallbackDataUrl || fallbackDataUrl === 'data:,') {
            return null;
        }

        return blobFromDataUrl(fallbackDataUrl);
    } catch (error) {
        console.warn('ImageCapture frame grab failed', error);
        return null;
    }
}

async function captureCurrentFrameBlob() {
    const ready = await waitForVideoFrame(4000);
    if (!ready) {
        throw new Error('Camera frame is not ready yet. Please keep the camera open and try again.');
    }

    for (let attempt = 1; attempt <= 3; attempt += 1) {
        const directBlob = await captureFrameViaImageCapture();
        if (directBlob && directBlob.size > 0) {
            return directBlob;
        }

        const tempCanvas = document.createElement('canvas');
        const tempContext = tempCanvas.getContext('2d');
        if (!tempContext) {
            throw new Error('Unable to prepare the captured frame for verification.');
        }

        tempCanvas.width = video.videoWidth;
        tempCanvas.height = video.videoHeight;
        tempContext.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

        const blob = await new Promise((resolve) => {
            tempCanvas.toBlob((result) => resolve(result), 'image/jpeg', 0.84);
        });

        if (blob && blob.size > 0) {
            return blob;
        }

        const fallbackDataUrl = tempCanvas.toDataURL('image/jpeg', 0.84);
        if (fallbackDataUrl && fallbackDataUrl !== 'data:,') {
            const fallbackBlob = blobFromDataUrl(fallbackDataUrl);
            if (fallbackBlob.size > 0) {
                return fallbackBlob;
            }
        }

        await new Promise(resolve => setTimeout(resolve, 250));
    }

    throw new Error('Failed to capture a usable face image from the camera stream. Keep the camera running, hold still, and try again.');
}

async function parseApiResponse(response) {
    const rawText = await response.text();
    if (!rawText) {
        return {};
    }

    try {
        return JSON.parse(rawText);
    } catch {
        return { detail: rawText };
    }
}

function formatVerificationError(detail) {
    const raw = String(detail || 'Verification failed').trim();
    const normalized = raw.toLowerCase();

    if (normalized.includes('expired: past-expiry')) {
        return 'This pass has expired. Ask the student to generate a fresh pass and scan it again.';
    }
    if (normalized.includes('replay: already-used')) {
        return 'This QR code has already been used.';
    }
    if (normalized.includes('invalid: face-not-detected')) {
        return 'No face was detected in the captured image. Ask the student to face the camera in good light and try again.';
    }
    if (normalized.includes('invalid: face-registration-outdated')) {
        return 'This student must re-register their face using the updated verification model before face verification can be used.';
    }
    if (normalized.includes('invalid: face-mismatch')) {
        return 'Face verification failed. The captured face does not match the registered face.';
    }
    if (normalized.includes('invalid: face-invalid-image')) {
        return 'The captured image was not valid for face verification. Keep the camera steady and try again.';
    }
    if (normalized.includes('invalid: malformed')) {
        return 'The scanned QR code is invalid.';
    }
    if (normalized.includes('invalid: sig-mismatch')) {
        return 'The scanned QR code signature is invalid.';
    }
    if (normalized.includes('not-approved:')) {
        return 'This pass is not approved for use yet.';
    }
    if (normalized.includes('invalid: face-service-unavailable')) {
        return 'Face verification is temporarily unavailable on the server. Try again in a moment.';
    }
    if (normalized.includes('invalid: face-verification-error')) {
        return 'The server could not complete face verification. Try again with a clear face image.';
    }

    return raw;
}

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
        let stream = null;
        const videoPresets = [
            {
                video: {
                    facingMode: { ideal: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            },
            {
                video: {
                    facingMode: { ideal: 'user' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            },
            {
                video: true
            }
        ];

        for (const constraints of videoPresets) {
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraints);
                break;
            } catch (error) {
                console.warn('Camera preset failed', constraints, error);
            }
        }

        if (!stream) {
            throw new Error('Unable to access any camera on this device');
        }

        video.srcObject = stream;
        video.setAttribute('playsinline', true);
        video.setAttribute('muted', 'true');
        video.playsInline = true;
        video.muted = true;
        video.autoplay = true;

        if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
            await new Promise((resolve) => {
                const onLoadedMetadata = () => {
                    video.removeEventListener('loadedmetadata', onLoadedMetadata);
                    resolve();
                };
                video.addEventListener('loadedmetadata', onLoadedMetadata, { once: true });
            });
        }

        await video.play();
        hideResult();
        
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
        updateStatus('📸 Hold still - capturing face...', 'face-capturing');

        const faceBlob = await captureCurrentFrameBlob();
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
        
        const res = await guardApiFetch('/verify', {
            method: 'POST',
            timeoutMs: 120000,
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await parseApiResponse(res);
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
            throw new Error(formatVerificationError(data.detail || data.message || 'Verification failed'));
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
        
        const res = await guardApiFetch('/verify', {
            method: 'POST',
            timeoutMs: 120000,
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await parseApiResponse(res);
        
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
            throw new Error(formatVerificationError(data.detail || data.message || 'QR verification failed'));
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
