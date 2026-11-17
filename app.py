from flask import Flask, render_template, request
from flask_login import LoginManager

from config import Config
from routes.auth_routes import auth, init_login_manager
from routes.main_routes import main

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager(app)
login_manager.session_protection = 'strong'
login_manager.refresh_view = 'auth.login'
init_login_manager(login_manager)
app.register_blueprint(auth)
app.register_blueprint(main)


@app.after_request
def security_headers(response):
    for header, value in Config.SECURITY_HEADERS.items():
        response.headers[header] = value
    bucket = Config.S3_BUCKET_NAME or ''
    region = Config.REGION_NAME
    media_origins = (
        f'https://{bucket}.s3.amazonaws.com https://{bucket}.s3.{region}.amazonaws.com '
        f'https://s3.amazonaws.com https://s3.{region}.amazonaws.com'
    )
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        f"img-src 'self' data: {media_origins}; media-src 'self' {media_origins}; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.endpoint != 'static' and request.endpoint != 'main.get_thumbnail':
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    app.run(debug=Config.DEBUG)
