import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"


def _load_local_env() -> None:
    if not LOCAL_ENV_PATH.exists():
        return
    for raw_line in LOCAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


class Settings:
    kb_root: Path = Path(os.getenv("RAG_KB_ROOT", r"D:\My-Knowledge-Base")).resolve()
    database_url: str = os.getenv("RAG_DATABASE_URL", "sqlite:///./data/rag_knowledge_base.db")
    default_top_k: int = int(os.getenv("RAG_DEFAULT_TOP_K", "8"))
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    embedding_provider: str = os.getenv("RAG_EMBEDDING_PROVIDER", "openai")
    embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "1536"))
    embedding_fallback_to_local: bool = os.getenv("RAG_EMBEDDING_FALLBACK_TO_LOCAL", "true").lower() == "true"
    vector_store: str = os.getenv("RAG_VECTOR_STORE", "chroma")
    chroma_path: str = os.getenv("RAG_CHROMA_PATH", "./data/chroma_openai")
    chroma_collection: str = os.getenv("RAG_CHROMA_COLLECTION", "rag_knowledge_base")
    chroma_shard_size: int = int(os.getenv("RAG_CHROMA_SHARD_SIZE", "500"))
    query_expansion_default: bool = os.getenv("RAG_QUERY_EXPANSION_DEFAULT", "true").lower() == "true"
    rerank_default: bool = os.getenv("RAG_RERANK_DEFAULT", "false").lower() == "true"
    rerank_strategy: str = os.getenv("RAG_RERANK_STRATEGY", "none").strip().lower()
    max_query_expansions: int = int(os.getenv("RAG_MAX_QUERY_EXPANSIONS", "8"))
    pdf_ocr_enabled: bool = os.getenv("RAG_PDF_OCR_ENABLED", "false").lower() == "true"
    pdf_ocr_max_pages: int = int(os.getenv("RAG_PDF_OCR_MAX_PAGES", "5"))
    index_scheduler_interval_seconds: int = int(os.getenv("RAG_INDEX_SCHEDULER_INTERVAL_SECONDS", "300"))
    saved_answers_dir: str = os.getenv("RAG_SAVED_ANSWERS_DIR", "04_Resources/RAG-Answers")


settings = Settings()


DEFAULT_EXCLUDED_DIRS = {
    "node_modules",
    ".next",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".turbo",
    "coverage",
    ".trash",
    "data",
}

DEFAULT_EXCLUDED_FILES = {
    "*.pyc",
    "*.log",
    "*.tmp",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}


CATEGORY_DIRS = {
    "all": "",
    "Inbox": "00_Inbox",
    "Dashboard": "01_Dashboard",
    "Projects": "02_Projects",
    "Areas": "03_Areas",
    "Resources": "04_Resources",
    "AI News": "04_Resources/AI-News",
    "AgentOS": "04_Resources/AgentOS",
    "Permanent Notes": "05_Permanent-Notes",
    "Outputs": "06_Outputs",
    "Templates": "07_Templates",
    "Prompts": "09_Prompts",
    "Error Fixes": "10_Error-Fixes",
    "Business Ideas": "11_Business-Ideas",
}
