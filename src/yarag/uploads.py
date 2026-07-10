import logging
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from yarag.auth import get_current_user
from yarag.config import settings
from yarag.models import User
from yarag.schemas import DownloadResponse, UploadResponse

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
    display_name: str


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_KEY_PREFIX_RE = re.compile(r"^[0-9a-f]{8}-")

MAX_FILENAME_LEN = 80


def _safe_filename(file_name: str, ext: str) -> str:
    name = file_name.replace("/", "").replace("\\", "")
    name = _CONTROL_CHARS_RE.sub("", name)
    name = name.strip()
    name = _WHITESPACE_RE.sub(" ", name)
    if not name:
        return f"file{ext}"
    name = name[:MAX_FILENAME_LEN]
    if not name.endswith(ext):
        stem, _, orig_ext = name.rpartition(".")
        if stem and orig_ext and len(orig_ext) <= 10:
            name = stem
        name = f"{name}{ext}"
        name = name[:MAX_FILENAME_LEN]
        if not name.endswith(ext):
            name = name[: MAX_FILENAME_LEN - len(ext)] + ext
    return name


def _display_name(key: str) -> str:
    tail = key.rsplit("/", 1)[-1]
    return _KEY_PREFIX_RE.sub("", tail)


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
    safe = _safe_filename(req.file_name, ext)
    key = f"{now:%Y/%m/%d}/{uuid.uuid4().hex[:8]}-{safe}"
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
                    name=obj["Key"],
                    size_bytes=obj["Size"],
                    updated_at=obj["LastModified"],
                    display_name=_display_name(obj["Key"]),
                )
            )
    docs.sort(key=lambda d: d.updated_at, reverse=True)
    return docs


@router.get("/documents/download")
def download_document(key: str, user: User = Depends(get_current_user)) -> DownloadResponse:
    if ".." in key or key.startswith("/"):
        raise HTTPException(status_code=400, detail="非法的檔案路徑")
    display_name = _display_name(key)
    try:
        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.default_bucket,
                "Key": key,
                "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(display_name)}",
            },
            ExpiresIn=settings.default_expires_in,
        )
    except (BotoCoreError, ClientError) as e:
        logger.exception("presign failed", extra={"key": key})
        raise HTTPException(status_code=500, detail="無法產生下載網址") from e
    return DownloadResponse(download_url=download_url, expires_in=settings.default_expires_in)
