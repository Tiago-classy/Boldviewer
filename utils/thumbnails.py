"""Bounded thumbnail jobs; atomic disk cache shared by Gunicorn workers."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import fcntl
import hashlib
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    def __init__(self, bucket_name, s3_client):
        self.bucket_name = bucket_name
        self.s3 = s3_client
        self.temp_dir = os.path.join(tempfile.gettempdir(), 'thumbnails')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.max_thumbnail_size = (640, 480)
        self.cache_duration = 86400 * 7
        self.processing_queue = set()
        self.failures = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='thumbnail')

    def get_thumbnail_path(self, filename, prefix='thumb_'):
        digest = hashlib.sha256(f'{self.bucket_name}/{filename}'.encode()).hexdigest()
        return os.path.join(self.temp_dir, f'{prefix}{digest}.jpg')

    def thumbnail_exists_and_fresh(self, path):
        try:
            stat = os.stat(path)
            return stat.st_size > 0 and time.time() - stat.st_mtime < self.cache_duration
        except OSError:
            return False

    def generate_image_thumbnail(self, image_data, path):
        with Image.open(BytesIO(image_data)) as source:
            rotated = source.getexif().get(274, 1) in (5, 6, 7, 8)
            bounds = self.max_thumbnail_size[::-1] if rotated else self.max_thumbnail_size
            source.thumbnail(bounds, Image.Resampling.LANCZOS)
            image = ImageOps.exif_transpose(source)
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                image = Image.new('RGB', rgba.size, 'white')
                image.paste(rgba, mask=rgba.getchannel('A'))
            else:
                image = image.convert('RGB')
            image.save(path, 'JPEG', quality=80, optimize=True)

    def generate_video_thumbnail(self, video_url, path):
        # Seek before opening: FFmpeg can use S3 range reads instead of downloading a video.
        subprocess.run([
            'ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', '0', '-i', video_url,
            '-frames:v', '1', '-vf', 'scale=640:480:force_original_aspect_ratio=decrease',
            '-threads', '1', '-q:v', '5', '-y', path,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=30)
        if not os.path.getsize(path):
            raise ValueError('Empty video thumbnail')

    def generate_thumbnail_async(self, filename, is_video=False, retry=False):
        path = self.get_thumbnail_path(filename, 'video_thumb_' if is_video else 'img_thumb_')
        if self.thumbnail_exists_and_fresh(path):
            return 'ready'
        with self.lock:
            if filename in self.processing_queue:
                return 'processing'
            now = time.monotonic()
            self.failures = {key: at for key, at in self.failures.items() if now - at < 60}
            if retry:
                self.failures.pop(filename, None)
            if filename in self.failures:
                return 'failed'
            if len(self.processing_queue) >= 32:
                return 'busy'
            self.processing_queue.add(filename)
        try:
            self.executor.submit(self._process, filename, is_video, path)
        except RuntimeError:
            with self.lock:
                self.processing_queue.discard(filename)
            return 'busy'
        return 'processing'

    def _process(self, filename, is_video, path):
        temp_path = None
        try:
            # Another process may already be producing this thumbnail. Keep lock files stable.
            with open(path + '.lock', 'a') as lock_file:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                if self.thumbnail_exists_and_fresh(path):
                    return
                fd, temp_path = tempfile.mkstemp(suffix='.jpg', dir=self.temp_dir)
                os.close(fd)
                if is_video:
                    url = self.s3.generate_presigned_url('get_object', Params={
                        'Bucket': self.bucket_name, 'Key': filename}, ExpiresIn=300)
                    self.generate_video_thumbnail(url, temp_path)
                else:
                    response = self.s3.get_object(Bucket=self.bucket_name, Key=filename)
                    body = response['Body']
                    try:
                        if response.get('ContentLength', 0) > 50 * 1024 * 1024:
                            raise ValueError('Image exceeds thumbnail size limit')
                        data = body.read(50 * 1024 * 1024 + 1)
                        if len(data) > 50 * 1024 * 1024:
                            raise ValueError('Image exceeds thumbnail size limit')
                        self.generate_image_thumbnail(data, temp_path)
                    finally:
                        body.close()
                os.replace(temp_path, path)
        except Exception:
            # Do not log signed URLs or object contents.
            logger.warning('Thumbnail generation failed for %s', filename)
            with self.lock:
                self.failures[filename] = time.monotonic()
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
                except OSError:
                    logger.warning('Could not remove temporary thumbnail')
            with self.lock:
                self.processing_queue.discard(filename)

    def cleanup_old_thumbnails(self):
        for path in Path(self.temp_dir).glob('*thumb_*.jpg'):
            try:
                if time.time() - path.stat().st_mtime > self.cache_duration:
                    path.unlink(missing_ok=True)
            except OSError:
                logger.warning('Could not clean expired thumbnail')
