#!/usr/bin/env python3
"""
Thumbnail Fix Script for BOLD-VIEWER
This script diagnoses and helps fix thumbnail loading issues.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
            return True
        else:
            print("❌ ffmpeg is not working properly")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ ffmpeg is not installed")
        return False

def install_ffmpeg():
    """Install ffmpeg on macOS"""
    print("Installing ffmpeg...")
    try:
        # Check if Homebrew is installed
        subprocess.run(['brew', '--version'], capture_output=True, check=True)
        print("Installing ffmpeg via Homebrew...")
        result = subprocess.run(['brew', 'install', 'ffmpeg'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg installed successfully")
            return True
        else:
            print(f"❌ Failed to install ffmpeg: {result.stderr}")
            return False
    except subprocess.CalledProcessError:
        print("❌ Homebrew not found. Please install Homebrew first:")
        print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        return False

def check_python_dependencies():
    """Check if required Python packages are installed"""
    required_packages = ['boto3', 'PIL', 'flask']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is missing")
            missing_packages.append(package)
    
    return missing_packages

def install_dependencies():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def test_aws_connection():
    """Test AWS S3 connection"""
    try:
        import boto3
        from config import Config
        
        s3 = boto3.client('s3',
                         aws_access_key_id=Config.AWS_ACCESS_KEY,
                         aws_secret_access_key=Config.AWS_SECRET_KEY,
                         region_name=Config.REGION_NAME)
        
        # Test connection
        response = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME, MaxKeys=1)
        print("✅ AWS S3 connection successful")
        print(f"   Bucket: {Config.S3_BUCKET_NAME}")
        print(f"   Region: {Config.REGION_NAME}")
        return True
        
    except Exception as e:
        print(f"❌ AWS S3 connection failed: {e}")
        print("   Check your AWS credentials in .env file")
        return False

def check_thumbnail_directory():
    """Check if thumbnail directory exists and is writable"""
    temp_dir = os.path.join(tempfile.gettempdir(), 'thumbnails')
    try:
        os.makedirs(temp_dir, exist_ok=True)
        # Test write permission
        test_file = os.path.join(temp_dir, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"✅ Thumbnail directory is writable: {temp_dir}")
        return True
    except Exception as e:
        print(f"❌ Thumbnail directory issue: {e}")
        return False

def main():
    """Main diagnostic function"""
    print("🔍 BOLD-VIEWER Thumbnail Diagnostic Tool")
    print("=" * 50)
    
    issues_found = []
    
    # Check ffmpeg
    if not check_ffmpeg():
        issues_found.append("ffmpeg")
    
    # Check Python dependencies
    missing_deps = check_python_dependencies()
    if missing_deps:
        issues_found.append("dependencies")
    
    # Check AWS connection
    if missing_deps:
        print("⚠️  Skipping AWS test due to missing dependencies")
    else:
        if not test_aws_connection():
            issues_found.append("aws")
    
    # Check thumbnail directory
    if not check_thumbnail_directory():
        issues_found.append("thumbnail_dir")
    
    print("\n" + "=" * 50)
    
    if not issues_found:
        print("✅ All checks passed! Thumbnails should work.")
        return
    
    print("❌ Issues found. Attempting to fix...")
    
    # Fix issues
    if "dependencies" in issues_found:
        if install_dependencies():
            issues_found.remove("dependencies")
    
    if "ffmpeg" in issues_found:
        if install_ffmpeg():
            issues_found.remove("ffmpeg")
    
    if issues_found:
        print(f"\n⚠️  Manual intervention needed for: {', '.join(issues_found)}")
        if "aws" in issues_found:
            print("   - Check AWS credentials in .env file")
            print("   - Verify S3 bucket permissions")
    else:
        print("\n✅ All issues fixed! Restart the application.")

if __name__ == "__main__":
    main()