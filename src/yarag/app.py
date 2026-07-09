import uvicorn
from fastapi import FastAPI

from yarag.auth import router as auth_router
from yarag.chat import router as chat_router
from yarag.threads import router as threads_router
from yarag.uploads import router as uploads_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(threads_router)
app.include_router(chat_router)
app.include_router(uploads_router)


def main() -> None:
    uvicorn.run("yarag.app:app", reload=True)


if __name__ == "__main__":
    main()
