import os
import shutil
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "siteproof-test.db"
TEST_STORAGE = Path(__file__).resolve().parent / "siteproof-test-evidence"
TEST_DATABASE_URL = os.getenv("SITEPROOF_TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    if TEST_DB.exists():
        TEST_DB.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["JWT_SECRET"] = "test-secret-key-for-siteproof-32-bytes-minimum"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = str(TEST_STORAGE)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)
    TEST_STORAGE.mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
