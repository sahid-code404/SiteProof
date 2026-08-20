from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.schemas.auth import LoginRequest

PASSWORD = "SiteProofSeed!42"


def load_seed_module():
    seed_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_phase2.py"
    spec = spec_from_file_location("siteproof_phase2_seed", seed_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase2_seed_emails_are_accepted_by_login_schema():
    seed = load_seed_module()
    emails = [seed.ADMIN_EMAIL, *(email for _, email, _ in seed.INSPECTORS)]

    for email in emails:
        payload = LoginRequest(email=email, password=PASSWORD)
        assert str(payload.email) == email
