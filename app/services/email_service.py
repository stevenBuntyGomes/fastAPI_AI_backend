import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")  # your Gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # your 16-character Gmail App Password (no spaces)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))


async def send_email_verification_code(to_email: str, code: str):
    subject = "🛡️ Your Verification Code"
    body = f"Your verification code is: {code}\n\nThis code will expire in 10 minutes."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
            print("✅ Email sent successfully to", to_email)
    except Exception as e:
        print("❌ Failed to send email:", e)
        raise
