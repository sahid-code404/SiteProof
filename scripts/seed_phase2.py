"""Optional Phase 2 development seed data.

Passwords must be supplied through environment variables; this script refuses to run
outside development/test environments.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Inspection,
    InspectionPriority,
    InspectionStatus,
    InspectionType,
    Inspector,
    Organization,
    User,
    UserRole,
)

ORG_NAME = "SiteProof Demo Authority"
ADMIN_EMAIL = "admin@siteproof.local"
INSPECTORS = [
    ("Inspector One", "inspector1@siteproof.local", "SP-I001"),
    ("Inspector Two", "inspector2@siteproof.local", "SP-I002"),
    ("Inspector Three", "inspector3@siteproof.local", "SP-I003"),
]


def main() -> None:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        raise SystemExit("Refusing to seed outside a development/test environment.")
    admin_password = os.getenv("SITEPROOF_DEMO_ADMIN_PASSWORD")
    inspector_password = os.getenv("SITEPROOF_DEMO_INSPECTOR_PASSWORD")
    if not admin_password or not inspector_password:
        raise SystemExit(
            "Set SITEPROOF_DEMO_ADMIN_PASSWORD and SITEPROOF_DEMO_INSPECTOR_PASSWORD first."
        )
    if min(len(admin_password), len(inspector_password)) < 12:
        raise SystemExit("Demo passwords must be at least 12 characters.")

    with SessionLocal() as db:
        organization = db.scalar(select(Organization).where(Organization.name == ORG_NAME))
        if organization is None:
            organization = Organization(name=ORG_NAME)
            db.add(organization)
            db.flush()

        admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if admin is None:
            admin = User(
                organization_id=organization.id,
                email=ADMIN_EMAIL,
                full_name="SiteProof Demo Admin",
                hashed_password=hash_password(admin_password),
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.flush()

        for full_name, email, employee_code in INSPECTORS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    organization_id=organization.id,
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(inspector_password),
                    role=UserRole.INSPECTOR,
                )
                db.add(user)
                db.flush()
            profile = db.scalar(select(Inspector).where(Inspector.user_id == user.id))
            if profile is None:
                db.add(
                    Inspector(
                        organization_id=organization.id,
                        user_id=user.id,
                        employee_code=employee_code,
                        active=True,
                    )
                )

        existing = db.scalar(
            select(Inspection).where(
                Inspection.organization_id == organization.id,
                Inspection.title == "Verify repaired pothole",
            )
        )
        if existing is None:
            db.add(
                Inspection(
                    organization_id=organization.id,
                    title="Verify repaired pothole",
                    description="Confirm whether the reported road repair has been completed.",
                    inspection_type=InspectionType.ROAD_REPAIR,
                    status=InspectionStatus.DRAFT,
                    expected_latitude=22.5726,
                    expected_longitude=88.3639,
                    allowed_radius_meters=100,
                    location_name="Central Avenue",
                    location_address="Kolkata, West Bengal",
                    deadline=datetime.now(timezone.utc) + timedelta(days=1),
                    priority=InspectionPriority.HIGH,
                    instructions="Inspect the repaired road surface and surrounding area.",
                    created_by_user_id=admin.id,
                )
            )
        db.commit()
        print("Phase 2 development seed data is ready.")


if __name__ == "__main__":
    main()
