import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import CATEGORY_DIRS, settings
from app.database import get_db
from app.models import QueryLog, RagDocument, RagEmbedding, RagEvalCase, RagConversation, RagConversationMessage
from app.schemas import (
    ApiKeySettingsRead,
    ApiKeySettingsUpdate,
    AskRequest,
    AskResponse,
    ConversationRead,
    EvalCaseCreate,
    EvalCaseRead,
    EvalRunRequest,
    EvalRunResponse,
    GraphEdge,
    GraphNode,
    IndexRequest,
    IndexResponse,
    IncrementalIndexResponse,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentPage,
    KnowledgeDocumentRead,
    KnowledgeDocumentSearchResult,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    ObsidianGraphResponse,
    QueryExpansionRequest,
    QueryExpansionResponse,
    QueryLogRead,
    RuntimeStatus,
    SaveAnswerRequest,
    SaveAnswerResponse,
    SearchRequest,
    SearchResult,
    StatsResponse,
    VectorStoreHealth,
    VectorStoreRebuildResponse,
)
from app.services.answer import ask
from app.services.api_key_settings import get_api_key_settings, update_api_key_settings
from app.services.chroma_store import count_vectors
from app.services.evaluation import create_eval_case, run_eval
from app.services.index_runtime import (
    run_incremental_index,
    scheduler_status,
    start_file_watcher,
    start_scheduler,
    stop_file_watcher,
    stop_scheduler,
    watcher_status,
)
from app.services.indexer import index_knowledge_base
from app.services.knowledge_documents import (
    create_document,
    delete_document,
    get_document_detail,
    list_documents,
    semantic_document_search,
    update_document,
)
from app.services.notes import list_conversations, save_answer_note
from app.services.obsidian_graph import build_obsidian_graph
from app.services.query_expansion import expand_query
from app.services.search import search
from app.services.vector_store_maintenance import rebuild_chroma_from_sqlite, vector_store_health

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)) -> dict:
    return {
        "kb_root": str(settings.kb_root),
        "documents": db.query(RagDocument).count(),
        "chunks": db.query(RagDocument).with_entities(func.sum(RagDocument.chunk_count)).scalar() or 0,
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
        raise HTTPException(status_code=400, detail=f"Knowledge indexing failed: {exc}") from exc


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
def stream_knowledge_document_search(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    try:
        results = semantic_document_search(
            db,
            query=payload.query,
            top_k=payload.top_k,
            retrieval_mode=payload.retrieval_mode,
            query_expansion=payload.query_expansion,
            rerank=payload.rerank,
        )
        if not results:
            text = "没有找到足够相关的知识库内容。"
        else:
            lines = [f"根据查询「{payload.query}」，找到 {len(results)} 个相关知识库：", ""]
            for index, item in enumerate(results, start=1):
                snippet = " ".join(str(item.get("snippet", "")).split())[:180]
                lines.extend(
                    [
                        f"{index}. 《{item.get('title', '')}》",
                        f"   相关度：{item.get('score', 0)}",
                        f"   路径：{item.get('file_path', '')}",
                        f"   命中片段：{item.get('matched_chunks', 0)}",
                        f"   摘要：{snippet}",
                        "",
                    ]
                )
            text = "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        text = f"检索失败：{exc}"

    def generate():
        for char in text:
            yield char.encode("utf-8")
            time.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.get("/knowledge/{document_id}", response_model=KnowledgeDocumentDetail)
def knowledge_document_detail(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = get_document_detail(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
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
        raise HTTPException(status_code=400, detail=f"Knowledge update/indexing failed: {exc}") from exc
    if not document:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return document


@router.delete("/knowledge/{document_id}")
def delete_knowledge_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    if not delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
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


@router.post("/index/incremental", response_model=IncrementalIndexResponse)
def index_incremental(category: str = "all", limit: int | None = None) -> dict:
    return run_incremental_index(category=category, limit=limit)


@router.post("/index/scheduler/start", response_model=RuntimeStatus)
def start_incremental_scheduler(interval_seconds: int | None = None) -> dict:
    return start_scheduler(interval_seconds=interval_seconds)


@router.post("/index/scheduler/stop", response_model=RuntimeStatus)
def stop_incremental_scheduler() -> dict:
    return stop_scheduler()


@router.get("/index/scheduler/status", response_model=RuntimeStatus)
def incremental_scheduler_status() -> dict:
    return scheduler_status()


@router.post("/index/watcher/start", response_model=RuntimeStatus)
def start_incremental_watcher(kb_root: str | None = None) -> dict:
    return start_file_watcher(kb_root=kb_root)


@router.post("/index/watcher/stop", response_model=RuntimeStatus)
def stop_incremental_watcher() -> dict:
    return stop_file_watcher()


@router.get("/index/watcher/status", response_model=RuntimeStatus)
def incremental_watcher_status() -> dict:
    return watcher_status()


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
        conversation_id=payload.conversation_id,
    )


@router.post("/answers/save", response_model=SaveAnswerResponse)
def save_answer(payload: SaveAnswerRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return save_answer_note(
            db,
            title=payload.title,
            question=payload.question,
            answer=payload.answer,
            sources=payload.sources,
            query_log_id=payload.query_log_id,
            conversation_id=payload.conversation_id,
            target_dir=payload.target_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/conversations", response_model=list[ConversationRead])
def conversations(limit: int = 50, db: Session = Depends(get_db)) -> list[RagConversation]:
    return list_conversations(db, limit=limit)


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(RagConversationMessage)
        .filter(RagConversationMessage.conversation_id == conversation_id)
        .order_by(RagConversationMessage.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "role": row.role,
            "content": row.content,
            "sources": json.loads(row.sources_json or "[]"),
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/graph", response_model=ObsidianGraphResponse)
def obsidian_graph(
    category: str = "all",
    search_text: str = "",
    min_degree: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    return build_obsidian_graph(category=category, search_text=search_text, min_degree=min_degree, limit=limit)


@router.post("/eval/cases", response_model=EvalCaseRead)
def add_eval_case(payload: EvalCaseCreate, db: Session = Depends(get_db)) -> RagEvalCase:
    return create_eval_case(
        db,
        query=payload.query,
        expected_document=payload.expected_document,
        expected_text=payload.expected_text,
        category=payload.category,
        notes=payload.notes,
    )


@router.get("/eval/cases", response_model=list[EvalCaseRead])
def eval_cases(db: Session = Depends(get_db)) -> list[RagEvalCase]:
    return db.query(RagEvalCase).order_by(RagEvalCase.id.desc()).all()


@router.post("/eval/run", response_model=EvalRunResponse)
def run_evaluation(payload: EvalRunRequest, db: Session = Depends(get_db)) -> dict:
    return run_eval(
        db,
        top_k=payload.top_k,
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
