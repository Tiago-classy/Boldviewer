from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
import bcrypt
from functools import wraps
from datetime import datetime, timedelta  # Add this import

auth = Blueprint("auth", __name__)

# Initialize with multiple users
users = {
    "admin": {
        "password": bcrypt.hashpw("0192023a7bbd73250516f069df18b500".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "admin"
    },
    "tigas": {
        "password": bcrypt.hashpw("c549506ec05fe824ebfd0be91536f8b8".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "user"
    },
    "bold": {
        "password": bcrypt.hashpw("b45694458b0ead6c6ab10963e262e1b8".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "user"
    }
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username
        self.role = users.get(username, {}).get('role', 'user')

    def get_id(self):
        return self.username

# Initialize login_manager
login_manager = None

def init_login_manager(lm):
    global login_manager
    login_manager = lm
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User(user_id) if user_id in users else None

def check_session_timeout():
    """Check if the session has timed out"""
    timeout_minutes = 30
    session_start = session.get('session_start')
    
    if not session_start:
        return True
        
    try:
        session_start_time = datetime.fromisoformat(session_start)
        time_elapsed = datetime.now() - session_start_time
        return time_elapsed > timedelta(minutes=timeout_minutes)
    except Exception:
        return True

@auth.before_request
def before_request():
    if current_user.is_authenticated:
        if check_session_timeout():
            logout_user()
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('auth.login'))
        session['session_start'] = datetime.now().isoformat()

@auth.route('/', methods=['GET', 'POST'])
def root():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').encode('utf-8')

        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('auth/login.html')

        user = users.get(username)

        try:
            if user and bcrypt.checkpw(password, user["password"].encode('utf-8')):
                user_obj = User(username)
                login_user(user_obj, remember=True)
                
                # Initialize session timeout
                session['session_start'] = datetime.now().isoformat()
                session.permanent = True
                
                # Get the next page from the URL parameters
                next_page = request.args.get('next')
                
                # Validate the next page to prevent open redirect vulnerability
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('main.dashboard')
                    
                return redirect(next_page)
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            flash('An error occurred during login. Please try again.', 'danger')
            print(f"Login error: {str(e)}")  # Log the error

    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))
