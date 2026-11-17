"""Shared S3 access and a short, bounded directory cache."""
from collections import OrderedDict
from threading import Lock
from time import monotonic
from urllib.parse import quote

import boto3
from botocore.config import Config as BotoConfig
from config import Config

s3 = boto3.client(
    's3', aws_access_key_id=Config.AWS_ACCESS_KEY,
    aws_secret_access_key=Config.AWS_SECRET_KEY, region_name=Config.REGION_NAME,
    config=BotoConfig(connect_timeout=5, read_timeout=15, retries={'max_attempts': 2}),
)
_cache = OrderedDict()
_cache_lock = Lock()
CACHE_SECONDS = 15
PAGE_SIZE = 120


def list_s3_contents(prefix='', cursor=None, refresh=False):
    """Fetch one page, keeping large libraries out of the DOM and request memory."""
    cache_key = (Config.S3_BUCKET_NAME, prefix, cursor)
    with _cache_lock:
        cached = _cache.get(cache_key)
        if not refresh and cached and monotonic() - cached[0] < CACHE_SECONDS:
            _cache.move_to_end(cache_key)
            return cached[1]
    params = dict(Bucket=Config.S3_BUCKET_NAME, Prefix=prefix, Delimiter='/', MaxKeys=PAGE_SIZE)
    if cursor:
        params['ContinuationToken'] = cursor
    response = s3.list_objects_v2(**params)
    objects = [obj for obj in response.get('Contents', [])
               if obj['Key'] != prefix and not obj['Key'].endswith('/')]
    result = {
        'folders': sorted(p['Prefix'] for p in response.get('CommonPrefixes', [])),
        'files': sorted(obj['Key'] for obj in objects),
        'next_token': response.get('NextContinuationToken'),
        'metadata': {obj['Key']: {'size': obj.get('Size'), 'modified': obj.get('LastModified')} for obj in objects},
    }
    with _cache_lock:
        _cache[cache_key] = (monotonic(), result)
        _cache.move_to_end(cache_key)
        while len(_cache) > 128:
            _cache.popitem(last=False)
    return result


def generate_presigned_url(object_key, download=False):
    params = {'Bucket': Config.S3_BUCKET_NAME, 'Key': object_key}
    if download:
        name = object_key.rsplit('/', 1)[-1]
        params['ResponseContentDisposition'] = "attachment; filename*=UTF-8''" + quote(name, safe='')
    return s3.generate_presigned_url('get_object', Params=params, ExpiresIn=3600)
