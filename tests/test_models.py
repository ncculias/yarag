from sqlalchemy import select

from yarag.db import Base, SessionLocal, engine, init_db
from yarag.models import Message, Thread, User


def setup_function():
    Base.metadata.drop_all(engine)
    init_db()


def test_create_user_thread_message():
    with SessionLocal() as db:
        user = User(username="alice", display_name="愛麗絲", password_hash="x")
        db.add(user)
        db.commit()
        thread = Thread(user_id=user.id, title="測試對話")
        db.add(thread)
        db.commit()
        assert len(thread.id) == 36  # UUID 自動產生
        msg = Message(thread_id=thread.id, role="user", content="哈囉")
        db.add(msg)
        db.commit()
        loaded = db.scalar(select(User).where(User.username == "alice"))
        assert loaded is not None and loaded.is_active and not loaded.is_admin
        assert db.scalar(select(Message).where(Message.thread_id == thread.id)).content == "哈囉"


def test_document_content_check_table_created():
    from sqlalchemy import inspect

    from yarag.db import Base, engine, init_db

    Base.metadata.drop_all(engine)
    init_db()
    assert "document_content_checks" in inspect(engine).get_table_names()
