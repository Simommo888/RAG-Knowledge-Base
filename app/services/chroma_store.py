from pathlib import Path
import shutil
from typing import Any

from app.config import settings

DEFAULT_SHARD_SIZE = 500


def chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


def _client():
    import chromadb

    path = Path(settings.chroma_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def _chroma_path() -> Path:
    path = Path(settings.chroma_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _shard_size() -> int:
    try:
        return max(100, int(getattr(settings, "chroma_shard_size", DEFAULT_SHARD_SIZE)))
    except (TypeError, ValueError):
        return DEFAULT_SHARD_SIZE


def _shard_name(shard_id: int) -> str:
    return f"{settings.chroma_collection}__shard_{shard_id:04d}"


def _shard_id_for_chunk(chunk_id: int) -> int:
    return max(0, int(chunk_id) // _shard_size())


def _collection_names(client) -> list[str]:
    try:
        collections = client.list_collections()
    except Exception:
        return []
    names: list[str] = []
    for item in collections:
        names.append(getattr(item, "name", str(item)))
    return names


def _managed_collection_names(client) -> list[str]:
    prefix = f"{settings.chroma_collection}__shard_"
    return [
        name
        for name in _collection_names(client)
        if name == settings.chroma_collection or name.startswith(prefix)
    ]


def collection(shard_id: int = 0):
    client = _client()
    return client.get_or_create_collection(name=_shard_name(shard_id))


def reset_collection() -> None:
    if not chroma_available():
        return
    try:
        client = _client()
        for name in _managed_collection_names(client):
            client.delete_collection(name=name)
    except Exception:
        path = _chroma_path()
        shutil.rmtree(path, ignore_errors=True)
    collection()


def hard_reset_collection() -> list[str]:
    errors: list[str] = []
    if not chroma_available():
        return ["chromadb is not installed."]
    path = _chroma_path()
    try:
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Failed to clear Chroma path {path}: {exc}")
    try:
        collection()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Failed to recreate Chroma collection: {exc}")
    return errors


def upsert_vectors(items: list[dict[str, Any]]) -> None:
    if not items or not chroma_available():
        return
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(_shard_id_for_chunk(int(item["chunk_id"])), []).append(item)

    for shard_id, shard_items in grouped.items():
        coll = collection(shard_id)
        coll.upsert(
            ids=[str(item["chunk_id"]) for item in shard_items],
            embeddings=[item["embedding"] for item in shard_items],
            documents=[item["content"] for item in shard_items],
            metadatas=[
                {
                    "chunk_id": int(item["chunk_id"]),
                    "document_id": int(item["document_id"]),
                    "file_path": item["file_path"],
                    "title": item["title"],
                    "heading": item.get("heading") or "",
                }
                for item in shard_items
            ],
        )


def delete_vectors(chunk_ids: list[int]) -> None:
    if not chunk_ids or not chroma_available():
        return
    grouped: dict[int, list[int]] = {}
    for chunk_id in chunk_ids:
        grouped.setdefault(_shard_id_for_chunk(chunk_id), []).append(chunk_id)
    for shard_id, ids in grouped.items():
        try:
            collection(shard_id).delete(ids=[str(chunk_id) for chunk_id in ids])
        except Exception:
            pass


def count_vectors() -> int:
    if not chroma_available():
        return 0
    try:
        client = _client()
        total = 0
        for name in _managed_collection_names(client):
            total += int(client.get_collection(name=name).count())
        return total
    except Exception:
        return 0


def query_vectors(query_embedding: list[float], top_k: int = 8, category_prefix: str = "") -> list[dict[str, Any]]:
    if not chroma_available():
        return []
    where = {"file_path": {"$contains": category_prefix}} if category_prefix else None
    client = _client()
    names = _managed_collection_names(client)
    rows: list[dict[str, Any]] = []
    if not names:
        return rows

    per_shard = max(top_k, 3)
    for name in names:
        try:
            coll = client.get_collection(name=name)
            if int(coll.count()) == 0:
                continue
            result = coll.query(
                query_embeddings=[query_embedding],
                n_results=min(per_shard, int(coll.count())),
                where=where,
                include=["metadatas", "documents", "distances"],
            )
        except Exception:
            continue

        ids = result.get("ids", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for raw_id, metadata, document, distance in zip(ids, metadatas, documents, distances):
            score = 1.0 / (1.0 + float(distance or 0))
            rows.append(
                {
                    "chunk_id": int(metadata.get("chunk_id") or raw_id),
                    "document_id": int(metadata.get("document_id") or 0),
                    "file_path": metadata.get("file_path") or "",
                    "title": metadata.get("title") or "",
                    "heading": metadata.get("heading") or "",
                    "content": document or "",
                    "score": score,
                }
            )

    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows[:top_k]
