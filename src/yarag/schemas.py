from pydantic import BaseModel


class DownloadRequest(BaseModel):
    file_key: str
    expires_in: int | None = None


class DownloadResponse(BaseModel):
    download_url: str
    expires_in: int


class UploadRequest(BaseModel):
    file_name: str
    content_type: str
    folder: str
    expires_in: int | None = None


class UploadResponse(BaseModel):
    file_key: str
    upload_url: str
    expires_in: int
    required_headers: dict[str, str]
