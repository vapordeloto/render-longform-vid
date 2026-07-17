"""Upload merged video to Railway bucket (S3-compatible)."""
import os
from datetime import datetime
from pathlib import Path
import boto3
from botocore.config import Config

BUCKET = os.getenv("BUCKET")
ENDPOINT = os.getenv("ENDPOINT")
ACCESS_KEY = os.getenv("ACCESS_KEY_ID")
SECRET_KEY = os.getenv("SECRET_ACCESS_KEY")
REGION = os.getenv("REGION", "auto")


def get_client():
    """Build S3 client for Railway storage."""
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def upload_merged_video(local_path: Path, key_prefix: str = "merged") -> str:
    """
    Upload a local video file to the bucket.
    Returns the public or presigned URL to the object.
    """
    if not all([BUCKET, ENDPOINT, ACCESS_KEY, SECRET_KEY]):
        raise ValueError("Storage env vars (BUCKET, ENDPOINT, ACCESS_KEY_ID, SECRET_ACCESS_KEY) must be set")

    client = get_client()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    key = f"{key_prefix}-{timestamp}.mp4"

    with open(local_path, "rb") as f:
        client.upload_fileobj(
            f,
            BUCKET,
            key,
            ExtraArgs={"ContentType": "video/mp4"},
        )

    # Public URL if bucket is public; otherwise presigned
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=86400 * 7,  # 7 days
        )
    except Exception:
        url = f"{ENDPOINT.rstrip('/')}/{BUCKET}/{key}"
    return url
