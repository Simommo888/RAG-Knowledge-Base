import type {
  ApiKeySettingsRead,
  ApiKeySettingsUpdate,
  AskResponse,
  KnowledgeDocumentDetail,
  KnowledgeDocumentPage,
  KnowledgeDocumentSearchResult,
  QueryLogRead,
  RetrievalMode,
  SearchResult,
  StatsResponse,
  VectorStoreHealth,
  VectorStoreRebuildResponse
} from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8020";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });

  if (!response.ok) {
    const text = await response.text();
    try {
      const data = JSON.parse(text) as { detail?: string };
      throw new Error(data.detail || text || `请求失败：${response.status}`);
    } catch (error) {
      if (error instanceof Error && error.message && error.message !== text) {
        throw error;
      }
      throw new Error(text || `请求失败：${response.status}`);
    }
  }

  return response.json() as Promise<T>;
}

export interface RetrievalPayload {
  category: string;
  top_k: number;
  retrieval_mode: RetrievalMode;
  query_expansion: boolean;
  rerank: boolean;
}

export const ragApi = {
  health: () => fetchJson<{ status: string; service: string }>("/api/health"),
  stats: () => fetchJson<StatsResponse>("/api/rag/stats"),
  history: () => fetchJson<QueryLogRead[]>("/api/rag/history"),
  apiKey: () => fetchJson<ApiKeySettingsRead>("/api/rag/api-key"),
  saveApiKey: (payload: ApiKeySettingsUpdate) =>
    fetchJson<ApiKeySettingsRead>("/api/rag/api-key", { method: "PUT", body: JSON.stringify(payload) }),
  ask: (payload: RetrievalPayload & { question: string; use_llm: boolean }) =>
    fetchJson<AskResponse>("/api/rag/ask", { method: "POST", body: JSON.stringify(payload) }),
  search: (payload: RetrievalPayload & { query: string }) =>
    fetchJson<SearchResult[]>("/api/rag/search", { method: "POST", body: JSON.stringify(payload) }),
  index: (payload: { category: string; rebuild: boolean }) =>
    fetchJson<{ indexed_documents: number; indexed_chunks: number; embedded_chunks: number; errors: string[] }>(
      "/api/rag/index",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  vectorHealth: () => fetchJson<VectorStoreHealth>("/api/rag/vector-store/health"),
  rebuildVectorStore: () =>
    fetchJson<VectorStoreRebuildResponse>("/api/rag/vector-store/rebuild", { method: "POST" }),
  listKnowledge: (params: { page: number; page_size: number; search_text?: string }) => {
    const query = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
      search_text: params.search_text || ""
    });
    return fetchJson<KnowledgeDocumentPage>(`/api/rag/knowledge?${query.toString()}`);
  },
  getKnowledge: (id: number) => fetchJson<KnowledgeDocumentDetail>(`/api/rag/knowledge/${id}`),
  createKnowledge: (payload: { title: string; content: string; source_kind?: string; original_name?: string }) =>
    fetchJson<KnowledgeDocumentDetail>("/api/rag/knowledge", { method: "POST", body: JSON.stringify(payload) }),
  updateKnowledge: (id: number, payload: { title?: string; content?: string }) =>
    fetchJson<KnowledgeDocumentDetail>(`/api/rag/knowledge/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteKnowledge: (id: number) => fetchJson<{ ok: boolean; deleted_id: number }>(`/api/rag/knowledge/${id}`, { method: "DELETE" }),
  searchKnowledge: (payload: { query: string; top_k: number; retrieval_mode: RetrievalMode; query_expansion: boolean; rerank: boolean }) =>
    fetchJson<KnowledgeDocumentSearchResult[]>("/api/rag/knowledge/search", { method: "POST", body: JSON.stringify(payload) }),
  streamKnowledgeSearch: (payload: { query: string; top_k: number; retrieval_mode: RetrievalMode; query_expansion: boolean; rerank: boolean }) =>
    fetch(`${API_BASE}/api/rag/knowledge/search/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
};
