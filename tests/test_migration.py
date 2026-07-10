from sqlalchemy import inspect, text

from yarag.db import Base, engine, init_db


def test_source_column_added_to_legacy_table():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        # Drop the table if it exists (in case of interference)
        conn.execute(text("DROP TABLE IF EXISTS messages"))
        conn.execute(
            text(
                "CREATE TABLE messages ("
                "id INTEGER PRIMARY KEY, "
                "thread_id VARCHAR(36), "
                "role VARCHAR(10), "
                "content TEXT, "
                "citations TEXT, "
                "created_at DATETIME)"
            )
        )
    init_db()
    cols = {c["name"] for c in inspect(engine).get_columns("messages")}
    assert "source" in cols
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO messages (thread_id, role, content) VALUES ('t', 'user', 'x')"))
        row = conn.execute(text("SELECT source FROM messages")).fetchone()
    assert row[0] == "kb"
