from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.services.indexer import index_knowledge_base


_state_lock = threading.Lock()
_scheduler = None
_watch_observer = None
_last_run: dict[str, Any] = {}
_running = False


def run_incremental_index(category: str = "all", limit: int | None = None) -> dict[str, Any]:
    global _last_run, _running
    with _state_lock:
        if _running:
            return {"status": "busy", "message": "An index job is already running.", "last_run": _last_run}
        _running = True
    started_at = datetime.utcnow()
    db = SessionLocal()
    try:
        result = index_knowledge_base(db, category=category, rebuild=False, limit=limit)
        payload = {
            "status": "ok" if not result.get("errors") else "partial",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "category": category,
            **result,
        }
        _last_run = payload
        return payload
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": "failed",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "category": category,
            "errors": [str(exc)],
        }
        _last_run = payload
        return payload
    finally:
        db.close()
        with _state_lock:
            _running = False


def _run_incremental_background() -> None:
    run_incremental_index()


def start_scheduler(interval_seconds: int | None = None) -> dict[str, Any]:
    global _scheduler
    if _scheduler:
        return scheduler_status()
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return {"enabled": False, "error": "apscheduler is not installed."}

    interval = max(30, int(interval_seconds or settings.index_scheduler_interval_seconds))
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_incremental_background, "interval", seconds=interval, id="rag_incremental_index")
    scheduler.start()
    _scheduler = scheduler
    return scheduler_status()


def stop_scheduler() -> dict[str, Any]:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    return scheduler_status()


def scheduler_status() -> dict[str, Any]:
    jobs = []
    if _scheduler:
        for job in _scheduler.get_jobs():
            jobs.append({"id": job.id, "next_run_time": str(job.next_run_time)})
    return {
        "enabled": bool(_scheduler),
        "jobs": jobs,
        "last_run": _last_run,
        "running": _running,
        "interval_seconds": settings.index_scheduler_interval_seconds,
    }


def start_file_watcher(kb_root: str | None = None) -> dict[str, Any]:
    global _watch_observer
    if _watch_observer:
        return watcher_status()
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return {"enabled": False, "error": "watchdog is not installed."}

    root = Path(kb_root).resolve() if kb_root else settings.kb_root
    if not root.exists():
        return {"enabled": False, "error": f"Knowledge root does not exist: {root}"}

    class Handler(FileSystemEventHandler):
        def on_created(self, event):  # noqa: ANN001
            if not event.is_directory:
                threading.Thread(target=_run_incremental_background, daemon=True).start()

        def on_modified(self, event):  # noqa: ANN001
            if not event.is_directory:
                threading.Thread(target=_run_incremental_background, daemon=True).start()

        def on_deleted(self, event):  # noqa: ANN001
            if not event.is_directory:
                threading.Thread(target=_run_incremental_background, daemon=True).start()

    observer = Observer()
    observer.schedule(Handler(), str(root), recursive=True)
    observer.start()
    _watch_observer = observer
    return watcher_status()


def stop_file_watcher() -> dict[str, Any]:
    global _watch_observer
    if _watch_observer:
        _watch_observer.stop()
        _watch_observer.join(timeout=3)
        _watch_observer = None
    return watcher_status()


def watcher_status() -> dict[str, Any]:
    return {
        "enabled": bool(_watch_observer),
        "kb_root": str(settings.kb_root),
        "last_run": _last_run,
        "running": _running,
    }
