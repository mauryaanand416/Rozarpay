import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_lock = threading.Lock()
_state: dict = {"engine": None, "factory": None}


def reset_engine() -> None:
    with _lock:
        if _state["engine"] is not None:
            _state["engine"].dispose()
        _state["engine"] = None
        _state["factory"] = None


def _ensure() -> None:
    with _lock:
        if _state["engine"] is not None:
            return
        settings = get_settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        url = settings.database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        _state["engine"] = engine
        _state["factory"] = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    import app.db.models  # noqa: F401

    _ensure()
    Base.metadata.create_all(_state["engine"])


def new_session():
    _ensure()
    return _state["factory"]()


def get_db():
    db = new_session()
    try:
        yield db
    finally:
        db.close()
