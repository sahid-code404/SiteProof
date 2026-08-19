from sqlalchemy import select

from app.core.security import hash_password
from app.models import Inspector, Organization, User, UserRole


OLD_PASSWORD = "LegacySeedPass!42"
NEW_ADMIN_PASSWORD = "Admin123456!"
NEW_INSPECTOR_PASSWORD = "Inspector123456!"


def test_seed_migrates_legacy_local_accounts_without_duplicate_employee_codes(
    client, db, monkeypatch
):
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    seed_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_phase2.py"
    spec = spec_from_file_location("siteproof_phase2_seed_migration", seed_path)
    assert spec is not None
    assert spec.loader is not None
    seed = module_from_spec(spec)
    spec.loader.exec_module(seed)

    organization = Organization(name=seed.ORG_NAME)
    db.add(organization)
    db.flush()

    legacy_admin = User(
        organization_id=organization.id,
        email=seed.LEGACY_ADMIN_EMAIL,
        full_name="SiteProof Demo Admin",
        hashed_password=hash_password(OLD_PASSWORD),
        role=UserRole.ADMIN,
    )
    db.add(legacy_admin)
    db.flush()

    profile_ids = {}
    for full_name, new_email, employee_code in seed.INSPECTORS:
        legacy_email = seed.LEGACY_INSPECTOR_EMAILS[employee_code]
        user = User(
            organization_id=organization.id,
            email=legacy_email,
            full_name=full_name,
            hashed_password=hash_password(OLD_PASSWORD),
            role=UserRole.INSPECTOR,
        )
        db.add(user)
        db.flush()
        profile = Inspector(
            organization_id=organization.id,
            user_id=user.id,
            employee_code=employee_code,
            active=True,
        )
        db.add(profile)
        db.flush()
        profile_ids[employee_code] = profile.id

    db.commit()

    monkeypatch.setenv("SITEPROOF_DEMO_ADMIN_PASSWORD", NEW_ADMIN_PASSWORD)
    monkeypatch.setenv("SITEPROOF_DEMO_INSPECTOR_PASSWORD", NEW_INSPECTOR_PASSWORD)

    seed.main()
    seed.main()  # A second run must remain idempotent.
    db.expire_all()

    assert db.scalar(select(User).where(User.email == seed.LEGACY_ADMIN_EMAIL)) is None
    for legacy_email in seed.LEGACY_INSPECTOR_EMAILS.values():
        assert db.scalar(select(User).where(User.email == legacy_email)) is None

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": seed.ADMIN_EMAIL, "password": NEW_ADMIN_PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text

    for _, email, employee_code in seed.INSPECTORS:
        inspector_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": NEW_INSPECTOR_PASSWORD},
        )
        assert inspector_login.status_code == 200, inspector_login.text
        profiles = db.scalars(
            select(Inspector).where(
                Inspector.organization_id == organization.id,
                Inspector.employee_code == employee_code,
            )
        ).all()
        assert len(profiles) == 1
        assert profiles[0].id == profile_ids[employee_code]
