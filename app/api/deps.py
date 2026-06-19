from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    token = None
    if bearer:
        token = bearer.credentials
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    token = None
    if bearer:
        token = bearer.credentials
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    return db.query(User).filter(User.id == payload["sub"]).first()


def require_role(*allowed_roles: str):
    """Return a dependency that checks if the user has one of the allowed roles."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


require_owner = require_role("owner", "superadmin")
require_manager_or_above = require_role("owner", "manager", "superadmin")
require_dispatcher_or_above = require_role("owner", "dispatcher", "superadmin")
require_accountant_or_above = require_role("owner", "accountant", "superadmin")
