"""Presentation helpers shared by the library and preview."""
import mimetypes


def media_type(filename):
    mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    kind = mime.split('/')[0]
    return kind if kind in ('image', 'video') else 'file', mime


def format_size(size):
    if size is None:
        return None
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1024
