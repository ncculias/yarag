from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from yarag.config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db() -> None:
    from sqlalchemy import inspect, text

    from yarag import models  # noqa: F401  確保模型已註冊

    Base.metadata.create_all(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("messages")}
    if "source" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN source VARCHAR(10) NOT NULL DEFAULT 'kb'"))


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
