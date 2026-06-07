export type RetrievalMode = "hybrid" | "vector" | "keyword";

export interface StatsResponse {
  kb_root: string;
  documents: number;
  chunks: number;
  embeddings: number;
  last_indexed_at?: string | null;
  categories: Record<string, string>;
  document_types: Record<string, number>;
  embedding_provider: string;
  embedding_model: string;
  embedding_providers: Record<string, number>;
  vector_store: string;
  chroma_collection: string;
  chroma_vectors: number;
}

export interface ApiKeySettingsRead {
  openai_api_key_configured: boolean;
  openai_api_key_masked: string;
  openai_model: string;
  openai_base_url: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_fallback_to_local: boolean;
  env_file_exists: boolean;
  warnings: string[];
}

export interface ApiKeySettingsUpdate {
  openai_api_key?: string | null;
  clear_openai_api_key?: boolean;
  openai_model?: string | null;
  openai_base_url?: string | null;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  embedding_fallback_to_local?: boolean | null;
}

export interface SearchResult {
  chunk_id: number;
  document_id: number;
  title: string;
  file_path: string;
  heading: string;
  content: string;
  score: number;
  keyword_score: number;
  vector_score: number;
  matched_query: string;
  expanded_queries: string[];
}

export interface AskResponse {
  question: string;
  answer: string;
  sources: SearchResult[];
  llm_used: boolean;
  model: string;
  warnings: string[];
  conversation_id?: number | null;
  query_log_id?: number | null;
}

export interface KnowledgeDocumentRead {
  id: number;
  title: string;
  file_path: string;
  document_type: string;
  source_kind: string;
  original_name: string;
  file_size: number;
  chunk_count: number;
  index_status: string;
  created_at?: string | null;
  updated_at?: string | null;
  indexed_at?: string | null;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocumentRead {
  content: string;
  error_message: string;
}

export interface KnowledgeDocumentPage {
  items: KnowledgeDocumentRead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface KnowledgeDocumentSearchResult {
  document_id: number;
  title: string;
  file_path: string;
  document_type: string;
  source_kind: string;
  score: number;
  best_heading: string;
  snippet: string;
  chunk_count: number;
  matched_chunks: number;
  matched_query: string;
  expanded_queries: string[];
}

export interface QueryLogRead {
  id: number;
  question: string;
  answer: string;
  category: string;
  top_k: number;
  llm_used: number;
  model: string;
  source_count: number;
  latency_ms: number;
  created_at: string;
}

export interface VectorStoreHealth {
  vector_store: string;
  chroma_available: boolean;
  chroma_path: string;
  chroma_collection: string;
  sqlite_embeddings: number;
  chroma_vectors: number;
  can_query: boolean;
  status: string;
  errors: string[];
}

export interface VectorStoreRebuildResponse {
  vector_store: string;
  reset_done: boolean;
  source_embeddings: number;
  upserted_vectors: number;
  skipped_vectors: number;
  target_dimensions: number;
  final_count: number;
  batches: number;
  status: string;
  errors: string[];
}

export interface RuntimeStatus {
  enabled: boolean;
  running: boolean;
  kb_root?: string | null;
  interval_seconds?: number | null;
  jobs: Array<Record<string, unknown>>;
  last_run: Record<string, unknown>;
  error?: string | null;
}

export interface ObsidianGraphResponse {
  nodes: Array<{ id: string; label: string; file_path: string; degree: number }>;
  edges: Array<{ source: string; target: string; label: string }>;
  total_files_scanned: number;
}

export interface ConversationRead {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface EvalCaseRead {
  id: number;
  query: string;
  expected_document: string;
  expected_text: string;
  category: string;
  notes: string;
  created_at: string;
}

export interface EvalRunResponse {
  run_id: number;
  case_count: number;
  hit_count: number;
  hit_rate: number;
  results: Array<{
    case_id: number;
    query: string;
    expected_document: string;
    hit: boolean;
    rank: number;
    top_results: Array<Record<string, unknown>>;
  }>;
}

export interface SaveAnswerResponse {
  id: number;
  title: string;
  file_path: string;
  created_at: string;
}
