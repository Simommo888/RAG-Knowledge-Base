from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now() -> datetime:
    return datetime.utcnow()


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    document_type: Mapped[str] = mapped_column(String(40), default="markdown")
    content_hash: Mapped[str] = mapped_column(String(80), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    index_status: Mapped[str] = mapped_column(String(40), default="indexed")
    error_message: Mapped[str] = mapped_column(Text, default="")
    raw_content: Mapped[str] = mapped_column(Text, default="")
    source_kind: Mapped[str] = mapped_column(String(40), default="file")
    original_name: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    heading: Mapped[str] = mapped_column(String(300), default="")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RagEmbedding(Base):
    __tablename__ = "rag_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("rag_chunks.id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="local_hash")
    model: Mapped[str] = mapped_column(String(160), default="local-hash-v1")
    dimensions: Mapped[int] = mapped_column(Integer, default=384)
    vector_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    top_k: Mapped[int] = mapped_column(Integer, default=8)
    category: Mapped[str] = mapped_column(String(120), default="all")
    llm_used: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(200), default="")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
