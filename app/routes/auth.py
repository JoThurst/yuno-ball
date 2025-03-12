from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from app.models.user import User
from app.utils.email_utils import send_password_reset_email, send_verification_email
from app.utils.rate_limiter import check_rate_limit, increment_rate_limit
from app.utils.session import get_user_sessions, delete_session
import re

# Initialize Blueprint and CSRF protection
auth = Blueprint('auth', __name__)
csrf = CSRFProtect()

def init_app(app):
    csrf.init_app(app)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check rate limit for registration attempts
        if not check_rate_limit(f"register:{request.remote_addr}", 5, 3600):
            flash('Too many registration attempts. Please try again later.', 'danger')
            return render_template('auth/register.html')

        # Validate input
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        # Password complexity check
        if not (len(password) >= 8 and 
                re.search(r'[A-Z]', password) and 
                re.search(r'[a-z]', password) and 
                re.search(r'\d', password) and 
                re.search(r'[!@#$%^&*(),.?":{}|<>]', password)):
            flash('Password does not meet complexity requirements.', 'danger')
            return render_template('auth/register.html')

        # Check if username or email already exists
        if User.get_by_username(username):
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')
        
        if User.get_by_email(email):
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')

        # Create new user
        try:
            hashed_password = generate_password_hash(password)
            user = User.create(username, email, hashed_password)
            if user:
                flash('Registration successful! Please check your email to verify your account.', 'success')
                return redirect(url_for('auth.login'))
        except Exception as e:
            current_app.logger.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration.', 'danger')

        increment_rate_limit(f"register:{request.remote_addr}")
        return render_template('auth/register.html')

    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        # Check rate limit for login attempts
        if not check_rate_limit(f"login:{request.remote_addr}", 5, 300):
            flash('Too many login attempts. Please try again later.', 'danger')
            return render_template('auth/login.html')

        user = User.get_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Please verify your email before logging in.', 'warning')
                return render_template('auth/login.html')

            login_user(user, remember=remember)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return render_template('auth/login.html')

        increment_rate_limit(f"login:{request.remote_addr}")
        flash('Invalid username or password.', 'danger')
        return render_template('auth/login.html')

    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return render_template('auth/login.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Check rate limit for password reset attempts
        if not check_rate_limit(f"reset:{request.remote_addr}", 3, 3600):
            flash('Too many password reset attempts. Please try again later.', 'danger')
            return render_template('auth/forgot_password.html')

        user = User.get_by_email(email)
        if user:
            try:
                token = user.generate_reset_token(email=email)
                send_password_reset_email(user.email, user.username, token)
                flash('Password reset instructions have been sent.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                current_app.logger.error(f"Password reset error: {str(e)}")
                flash('An error occurred while sending reset instructions.', 'danger')
        else:
            # Use same message to prevent email enumeration
            flash('Password reset instructions have been sent if the email exists.', 'info')

        increment_rate_limit(f"reset:{request.remote_addr}")
        return render_template('auth/forgot_password.html')

    return render_template('auth/forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        # Password complexity check
        if not (len(password) >= 8 and 
                re.search(r'[A-Z]', password) and 
                re.search(r'[a-z]', password) and 
                re.search(r'\d', password) and 
                re.search(r'[!@#$%^&*(),.?":{}|<>]', password)):
            flash('Password does not meet complexity requirements.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        try:
            user = User.verify_reset_token(token)
            if user:
                hashed_password = generate_password_hash(password)
                user.update_password(hashed_password)
                flash('Your password has been reset successfully.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Invalid or expired reset token.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Password reset error: {str(e)}")
            flash('An error occurred while resetting your password.', 'danger')

        return render_template('auth/reset_password.html', token=token)

    return render_template('auth/reset_password.html', token=token)

@auth.route('/settings')
@login_required
def settings():
    active_sessions = get_user_sessions(current_user.id)
    return render_template('auth/settings.html', active_sessions=active_sessions)

@auth.route('/settings/update-profile', methods=['POST'])
@login_required
def update_profile():
    email = request.form.get('email')
    
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.settings'))
    
    # Check if email is already in use by another user
    existing_user = User.get_by_email(email)
    if existing_user and existing_user.id != current_user.id:
        flash('Email is already in use.', 'danger')
        return redirect(url_for('auth.settings'))
    
    try:
        # If email has changed, require reverification
        if email != current_user.email:
            current_user.update_email(email)
            send_verification_email(current_user)
            flash('Email updated. Please verify your new email address.', 'success')
        else:
            flash('Profile updated successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Profile update error: {str(e)}")
        flash('An error occurred while updating your profile.', 'danger')
    
    return redirect(url_for('auth.settings'))

@auth.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')
    
    if not all([current_password, new_password, confirm_new_password]):
        flash('All password fields are required.', 'danger')
        return render_template('auth/settings.html')
    
    if new_password != confirm_new_password:
        flash('New passwords do not match.', 'danger')
        return render_template('auth/settings.html')
    
    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'danger')
        return render_template('auth/settings.html')
    
    # Password complexity check
    if not (len(new_password) >= 8 and 
            re.search(r'[A-Z]', new_password) and 
            re.search(r'[a-z]', new_password) and 
            re.search(r'\d', new_password) and 
            re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password)):
        flash('New password does not meet complexity requirements.', 'danger')
        return render_template('auth/settings.html')
    
    try:
        hashed_password = generate_password_hash(new_password)
        current_user.update_password(hashed_password)
        flash('Password updated successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Password change error: {str(e)}")
        flash('An error occurred while changing your password.', 'danger')
    
    return render_template('auth/settings.html')

@auth.route('/settings/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    if current_user.is_active:
        flash('Your email is already verified.', 'info')
        return redirect(url_for('auth.settings'))
    
    # Check rate limit for verification email requests
    if not check_rate_limit(f"verify:{current_user.id}", 3, 3600):
        flash('Too many verification attempts. Please try again later.', 'danger')
        return redirect(url_for('auth.settings'))
    
    try:
        send_verification_email(current_user)
        flash('Verification email sent. Please check your inbox.', 'success')
    except Exception as e:
        current_app.logger.error(f"Verification email error: {str(e)}")
        flash('An error occurred while sending the verification email.', 'danger')
    
    increment_rate_limit(f"verify:{current_user.id}")
    return redirect(url_for('auth.settings'))

@auth.route('/settings/terminate-session/<session_id>', methods=['POST'])
@login_required
def terminate_session(session_id):
    try:
        delete_session(current_user.id, session_id)
        flash('Session terminated successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Session termination error: {str(e)}")
        flash('An error occurred while terminating the session.', 'danger')
    
    return redirect(url_for('auth.settings'))

@auth.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    try:
        user_id = current_user.user_id
        logout_user()
        User.delete_by_id(user_id)
        flash('Your account has been deleted successfully', 'success')
        return render_template('auth/login.html')
    except Exception as e:
        current_app.logger.error(f"Account deletion error: {str(e)}")
        flash('An error occurred while deleting your account', 'danger')
        return render_template('auth/settings.html') 