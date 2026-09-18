"""
Email and Notification Delivery Service for KPRIET Smart Food Court.

Enforces:
1. Standards-compliant SMTP delivery with TLS/SSL encryption.
2. Graceful fallback and clear environment variable documentation when SMTP is not configured.
3. Strict confidentiality: NEVER logs passwords, password reset tokens, or sensitive credentials.
4. In-memory test hooks for automated validation without disk or log exposure.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

logger = logging.getLogger("food_court.services.email")


class EmailService:
    """Manages transactional emails (password reset, security notifications, order tickets)."""

    # In-memory store for automated testing/development only. Never logs tokens or writes to disk.
    _last_dev_dispatch: Optional[Dict[str, Any]] = None

    @classmethod
    def get_smtp_config(cls) -> Dict[str, Any]:
        """Reads and normalizes SMTP configuration from environment variables."""
        default_frontend = "https://college-food-court-frontend.onrender.com"
        frontend_url = (os.getenv("FRONTEND_URL") or os.getenv("APP_URL") or default_frontend).strip().rstrip("/")
        return {
            "host": (os.getenv("SMTP_HOST") or "").strip(),
            "port": int(os.getenv("SMTP_PORT") or 587),
            "user": (os.getenv("SMTP_USER") or "").strip(),
            "password": (os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD") or "").strip(),
            "use_tls": str(os.getenv("SMTP_USE_TLS", "1")).lower() in ("1", "true", "yes"),
            "sender": (os.getenv("MAIL_DEFAULT_SENDER") or "KPRIET Smart Food Court <noreply@kpriet.ac.in>").strip(),
            "app_url": frontend_url,
            "frontend_url": frontend_url,
        }

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """Returns True only if a real SMTP host and credentials are provided."""
        cfg = cls.get_smtp_config()
        if not cfg["host"]:
            return False
        # Treat typical placeholders as unconfigured
        if "your_smtp" in cfg["host"] or "smtp.example.com" in cfg["host"]:
            return False
        return True

    @classmethod
    def send_password_reset_email(cls, to_email: str, user_name: str, reset_url: str, raw_token: str = "") -> bool:
        """
        Dispatches password reset instructions containing the secure reset URL.
        Never logs the reset token or password.
        """
        cfg = cls.get_smtp_config()
        subject = "Reset Your KPRIET Smart Food Court Password"

        plaintext_body = (
            f"Hello {user_name},\n\n"
            f"We received a request to reset the password for your KPRIET Smart Food Court account.\n\n"
            f"Please click the link below or copy and paste it into your browser to choose a new password:\n"
            f"{reset_url}\n\n"
            f"This link is valid for 15 minutes and can only be used once.\n"
            f"If you did not request this password reset, please ignore this email. Your password will remain unchanged.\n\n"
            f"— The KPRIET Campus Dining & Food Court Team\n"
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #071638, #113377); padding: 32px 24px; text-align: center; color: #ffffff; }}
            .header h1 {{ margin: 0; font-size: 20px; font-weight: 800; letter-spacing: 0.5px; }}
            .header p {{ margin: 6px 0 0 0; font-size: 12px; color: #94a3b8; }}
            .content {{ padding: 32px 24px; }}
            .content p {{ font-size: 14px; line-height: 1.6; color: #334155; margin: 0 0 16px 0; }}
            .btn-container {{ text-align: center; margin: 28px 0; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #0d9488, #06b6d4); color: #ffffff !important; font-weight: 700; font-size: 14px; text-decoration: none; padding: 14px 28px; border-radius: 12px; box-shadow: 0 4px 14px rgba(13, 148, 136, 0.25); }}
            .link-box {{ background: #f1f5f9; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 12px; word-break: break-all; color: #0f766e; margin-bottom: 20px; }}
            .footer {{ background: #f8fafc; padding: 20px 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>KPRIET Smart Food Court</h1>
              <p>Campus Dining & Pre-Order System</p>
            </div>
            <div class="content">
              <p>Hello <strong>{user_name}</strong>,</p>
              <p>We received a request to reset the password associated with your food court account.</p>
              <div class="btn-container">
                <a href="{reset_url}" class="btn" target="_blank">Reset My Password</a>
              </div>
              <p>If the button doesn't work, copy and paste the link below into your browser:</p>
              <div class="link-box">{reset_url}</div>
              <p style="font-size: 12px; color: #64748b;">This link will expire in <strong>15 minutes</strong> and can only be used once. If you did not request this change, you can safely ignore this email.</p>
            </div>
            <div class="footer">
              <p>© KPR Institute of Engineering and Technology. All rights reserved.</p>
              <p>This is an automated system email. Please do not reply directly.</p>
            </div>
          </div>
        </body>
        </html>
        """

        # In-memory test hook for automated test suites (never logged)
        cls._last_dev_dispatch = {
            "to": to_email,
            "user_name": user_name,
            "reset_url": reset_url,
            "raw_token": raw_token
        }

        if not cls.is_smtp_configured():
            logger.info(
                "SMTP not configured. Generated password reset request for %s. "
                "To deliver live emails, configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in .env.",
                to_email
            )
            return True

        # Send via SMTP
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = cfg["sender"]
            msg["To"] = to_email

            part1 = MIMEText(plaintext_body, "plain", "utf-8")
            part2 = MIMEText(html_body, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
                if cfg["use_tls"]:
                    server.starttls()
                if cfg["user"] and cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["sender"], [to_email], msg.as_string())

            logger.info("Password reset email sent successfully to %s", to_email)
            return True
        except Exception as e:
            logger.error("Failed to deliver password reset email to %s: %s", to_email, type(e).__name__)
            return False

    @classmethod
    def send_password_changed_notification(cls, to_email: str, user_name: str) -> bool:
        """Sends security confirmation email when password has been successfully reset."""
        cfg = cls.get_smtp_config()
        if not cls.is_smtp_configured():
            return True

        subject = "Security Notice: Your Password Has Been Changed"
        plaintext_body = (
            f"Hello {user_name},\n\n"
            f"The password for your KPRIET Smart Food Court account was recently reset.\n\n"
            f"If you made this change, you can disregard this message.\n"
            f"If you did NOT change your password, please contact the campus food court administrator immediately.\n\n"
            f"— The KPRIET Campus Dining Team\n"
        )

        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = cfg["sender"]
            msg["To"] = to_email
            msg.attach(MIMEText(plaintext_body, "plain", "utf-8"))

            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
                if cfg["use_tls"]:
                    server.starttls()
                if cfg["user"] and cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["sender"], [to_email], msg.as_string())
            return True
        except Exception as e:
            logger.error("Failed to send password changed confirmation to %s: %s", to_email, type(e).__name__)
            return False

    @classmethod
    def get_last_reset_for_testing(cls) -> Optional[Dict[str, Any]]:
        """Test helper to inspect dispatched reset metadata without logging tokens."""
        return cls._last_dev_dispatch

    @classmethod
    def clear_testing_state(cls):
        """Clears test hook memory."""
        cls._last_dev_dispatch = None
