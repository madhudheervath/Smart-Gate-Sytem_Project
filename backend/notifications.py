"""
Notification Service for Smart Gate Pass System
Supports: Firebase Cloud Messaging (FCM) and Twilio SMS
"""

import requests
import os
from typing import Optional, List
from datetime import datetime
from settings import settings

# =====================
# Firebase Cloud Messaging (FCM)
# =====================

FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
FCM_URL = "https://fcm.googleapis.com/fcm/send"

def send_push_notification(token: str, title: str, body: str, data: dict = None) -> bool:
    """
    Send push notification via Firebase Cloud Messaging
    
    Args:
        token: FCM device token
        title: Notification title
        body: Notification body
        data: Optional data payload
    
    Returns:
        True if successful, False otherwise
    """
    if not FCM_SERVER_KEY:
        print("⚠️  FCM_SERVER_KEY not configured, skipping push notification")
        return False
    
    if not token:
        print("⚠️  No FCM token provided")
        return False
    
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "notification": {
            "title": title,
            "body": body,
            "icon": "/static/icon-192x192.png",
            "badge": "/static/badge-72x72.png",
            "click_action": "https://yoursite.com"
        },
        "to": token
    }
    
    if data:
        payload["data"] = data
    
    try:
        res = requests.post(FCM_URL, json=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            print(f"✅ Push notification sent: {title}")
            return True
        else:
            print(f"❌ FCM error {res.status_code}: {res.text}")
            return False
            
    except Exception as e:
        print(f"❌ Push notification error: {e}")
        return False


def send_push_to_multiple(tokens: List[str], title: str, body: str, data: dict = None) -> int:
    """
    Send push notification to multiple devices
    
    Returns:
        Number of successful sends
    """
    if not FCM_SERVER_KEY or not tokens:
        return 0
    
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "notification": {
            "title": title,
            "body": body,
            "icon": "/static/icon-192x192.png"
        },
        "registration_ids": tokens  # Multiple tokens
    }
    
    if data:
        payload["data"] = data
    
    try:
        res = requests.post(FCM_URL, json=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            result = res.json()
            success_count = result.get("success", 0)
            print(f"✅ Push sent to {success_count}/{len(tokens)} devices")
            return success_count
        else:
            print(f"❌ FCM batch error {res.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ Batch push error: {e}")
        return 0


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
    except Exception as e:
        print(f"⚠️  Twilio initialization error: {e}")


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
        send_push_notification(fcm_token, title, body, {"pass_id": pass_id, "type": "approval"})
    
    if phone:
        send_sms(phone, sms_msg)


def notify_pass_rejected(student_name: str, pass_id: int, fcm_token: str = None, phone: str = None):
    """Notify student when pass is rejected"""
    title = "❌ Pass Rejected"
    body = f"Your gate pass request #{pass_id} has been rejected. Please contact admin for details."
    sms_msg = f"Campus GatePass: Your pass #{pass_id} has been rejected. Contact admin for details."
    
    if fcm_token:
        send_push_notification(fcm_token, title, body, {"pass_id": pass_id, "type": "rejection"})
    
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
        send_push_notification(fcm_token, title, body, {"pass_id": pass_id, "type": "expiry_warning"})
    
    if phone:
        send_sms(phone, sms_msg)


def notify_admin_new_request(admin_fcm: List[str], student_name: str, pass_id: int):
    """Notify admins of new pass request"""
    title = "📥 New Pass Request"
    body = f"{student_name} submitted a new pass request #{pass_id}"
    
    if admin_fcm:
        send_push_to_multiple(admin_fcm, title, body, {"pass_id": pass_id, "type": "new_request"})


# =====================
# Notification Preferences
# =====================

NOTIFICATION_ENABLED = True

def is_notification_enabled() -> bool:
    """Check if notification system is enabled"""
    return NOTIFICATION_ENABLED and (bool(FCM_SERVER_KEY) or bool(twilio_client))


def get_notification_status() -> dict:
    """Get status of notification services"""
    return {
        "fcm_enabled": bool(FCM_SERVER_KEY),
        "sms_enabled": bool(twilio_client),
        "twilio_available": TWILIO_AVAILABLE,
        "overall_enabled": is_notification_enabled()
    }


if __name__ == "__main__":
    # Test notification system
    print("Notification Service Status:")
    print(get_notification_status())
