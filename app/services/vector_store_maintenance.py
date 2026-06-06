from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import RagChunk, RagEmbedding
from app.services.chroma_store import chroma_available, count_vectors, hard_reset_collection, query_vectors, upsert_vectors
from app.services.embeddings import vector_from_json


def vector_store_health(db: Session) -> dict[str, Any]:
    errors: list[str] = []
    sqlite_embeddings = db.query(RagEmbedding).count()
    chroma_vectors = count_vectors()
    can_query = False

    sample = db.query(RagEmbedding).first()
    if sample:
        try:
            vector = vector_from_json(sample.vector_json)
            can_query = bool(query_vectors(vector, top_k=1))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    if not chroma_available():
        status = "unavailable"
        errors.append("chromadb is not installed.")
    elif sqlite_embeddings and chroma_vectors == 0:
        status = "needs_rebuild"
    elif sqlite_embeddings and chroma_vectors < sqlite_embeddings:
        status = "partial"
    else:
        status = "ok"

    return {
        "vector_store": settings.vector_store,
        "chroma_available": chroma_available(),
        "chroma_path": settings.chroma_path,
        "chroma_collection": settings.chroma_collection,
        "sqlite_embeddings": sqlite_embeddings,
        "chroma_vectors": chroma_vectors,
        "can_query": can_query,
        "status": status,
        "errors": errors,
    }


def rebuild_chroma_from_sqlite(db: Session, batch_size: int = 200) -> dict[str, Any]:
    errors: list[str] = []
    if not chroma_available():
        return {
            "vector_store": settings.vector_store,
            "reset_done": False,
            "source_embeddings": db.query(RagEmbedding).count(),
            "upserted_vectors": 0,
            "skipped_vectors": 0,
            "target_dimensions": 0,
            "final_count": 0,
            "batches": 0,
            "status": "unavailable",
            "errors": ["chromadb is not installed."],
        }

    source_embeddings = db.query(RagEmbedding).count()
    dimensions = Counter(
        int(row[0] or 0)
        for row in db.query(RagEmbedding.dimensions).all()
        if int(row[0] or 0) > 0
    )
    target_dimensions = dimensions.most_common(1)[0][0] if dimensions else 0

    errors.extend(hard_reset_collection())
    if errors:
        return {
            "vector_store": settings.vector_store,
            "reset_done": False,
            "source_embeddings": source_embeddings,
            "upserted_vectors": 0,
            "skipped_vectors": source_embeddings,
            "target_dimensions": target_dimensions,
            "final_count": count_vectors(),
            "batches": 0,
            "status": "failed",
            "errors": errors,
        }

    rows = (
        db.query(RagChunk, RagEmbedding)
        .join(RagEmbedding, RagEmbedding.chunk_id == RagChunk.id)
        .filter(RagEmbedding.dimensions == target_dimensions)
        .order_by(RagChunk.id.asc())
        .all()
    )

    upserted = 0
    batches = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        items: list[dict[str, Any]] = []
        for chunk, embedding in batch:
            vector = vector_from_json(embedding.vector_json)
            if not vector or len(vector) != target_dimensions:
                continue
            items.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "file_path": chunk.file_path,
                    "title": chunk.title,
                    "heading": chunk.heading,
                    "content": chunk.content,
                    "embedding": vector,
                }
            )
        if not items:
            continue
        try:
            upsert_vectors(items)
            upserted += len(items)
            batches += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Batch {batches + 1} failed: {exc}")
            break

    final_count = count_vectors()
    status = "ok" if not errors and final_count == upserted else "partial" if upserted else "failed"
    return {
        "vector_store": settings.vector_store,
        "reset_done": True,
        "source_embeddings": source_embeddings,
        "upserted_vectors": upserted,
        "skipped_vectors": max(0, source_embeddings - upserted),
        "target_dimensions": target_dimensions,
        "final_count": final_count,
        "batches": batches,
        "status": status,
        "errors": errors[:20],
    }
