"""Create an organization-aware administrator for local development.

Run from an activated backend environment after migrations:
    python ../scripts/seed_admin.py "Demo Authority" admin@example.com "Admin User" "change-me-now"
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Organization, User, UserRole  # noqa: E402


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: seed_admin.py <organization_name> <email> <full_name> <password>"
        )

    organization_name, email, full_name, password = sys.argv[1:]
    if len(password) < 12:
        raise SystemExit("Use a development password with at least 12 characters.")

    with SessionLocal() as db:
        organization = db.scalar(select(Organization).where(Organization.name == organization_name))
        if organization is None:
            organization = Organization(name=organization_name)
            db.add(organization)
            db.flush()
        if db.scalar(select(User).where(User.email == email.lower())):
            raise SystemExit(f"User already exists: {email}")
        db.add(
            User(
                organization_id=organization.id,
                email=email.lower(),
                full_name=full_name,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
        print(f"Created admin {email} in organization {organization_name}")


if __name__ == "__main__":
    main()
