import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RagChunk, RagEmbedding
from app.services.chroma_store import query_vectors
from app.services.embeddings import cosine_similarity, embed_text, vector_from_json
from app.services.query_expansion import QueryVariant, expand_query
from app.services.scanner import category_prefix


def _terms(query: str) -> list[str]:
    lowered = query.lower().strip()
    words = re.findall(r"[a-z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}", lowered)
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    words.extend(cjk[index : index + 2] for index in range(max(0, len(cjk) - 1)))
    if lowered:
        words.append(lowered)
    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return unique[:40]


def _safe_fts_query(query: str) -> str:
    parts = re.findall(r"[a-zA-Z0-9_\-]{2,}", query)
    return " OR ".join(parts[:12])


def _score(chunk: RagChunk, query: str, terms: list[str]) -> float:
    content = (chunk.content or "").lower()
    title = (chunk.title or "").lower()
    heading = (chunk.heading or "").lower()
    path = (chunk.file_path or "").lower()
    lowered = query.lower().strip()
    score = 0.0
    if lowered in content:
        score += 24
    if lowered in title:
        score += 10
    if lowered in heading:
        score += 8
    for term in terms:
        score += min(content.count(term), 8) * 3
        if term in title:
            score += 6
        if term in heading:
            score += 4
        if term in path:
            score += 2
    return score


def _to_result(
    chunk: RagChunk,
    score: float,
    keyword_score: float = 0,
    vector_score: float = 0,
    matched_query: str = "",
    expanded_queries: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "title": chunk.title,
        "file_path": chunk.file_path,
        "heading": chunk.heading,
        "content": chunk.content,
        "score": round(score, 2),
        "keyword_score": round(keyword_score, 2),
        "vector_score": round(vector_score, 4),
        "matched_query": matched_query,
        "expanded_queries": expanded_queries or [],
    }


def _keyword_candidates(db: Session, query: str, category: str = "all", limit: int = 5000) -> dict[int, tuple[RagChunk, float]]:
    query = query.strip()
    if not query:
        return {}

    prefix = category_prefix(category)
    candidate_ids: set[int] = set()
    fts_query = _safe_fts_query(query)
    if fts_query:
        rows = db.execute(
            text(
                """
                SELECT chunk_id FROM rag_chunks_fts
                WHERE rag_chunks_fts MATCH :query
                LIMIT 100
                """
            ),
            {"query": fts_query},
        ).fetchall()
        candidate_ids.update(int(row[0]) for row in rows)

    chunk_query = db.query(RagChunk)
    if prefix:
        chunk_query = chunk_query.filter(RagChunk.file_path.like(f"{prefix}%"))
    if candidate_ids:
        id_rows = chunk_query.filter(RagChunk.id.in_(candidate_ids)).all()
    else:
        id_rows = []

    # Always include lexical fallback because Chinese personal notes often need substring matching.
    fallback_rows = chunk_query.limit(5000).all()
    candidates = {chunk.id: chunk for chunk in id_rows + fallback_rows}
    terms = _terms(query)
    scored = [(_score(chunk, query, terms), chunk) for chunk in candidates.values()]
    scored = [(score, chunk) for score, chunk in scored if score > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    return {chunk.id: (chunk, score) for score, chunk in scored[:limit]}


def _expanded_keyword_candidates(
    db: Session,
    variants: list[QueryVariant],
    category: str = "all",
    limit: int = 5000,
) -> dict[int, tuple[RagChunk, float, str]]:
    combined: dict[int, tuple[RagChunk, float, str]] = {}
    for variant in variants:
        rows = _keyword_candidates(db, variant.text, category=category, limit=limit)
        for chunk_id, (chunk, score) in rows.items():
            weighted_score = score * variant.weight
            current = combined.get(chunk_id)
            if not current or weighted_score > current[1]:
                combined[chunk_id] = (chunk, weighted_score, variant.text)
    return combined


def _vector_candidates(db: Session, query: str, category: str = "all", limit: int = 5000) -> dict[int, tuple[RagChunk, float]]:
    prefix = category_prefix(category)
    query_vector, _, _ = embed_text(query)
    chroma_rows = query_vectors(query_vector, top_k=limit, category_prefix=prefix)
    if chroma_rows:
        ids = [row["chunk_id"] for row in chroma_rows]
        chunks = {chunk.id: chunk for chunk in db.query(RagChunk).filter(RagChunk.id.in_(ids)).all()}
        return {
            row["chunk_id"]: (chunks[row["chunk_id"]], float(row["score"]))
            for row in chroma_rows
            if row["chunk_id"] in chunks
        }

    rows = db.query(RagChunk, RagEmbedding).join(RagEmbedding, RagEmbedding.chunk_id == RagChunk.id)
    if prefix:
        rows = rows.filter(RagChunk.file_path.like(f"{prefix}%"))
    scored: list[tuple[float, RagChunk]] = []
    for chunk, embedding in rows.limit(limit).all():
        score = cosine_similarity(query_vector, vector_from_json(embedding.vector_json))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return {chunk.id: (chunk, score) for score, chunk in scored[:limit]}


def _rerank_boost(chunk: RagChunk, original_query: str, variants: list[QueryVariant]) -> float:
    title = (chunk.title or "").lower()
    heading = (chunk.heading or "").lower()
    content = (chunk.content or "").lower()
    path = (chunk.file_path or "").lower()
    original = original_query.lower().strip()
    boost = 0.0

    if original:
        if original in title:
            boost += 18
        if original in heading:
            boost += 10
        if original in path:
            boost += 8
        if original in content:
            boost += 8

    covered = 0
    for variant in variants[1:]:
        text = variant.text.lower()
        if not text:
            continue
        hit_title = text in title
        hit_heading = text in heading
        hit_path = text in path
        hit_content = text in content
        if hit_title or hit_heading or hit_path or hit_content:
            covered += 1
            boost += 8 * variant.weight if hit_title else 0
            boost += 5 * variant.weight if hit_heading else 0
            boost += 4 * variant.weight if hit_path else 0
            boost += 3 * variant.weight if hit_content else 0

    if covered >= 2:
        boost += 4
    return boost


def search(
    db: Session,
    query: str,
    top_k: int = 8,
    category: str = "all",
    retrieval_mode: str = "hybrid",
    query_expansion: bool | None = None,
    rerank: bool | None = None,
) -> list[dict[str, Any]]:
    retrieval_mode = retrieval_mode if retrieval_mode in {"keyword", "vector", "hybrid"} else "hybrid"
    expansion_enabled = settings.query_expansion_default if query_expansion is None else query_expansion
    rerank_enabled = settings.rerank_default if rerank is None else rerank
    variants = expand_query(query, enabled=expansion_enabled, max_variants=settings.max_query_expansions)
    expanded_queries = [variant.text for variant in variants[1:]]

    keyword = {} if retrieval_mode == "vector" and not expansion_enabled else _expanded_keyword_candidates(db, variants, category=category)
    vector: dict[int, tuple[RagChunk, float]] = {}
    vector_failed = False
    if retrieval_mode != "keyword":
        try:
            vector = _vector_candidates(db, query, category=category)
        except Exception:  # noqa: BLE001
            # Keep semantic search usable when OpenAI embeddings or Chroma are temporarily unavailable.
            vector_failed = True
            vector = {}
            if not keyword:
                keyword = _expanded_keyword_candidates(db, variants, category=category)

    combined_ids = set(keyword) | set(vector)
    scored: list[tuple[float, RagChunk, float, float, str]] = []
    for chunk_id in combined_ids:
        chunk = (keyword.get(chunk_id) or vector.get(chunk_id))[0]
        keyword_row = keyword.get(chunk_id)
        keyword_score = keyword_row[1] if keyword_row else 0.0
        matched_query = keyword_row[2] if keyword_row else ""
        vector_score = vector.get(chunk_id, (chunk, 0.0))[1]
        if retrieval_mode == "keyword":
            score = keyword_score
        elif retrieval_mode == "vector":
            score = keyword_score if vector_failed else vector_score * 100 + keyword_score * 0.35
        else:
            score = keyword_score if vector_failed else keyword_score + vector_score * 45
        if rerank_enabled:
            score += _rerank_boost(chunk, query, variants)
        scored.append((score, chunk, keyword_score, vector_score, matched_query))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        _to_result(chunk, score, keyword_score, vector_score, matched_query, expanded_queries)
        for score, chunk, keyword_score, vector_score, matched_query in scored[:top_k]
    ]
