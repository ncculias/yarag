import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from yarag.auth import get_current_user
from yarag.db import get_db
from yarag.models import Message, Thread, User

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到對話")


class ThreadSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime
    preview: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[dict] | None
    source: str
    created_at: datetime


class ThreadDetail(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]


def _own_thread(thread_id: str, user: User, db: Session) -> Thread:
    thread = db.get(Thread, thread_id)
    if thread is None or thread.user_id != user.id:
        raise _NOT_FOUND
    return thread


@router.get("")
def list_threads(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ThreadSummary]:
    threads = db.scalars(
        select(Thread).where(Thread.user_id == user.id).order_by(Thread.updated_at.desc())
    ).all()
    out = []
    for t in threads:
        last = t.messages[-1].content if t.messages else ""
        out.append(
            ThreadSummary(id=t.id, title=t.title, updated_at=t.updated_at, preview=last[:60])
        )
    return out


@router.get("/{thread_id}")
def get_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadDetail:
    thread = _own_thread(thread_id, user, db)
    messages = [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=json.loads(m.citations) if m.citations else None,
            source=m.source,
            created_at=m.created_at,
        )
        for m in thread.messages
    ]
    return ThreadDetail(id=thread.id, title=thread.title, messages=messages)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.delete(_own_thread(thread_id, user, db))
    db.commit()


__all__ = ["router", "Message"]
