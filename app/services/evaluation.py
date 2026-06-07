import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import RagEvalCase, RagEvalResult, RagEvalRun
from app.services.search import search


def create_eval_case(
    db: Session,
    query: str,
    expected_document: str,
    expected_text: str = "",
    category: str = "all",
    notes: str = "",
) -> RagEvalCase:
    row = RagEvalCase(
        query=query.strip(),
        expected_document=expected_document.strip(),
        expected_text=expected_text.strip(),
        category=category or "all",
        notes=notes or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def run_eval(
    db: Session,
    top_k: int = 8,
    retrieval_mode: str = "hybrid",
    query_expansion: bool = True,
    rerank: bool = False,
) -> dict[str, Any]:
    cases = db.query(RagEvalCase).order_by(RagEvalCase.id.asc()).all()
    eval_run = RagEvalRun(
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        query_expansion=1 if query_expansion else 0,
        rerank=1 if rerank else 0,
        case_count=len(cases),
    )
    db.add(eval_run)
    db.flush()
    results: list[dict[str, Any]] = []
    hit_count = 0

    for case in cases:
        rows = search(
            db,
            query=case.query,
            category=case.category or "all",
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            query_expansion=query_expansion,
            rerank=rerank,
        )
        expected = case.expected_document.lower().strip()
        rank = 0
        for index, row in enumerate(rows, start=1):
            haystack = f"{row.get('title', '')} {row.get('file_path', '')} {row.get('content', '')}".lower()
            if expected and expected in haystack:
                rank = index
                break
        hit = rank > 0
        hit_count += 1 if hit else 0
        payload = {
            "case_id": case.id,
            "query": case.query,
            "expected_document": case.expected_document,
            "hit": hit,
            "rank": rank,
            "top_results": [
                {
                    "title": row.get("title"),
                    "file_path": row.get("file_path"),
                    "score": row.get("score"),
                    "chunk_id": row.get("chunk_id"),
                }
                for row in rows
            ],
        }
        results.append(payload)
        db.add(
            RagEvalResult(
                run_id=eval_run.id,
                case_id=case.id,
                query=case.query,
                expected_document=case.expected_document,
                hit=1 if hit else 0,
                rank=rank,
                top_results_json=json.dumps(payload["top_results"], ensure_ascii=False),
            )
        )

    eval_run.hit_count = hit_count
    eval_run.hit_rate = round(hit_count / len(cases), 4) if cases else 0
    db.commit()
    return {
        "run_id": eval_run.id,
        "case_count": len(cases),
        "hit_count": hit_count,
        "hit_rate": eval_run.hit_rate,
        "results": results,
    }
