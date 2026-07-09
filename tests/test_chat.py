import json


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        name = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        events.append((name, data))
    return events


def _patch_cloudflare(monkeypatch, deltas=("你好", "，議案辦理中")):
    from yarag import chat

    async def fake_search(query):
        return [{"doc_name": "bills/33717.md", "snippet": "…", "similarity": 0.9}]

    async def fake_stream(messages):
        for d in deltas:
            yield d

    monkeypatch.setattr(chat.cloudflare, "search", fake_search)
    monkeypatch.setattr(chat.cloudflare, "stream_chat", fake_stream)


def test_chat_event_order_and_persistence(client, auth_headers, monkeypatch):
    _patch_cloudflare(monkeypatch)
    r = client.post(
        "/api/v1/chat", json={"message": "尖山國中進度？", "thread_id": None}, headers=auth_headers
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert [e[0] for e in events] == ["citations", "delta", "delta", "done"]
    assert events[0][1][0]["doc_name"] == "bills/33717.md"
    tid = events[-1][1]["thread_id"]

    detail = client.get(f"/api/v1/threads/{tid}", headers=auth_headers).json()
    assert detail["title"] == "尖山國中進度？"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "你好，議案辦理中"
    assert detail["messages"][1]["citations"][0]["doc_name"] == "bills/33717.md"


def test_chat_appends_to_existing_thread(client, auth_headers, monkeypatch):
    _patch_cloudflare(monkeypatch)
    first = client.post(
        "/api/v1/chat", json={"message": "第一問", "thread_id": None}, headers=auth_headers
    )
    tid = _parse_sse(first.text)[-1][1]["thread_id"]
    client.post("/api/v1/chat", json={"message": "第二問", "thread_id": tid}, headers=auth_headers)
    detail = client.get(f"/api/v1/threads/{tid}", headers=auth_headers).json()
    assert len(detail["messages"]) == 4


def test_chat_error_event_when_cloudflare_fails(client, auth_headers, monkeypatch):
    from yarag import chat

    async def boom(query):
        raise RuntimeError("cf down")

    monkeypatch.setattr(chat.cloudflare, "search", boom)
    r = client.post(
        "/api/v1/chat", json={"message": "問題", "thread_id": None}, headers=auth_headers
    )
    events = _parse_sse(r.text)
    assert events[-1][0] == "error"
    assert "稍後再試" in events[-1][1]["message"]


def test_chat_rejects_others_thread(client, make_user, auth_headers, monkeypatch):
    _patch_cloudflare(monkeypatch)
    from yarag.db import SessionLocal
    from yarag.models import Thread

    other_id = make_user(username="bob")
    with SessionLocal() as db:
        t = Thread(user_id=other_id, title="別人的")
        db.add(t)
        db.commit()
        tid = t.id
    r = client.post(
        "/api/v1/chat", json={"message": "偷看", "thread_id": tid}, headers=auth_headers
    )
    assert r.status_code == 404


def test_chat_bumps_thread_to_top_on_followup(client, auth_headers, monkeypatch):
    _patch_cloudflare(monkeypatch)
    first = client.post(
        "/api/v1/chat", json={"message": "第一個對話", "thread_id": None}, headers=auth_headers
    )
    first_tid = _parse_sse(first.text)[-1][1]["thread_id"]

    second = client.post(
        "/api/v1/chat", json={"message": "第二個對話", "thread_id": None}, headers=auth_headers
    )
    second_tid = _parse_sse(second.text)[-1][1]["thread_id"]

    # Sanity: right after creation, second thread is newest.
    threads = client.get("/api/v1/threads", headers=auth_headers).json()
    assert threads[0]["id"] == second_tid

    # Follow up on the FIRST thread — it should now be newest.
    client.post(
        "/api/v1/chat",
        json={"message": "追問第一個", "thread_id": first_tid},
        headers=auth_headers,
    )
    threads = client.get("/api/v1/threads", headers=auth_headers).json()
    assert threads[0]["id"] == first_tid
