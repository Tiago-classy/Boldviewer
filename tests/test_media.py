"""Offline regressions for the media pipeline. Never connects to AWS."""
import os
os.environ.update(AWS_ACCESS_KEY='test', AWS_SECRET_KEY='test', S3_BUCKET_NAME='test-bucket',
                  AWS_EC2_METADATA_DISABLED='true')

from concurrent.futures import Future
from io import BytesIO
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app import app
from routes import main_routes
from utils import s3_utils
from utils.thumbnails import ThumbnailGenerator
from utils.media import format_size


class MetadataTests(unittest.TestCase):
    def test_sizes_distinguish_zero_from_missing_and_include_units(self):
        self.assertIsNone(format_size(None))
        self.assertEqual(format_size(0), '0 B')
        self.assertEqual(format_size(1024), '1.0 KB')
        self.assertEqual(format_size(1536 * 1024), '1.5 MB')


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        s3_utils._cache.clear()

    @patch.object(s3_utils.s3, 'list_objects_v2')
    def test_listing_is_bounded_and_cached_by_prefix_and_cursor(self, listing):
        listing.return_value = {'Contents': [{'Key': 'work/'}, {'Key': 'work/b.jpg', 'Size': 1024}, {'Key': 'work/a.jpg'}],
                                'CommonPrefixes': [{'Prefix': 'work/edits/'}], 'NextContinuationToken': 'next'}
        result = s3_utils.list_s3_contents('work/')
        self.assertEqual(result['files'], ['work/a.jpg', 'work/b.jpg'])
        self.assertEqual(result['next_token'], 'next')
        self.assertEqual(result['metadata']['work/b.jpg']['size'], 1024)
        self.assertEqual(s3_utils.list_s3_contents('work/'), result)
        listing.assert_called_once_with(Bucket='test-bucket', Prefix='work/', Delimiter='/', MaxKeys=120)
        s3_utils.list_s3_contents('work/', 'next')
        self.assertEqual(listing.call_args.kwargs['ContinuationToken'], 'next')
        s3_utils.list_s3_contents('other/')
        self.assertEqual(listing.call_count, 3)

    @patch.object(s3_utils.s3, 'list_objects_v2', return_value={})
    @patch.object(s3_utils, 'monotonic')
    def test_expired_listing_refreshes(self, clock, listing):
        clock.return_value = 0
        s3_utils.list_s3_contents()
        clock.return_value = 16
        s3_utils.list_s3_contents()
        self.assertEqual(listing.call_count, 2)

    @patch.object(s3_utils.s3, 'list_objects_v2', return_value={})
    def test_explicit_reload_bypasses_cache(self, listing):
        s3_utils.list_s3_contents()
        s3_utils.list_s3_contents(refresh=True)
        self.assertEqual(listing.call_count, 2)

    @patch.object(s3_utils.s3, 'generate_presigned_url', return_value='signed')
    def test_download_uses_safe_utf8_content_disposition(self, sign):
        s3_utils.generate_presigned_url('folder/a "name".jpg', download=True)
        params = sign.call_args.kwargs['Params']
        self.assertEqual(params['Bucket'], 'test-bucket')
        self.assertEqual(params['ResponseContentDisposition'], "attachment; filename*=UTF-8''a%20%22name%22.jpg")


class RouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, LOGIN_DISABLED=True)
        self.client = app.test_client()

    def tearDown(self):
        app.config['LOGIN_DISABLED'] = False

    @patch.object(main_routes, 'list_s3_contents')
    def test_dashboard_renders_types_and_pagination(self, listing):
        listing.return_value = {'folders': ['work/drafts/'], 'files': ['work/a.webp', 'work/b.webm', 'work/readme.pdf'], 'next_token': 'a+/='}
        response = self.client.get('/dashboard/work?cursor=previous')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-kind="video"', html)
        self.assertIn('data-kind="image"', html)
        self.assertIn('data-kind="file"', html)
        self.assertIn('Next page', html)
        self.assertIn('on this page', html)
        listing.assert_called_once_with('work/', 'previous', refresh=False)

    @patch.object(main_routes, 'list_s3_contents', side_effect=RuntimeError('offline'))
    def test_listing_failure_is_not_an_empty_folder(self, listing):
        with self.assertLogs(app.logger, level='ERROR'):
            response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'Library unavailable', response.data)
        self.assertNotIn(b'This folder is empty', response.data)
        self.assertNotIn(b'0 folders', response.data)
        self.assertIn(b'Contents unavailable', response.data)

    @patch.object(main_routes, 'list_s3_contents', return_value={'folders': [], 'files': [], 'next_token': None})
    def test_empty_folder_and_no_per_request_disk_scan(self, listing):
        with patch.object(main_routes.thumbnail_generator, 'cleanup_old_thumbnails') as cleanup:
            response = self.client.get('/dashboard')
            self.client.get('/dashboard')
        cleanup.assert_not_called()
        self.assertIn(b'This folder is empty', response.data)

    @patch.object(main_routes, 'generate_presigned_url', return_value='https://test-bucket.s3.amazonaws.com/film.webm')
    def test_native_video_uses_actual_mime_and_metadata_preload(self, sign):
        response = self.client.get('/view-file/film.webm')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'type="video/webm"', response.data)
        self.assertIn(b'preload="metadata"', response.data)
        self.assertNotIn(b'videojs(', response.data)

    @patch.object(main_routes.thumbnail_generator, 'generate_thumbnail_async', return_value='processing')
    def test_status_starts_generation_without_exposing_paths(self, generate):
        response = self.client.get('/check-thumbnail/work/a.jpg')
        generate.assert_called_once_with('work/a.jpg', False)
        self.assertEqual(response.json, {'ready': False, 'processing': True, 'state': 'processing', 'url': None})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    @patch.object(main_routes.thumbnail_generator, 'generate_thumbnail_async', return_value='processing')
    def test_explicit_thumbnail_retry_is_passed_to_generator(self, generate):
        response = self.client.get('/check-thumbnail/a.jpg?retry=1')
        generate.assert_called_once_with('a.jpg', False, retry=True)
        self.assertEqual(response.json['state'], 'processing')

    @patch.object(main_routes.thumbnail_generator, 'generate_thumbnail_async')
    def test_unsupported_file_never_starts_thumbnail_work(self, generate):
        response = self.client.get('/check-thumbnail/notes.pdf')
        self.assertEqual(response.json['state'], 'unsupported')
        self.assertEqual(self.client.get('/thumbnail/notes.pdf').status_code, 404)
        generate.assert_not_called()

    def test_ready_thumbnail_private_cache_and_conditional_get(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'thumbnail.jpg'
            Image.new('RGB', (20, 20)).save(path)
            with patch.object(main_routes.thumbnail_generator, 'get_thumbnail_path', return_value=str(path)):
                response = self.client.get('/thumbnail/a.jpg')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'private, max-age=86400')
                etag = response.headers['ETag']
                response.close()
                cached = self.client.get('/thumbnail/a.jpg', headers={'If-None-Match': etag})
                self.assertEqual(cached.status_code, 304)
                cached.close()

    @patch.object(main_routes.thumbnail_generator, 'generate_thumbnail_async', return_value='processing')
    def test_placeholder_cannot_be_cached_as_completed_thumbnail(self, generate):
        with patch.object(main_routes.thumbnail_generator, 'thumbnail_exists_and_fresh', return_value=False):
            response = self.client.get('/thumbnail/not-ready.jpg')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response.close()

    def test_private_routes_require_login(self):
        app.config['LOGIN_DISABLED'] = False
        for path in ['/dashboard', '/view-file/a.jpg', '/thumbnail/a.jpg', '/check-thumbnail/a.jpg', '/debug/thumbnails']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.location)

    def test_login_error_and_csp_render_without_inline_code(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'for="username"', response.data)
        self.assertNotIn(b'<style>', response.data)
        self.assertNotIn(b'<script>', response.data)
        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', response.headers['Content-Security-Policy'])
        self.assertEqual(self.client.get('/missing').status_code, 404)


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.s3 = Mock()
        self.generator = ThumbnailGenerator('test-bucket', self.s3)
        self.generator.temp_dir = self.directory.name

    def tearDown(self):
        self.generator.executor.shutdown(wait=True)
        self.directory.cleanup()

    def test_cache_separates_buckets_and_paths(self):
        first = self.generator.get_thumbnail_path('folder/a.jpg')
        self.assertNotEqual(first, self.generator.get_thumbnail_path('other/a.jpg'))
        self.generator.bucket_name = 'other-bucket'
        self.assertNotEqual(first, self.generator.get_thumbnail_path('folder/a.jpg'))

    def test_palette_and_transparent_images_encode_as_jpeg(self):
        for mode in ['P', 'RGBA', 'RGB']:
            with self.subTest(mode=mode):
                data = BytesIO()
                Image.new(mode, (1200, 600)).save(data, format='PNG')
                path = str(Path(self.directory.name) / 'result.jpg')
                self.generator.generate_image_thumbnail(data.getvalue(), path)
                with Image.open(path) as image:
                    self.assertEqual(image.mode, 'RGB')
                    self.assertLessEqual(image.width, 640)
                    self.assertLessEqual(image.height, 480)

    def test_exif_rotation_keeps_thumbnail_within_bounds(self):
        data = BytesIO()
        source = Image.new('RGB', (1200, 600))
        exif = source.getexif()
        exif[274] = 6
        source.save(data, format='JPEG', exif=exif)
        path = str(Path(self.directory.name) / 'rotated.jpg')
        self.generator.generate_image_thumbnail(data.getvalue(), path)
        with Image.open(path) as image:
            self.assertLessEqual(image.width, 640)
            self.assertLessEqual(image.height, 480)
            self.assertGreater(image.height, image.width)

    def test_job_deduplication_and_backpressure(self):
        with patch.object(self.generator.executor, 'submit', return_value=Future()) as submit:
            self.assertEqual(self.generator.generate_thumbnail_async('a.jpg'), 'processing')
            self.assertEqual(self.generator.generate_thumbnail_async('a.jpg'), 'processing')
            submit.assert_called_once()
            self.generator.processing_queue.update(f'{index}.jpg' for index in range(32))
            self.assertEqual(self.generator.generate_thumbnail_async('overflow.jpg'), 'busy')
            submit.assert_called_once()

    def test_background_job_writes_complete_cache_without_flask_context(self):
        data = BytesIO()
        Image.new('RGB', (30, 30)).save(data, format='PNG')
        body = BytesIO(data.getvalue())
        self.s3.get_object.return_value = {'Body': body}
        self.generator.generate_thumbnail_async('a.png')
        self.generator.executor.shutdown(wait=True)
        self.assertTrue(body.closed)
        self.assertEqual(self.generator.generate_thumbnail_async('a.png'), 'ready')
        self.assertEqual(self.generator.processing_queue, set())
        self.s3.get_object.assert_called_once()

    def test_failed_job_has_cooldown_and_cleans_partial_files(self):
        self.s3.get_object.side_effect = RuntimeError('offline')
        self.generator.generate_thumbnail_async('broken.jpg')
        self.generator.executor.shutdown(wait=True)
        self.assertEqual(self.generator.generate_thumbnail_async('broken.jpg'), 'failed')
        self.assertEqual(list(Path(self.directory.name).glob('*.jpg')), [])
        self.assertEqual(self.generator.processing_queue, set())

    def test_explicit_retry_bypasses_failure_cooldown(self):
        import time
        self.generator.failures['a.jpg'] = time.monotonic()
        with patch.object(self.generator.executor, 'submit', return_value=Future()) as submit:
            self.assertEqual(self.generator.generate_thumbnail_async('a.jpg'), 'failed')
            self.assertEqual(self.generator.generate_thumbnail_async('a.jpg', retry=True), 'processing')
            submit.assert_called_once()

    def test_file_lock_prevents_duplicate_work_between_workers(self):
        import fcntl
        output = self.generator.get_thumbnail_path('a.jpg')
        with open(output + '.lock', 'a') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.generator._process('a.jpg', False, output)
        self.s3.get_object.assert_not_called()
        self.assertFalse(Path(output).exists())

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is not installed')
    def test_real_video_frame_can_be_generated(self):
        video = str(Path(self.directory.name) / 'sample.mp4')
        output = str(Path(self.directory.name) / 'frame.jpg')
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'color=c=blue:s=64x48:r=1:d=1', '-pix_fmt', 'yuv420p', '-y', video],
                       check=True, timeout=15)
        self.generator.generate_video_thumbnail(video, output)
        with Image.open(output) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertGreater(image.width, 0)

    @patch('utils.thumbnails.subprocess.run')
    def test_video_seek_precedes_input_and_has_timeout(self, run):
        path = Path(self.directory.name) / 'frame.jpg'
        path.write_bytes(b'frame')
        self.generator.generate_video_thumbnail('https://signed-video', str(path))
        command = run.call_args.args[0]
        self.assertLess(command.index('-ss'), command.index('-i'))
        self.assertEqual(run.call_args.kwargs['timeout'], 30)


if __name__ == '__main__':
    unittest.main()
