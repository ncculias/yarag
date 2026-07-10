import json
from collections.abc import AsyncIterator

import httpx

from yarag.config import settings

_URL = "https://api.openai.com/v1/responses"
_SYSTEM = (
    "你是新北市教育局系統的網路搜尋助理。以繁體中文回答，"
    "內容為網路公開資訊、非官方資料；請附上資訊來源。"
)


def _extract_sources(payload: dict) -> list[dict]:
    sources: list[dict] = []
    response = payload.get("response") or {}
    for item in response.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            text = content.get("text") or ""
            for ann in content.get("annotations") or []:
                if ann.get("type") == "url_citation":
                    sources.append(
                        {
                            "doc_name": ann.get("title") or ann.get("url") or "網路來源",
                            "snippet": text[:200],
                            "similarity": 0,
                            "url": ann.get("url") or "",
                        }
                    )
    return sources


async def stream_web_answer(question: str) -> AsyncIterator[tuple[str, object]]:
    body = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "web_search"}],
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", _URL, headers=headers, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    payload = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                kind = payload.get("type")
                if kind == "response.output_text.delta":
                    delta = payload.get("delta") or ""
                    if delta:
                        yield ("delta", delta)
                elif kind == "response.completed":
                    yield ("sources", _extract_sources(payload))
