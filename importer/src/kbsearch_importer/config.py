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
    vector_size: int
    dashscope_image_max_bytes: int
    dashscope_jpeg_quality: int
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    cjk_font_path: Path
    pdf_render_target_dpi: int
    pdf_render_max_pixels: int
    keep_success_work_files: bool
    keep_failed_work_files: bool
    log_retention_days: int
    log_level: str


APP_ROOT = Path("/app")
DEFAULT_ENV_FILE = APP_ROOT / "config" / ".env"
DEFAULT_WORK_DIR = APP_ROOT / "work"
DEFAULT_LOG_DIR = APP_ROOT / "logs"
DEFAULT_GCP_ADC_FILE = APP_ROOT / "config" / "gcp-adc.json"
DEFAULT_SOURCE_CONFIG = APP_ROOT / "config" / "google_drive_sources.yaml"
CJK_FONT_PATH = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")


def load_importer_config(env_file: str | Path | None = DEFAULT_ENV_FILE) -> ImporterConfig:
    """Load importer configuration from an optional env file and process env."""
    from kbsearch_importer.google_credentials import ensure_google_application_credentials

    env_path = Path(env_file) if env_file is not None else None
    if env_file is not None:
        load_dotenv(dotenv_path=env_path, override=False, encoding="utf-8-sig")

    ensure_google_application_credentials()

    source_config = DEFAULT_SOURCE_CONFIG

    config = ImporterConfig(
        app_root=APP_ROOT,
        google_drive_source_config=source_config,
        google_drive_sources=load_google_drive_sources(source_config),
        google_dwd_subject_email=_required_str("GOOGLE_DWD_SUBJECT_EMAIL"),
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
        cjk_font_path=CJK_FONT_PATH,
        pdf_render_target_dpi=_optional_int_in_range(
            "IMPORTER_PDF_RENDER_TARGET_DPI",
            200,
            minimum=72,
            maximum=600,
        ),
        pdf_render_max_pixels=_optional_int_in_range(
            "IMPORTER_PDF_RENDER_MAX_PIXELS",
            80_000_000,
            minimum=1,
            maximum=89_000_000,
        ),
        keep_success_work_files=_optional_bool("IMPORTER_KEEP_SUCCESS_WORK_FILES", False),
        keep_failed_work_files=_optional_bool("IMPORTER_KEEP_FAILED_WORK_FILES", True),
        log_retention_days=_optional_int("IMPORTER_LOG_RETENTION_DAYS", 14),
        log_level=_optional_log_level("IMPORTER_LOG_LEVEL", "INFO"),
    )

    return config


def load_google_drive_sources(config_path: str | Path) -> tuple[GoogleDriveSource, ...]:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Google Drive source config not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            raw_config = yaml.safe_load(file)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Unable to parse Google Drive source config: {path}") from exc

    if not isinstance(raw_config, dict):
        raise ConfigError("Google Drive source config must be a YAML mapping.")

    raw_sources = raw_config.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ConfigError("Google Drive source config must define a non-empty sources list.")

    sources = tuple(_parse_google_drive_source(item, index) for index, item in enumerate(raw_sources))
    _validate_unique_sources(sources)
    return sources


def _validate_unique_sources(sources: tuple[GoogleDriveSource, ...]) -> None:
    names: set[str] = set()
    identifiers: set[str] = set()
    for source in sources:
        if source.name in names:
            raise ConfigError(f"Duplicate Google Drive source name: {source.name}")
        names.add(source.name)

        identifier = source.drive_id or source.folder_id
        if identifier in identifiers:
            raise ConfigError(f"Duplicate Google Drive source identifier: {identifier}")
        identifiers.add(identifier)


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


def _required_positive_int(name: str) -> int:
    parsed = _required_int(name)
    if parsed <= 0:
        raise ConfigError(f"Config {name} must be a positive integer.")
    return parsed


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


def _optional_int_in_range(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    parsed = _optional_int(name, default)
    if parsed < minimum or parsed > maximum:
        raise ConfigError(f"Config {name} must be between {minimum} and {maximum}.")
    return parsed


def _optional_log_level(name: str, default: str) -> str:
    value = _optional_str(name)
    normalized = (value or default).upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError(
            f"Config {name} must be one of DEBUG, INFO, WARNING, ERROR."
        )
    return normalized
