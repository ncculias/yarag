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
        return None  # 不存在或讀取失敗：視為非議案編號，走原流程
