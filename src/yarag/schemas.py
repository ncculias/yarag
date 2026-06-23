from pydantic import BaseModel


class UploadRequest(BaseModel):
    content_type: str


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
