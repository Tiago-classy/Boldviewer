from dotenv import load_dotenv
import os
from datetime import timedelta
load_dotenv()


class Config:
    # Existing configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secure-secret-key-here'
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    REGION_NAME = os.getenv("REGION_NAME", "us-east-1")
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_SECURE = True  # For HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Security headers
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com"

    }

    # Development flag
    DEBUG = False
