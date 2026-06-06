# RAG Knowledge Base

## Frontend Upgrade: Next.js + shadcn/ui Style

本项目现在保留两套前端入口：

- `frontend/index.html`：旧版 FastAPI 静态页面，作为可回滚版本保留。
- `frontend/app`：新版正式前端，使用 `Next.js + React + TypeScript + Tailwind CSS + shadcn/ui 风格组件`。

推荐日常开发使用新版 Next 前端：

```powershell
cd D:\github仓库\RAG-Knowledge-Base
python -m uvicorn main:app --reload --port 8020

cd D:\github仓库\RAG-Knowledge-Base\frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:3000
```

生产构建：

```powershell
cd D:\github仓库\RAG-Knowledge-Base\frontend
npm run build
```

新版前端默认调用：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8020
```

如果需要修改后端地址，请复制 `frontend/.env.local.example` 为 `frontend/.env.local`。不要把 `OPENAI_API_KEY` 写进前端环境变量；API Key 继续由 FastAPI 后端管理，前端不会回显明文。

这是一个独立的个人知识库 RAG 问答项目，用于把 `D:\My-Knowledge-Base` 中的 Obsidian / Markdown / PDF / DOCX 资料索引成可检索、可问答的知识库。

它和 AgentOS 是两个项目：

- **AgentOS**：多 Agent 管理平台，负责 Agent 注册、运行、队列、日志、配置、权限和工作流。
- **RAG Knowledge Base**：知识库问答系统，负责文档扫描、切块、索引、向量检索、引用来源和问答。

两者可以集成，但不混为一个项目。未来 AgentOS 可以把本项目注册为一个外部 RAG Agent 或外部服务入口。

## 当前能力

- 扫描 Obsidian 知识库
- 支持 `.md`、`.pdf`、`.docx`
- 跳过 `node_modules`、`.next`、`.git`、`venv` 等无关目录
- 按 Markdown heading / 文档段落切块
- 写入 SQLite
- 使用 SQLite FTS5 做关键词检索
- 使用 embedding 做向量检索
- 支持 `keyword`、`vector`、`hybrid` 三种检索模式
- 支持本地 query expansion，把同义词、领域词和常见表达补进检索
- 支持轻量 reranker，按标题、路径、片段覆盖度重新加权
- 默认使用本地哈希 embedding，无需 API Key
- 可选 OpenAI embeddings，推荐 `text-embedding-3-small`
- 使用 Chroma 作为持久化向量库
- 支持增量索引：只处理新增、修改、删除文件
- 支持本地摘录式回答
- 可选 OpenAI-compatible LLM 综合回答
- 返回来源文件、标题、小节、相关性分数
- 记录查询历史
- 提供内置 Web 问答界面

## 启动

```powershell
cd D:\github仓库\RAG-Knowledge-Base
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8020
```

打开：

```text
http://127.0.0.1:8020
```

API 文档：

```text
http://127.0.0.1:8020/docs
```

## Web UI

当前 Web UI 被设计成一个独立的 RAG 问答工作台，核心区域包括：

- 左侧项目说明和检索导航，明确本项目与 AgentOS 分离。
- 顶部运行状态，展示服务连接状态、向量库和 Chroma collection。
- 提问控制台，支持 `hybrid`、`vector`、`keyword` 三种检索模式。
- 索引操作，支持增量索引和全量重建。
- 统计卡片，展示文档数、chunk 数、embedding 数和 Chroma 向量数。
- 回答面板，展示本地摘录式回答或 LLM 综合回答。
- 来源证据卡片，展示文件路径、标题、小节、片段内容和相关度分数。
- 最近提问历史，方便快速复用问题。
- API Key / LLM 配置面板，支持在本地 Web UI 中配置 `OPENAI_API_KEY`、问答模型、Base URL 和 embedding 模型。
- 知识管理面板，支持分页查看、新增、编辑、删除、上传 txt 和直接输入文本。
- 语义查询面板，支持按内容相关性查找知识库，并提供逐字流式返回。
- 向量库维护面板，支持检查 Chroma 健康状态，并从 SQLite embedding 重建 Chroma。
- 检索增强开关，支持开启 / 关闭 query expansion 和轻量 rerank。

设计原则：

- RAG 问答优先展示“答案 + 来源证据”，避免只给结论。
- 检索设置靠近提问区域，方便快速切换范围和检索模式。
- Knowledge Base 是独立问答项目，不把 AgentOS 的运行管理功能混入本页面。

## 知识库 CRUD 与语义查询

当前 RAG Knowledge Base 不只支持扫描本地 Obsidian 文件，也支持通过 Web UI 直接管理知识内容。

知识管理能力：

- 分页查看知识条目。
- 按标题、路径、文件名搜索知识条目。
- 直接输入文本并保存为知识条目。
- 上传 `.txt` 文件，浏览器读取文本后再保存。
- 编辑知识标题和内容。
- 删除知识条目及其索引。
- 新增或更新后自动切块、写入 SQLite FTS、生成 embedding，并尽力写入 Chroma。

语义查询能力：

- `hybrid`：关键词 + 向量混合检索，推荐默认使用。
- `vector`：向量语义检索。
- `keyword`：关键词检索。
- 返回相关知识库标题、路径、命中片段、相关度分数。
- 支持流式返回，文字会逐步出现，接近对话产品的响应体验。

示例：

- 上传朱自清《春》，搜索 `春天` 应该可以找到《春》。
- 上传鲁迅《故乡》，搜索 `少年闰土` 应该可以找到《故乡》。
- 如果文本中有足够语义信息，搜索 `小孩子` 也可以召回《故乡》相关内容。

相关 API：

```text
GET    /api/rag/knowledge?page=1&page_size=10&search_text=
GET    /api/rag/knowledge/{document_id}
POST   /api/rag/knowledge
PUT    /api/rag/knowledge/{document_id}
DELETE /api/rag/knowledge/{document_id}
POST   /api/rag/knowledge/search
POST   /api/rag/knowledge/search/stream
POST   /api/rag/query/expand
```

注意：

- 删除 Web UI 创建或索引中的知识条目，只会删除当前 RAG 索引记录，不会删除原始 Obsidian 文件。
- 如果本地 Chroma 索引临时不可用，系统会继续保留 SQLite FTS 和 SQLite embedding 兜底，避免知识保存失败。

## Query Expansion 与轻量 Rerank

为了提高语义召回率，系统新增了两层低成本增强：

1. `query_expansion`：本地规则扩展，不调用 LLM，也不会额外消耗 OpenAI token。例如 `儿童` 会扩展出 `小孩子`、`孩子`、`少年闰土`、`闰土` 等候选词。
2. `rerank`：轻量重排，不引入新依赖。它会根据原始 query、扩展词在标题、路径、小节和片段正文中的覆盖度，对初始检索结果加权。

默认推荐：

- 日常问答：`hybrid + query_expansion + rerank`
- 想看纯关键词效果：`keyword`，可关闭 rerank 对比
- 想看纯向量效果：`vector`，但默认仍会用扩展词作为低权重 lexical hint，避免明显语义漏召

新增 API：

```text
POST /api/rag/query/expand
```

请求示例：

```json
{
  "query": "儿童"
}
```

响应示例：

```json
{
  "query": "儿童",
  "variants": ["儿童", "小孩子", "儿童 小孩子", "孩子"]
}
```

检索请求可显式控制：

```json
{
  "query": "儿童",
  "retrieval_mode": "hybrid",
  "query_expansion": true,
  "rerank": true,
  "top_k": 8
}
```

环境变量：

```text
RAG_QUERY_EXPANSION_DEFAULT=true
RAG_RERANK_DEFAULT=true
RAG_MAX_QUERY_EXPANSIONS=8
```

当前版本的 reranker 是规则版，不是 cross-encoder，也不会调用 LLM。好处是便宜、稳定、可解释；限制是复杂语义判断仍不如真正的重排模型。

## Chroma 向量库修复 / 重建

如果出现以下情况，可以使用 Web UI 右侧的 `向量库维护` 面板：

- `Chroma Vectors` 显示为 0，但 SQLite embeddings 不为 0。
- Chroma HNSW 报错。
- 向量检索异常，但 SQLite embedding 仍存在。
- 本地 Chroma 目录状态损坏。

重建逻辑：

1. 清空本地 Chroma 持久化目录。
2. 重新创建 Chroma collection。
3. 从 SQLite 的 `rag_embeddings` 表读取已经生成好的 embedding。
4. 按批次把向量、chunk 内容和 metadata 写回 Chroma。
5. 刷新 Chroma count 和健康状态。

这个过程不会重新调用 OpenAI，也不会重新计算 embedding，不会删除知识内容。

相关 API：

```text
GET  /api/rag/vector-store/health
POST /api/rag/vector-store/rebuild
```

## API Key 配置

你可以用两种方式配置 OpenAI API Key。

方式一：在 Web UI 中配置

1. 打开 `http://127.0.0.1:8020`。
2. 在右侧 `API Key / LLM 配置` 面板中粘贴 `OPENAI_API_KEY`。
3. 根据需要调整问答模型、Base URL、embedding provider 和 embedding model。
4. 点击 `保存配置`。

保存后：

- API Key 会写入本项目本地 `.env` 文件。
- `.env` 已在 `.gitignore` 中，不会被 Git 提交。
- 页面只显示 Key 的掩码，不会回显明文。
- 当前后端进程会立即更新环境变量，不一定需要重启。

方式二：手动创建 `.env`

```text
OPENAI_API_KEY=你的 key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_EMBEDDING_FALLBACK_TO_LOCAL=true
```

如果没有配置 `OPENAI_API_KEY`：

- 问答会自动回退为本地摘录式回答。
- OpenAI embedding 会自动回退为本地 hash embedding。
- 系统仍可本地运行，只是语义质量弱于真实 embedding / LLM。

如果你从本地 hash embedding 切换到 OpenAI `text-embedding-3-small`，建议执行一次全量重建索引，让已有向量被替换为真实 OpenAI embedding。

## 环境变量

```text
RAG_KB_ROOT=D:\My-Knowledge-Base
RAG_DATABASE_URL=sqlite:///./data/rag_knowledge_base.db
RAG_DEFAULT_TOP_K=8

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1

RAG_EMBEDDING_PROVIDER=local_hash
RAG_EMBEDDING_MODEL=local-hash-v1
RAG_EMBEDDING_DIMENSIONS=384
```

默认配置会尝试使用 OpenAI `text-embedding-3-small`。如果没有 `OPENAI_API_KEY` 且 `RAG_EMBEDDING_FALLBACK_TO_LOCAL=true`，系统会自动回退到本地哈希 embedding，保证索引流程不中断。

如果想使用 OpenAI embedding：

```text
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=你的 key
```

设置后需要重新全量索引，已有本地哈希向量才会被替换为 `text-embedding-3-small` 向量。

Chroma 配置：

```text
RAG_VECTOR_STORE=chroma
RAG_CHROMA_PATH=./data/chroma
RAG_CHROMA_COLLECTION=rag_knowledge_base
RAG_CHROMA_SHARD_SIZE=500
RAG_QUERY_EXPANSION_DEFAULT=true
RAG_RERANK_DEFAULT=true
RAG_MAX_QUERY_EXPANSIONS=8
```

## API

```text
GET  /api/health
GET  /api/rag/stats
POST /api/rag/index
POST /api/rag/search
POST /api/rag/ask
GET  /api/rag/history
```

## 索引

增量索引：

```json
{
  "category": "all",
  "rebuild": false
}
```

全量重建：

```json
{
  "category": "all",
  "rebuild": true
}
```

返回字段：

- `indexed_documents`
- `indexed_chunks`
- `embedded_chunks`
- `skipped_files`
- `deleted_documents`
- `errors`

## 检索模式

关键词检索：

```json
{
  "query": "AgentOS 和 RAG 的区别",
  "retrieval_mode": "keyword",
  "top_k": 8
}
```

向量检索：

```json
{
  "query": "AgentOS 和 RAG 的区别",
  "retrieval_mode": "vector",
  "top_k": 8
}
```

混合检索：

```json
{
  "query": "AgentOS 和 RAG 的区别",
  "retrieval_mode": "hybrid",
  "top_k": 8
}
```

推荐默认使用 `hybrid`。

## 问答模式

本地摘录式回答：

```json
{
  "question": "RAG 知识库现在支持哪些能力？",
  "retrieval_mode": "hybrid",
  "use_llm": false
}
```

LLM 综合回答：

```json
{
  "question": "RAG 知识库现在支持哪些能力？",
  "retrieval_mode": "hybrid",
  "use_llm": true
}
```

如果没有 `OPENAI_API_KEY`，即使 `use_llm=true`，系统也会自动回退为本地摘录式回答。

## PDF / DOCX 支持

PDF 使用 `pypdf` 抽取文本。

DOCX 使用 `python-docx` 抽取段落和表格文本。

限制：

- 扫描版 PDF 如果没有 OCR 文本层，无法抽取有效内容。
- 复杂表格、图片、脚注、批注暂不做高级解析。
- 当前只读取文本，不修改原始文件。

## 增量索引如何工作

系统会记录每个文件的：

- 相对路径
- 内容 hash
- 文件大小
- 修改时间
- 文档类型
- chunk 数量

增量索引时：

- hash 未变化：跳过
- 新文件：索引
- 修改文件：删除旧 chunk 和 embedding 后重建
- 已删除文件：从索引中移除

## 当前限制

- 本地哈希 embedding 是轻量近似方案，不等同于高质量语义模型。
- OpenAI embedding 会逐 chunk 调用接口，可能产生费用。
- 向量保存在 SQLite JSON 字段中，适合个人知识库规模，不适合百万级文档。
- Chroma 本地持久化目录建议只由当前 FastAPI 服务进程访问，不要多个 Python 进程同时打开同一个 collection。
- Query expansion 目前是本地规则词表，覆盖范围有限，需要根据评测结果持续补充。
- 轻量 reranker 不是深度语义模型，无法替代 cross-encoder / LLM rerank。
- 暂未实现文件监听，需要手动点击增量索引。
- 暂未支持 OCR、网页抓取、图片内容理解。

## 下一步路线

1. 加入真正的向量数据库，例如 Chroma、Qdrant 或 FAISS。
2. 增加文件监听和定时增量索引。
3. 增加 PDF OCR。
4. 增加 Obsidian 双链图谱过滤。
5. 增加回答保存为 Markdown 笔记。
6. 增加对话多轮上下文。
7. 增加 RAG 评测集和命中率统计。
8. 增加可选 cross-encoder reranker 或 LLM rerank，但默认关闭以控制成本。
