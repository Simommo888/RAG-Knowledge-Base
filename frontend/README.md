# RAG Knowledge Base Frontend

This is the Next.js + React + TypeScript frontend for the standalone RAG Knowledge Base project.

It is separate from AgentOS. AgentOS is an Agent management platform; this frontend is for knowledge base question answering, semantic retrieval, Chroma health, API key settings, and knowledge CRUD.

## Start Backend First

```powershell
cd D:\github仓库\RAG-Knowledge-Base
python -m uvicorn main:app --reload --port 8020
```

## Start Frontend

```powershell
cd D:\github仓库\RAG-Knowledge-Base\frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

## API Base URL

By default, the frontend calls:

```text
http://127.0.0.1:8020
```

To override it, create `frontend/.env.local`:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8020
```

Do not put `OPENAI_API_KEY` in `.env.local`. The API key is managed by the FastAPI backend and is never displayed in plaintext by the frontend.

## Build

```powershell
npm run build
```

The static `frontend/index.html` is kept as a rollback version. The formal frontend is now the Next.js app under `frontend/app`.
