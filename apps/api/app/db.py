from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_add_columns() -> None:
    """Lightweight migrations for existing SQLite DBs."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(media)")).fetchall()
        }
        if cols and "file_size" not in cols:
            conn.execute(text("ALTER TABLE media ADD COLUMN file_size INTEGER DEFAULT 0"))
        if cols and "audio_storage_key" not in cols:
            conn.execute(text("ALTER TABLE media ADD COLUMN audio_storage_key VARCHAR(512) DEFAULT ''"))
        if cols and "progress" not in cols:
            conn.execute(text("ALTER TABLE media ADD COLUMN progress VARCHAR(255) DEFAULT ''"))


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _sqlite_add_columns()
