from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _sqlite_path_from_url(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.replace("sqlite:///", "", 1)).resolve()


db_path = _sqlite_path_from_url(settings.database_url)
if db_path:
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _lightweight_schema_upgrade(conn)
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    title,
                    file_path UNINDEXED,
                    heading,
                    content,
                    tokenize='unicode61'
                )
                """
            )
        )


def _lightweight_schema_upgrade(conn) -> None:
    tables = {
        row[0]
        for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    }
    if "rag_documents" in tables:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(rag_documents)")).fetchall()
        }
        if "document_type" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN document_type VARCHAR(40) DEFAULT 'markdown'"))
        if "index_status" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN index_status VARCHAR(40) DEFAULT 'indexed'"))
        if "error_message" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN error_message TEXT DEFAULT ''"))
        if "raw_content" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN raw_content TEXT DEFAULT ''"))
        if "source_kind" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN source_kind VARCHAR(40) DEFAULT 'file'"))
        if "original_name" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN original_name VARCHAR(500) DEFAULT ''"))
        if "created_at" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN created_at DATETIME"))
            conn.execute(text("UPDATE rag_documents SET created_at = indexed_at WHERE created_at IS NULL"))
        if "updated_at" not in columns:
            conn.execute(text("ALTER TABLE rag_documents ADD COLUMN updated_at DATETIME"))
            conn.execute(text("UPDATE rag_documents SET updated_at = indexed_at WHERE updated_at IS NULL"))
