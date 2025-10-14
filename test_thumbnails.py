#!/usr/bin/env python3
"""
Test script to verify thumbnail generation is working
"""

import os
import sys
import tempfile
import subprocess
from PIL import Image
from io import BytesIO

def test_ffmpeg():
    """Test if ffmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        print("✅ ffmpeg is available")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ ffmpeg is not available")
        return False

def test_pillow():
    """Test if PIL/Pillow is working"""
    try:
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img_io = BytesIO()
        img.save(img_io, 'JPEG')
        print("✅ PIL/Pillow is working")
        return True
    except Exception as e:
        print(f"❌ PIL/Pillow error: {e}")
        return False

def test_temp_directory():
    """Test if we can create thumbnails directory"""
    try:
        temp_dir = os.path.join(tempfile.gettempdir(), 'thumbnails')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Test write permission
        test_file = os.path.join(temp_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        
        print(f"✅ Thumbnail directory is writable: {temp_dir}")
        return True
    except Exception as e:
        print(f"❌ Thumbnail directory error: {e}")
        return False

def test_aws_imports():
    """Test if AWS SDK is available"""
    try:
        import boto3
        print("✅ boto3 is available")
        return True
    except ImportError:
        print("❌ boto3 is not available")
        return False

def main():
    print("🔍 Testing BOLD-VIEWER Thumbnail System")
    print("=" * 50)
    
    tests = [
        ("FFmpeg", test_ffmpeg),
        ("PIL/Pillow", test_pillow),
        ("Temp Directory", test_temp_directory),
        ("AWS SDK", test_aws_imports)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nTesting {name}...")
        results.append(test_func())
    
    print("\n" + "=" * 50)
    print("Summary:")
    
    if all(results):
        print("✅ All tests passed! Thumbnail system should work.")
    else:
        print("❌ Some tests failed. Check the issues above.")
        
        if not results[0]:  # ffmpeg
            print("\n🔧 To install ffmpeg on macOS:")
            print("   brew install ffmpeg")
            
        if not results[3]:  # boto3
            print("\n🔧 To install missing Python packages:")
            print("   pip install -r requirements.txt")

if __name__ == "__main__":
    main()