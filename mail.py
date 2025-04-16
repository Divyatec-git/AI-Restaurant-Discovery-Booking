import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email credentials
EMAIL = "abcds@gmail.com"
APP_PASSWORD = "qw12qwqw12121221"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Recipient details
TO_EMAIL = "abcdaert@gmail.com"
SUBJECT = "Test Email from Python"
BODY = "Hello, this is a test email sent using Python!"

# Create email message
msg = MIMEMultipart()
msg["From"] = EMAIL
msg["To"] = TO_EMAIL
msg["Subject"] = SUBJECT
msg.attach(MIMEText(BODY, "plain"))


# Send email
def send_email(to_email, subject, body):
    """Sends an email using the provided SMTP server and email credentials"""
    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Secure the connection
        server.login(EMAIL, APP_PASSWORD)
        server.sendmail(EMAIL, to_email, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


if __name__ == "__main__":
    send_email(TO_EMAIL, SUBJECT, BODY)
