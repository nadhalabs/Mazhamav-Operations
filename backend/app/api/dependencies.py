import uuid
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User, UserRole


def current_user(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id = uuid.UUID(decode_access_token(access_token))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive or unavailable")
    return user


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")
        return user
    return dependency


owner_only = require_roles(UserRole.owner)
operations_viewer = require_roles(UserRole.owner, UserRole.manager)
staff_only = require_roles(UserRole.staff)
