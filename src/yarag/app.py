import logging
import uuid

import boto3
import uvicorn
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, status

from yarag.config import settings
from yarag.schemas import UploadRequest, UploadResponse

app = FastAPI()


# TODO: Use a independent logger and config
logger = logging.getLogger("uvicorn")


s3_client = boto3.client(
    "s3",
    endpoint_url=settings.endpoint_url,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.region_name,
    config=Config(signature_version="s3v4"),
)


# TODO: Limit maximum file upload size
@app.post(path="/api/v1/uploads", status_code=status.HTTP_200_OK)
def generate_upload_url(request: UploadRequest) -> UploadResponse:
    unique_id = uuid.uuid4().hex
    file_key = f"{request.folder}/{unique_id}-{request.file_name}"

    logger.info(
        "Generating upload URL",
        extra={
            "folder": request.folder,
            "content_type": request.content_type,
            "file_key": file_key,
        },
    )

    try:
        params = {
            "Bucket": settings.default_bucket,
            "Key": file_key,
            "ContentType": request.content_type,
        }

        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=settings.default_expires_in,
        )

        logger.info(
            "Upload URL generated successfully",
            extra={
                "file_key": file_key,
            },
        )

        return UploadResponse(
            file_key=file_key,
            upload_url=upload_url,
            expires_in=settings.default_expires_in,
            required_headers={"Content-Type": request.content_type},
        )

    except (BotoCoreError, ClientError) as e:
        logger.exception(
            "Failed to generate upload URL",
            extra={
                "file_key": file_key,
                "bucket": settings.default_bucket,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        ) from e


if __name__ == "__main__":
    uvicorn.run("yarag.app:app", reload=True)
