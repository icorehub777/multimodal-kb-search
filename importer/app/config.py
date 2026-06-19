from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when importer configuration is missing or invalid."""


@dataclass(frozen=True)
class GoogleDriveSource:
    name: str
    type: str
    drive_id: str | None = None
    folder_id: str | None = None


@dataclass(frozen=True)
class ImporterConfig:
    app_root: Path
    google_drive_source_config: Path
    google_drive_sources: tuple[GoogleDriveSource, ...]
    google_dwd_subject_email: str
    dashscope_api_key: str
    dashscope_embedding_model: str
    dashscope_vector_size: int
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    qdrant_vector_size: int
    cjk_font_path: Path
    keep_success_work_files: bool
    keep_failed_work_files: bool
    log_retention_days: int


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = APP_ROOT / "config" / ".env"
DEFAULT_WORK_DIR = APP_ROOT / "work"
DEFAULT_LOG_DIR = APP_ROOT / "logs"


def resolve_app_path(raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (APP_ROOT / path).resolve()
    return path


def _required_config_path(env_name: str) -> Path:
    value = _required_str(env_name)
    return resolve_app_path(value)


def load_importer_config(env_file: str | Path | None = DEFAULT_ENV_FILE) -> ImporterConfig:
    """Load importer configuration from an optional env file and process env."""
    from app.google_credentials import ensure_google_application_credentials

    env_path = Path(env_file) if env_file is not None else None
    if env_file is not None:
        load_dotenv(dotenv_path=env_path, override=False, encoding="utf-8-sig")

    ensure_google_application_credentials()

    source_config = _required_config_path("GOOGLE_DRIVE_SOURCE_CONFIG")

    config = ImporterConfig(
        app_root=APP_ROOT,
        google_drive_source_config=source_config,
        google_drive_sources=load_google_drive_sources(source_config),
        google_dwd_subject_email=_required_str("GOOGLE_DWD_SUBJECT_EMAIL"),
        dashscope_api_key=_required_str("DASHSCOPE_API_KEY"),
        dashscope_embedding_model=_required_str("DASHSCOPE_EMBEDDING_MODEL"),
        dashscope_vector_size=_required_int("DASHSCOPE_VECTOR_SIZE"),
        qdrant_url=_required_str("QDRANT_URL"),
        qdrant_api_key=_optional_str("QDRANT_API_KEY"),
        qdrant_collection=_required_str("QDRANT_COLLECTION"),
        qdrant_vector_size=_required_int("QDRANT_VECTOR_SIZE"),
        cjk_font_path=_required_absolute_path("KBSEARCH_CJK_FONT_PATH"),
        keep_success_work_files=_optional_bool("IMPORTER_KEEP_SUCCESS_WORK_FILES", True),
        keep_failed_work_files=_optional_bool("IMPORTER_KEEP_FAILED_WORK_FILES", True),
        log_retention_days=_optional_int("IMPORTER_LOG_RETENTION_DAYS", 14),
    )

    if config.dashscope_vector_size != config.qdrant_vector_size:
        raise ConfigError(
            "DASHSCOPE_VECTOR_SIZE must match QDRANT_VECTOR_SIZE "
            f"({config.dashscope_vector_size} != {config.qdrant_vector_size})."
        )

    return config


def load_google_drive_sources(config_path: str | Path) -> tuple[GoogleDriveSource, ...]:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Google Drive source config not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    if not isinstance(raw_config, dict):
        raise ConfigError("Google Drive source config must be a YAML mapping.")

    raw_sources = raw_config.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ConfigError("Google Drive source config must define a non-empty sources list.")

    return tuple(_parse_google_drive_source(item, index) for index, item in enumerate(raw_sources))


def _parse_google_drive_source(raw_source: Any, index: int) -> GoogleDriveSource:
    if not isinstance(raw_source, dict):
        raise ConfigError(f"Google Drive source at index {index} must be a mapping.")

    name = _required_mapping_str(raw_source, "name", index)
    source_type = _required_mapping_str(raw_source, "type", index)
    drive_id = _optional_mapping_str(raw_source, "drive_id", index)
    folder_id = _optional_mapping_str(raw_source, "folder_id", index)

    if source_type == "shared_drive":
        if not drive_id:
            raise ConfigError(f"Google Drive source '{name}' requires drive_id.")
        if folder_id:
            raise ConfigError(f"Google Drive source '{name}' must not define folder_id.")
    elif source_type == "folder":
        if not folder_id:
            raise ConfigError(f"Google Drive source '{name}' requires folder_id.")
        if drive_id:
            raise ConfigError(f"Google Drive source '{name}' must not define drive_id.")
    else:
        raise ConfigError(
            f"Google Drive source '{name}' has unsupported type '{source_type}'. "
            "Supported types: shared_drive, folder."
        )

    return GoogleDriveSource(name=name, type=source_type, drive_id=drive_id, folder_id=folder_id)


def _required_mapping_str(raw_source: dict[str, Any], key: str, index: int) -> str:
    value = raw_source.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ConfigError(f"Google Drive source at index {index} requires non-empty {key}.")
    return value.strip()


def _optional_mapping_str(raw_source: dict[str, Any], key: str, index: int) -> str | None:
    value = raw_source.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() == "":
        raise ConfigError(f"Google Drive source at index {index} has invalid {key}.")
    return value.strip()


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


def _required_absolute_path_str(name: str) -> str:
    value = _required_str(name)
    if not Path(value).is_absolute():
        raise ConfigError(f"Config {name} must be an absolute path.")
    return value


def _required_absolute_path(name: str) -> Path:
    value = Path(_required_absolute_path_str(name))
    return value


def _optional_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"Config {name} must be a boolean.")


def _required_int(name: str) -> int:
    value = _required_str(name)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc


def _optional_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc
    if parsed < 0:
        raise ConfigError(f"Config {name} must be zero or a positive integer.")
    return parsed
