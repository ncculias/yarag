from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from yarag.db import get_db
from yarag.models import User
from yarag.security import create_token, decode_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)

_CRED_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="帳號或密碼錯誤")
_TOKEN_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    display_name: str


class MeResponse(BaseModel):
    username: str
    display_name: str


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise _TOKEN_ERROR
    user_id = decode_token(cred.credentials)
    if user_id is None:
        raise _TOKEN_ERROR
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _TOKEN_ERROR
    return user


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == req.username))
    if user is None or not user.is_active or not verify_password(req.password, user.password_hash):
        raise _CRED_ERROR
    return LoginResponse(access_token=create_token(user.id), display_name=user.display_name)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, display_name=user.display_name)
