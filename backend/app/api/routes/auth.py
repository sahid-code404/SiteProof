from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.errors import SiteProofError
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise SiteProofError(401, "INVALID_CREDENTIALS", "Invalid email or password.")

    token = create_access_token(
        str(user.id),
        {"role": user.role.value, "organization_id": str(user.organization_id)},
    )
    return TokenResponse(access_token=token, user=_auth_user(user))


@router.get("/me", response_model=AuthUser)
def me(current_user: User = Depends(get_current_user)) -> AuthUser:
    return _auth_user(current_user)
