"use client";

import { BookOpen, Database, FileText, GitBranch, KeyRound, Play, RefreshCcw, Save, Search, Settings, ShieldCheck, Timer, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { API_BASE, ragApi, type RetrievalPayload } from "@/lib/api";
import type { AskResponse, EvalRunResponse, KnowledgeDocumentPage, ObsidianGraphResponse, RetrievalMode, RuntimeStatus, SearchResult, StatsResponse, VectorStoreHealth } from "@/lib/types";
import { compactText, formatDate, formatNumber } from "@/lib/utils";

function score(value: number) {
  return Number(value || 0).toFixed(2);
}

function sourcesLabel(items: SearchResult[]) {
  return items.length ? `${items.length} sources` : "no sources";
}

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [health, setHealth] = useState<VectorStoreHealth | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeDocumentPage>({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  const [scheduler, setScheduler] = useState<RuntimeStatus | null>(null);
  const [watcher, setWatcher] = useState<RuntimeStatus | null>(null);
  const [graph, setGraph] = useState<ObsidianGraphResponse | null>(null);

  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [question, setQuestion] = useState("小孩子在哪篇文章里出现？");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SearchResult[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [queryLogId, setQueryLogId] = useState<number | null>(null);

  const [category, setCategory] = useState("all");
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("hybrid");
  const [topK, setTopK] = useState(8);
  const [useLlm, setUseLlm] = useState(true);
  const [queryExpansion, setQueryExpansion] = useState(true);
  const [rerank, setRerank] = useState(false);

  const [knowledgeTitle, setKnowledgeTitle] = useState("");
  const [knowledgeContent, setKnowledgeContent] = useState("");
  const [knowledgeSearch, setKnowledgeSearch] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("小孩子");
  const [semanticText, setSemanticText] = useState("");

  const [evalQuery, setEvalQuery] = useState("小孩子");
  const [evalExpected, setEvalExpected] = useState("故乡");
  const [evalResult, setEvalResult] = useState<EvalRunResponse | null>(null);

  const categories = useMemo(() => Object.entries(stats?.categories || { all: "" }), [stats]);

  function payload(): RetrievalPayload {
    return {
      category,
      top_k: topK,
      retrieval_mode: retrievalMode,
      query_expansion: queryExpansion,
      rerank
    };
  }

  async function refreshAll() {
    const [statsData, healthData, knowledgeData, schedulerData, watcherData] = await Promise.all([
      ragApi.stats(),
      ragApi.vectorHealth(),
      ragApi.listKnowledge({ page: 1, page_size: 10, search_text: knowledgeSearch }),
      ragApi.schedulerStatus(),
      ragApi.watcherStatus()
    ]);
    setStats(statsData);
    setHealth(healthData);
    setKnowledge(knowledgeData);
    setScheduler(schedulerData);
    setWatcher(watcherData);
  }

  useEffect(() => {
    void refreshAll().catch((error) => setNotice(error instanceof Error ? error.message : "加载失败"));
    void ragApi.graph({ limit: 80 }).then(setGraph).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAsk() {
    if (!question.trim()) return;
    setBusy("ask");
    setAnswer("");
    setSources([]);
    try {
      const result: AskResponse = await ragApi.ask({
        ...payload(),
        question,
        use_llm: useLlm,
        conversation_id: conversationId
      });
      setConversationId(result.conversation_id || null);
      setQueryLogId(result.query_log_id || null);
      setSources(result.sources || []);
      let typed = "";
      for (const char of result.answer || "") {
        typed += char;
        setAnswer(typed);
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
      setNotice(result.llm_used ? `LLM answered with ${result.model}` : "使用本地摘录式回答");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "问答失败");
    } finally {
      setBusy("");
    }
  }

  async function saveCurrentAnswer() {
    if (!answer.trim()) {
      setNotice("当前没有可保存的回答。");
      return;
    }
    setBusy("save-answer");
    try {
      const result = await ragApi.saveAnswer({
        title: `RAG回答-${question.slice(0, 30)}`,
        question,
        answer,
        sources,
        query_log_id: queryLogId,
        conversation_id: conversationId
      });
      setNotice(`回答已保存为 Markdown：${result.file_path}`);
      await refreshAll();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusy("");
    }
  }

  async function saveKnowledge() {
    if (!knowledgeTitle.trim() || !knowledgeContent.trim()) {
      setNotice("请填写标题和内容。");
      return;
    }
    setBusy("knowledge");
    try {
      await ragApi.createKnowledge({ title: knowledgeTitle, content: knowledgeContent, source_kind: "manual" });
      setKnowledgeTitle("");
      setKnowledgeContent("");
      setNotice("知识已保存、切块、embedding 并写入 Chroma。");
      await refreshAll();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "保存知识失败");
    } finally {
      setBusy("");
    }
  }

  async function uploadTxt(file?: File | null) {
    if (!file) return;
    const text = await file.text();
    setKnowledgeTitle(file.name.replace(/\.[^.]+$/, ""));
    setKnowledgeContent(text);
    setNotice(`已读取 ${file.name}，确认后点击保存知识。`);
  }

  async function runSemanticStream() {
    setBusy("semantic");
    setSemanticText("");
    try {
      const response = await ragApi.streamKnowledgeSearch({
        query: semanticQuery,
        top_k: topK,
        retrieval_mode: retrievalMode,
        query_expansion: queryExpansion,
        rerank
      });
      if (!response.body) throw new Error("流式响应不可用");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setSemanticText((current) => current + decoder.decode(value, { stream: true }));
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "流式检索失败");
    } finally {
      setBusy("");
    }
  }

  async function runIndex(rebuild: boolean) {
    setBusy(rebuild ? "rebuild" : "incremental");
    try {
      const result = rebuild ? await ragApi.index({ category, rebuild: true }) : await ragApi.incrementalIndex({ category });
      setNotice(JSON.stringify(result));
      await refreshAll();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "索引失败");
    } finally {
      setBusy("");
    }
  }

  async function runEval() {
    setBusy("eval");
    try {
      await ragApi.createEvalCase({ query: evalQuery, expected_document: evalExpected, category });
      const result = await ragApi.runEval({ top_k: topK, retrieval_mode: retrievalMode, query_expansion: queryExpansion, rerank });
      setEvalResult(result);
      setNotice(`评测完成：Hit ${result.hit_count}/${result.case_count}，命中率 ${(result.hit_rate * 100).toFixed(1)}%`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "评测失败");
    } finally {
      setBusy("");
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-lg bg-blue-600 text-sm font-black text-white">R</div>
            <div>
              <h1 className="text-base font-black">RAG Knowledge Base</h1>
              <p className="text-xs text-slate-500">Chroma + OpenAI embedding + incremental indexing</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={health?.status === "ok" ? "success" : "warning"}>Chroma {health?.status || "unknown"}</Badge>
            <Badge variant={stats?.embedding_provider === "openai" ? "success" : "secondary"}>{stats?.embedding_model || "embedding"}</Badge>
            <Badge>{API_BASE}</Badge>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] grid-cols-[220px_minmax(0,1fr)_340px] gap-5 px-6 py-5 max-[1150px]:grid-cols-1">
        <aside className="space-y-3">
          {["Ask", "Knowledge", "Semantic Search", "Index Ops", "Graph", "Evaluation", "Settings"].map((item) => (
            <a key={item} href={`#${item.toLowerCase().replace(/\s+/g, "-")}`} className="block rounded-md px-3 py-2 text-sm font-bold text-slate-600 hover:bg-white hover:text-blue-700">
              {item}
            </a>
          ))}
        </aside>

        <section className="space-y-5">
          {notice ? <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">{notice}</div> : null}

          <div className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-2">
            <Card><CardContent className="p-4"><FileText className="mb-3 size-5 text-blue-600" /><div className="text-2xl font-black">{formatNumber(stats?.documents || 0)}</div><p className="text-xs text-slate-500">Documents</p></CardContent></Card>
            <Card><CardContent className="p-4"><BookOpen className="mb-3 size-5 text-blue-600" /><div className="text-2xl font-black">{formatNumber(stats?.chunks || 0)}</div><p className="text-xs text-slate-500">Chunks</p></CardContent></Card>
            <Card><CardContent className="p-4"><Database className="mb-3 size-5 text-blue-600" /><div className="text-2xl font-black">{formatNumber(stats?.chroma_vectors || 0)}</div><p className="text-xs text-slate-500">Chroma vectors</p></CardContent></Card>
            <Card><CardContent className="p-4"><Timer className="mb-3 size-5 text-blue-600" /><div className="text-2xl font-black">{scheduler?.enabled ? "On" : "Off"}</div><p className="text-xs text-slate-500">Scheduler</p></CardContent></Card>
          </div>

          <Card id="ask">
            <CardHeader>
              <CardTitle>知识库问答工作台</CardTitle>
              <CardDescription>支持多轮上下文、来源证据、流式打字效果和回答保存为 Markdown。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea className="min-h-28" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="请输入问题..." />
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void runAsk()} disabled={busy === "ask"}><Play className="size-4" />发送</Button>
                <Button variant="secondary" onClick={() => { setConversationId(null); setAnswer(""); setSources([]); }}>新对话</Button>
                <Button variant="secondary" onClick={() => void saveCurrentAnswer()} disabled={busy === "save-answer"}><Save className="size-4" />保存为 Markdown</Button>
                <Badge>conversation {conversationId || "new"}</Badge>
                <Badge>{sourcesLabel(sources)}</Badge>
              </div>
              <div className="min-h-40 whitespace-pre-wrap rounded-md border bg-white p-4 text-sm leading-7">{answer || "答案会显示在这里。"}</div>
              <div className="grid grid-cols-2 gap-3 max-[900px]:grid-cols-1">
                {sources.map((source, index) => (
                  <article key={`${source.chunk_id}-${index}`} className="rounded-md border bg-white p-3">
                    <div className="flex justify-between gap-3">
                      <strong>[{index + 1}] {source.title}</strong>
                      <Badge>{score(source.score)}</Badge>
                    </div>
                    <p className="mt-1 break-all text-xs text-slate-500">{source.file_path}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{compactText(source.content, 260)}</p>
                  </article>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card id="knowledge">
            <CardHeader>
              <CardTitle>知识库管理</CardTitle>
              <CardDescription>支持直接输入文本和 TXT 上传。PDF/DOCX 通过索引扫描进入，PDF OCR 默认关闭。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-[minmax(0,1fr)_240px] gap-3 max-[760px]:grid-cols-1">
                <Input value={knowledgeTitle} onChange={(event) => setKnowledgeTitle(event.target.value)} placeholder="标题" />
                <Input type="file" accept=".txt,text/plain" onChange={(event) => void uploadTxt(event.target.files?.[0])} />
              </div>
              <Textarea className="min-h-32" value={knowledgeContent} onChange={(event) => setKnowledgeContent(event.target.value)} placeholder="粘贴知识内容..." />
              <Button onClick={() => void saveKnowledge()} disabled={busy === "knowledge"}><Upload className="size-4" />保存知识</Button>
              <div className="flex gap-2">
                <Input value={knowledgeSearch} onChange={(event) => setKnowledgeSearch(event.target.value)} placeholder="搜索标题或路径" />
                <Button variant="secondary" onClick={() => void refreshAll()}><Search className="size-4" />刷新</Button>
              </div>
              <div className="overflow-auto rounded-md border bg-white">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="bg-slate-100 text-xs text-slate-500">
                    <tr><th className="p-3">标题</th><th className="p-3">类型</th><th className="p-3">Chunks</th><th className="p-3">更新时间</th></tr>
                  </thead>
                  <tbody>
                    {knowledge.items.map((item) => (
                      <tr key={item.id} className="border-t">
                        <td className="p-3"><strong>{item.title}</strong><p className="break-all text-xs text-slate-500">{item.file_path}</p></td>
                        <td className="p-3">{item.document_type}</td>
                        <td className="p-3">{item.chunk_count}</td>
                        <td className="p-3">{formatDate(item.updated_at || item.indexed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card id="semantic-search">
            <CardHeader>
              <CardTitle>语义检索流式返回</CardTitle>
              <CardDescription>输入知识库里的概念，返回相关知识条目，支持流式文本。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input value={semanticQuery} onChange={(event) => setSemanticQuery(event.target.value)} />
                <Button onClick={() => void runSemanticStream()} disabled={busy === "semantic"}>流式查询</Button>
              </div>
              <div className="min-h-28 whitespace-pre-wrap rounded-md border bg-white p-4 text-sm leading-7">{semanticText || "流式查询结果会显示在这里。"}</div>
            </CardContent>
          </Card>

          <Card id="graph">
            <CardHeader>
              <CardTitle>Obsidian 双链图谱过滤</CardTitle>
              <CardDescription>扫描 Markdown 中的 [[双链]]，只读不改原始笔记。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="secondary" onClick={() => void ragApi.graph({ category, limit: 120 }).then(setGraph)}>刷新图谱</Button>
              <div className="grid grid-cols-3 gap-3 max-[760px]:grid-cols-1">
                <Badge>{graph?.total_files_scanned || 0} files scanned</Badge>
                <Badge>{graph?.nodes.length || 0} nodes</Badge>
                <Badge>{graph?.edges.length || 0} edges</Badge>
              </div>
              <div className="max-h-60 overflow-auto rounded-md border bg-white p-3">
                {(graph?.nodes || []).slice(0, 20).map((node) => (
                  <div key={node.id} className="flex justify-between border-b py-2 text-sm">
                    <span>{node.label}</span>
                    <Badge>{node.degree}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card id="evaluation">
            <CardHeader>
              <CardTitle>RAG 评测集和命中率</CardTitle>
              <CardDescription>用 query + expected document 评估 Top K 命中率。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3 max-[760px]:grid-cols-1">
                <Input value={evalQuery} onChange={(event) => setEvalQuery(event.target.value)} placeholder="测试问题" />
                <Input value={evalExpected} onChange={(event) => setEvalExpected(event.target.value)} placeholder="期望命中文档关键词" />
              </div>
              <Button onClick={() => void runEval()} disabled={busy === "eval"}><ShieldCheck className="size-4" />添加用例并运行评测</Button>
              {evalResult ? (
                <div className="rounded-md border bg-white p-3 text-sm">
                  <strong>Hit rate: {(evalResult.hit_rate * 100).toFixed(1)}%</strong>
                  <p>{evalResult.hit_count}/{evalResult.case_count} hit</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </section>

        <aside className="space-y-5">
          <Card id="settings">
            <CardHeader>
              <CardTitle>检索设置</CardTitle>
              <CardDescription>Rerank 默认关闭，避免 cross-encoder / LLM rerank 产生额外成本。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <select className="min-h-10 w-full rounded-md border bg-white px-3 text-sm" value={category} onChange={(event) => setCategory(event.target.value)}>
                {categories.map(([key, label]) => <option key={key} value={key}>{key} {label ? `- ${label}` : ""}</option>)}
              </select>
              <select className="min-h-10 w-full rounded-md border bg-white px-3 text-sm" value={retrievalMode} onChange={(event) => setRetrievalMode(event.target.value as RetrievalMode)}>
                <option value="hybrid">hybrid</option>
                <option value="vector">vector</option>
                <option value="keyword">keyword</option>
              </select>
              <select className="min-h-10 w-full rounded-md border bg-white px-3 text-sm" value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
                {[5, 8, 12, 16, 20].map((value) => <option key={value} value={value}>Top K {value}</option>)}
              </select>
              {[
                ["使用 LLM 回答", useLlm, setUseLlm],
                ["Query expansion", queryExpansion, setQueryExpansion],
                ["Optional rerank", rerank, setRerank]
              ].map(([label, checked, setter]) => (
                <label key={String(label)} className="flex items-center justify-between text-sm font-semibold">
                  {String(label)}
                  <input type="checkbox" checked={Boolean(checked)} onChange={(event) => (setter as (value: boolean) => void)(event.target.checked)} className="size-4 accent-blue-600" />
                </label>
              ))}
            </CardContent>
          </Card>

          <Card id="index-ops">
            <CardHeader>
              <CardTitle>索引与向量库运维</CardTitle>
              <CardDescription>Chroma 是当前真正向量库；SQLite embeddings 作为可重建来源。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="rounded-md border bg-white p-3">
                <div>SQLite embeddings: {formatNumber(health?.sqlite_embeddings || 0)}</div>
                <div>Chroma vectors: {formatNumber(health?.chroma_vectors || 0)}</div>
                <div>Status: {health?.status || "unknown"}</div>
              </div>
              <Button className="w-full" variant="secondary" onClick={() => void runIndex(false)}><RefreshCcw className="size-4" />增量索引</Button>
              <Button className="w-full" variant="secondary" onClick={() => void runIndex(true)}>全量重建</Button>
              <Button className="w-full" onClick={() => void ragApi.rebuildVectorStore().then(() => refreshAll())}><Database className="size-4" />修复 Chroma</Button>
              <Button className="w-full" variant="secondary" onClick={() => void ragApi.startScheduler().then(setScheduler)}>{scheduler?.enabled ? "定时已开启" : "开启定时增量"}</Button>
              <Button className="w-full" variant="secondary" onClick={() => void ragApi.stopScheduler().then(setScheduler)}>停止定时</Button>
              <Button className="w-full" variant="secondary" onClick={() => void ragApi.startWatcher().then(setWatcher)}>{watcher?.enabled ? "监听已开启" : "开启文件监听"}</Button>
              <Button className="w-full" variant="secondary" onClick={() => void ragApi.stopWatcher().then(setWatcher)}>停止监听</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>API Key</CardTitle>
              <CardDescription>API Key 页面仍在原设置接口保存，不在前端明文回显。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-600">
              <p><KeyRound className="mr-2 inline size-4" />通过 `/api/rag/api-key` 配置 OpenAI Key。</p>
              <p>当前 API: {API_BASE}</p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  );
}
