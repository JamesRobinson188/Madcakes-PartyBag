import os, secrets, string, smtplib
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import stripe
from flask import current_app

def init_stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe

def send_email(subject, body, to_email=None):
    smtp_server, smtp_port = 'smtp.office365.com', 587
    sender_email = 'contact@jj-digital.uk'
    receiver_email = to_email or 'jandjdigitalsolutions@gmail.com'
    auth_user = current_app.config.get('EMAIL_USER')
    auth_password = current_app.config.get('EMAIL_PASS')

    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = sender_email, receiver_email, subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth_user, auth_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
    except Exception as e:
        current_app.logger.exception(f'Failed to send email: {e}')

def generate_order_id(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def money_to_pence(value): return int(round(float(value) * 100))
def pence_to_gbp(pence:int) -> str: return f"£{(Decimal(pence)/100):.2f}"
