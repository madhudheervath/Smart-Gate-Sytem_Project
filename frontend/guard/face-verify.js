/**
 * Face Verification Module for Guard Portal
 * Automatic face capture and verification during QR scanning
 */

let faceVideo = null;
let faceCanvas = null;
let faceCanvasContext = null;
let faceStream = null;
let faceVerificationEnabled = true;

// Initialize face verification components
function initFaceVerification() {
    faceVideo = document.getElementById('faceVideo');
    faceCanvas = document.getElementById('faceCanvas');
    faceCanvasContext = faceCanvas.getContext('2d');
    
    // Listen to toggle
    document.getElementById('faceVerifyToggle')?.addEventListener('change', (e) => {
        faceVerificationEnabled = e.target.checked;
        updateFaceStatus(faceVerificationEnabled ? '✅ Enabled' : '⏸️ Disabled');
    });
}

// Start face camera
async function startFaceCamera() {
    try {
        faceStream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'user',  // Front camera for face
                width: { ideal: 1280 },
                height: { ideal: 720 }
            } 
        });
        faceVideo.srcObject = faceStream;
        faceVideo.setAttribute('playsinline', true);
        faceVideo.play();
        updateFaceStatus('🟢 Ready');
        return true;
    } catch (err) {
        console.error('Failed to start face camera:', err);
        updateFaceStatus('❌ Camera Error');
        return false;
    }
}

// Stop face camera
function stopFaceCamera() {
    if (faceStream) {
        faceStream.getTracks().forEach(track => track.stop());
        faceStream = null;
        faceVideo.srcObject = null;
        updateFaceStatus('⏸️ Standby');
    }
}

// Capture face snapshot
async function captureFaceSnapshot() {
    if (!faceVerificationEnabled) {
        return null;
    }
    
    if (!faceVideo || faceVideo.readyState !== faceVideo.HAVE_ENOUGH_DATA) {
        console.warn('Face video not ready');
        return null;
    }
    
    try {
        updateFaceStatus('📸 Capturing...');
        
        // Set canvas dimensions to video dimensions
        faceCanvas.width = faceVideo.videoWidth;
        faceCanvas.height = faceVideo.videoHeight;
        
        // Draw current frame
        faceCanvasContext.drawImage(faceVideo, 0, 0, faceCanvas.width, faceCanvas.height);
        
        // Convert to blob
        return new Promise((resolve) => {
            faceCanvas.toBlob((blob) => {
                if (blob) {
                    updateFaceStatus('🔍 Verifying...');
                    resolve(blob);
                } else {
                    updateFaceStatus('❌ Capture Failed');
                    resolve(null);
                }
            }, 'image/jpeg', 0.85);
        });
    } catch (err) {
        console.error('Face capture error:', err);
        updateFaceStatus('❌ Capture Error');
        return null;
    }
}

// Update face status display
function updateFaceStatus(status) {
    const statusDiv = document.getElementById('faceStatus');
    if (statusDiv) {
        statusDiv.textContent = status;
        
        // Update class based on status
        statusDiv.classList.remove('capturing', 'verifying', 'success', 'failed');
        
        if (status.includes('Capturing')) {
            statusDiv.classList.add('capturing');
        } else if (status.includes('Verifying')) {
            statusDiv.classList.add('verifying');
        } else if (status.includes('✅') || status.includes('Match')) {
            statusDiv.classList.add('success');
        } else if (status.includes('❌') || status.includes('No Match')) {
            statusDiv.classList.add('failed');
        }
    }
}

// Verify token with face verification
async function verifyTokenWithFace(token_str) {
    try {
        // Capture face first (if enabled)
        let faceBlob = null;
        if (faceVerificationEnabled) {
            console.log('Capturing face for verification...');
            faceBlob = await captureFaceSnapshot();
            console.log('Face captured:', faceBlob ? `${faceBlob.size} bytes` : 'null');
        }
        
        // Prepare form data
        const formData = new FormData();
        formData.append('token', token_str);
        if (faceBlob) {
            formData.append('face_image', faceBlob, 'face.jpg');
            console.log('Face image added to form data');
        } else {
            console.log('No face image to send');
        }
        
        // Send to backend
        console.log('Sending verification request with', faceBlob ? 'face image' : 'no face image');
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
            // Handle face verification result
            let faceInfo = '';
            if (data.face_verified !== undefined) {
                if (data.face_verified) {
                    const confidence = data.face_confidence || 0;
                    const confidenceClass = confidence > 85 ? 'high' : confidence > 70 ? 'medium' : 'low';
                    faceInfo = `
                        <div class="result-face-info verified">
                            <div>✅ <strong>Face Match Verified</strong></div>
                            <span class="face-match-badge ${confidenceClass}">
                                ${confidence.toFixed(1)}% Confidence
                            </span>
                            <div style="font-size:11px; margin-top:5px; opacity:0.7;">
                                Distance: ${data.face_distance?.toFixed(3) || 'N/A'}
                            </div>
                        </div>
                    `;
                    updateFaceStatus('✅ Match');
                } else if (data.face_verified === false) {
                    faceInfo = `
                        <div class="result-face-info not-verified">
                            <div>⚠️ <strong>Face Not Verified</strong></div>
                            <div style="font-size:12px; margin-top:4px;">
                                ${data.face_message || 'Face does not match registered photo'}
                            </div>
                        </div>
                    `;
                    updateFaceStatus('❌ No Match');
                }
            } else {
                // Face verification not performed
                faceInfo = faceVerificationEnabled ? 
                    '<div class="result-face-info not-verified"><div>ℹ️ Face verification not available</div></div>' : '';
                updateFaceStatus('⏸️ Disabled');
            }
            
            const studentInfo = data.student_name ? 
                `${data.student_name} (${data.student_code})` : 
                `Student #${data.student_id}`;
            
            showResult('success', '✅ GRANTED', 
                `Pass #${data.pass_id}<br>${studentInfo}${faceInfo}`);
            playSound('success');
            
            // Reload stats and scans
            setTimeout(() => {
                loadRecentScans();
                loadStats();
                updateFaceStatus('🟢 Ready');
            }, 2000);
        } else {
            throw new Error(data.detail || 'Verification failed');
        }
    } catch (err) {
        showResult('error', '❌ DENIED', err.message);
        playSound('error');
        updateFaceStatus('❌ Failed');
        
        setTimeout(() => {
            loadRecentScans();
            loadStats();
            updateFaceStatus('🟢 Ready');
        }, 2000);
    }
}

// Export functions for use in main app.js
window.faceVerify = {
    init: initFaceVerification,
    startCamera: startFaceCamera,
    stopCamera: stopFaceCamera,
    verifyWithFace: verifyTokenWithFace,
    updateStatus: updateFaceStatus
};
