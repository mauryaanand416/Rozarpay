import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="sentipay-tests-"))
TEST_DB = _TMP_DIR / "test.db"

os.environ["SENTINELPAY_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"


def _reset_db():
    from app.db.base import reset_engine

    reset_engine()
    if TEST_DB.exists():
        TEST_DB.unlink()


import pytest


@pytest.fixture()
def fresh_db():
    from app.db.base import init_db, new_session

    _reset_db()
    init_db()
    yield new_session
    _reset_db()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.db.base import init_db
    from app.main import app

    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers():
    return {"X-API-Key": "test-key"}


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
