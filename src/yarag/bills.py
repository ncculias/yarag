import logging
import re

from yarag.config import settings
from yarag.uploads import s3_client

logger = logging.getLogger("uvicorn")

_BILL_ID_RE = re.compile(r"(?<!\d)\d{4,6}(?!\d)")
MAX_BILLS = 3


def extract_bill_ids(text: str) -> list[str]:
    seen: list[str] = []
    for match in _BILL_ID_RE.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def fetch_bill(bill_id: str) -> str | None:
    key = f"bills/{bill_id}.md"
    try:
        obj = s3_client.get_object(Bucket=settings.default_bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        # 查無此檔屬正常情形（數字未必是議案編號）；但設定/認證錯誤也會走到這裡，
        # 故記錄下來以利診斷，行為維持回傳 None 讓呼叫端走原流程。
        logger.debug("fetch_bill miss", extra={"key": key}, exc_info=True)
        return None
