import boto3
from config import Config

s3 = boto3.client(
    "s3",
    aws_access_key_id=Config.AWS_ACCESS_KEY,
    aws_secret_access_key=Config.AWS_SECRET_KEY,
    region_name=Config.REGION_NAME
)

def list_s3_contents(prefix=""):
    response = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME, Prefix=prefix, Delimiter="/")
    folders = [content['Prefix'] for content in response.get('CommonPrefixes', [])]
    files = [content['Key'] for content in response.get('Contents', [])]
    return {"folders": folders, "files": files}

def generate_presigned_url(object_key):
    return s3.generate_presigned_url("get_object", Params={"Bucket": Config.S3_BUCKET_NAME, "Key": object_key}, ExpiresIn=3600)
