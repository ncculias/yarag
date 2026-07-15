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
from sqlalchemy.orm import Session

from yarag import cloudflare
from yarag.auth import get_current_user
from yarag.config import settings
from yarag.db import get_db
from yarag.models import DocumentContentCheck, User
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
    index_status: str


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_KEY_PREFIX_RE = re.compile(r"^[0-9a-f]{8}-")

MAX_FILENAME_LEN = 80


def _safe_filename(file_name: str, ext: str) -> str:
    name = file_name.replace("/", "").replace("\\", "")
    name = _CONTROL_CHARS_RE.sub("", name)
    name = name.strip()
    name = _WHITESPACE_RE.sub(" ", name)
    name = re.sub(r"\.{2,}", ".", name)
    name = name.rstrip(". ")
    if not name:
        return f"file{ext}"
    name = name[:MAX_FILENAME_LEN]
    name = name.rstrip(". ")
    if not name:
        return f"file{ext}"
    if not name.endswith(ext):
        stem, _, orig_ext = name.rpartition(".")
        if stem and orig_ext and len(orig_ext) <= 10:
            name = stem
        name = name.rstrip(". ")
        if not name:
            return f"file{ext}"
        name = f"{name}{ext}"
        name = name[:MAX_FILENAME_LEN]
        if not name.endswith(ext):
            name = name[: MAX_FILENAME_LEN - len(ext)] + ext
    # Final safety pass: guarantee the returned key can never contain ".."
    # regardless of what truncation/append steps above did to the boundary.
    result = re.sub(r"\.{2,}", ".", name)
    if not result.endswith(ext):
        result = result.rstrip(". ")
        if not result:
            return f"file{ext}"
        result = f"{result}{ext}"
        result = re.sub(r"\.{2,}", ".", result)
    return result


def _display_name(key: str) -> str:
    tail = key.rsplit("/", 1)[-1]
    return _KEY_PREFIX_RE.sub("", tail)


_CONTENT_MIN_CHARS = 20


def _content_is_empty(text: str) -> bool:
    # 取 "## Contents" 之後的正文；沒有則視整體
    body = text.split("## Contents", 1)[-1]
    body = re.sub(r"(?m)^\s*#+.*$", "", body)  # 標題行（含 ### Page N）
    body = re.sub(r"(?m)^\s*[-*]\s.*$", "", body)  # 清單行（metadata 殘留）
    return len(re.sub(r"\s+", "", body)) < _CONTENT_MIN_CHARS


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


_CHECKED_EXTS = (".pdf", ".docx", ".xlsx")


def _cached_is_empty(db: Session, key: str, item: dict) -> bool:
    checksum = item.get("checksum") or ""
    if checksum:
        cached = db.get(DocumentContentCheck, checksum)
        if cached is not None:
            return cached.is_empty
    query = _display_name(key).rsplit(".", 1)[0]
    empty = _content_is_empty(cloudflare.retrieve_text(query, key))
    if checksum:
        db.add(DocumentContentCheck(checksum=checksum, is_empty=empty))
        db.commit()
    return empty


def _derive_status(db: Session, key: str, item: dict | None) -> str:
    if item is None:
        return "indexing"
    if item.get("error") or item.get("status") in {"error", "failed"}:
        return "failed"
    if item.get("status") != "completed":
        return "indexing"
    if not key.lower().endswith(_CHECKED_EXTS):
        return "ready"  # md/txt 一定有文字
    try:
        return "empty" if _cached_is_empty(db, key, item) else "ready"
    except Exception:
        logger.exception("content check failed", extra={"key": key})
        return "indexing"  # 判不出來時安全退，不誤報 ready/empty


@router.get("/documents")
def list_documents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DocumentOut]:
    try:
        status_map = cloudflare.list_item_status()
    except Exception:
        logger.exception("list_item_status failed")
        status_map = {}
    paginator = s3_client.get_paginator("list_objects_v2")
    docs = []
    for page in paginator.paginate(Bucket=settings.default_bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            docs.append(
                DocumentOut(
                    name=key,
                    size_bytes=obj["Size"],
                    updated_at=obj["LastModified"],
                    display_name=_display_name(key),
                    index_status=_derive_status(db, key, status_map.get(key)),
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


@router.post("/documents/sync")
def sync_documents(user: User = Depends(get_current_user)) -> dict[str, str]:
    try:
        job_id = cloudflare.trigger_sync()
    except Exception as e:
        logger.exception("trigger_sync failed")
        raise HTTPException(status_code=502, detail="無法觸發索引同步，稍後會由排程自動處理") from e
    return {"job_id": job_id}
