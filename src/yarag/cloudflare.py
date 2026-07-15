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


async def search(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _url("/search"),
            headers=_headers(),
            json={"messages": [{"role": "user", "content": query}]},
        )
        resp.raise_for_status()
        body = resp.json()
    chunks = (body.get("result") or {}).get("chunks") or []
    return [
        {
            "doc_name": c.get("item", {}).get("key") or "未知文件",
            "snippet": (c.get("text") or "")[:200],
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
                    payload = json.loads(data)
                    if not isinstance(payload, dict):
                        continue
                    delta = payload["choices"][0]["delta"].get("content") or ""
                except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta


def _sync_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.cf_sync_api_token}"}


def list_item_status() -> dict[str, dict]:
    items: dict[str, dict] = {}
    page = 1
    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                _url("/items"), headers=_headers(), params={"page": page, "per_page": 100}
            )
            resp.raise_for_status()
            batch = resp.json().get("result") or []
            for it in batch:
                key = it.get("key")
                if key:
                    items[key] = it
            if len(batch) < 100:
                break
            page += 1
    return items


def retrieve_text(query: str, key: str) -> str:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            _url("/search"),
            headers=_headers(),
            json={"messages": [{"role": "user", "content": query}]},
        )
        resp.raise_for_status()
        chunks = (resp.json().get("result") or {}).get("chunks") or []
    texts = [c.get("text") or "" for c in chunks if (c.get("item") or {}).get("key") == key]
    return "\n".join(texts)


def trigger_sync() -> str:
    with httpx.Client(timeout=30) as client:
        resp = client.post(_url("/jobs"), headers=_sync_headers(), json={})
        resp.raise_for_status()
        return (resp.json().get("result") or {}).get("id") or ""
