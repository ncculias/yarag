import httpx
import pytest

from yarag import openai_client

_SSE_LINES = [
    'event: response.output_text.delta',
    'data: {"type":"response.output_text.delta","delta":"議會"}',
    '',
    'event: response.output_text.delta',
    'data: {"type":"response.output_text.delta","delta":"改選"}',
    '',
    'event: response.completed',
    'data: {"type":"response.completed","response":{"output":[{"type":"message","content":[{"type":"output_text","text":"議會改選","annotations":[{"type":"url_citation","title":"中央社報導","url":"https://example.com/news"}]}]}]}}',
    '',
]


class _FakeStream:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


@pytest.mark.anyio
async def test_stream_web_answer_yields_deltas_then_sources(monkeypatch):
    def fake_stream(self, method, url, **kwargs):
        assert "/responses" in url
        assert kwargs["json"]["tools"] == [{"type": "web_search"}]
        return _FakeStream(_SSE_LINES)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    events = [e async for e in openai_client.stream_web_answer("最近議會改選？")]
    assert events[0] == ("delta", "議會")
    assert events[1] == ("delta", "改選")
    kind, sources = events[-1]
    assert kind == "sources"
    assert sources == [
        {"doc_name": "中央社報導", "snippet": "議會改選", "similarity": 0, "url": "https://example.com/news"}
    ]


@pytest.mark.anyio
async def test_stream_web_answer_tolerates_unknown_events(monkeypatch):
    lines = ['event: response.created', 'data: {"type":"response.created"}', '', *_SSE_LINES]

    def fake_stream(self, method, url, **kwargs):
        return _FakeStream(lines)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    events = [e async for e in openai_client.stream_web_answer("q")]
    assert ("delta", "議會") in events and events[-1][0] == "sources"


@pytest.mark.anyio
async def test_stream_ends_without_completed_still_yields_empty_sources(monkeypatch):
    lines = ['event: response.output_text.delta', 'data: {"type":"response.output_text.delta","delta":"嗨"}', '']

    def fake_stream(self, method, url, **kwargs):
        return _FakeStream(lines)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    events = [e async for e in openai_client.stream_web_answer("q")]
    assert events == [("delta", "嗨"), ("sources", [])]


@pytest.mark.anyio
async def test_failed_event_raises(monkeypatch):
    lines = ['event: response.failed', 'data: {"type":"response.failed"}', '']

    def fake_stream(self, method, url, **kwargs):
        return _FakeStream(lines)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    with pytest.raises(RuntimeError):
        [e async for e in openai_client.stream_web_answer("q")]
