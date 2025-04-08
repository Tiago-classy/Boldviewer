import os
import time
import tempfile
import mimetypes
import subprocess
from io import BytesIO
from PIL import Image
from flask import Blueprint, render_template, request, send_file, current_app, flash, url_for,redirect
from flask import redirect
from flask_login import login_required
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
from config import Config
from utils.s3_utils import list_s3_contents, generate_presigned_url

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
        self.temp_dir = tempfile.gettempdir()
        self.s3 = s3_client
        self.max_thumbnail_size = (640, 640)

    def get_thumbnail_path(self, filename, prefix='thumb_'):
        """Generate the thumbnail path for a given filename"""
        safe_filename = secure_filename(filename)
        return os.path.join(self.temp_dir, f"{prefix}{safe_filename}.jpg")

    def thumbnail_exists_and_fresh(self, thumbnail_path, max_age=86400):
        """Check if thumbnail exists and is fresh"""
        try:
            if os.path.exists(thumbnail_path):
                file_age = time.time() - os.path.getmtime(thumbnail_path)
                return file_age < max_age
        except Exception:
            pass
        return False

    def generate_image_thumbnail(self, image_data, thumbnail_path):
        """Generate thumbnail for image"""
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Convert RGBA to RGB if necessary
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, 'white')
                    background.paste(img, mask=img.split()[-1])
                    img = background
                
                # Resize image maintaining aspect ratio
                img.thumbnail(self.max_thumbnail_size, Image.Resampling.LANCZOS)
                
                # Save with optimized quality
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
        except Exception as e:
            current_app.logger.error(f"Error generating image thumbnail: {str(e)}")
            raise

    def generate_video_thumbnail(self, video_path, thumbnail_path):
        """Generate thumbnail for video"""
        try:
            command = [
                'ffmpeg',
                '-i', video_path,
                '-ss', '00:00:01',  # Take frame from 1 second
                '-vframes', '1',
                '-vf', f'scale={self.max_thumbnail_size[0]}:-1',
                '-y',
                thumbnail_path
            ]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            
            # Verify thumbnail was created
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

# Initialize the thumbnail generator
thumbnail_generator = ThumbnailGenerator(BUCKET_NAME, s3)
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


@main.route("/dashboard/<path:folder_path>")
@main.route("/dashboard", defaults={"folder_path": ""})
@login_required
def browse_folder(folder_path):
    folder_path = folder_path.rstrip("/") + "/" if folder_path else ""
    s3_contents = list_s3_contents(folder_path)
    objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path, Delimiter="/")

    folders = [obj["Prefix"] for obj in objects.get("CommonPrefixes", [])]
    files = [obj["Key"] for obj in objects.get("Contents", []) if obj["Key"] != folder_path]

    breadcrumbs = []
    path_parts = folder_path.strip("/").split("/") if folder_path else []
    for i, part in enumerate(path_parts):
        breadcrumbs.append({
            "name": part,
            "url": "/dashboard/" + "/".join(path_parts[:i+1])
        })
    
    return render_template(
        "dashboard.html",
        s3_contents=s3_contents,
        folders=folders,
        files=files,
        breadcrumbs=breadcrumbs
    )

@main.route('/image-thumbnail/<path:filename>')
@login_required
def get_image_thumbnail(filename):
    try:
        thumbnail_path = thumbnail_generator.get_thumbnail_path(filename, prefix='img_thumb_')
        
        # Check for existing thumbnail
        if thumbnail_generator.thumbnail_exists_and_fresh(thumbnail_path):
            return send_file(thumbnail_path, mimetype='image/jpeg')

        # Generate new thumbnail
        image_data = thumbnail_generator.get_s3_object(filename)
        thumbnail_generator.generate_image_thumbnail(image_data, thumbnail_path)
        
        return send_file(thumbnail_path, mimetype='image/jpeg')

    except Exception as e:
        current_app.logger.error(f"Error in get_image_thumbnail: {str(e)}")
        return send_file('static/images/image-placeholder.png', mimetype='image/png')

@main.route('/video-thumbnail/<path:filename>')
@login_required
def get_video_thumbnail(filename):
    try:
        thumbnail_path = thumbnail_generator.get_thumbnail_path(filename, prefix='vid_thumb_')
        
        # Check for existing thumbnail
        if thumbnail_generator.thumbnail_exists_and_fresh(thumbnail_path):
            return send_file(thumbnail_path, mimetype='image/jpeg')

        # Download video and generate thumbnail
        temp_video = os.path.join(thumbnail_generator.temp_dir, secure_filename(filename))
        try:
            # Download video file
            thumbnail_generator.s3.download_file(BUCKET_NAME, filename, temp_video)
            
            # Generate thumbnail
            thumbnail_generator.generate_video_thumbnail(temp_video, thumbnail_path)
            
            if os.path.exists(thumbnail_path):
                return send_file(thumbnail_path, mimetype='image/jpeg')
            else:
                raise Exception("Thumbnail generation failed")

        except Exception as e:
            current_app.logger.error(f"Error generating video thumbnail: {str(e)}")
            return send_file('static/images/video-placeholder.jpg', mimetype='image/jpeg')

        finally:
            # Clean up temporary video file
            if os.path.exists(temp_video):
                try:
                    os.remove(temp_video)
                except Exception:
                    pass

    except Exception as e:
        current_app.logger.error(f"Error in get_video_thumbnail: {str(e)}")
        return send_file('static/images/video-placeholder.jpg', mimetype='image/jpeg')
