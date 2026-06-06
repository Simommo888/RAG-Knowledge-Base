import fnmatch
import os
from pathlib import Path

from app.config import CATEGORY_DIRS, DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_FILES, SUPPORTED_EXTENSIONS, settings


def resolve_kb_root(kb_root: str | None = None) -> Path:
    return Path(kb_root).resolve() if kb_root else settings.kb_root


def category_prefix(category: str = "all") -> str:
    return CATEGORY_DIRS.get(category, category).replace("\\", "/").strip("/")


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_excluded_dir(path: Path, root: Path) -> bool:
    relative = relative_path(path, root)
    parts = set(relative.split("/"))
    return path.name in DEFAULT_EXCLUDED_DIRS or bool(parts.intersection(DEFAULT_EXCLUDED_DIRS))


def _is_excluded_file(path: Path, root: Path) -> bool:
    relative = relative_path(path, root)
    return any(fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(relative, pattern) for pattern in DEFAULT_EXCLUDED_FILES)


def iter_source_files(root: Path, category: str = "all") -> list[Path]:
    if not root.exists():
        return []
    prefix = category_prefix(category)
    files: list[Path] = []
    for current_root, dir_names, file_names in os.walk(root):
        current = Path(current_root)
        dir_names[:] = [name for name in dir_names if not _is_excluded_dir(current / name, root)]
        for file_name in file_names:
            path = current / file_name
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if _is_excluded_file(path, root):
                continue
            if prefix and not relative_path(path, root).startswith(prefix):
                continue
            files.append(path)
    return sorted(files, key=lambda item: item.as_posix())


def iter_markdown_files(root: Path, category: str = "all") -> list[Path]:
    return [path for path in iter_source_files(root, category=category) if path.suffix.lower() == ".md"]


def read_text(path: Path, limit: int = 1_500_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""
