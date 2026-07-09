import httpx
import pytest

from yarag import cloudflare


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.anyio
async def test_search_maps_citations(monkeypatch):
    payload = {
        "success": True,
        "result": {
            "query_kind": "text",
            "search_query": "尖山國中",
            "chunks": [
                {
                    "id": "abc123",
                    "type": "text",
                    "score": 0.6456971,
                    "text": "尖山國中新建校舍…",
                    "item": {
                        "key": "bills/33717.md",
                        "timestamp": 1783526460000,
                        "metadata": {},
                    },
                    "scoring_details": {"vector_score": 0.6456971},
                }
            ],
        },
    }

    async def fake_post(self, url, **kwargs):
        assert "/search" in url
        return _FakeResponse(payload)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    citations = await cloudflare.search("尖山國中")
    assert citations == [
        {"doc_name": "bills/33717.md", "snippet": "尖山國中新建校舍…", "similarity": 0.6456971}
    ]


@pytest.mark.anyio
async def test_search_handles_missing_fields(monkeypatch):
    async def fake_post(self, url, **kwargs):
        return _FakeResponse({"result": {"chunks": [{}]}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    citations = await cloudflare.search("x")
    assert citations[0]["doc_name"] == "未知文件"
    assert citations[0]["similarity"] == 0


class _FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


@pytest.mark.anyio
async def test_stream_chat_parses_sse_deltas(monkeypatch):
    lines = [
        "event: chunks",
        'data: [{"id": "abc123", "type": "text", "score": 0.6456971, "text": "尖山國中新建校舍…", '
        '"item": {"key": "bills/33717.md"}}]',
        "",
        'data: {"choices": [{"delta": {"content": "尖"}}]}',
        "",
        'data: {"choices": [{"delta": {"content": "山"}}]}',
        'data: {"choices": [{"delta": {}}]}',
        "not-a-data-line",
        'data: {"broken json"',
        "data: [DONE]",
        'data: {"choices": [{"delta": {"content": "後面不該出現"}}]}',
    ]

    def fake_stream(self, method, url, **kwargs):
        assert method == "POST"
        assert "/chat/completions" in url
        return _FakeStreamResponse(lines)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    deltas = [d async for d in cloudflare.stream_chat([{"role": "user", "content": "hi"}])]
    assert deltas == ["尖", "山"]
