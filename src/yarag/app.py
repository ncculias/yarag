import logging
import mimetypes
import uuid
from datetime import UTC, datetime

import boto3
import uvicorn
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, status

from yarag.auth import router as auth_router
from yarag.config import settings
from yarag.schemas import UploadRequest, UploadResponse
from yarag.threads import router as threads_router

ALLOWED_CONTENT_TYPES = {"text/plain", "application/pdf"}

app = FastAPI()

app.include_router(auth_router)
app.include_router(threads_router)


# TODO: Use a independent logger and config
logger = logging.getLogger("uvicorn")

# TODO: Move this to lifespan.py
s3_client = boto3.client(
    "s3",
    endpoint_url=settings.endpoint_url,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.region_name,
    config=Config(signature_version="s3v4"),
)


# TODO: Limit maximum file upload size
@app.post(path="/api/v1/uploads", status_code=status.HTTP_201_CREATED)
def generate_upload_url(request: UploadRequest) -> UploadResponse:

    logger.info(
        "Generating upload URL",
        extra={
            "content_type": request.content_type,
        },
    )

    if request.content_type not in ALLOWED_CONTENT_TYPES:
        logger.error(
            "Unsupported content type",
            extra={
                "content_type": request.content_type,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type",
        )

    ext = mimetypes.guess_extension(request.content_type)

    if not ext:
        logger.error(
            "Unable to guess MIME type.",
            extra={
                "content_type": request.content_type,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type",
        )

    now = datetime.now(UTC)
    unique_id = uuid.uuid4().hex
    key = f"{now.strftime('%Y/%m/%d')}/{unique_id}{ext}"

    try:
        params = {"Bucket": settings.default_bucket, "Key": key, "ContentType": request.content_type}

        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=settings.default_expires_in,
        )

        logger.info(
            "Upload URL generated successfully",
            extra={
                "key": key,
            },
        )

        return UploadResponse(
            key=key,
            upload_url=upload_url,
            expires_in=settings.default_expires_in,
            required_headers={"Content-Type": request.content_type},
        )

    except (BotoCoreError, ClientError) as e:
        logger.exception(
            "Failed to generate upload URL",
            extra={
                "key": key,
                "bucket": settings.default_bucket,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        ) from e


def main() -> None:
    uvicorn.run("yarag.app:app", reload=True)


if __name__ == "__main__":
    main()
