import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request

from app.config import settings


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9_\-]{2,}|[\u4e00-\u9fff]", lowered)
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    tokens.extend(cjk[index : index + 2] for index in range(max(0, len(cjk) - 1)))
    return tokens[:4000]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def local_hash_embedding(text: str, dimensions: int | None = None) -> list[float]:
    dims = dimensions or settings.embedding_dimensions
    vector = [0.0] * dims
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return _normalize(vector)


def openai_embedding(text: str) -> list[float]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    payload = {"model": model, "input": text[:12000]}
    request = urllib.request.Request(
        f"{settings.openai_base_url}/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"Embedding request failed: HTTP {exc.code} {body}") from exc
    return data["data"][0]["embedding"]


def embed_text(text: str) -> tuple[list[float], str, str]:
    provider = os.getenv("RAG_EMBEDDING_PROVIDER", settings.embedding_provider).strip().lower()
    if provider == "openai":
        try:
            vector = openai_embedding(text)
            return vector, "openai", os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        except RuntimeError:
            if not settings.embedding_fallback_to_local:
                raise
            return local_hash_embedding(text, 384), "local_hash_fallback", "local-hash-v1"
    return local_hash_embedding(text), "local_hash", settings.embedding_model


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def vector_to_json(vector: list[float]) -> str:
    return json.dumps([round(value, 6) for value in vector], ensure_ascii=False)


def vector_from_json(value: str) -> list[float]:
    try:
        data = json.loads(value or "[]")
        return [float(item) for item in data]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
