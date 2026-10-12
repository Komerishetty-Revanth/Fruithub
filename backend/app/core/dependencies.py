import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError("NOT_AUTHENTICATED", "Please log in first.", 401)
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise AppError("INVALID_TOKEN", "Your session is invalid or expired.", 401)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AppError("INVALID_TOKEN", "Your session is invalid or expired.", 401)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("ACCOUNT_DISABLED", "This account is not available.", 401)
    return user


def require_roles(*allowed: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise AppError("FORBIDDEN", "You do not have access to this resource.", 403)
        return user
    return checker


require_customer = require_roles(UserRole.CUSTOMER)
require_owner = require_roles(UserRole.OWNER)
require_admin = require_roles(UserRole.ADMIN)