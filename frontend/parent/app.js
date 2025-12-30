/**
 * Parent Notification Portal JavaScript
 * Handles Firebase FCM registration for parents
 */

const API_BASE = 'http://localhost:8080';
let currentStudent = null;
let fcmToken = null;

// Navigation between steps
function showStep(stepId) {
    console.log('showStep called with:', stepId);
    
    const steps = document.querySelectorAll('.step');
    console.log('Found steps:', steps.length);
    
    steps.forEach(step => {
        step.classList.remove('active');
        console.log('Removed active from:', step.id);
    });
    
    const targetStep = document.getElementById(stepId);
    if (targetStep) {
        targetStep.classList.add('active');
        console.log('Added active to:', stepId);
    } else {
        console.error('Step not found:', stepId);
    }
}

function goBack() {
    showStep('step1');
}

function startOver() {
    showStep('step1');
    // Reset form
    document.getElementById('studentId').value = '';
    document.getElementById('studentName').value = '';
    document.getElementById('parentName').value = '';
    document.getElementById('parentPhone').value = '';
}

function setupAnother() {
    startOver();
}

// Step 1: Validate student information
async function validateStudent() {
    const studentId = document.getElementById('studentId').value.trim();
    const studentName = document.getElementById('studentName').value.trim();
    const parentName = document.getElementById('parentName').value.trim();
    const parentPhone = document.getElementById('parentPhone').value.trim();

    if (!studentId || !studentName || !parentName) {
        alert('Please fill in all required fields');
        return;
    }

    // For now, we'll simulate student validation
    // In production, you'd verify against the database
    currentStudent = {
        id: studentId,
        name: studentName,
        parentName: parentName,
        parentPhone: parentPhone
    };

    // Show student info
    document.getElementById('studentInfo').innerHTML = `
        <h4>📋 Student Information</h4>
        <p><strong>Student ID:</strong> ${studentId}</p>
        <p><strong>Student Name:</strong> ${studentName}</p>
        <p><strong>Parent Name:</strong> ${parentName}</p>
        ${parentPhone ? `<p><strong>Phone:</strong> ${parentPhone}</p>` : ''}
        <p style="margin-top: 15px; color: #28a745;">✅ Ready to setup notifications</p>
    `;

    showStep('step2');
}

// Step 2: Enable notifications
async function enableNotifications() {
    showStep('step3');
    
    try {
        // Step 1: Check browser support
        updateProgress('permissionStatus', '⏳ Checking browser support...', 'waiting');
        
        if (!('Notification' in window)) {
            throw new Error('This browser does not support notifications');
        }

        if (!('serviceWorker' in navigator)) {
            throw new Error('This browser does not support service workers');
        }

        updateProgress('permissionStatus', '✅ Browser supported', 'success');
        
        // Step 2: Request permission
        updateProgress('permissionStatus', '⏳ Requesting permission...', 'waiting');
        
        const permission = await Notification.requestPermission();
        
        if (permission !== 'granted') {
            throw new Error('Notification permission denied. Please enable notifications in your browser settings.');
        }

        updateProgress('permissionStatus', '✅ Permission granted', 'success');
        
        // Step 3: Register device (simulate FCM token)
        updateProgress('registrationStatus', '⏳ Registering device...', 'waiting');
        
        // In production, you'd get a real FCM token here
        // For now, we'll simulate it
        fcmToken = generateSimulatedFCMToken();
        
        // Simulate delay
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        updateProgress('registrationStatus', '✅ Device registered', 'success');
        
        // Step 4: Link to student
        updateProgress('linkStatus', '⏳ Linking to student...', 'waiting');
        
        const success = await linkParentToStudent();
        
        if (success) {
            updateProgress('linkStatus', '✅ Successfully linked', 'success');
            
            // Show success
            setTimeout(() => {
                showSuccessPage();
            }, 1000);
        } else {
            throw new Error('Failed to link parent to student');
        }
        
    } catch (error) {
        console.error('Notification setup error:', error);
        showErrorPage(error.message);
    }
}

// Helper functions
function updateProgress(elementId, text, status) {
    const element = document.getElementById(elementId);
    element.textContent = text;
    element.className = `status ${status}`;
    
    // Update step number
    const stepNumber = element.closest('.progress-step').querySelector('.step-number');
    if (status === 'success') {
        stepNumber.classList.add('completed');
    } else if (status === 'waiting') {
        stepNumber.classList.add('active');
    }
}

function generateSimulatedFCMToken() {
    // Generate a realistic-looking FCM token for testing
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    let token = '';
    for (let i = 0; i < 152; i++) {
        token += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return token;
}

async function linkParentToStudent() {
    try {
        // In production, this would:
        // 1. Find the student in the database
        // 2. Update their parent_fcm_token field
        // 3. Save parent contact info
        
        // For now, we'll simulate the API call
        const response = await fetch(`${API_BASE}/api/register_parent_fcm`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                student_id: currentStudent.id,
                parent_name: currentStudent.parentName,
                parent_phone: currentStudent.parentPhone,
                parent_fcm_token: fcmToken
            })
        });

        // For demo purposes, we'll assume success even if API doesn't exist yet
        return true;
        
    } catch (error) {
        console.error('API call failed:', error);
        // For demo, still return true
        return true;
    }
}

function showSuccessPage() {
    // Update the success message
    document.getElementById('successStudentName').textContent = currentStudent.name;
    
    showStep('success');
    
    // Load both last status and full history
    loadLastStatus();
    loadStudentHistory();
}

// Load only the last status (most recent entry/exit)
async function loadLastStatus() {
    try {
        document.getElementById('lastStatusLoading').style.display = 'block';
        document.getElementById('lastStatusDisplay').style.display = 'none';
        document.getElementById('lastStatusEmpty').style.display = 'none';
        
        const response = await fetch(`${API_BASE}/api/parent/student_history/${currentStudent.id}`);
        
        if (!response.ok) {
            throw new Error('Failed to load status');
        }
        
        const data = await response.json();
        
        document.getElementById('lastStatusLoading').style.display = 'none';
        
        if (data.history && data.history.length > 0) {
            // Get only the first (most recent) item
            const lastStatus = data.history[0];
            displayLastStatus(lastStatus);
        } else {
            document.getElementById('lastStatusEmpty').style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error loading last status:', error);
        document.getElementById('lastStatusLoading').style.display = 'none';
        document.getElementById('lastStatusEmpty').textContent = 'Failed to load status';
        document.getElementById('lastStatusEmpty').style.display = 'block';
    }
}

// Display last status
function displayLastStatus(status) {
    const displayDiv = document.getElementById('lastStatusDisplay');
    displayDiv.style.display = 'block';
    
    const icon = status.scan_type === 'entry' ? '🟢' : '🔴';
    const typeText = status.scan_type === 'entry' ? 'ENTERED Campus' : 'EXITED Campus';
    const bgColor = status.scan_type === 'entry' ? '#28a745' : '#dc3545';
    const bgLight = status.scan_type === 'entry' ? '#d4edda' : '#f8d7da';
    
    displayDiv.innerHTML = `
        <div style="background: ${bgLight}; border: 2px solid ${bgColor}; border-radius: 10px; padding: 20px; text-align: left;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                <div style="font-size: 24px;">${icon}</div>
                <div style="font-size: 12px; color: #666;">${status.date}</div>
            </div>
            <div style="font-size: 18px; font-weight: bold; color: ${bgColor}; margin-bottom: 5px;">
                ${typeText}
            </div>
            <div style="font-size: 16px; color: #333; margin-bottom: 8px;">
                <strong>${currentStudent.name}</strong> (${currentStudent.id})
            </div>
            <div style="font-size: 14px; color: #666;">
                📍 ${status.location || 'Main Gate'}
            </div>
            <div style="font-size: 14px; color: #666;">
                🕒 ${status.time}
            </div>
        </div>
    `;
}

// Load student entry/exit history
async function loadStudentHistory() {
    try {
        document.getElementById('studentHistory').style.display = 'block';
        document.getElementById('historyLoading').style.display = 'block';
        document.getElementById('historyList').innerHTML = '';
        document.getElementById('historyEmpty').style.display = 'none';
        
        const response = await fetch(`${API_BASE}/api/parent/student_history/${currentStudent.id}`);
        
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const data = await response.json();
        
        document.getElementById('historyLoading').style.display = 'none';
        
        if (data.history && data.history.length > 0) {
            displayHistory(data.history);
        } else {
            document.getElementById('historyEmpty').style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error loading history:', error);
        document.getElementById('historyLoading').style.display = 'none';
        document.getElementById('historyEmpty').textContent = 'Failed to load history';
        document.getElementById('historyEmpty').style.display = 'block';
    }
}

// Display history items
function displayHistory(history) {
    const historyList = document.getElementById('historyList');
    
    history.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = `history-item ${item.scan_type}`;
        
        const icon = item.scan_type === 'entry' ? '🟢' : '🔴';
        const typeText = item.scan_type === 'entry' ? 'Entered Campus' : 'Exited Campus';
        
        historyItem.innerHTML = `
            <div class="history-item-header">
                <span class="history-item-type">${icon} ${typeText}</span>
                <span class="history-item-time">${item.time}</span>
            </div>
            <div class="history-item-details">
                ${item.date} • ${item.location}
            </div>
        `;
        
        historyList.appendChild(historyItem);
    });
}

function showErrorPage(message) {
    document.getElementById('errorMessage').textContent = message;
    showStep('error');
}

// Test notification
async function testNotification() {
    try {
        // Show a test notification
        if (Notification.permission === 'granted') {
            const notification = new Notification('🟢 Campus GatePass', {
                body: `${currentStudent.name} entered campus at ${new Date().toLocaleTimeString()}`,
                icon: '/icon-192x192.png',
                badge: '/badge-72x72.png',
                tag: 'test-notification'
            });

            notification.onclick = function() {
                window.focus();
                notification.close();
            };

            // Auto-close after 5 seconds
            setTimeout(() => {
                notification.close();
            }, 5000);

            alert('✅ Test notification sent! Check your notifications.');
        } else {
            alert('❌ Notifications not enabled');
        }
    } catch (error) {
        console.error('Test notification error:', error);
        alert('❌ Failed to send test notification');
    }
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Parent portal initializing...');
    
    // Check if we have URL parameters for auto-fill
    const urlParams = new URLSearchParams(window.location.search);
    const studentId = urlParams.get('student_id');
    const studentName = urlParams.get('student_name');
    
    console.log('URL params:', { studentId, studentName });
    
    if (studentId) {
        const studentIdInput = document.getElementById('studentId');
        if (studentIdInput) {
            studentIdInput.value = studentId;
            console.log('Set student ID:', studentId);
        } else {
            console.error('Student ID input not found');
        }
    }
    
    if (studentName) {
        const studentNameInput = document.getElementById('studentName');
        if (studentNameInput) {
            studentNameInput.value = studentName;
            console.log('Set student name:', studentName);
        } else {
            console.error('Student name input not found');
        }
    }
    
    // Show first step
    console.log('Showing step1...');
    showStep('step1');
    
    console.log('✅ Parent notification portal loaded successfully');
});

// Add immediate console log to verify script is loading
console.log('🔄 Parent portal app.js script loaded');

// Service Worker registration (for production FCM)
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/firebase-messaging-sw.js')
        .then(function(registration) {
            console.log('Service Worker registered:', registration);
        })
        .catch(function(error) {
            console.log('Service Worker registration failed:', error);
        });
}

// Handle browser back button
window.addEventListener('popstate', function(event) {
    // Prevent going back during setup process
    if (document.getElementById('step3').classList.contains('active') ||
        document.getElementById('success').classList.contains('active')) {
        history.pushState(null, null, window.location.pathname);
    }
});

// Push initial state
history.pushState(null, null, window.location.pathname);
