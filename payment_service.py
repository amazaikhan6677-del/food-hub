"""
payment_service.py

A small abstraction layer around "payment processing" so a real gateway
(Stripe, PayFast, JazzCash API, Easypaisa API, etc.) can be plugged in
later without touching the rest of the application.

IMPORTANT / SECURITY:
- This module NEVER receives or stores a full card number or CVV.
- Only a masked/last-4 digit reference is accepted for demo display.
- Everything here runs in "Demo Payment Mode" and clearly labels
  transactions as simulated. No money moves and no real gateway is called.

To connect a real gateway:
1. Replace the body of `process_payment()` with a real API call
   (e.g. to Stripe's PaymentIntents API, or JazzCash/Easypaisa's
   merchant API) using their official SDK.
2. Keep the same return shape: {"status", "transaction_id"} so the rest
   of the app (app.py / database.py) doesn't need to change.
3. Store secrets (API keys) as environment variables, never in code.
"""

import uuid


DEMO_MODE = True  # This project ships in demo mode only.


def process_payment(method, amount, card_last4=None, mobile_number=None):
    """
    Simulates a payment transaction.

    method: 'cod' | 'card' | 'jazzcash' | 'easypaisa'
    amount: total order amount (float)
    card_last4: optional, last 4 digits ONLY (never a full card number)
    mobile_number: optional, for JazzCash/Easypaisa demo reference

    Returns: {"status": "Paid" | "Pending" | "Failed", "transaction_id": str|None}
    """
    method = (method or "cod").lower()
    transaction_id = "DEMO-" + uuid.uuid4().hex[:10].upper()

    if method == "cod":
        # Cash on Delivery — payment is collected later, in person.
        return {"status": "Pending", "transaction_id": None}

    if method in ("card", "jazzcash", "easypaisa"):
        if amount <= 0:
            return {"status": "Failed", "transaction_id": None}
        # --- DEMO PAYMENT MODE -------------------------------------------
        # A real integration would call the gateway's API here and verify
        # the response before marking the order as Paid.
        return {"status": "Paid", "transaction_id": transaction_id}

    return {"status": "Failed", "transaction_id": None}
