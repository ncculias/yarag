import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from yarag import bills, cloudflare, openai_client
from yarag.auth import get_current_user
from yarag.db import get_db
from yarag.models import Message, Thread, User

router = APIRouter(prefix="/api/v1", tags=["chat"])
logger = logging.getLogger("uvicorn")

_HISTORY_LIMIT = 10


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    mode: Literal["kb", "web"] = "kb"


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _direct_bills(question: str) -> list[tuple[str, str]]:
    """辨識問題中的議案編號並取出存在的文件（最多 MAX_BILLS 筆）。"""
    found: list[tuple[str, str]] = []
    for bill_id in bills.extract_bill_ids(question):
        if len(found) >= bills.MAX_BILLS:
            break
        content = await asyncio.to_thread(bills.fetch_bill, bill_id)
        if content:
            found.append((bill_id, content))
    return found


def _augment(question: str, docs: list[tuple[str, str]]) -> str:
    """把議案全文置於問題之前，確保生成階段一定看得到。"""
    if not docs:
        return question
    blocks = "\n\n".join(f"【議案 {bid} 全文】\n{content}" for bid, content in docs)
    return f"{blocks}\n\n---\n請依據上列議案全文回答以下問題：\n{question}"


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
            if req.mode == "web":
                full_text = ""
                citations: list[dict] = []
                async for kind, value in openai_client.stream_web_answer(req.message):
                    if kind == "delta":
                        full_text += value
                        yield _sse("delta", {"text": value})
                    elif kind == "sources":
                        citations = value
                        yield _sse("citations", citations)
            else:
                direct = await _direct_bills(req.message)
                citations = await cloudflare.search(req.message)
                for bill_id, content in reversed(direct):
                    citations.insert(
                        0,
                        {
                            "doc_name": f"bills/{bill_id}.md",
                            "snippet": content[:200],
                            "similarity": 1.0,
                        },
                    )
                yield _sse("citations", citations)
                full_text = ""
                messages = [*history, {"role": "user", "content": _augment(req.message, direct)}]
                async for delta in cloudflare.stream_chat(messages):
                    full_text += delta
                    yield _sse("delta", {"text": delta})
            assistant = Message(
                thread_id=thread_id,
                role="assistant",
                content=full_text,
                citations=json.dumps(citations, ensure_ascii=False),
                source=req.mode,
            )
            db.add(assistant)
            db.query(Thread).filter(Thread.id == thread_id).update({"updated_at": datetime.now(UTC)})
            db.commit()
            yield _sse("done", {"thread_id": thread_id, "message_id": assistant.id, "source": req.mode})
        except Exception:
            logger.exception("chat stream failed", extra={"thread_id": thread_id})
            yield _sse("error", {"message": "系統暫時無法取得資料，請稍後再試"})

    return StreamingResponse(generate(), media_type="text/event-stream")
