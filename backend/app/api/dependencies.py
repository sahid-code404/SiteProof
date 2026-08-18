from collections.abc import Callable
import uuid

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
    except jwt.InvalidTokenError as exc:
        raise SiteProofError(401, "INVALID_TOKEN", "Authentication token is invalid or expired.") from exc
    if not subject:
        raise SiteProofError(401, "INVALID_TOKEN", "Authentication token is invalid.")
    try:
        user_id = uuid.UUID(str(subject))
        user = db.get(User, user_id)
    except (TypeError, ValueError):
        user = None
    if user is None or not user.is_active:
        raise SiteProofError(401, "INVALID_TOKEN", "Authentication token is invalid.")
    return user


def require_roles(*roles: UserRole) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise SiteProofError(403, "FORBIDDEN", "You do not have permission for this action.")
        return current_user

    return dependency
