"""Development helper for creating an initial administrator.

Run from backend environment:
    python ../scripts/seed_admin.py admin@example.com "Admin User" "change-me-now"
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User, UserRole


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: seed_admin.py <email> <full_name> <password>")

    email, full_name, password = sys.argv[1:]
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit(f"User already exists: {email}")
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(user)
        db.commit()
        print(f"Created admin: {email}")


if __name__ == "__main__":
    main()
