from flask import Flask, render_template, request, make_response
from flask_login import LoginManager
from datetime import timedelta
from config import Config  
from routes.auth_routes import auth, init_login_manager 
from routes.main_routes import main
import secrets

app = Flask(__name__)
@app.after_request
def apply_csp(response):
    nonce = secrets.token_urlsafe(16)
    csp = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' https://fonts.googleapis.com; "
        f"font-src 'self' https://fonts.gstatic.com; "
        f"img-src 'self' https://ic4u-ig-videos.s3.amazonaws.com data:; "
        f"media-src 'self' https://ic4u-ig-videos.s3.amazonaws.com;"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['Permissions-Policy'] = 'unload=()'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'no-referrer'
    request.csp_nonce = nonce
    return response
@app.context_processor
def inject_nonce():
    return dict(nonce=getattr(request, 'csp_nonce', ''))

@app.after_request
def add_security_headers(response):
    for header, value in Config.SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
class ExtendedConfig(Config):
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_SECURE = True  # For HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

app.config.from_object(ExtendedConfig)

# Initialize LoginManager with enhanced security
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"
login_manager.refresh_view = "auth.login"
login_manager.needs_refresh_message = "Session timed out, please login again"
login_manager.needs_refresh_message_category = "warning"

# Initialize login manager
init_login_manager(login_manager)

# Register blueprints
app.register_blueprint(auth)
app.register_blueprint(main, url_prefix="/")

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == "__main__":
    app.run(debug=True)
