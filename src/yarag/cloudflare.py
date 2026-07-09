import json
from collections.abc import AsyncIterator

import httpx

from yarag.config import settings

_API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai-search/instances/{instance}"


def _url(path: str) -> str:
    base = _API.format(account=settings.cf_account_id, instance=settings.cf_ai_search_instance)
    return base + path


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.cf_api_token}"}


def _snippet(chunk: dict) -> str:
    content = chunk.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        text = first.get("text", "") if isinstance(first, dict) else str(first)
        return text[:200]
    return str(content or "")[:200]


async def search(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _url("/search"),
            headers=_headers(),
            json={"messages": [{"role": "user", "content": query}]},
        )
        resp.raise_for_status()
        body = resp.json()
    chunks = (body.get("result") or {}).get("data") or []
    return [
        {
            "doc_name": c.get("filename") or "未知文件",
            "snippet": _snippet(c),
            "similarity": c.get("score") or 0,
        }
        for c in chunks
    ]


async def stream_chat(messages: list[dict]) -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            _url("/chat/completions"),
            headers=_headers(),
            json={"messages": messages, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content") or ""
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta
