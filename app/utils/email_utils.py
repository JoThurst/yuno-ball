import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string
import logging

# HTML template for password reset emails
PASSWORD_RESET_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .button {
            display: inline-block;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .footer {
            margin-top: 30px;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Request</h2>
        <p>Hello {{ username }},</p>
        <p>We received a request to reset your password. If you didn't make this request, you can safely ignore this email.</p>
        <p>To reset your password, click the button below:</p>
        <a href="{{ reset_url }}" class="button">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p>{{ reset_url }}</p>
        <div class="footer">
            <p>This link will expire in 1 hour for security reasons.</p>
            <p>If you need assistance, please contact support.</p>
        </div>
    </div>
</body>
</html>
"""

# HTML template for email verification
EMAIL_VERIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .button {
            display: inline-block;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .footer {
            margin-top: 30px;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Verify Your Email Address</h2>
        <p>Hello {{ username }},</p>
        <p>Thank you for registering! Please click the button below to verify your email address:</p>
        <a href="{{ verification_url }}" class="button">Verify Email</a>
        <p>Or copy and paste this link into your browser:</p>
        <p>{{ verification_url }}</p>
        <div class="footer">
            <p>This link will expire in 24 hours for security reasons.</p>
            <p>If you need assistance, please contact support.</p>
        </div>
    </div>
</body>
</html>
"""

def send_email(to_email, subject, html_content):
    """
    Send an email using SMTP.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML content of the email
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get email configuration from app config
        smtp_server = current_app.config['SMTP_SERVER']
        smtp_port = current_app.config['SMTP_PORT']
        smtp_username = current_app.config['SMTP_USERNAME']
        smtp_password = current_app.config['SMTP_PASSWORD']
        from_email = current_app.config['FROM_EMAIL']
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            
        logging.info(f"Password reset email sent to {to_email}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending email: {str(e)}")
        return False

def send_password_reset_email(email, username, reset_token):
    """
    Send password reset email to user.
    
    Args:
        email (str): User's email address
        username (str): User's username
        reset_token (str): Password reset token
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Generate reset URL
        reset_url = f"{current_app.config['BASE_URL']}/reset-password?token={reset_token}"
        
        # Render email template
        html_content = render_template_string(
            PASSWORD_RESET_TEMPLATE,
            username=username,
            reset_url=reset_url
        )
        
        # Send email
        return send_email(
            to_email=email,
            subject="Password Reset Request",
            html_content=html_content
        )
        
    except Exception as e:
        logging.error(f"Error sending password reset email: {str(e)}")
        return False

def send_verification_email(user):
    """
    Send email verification link to user.
    
    Args:
        user: User object containing email, username, and methods to generate verification token
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Generate verification token
        verification_token = user.generate_reset_token(email=user.email)  # Pass email parameter
        
        # Generate verification URL
        verification_url = f"{current_app.config['BASE_URL']}/verify-email?token={verification_token}"
        
        # Render email template
        html_content = render_template_string(
            EMAIL_VERIFICATION_TEMPLATE,
            username=user.username,
            verification_url=verification_url
        )
        
        # Send email
        return send_email(
            to_email=user.email,
            subject="Verify Your Email Address",
            html_content=html_content
        )
        
    except Exception as e:
        logging.error(f"Error sending verification email: {str(e)}")
        return False 