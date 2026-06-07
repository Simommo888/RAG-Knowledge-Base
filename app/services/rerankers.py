import json
import os
import urllib.error
import urllib.request
from typing import Any

from app.config import settings


def rerank_results(query: str, results: list[dict[str, Any]], strategy: str | None = None) -> list[dict[str, Any]]:
    strategy = (strategy or settings.rerank_strategy or "none").strip().lower()
    if strategy in {"", "none", "off"}:
        return results
    if strategy == "llm":
        return _llm_rerank(query, results)
    if strategy == "cross_encoder":
        return _cross_encoder_rerank(query, results)
    return results


def _llm_rerank(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not results:
        return results
    items = [
        {"index": index, "title": item.get("title", ""), "content": (item.get("content", "") or "")[:900]}
        for index, item in enumerate(results)
    ]
    payload = {
        "model": settings.openai_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Rank search results by relevance. Return JSON array of indexes only."},
            {"role": "user", "content": json.dumps({"query": query, "results": items}, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "[]")
        order = json.loads(content)
        ranked = [results[int(index)] for index in order if isinstance(index, int) or str(index).isdigit()]
        seen = {id(item) for item in ranked}
        ranked.extend(item for item in results if id(item) not in seen)
        return ranked
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError, ValueError, TypeError):
        return results


def _cross_encoder_rerank(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not results:
        return results
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        return results
    try:
        model_name = os.getenv("RAG_CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        model = CrossEncoder(model_name)
        pairs = [(query, item.get("content", "")) for item in results]
        scores = model.predict(pairs)
        ranked = list(zip(scores, results))
        ranked.sort(key=lambda item: float(item[0]), reverse=True)
        return [item for _, item in ranked]
    except Exception:  # noqa: BLE001
        return results
