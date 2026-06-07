import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import QueryLog, RagConversation, SavedAnswerNote


def _safe_filename(value: str) -> str:
    value = (value or "RAG Answer").strip()[:90]
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(". ")
    return value or "RAG Answer"


def _unique_path(directory: Path, title: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = _safe_filename(title)
    candidate = directory / f"{base}.md"
    index = 2
    while candidate.exists():
        candidate = directory / f"{base}-{index}.md"
        index += 1
    return candidate


def save_answer_note(
    db: Session,
    title: str,
    question: str,
    answer: str,
    sources: list[dict[str, Any]] | None = None,
    query_log_id: int | None = None,
    conversation_id: int | None = None,
    target_dir: str | None = None,
) -> dict[str, Any]:
    root = settings.kb_root
    relative_dir = target_dir or settings.saved_answers_dir
    if Path(relative_dir).is_absolute():
        raise ValueError("target_dir must be relative to the knowledge base root.")
    directory = (root / relative_dir).resolve()
    if not str(directory).startswith(str(root.resolve())):
        raise ValueError("target_dir is outside the knowledge base root.")

    path = _unique_path(directory, title)
    created = datetime.utcnow()
    source_lines = []
    for index, source in enumerate(sources or [], start=1):
        source_lines.append(f"- [{index}] {source.get('title') or source.get('file_path')} - `{source.get('file_path', '')}`")

    content = "\n".join(
        [
            "---",
            "type: rag-answer",
            f"created: {created.isoformat()}Z",
            f"source_query_log_id: {query_log_id or ''}",
            f"conversation_id: {conversation_id or ''}",
            "tags: [rag, answer]",
            "---",
            "",
            f"# {title}",
            "",
            "## Question",
            "",
            question.strip(),
            "",
            "## Answer",
            "",
            answer.strip(),
            "",
            "## Sources",
            "",
            "\n".join(source_lines) if source_lines else "- No sources recorded.",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    note = SavedAnswerNote(
        query_log_id=query_log_id,
        conversation_id=conversation_id,
        title=title,
        question=question,
        answer=answer,
        sources_json=json.dumps(sources or [], ensure_ascii=False),
        file_path=path.relative_to(root).as_posix(),
        created_at=created,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "file_path": note.file_path,
        "title": note.title,
        "created_at": note.created_at,
    }


def list_conversations(db: Session, limit: int = 50) -> list[RagConversation]:
    return db.query(RagConversation).order_by(RagConversation.updated_at.desc()).limit(min(limit, 100)).all()
