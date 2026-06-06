from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api import rag
from app.database import init_db

app = FastAPI(title="RAG Knowledge Base", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "RAG Knowledge Base"}


app.include_router(rag.router, prefix="/api/rag", tags=["rag"])


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    html_path = Path(__file__).parent / "frontend" / "index.html"
    return html_path.read_text(encoding="utf-8")
