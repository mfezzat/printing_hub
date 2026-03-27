"""
services/storage.py — S3-compatible chunked file upload.
Supports any file type and any file size via streaming upload.
MIME type is validated client-side before storage.
"""
import io, uuid, magic
from fastapi import UploadFile, HTTPException
import aiobotocore.session
from config import get_settings

settings = get_settings()

# MIME types that are BLOCKED (executables, scripts)
BLOCKED_MIMES = {
    "application/x-msdownload", "application/x-executable",
    "application/x-sh", "application/x-bat",
    "text/x-shellscript",
}

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks


async def upload_file_chunked(file: UploadFile, folder: str = "uploads") -> tuple[str, str]:
    """
    Upload a file to S3-compatible storage in chunks.
    Returns (storage_key, mime_type).
    """
    # Read first 2048 bytes for MIME detection
    header = await file.read(2048)
    mime   = magic.from_buffer(header, mime=True)

    if mime in BLOCKED_MIMES:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {mime}")

    ext         = (file.filename or "file").rsplit(".", 1)[-1][:10]
    storage_key = f"{folder}/{uuid.uuid4()}.{ext}"

    session    = aiobotocore.session.get_session()
    config     = {
        "endpoint_url":          settings.S3_ENDPOINT or None,
        "aws_access_key_id":     settings.S3_ACCESS_KEY,
        "aws_secret_access_key": settings.S3_SECRET_KEY,
        "region_name":           settings.S3_REGION,
    }

    async with session.create_client("s3", **config) as s3:
        # Initiate multipart upload
        mpu = await s3.create_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=storage_key,
            ContentType=mime,
        )
        upload_id = mpu["UploadId"]
        parts     = []
        part_num  = 1

        # Upload first chunk (header + rest)
        buf = io.BytesIO(header)
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() >= CHUNK_SIZE:
                buf.seek(0)
                part = await s3.upload_part(
                    Bucket=settings.S3_BUCKET,
                    Key=storage_key,
                    PartNumber=part_num,
                    UploadId=upload_id,
                    Body=buf.read(),
                )
                parts.append({"PartNumber": part_num, "ETag": part["ETag"]})
                part_num += 1
                buf = io.BytesIO()

        # Upload remaining buffer
        remaining = buf.getvalue()
        if remaining:
            part = await s3.upload_part(
                Bucket=settings.S3_BUCKET,
                Key=storage_key,
                PartNumber=part_num,
                UploadId=upload_id,
                Body=remaining,
            )
            parts.append({"PartNumber": part_num, "ETag": part["ETag"]})

        await s3.complete_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=storage_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    return storage_key, mime


async def get_presigned_url(storage_key: str, expires: int = 3600) -> str:
    """Generate a temporary download URL."""
    session = aiobotocore.session.get_session()
    config  = {
        "endpoint_url":          settings.S3_ENDPOINT or None,
        "aws_access_key_id":     settings.S3_ACCESS_KEY,
        "aws_secret_access_key": settings.S3_SECRET_KEY,
        "region_name":           settings.S3_REGION,
    }
    async with session.create_client("s3", **config) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": storage_key},
            ExpiresIn=expires,
        )
    return url
