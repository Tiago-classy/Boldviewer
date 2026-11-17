"""Authenticated media browsing and thumbnail endpoints."""
import os
import shutil

from flask import Blueprint, current_app, jsonify, render_template, request, send_file, url_for
from flask_login import login_required

from config import Config
from utils.s3_utils import generate_presigned_url, list_s3_contents, s3
from utils.thumbnails import ThumbnailGenerator
from utils.media import format_size, media_type

main = Blueprint('main', __name__)
thumbnail_generator = ThumbnailGenerator(Config.S3_BUCKET_NAME, s3)
thumbnail_generator.cleanup_old_thumbnails()


def clean_path(path):
    return '/'.join(filter(None, path.split('/')))


@main.route('/dashboard', defaults={'prefix': ''})
@main.route('/dashboard/<path:prefix>')
@login_required
def dashboard(prefix):
    prefix = clean_path(prefix)
    prefix = prefix + '/' if prefix else ''
    breadcrumbs = []
    parts = prefix.rstrip('/').split('/') if prefix else []
    for index, part in enumerate(parts):
        breadcrumbs.append({'name': part, 'url': url_for('main.dashboard', prefix='/'.join(parts[:index + 1]))})
    error = False
    try:
        contents = list_s3_contents(prefix, request.args.get('cursor'), refresh=request.args.get('refresh') == '1')
    except Exception:
        current_app.logger.exception('Unable to list media library')
        contents = {'folders': [], 'files': [], 'next_token': None}
        error = True
    files = []
    for key in contents['files']:
        metadata = contents.get('metadata', {}).get(key, {})
        modified = metadata.get('modified')
        files.append({
            'key': key, 'name': key.rsplit('/', 1)[-1], 'kind': media_type(key)[0],
            'extension': os.path.splitext(key)[1].lstrip('.').upper() or 'File',
            'size': metadata.get('size'), 'size_label': format_size(metadata.get('size')),
            'modified': modified, 'timestamp': modified.timestamp() if modified else 0,
        })
    counts = {kind: sum(file['kind'] == kind for file in files) for kind in ('image', 'video', 'file')}
    page = render_template(
        'dashboard.html', s3_contents=contents, files=files, counts=counts,
        breadcrumbs=breadcrumbs, current_prefix=prefix, load_error=error,
        paginated=bool(request.args.get('cursor') or contents.get('next_token')),
    )
    return page, 503 if error else 200


@main.route('/view-file/<path:filename>')
@login_required
def view_file(filename):
    filename = clean_path(filename)
    kind, mime = media_type(filename)
    parts = filename.split('/')
    path = [{'name': part, 'path': '/'.join(parts[:index + 1])}
            for index, part in enumerate(parts[:-1])]
    try:
        return render_template('view_file.html', filename=filename, file_type=kind, mime_type=mime,
                               file_url=generate_presigned_url(filename),
                               download_url=generate_presigned_url(filename, download=True),
                               path=path, parent_path='/'.join(parts[:-1]))
    except Exception:
        current_app.logger.exception('Unable to open media')
        return render_template('errors/500.html'), 503


@main.route('/thumbnail/<path:filename>')
@login_required
def get_thumbnail(filename):
    kind, _ = media_type(filename)
    if kind == 'file':
        return '', 404
    path = thumbnail_generator.get_thumbnail_path(filename, 'video_thumb_' if kind == 'video' else 'img_thumb_')
    if thumbnail_generator.thumbnail_exists_and_fresh(path):
        response = send_file(path, mimetype='image/jpeg', conditional=True, max_age=86400)
        response.headers['Cache-Control'] = 'private, max-age=86400'
        return response
    thumbnail_generator.generate_thumbnail_async(filename, kind == 'video')
    response = send_file(os.path.join(current_app.static_folder, 'images', f'{kind}-placeholder.jpg'), mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'no-store'
    return response


@main.route('/check-thumbnail/<path:filename>')
@login_required
def check_thumbnail(filename):
    kind, _ = media_type(filename)
    if kind == 'file':
        state = 'unsupported'
    elif request.args.get('retry') == '1':
        state = thumbnail_generator.generate_thumbnail_async(filename, kind == 'video', retry=True)
    else:
        state = thumbnail_generator.generate_thumbnail_async(filename, kind == 'video')
    return jsonify(ready=state == 'ready', processing=state == 'processing', state=state,
                   url=url_for('main.get_thumbnail', filename=filename) if state == 'ready' else None)


@main.route('/debug/thumbnails')
@login_required
def debug_thumbnails():
    # Retain diagnostics without exposing filesystem paths or signed URLs.
    with thumbnail_generator.lock:
        pending = len(thumbnail_generator.processing_queue)
    return jsonify(pending=pending, ffmpeg_available=bool(shutil.which('ffmpeg')))
