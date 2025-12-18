# test_real_push.py
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.notifications.services.fcm_service import FCMService
from apps.authentication.models import User
from apps.notifications.models import FCMDevice

def send_test(token):
    print(f"Sending test to token: {token[:20]}...")
    
    # 1. Create a dummy user context (optional, but good for DB record)
    user = User.objects.first()
    if not user:
        print("No users found in DB, creating temporary user for test context")
        user = User.objects.create(email="temp_test@example.com", clerk_user_id="temp_test_123")
    
    # 2. Find existing device or create new
    device = FCMDevice.objects.filter(fcm_token=token).first()
    if device:
        print(f"Token belongs to user: {device.user.email}")
        user = device.user
    else:
        device = FCMDevice.objects.create(user=user, fcm_token=token, device_type='web')
    
    # 3. Send
    success = FCMService.send_to_user(
        user=user,
        title="Works! 🚀",
        body="This notification came from your Django Backend!",
        data={"type": "test_message"}
    )
    
    if success:
        print("\n✅ SUCCESS: Message sent to Firebase!")
        print("Check your device/browser now.")
    else:
        print("\n❌ FAILED: Message could not be sent.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_real_push.py <YOUR_FCM_TOKEN>")
    else:
        send_test(sys.argv[1])