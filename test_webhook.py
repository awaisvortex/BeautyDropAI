
import os
import django
import stripe
import time
import requests
import json
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
webhook_secret = settings.STRIPE_CONNECT_WEBHOOK_SECRET

print(f"Using Webhook Secret: {webhook_secret[:20]}...")

# Payload for payment_intent.succeeded
payload_data = {
  "id": "evt_test_webhook_123",
  "object": "event",
  "api_version": "2025-08-27.basil",
  "created": int(time.time()),
  "type": "payment_intent.succeeded",
  "data": {
    "object": {
      "id": "pi_3SmG4vDKMGdQKiWa2cghrb9F",
      "object": "payment_intent",
      "amount": 1000,
      "currency": "usd",
      "status": "succeeded",
      "metadata": {
        "booking_id": "f746bb3b-237c-4f0d-aff4-ab7b281bdb95",
        "type": "advance_deposit"
      }
    }
  }
}

payload = json.dumps(payload_data)
timestamp = int(time.time())

import hmac
import hashlib

# Generate signature manually
signed_payload = f"{timestamp}.{payload}"
signature = hmac.new(
    key=webhook_secret.encode('utf-8'),
    msg=signed_payload.encode('utf-8'),
    digestmod=hashlib.sha256
).hexdigest()

signature = f"t={timestamp},v1={signature}"

headers = {
    'Content-Type': 'application/json',
    'Stripe-Signature': signature,
}

print(f"Sending webhook to http://localhost:8000/api/payments/webhooks/stripe/")
response = requests.post(
    'http://localhost:8000/api/payments/webhooks/stripe/',
    data=payload,
    headers=headers
)

print(f"Response Status: {response.status_code}")
print(f"Response Body: {response.text}")
