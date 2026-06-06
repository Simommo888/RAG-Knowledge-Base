from pathlib import Path


MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP = 160


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


def title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:280] or path.stem
    return path.stem[:280]


def chunk_markdown(text: str) -> list[dict[str, str]]:
    text = strip_frontmatter(text).replace("\r\n", "\n")
    sections: list[dict[str, str]] = []
    heading = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if lines:
                sections.append({"heading": heading, "content": "\n".join(lines).strip()})
                lines = []
            heading = line.lstrip("#").strip()[:280]
        lines.append(line)
    if lines:
        sections.append({"heading": heading, "content": "\n".join(lines).strip()})

    chunks: list[dict[str, str]] = []
    for section in sections:
        content = section["content"].strip()
        if not content:
            continue
        start = 0
        while start < len(content):
            end = min(start + MAX_CHUNK_CHARS, len(content))
            chunk = content[start:end].strip()
            if chunk:
                chunks.append({"heading": section["heading"], "content": chunk})
            if end >= len(content):
                break
            start = max(0, end - CHUNK_OVERLAP)
    return chunks
