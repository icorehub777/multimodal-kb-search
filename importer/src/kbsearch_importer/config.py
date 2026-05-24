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
    importer_root: Path
    google_drive_source_config: Path
    google_drive_sources: tuple[GoogleDriveSource, ...]
    google_service_account_email: str
    google_dwd_subject_email: str
    dashscope_api_key: str
    dashscope_embedding_model: str
    dashscope_vector_size: int
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str
    qdrant_vector_size: int
    libreoffice_command: str
    keep_success_work_files: bool
    keep_failed_work_files: bool


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / "config" / ".env"


def load_importer_config(env_file: str | Path | None = DEFAULT_ENV_FILE) -> ImporterConfig:
    """Load importer configuration from an optional env file and process env."""
    env_path = Path(env_file) if env_file is not None else None
    if env_file is not None:
        load_dotenv(dotenv_path=env_path, override=False)

    importer_root = _resolve_importer_root(env_path)
    source_config = _resolve_config_path(
        _required_str("GOOGLE_DRIVE_SOURCE_CONFIG"),
        importer_root,
    )

    config = ImporterConfig(
        importer_root=importer_root,
        google_drive_source_config=source_config,
        google_drive_sources=load_google_drive_sources(source_config),
        google_service_account_email=_required_str("GOOGLE_SERVICE_ACCOUNT_EMAIL"),
        google_dwd_subject_email=_required_str("GOOGLE_DWD_SUBJECT_EMAIL"),
        dashscope_api_key=_required_str("DASHSCOPE_API_KEY"),
        dashscope_embedding_model=_required_str("DASHSCOPE_EMBEDDING_MODEL"),
        dashscope_vector_size=_required_int("DASHSCOPE_VECTOR_SIZE"),
        qdrant_url=_required_str("QDRANT_URL"),
        qdrant_api_key=_required_str("QDRANT_API_KEY"),
        qdrant_collection=_required_str("QDRANT_COLLECTION"),
        qdrant_vector_size=_required_int("QDRANT_VECTOR_SIZE"),
        libreoffice_command=_optional_str("LIBREOFFICE_COMMAND", "soffice"),
        keep_success_work_files=_optional_bool("IMPORTER_KEEP_SUCCESS_WORK_FILES", True),
        keep_failed_work_files=_optional_bool("IMPORTER_KEEP_FAILED_WORK_FILES", True),
    )

    if config.dashscope_vector_size != config.qdrant_vector_size:
        raise ConfigError(
            "DASHSCOPE_VECTOR_SIZE must match QDRANT_VECTOR_SIZE "
            f"({config.dashscope_vector_size} != {config.qdrant_vector_size})."
        )

    return config


def _resolve_importer_root(env_path: Path | None) -> Path:
    if env_path is None:
        return Path.cwd()
    return env_path.parent.parent


def _resolve_config_path(value: str, importer_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return importer_root / path


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


def _required_str(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ConfigError(f"Missing required config: {name}")
    return value.strip()


def _optional_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


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
