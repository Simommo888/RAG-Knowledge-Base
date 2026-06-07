from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IndexRequest(BaseModel):
    kb_root: str | None = None
    category: str = "all"
    rebuild: bool = False
    limit: int | None = Field(default=None, ge=1, le=10000)


class IndexResponse(BaseModel):
    indexed_documents: int = 0
    indexed_chunks: int = 0
    skipped_files: int = 0
    deleted_documents: int = 0
    embedded_chunks: int = 0
    errors: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    category: str = "all"
    top_k: int = Field(default=8, ge=1, le=30)
    retrieval_mode: str = "hybrid"
    query_expansion: bool | None = None
    rerank: bool | None = None


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    file_path: str
    heading: str = ""
    content: str
    score: float
    keyword_score: float = 0
    vector_score: float = 0
    matched_query: str = ""
    expanded_queries: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    category: str = "all"
    top_k: int = Field(default=8, ge=1, le=20)
    use_llm: bool = True
    retrieval_mode: str = "hybrid"
    query_expansion: bool | None = None
    rerank: bool | None = None
    conversation_id: int | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    llm_used: bool = False
    model: str = ""
    warnings: list[str] = Field(default_factory=list)
    conversation_id: int | None = None
    query_log_id: int | None = None


class StatsResponse(BaseModel):
    kb_root: str
    documents: int = 0
    chunks: int = 0
    embeddings: int = 0
    last_indexed_at: datetime | None = None
    categories: dict[str, str] = Field(default_factory=dict)
    document_types: dict[str, int] = Field(default_factory=dict)
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_providers: dict[str, int] = Field(default_factory=dict)
    vector_store: str = ""
    chroma_collection: str = ""
    chroma_vectors: int = 0


class ApiKeySettingsRead(BaseModel):
    openai_api_key_configured: bool = False
    openai_api_key_masked: str = ""
    openai_model: str = ""
    openai_base_url: str = ""
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_fallback_to_local: bool = True
    env_file_exists: bool = False
    warnings: list[str] = Field(default_factory=list)


class ApiKeySettingsUpdate(BaseModel):
    openai_api_key: str | None = Field(default=None, max_length=4096)
    clear_openai_api_key: bool = False
    openai_model: str | None = Field(default=None, max_length=120)
    openai_base_url: str | None = Field(default=None, max_length=300)
    embedding_provider: str | None = Field(default=None, max_length=40)
    embedding_model: str | None = Field(default=None, max_length=120)
    embedding_fallback_to_local: bool | None = None


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_path: str
    document_type: str
    source_kind: str = "file"
    original_name: str = ""
    file_size: int = 0
    chunk_count: int = 0
    index_status: str = "indexed"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    indexed_at: datetime | None = None


class KnowledgeDocumentDetail(KnowledgeDocumentRead):
    content: str = ""
    error_message: str = ""


class KnowledgeDocumentPage(BaseModel):
    items: list[KnowledgeDocumentRead] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1)
    source_kind: str = "manual"
    original_name: str = ""


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=30)
    retrieval_mode: str = "hybrid"
    query_expansion: bool | None = None
    rerank: bool | None = None


class KnowledgeDocumentSearchResult(BaseModel):
    document_id: int
    title: str
    file_path: str
    document_type: str = ""
    source_kind: str = ""
    score: float = 0
    best_heading: str = ""
    snippet: str = ""
    chunk_count: int = 0
    matched_chunks: int = 0
    matched_query: str = ""
    expanded_queries: list[str] = Field(default_factory=list)


class QueryExpansionRequest(BaseModel):
    query: str = Field(..., min_length=1)


class QueryExpansionResponse(BaseModel):
    query: str
    variants: list[str] = Field(default_factory=list)


class VectorStoreHealth(BaseModel):
    vector_store: str = ""
    chroma_available: bool = False
    chroma_path: str = ""
    chroma_collection: str = ""
    sqlite_embeddings: int = 0
    chroma_vectors: int = 0
    can_query: bool = False
    status: str = ""
    errors: list[str] = Field(default_factory=list)


class VectorStoreRebuildResponse(BaseModel):
    vector_store: str = ""
    reset_done: bool = False
    source_embeddings: int = 0
    upserted_vectors: int = 0
    skipped_vectors: int = 0
    target_dimensions: int = 0
    final_count: int = 0
    batches: int = 0
    status: str = ""
    errors: list[str] = Field(default_factory=list)


class QueryLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    category: str
    top_k: int
    llm_used: int
    model: str
    source_count: int
    latency_ms: float
    created_at: datetime


class IncrementalIndexResponse(BaseModel):
    status: str = ""
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    category: str = "all"
    indexed_documents: int = 0
    indexed_chunks: int = 0
    skipped_files: int = 0
    deleted_documents: int = 0
    embedded_chunks: int = 0
    errors: list[str] = Field(default_factory=list)


class RuntimeStatus(BaseModel):
    enabled: bool = False
    running: bool = False
    kb_root: str | None = None
    interval_seconds: int | None = None
    jobs: list[dict] = Field(default_factory=list)
    last_run: dict = Field(default_factory=dict)
    error: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    file_path: str = ""
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class ObsidianGraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_files_scanned: int = 0


class SaveAnswerRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    sources: list[dict] = Field(default_factory=list)
    query_log_id: int | None = None
    conversation_id: int | None = None
    target_dir: str | None = None


class SaveAnswerResponse(BaseModel):
    id: int
    title: str
    file_path: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class EvalCaseCreate(BaseModel):
    query: str = Field(..., min_length=1)
    expected_document: str = Field(..., min_length=1)
    expected_text: str = ""
    category: str = "all"
    notes: str = ""


class EvalCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    expected_document: str
    expected_text: str
    category: str
    notes: str
    created_at: datetime


class EvalRunRequest(BaseModel):
    top_k: int = Field(default=8, ge=1, le=30)
    retrieval_mode: str = "hybrid"
    query_expansion: bool = True
    rerank: bool = False


class EvalResultRead(BaseModel):
    case_id: int
    query: str
    expected_document: str
    hit: bool
    rank: int
    top_results: list[dict] = Field(default_factory=list)


class EvalRunResponse(BaseModel):
    run_id: int
    case_count: int
    hit_count: int
    hit_rate: float
    results: list[EvalResultRead] = Field(default_factory=list)
