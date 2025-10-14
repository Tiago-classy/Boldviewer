import os
import time
import tempfile
import mimetypes
import subprocess
import threading
import hashlib
from io import BytesIO
from PIL import Image
from flask import Blueprint, render_template, request, send_file, current_app, flash, url_for, redirect, jsonify
from flask_login import login_required
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from config import Config
from utils.s3_utils import list_s3_contents, generate_presigned_url
from utils.placeholder_generator import get_placeholder_bytes, ensure_placeholder_files

# Constants
BUCKET_NAME = 'ic4u-ig-videos'
SUPPORTED_IMAGE_FORMATS = ['image/jpeg', 'image/png', 'image/gif']
SUPPORTED_VIDEO_FORMATS = ['video/mp4', 'video/webm', 'video/ogg']

# Initialize Blueprint and S3 client
main = Blueprint("main", __name__)

s3 = boto3.client(
    "s3",
    aws_access_key_id=Config.AWS_ACCESS_KEY,
    aws_secret_access_key=Config.AWS_SECRET_KEY,
    region_name=Config.REGION_NAME
)


class ThumbnailGenerator:
    def __init__(self, bucket_name, s3_client):
        self.bucket_name = bucket_name
        self.temp_dir = os.path.join(tempfile.gettempdir(), 'thumbnails')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.s3 = s3_client
        self.max_thumbnail_size = (300, 300)
        self.processing_queue = set()
        self.cache_duration = 86400 * 7  # 7 days

    def get_thumbnail_path(self, filename, prefix='thumb_'):
        """Generate the thumbnail path for a given filename"""
        # Use hash for consistent naming and avoid path issues
        file_hash = hashlib.md5(filename.encode()).hexdigest()
        return os.path.join(self.temp_dir, f"{prefix}{file_hash}.jpg")

    def thumbnail_exists_and_fresh(self, thumbnail_path):
        """Check if thumbnail exists and is fresh"""
        try:
            if os.path.exists(thumbnail_path):
                file_age = time.time() - os.path.getmtime(thumbnail_path)
                return file_age < self.cache_duration
        except Exception:
            pass
        return False

    def generate_image_thumbnail(self, image_data, thumbnail_path):
        """Generate thumbnail for image"""
        try:
            with Image.open(BytesIO(image_data)) as img:
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, 'white')
                    background.paste(img, mask=img.split()[-1])
                    img = background
                
                img.thumbnail(self.max_thumbnail_size, Image.Resampling.LANCZOS)
                img.save(thumbnail_path, 'JPEG', quality=75, optimize=True)
        except Exception as e:
            current_app.logger.error(f"Error generating image thumbnail: {str(e)}")
            raise

    def generate_video_thumbnail(self, video_path, thumbnail_path):
        """Generate thumbnail for video"""
        try:
            command = [
                'ffmpeg', '-i', video_path, '-ss', '00:00:01', '-vframes', '1',
                '-vf', f'scale={self.max_thumbnail_size[0]}:-1',
                '-q:v', '5', '-y', thumbnail_path
            ]
            
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            if not os.path.exists(thumbnail_path) or os.path.getsize(thumbnail_path) == 0:
                raise Exception("Failed to generate video thumbnail")
                
        except Exception as e:
            current_app.logger.error(f"Error generating video thumbnail: {str(e)}")
            raise

    def get_s3_object(self, filename):
        """Get object from S3"""
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=filename)
            return response['Body'].read()
        except Exception as e:
            current_app.logger.error(f"Error getting S3 object: {str(e)}")
            raise
    
    def generate_thumbnail_async(self, filename, is_video=False):
        """Generate thumbnail asynchronously"""
        if filename in self.processing_queue:
            return
        
        self.processing_queue.add(filename)
        
        def process():
            try:
                prefix = 'video_thumb_' if is_video else 'img_thumb_'
                thumbnail_path = self.get_thumbnail_path(filename, prefix)
                
                if self.thumbnail_exists_and_fresh(thumbnail_path):
                    return
                
                if is_video:
                    temp_video = os.path.join(tempfile.gettempdir(), f"temp_{hashlib.md5(filename.encode()).hexdigest()}.mp4")
                    try:
                        video_data = self.get_s3_object(filename)
                        with open(temp_video, 'wb') as f:
                            f.write(video_data)
                        self.generate_video_thumbnail(temp_video, thumbnail_path)
                    finally:
                        if os.path.exists(temp_video):
                            os.remove(temp_video)
                else:
                    image_data = self.get_s3_object(filename)
                    self.generate_image_thumbnail(image_data, thumbnail_path)
                    
            except Exception as e:
                current_app.logger.error(f"Async thumbnail generation failed for {filename}: {str(e)}")
            finally:
                self.processing_queue.discard(filename)
        
        threading.Thread(target=process, daemon=True).start()
    
    def cleanup_old_thumbnails(self):
        """Clean up old thumbnail files"""
        try:
            current_time = time.time()
            for filename in os.listdir(self.temp_dir):
                if filename.startswith(('img_thumb_', 'video_thumb_')):
                    filepath = os.path.join(self.temp_dir, filename)
                    if os.path.isfile(filepath):
                        file_age = current_time - os.path.getmtime(filepath)
                        if file_age > self.cache_duration:
                            os.remove(filepath)
                            current_app.logger.info(f"Removed old thumbnail: {filename}")
        except Exception as e:
            current_app.logger.error(f"Error cleaning up thumbnails: {str(e)}")

# Initialize the thumbnail generator
thumbnail_generator = ThumbnailGenerator(BUCKET_NAME, s3)

# Ensure placeholder files exist and setup cleanup
@main.before_app_request
def setup_placeholders():
    ensure_placeholder_files(current_app.static_folder)
    # Clean up old thumbnails on startup
    thumbnail_generator.cleanup_old_thumbnails()
@main.route("/dashboard", defaults={"prefix": ""})
@main.route("/dashboard/<path:prefix>")
@login_required
def dashboard(prefix):
    try:
        # Ensure prefix ends with '/' if not empty
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        # List objects from S3
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )

        # Initialize contents dictionary
        s3_contents = {
            'folders': [],
            'files': []
        }

        # Get folders (CommonPrefixes)
        if 'CommonPrefixes' in response:
            s3_contents['folders'] = [p['Prefix'] for p in response['CommonPrefixes']]

        # Get files (excluding folders and the prefix itself)
        if 'Contents' in response:
            s3_contents['files'] = [
                obj['Key'] for obj in response['Contents']
                if obj['Key'] != prefix and not obj['Key'].endswith('/')
            ]

        # Generate breadcrumbs
        breadcrumbs = []
        if prefix:
            parts = prefix.rstrip('/').split('/')
            current_path = ""
            for part in parts:
                if part:
                    current_path += part + "/"
                    breadcrumbs.append({
                        "name": part,
                        "url": url_for('main.dashboard', prefix=current_path.rstrip('/'))
                    })

        current_app.logger.info(f"Found {len(s3_contents['folders'])} folders and {len(s3_contents['files'])} files")

        return render_template(
            "dashboard.html",
            s3_contents=s3_contents,
            breadcrumbs=breadcrumbs,
            current_prefix=prefix
        )

    except Exception as e:
        current_app.logger.error(f"Error listing S3 contents: {str(e)}")
        flash("Error loading contents. Please try again.", "danger")
        return render_template("dashboard.html", s3_contents={'folders': [], 'files': []})


def clean_path(path):
    """Clean and normalize path"""
    # Remove any double slashes and leading/trailing slashes
    cleaned = '/'.join(filter(None, path.split('/')))
    return cleaned

@main.route("/view-file/<path:filename>")
@login_required
def view_file(filename):
    try:
        # Clean the filename path
        filename = clean_path(filename)
        file_url = generate_presigned_url(filename)
        mime_type, _ = mimetypes.guess_type(filename)

        # Generate path for breadcrumbs
        path = []
        parts = filename.split('/')
        current_path = ""
        
        # Build the path for breadcrumbs, excluding the filename
        for part in parts[:-1]:
            if part:  # Skip empty parts
                current_path = clean_path(current_path + '/' + part)
                path.append({
                    "name": part,
                    "path": current_path
                })

        # Determine file type
        file_type = 'unsupported'
        if mime_type:
            if mime_type.startswith('image/'):
                file_type = 'image'
            elif mime_type.startswith('video/'):
                file_type = 'video'

        # Get the parent directory path for the back button
        parent_path = clean_path('/'.join(parts[:-1]))

        return render_template(
            "view_file.html",
            file_url=file_url,
            file_type=file_type,
            filename=filename,
            path=path,
            parent_path=parent_path
        )

    except Exception as e:
        current_app.logger.error(f"Error viewing file: {str(e)}")
        flash("Error loading file. Please try again.", "danger")
        return redirect(url_for('main.dashboard'))




@main.route('/thumbnail/<path:filename>')
@login_required
def get_thumbnail(filename):
    try:
        current_app.logger.info(f"Thumbnail requested for: {filename}")
        
        # Determine if it's a video or image
        mime_type, _ = mimetypes.guess_type(filename)
        is_video = mime_type and mime_type.startswith('video/')
        
        current_app.logger.info(f"File type detected: {'video' if is_video else 'image'}, mime: {mime_type}")
        
        prefix = 'video_thumb_' if is_video else 'img_thumb_'
        thumbnail_path = thumbnail_generator.get_thumbnail_path(filename, prefix)
        
        # If thumbnail exists and is fresh, serve it
        if thumbnail_generator.thumbnail_exists_and_fresh(thumbnail_path):
            current_app.logger.info(f"Serving cached thumbnail: {thumbnail_path}")
            return send_file(thumbnail_path, mimetype='image/jpeg')
        
        # Start async generation
        current_app.logger.info(f"Starting async thumbnail generation for: {filename}")
        thumbnail_generator.generate_thumbnail_async(filename, is_video)
        
        # Return appropriate placeholder
        file_type = 'video' if is_video else 'image'
        placeholder_name = f'{file_type}-placeholder.jpg'
        placeholder_path = os.path.join(current_app.static_folder, 'images', placeholder_name)
        
        if os.path.exists(placeholder_path):
            current_app.logger.info(f"Serving static placeholder: {placeholder_path}")
            return send_file(placeholder_path, mimetype='image/jpeg')
        
        # Generate placeholder on the fly
        current_app.logger.info("Generating placeholder on the fly")
        placeholder_bytes = get_placeholder_bytes(file_type)
        return send_file(placeholder_bytes, mimetype='image/jpeg')
        
    except Exception as e:
        current_app.logger.error(f"Error serving thumbnail for {filename}: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        
        # Return a basic error placeholder
        try:
            error_placeholder = get_placeholder_bytes('error')
            return send_file(error_placeholder, mimetype='image/jpeg')
        except:
            return '', 404

@main.route('/check-thumbnail/<path:filename>')
@login_required
def check_thumbnail(filename):
    """Check if thumbnail is ready"""
    try:
        mime_type, _ = mimetypes.guess_type(filename)
        is_video = mime_type and mime_type.startswith('video/')
        prefix = 'video_thumb_' if is_video else 'img_thumb_'
        thumbnail_path = thumbnail_generator.get_thumbnail_path(filename, prefix)
        
        ready = thumbnail_generator.thumbnail_exists_and_fresh(thumbnail_path)
        processing = filename in thumbnail_generator.processing_queue
        
        current_app.logger.info(f"Thumbnail check for {filename}: ready={ready}, processing={processing}")
        
        return jsonify({
            'ready': ready,
            'processing': processing,
            'url': url_for('main.get_thumbnail', filename=filename) if ready else None,
            'thumbnail_path': thumbnail_path,
            'file_exists': os.path.exists(thumbnail_path) if thumbnail_path else False
        })
    except Exception as e:
        current_app.logger.error(f"Error checking thumbnail for {filename}: {str(e)}")
        return jsonify({'ready': False, 'processing': False, 'error': str(e)})

@main.route('/debug/thumbnails')
@login_required
def debug_thumbnails():
    """Debug endpoint to check thumbnail system"""
    try:
        temp_dir = thumbnail_generator.temp_dir
        thumbnails = []
        
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                if file.startswith(('img_thumb_', 'video_thumb_')):
                    file_path = os.path.join(temp_dir, file)
                    thumbnails.append({
                        'name': file,
                        'size': os.path.getsize(file_path),
                        'modified': os.path.getmtime(file_path)
                    })
        
        return jsonify({
            'temp_dir': temp_dir,
            'temp_dir_exists': os.path.exists(temp_dir),
            'thumbnails': thumbnails,
            'processing_queue': list(thumbnail_generator.processing_queue),
            'ffmpeg_available': os.system('which ffmpeg') == 0
        })
    except Exception as e:
        return jsonify({'error': str(e)})
