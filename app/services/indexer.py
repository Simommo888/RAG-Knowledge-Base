import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import RagChunk, RagDocument, RagEmbedding
from app.services.chunker import chunk_markdown, title_from_markdown
from app.services.chroma_store import delete_vectors, reset_collection, upsert_vectors
from app.services.embeddings import embed_text, vector_to_json
from app.services.extractors import document_type, extract_text
from app.services.scanner import category_prefix, iter_source_files, relative_path, resolve_kb_root


def rebuild_fts(db: Session) -> None:
    db.execute(text("DELETE FROM rag_chunks_fts"))
    chunks = db.query(RagChunk).all()
    for chunk in chunks:
        db.execute(
            text(
                """
                INSERT INTO rag_chunks_fts(chunk_id, title, file_path, heading, content)
                VALUES (:chunk_id, :title, :file_path, :heading, :content)
                """
            ),
            {
                "chunk_id": chunk.id,
                "title": chunk.title,
                "file_path": chunk.file_path,
                "heading": chunk.heading,
                "content": chunk.content,
            },
        )


def index_knowledge_base(
    db: Session,
    kb_root: str | None = None,
    category: str = "all",
    rebuild: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    root = resolve_kb_root(kb_root)
    files = iter_source_files(root, category=category)
    if limit:
        files = files[:limit]
    current_paths = {relative_path(path, root) for path in files}
    prefix = category_prefix(category)

    if rebuild:
        chunk_ids = [row.id for row in db.query(RagChunk).all()] if not prefix else [
            row.id for row in db.query(RagChunk).filter(RagChunk.file_path.like(f"{prefix}%")).all()
        ]
        if chunk_ids:
            db.query(RagEmbedding).filter(RagEmbedding.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        if prefix:
            db.query(RagChunk).filter(RagChunk.file_path.like(f"{prefix}%")).delete(synchronize_session=False)
            db.query(RagDocument).filter(RagDocument.file_path.like(f"{prefix}%")).delete(synchronize_session=False)
        else:
            db.query(RagChunk).delete(synchronize_session=False)
            db.query(RagDocument).delete(synchronize_session=False)
        db.execute(text("DELETE FROM rag_chunks_fts"))
        db.commit()
        reset_collection()

    indexed_documents = 0
    indexed_chunks = 0
    skipped_files = 0
    deleted_documents = 0
    embedded_chunks = 0
    errors: list[str] = []

    if not rebuild:
        doc_query = db.query(RagDocument)
        if prefix:
            doc_query = doc_query.filter(RagDocument.file_path.like(f"{prefix}%"))
        for document in doc_query.all():
            if document.file_path not in current_paths:
                chunk_ids = [row.id for row in db.query(RagChunk).filter(RagChunk.document_id == document.id).all()]
                if chunk_ids:
                    db.query(RagEmbedding).filter(RagEmbedding.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
                    delete_vectors(chunk_ids)
                db.query(RagChunk).filter(RagChunk.document_id == document.id).delete(synchronize_session=False)
                db.query(RagDocument).filter(RagDocument.id == document.id).delete(synchronize_session=False)
                deleted_documents += 1
        db.execute(text("DELETE FROM rag_chunks_fts"))
        db.commit()

    for path in files:
        rel = relative_path(path, root)
        try:
            content = extract_text(path)
            if not content.strip():
                skipped_files += 1
                continue
            digest = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            stat = path.stat()
            existing = db.query(RagDocument).filter(RagDocument.file_path == rel).first()
            if existing and existing.content_hash == digest and not rebuild:
                skipped_files += 1
                continue

            document = existing or RagDocument(file_path=rel)
            document.title = title_from_markdown(path, content)
            document.document_type = document_type(path)
            document.content_hash = digest
            document.file_size = stat.st_size
            document.modified_at = datetime.fromtimestamp(stat.st_mtime)
            document.indexed_at = datetime.utcnow()
            document.updated_at = datetime.utcnow()
            document.raw_content = content
            document.source_kind = "file"
            document.original_name = path.name
            document.index_status = "indexed"
            document.error_message = ""
            if not existing:
                db.add(document)
                db.flush()
            else:
                old_chunk_ids = [row.id for row in db.query(RagChunk).filter(RagChunk.document_id == document.id).all()]
                if old_chunk_ids:
                    db.query(RagEmbedding).filter(RagEmbedding.chunk_id.in_(old_chunk_ids)).delete(synchronize_session=False)
                    delete_vectors(old_chunk_ids)
                db.query(RagChunk).filter(RagChunk.document_id == document.id).delete(synchronize_session=False)

            chunks = chunk_markdown(content)
            document.chunk_count = len(chunks)
            chroma_items: list[dict[str, Any]] = []
            for index, chunk in enumerate(chunks):
                row = RagChunk(
                    document_id=document.id,
                    file_path=rel,
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
                embedded_chunks += 1
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
                pass
            indexed_documents += 1
            indexed_chunks += len(chunks)
        except Exception as exc:  # noqa: BLE001
            existing = db.query(RagDocument).filter(RagDocument.file_path == rel).first()
            if existing:
                existing.index_status = "failed"
                existing.error_message = str(exc)
            errors.append(f"{rel}: {exc}")

    rebuild_fts(db)
    db.commit()
    return {
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "skipped_files": skipped_files,
        "deleted_documents": deleted_documents,
        "embedded_chunks": embedded_chunks,
        "errors": errors[:50],
    }
