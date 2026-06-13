from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kbsearch_cli.errors import ConfigError


@dataclass(frozen=True)
class QueryCliConfig:
    secure_backend_base_url: str
    google_oauth_client_config: Path
    google_oauth_token_cache: Path
    query_logs_root: Path
    libreoffice_command: str
    cjk_font_path: Path


DEFAULT_LOGS_ROOT = Path("logs")


def load_query_cli_config(env_file: str | Path | None = None) -> QueryCliConfig:
    if env_file is None:
        env_file = find_query_cli_env_file()
    env_path = Path(env_file) if env_file is not None else None
    if env_path is not None:
        load_dotenv(dotenv_path=env_path, override=False)

    root = _resolve_query_cli_root(env_path)
    return QueryCliConfig(
        secure_backend_base_url=_required_str("KBSEARCH_SECURE_BACKEND_BASE_URL"),
        google_oauth_client_config=_resolve_path(_required_str("GOOGLE_OAUTH_CLIENT_CONFIG"), root),
        google_oauth_token_cache=_resolve_path(_required_str("GOOGLE_OAUTH_TOKEN_CACHE"), root),
        query_logs_root=_resolve_cwd_path(
            _optional_str("KBSEARCH_QUERY_LOGS_ROOT", str(DEFAULT_LOGS_ROOT)),
        ),
        libreoffice_command=_required_absolute_path_str("LIBREOFFICE_COMMAND"),
        cjk_font_path=_required_absolute_path("KBSEARCH_CJK_FONT_PATH"),
    )


def find_query_cli_env_file() -> Path:
    return Path.cwd() / "config" / ".env"


def _resolve_query_cli_root(env_path: Path | None) -> Path:
    if env_path is None:
        return Path.cwd()
    return env_path.parent.parent


def _resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _resolve_cwd_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


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
    return Path(_required_absolute_path_str(name))


def _optional_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()
