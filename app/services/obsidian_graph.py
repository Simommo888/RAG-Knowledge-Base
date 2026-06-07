import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.scanner import iter_markdown_files, read_text, relative_path, resolve_kb_root

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def build_obsidian_graph(
    kb_root: str | None = None,
    category: str = "all",
    search_text: str = "",
    min_degree: int = 0,
    limit: int = 200,
) -> dict[str, Any]:
    root = resolve_kb_root(kb_root)
    files = iter_markdown_files(root, category=category)
    title_to_path: dict[str, str] = {}
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    scanned = 0

    for path in files:
        scanned += 1
        source_title = path.stem
        source_path = relative_path(path, root)
        title_to_path[source_title] = source_path
        text = read_text(path, limit=300_000)
        for raw_target in WIKILINK_RE.findall(text):
            target = raw_target.strip()
            if not target:
                continue
            outgoing[source_title].add(target)
            incoming[target].add(source_title)

    all_titles = set(title_to_path) | set(incoming) | set(outgoing)
    query = search_text.strip().lower()
    nodes = []
    for title in all_titles:
        degree = len(incoming.get(title, set())) + len(outgoing.get(title, set()))
        if degree < min_degree:
            continue
        file_path = title_to_path.get(title, "")
        if query and query not in title.lower() and query not in file_path.lower():
            continue
        nodes.append({"id": title, "label": title, "file_path": file_path, "degree": degree})

    nodes.sort(key=lambda item: (item["degree"], item["label"]), reverse=True)
    nodes = nodes[: max(1, min(limit, 1000))]
    allowed = {item["id"] for item in nodes}
    edges = []
    for source, targets in outgoing.items():
        if source not in allowed:
            continue
        for target in targets:
            if target in allowed:
                edges.append({"source": source, "target": target, "label": "wikilink"})

    return {"nodes": nodes, "edges": edges, "total_files_scanned": scanned}
