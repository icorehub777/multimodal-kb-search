from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kbsearch_secure_backend.errors import ConfigError


@dataclass(frozen=True)
class BackendConfig:
    dashscope_api_key: str
    dashscope_embedding_model: str
    dashscope_vector_size: int
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str
    qdrant_vector_size: int
    log_file_path: Path


APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = APP_ROOT / "config" / ".env"


def load_backend_config(env_file: str | Path | None = DEFAULT_ENV_FILE) -> BackendConfig:
    env_path = Path(env_file) if env_file is not None else None
    if env_file is not None:
        load_dotenv(dotenv_path=env_path, override=False)

    config = BackendConfig(
        dashscope_api_key=_required_str("DASHSCOPE_API_KEY"),
        dashscope_embedding_model=_required_str("DASHSCOPE_EMBEDDING_MODEL"),
        dashscope_vector_size=_required_int("DASHSCOPE_VECTOR_SIZE"),
        qdrant_url=_required_str("QDRANT_URL"),
        qdrant_api_key=_required_str("QDRANT_API_KEY"),
        qdrant_collection=_required_str("QDRANT_COLLECTION"),
        qdrant_vector_size=_required_int("QDRANT_VECTOR_SIZE"),
        log_file_path=_resolve_path(_required_str("KBSEARCH_SECURE_BACKEND_LOG_FILE"), APP_ROOT),
    )
    if config.dashscope_vector_size != config.qdrant_vector_size:
        raise ConfigError(
            "DASHSCOPE_VECTOR_SIZE must match QDRANT_VECTOR_SIZE "
            f"({config.dashscope_vector_size} != {config.qdrant_vector_size})."
        )
    return config


def _resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _required_str(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ConfigError(f"Missing required config: {name}")
    return value.strip()


def _required_int(name: str) -> int:
    value = _required_str(name)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc
