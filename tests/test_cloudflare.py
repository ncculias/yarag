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


class _SyncResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_list_item_status_paginates(monkeypatch):
    pages = {
        1: {
            "result": [
                {"key": f"bills/{i}.md", "status": "completed", "checksum": f"c{i}", "error": None}
                for i in range(50)
            ],
            "result_info": {"total_count": 51},
        },
        2: {
            "result": [
                {"key": "bills/50.md", "status": "completed", "checksum": "c50", "error": None}
            ],
            "result_info": {"total_count": 51},
        },
    }

    def fake_get(self, url, **kwargs):
        assert "/items" in url
        assert kwargs["headers"]["Authorization"] == "Bearer test-cf-token"
        assert kwargs["params"]["per_page"] == 50
        return _SyncResp(pages[kwargs["params"]["page"]])

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    m = cloudflare.list_item_status()
    assert len(m) == 51
    assert m["bills/50.md"]["checksum"] == "c50"


def test_retrieve_text_filters_by_key(monkeypatch):
    payload = {"result": {"chunks": [
        {"text": "正文內容", "item": {"key": "2026/07/15/x-a.pdf"}},
        {"text": "別的檔", "item": {"key": "bills/1.md"}},
    ]}}

    def fake_post(self, url, **kwargs):
        assert "/search" in url
        assert kwargs["headers"]["Authorization"] == "Bearer test-cf-token"
        return _SyncResp(payload)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert cloudflare.retrieve_text("a", "2026/07/15/x-a.pdf") == "正文內容"


def test_trigger_sync_returns_job_id(monkeypatch):
    def fake_post(self, url, **kwargs):
        assert "/jobs" in url
        assert kwargs["headers"]["Authorization"] == "Bearer test-cf-sync-token"
        return _SyncResp({"result": {"id": "job-123"}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert cloudflare.trigger_sync() == "job-123"
