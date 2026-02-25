"""
Email Service — SendPulse integration for Inventro Bookstore.
Uses SendPulse SMTP API (OAuth2 token → send email).
"""

import os
import requests
from datetime import datetime


SENDPULSE_TOKEN_URL = "https://api.sendpulse.com/oauth/access_token"
SENDPULSE_SEND_URL = "https://api.sendpulse.com/smtp/emails"


def _get_config():
    """Get SendPulse configuration from environment."""
    client_id = os.environ.get('SENDPULSE_CLIENT_ID', '')
    client_secret = os.environ.get('SENDPULSE_CLIENT_SECRET', '')
    from_email = os.environ.get('SMTP_FROM_EMAIL', 'noreply@inventro.com')
    from_name = os.environ.get('SMTP_FROM_NAME', 'Inventro Bookstore')
    return client_id, client_secret, from_email, from_name


# Cache the token in module-level variable
_cached_token = None
_token_expiry = 0


def _get_access_token():
    """Get a SendPulse OAuth2 access token (cached)."""
    global _cached_token, _token_expiry
    import time

    # Return cached token if still valid
    if _cached_token and time.time() < _token_expiry:
        return _cached_token

    client_id, client_secret, _, _ = _get_config()
    if not client_id or not client_secret:
        return None

    try:
        response = requests.post(SENDPULSE_TOKEN_URL, json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }, timeout=10)

        data = response.json()
        if response.status_code == 200 and "access_token" in data:
            _cached_token = data["access_token"]
            _token_expiry = time.time() + data.get("expires_in", 3600) - 60  # refresh 1 min early
            return _cached_token
        else:
            print(f"[EMAIL] ❌ Token request failed: {data}")
            return None
    except Exception as e:
        print(f"[EMAIL] ❌ Token error: {e}")
        return None


def _send_email(to_email, to_name, subject, html_body):
    """
    Send an email via SendPulse SMTP API.
    Returns True on success, False on failure. Never raises.
    """
    client_id, _, from_email, from_name = _get_config()

    if not client_id:
        print("[EMAIL] SendPulse not configured — skipping email send.")
        return False

    token = _get_access_token()
    if not token:
        print("[EMAIL] ❌ Could not get SendPulse access token.")
        return False

    payload = {
        "email": {
            "html": html_body,
            "text": "",
            "subject": subject,
            "from": {"name": from_name, "email": from_email},
            "to": [{"name": to_name, "email": to_email}],
        }
    }

    try:
        response = requests.post(
            SENDPULSE_SEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        result = response.json()
        if response.status_code == 200 and result.get("result"):
            print(f"[EMAIL] ✅ Sent '{subject}' to {to_email}")
            return True
        else:
            print(f"[EMAIL] ❌ Failed: {result}")
            return False
    except Exception as e:
        print(f"[EMAIL] ❌ Error sending email: {e}")
        return False


# ─────────────────────────────────────────────────
#  Email Templates
# ─────────────────────────────────────────────────

def _base_template(content):
    """Wrap content in the Inventro-branded email shell."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f4f7; color: #1f2937; }}
            .email-wrapper {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
            .email-header {{ background: linear-gradient(135deg, #6366f1, #818cf8); padding: 32px 24px; text-align: center; }}
            .email-header h1 {{ color: #fff; margin: 0; font-size: 24px; font-weight: 700; }}
            .email-header p {{ color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 14px; }}
            .email-body {{ padding: 32px 24px; }}
            .email-footer {{ padding: 20px 24px; text-align: center; color: #9ca3af; font-size: 12px; border-top: 1px solid #e5e7eb; }}
            .btn {{ display: inline-block; padding: 12px 28px; background: #4f46e5; color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; }}
            .order-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
            .order-table th {{ text-align: left; padding: 10px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }}
            .order-table td {{ padding: 12px; border-bottom: 1px solid #f3f4f6; font-size: 14px; }}
            .total-row td {{ font-weight: 700; font-size: 16px; border-top: 2px solid #e5e7eb; padding-top: 16px; }}
            .highlight {{ color: #4f46e5; font-weight: 600; }}
            .badge {{ display: inline-block; padding: 4px 12px; background: #ecfdf5; color: #059669; border-radius: 20px; font-size: 12px; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div style="padding: 24px 16px;">
            <div class="email-wrapper">
                <div class="email-header">
                    <h1>📚 Inventro Bookstore</h1>
                    <p>Your destination for quality books</p>
                </div>
                <div class="email-body">
                    {content}
                </div>
                <div class="email-footer">
                    &copy; {datetime.utcnow().year} Inventro Bookstore. All rights reserved.<br>
                    <a href="#" style="color: #6b7280;">Unsubscribe</a> &middot; <a href="#" style="color: #6b7280;">Help</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# ─────────────────────────────────────────────────
#  Public Functions
# ─────────────────────────────────────────────────

def send_welcome_email(email, name):
    """Send a welcome email after customer registration."""
    first_name = name.split()[0] if name else "there"

    content = f"""
    <h2 style="margin-top:0;">Welcome to Inventro, {first_name}! 🎉</h2>
    <p style="color: #4b5563; line-height: 1.7;">
        Thank you for creating your account. You now have access to:
    </p>
    <ul style="color: #4b5563; line-height: 2;">
        <li>📖 Thousands of books at great prices</li>
        <li>🛒 Fast & easy checkout</li>
        <li>📦 Order tracking & history</li>
        <li>⭐ Rate & review your favourite reads</li>
    </ul>
    <div style="text-align: center; margin: 28px 0;">
        <a href="#" class="btn">Start Shopping →</a>
    </div>
    <p style="color: #9ca3af; font-size: 13px;">
        If you didn't create this account, you can safely ignore this email.
    </p>
    """

    return _send_email(email, name, "Welcome to Inventro Bookstore! 📚", _base_template(content))


def send_order_confirmation(email, name, order_id, tracking_number, items, total_amount):
    """
    Send an order confirmation email.
    items: list of dicts with 'title', 'quantity', 'price_at_order'
    """
    first_name = name.split()[0] if name else "Customer"

    # Build item rows
    item_rows = ""
    for item in items:
        qty = item.get('quantity', 1)
        price = float(item.get('price_at_order', item.get('price', 0)))
        subtotal = qty * price
        item_rows += f"""
        <tr>
            <td>{item.get('title', 'Book')}</td>
            <td style="text-align:center;">{qty}</td>
            <td style="text-align:right;">₹{price:.2f}</td>
            <td style="text-align:right;">₹{subtotal:.2f}</td>
        </tr>
        """

    content = f"""
    <h2 style="margin-top:0;">Order Confirmed! 🎉</h2>
    <p style="color: #4b5563; line-height: 1.7;">
        Hi {first_name}, thank you for your order. Here's a summary:
    </p>

    <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin: 16px 0;">
        <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div>
                <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Order ID</span><br>
                <span class="highlight">{order_id}</span>
            </div>
            <div>
                <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Tracking</span><br>
                <span class="highlight">{tracking_number}</span>
            </div>
            <div>
                <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Status</span><br>
                <span class="badge">Pending</span>
            </div>
        </div>
    </div>

    <table class="order-table">
        <thead>
            <tr>
                <th>Item</th>
                <th style="text-align:center;">Qty</th>
                <th style="text-align:right;">Price</th>
                <th style="text-align:right;">Total</th>
            </tr>
        </thead>
        <tbody>
            {item_rows}
            <tr class="total-row">
                <td colspan="3">Total</td>
                <td style="text-align:right; color: #4f46e5;">₹{float(total_amount):.2f}</td>
            </tr>
        </tbody>
    </table>

    <p style="color: #4b5563; line-height: 1.7; margin-top: 24px;">
        We'll notify you when your order ships. You can track your order anytime from your 
        <a href="#" style="color: #4f46e5;">dashboard</a>.
    </p>
    """

    return _send_email(
        email, name,
        f"Order Confirmed — {tracking_number} 📦",
        _base_template(content)
    )
