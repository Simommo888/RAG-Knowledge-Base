import hashlib
import math
import re
import time
from datetime import datetime
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models import RagChunk, RagDocument, RagEmbedding
from app.services.chunker import chunk_markdown
from app.services.chroma_store import delete_vectors, upsert_vectors
from app.services.embeddings import embed_text, vector_to_json
from app.services.indexer import rebuild_fts
from app.services.search import search


def _safe_slug(value: str) -> str:
    value = value.strip()[:80] or "knowledge"
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", "-", value).strip(".-")
    return value or "knowledge"


def _manual_path(title: str, original_name: str = "") -> str:
    base = _safe_slug(original_name.rsplit(".", 1)[0] if original_name else title)
    suffix = int(time.time() * 1000)
    return f"manual/{base}-{suffix}.txt"


def _document_content(db: Session, document: RagDocument) -> str:
    if document.raw_content:
        return document.raw_content
    chunks = (
        db.query(RagChunk)
        .filter(RagChunk.document_id == document.id)
        .order_by(RagChunk.chunk_index.asc())
        .all()
    )
    return "\n\n".join(chunk.content for chunk in chunks)


def _delete_document_index(db: Session, document_id: int) -> list[int]:
    old_chunks = db.query(RagChunk).filter(RagChunk.document_id == document_id).all()
    old_chunk_ids = [chunk.id for chunk in old_chunks]
    if old_chunk_ids:
        db.query(RagEmbedding).filter(RagEmbedding.chunk_id.in_(old_chunk_ids)).delete(synchronize_session=False)
        db.query(RagChunk).filter(RagChunk.id.in_(old_chunk_ids)).delete(synchronize_session=False)
        delete_vectors(old_chunk_ids)
    return old_chunk_ids


def _index_document_content(db: Session, document: RagDocument, content: str) -> int:
    _delete_document_index(db, document.id)
    chunks = chunk_markdown(content)
    document.chunk_count = len(chunks)
    chroma_items: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks):
        row = RagChunk(
            document_id=document.id,
            file_path=document.file_path,
            title=document.title,
            heading=chunk["heading"],
            chunk_index=index,
            content=chunk["content"],
            token_estimate=max(1, len(chunk["content"]) // 4),
        )
        db.add(row)
        db.flush()
        vector, provider, model = embed_text(f"{row.title}\n{row.heading}\n{row.content}")
        db.add(
            RagEmbedding(
                chunk_id=row.id,
                provider=provider,
                model=model,
                dimensions=len(vector),
                vector_json=vector_to_json(vector),
            )
        )
        chroma_items.append(
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "file_path": row.file_path,
                "title": row.title,
                "heading": row.heading,
                "content": row.content,
                "embedding": vector,
            }
        )
        db.execute(
            text(
                """
                INSERT INTO rag_chunks_fts(chunk_id, title, file_path, heading, content)
                VALUES (:chunk_id, :title, :file_path, :heading, :content)
                """
            ),
            {
                "chunk_id": row.id,
                "title": row.title,
                "file_path": row.file_path,
                "heading": row.heading,
                "content": row.content,
            },
        )

    try:
        upsert_vectors(chroma_items)
    except Exception:
        # SQLite embeddings remain the durable fallback if the local Chroma HNSW index is unavailable.
        pass
    return len(chunks)


def list_documents(db: Session, page: int = 1, page_size: int = 10, query: str = "", source_kind: str = "") -> dict:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    rows = db.query(RagDocument)
    if query:
        pattern = f"%{query.strip()}%"
        rows = rows.filter(
            or_(
                RagDocument.title.like(pattern),
                RagDocument.file_path.like(pattern),
                RagDocument.original_name.like(pattern),
            )
        )
    if source_kind:
        rows = rows.filter(RagDocument.source_kind == source_kind)
    total = rows.count()
    items = (
        rows.order_by(RagDocument.updated_at.desc().nullslast(), RagDocument.indexed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


def get_document_detail(db: Session, document_id: int) -> dict | None:
    document = db.query(RagDocument).filter(RagDocument.id == document_id).first()
    if not document:
        return None
    return {
        "id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "document_type": document.document_type,
        "source_kind": document.source_kind,
        "original_name": document.original_name,
        "file_size": document.file_size,
        "chunk_count": document.chunk_count,
        "index_status": document.index_status,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "indexed_at": document.indexed_at,
        "content": _document_content(db, document),
        "error_message": document.error_message,
    }


def create_document(db: Session, title: str, content: str, source_kind: str = "manual", original_name: str = "") -> RagDocument:
    now = datetime.utcnow()
    document = RagDocument(
        file_path=_manual_path(title, original_name),
        title=title.strip(),
        document_type="txt",
        source_kind=source_kind or "manual",
        original_name=original_name or "",
        raw_content=content,
        content_hash=hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest(),
        file_size=len(content.encode("utf-8", errors="ignore")),
        modified_at=now,
        indexed_at=now,
        created_at=now,
        updated_at=now,
        index_status="indexed",
        error_message="",
    )
    db.add(document)
    db.flush()
    try:
        _index_document_content(db, document, content)
    except Exception as exc:  # noqa: BLE001
        document.index_status = "failed"
        document.error_message = str(exc)
        raise
    rebuild_fts(db)
    db.commit()
    db.refresh(document)
    return document


def update_document(db: Session, document_id: int, title: str | None = None, content: str | None = None) -> RagDocument | None:
    document = db.query(RagDocument).filter(RagDocument.id == document_id).first()
    if not document:
        return None
    if title is not None:
        document.title = title.strip()
    if content is not None:
        document.raw_content = content
        document.content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
        document.file_size = len(content.encode("utf-8", errors="ignore"))
        document.modified_at = datetime.utcnow()
        document.indexed_at = datetime.utcnow()
        document.index_status = "indexed"
        document.error_message = ""
        _index_document_content(db, document, content)
    else:
        for chunk in db.query(RagChunk).filter(RagChunk.document_id == document.id).all():
            chunk.title = document.title
    document.updated_at = datetime.utcnow()
    rebuild_fts(db)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document_id: int) -> bool:
    document = db.query(RagDocument).filter(RagDocument.id == document_id).first()
    if not document:
        return False
    _delete_document_index(db, document.id)
    db.delete(document)
    rebuild_fts(db)
    db.commit()
    return True


def semantic_document_search(
    db: Session,
    query: str,
    top_k: int = 8,
    retrieval_mode: str = "hybrid",
    query_expansion: bool | None = None,
    rerank: bool | None = None,
) -> list[dict]:
    chunks = search(
        db,
        query=query,
        top_k=min(max(top_k * 4, top_k), 30),
        category="all",
        retrieval_mode=retrieval_mode,
        query_expansion=query_expansion,
        rerank=rerank,
    )
    grouped: dict[int, dict] = {}
    for chunk in chunks:
        current = grouped.get(chunk["document_id"])
        if not current:
            document = db.query(RagDocument).filter(RagDocument.id == chunk["document_id"]).first()
            grouped[chunk["document_id"]] = {
                "document_id": chunk["document_id"],
                "title": chunk["title"],
                "file_path": chunk["file_path"],
                "document_type": document.document_type if document else "",
                "source_kind": document.source_kind if document else "",
                "score": chunk["score"],
                "best_heading": chunk.get("heading") or "",
                "snippet": chunk["content"][:420],
                "chunk_count": document.chunk_count if document else 0,
                "matched_chunks": 1,
                "matched_query": chunk.get("matched_query") or "",
                "expanded_queries": chunk.get("expanded_queries") or [],
            }
        else:
            current["score"] = max(current["score"], chunk["score"])
            current["matched_chunks"] += 1
            if not current.get("matched_query") and chunk.get("matched_query"):
                current["matched_query"] = chunk.get("matched_query") or ""
    return sorted(grouped.values(), key=lambda item: item["score"], reverse=True)[:top_k]
