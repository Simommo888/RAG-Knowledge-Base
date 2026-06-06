"use client";

import {
  BookOpen,
  Box,
  Check,
  ChevronDown,
  Clock,
  Copy,
  Database,
  FileText,
  History,
  KeyRound,
  MessageCircle,
  RefreshCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Terminal,
  Upload
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { API_BASE, ragApi, type RetrievalPayload } from "@/lib/api";
import type {
  ApiKeySettingsRead,
  AskResponse,
  KnowledgeDocumentPage,
  KnowledgeDocumentSearchResult,
  QueryLogRead,
  RetrievalMode,
  SearchResult,
  StatsResponse,
  VectorStoreHealth
} from "@/lib/types";
import { cn, compactText, formatDate, formatNumber } from "@/lib/utils";

const navGroups = [
  {
    title: "开始",
    items: [{ label: "Ask", href: "#ask", icon: MessageCircle, active: true }]
  },
  {
    title: "知识库",
    items: [
      { label: "Knowledge", href: "#knowledge", icon: BookOpen },
      { label: "Semantic Search", href: "#semantic", icon: Search },
      { label: "Sources", href: "#sources", icon: FileText },
      { label: "History", href: "#history", icon: History }
    ]
  },
  {
    title: "系统",
    items: [{ label: "Settings", href: "#api-settings", icon: Settings }]
  }
];

const defaultQuestion = "AgentOS 和 RAG 知识库分别负责什么？当前知识库问答已经实现了哪些能力？";

function retrievalLabel(mode: RetrievalMode) {
  if (mode === "hybrid") return "混合检索";
  if (mode === "vector") return "向量检索";
  return "关键词检索";
}

function scoreText(value: number) {
  return Number(value || 0).toFixed(2);
}

function summarizeMap(map: Record<string, number> | undefined, fallback: string) {
  const entries = Object.entries(map || {});
  if (!entries.length) return fallback;
  return entries.map(([key, value]) => `${key} ${formatNumber(value)}`).join(" / ");
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: typeof FileText;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="min-h-24">
      <CardContent className="flex gap-4 p-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent text-primary">
          <Icon className="size-5" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-extrabold uppercase tracking-wide text-muted-foreground">{label}</div>
          <div className="mt-2 text-3xl font-black leading-none tracking-tight">{value}</div>
          <div className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function SourceList({ sources }: { sources: SearchResult[] }) {
  if (!sources.length) {
    return <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">暂未检索。先提出一个问题，或点击“检索设置”。</div>;
  }

  const maxScore = Math.max(...sources.map((item) => Number(item.score || 0)), 1);

  return (
    <div className="flex flex-col gap-3">
      {sources.map((item, index) => {
        const pct = Math.max(6, Math.min(100, Math.round((Number(item.score || 0) / maxScore) * 100)));
        return (
          <article key={`${item.chunk_id}-${index}`} className="rounded-md border bg-background p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h4 className="truncate text-sm font-bold">
                  [{index + 1}] {item.title}
                </h4>
                <p className="mt-1 break-all text-xs text-muted-foreground">{item.file_path}</p>
              </div>
              <Badge variant="outline">{scoreText(item.score)}</Badge>
            </div>
            {item.heading ? <div className="mt-2 text-xs font-semibold text-slate-700">{item.heading}</div> : null}
            <p className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">{compactText(item.content, 260)}</p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="secondary">keyword {scoreText(item.keyword_score)}</Badge>
              <Badge variant="secondary">vector {scoreText(item.vector_score)}</Badge>
              {item.matched_query ? <Badge variant="success">matched {item.matched_query}</Badge> : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [apiKey, setApiKey] = useState<ApiKeySettingsRead | null>(null);
  const [vectorHealth, setVectorHealth] = useState<VectorStoreHealth | null>(null);
  const [history, setHistory] = useState<QueryLogRead[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeDocumentPage>({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });

  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"info" | "success" | "error">("info");
  const [busy, setBusy] = useState("");

  const [question, setQuestion] = useState(defaultQuestion);
  const [answer, setAnswer] = useState("RAG（Retrieval-Augmented Generation）会先检索相关知识，再基于来源证据生成回答。回答区会在提问后展示摘要、引用片段和模型使用状态。");
  const [answerMeta, setAnswerMeta] = useState("基于检索结果生成");
  const [answerMode, setAnswerMode] = useState("Local");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [sources, setSources] = useState<SearchResult[]>([]);

  const [category, setCategory] = useState("all");
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("hybrid");
  const [topK, setTopK] = useState(8);
  const [useLlm, setUseLlm] = useState(true);
  const [queryExpansion, setQueryExpansion] = useState(true);
  const [rerank, setRerank] = useState(true);

  const [knowledgeTitle, setKnowledgeTitle] = useState("");
  const [knowledgeContent, setKnowledgeContent] = useState("");
  const [knowledgeSearch, setKnowledgeSearch] = useState("");
  const [knowledgePageSize, setKnowledgePageSize] = useState(10);
  const [editingKnowledgeId, setEditingKnowledgeId] = useState<number | null>(null);

  const [semanticQuery, setSemanticQuery] = useState("小孩子");
  const [semanticTopK, setSemanticTopK] = useState(5);
  const [semanticOutput, setSemanticOutput] = useState("等待查询...");
  const [semanticResults, setSemanticResults] = useState<KnowledgeDocumentSearchResult[]>([]);

  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [openaiModel, setOpenaiModel] = useState("gpt-4.1-mini");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState("https://api.openai.com/v1");
  const [embeddingProvider, setEmbeddingProvider] = useState("openai");
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");
  const [embeddingFallback, setEmbeddingFallback] = useState(true);

  const categories = useMemo(() => Object.entries(stats?.categories || { all: "" }), [stats?.categories]);

  function show(text: string, type: "info" | "success" | "error" = "info") {
    setMessage(text);
    setMessageType(type);
  }

  function payload(): RetrievalPayload {
    return {
      category,
      top_k: topK,
      retrieval_mode: retrievalMode,
      query_expansion: queryExpansion,
      rerank
    };
  }

  async function refreshStats() {
    const data = await ragApi.stats();
    setStats(data);
  }

  async function refreshAll() {
    try {
      const [statsData, apiKeyData, historyData, healthData, knowledgeData] = await Promise.all([
        ragApi.stats(),
        ragApi.apiKey(),
        ragApi.history(),
        ragApi.vectorHealth(),
        ragApi.listKnowledge({ page: knowledge.page, page_size: knowledgePageSize, search_text: knowledgeSearch })
      ]);
      setStats(statsData);
      setApiKey(apiKeyData);
      setHistory(historyData);
      setVectorHealth(healthData);
      setKnowledge(knowledgeData);
      setOpenaiModel(apiKeyData.openai_model || "gpt-4.1-mini");
      setOpenaiBaseUrl(apiKeyData.openai_base_url || "https://api.openai.com/v1");
      setEmbeddingProvider(apiKeyData.embedding_provider || "openai");
      setEmbeddingModel(apiKeyData.embedding_model || "text-embedding-3-small");
      setEmbeddingFallback(Boolean(apiKeyData.embedding_fallback_to_local));
    } catch (error) {
      show(error instanceof Error ? error.message : "加载失败", "error");
    }
  }

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAsk() {
    const clean = question.trim();
    if (!clean) {
      show("请输入问题。", "error");
      return;
    }
    setBusy("ask");
    setWarnings([]);
    setSources([]);
    setAnswer("");
    setAnswerMeta("正在检索来源并生成回答...");
    try {
      const result: AskResponse = await ragApi.ask({
        ...payload(),
        question: clean,
        use_llm: useLlm
      });
      setAnswerMode(result.llm_used ? result.model || "LLM" : "Local");
      setSources(result.sources || []);
      setWarnings(result.warnings || []);
      setAnswerMeta(`命中 ${result.sources?.length || 0} 条来源，模式：${result.llm_used ? "LLM 综合" : "本地摘录"}`);

      let typed = "";
      const text = result.answer || "没有生成回答。";
      for (const char of text) {
        typed += char;
        setAnswer(typed);
        await new Promise((resolve) => setTimeout(resolve, 6));
      }
      await ragApi.history().then(setHistory).catch(() => undefined);
      show("问答完成。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "问答失败", "error");
      setAnswerMeta("问答失败");
    } finally {
      setBusy("");
    }
  }

  async function runSearchOnly() {
    const clean = question.trim();
    if (!clean) {
      show("请输入问题。", "error");
      return;
    }
    setBusy("search");
    try {
      const results = await ragApi.search({ ...payload(), query: clean });
      setSources(results);
      setAnswerMode("Search");
      setAnswerMeta(`只检索：命中 ${results.length} 条来源`);
      setAnswer(results.length ? "已完成检索。请在右侧来源证据中查看命中文档、片段和相关度。" : "没有找到相关来源。");
    } catch (error) {
      show(error instanceof Error ? error.message : "检索失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function loadKnowledge(page = knowledge.page) {
    const data = await ragApi.listKnowledge({ page, page_size: knowledgePageSize, search_text: knowledgeSearch });
    setKnowledge(data);
  }

  async function saveKnowledge() {
    if (!knowledgeTitle.trim() || !knowledgeContent.trim()) {
      show("请填写标题和知识内容。", "error");
      return;
    }
    setBusy("knowledge");
    try {
      if (editingKnowledgeId) {
        await ragApi.updateKnowledge(editingKnowledgeId, { title: knowledgeTitle.trim(), content: knowledgeContent.trim() });
        show("知识条目已更新并重新索引。", "success");
      } else {
        await ragApi.createKnowledge({ title: knowledgeTitle.trim(), content: knowledgeContent.trim(), source_kind: "manual" });
        show("知识条目已创建并写入索引。", "success");
      }
      setEditingKnowledgeId(null);
      setKnowledgeTitle("");
      setKnowledgeContent("");
      await Promise.all([loadKnowledge(1), refreshStats()]);
    } catch (error) {
      show(error instanceof Error ? error.message : "保存失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function editKnowledge(id: number) {
    try {
      const item = await ragApi.getKnowledge(id);
      setEditingKnowledgeId(item.id);
      setKnowledgeTitle(item.title);
      setKnowledgeContent(item.content || "");
      window.setTimeout(() => {
        document.getElementById("knowledge-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
        document.getElementById("knowledge-title-input")?.focus();
      }, 0);
      show(`正在编辑知识条目 #${item.id}，修改后点击“保存修改”。`, "info");
    } catch (error) {
      show(error instanceof Error ? error.message : "加载知识详情失败", "error");
    }
  }

  async function deleteKnowledge(id: number) {
    if (!confirm("确定要从当前 RAG 索引中删除这个知识条目吗？不会删除原始 Obsidian 文件。")) return;
    setBusy("knowledge");
    try {
      await ragApi.deleteKnowledge(id);
      await Promise.all([loadKnowledge(), refreshStats()]);
      show("知识条目已删除。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "删除失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function handleTxtUpload(file?: File | null) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".txt") && file.type !== "text/plain") {
      show("当前只支持上传 txt 文本文件。", "error");
      return;
    }
    const text = await file.text();
    setKnowledgeTitle((current) => current || file.name.replace(/\.txt$/i, ""));
    setKnowledgeContent(text);
    show(`已读取文件：${file.name}，确认后点击保存知识。`, "success");
  }

  async function runSemanticStream() {
    const query = semanticQuery.trim();
    if (!query) {
      show("请输入语义查询内容。", "error");
      return;
    }
    setBusy("semantic");
    setSemanticOutput("");
    try {
      const response = await ragApi.streamKnowledgeSearch({
        query,
        top_k: semanticTopK,
        retrieval_mode: retrievalMode,
        query_expansion: queryExpansion,
        rerank
      });
      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        setSemanticOutput((current) => current + decoder.decode(value, { stream: true }));
      }
      const results = await ragApi.searchKnowledge({
        query,
        top_k: semanticTopK,
        retrieval_mode: retrievalMode,
        query_expansion: queryExpansion,
        rerank
      });
      setSemanticResults(results);
      show("流式查询完成。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "流式查询失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function runSemanticSearchOnly() {
    const query = semanticQuery.trim();
    if (!query) {
      show("请输入语义查询内容。", "error");
      return;
    }
    setBusy("semantic-search");
    try {
      const results = await ragApi.searchKnowledge({
        query,
        top_k: semanticTopK,
        retrieval_mode: retrievalMode,
        query_expansion: queryExpansion,
        rerank
      });
      setSemanticResults(results);
      setSemanticOutput(`普通检索完成：找到 ${results.length} 个相关知识库。`);
      show("普通检索完成。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "普通检索失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function saveApiKey() {
    setBusy("api-key");
    try {
      const result = await ragApi.saveApiKey({
        openai_api_key: openaiApiKey.trim() || null,
        clear_openai_api_key: false,
        openai_model: openaiModel.trim(),
        openai_base_url: openaiBaseUrl.trim(),
        embedding_provider: embeddingProvider,
        embedding_model: embeddingModel.trim(),
        embedding_fallback_to_local: embeddingFallback
      });
      setOpenaiApiKey("");
      setApiKey(result);
      await refreshStats();
      show("API Key 配置已保存。页面不会回显明文。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "API Key 配置保存失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function clearApiKey() {
    if (!confirm("确定要清除本地保存的 OPENAI_API_KEY 吗？")) return;
    setBusy("api-key");
    try {
      const result = await ragApi.saveApiKey({
        clear_openai_api_key: true,
        openai_model: openaiModel,
        openai_base_url: openaiBaseUrl,
        embedding_provider: embeddingProvider,
        embedding_model: embeddingModel,
        embedding_fallback_to_local: embeddingFallback
      });
      setApiKey(result);
      show("OPENAI_API_KEY 已清除。", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "清除失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function runIndex(rebuild: boolean) {
    if (rebuild && !confirm("确定要全量重建索引吗？如果使用 OpenAI embedding，会消耗 API 额度。")) return;
    setBusy(rebuild ? "rebuild-index" : "index");
    try {
      const result = await ragApi.index({ category, rebuild });
      await refreshAll();
      show(`索引完成：文档 ${result.indexed_documents}，Chunks ${result.indexed_chunks}，Embeddings ${result.embedded_chunks}。`, result.errors?.length ? "error" : "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "索引失败", "error");
    } finally {
      setBusy("");
    }
  }

  async function rebuildVectorStore() {
    if (!confirm("确定要从 SQLite embeddings 修复/重建 Chroma 吗？这不会重新调用 OpenAI。")) return;
    setBusy("vector");
    try {
      const result = await ragApi.rebuildVectorStore();
      const health = await ragApi.vectorHealth();
      setVectorHealth(health);
      await refreshStats();
      show(`Chroma 重建完成：写入 ${result.upserted_vectors} / ${result.source_embeddings}，最终 count ${result.final_count}。`, result.status === "ok" ? "success" : "error");
    } catch (error) {
      show(error instanceof Error ? error.message : "Chroma 重建失败", "error");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 grid min-h-14 grid-cols-[240px_minmax(280px,420px)_minmax(0,1fr)] items-center border-b bg-background/95 backdrop-blur max-[1180px]:grid-cols-1">
        <div className="flex h-14 items-center gap-3 border-r px-5 max-[1180px]:border-b max-[1180px]:border-r-0">
          <div className="grid size-8 place-items-center rounded-md bg-primary text-sm font-black text-primary-foreground shadow">R</div>
          <h1 className="text-sm font-extrabold">RAG Knowledge Base</h1>
        </div>
        <div className="px-5 max-[1180px]:hidden">
          <div className="flex h-10 items-center rounded-lg border bg-background px-3">
            <Search className="size-4 text-muted-foreground" />
            <Input
              className="border-0 shadow-none focus-visible:ring-0"
              placeholder="Search..."
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  setQuestion(event.currentTarget.value);
                  void runAsk();
                }
              }}
            />
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">⌘ K</span>
          </div>
        </div>
        <div className="flex items-center justify-end gap-3 px-5 max-[1180px]:hidden">
          <Badge variant="success"><span className="mr-1 size-2 rounded-full bg-emerald-500" />{stats ? "服务运行中" : "连接中"}</Badge>
          <Badge variant="outline">{stats?.vector_store || "Chroma"} ✓ {stats?.chroma_collection || "Connected"}</Badge>
          <Badge variant="outline">Embedding ✓ {stats?.embedding_provider === "openai" ? "OK" : "Local"}</Badge>
          <Button variant="ghost" size="icon" aria-label="Theme"><Sparkles className="size-4" /></Button>
          <div className="grid size-8 place-items-center rounded-full border bg-muted text-xs font-bold">AK</div>
          <ChevronDown className="size-4 text-muted-foreground" />
        </div>
      </header>

      <div className="app-grid grid min-h-[calc(100vh-56px)]">
        <aside className="sticky top-14 h-[calc(100vh-56px)] overflow-auto border-r bg-background p-4 max-[1180px]:static max-[1180px]:h-auto max-[1180px]:border-b max-[1180px]:border-r-0">
          <nav className="flex flex-col gap-4 max-[1180px]:flex-row max-[1180px]:overflow-auto" aria-label="主导航">
            {navGroups.map((group) => (
              <div key={group.title} className="flex flex-col gap-2 max-[1180px]:flex-row">
                <p className="px-2 text-xs font-extrabold max-[1180px]:hidden">{group.title}</p>
                {group.items.map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex min-h-9 items-center gap-2 rounded-md px-3 text-sm text-slate-700 hover:bg-accent hover:text-accent-foreground",
                      "active" in item && item.active && "bg-accent text-accent-foreground"
                    )}
                  >
                    <item.icon className="size-4" />
                    {item.label}
                  </a>
                ))}
              </div>
            ))}
          </nav>

          <Card className="mt-8 max-[1180px]:hidden">
            <CardContent className="p-4">
              <h2 className="text-sm font-extrabold">RAG Knowledge Base</h2>
              <p className="mt-1 text-xs text-muted-foreground">v0.1.0</p>
              <div className="mt-4 border-t pt-4 text-xs leading-6 text-muted-foreground">
                <p className="font-semibold text-foreground">本地模式</p>
                <p className="break-all">{stats?.kb_root || "加载中..."}</p>
              </div>
              <div className="mt-4 border-t pt-4 text-xs leading-6">
                <p className="font-semibold">文档与帮助</p>
                <a className="text-primary underline underline-offset-4" href="#knowledge">查看使用指南 ↗</a>
              </div>
            </CardContent>
          </Card>
        </aside>

        <main className="min-w-0 px-6 py-6 max-[760px]:px-4">
          <div className="workbench-grid mx-auto grid max-w-[1248px] gap-7">
            <div className="min-w-0">
              <div className="mb-5">
                <p className="text-sm text-muted-foreground">Ask <span className="mx-2">›</span> 工作台</p>
                <h2 className="mt-2 text-3xl font-black tracking-tight max-[760px]:text-2xl">知识库问答工作台</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">基于你的知识库进行问答，查看来源证据与检索详情。</p>
              </div>

              {message ? (
                <div
                  className={cn(
                    "mb-4 rounded-md border px-4 py-3 text-sm",
                    messageType === "success" && "border-emerald-200 bg-emerald-50 text-emerald-700",
                    messageType === "error" && "border-red-200 bg-red-50 text-red-700",
                    messageType === "info" && "bg-muted text-muted-foreground"
                  )}
                >
                  {message}
                </div>
              ) : null}

              <Card id="ask">
                <CardHeader>
                  <div>
                    <CardTitle>提问</CardTitle>
                    <CardDescription>输入问题后按 Ctrl + Enter，可直接向知识库提问。没有 API Key 时会自动使用本地摘录式回答。</CardDescription>
                  </div>
                  <Badge>{retrievalMode}</Badge>
                </CardHeader>
                <CardContent>
                  <div className="rounded-lg border border-input bg-background p-4">
                    <div className="flex gap-3">
                      <Terminal className="mt-1 size-5 shrink-0" />
                      <Textarea
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        onKeyDown={(event) => {
                          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                            void runAsk();
                          }
                        }}
                        placeholder="请输入你的问题，或使用自然语言提问..."
                        className="min-h-24 resize-y border-0 p-0 text-base shadow-none focus-visible:ring-0"
                        maxLength={4000}
                      />
                    </div>
                    <div className="mt-4 flex items-center justify-between gap-3 max-[760px]:grid">
                      <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => setQuestion("RAG 知识库现在支持哪些能力？")}>推荐问题</Button>
                        <Button variant="secondary" onClick={() => void runSearchOnly()} disabled={busy === "search"}>检索设置</Button>
                        <Button variant="secondary" onClick={() => setRetrievalMode("hybrid")}>混合检索</Button>
                      </div>
                      <div className="flex items-center justify-end gap-3">
                        <span className="text-xs text-muted-foreground">{question.length} / 4000</span>
                        <Button onClick={() => void runAsk()} disabled={busy === "ask"}><Send className="size-4" />⌘ ↵ 发送</Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <section className="metric-grid my-5 grid gap-4" aria-label="知识库统计">
                <StatCard icon={FileText} label="文档数" value={formatNumber(stats?.documents)} detail={summarizeMap(stats?.document_types, "文档类型加载中")} />
                <StatCard icon={Box} label="文本块 Chunks" value={formatNumber(stats?.chunks)} detail="用于检索和引用的文本片段" />
                <StatCard icon={Sparkles} label="向量 Embeddings" value={formatNumber(stats?.embeddings)} detail={summarizeMap(stats?.embedding_providers, stats?.embedding_provider || "provider 加载中")} />
                <StatCard icon={Database} label="向量库 Chroma" value={formatNumber(stats?.chroma_vectors)} detail={`最近索引：${formatDate(stats?.last_indexed_at)}`} />
              </section>

              <div className="result-grid grid gap-4">
                <Card>
                  <CardHeader>
                    <div>
                      <CardTitle>回答</CardTitle>
                      <CardDescription>{answerMeta}</CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <Badge>{answerMode}</Badge>
                      <Button variant="secondary" size="sm" onClick={() => void navigator.clipboard.writeText(answer)}><Copy className="size-3" />复制回答</Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {warnings.length ? (
                      <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                        {warnings.join(" ")}
                      </div>
                    ) : null}
                    <div className="min-h-32 whitespace-pre-wrap rounded-md border bg-slate-50 p-4 text-sm leading-7 text-slate-800">{answer || "等待回答..."}</div>
                  </CardContent>
                </Card>

                <Card id="sources">
                  <CardHeader>
                    <div>
                      <CardTitle>来源证据</CardTitle>
                      <CardDescription>查看命中文档、片段和相关度。</CardDescription>
                    </div>
                    <Badge>{sources.length} sources</Badge>
                  </CardHeader>
                  <CardContent>
                    <SourceList sources={sources} />
                  </CardContent>
                </Card>
              </div>

              <Card id="knowledge" className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>知识管理</CardTitle>
                    <CardDescription>支持分页查看、直接输入文本、上传 txt、编辑和删除。新增或更新后会自动切块、embedding 并写入向量库。</CardDescription>
                  </div>
                  <Badge>{knowledge.total} 条</Badge>
                </CardHeader>
                <CardContent id="knowledge-editor" className="flex scroll-mt-20 flex-col gap-4">
                  {editingKnowledgeId ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-primary/20 bg-accent px-3 py-2 text-sm">
                      <div className="font-semibold text-primary">正在编辑知识条目 #{editingKnowledgeId}</div>
                      <Button variant="secondary" size="sm" onClick={() => { setEditingKnowledgeId(null); setKnowledgeTitle(""); setKnowledgeContent(""); }}>取消编辑</Button>
                    </div>
                  ) : null}
                  <div className="grid grid-cols-[minmax(0,1fr)_220px] gap-3 max-[760px]:grid-cols-1">
                    <label className="flex flex-col gap-2 text-sm font-semibold">
                      标题
                      <Input id="knowledge-title-input" value={knowledgeTitle} onChange={(event) => setKnowledgeTitle(event.target.value)} placeholder="例如：朱自清《春》" />
                    </label>
                    <label className="flex flex-col gap-2 text-sm font-semibold">
                      上传 txt
                      <Input type="file" accept=".txt,text/plain" onChange={(event) => void handleTxtUpload(event.target.files?.[0])} />
                    </label>
                  </div>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    知识内容
                    <Textarea value={knowledgeContent} onChange={(event) => setKnowledgeContent(event.target.value)} className="min-h-36" placeholder="可以直接粘贴文本。例如：朱自清《春》、鲁迅《故乡》全文或片段。" />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => void saveKnowledge()} disabled={busy === "knowledge"}>{editingKnowledgeId ? "保存修改" : "保存知识"}</Button>
                    <Button variant="secondary" onClick={() => { setEditingKnowledgeId(null); setKnowledgeTitle(""); setKnowledgeContent(""); }}>清空表单</Button>
                    <Button variant="secondary" onClick={() => void loadKnowledge(1)}>刷新列表</Button>
                  </div>
                  <div className="grid grid-cols-[minmax(0,1fr)_160px] gap-3 max-[760px]:grid-cols-1">
                    <Input value={knowledgeSearch} onChange={(event) => setKnowledgeSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void loadKnowledge(1); }} placeholder="按标题、路径、文件名搜索" />
                    <select className="min-h-10 rounded-md border bg-background px-3 text-sm" value={knowledgePageSize} onChange={(event) => setKnowledgePageSize(Number(event.target.value))}>
                      {[5, 10, 20, 50].map((size) => <option key={size} value={size}>每页 {size} 条</option>)}
                    </select>
                  </div>
                  <div className="overflow-auto rounded-md border">
                    <table className="w-full min-w-[720px] text-left text-sm">
                      <thead className="bg-muted text-xs text-muted-foreground">
                        <tr>
                          <th className="p-3">标题</th>
                          <th className="p-3">来源</th>
                          <th className="p-3">Chunks</th>
                          <th className="p-3">更新时间</th>
                          <th className="p-3">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {knowledge.items.length ? knowledge.items.map((item) => (
                          <tr key={item.id} className="border-t">
                            <td className="p-3">
                              <div className="font-semibold">{item.title}</div>
                              <div className="mt-1 break-all text-xs text-muted-foreground">{item.file_path}</div>
                            </td>
                            <td className="p-3"><Badge>{item.source_kind || "file"}</Badge></td>
                            <td className="p-3">{item.chunk_count}</td>
                            <td className="p-3">{formatDate(item.updated_at || item.indexed_at)}</td>
                            <td className="p-3">
                              <div className="flex flex-wrap gap-2">
                                <Button variant="secondary" size="sm" onClick={() => void editKnowledge(item.id)}>编辑</Button>
                                <Button variant="secondary" size="sm" onClick={() => { setSemanticQuery(item.title); location.hash = "#semantic"; }}>查询</Button>
                                <Button variant="secondary" size="sm" onClick={() => void deleteKnowledge(item.id)}>删除</Button>
                              </div>
                            </td>
                          </tr>
                        )) : (
                          <tr><td className="p-6 text-center text-muted-foreground" colSpan={5}>暂无知识条目。</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex items-center justify-between">
                    <Button variant="secondary" disabled={knowledge.page <= 1} onClick={() => void loadKnowledge(knowledge.page - 1)}>上一页</Button>
                    <span className="text-sm text-muted-foreground">第 {knowledge.page} / {Math.max(knowledge.total_pages, 1)} 页</span>
                    <Button variant="secondary" disabled={knowledge.page >= knowledge.total_pages} onClick={() => void loadKnowledge(knowledge.page + 1)}>下一页</Button>
                  </div>
                </CardContent>
              </Card>

              <Card id="semantic" className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>相关性 / 语义查询</CardTitle>
                    <CardDescription>输入“春天”应能找到《春》；输入“少年闰土”或“小孩子”应能找到《故乡》。结果会逐字出现。</CardDescription>
                  </div>
                  <Badge>{semanticResults.length} results</Badge>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="grid grid-cols-[minmax(0,1fr)_160px] gap-3 max-[760px]:grid-cols-1">
                    <Input value={semanticQuery} onChange={(event) => setSemanticQuery(event.target.value)} placeholder="例如：春天 / 少年闰土 / 小孩子" />
                    <select className="min-h-10 rounded-md border bg-background px-3 text-sm" value={semanticTopK} onChange={(event) => setSemanticTopK(Number(event.target.value))}>
                      {[3, 5, 8, 12].map((size) => <option key={size} value={size}>返回 {size} 条</option>)}
                    </select>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => void runSemanticStream()} disabled={busy === "semantic"}>流式查询</Button>
                    <Button variant="secondary" onClick={() => void runSemanticSearchOnly()} disabled={busy === "semantic-search"}>普通检索</Button>
                  </div>
                  <div className="min-h-28 whitespace-pre-wrap rounded-md border bg-slate-50 p-4 text-sm leading-7">{semanticOutput}</div>
                  <div className="flex flex-col gap-3">
                    {semanticResults.map((item, index) => (
                      <article key={`${item.document_id}-${index}`} className="rounded-md border p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h4 className="font-bold">[{index + 1}] 《{item.title}》</h4>
                            <p className="mt-1 break-all text-xs text-muted-foreground">{item.file_path}</p>
                          </div>
                          <Badge variant="outline">{scoreText(item.score)}</Badge>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{compactText(item.snippet, 220)}</p>
                      </article>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            <aside className="sticky top-24 max-h-[calc(100vh-112px)] overflow-auto border-l pl-5 max-[1180px]:static max-[1180px]:max-h-none max-[1180px]:border-l-0 max-[1180px]:pl-0">
              <section aria-label="On this page">
                <h3 className="text-sm font-extrabold">On This Page</h3>
                <nav className="mt-3 flex flex-col gap-2 text-sm text-muted-foreground">
                  <a href="#ask" className="hover:text-primary">提问</a>
                  <a href="#knowledge" className="hover:text-primary">知识管理</a>
                  <a href="#semantic" className="hover:text-primary">语义查询</a>
                  <a href="#sources" className="hover:text-primary">来源证据</a>
                  <a href="#history" className="hover:text-primary">最近提问</a>
                </nav>
              </section>

              <Card className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>检索设置</CardTitle>
                    <CardDescription>用分面和模式切换减少噪音，适合在大型个人知识库中定位资料。</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    索引范围
                    <select className="min-h-10 rounded-md border bg-background px-3 text-sm" value={category} onChange={(event) => setCategory(event.target.value)}>
                      {categories.length ? categories.map(([key, label]) => <option key={key} value={key}>{key} - {label}</option>) : <option value="all">all -</option>}
                    </select>
                  </label>
                  <div className="flex flex-col gap-2 text-sm font-semibold">
                    检索模式
                    <div className="grid grid-cols-3 gap-1 rounded-lg border bg-muted p-1">
                      {(["hybrid", "vector", "keyword"] as RetrievalMode[]).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          className={cn("min-h-9 rounded-md text-sm font-bold text-muted-foreground", retrievalMode === mode && "bg-background text-foreground shadow-sm")}
                          onClick={() => setRetrievalMode(mode)}
                        >
                          {mode[0].toUpperCase() + mode.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    返回片段数
                    <select className="min-h-10 rounded-md border bg-background px-3 text-sm" value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
                      {[5, 8, 12, 16, 20].map((size) => <option key={size} value={size}>{size}</option>)}
                    </select>
                  </label>
                  {[
                    ["有 OPENAI_API_KEY 时使用 LLM 综合", useLlm, setUseLlm],
                    ["语义扩展：本地同义词 / 领域词补全", queryExpansion, setQueryExpansion],
                    ["轻量重排：标题、路径、片段覆盖度加权", rerank, setRerank]
                  ].map(([label, checked, setter]) => (
                    <label key={String(label)} className="flex items-center justify-between gap-3 text-sm font-semibold">
                      <span>{String(label)}</span>
                      <input type="checkbox" checked={Boolean(checked)} onChange={(event) => (setter as (value: boolean) => void)(event.target.checked)} className="size-4 accent-blue-600" />
                    </label>
                  ))}
                </CardContent>
              </Card>

              <Card id="api-settings" className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>API Key / LLM 配置</CardTitle>
                    <CardDescription>本地保存到项目 `.env`，页面不会回显明文。</CardDescription>
                  </div>
                  <Badge variant={apiKey?.openai_api_key_configured ? "success" : "warning"}>{apiKey?.openai_api_key_configured ? "已配置" : "未配置"}</Badge>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    OPENAI_API_KEY
                    <Input type="password" value={openaiApiKey} onChange={(event) => setOpenaiApiKey(event.target.value)} placeholder="粘贴 OpenAI API Key，留空表示不修改" autoComplete="off" />
                  </label>
                  <p className="text-xs text-muted-foreground">当前 Key：{apiKey?.openai_api_key_configured ? apiKey.openai_api_key_masked : "未配置"}</p>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    问答模型
                    <Input value={openaiModel} onChange={(event) => setOpenaiModel(event.target.value)} />
                  </label>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    Base URL
                    <Input value={openaiBaseUrl} onChange={(event) => setOpenaiBaseUrl(event.target.value)} />
                  </label>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    Embedding Provider
                    <select className="min-h-10 rounded-md border bg-background px-3 text-sm" value={embeddingProvider} onChange={(event) => setEmbeddingProvider(event.target.value)}>
                      <option value="openai">openai</option>
                      <option value="local_hash">local_hash</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-2 text-sm font-semibold">
                    Embedding Model
                    <Input value={embeddingModel} onChange={(event) => setEmbeddingModel(event.target.value)} />
                  </label>
                  <label className="flex items-center justify-between gap-3 text-sm font-semibold">
                    OpenAI embedding 失败时回退本地 hash
                    <input type="checkbox" checked={embeddingFallback} onChange={(event) => setEmbeddingFallback(event.target.checked)} className="size-4 accent-blue-600" />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => void saveApiKey()} disabled={busy === "api-key"}><KeyRound className="size-4" />保存配置</Button>
                    <Button variant="secondary" onClick={() => void clearApiKey()}>清除 Key</Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>Vector Health</CardTitle>
                    <CardDescription>当 Chroma 计数异常时，可从 SQLite embedding 修复。</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 text-sm">
                  <div className="rounded-md border p-3">
                    <div className="font-bold">SQLite embeddings {formatNumber(vectorHealth?.sqlite_embeddings)} / Chroma vectors {formatNumber(vectorHealth?.chroma_vectors)}</div>
                    <p className="mt-2 break-all text-xs leading-5 text-muted-foreground">{vectorHealth?.chroma_path || "等待检查"}</p>
                    <Badge className="mt-3" variant={vectorHealth?.status === "ok" ? "success" : "warning"}>{vectorHealth?.status || "unknown"}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => void runIndex(false)} disabled={busy === "index"}><RefreshCcw className="size-4" />增量索引</Button>
                    <Button variant="secondary" onClick={() => void runIndex(true)} disabled={busy === "rebuild-index"}>全量重建</Button>
                    <Button onClick={() => void rebuildVectorStore()} disabled={busy === "vector"}><ShieldCheck className="size-4" />修复 Chroma</Button>
                  </div>
                </CardContent>
              </Card>

              <Card id="history" className="mt-5">
                <CardHeader>
                  <div>
                    <CardTitle>最近提问</CardTitle>
                    <CardDescription>点击问题可重新填入输入框。</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  {history.length ? history.slice(0, 8).map((item) => (
                    <button key={item.id} type="button" onClick={() => setQuestion(item.question)} className="rounded-md border p-3 text-left text-sm hover:bg-muted">
                      <strong className="line-clamp-2">{item.question}</strong>
                      <span className="mt-1 block text-xs text-muted-foreground"><Clock className="mr-1 inline size-3" />{formatDate(item.created_at)} · {item.source_count} sources</span>
                    </button>
                  )) : <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">暂无历史记录</div>}
                </CardContent>
              </Card>

              <div className="mt-5 rounded-md border bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
                API：{API_BASE}
              </div>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
