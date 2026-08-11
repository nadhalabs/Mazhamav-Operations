from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import User
from app.schemas import LoginIn, UserOut
from app.core.rate_limit import enforce_login_rate_limit, record_login_failure

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, request: Request, db: Session = Depends(get_db)):
    enforce_login_rate_limit(request)
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        record_login_failure(request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone or password")
    settings = get_settings()
    response.set_cookie("access_token", create_access_token(str(user.id)), httponly=True, secure=settings.secure_cookies, samesite="lax", max_age=settings.access_token_minutes * 60, path="/")
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie("access_token", path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
