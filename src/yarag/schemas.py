from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    content_type: str = Field(..., examples=["application/pdf"])


class UploadResponse(BaseModel):
    key: str
    upload_url: str
    expires_in: int
    required_headers: dict[str, str]


class DownloadRequest(BaseModel):
    key: str
    expires_in: int | None = None


class DownloadResponse(BaseModel):
    download_url: str
    expires_in: int
