import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from yarag import cloudflare
from yarag.auth import get_current_user
from yarag.db import get_db
from yarag.models import Message, Thread, User

router = APIRouter(prefix="/api/v1", tags=["chat"])
logger = logging.getLogger("uvicorn")

_HISTORY_LIMIT = 10


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if req.thread_id:
        thread = db.get(Thread, req.thread_id)
        if thread is None or thread.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到對話")
    else:
        thread = Thread(user_id=user.id, title=req.message[:30])
        db.add(thread)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in thread.messages[-_HISTORY_LIMIT:]]
    db.add(Message(thread_id=thread.id, role="user", content=req.message))
    thread.updated_at = datetime.now(UTC)
    db.commit()
    thread_id = thread.id

    async def generate():
        try:
            citations = await cloudflare.search(req.message)
            yield _sse("citations", citations)
            full_text = ""
            messages = [*history, {"role": "user", "content": req.message}]
            async for delta in cloudflare.stream_chat(messages):
                full_text += delta
                yield _sse("delta", {"text": delta})
            assistant = Message(
                thread_id=thread_id,
                role="assistant",
                content=full_text,
                citations=json.dumps(citations, ensure_ascii=False),
            )
            db.add(assistant)
            db.query(Thread).filter(Thread.id == thread_id).update(
                {"updated_at": datetime.now(UTC)}
            )
            db.commit()
            yield _sse("done", {"thread_id": thread_id, "message_id": assistant.id})
        except Exception:
            logger.exception("chat stream failed", extra={"thread_id": thread_id})
            yield _sse("error", {"message": "系統暫時無法取得資料，請稍後再試"})

    return StreamingResponse(generate(), media_type="text/event-stream")
