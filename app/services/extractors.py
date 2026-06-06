from pathlib import Path


def extract_markdown(path: Path, limit: int = 1_500_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def extract_pdf(path: Path, limit: int = 1_500_000) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[PDF extraction unavailable: install pypdf]"

    try:
        reader = PdfReader(str(path))
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"# Page {index}\n\n{text.strip()}")
            if sum(len(item) for item in pages) >= limit:
                break
        return "\n\n".join(pages)[:limit]
    except Exception as exc:  # noqa: BLE001
        return f"[PDF extraction failed: {exc}]"


def extract_docx(path: Path, limit: int = 1_500_000) -> str:
    try:
        from docx import Document
    except ImportError:
        return "[DOCX extraction unavailable: install python-docx]"

    try:
        document = Document(str(path))
        blocks: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                blocks.append(text)
            if sum(len(item) for item in blocks) >= limit:
                break
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        return "\n\n".join(blocks)[:limit]
    except Exception as exc:  # noqa: BLE001
        return f"[DOCX extraction failed: {exc}]"


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return extract_markdown(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".docx":
        return extract_docx(path)
    return ""


def document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    return "unknown"
