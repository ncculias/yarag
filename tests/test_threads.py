import json

from yarag.db import SessionLocal
from yarag.models import Message, Thread


def _seed_thread(user_id, title="議案詢問"):
    with SessionLocal() as db:
        t = Thread(user_id=user_id, title=title)
        db.add(t)
        db.commit()
        db.add(Message(thread_id=t.id, role="user", content="尖山國中案進度？"))
        db.add(
            Message(
                thread_id=t.id,
                role="assistant",
                content="辦理中",
                citations=json.dumps([{"doc_name": "33717.md", "snippet": "…", "similarity": 0.9}]),
            )
        )
        db.commit()
        return t.id


def test_list_only_own_threads(client, make_user, auth_headers):
    other_id = make_user(username="bob")
    _seed_thread(other_id)
    r = client.get("/api/v1/threads", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_get_thread_with_citations(client, make_user, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    with SessionLocal() as db:
        from sqlalchemy import select

        from yarag.models import User

        uid = db.scalar(select(User.id).where(User.username == "alice"))
    tid = _seed_thread(uid)
    r = client.get(f"/api/v1/threads/{tid}", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs[1]["citations"][0]["doc_name"] == "33717.md"
    assert msgs[0]["source"] == "kb"


def test_cannot_read_others_thread(client, make_user, auth_headers):
    other_id = make_user(username="bob")
    tid = _seed_thread(other_id)
    assert client.get(f"/api/v1/threads/{tid}", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/v1/threads/{tid}", headers=auth_headers).status_code == 404


def test_delete_own_thread(client, make_user, auth_headers):
    with SessionLocal() as db:
        from sqlalchemy import select

        from yarag.models import User

        uid = db.scalar(select(User.id).where(User.username == "alice"))
    tid = _seed_thread(uid)
    assert client.delete(f"/api/v1/threads/{tid}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/threads/{tid}", headers=auth_headers).status_code == 404
