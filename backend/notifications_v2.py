"""
Updated Notification Service with Firebase Admin SDK (V1 API)
Supports: Firebase Cloud Messaging + Twilio SMS
"""

import os
from typing import Optional, List
from datetime import datetime

# =====================
# Firebase Admin SDK (V1 API)
# =====================

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    
    # Initialize Firebase Admin SDK
    cred_path = os.path.join(os.path.dirname(__file__), "firebase-credentials.json")
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        FIREBASE_ENABLED = True
        print("✅ Firebase Admin SDK initialized successfully")
        print(f"   Project: {cred.project_id}")
    else:
        FIREBASE_ENABLED = False
        print("⚠️  firebase-credentials.json not found")
        print(f"   Looking for: {cred_path}")
        
except ImportError:
    FIREBASE_ENABLED = False
    print("⚠️  firebase-admin not installed")
    print("   Run: pip install firebase-admin")
except Exception as e:
    FIREBASE_ENABLED = False
    print(f"⚠️  Firebase initialization error: {e}")


# =====================
# Twilio SMS
# =====================

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️  Twilio not installed. Run: pip install twilio")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

twilio_client = None
if TWILIO_AVAILABLE and TWILIO_SID and TWILIO_TOKEN:
    try:
        twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
        print("✅ Twilio SMS initialized successfully")
        print(f"   From: {TWILIO_NUMBER}")
    except Exception as e:
        print(f"⚠️  Twilio initialization error: {e}")


# =====================
# Push Notification Functions (Firebase V1 API)
# =====================

def send_push_notification(token: str, title: str, body: str, data: dict = None) -> bool:
    """
    Send push notification using Firebase Admin SDK (V1 API)
    
    Args:
        token: FCM device token
        title: Notification title
        body: Notification body
        data: Optional data payload
    
    Returns:
        True if successful, False otherwise
    """
    if not FIREBASE_ENABLED:
        print("⚠️  Firebase not configured, skipping push notification")
        return False
    
    if not token:
        print("⚠️  No FCM token provided")
        return False
    
    try:
        # Create message using Firebase Admin SDK
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='notification_icon',
                    color='#4285F4'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        badge=1,
                        sound='default'
                    )
                )
            ),
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon='/icon-192x192.png',
                    badge='/badge-72x72.png'
                )
            )
        )
        
        # Send message
        response = messaging.send(message)
        print(f"✅ Push notification sent successfully: {response}")
        return True
        
    except messaging.UnregisteredError:
        print(f"⚠️  FCM token is invalid or unregistered: {token[:20]}...")
        return False
    except Exception as e:
        print(f"❌ Push notification error: {e}")
        return False


def send_push_to_multiple(tokens: List[str], title: str, body: str, data: dict = None) -> int:
    """
    Send push notification to multiple devices
    
    Args:
        tokens: List of FCM device tokens
        title: Notification title
        body: Notification body
        data: Optional data payload
    
    Returns:
        Number of successful sends
    """
    if not FIREBASE_ENABLED or not tokens:
        return 0
    
    try:
        # Create multicast message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=tokens,
            android=messaging.AndroidConfig(
                priority='high',
            ),
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon='/icon-192x192.png'
                )
            )
        )
        
        # Send to multiple devices
        response = messaging.send_multicast(message)
        
        # Log results
        print(f"✅ Multicast: {response.success_count}/{len(tokens)} sent successfully")
        if response.failure_count > 0:
            print(f"⚠️  {response.failure_count} failed")
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    print(f"   Token {idx}: {resp.exception}")
        
        return response.success_count
        
    except Exception as e:
        print(f"❌ Batch push error: {e}")
        return 0


# =====================
# SMS Functions (Twilio)
# =====================

def send_sms(to_number: str, message: str) -> bool:
    """
    Send SMS via Twilio
    
    Args:
        to_number: Phone number in E.164 format (e.g., +919876543210)
        message: SMS message text
    
    Returns:
        True if successful, False otherwise
    """
    if not twilio_client:
        print("⚠️  Twilio not configured, skipping SMS")
        return False
    
    if not to_number:
        print("⚠️  No phone number provided")
        return False
    
    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=TWILIO_NUMBER,
            to=to_number
        )
        
        print(f"✅ SMS sent to {to_number}: {msg.sid}")
        return True
        
    except Exception as e:
        print(f"❌ SMS error to {to_number}: {e}")
        return False


def send_sms_to_multiple(phone_numbers: List[str], message: str) -> int:
    """
    Send SMS to multiple recipients
    
    Args:
        phone_numbers: List of phone numbers
        message: SMS message text
    
    Returns:
        Number of successful sends
    """
    if not twilio_client or not phone_numbers:
        return 0
    
    success_count = 0
    for number in phone_numbers:
        if send_sms(number, message):
            success_count += 1
    
    return success_count


# =====================
# High-Level Notification Functions
# =====================

def notify_pass_approved(student_name: str, pass_id: int, fcm_token: str = None, phone: str = None):
    """Notify student when pass is approved"""
    title = "✅ Pass Approved"
    body = f"Your gate pass #{pass_id} has been approved. You can now generate your QR code."
    sms_msg = f"Campus GatePass: Your pass #{pass_id} has been approved. Login to download QR code."
    
    if fcm_token:
        send_push_notification(fcm_token, title, body, {"pass_id": str(pass_id), "type": "approval"})
    
    if phone:
        send_sms(phone, sms_msg)


def notify_pass_rejected(student_name: str, pass_id: int, fcm_token: str = None, phone: str = None):
    """Notify student when pass is rejected"""
    title = "❌ Pass Rejected"
    body = f"Your gate pass request #{pass_id} has been rejected. Please contact admin for details."
    sms_msg = f"Campus GatePass: Your pass #{pass_id} has been rejected. Contact admin for details."
    
    if fcm_token:
        send_push_notification(fcm_token, title, body, {"pass_id": str(pass_id), "type": "rejection"})
    
    if phone:
        send_sms(phone, sms_msg)


def notify_entry_scan(student_name: str, student_code: str, timestamp: str, 
                      parent_fcm: List[str] = None, parent_phones: List[str] = None):
    """Notify parents/guardians when student enters campus"""
    title = f"🟢 {student_name} Entered Campus"
    body = f"{student_name} ({student_code}) entered campus at {timestamp}"
    sms_msg = f"Campus Alert: {student_name} ({student_code}) entered campus at {timestamp}"
    
    # Notify parents via push
    if parent_fcm:
        send_push_to_multiple(parent_fcm, title, body, {"type": "entry", "student": student_code})
    
    # Notify parents via SMS
    if parent_phones:
        send_sms_to_multiple(parent_phones, sms_msg)


def notify_exit_scan(student_name: str, student_code: str, timestamp: str,
                     parent_fcm: List[str] = None, parent_phones: List[str] = None):
    """Notify parents/guardians when student exits campus"""
    title = f"🔴 {student_name} Exited Campus"
    body = f"{student_name} ({student_code}) exited campus at {timestamp}"
    sms_msg = f"Campus Alert: {student_name} ({student_code}) exited campus at {timestamp}"
    
    # Notify parents via push
    if parent_fcm:
        send_push_to_multiple(parent_fcm, title, body, {"type": "exit", "student": student_code})
    
    # Notify parents via SMS
    if parent_phones:
        send_sms_to_multiple(parent_phones, sms_msg)


def notify_pass_expiring(student_name: str, pass_id: int, hours_left: int,
                        fcm_token: str = None, phone: str = None):
    """Notify student when pass is about to expire"""
    title = "⏰ Pass Expiring Soon"
    body = f"Your gate pass #{pass_id} will expire in {hours_left} hours. Use it before expiry."
    sms_msg = f"Campus GatePass: Your pass #{pass_id} expires in {hours_left} hours."
    
    if fcm_token:
        send_push_notification(fcm_token, title, body, {"pass_id": str(pass_id), "type": "expiry_warning"})
    
    if phone:
        send_sms(phone, sms_msg)


def notify_admin_new_request(admin_fcm: List[str], student_name: str, pass_id: int):
    """Notify admins of new pass request"""
    title = "📥 New Pass Request"
    body = f"{student_name} submitted a new pass request #{pass_id}"
    
    if admin_fcm:
        send_push_to_multiple(admin_fcm, title, body, {"pass_id": str(pass_id), "type": "new_request"})


# =====================
# System Status
# =====================

def is_notification_enabled() -> bool:
    """Check if notification system is enabled"""
    return FIREBASE_ENABLED or bool(twilio_client)


def get_notification_status() -> dict:
    """Get status of notification services"""
    return {
        "firebase_enabled": FIREBASE_ENABLED,
        "sms_enabled": bool(twilio_client),
        "twilio_available": TWILIO_AVAILABLE,
        "overall_enabled": is_notification_enabled()
    }


# =====================
# Testing
# =====================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("Notification Service Status Check")
    print("="*50)
    
    status = get_notification_status()
    print(f"\n📊 Status:")
    print(f"   Firebase (Push):  {'✅ Enabled' if status['firebase_enabled'] else '❌ Disabled'}")
    print(f"   Twilio (SMS):     {'✅ Enabled' if status['sms_enabled'] else '❌ Disabled'}")
    print(f"   Overall:          {'✅ Ready' if status['overall_enabled'] else '❌ Not Ready'}")
    print("\n" + "="*50)
