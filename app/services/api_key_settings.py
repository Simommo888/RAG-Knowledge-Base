import os
import re
from pathlib import Path
from urllib.parse import urlparse

from app.config import LOCAL_ENV_PATH, settings


MANAGED_KEYS = {
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "RAG_EMBEDDING_PROVIDER",
    "RAG_EMBEDDING_MODEL",
    "RAG_EMBEDDING_FALLBACK_TO_LOCAL",
}


def _read_env_file(path: Path = LOCAL_ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_file(values: dict[str, str], path: Path = LOCAL_ENV_PATH) -> None:
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    written: set[str] = set()
    output: list[str] = []

    for raw_line in existing_lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            output.append(raw_line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in values:
            output.append(f"{key}={_quote_env_value(values[key])}")
            written.add(key)
        elif key in MANAGED_KEYS:
            continue
        else:
            output.append(raw_line)

    for key in MANAGED_KEYS:
        if key in values and key not in written:
            output.append(f"{key}={_quote_env_value(values[key])}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _quote_env_value(value: str) -> str:
    if not value:
        return ""
    if re.search(r"\s|#|=", value):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _mask_key(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) <= 12:
        return f"{value[:3]}...{value[-2:]}"
    return f"{value[:7]}...{value[-4:]}"


def _validate_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OPENAI_BASE_URL 必须是有效的 http/https URL。")
    return value


def _validate_embedding_provider(value: str) -> str:
    provider = value.strip().lower()
    if provider not in {"openai", "local_hash"}:
        raise ValueError("RAG_EMBEDDING_PROVIDER 只能是 openai 或 local_hash。")
    return provider


def get_api_key_settings() -> dict:
    env_values = _read_env_file()
    api_key = os.getenv("OPENAI_API_KEY", env_values.get("OPENAI_API_KEY", "")).strip()
    warnings: list[str] = []
    if not api_key:
        warnings.append("OPENAI_API_KEY 未配置：问答会回退为本地摘录式回答，OpenAI embedding 会回退为本地 hash embedding。")

    return {
        "openai_api_key_configured": bool(api_key),
        "openai_api_key_masked": _mask_key(api_key),
        "openai_model": os.getenv("OPENAI_MODEL", settings.openai_model),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", settings.openai_base_url),
        "embedding_provider": os.getenv("RAG_EMBEDDING_PROVIDER", settings.embedding_provider),
        "embedding_model": os.getenv("RAG_EMBEDDING_MODEL", settings.embedding_model),
        "embedding_fallback_to_local": os.getenv(
            "RAG_EMBEDDING_FALLBACK_TO_LOCAL",
            "true" if settings.embedding_fallback_to_local else "false",
        ).lower()
        == "true",
        "env_file_exists": LOCAL_ENV_PATH.exists(),
        "warnings": warnings,
    }


def update_api_key_settings(payload: dict) -> dict:
    values = _read_env_file()

    raw_key = (payload.get("openai_api_key") or "").strip()
    if payload.get("clear_openai_api_key"):
        values.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
    elif raw_key:
        if any(token in raw_key.lower() for token in ["\n", "\r", "bearer "]):
            raise ValueError("OPENAI_API_KEY 格式不正确，请只粘贴 key 本身，不要包含 Bearer 或换行。")
        if raw_key.lower().startswith(("http://", "https://")):
            raise ValueError("OPENAI_API_KEY 格式不正确：请粘贴 secret key 本身，不要粘贴 OpenAI 平台网页链接。")
        values["OPENAI_API_KEY"] = raw_key
        os.environ["OPENAI_API_KEY"] = raw_key

    if payload.get("openai_model") is not None:
        model = payload["openai_model"].strip()
        if model:
            values["OPENAI_MODEL"] = model
            os.environ["OPENAI_MODEL"] = model
            settings.openai_model = model

    if payload.get("openai_base_url") is not None:
        base_url = payload["openai_base_url"].strip()
        if base_url:
            base_url = _validate_url(base_url)
            values["OPENAI_BASE_URL"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url
            settings.openai_base_url = base_url

    if payload.get("embedding_provider") is not None:
        provider = _validate_embedding_provider(payload["embedding_provider"])
        values["RAG_EMBEDDING_PROVIDER"] = provider
        os.environ["RAG_EMBEDDING_PROVIDER"] = provider
        settings.embedding_provider = provider

    if payload.get("embedding_model") is not None:
        embedding_model = payload["embedding_model"].strip()
        if embedding_model:
            values["RAG_EMBEDDING_MODEL"] = embedding_model
            os.environ["RAG_EMBEDDING_MODEL"] = embedding_model
            settings.embedding_model = embedding_model

    if payload.get("embedding_fallback_to_local") is not None:
        fallback = bool(payload["embedding_fallback_to_local"])
        values["RAG_EMBEDDING_FALLBACK_TO_LOCAL"] = "true" if fallback else "false"
        os.environ["RAG_EMBEDDING_FALLBACK_TO_LOCAL"] = values["RAG_EMBEDDING_FALLBACK_TO_LOCAL"]
        settings.embedding_fallback_to_local = fallback

    _write_env_file(values)
    return get_api_key_settings()
