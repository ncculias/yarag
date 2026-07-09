import logging
import uuid
from datetime import UTC, datetime

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from yarag.auth import get_current_user
from yarag.config import settings
from yarag.models import User
from yarag.schemas import UploadResponse

router = APIRouter(prefix="/api/v1", tags=["uploads"])
logger = logging.getLogger("uvicorn")

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.endpoint_url,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.region_name,
    config=Config(signature_version="s3v4"),
)


class UploadRequest(BaseModel):
    content_type: str
    file_name: str
    size_bytes: int


class DocumentOut(BaseModel):
    name: str
    size_bytes: int
    updated_at: datetime


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
def generate_upload_url(
    req: UploadRequest, user: User = Depends(get_current_user)
) -> UploadResponse:
    ext = ALLOWED_CONTENT_TYPES.get(req.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="不支援的檔案格式")
    if req.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="檔案超過 4MB 上限，系統無法索引")
    now = datetime.now(UTC)
    key = f"{now.strftime('%Y/%m/%d')}/{uuid.uuid4().hex}{ext}"
    try:
        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.default_bucket,
                "Key": key,
                "ContentType": req.content_type,
            },
            ExpiresIn=settings.default_expires_in,
        )
    except (BotoCoreError, ClientError) as e:
        logger.exception("presign failed", extra={"key": key})
        raise HTTPException(status_code=500, detail="無法產生上傳網址") from e
    return UploadResponse(
        key=key,
        upload_url=upload_url,
        expires_in=settings.default_expires_in,
        required_headers={"Content-Type": req.content_type},
    )


@router.get("/documents")
def list_documents(user: User = Depends(get_current_user)) -> list[DocumentOut]:
    paginator = s3_client.get_paginator("list_objects_v2")
    docs = []
    for page in paginator.paginate(Bucket=settings.default_bucket):
        for obj in page.get("Contents", []):
            docs.append(
                DocumentOut(
                    name=obj["Key"], size_bytes=obj["Size"], updated_at=obj["LastModified"]
                )
            )
    docs.sort(key=lambda d: d.updated_at, reverse=True)
    return docs
