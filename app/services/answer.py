import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import QueryLog
from app.services.search import search


def _extractive_answer(question: str, sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "当前索引中没有找到足够相关的内容。请先重建索引，或换一个更具体的问题。"
    lines = ["基于本地知识库检索结果，我找到这些相关信息：", ""]
    for index, source in enumerate(sources[:5], start=1):
        snippet = " ".join(source["content"].split())[:320]
        title = source.get("heading") or source.get("title") or "相关片段"
        lines.append(f"{index}. {title}：{snippet} [{index}]")
    lines.append("")
    lines.append("来源：")
    for index, source in enumerate(sources[:5], start=1):
        lines.append(f"[{index}] {source['file_path']}")
    return "\n".join(lines)


def _llm_answer(question: str, sources: list[dict[str, Any]]) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    context = "\n\n".join(
        f"[{index}] {source['file_path']}\n标题：{source['title']}\n小节：{source.get('heading') or ''}\n内容：{source['content']}"
        for index, source in enumerate(sources, start=1)
    )
    payload = {
        "model": settings.openai_model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个个人知识库 RAG 问答助手。只能依据提供的资料回答。"
                    "使用中文，答案要结构清晰，关键结论后用 [1] 这样的来源编号标注。"
                    "如果资料不足，直接说明不足，不要编造。"
                ),
            },
            {"role": "user", "content": f"问题：{question}\n\n资料：\n{context}"},
        ],
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"LLM request failed: HTTP {exc.code} {body}") from exc
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("LLM returned an empty answer.")
    return answer, settings.openai_model


def ask(
    db: Session,
    question: str,
    top_k: int = 8,
    category: str = "all",
    use_llm: bool = True,
    retrieval_mode: str = "hybrid",
    query_expansion: bool | None = None,
    rerank: bool | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    sources = search(
        db,
        question,
        top_k=top_k,
        category=category,
        retrieval_mode=retrieval_mode,
        query_expansion=query_expansion,
        rerank=rerank,
    )
    warnings: list[str] = []
    llm_used = False
    model = ""

    if use_llm and sources:
        try:
            answer, model = _llm_answer(question, sources)
            llm_used = True
        except RuntimeError as exc:
            warnings.append(str(exc))
            warnings.append("已回退到本地摘录式回答。")
            answer = _extractive_answer(question, sources)
    else:
        answer = _extractive_answer(question, sources)
        if use_llm and not sources:
            warnings.append("没有找到可供 LLM 使用的来源片段。")

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    db.add(
        QueryLog(
            question=question,
            answer=answer,
            category=category,
            top_k=top_k,
            llm_used=1 if llm_used else 0,
            model=model,
            source_count=len(sources),
            latency_ms=latency_ms,
        )
    )
    db.commit()
    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "llm_used": llm_used,
        "model": model,
        "warnings": warnings,
    }
