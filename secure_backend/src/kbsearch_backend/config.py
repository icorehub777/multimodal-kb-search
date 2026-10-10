from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kbsearch_backend.errors import ConfigError


@dataclass(frozen=True)
class BackendConfig:
    secure_backend_api_key: str
    dashscope_api_key: str
    dashscope_embedding_model: str
    vector_size: int
    dashscope_image_max_bytes: int
    dashscope_jpeg_quality: int
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    log_file_path: Path
    max_query_length: int = 4_000
    max_images: int = 5
    max_search_limit: int = 100
    log_level: str = "INFO"


APP_ROOT = Path("/app")
DEFAULT_ENV_FILE = APP_ROOT / "config" / ".env"
DEFAULT_LOG_FILE = APP_ROOT / "logs" / "secure_backend.log"


def load_backend_config(env_file: str | Path | None = DEFAULT_ENV_FILE) -> BackendConfig:
    env_path = Path(env_file) if env_file is not None else None
    if env_file is not None:
        load_dotenv(dotenv_path=env_path, override=False)

    config = BackendConfig(
        secure_backend_api_key=_required_str("SECURE_BACKEND_API_KEY"),
        dashscope_api_key=_required_str("DASHSCOPE_API_KEY"),
        dashscope_embedding_model=_required_str("DASHSCOPE_EMBEDDING_MODEL"),
        vector_size=_required_positive_int("KBSEARCH_VECTOR_SIZE"),
        dashscope_image_max_bytes=_optional_int_in_range(
            "DASHSCOPE_IMAGE_MAX_BYTES",
            9_728_000,
            minimum=1,
            maximum=10_485_760,
        ),
        dashscope_jpeg_quality=_optional_int_in_range(
            "DASHSCOPE_JPEG_QUALITY",
            95,
            minimum=1,
            maximum=100,
        ),
        qdrant_url=_required_str("QDRANT_URL"),
        qdrant_api_key=_optional_str("QDRANT_API_KEY"),
        qdrant_collection=_required_str("QDRANT_COLLECTION"),
        log_file_path=DEFAULT_LOG_FILE,
        max_query_length=_optional_positive_int("SECURE_BACKEND_MAX_QUERY_LENGTH", 4_000),
        max_images=_optional_positive_int("SECURE_BACKEND_MAX_IMAGES", 5),
        max_search_limit=_optional_positive_int("SECURE_BACKEND_MAX_SEARCH_LIMIT", 100),
        log_level=_optional_log_level("SECURE_BACKEND_LOG_LEVEL", "INFO"),
    )
    return config


def _optional_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


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


def _required_positive_int(name: str) -> int:
    value = _required_int(name)
    if value < 1:
        raise ConfigError(f"Config {name} must be a positive integer.")
    return value


def _optional_positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc
    if parsed < 1:
        raise ConfigError(f"Config {name} must be a positive integer.")
    return parsed


def _optional_log_level(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().upper()
    if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError(f"Config {name} must be one of DEBUG, INFO, WARNING or ERROR.")
    return value


def _optional_int_in_range(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ConfigError(f"Config {name} must be between {minimum} and {maximum}.")
    return parsed
