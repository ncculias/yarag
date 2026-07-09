import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yarag.auth import router as auth_router
from yarag.chat import router as chat_router
from yarag.config import settings
from yarag.db import init_db
from yarag.threads import router as threads_router
from yarag.uploads import router as uploads_router

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(threads_router)
app.include_router(uploads_router)


def main() -> None:
    uvicorn.run("yarag.app:app", reload=True, port=8010)


if __name__ == "__main__":
    main()
