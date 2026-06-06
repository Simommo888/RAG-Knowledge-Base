import time

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import CATEGORY_DIRS, settings
from app.database import get_db
from app.models import QueryLog, RagChunk, RagDocument, RagEmbedding
from app.schemas import (
    ApiKeySettingsRead,
    ApiKeySettingsUpdate,
    AskRequest,
    AskResponse,
    IndexRequest,
    IndexResponse,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentPage,
    KnowledgeDocumentRead,
    KnowledgeDocumentSearchResult,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    QueryExpansionRequest,
    QueryExpansionResponse,
    QueryLogRead,
    SearchRequest,
    SearchResult,
    StatsResponse,
    VectorStoreHealth,
    VectorStoreRebuildResponse,
)
from app.services.api_key_settings import get_api_key_settings, update_api_key_settings
from app.services.answer import ask
from app.services.chroma_store import count_vectors
from app.services.indexer import index_knowledge_base
from app.services.knowledge_documents import (
    create_document,
    delete_document,
    get_document_detail,
    list_documents,
    semantic_document_search,
    update_document,
)
from app.services.query_expansion import expand_query
from app.services.search import search
from app.services.vector_store_maintenance import rebuild_chroma_from_sqlite, vector_store_health

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)) -> dict:
    return {
        "kb_root": str(settings.kb_root),
        "documents": db.query(RagDocument).count(),
        "chunks": db.query(RagChunk).count(),
        "embeddings": db.query(RagEmbedding).count(),
        "last_indexed_at": db.query(func.max(RagDocument.indexed_at)).scalar(),
        "categories": CATEGORY_DIRS,
        "document_types": dict(
            db.query(RagDocument.document_type, func.count(RagDocument.id)).group_by(RagDocument.document_type).all()
        ),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_providers": dict(
            db.query(RagEmbedding.provider, func.count(RagEmbedding.id)).group_by(RagEmbedding.provider).all()
        ),
        "vector_store": settings.vector_store,
        "chroma_collection": settings.chroma_collection,
        "chroma_vectors": count_vectors(),
    }


@router.get("/api-key", response_model=ApiKeySettingsRead)
def api_key_settings() -> dict:
    return get_api_key_settings()


@router.put("/api-key", response_model=ApiKeySettingsRead)
def save_api_key_settings(payload: ApiKeySettingsUpdate) -> dict:
    try:
        return update_api_key_settings(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/vector-store/health", response_model=VectorStoreHealth)
def vector_store_health_check(db: Session = Depends(get_db)) -> dict:
    return vector_store_health(db)


@router.post("/vector-store/rebuild", response_model=VectorStoreRebuildResponse)
def rebuild_vector_store(db: Session = Depends(get_db)) -> dict:
    return rebuild_chroma_from_sqlite(db)


@router.get("/knowledge", response_model=KnowledgeDocumentPage)
def knowledge_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search_text: str = Query(default=""),
    source_kind: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict:
    return list_documents(db, page=page, page_size=page_size, query=search_text, source_kind=source_kind)


@router.post("/knowledge", response_model=KnowledgeDocumentRead)
def create_knowledge_document(payload: KnowledgeDocumentCreate, db: Session = Depends(get_db)) -> object:
    try:
        return create_document(
            db,
            title=payload.title,
            content=payload.content,
            source_kind=payload.source_kind or "manual",
            original_name=payload.original_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"知识内容索引失败：{exc}") from exc


@router.post("/knowledge/search", response_model=list[KnowledgeDocumentSearchResult])
def search_knowledge_documents(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> list[dict]:
    return semantic_document_search(
        db,
        query=payload.query,
        top_k=payload.top_k,
        retrieval_mode=payload.retrieval_mode,
        query_expansion=payload.query_expansion,
        rerank=payload.rerank,
    )


@router.post("/knowledge/search/stream")
def stream_knowledge_document_search_fixed(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    try:
        results = semantic_document_search(
            db,
            query=payload.query,
            top_k=payload.top_k,
            retrieval_mode=payload.retrieval_mode,
            query_expansion=payload.query_expansion,
            rerank=payload.rerank,
        )
        error_text = ""
    except Exception as exc:  # noqa: BLE001
        results = []
        error_text = f"检索时发生异常，已停止本次流式返回：{exc}"

    def generate():
        if error_text:
            text = error_text
        elif not results:
            text = "没有找到相关知识。可以换一个更具体的问题，或先上传并索引知识内容。"
        else:
            lines = [
                f"根据你的查询“{payload.query}”，找到 {len(results)} 条相关知识：",
                "",
            ]
            for index, item in enumerate(results, start=1):
                snippet = " ".join(str(item.get("snippet", "")).split())[:180]
                lines.extend(
                    [
                        f"{index}. 《{item.get('title', '')}》",
                        f"   相关度：{item.get('score', 0)}",
                        f"   路径：{item.get('file_path', '')}",
                        f"   命中片段：{item.get('matched_chunks', 0)} 个",
                        f"   摘要：{snippet}",
                        "",
                    ]
                )
            text = "\n".join(lines)

        for char in text:
            yield char.encode("utf-8")
            time.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.post("/knowledge/search/stream")
def stream_knowledge_document_search_clean(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    results = semantic_document_search(
        db,
        query=payload.query,
        top_k=payload.top_k,
        retrieval_mode=payload.retrieval_mode,
        query_expansion=payload.query_expansion,
        rerank=payload.rerank,
    )

    def generate():
        if not results:
            text = "没有找到相关知识库。可以尝试换一个更具体的关键词，或先上传并索引知识内容。"
        else:
            lines = [
                f"根据你的查询“{payload.query}”，找到 {len(results)} 个相关知识库：",
                "",
            ]
            for index, item in enumerate(results, start=1):
                snippet = " ".join(str(item.get("snippet", "")).split())[:180]
                lines.extend(
                    [
                        f"{index}. 《{item.get('title', '')}》",
                        f"   相关度：{item.get('score', 0)}",
                        f"   路径：{item.get('file_path', '')}",
                        f"   命中片段：{item.get('matched_chunks', 0)} 个",
                        f"   摘要：{snippet}",
                        "",
                    ]
                )
            text = "\n".join(lines)

        for char in text:
            yield char.encode("utf-8")
            time.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.post("/knowledge/search/stream-legacy")
def stream_knowledge_document_search(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    results = semantic_document_search(
        db,
        query=payload.query,
        top_k=payload.top_k,
        retrieval_mode=payload.retrieval_mode,
        query_expansion=payload.query_expansion,
        rerank=payload.rerank,
    )

    def generate():
        if not results:
            text = "没有找到相关知识库。可以尝试换一个更具体的关键词，或先上传/索引知识内容。"
        else:
            lines = [
                f"根据你的查询“{payload.query}”，找到 {len(results)} 个相关知识库：",
                "",
            ]
            for index, item in enumerate(results, start=1):
                lines.extend(
                    [
                        f"{index}. 《{item['title']}》",
                        f"   相关度：{item['score']}",
                        f"   路径：{item['file_path']}",
                        f"   命中片段：{item['matched_chunks']} 个",
                        f"   摘要：{' '.join(item['snippet'].split())[:180]}",
                        "",
                    ]
                )
            text = "\n".join(lines)
        for char in text:
            yield char.encode("utf-8")
            time.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.get("/knowledge/{document_id}", response_model=KnowledgeDocumentDetail)
def knowledge_document_detail(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = get_document_detail(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="知识条目不存在。")
    return document


@router.put("/knowledge/{document_id}", response_model=KnowledgeDocumentRead)
def update_knowledge_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    db: Session = Depends(get_db),
) -> object:
    try:
        document = update_document(db, document_id=document_id, title=payload.title, content=payload.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"知识内容更新索引失败：{exc}") from exc
    if not document:
        raise HTTPException(status_code=404, detail="知识条目不存在。")
    return document


@router.delete("/knowledge/{document_id}")
def delete_knowledge_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    if not delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="知识条目不存在。")
    return {"ok": True, "deleted_id": document_id}


@router.post("/index", response_model=IndexResponse)
def index(payload: IndexRequest, db: Session = Depends(get_db)) -> dict:
    return index_knowledge_base(
        db,
        kb_root=payload.kb_root,
        category=payload.category,
        rebuild=payload.rebuild,
        limit=payload.limit,
    )


@router.post("/search", response_model=list[SearchResult])
def rag_search(payload: SearchRequest, db: Session = Depends(get_db)) -> list[dict]:
    return search(
        db,
        query=payload.query,
        top_k=payload.top_k,
        category=payload.category,
        retrieval_mode=payload.retrieval_mode,
        query_expansion=payload.query_expansion,
        rerank=payload.rerank,
    )


@router.post("/ask", response_model=AskResponse)
def rag_ask(payload: AskRequest, db: Session = Depends(get_db)) -> dict:
    return ask(
        db,
        question=payload.question,
        top_k=payload.top_k,
        category=payload.category,
        use_llm=payload.use_llm,
        retrieval_mode=payload.retrieval_mode,
        query_expansion=payload.query_expansion,
        rerank=payload.rerank,
    )


@router.post("/query/expand", response_model=QueryExpansionResponse)
def expand_query_preview(payload: QueryExpansionRequest) -> dict:
    variants = expand_query(payload.query)
    return {"query": payload.query, "variants": [variant.text for variant in variants]}


@router.get("/history", response_model=list[QueryLogRead])
def history(limit: int = 30, db: Session = Depends(get_db)) -> list[QueryLog]:
    return db.query(QueryLog).order_by(QueryLog.created_at.desc()).limit(min(limit, 100)).all()
