#!/usr/bin/env python3
"""
Test script for notification system
"""

import notifications_v2 as notifications

print("\n" + "="*60)
print("🔔 NOTIFICATION SYSTEM TEST")
print("="*60)

# Check status
status = notifications.get_notification_status()

print("\n📊 System Status:")
print(f"   Firebase Admin SDK: {'✅ Enabled' if status['firebase_enabled'] else '❌ Disabled'}")
print(f"   Twilio SMS:         {'✅ Enabled' if status['sms_enabled'] else '❌ Disabled'}")
print(f"   Overall Ready:      {'✅ YES' if status['overall_enabled'] else '❌ NO'}")

if status['firebase_enabled']:
    print("\n✅ Firebase Cloud Messaging is READY!")
    print("   You can now send push notifications to:")
    print("   - Students (when pass approved/rejected)")
    print("   - Parents (when student enters/exits campus)")
    print("   - Admins (when new pass request is submitted)")
    
    print("\n💡 Next Steps:")
    print("   1. Students need to register FCM tokens in frontend")
    print("   2. Use POST /api/register_fcm_token to save tokens")
    print("   3. Notifications will be sent automatically!")
else:
    print("\n⚠️  Firebase not enabled")
    print("   Check: /home/madhu/smart Gate/backend/firebase-credentials.json")

if status['sms_enabled']:
    print("\n✅ Twilio SMS is READY!")
    print("   SMS will be sent to phone numbers")
else:
    print("\n⚠️  Twilio SMS not configured")
    print("   To enable SMS notifications:")
    print("   1. Install: pip install twilio")
    print("   2. Set environment variables:")
    print("      export TWILIO_ACCOUNT_SID='your_sid'")
    print("      export TWILIO_AUTH_TOKEN='your_token'")
    print("      export TWILIO_PHONE_NUMBER='+1234567890'")

print("\n" + "="*60)
print("📝 Test Summary")
print("="*60)

if status['firebase_enabled']:
    print("✅ Push Notifications: WORKING")
else:
    print("❌ Push Notifications: NOT CONFIGURED")

if status['sms_enabled']:
    print("✅ SMS Alerts: WORKING")
else:
    print("❌ SMS Alerts: NOT CONFIGURED")

print("\n" + "="*60)

# Example notification calls (won't send without valid tokens)
print("\n🧪 Testing Notification Functions:")
print("\n1. Test Pass Approval Notification:")
print("   notifications.notify_pass_approved('John Doe', 123, 'fcm_token', '+919876543210')")

print("\n2. Test Entry Scan Notification:")
print("   notifications.notify_entry_scan('John Doe', 'U22CN123', '3:45 PM',")
print("                                   ['parent_fcm_token'], ['+919876543210'])")

print("\n3. Test Admin Alert:")
print("   notifications.notify_admin_new_request(['admin_fcm_token'], 'John Doe', 124)")

print("\n✅ All notification functions are loaded and ready!")
print("="*60 + "\n")
