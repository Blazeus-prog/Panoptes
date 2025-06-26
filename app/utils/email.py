import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "panoptes.notification@gmail.com"
SMTP_PASSWORD = "crdyotmhzgjjijob"

def send_alert_email(to_email: str, product_name: str, product_url: str, current_price: float):
    subject = f"Price Alert: {product_name}"
    body = f"""
    Hello,

    The price of the product you're tracking has crossed your alert threshold.

    📦 Product: {product_name}
    💰 Current Price: {current_price} DKK
    🔗 Link: {product_url}

    Best regards,
    Price Monitor
    """

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"[📧] Email sent to {to_email} for product '{product_name}'")
    except Exception as e:
        print(f"[❌] Failed to send email to {to_email}: {e}")