from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kbsearch_cli.errors import ConfigError, QueryInputError
from kbsearch_cli.paths import require_scoped_path


@dataclass(frozen=True)
class QueryCliConfig:
    secure_backend_base_url: str
    secure_backend_api_key: str
    query_logs_root: Path
    tasks_root: Path
    query_log_retention_days: int
    log_level: str
    cjk_font_path: Path


DEFAULT_LOGS_ROOT = Path("logs")


@dataclass(frozen=True)
class LoginConfig:
    google_oauth_client_config: Path


@dataclass(frozen=True)
class ViewerConfig:
    viewer_port: int


def _load_runtime_env(env_file: str | Path | None = None) -> Path:
    resolve_workspace_tasks_root()
    path = Path(env_file) if env_file is not None else find_query_cli_env_file()
    load_dotenv(dotenv_path=path, override=False)
    return path


def load_login_config() -> LoginConfig:
    env = _load_runtime_env()
    return LoginConfig(_resolve_path(_required_str("GOOGLE_OAUTH_CLIENT_CONFIG"), env.parent.parent))


def load_viewer_config() -> ViewerConfig:
    _load_runtime_env()
    return ViewerConfig(_optional_port("KBSEARCH_VIEWER_PORT", 8501))


def load_query_cli_config(env_file: str | Path | None = None) -> QueryCliConfig:
    tasks_root = resolve_workspace_tasks_root()
    _load_runtime_env(env_file)
    return QueryCliConfig(
        secure_backend_base_url=_required_str("KBSEARCH_SECURE_BACKEND_BASE_URL"),
        secure_backend_api_key=_required_str("KBSEARCH_SECURE_BACKEND_API_KEY"),
        query_logs_root=resolve_query_logs_root(),
        tasks_root=tasks_root,
        query_log_retention_days=_optional_non_negative_int(
            "KBSEARCH_QUERY_LOG_RETENTION_DAYS",
            14,
        ),
        log_level=_optional_log_level("KBSEARCH_LOG_LEVEL", "INFO"),
        cjk_font_path=_required_absolute_path("KBSEARCH_CJK_FONT_PATH"),
    )


def resolve_workspace_tasks_root() -> Path:
    cwd = Path.cwd()
    if cwd.name != "_internal":
        raise ConfigError("Run kbsearch from the workspace _internal directory.")
    try:
        workspace = cwd.parent.resolve()
        tasks = workspace / "tasks"
        if not tasks.resolve().is_relative_to(workspace):
            raise ConfigError(f"Task root must remain within the workspace: {tasks}")
        try:
            require_scoped_path(tasks, workspace)
        except QueryInputError as exc:
            raise ConfigError(str(exc)) from exc
        if tasks.exists() and not tasks.is_dir():
            raise ConfigError(f"Task root is not a directory: {tasks}")
        return tasks
    except ConfigError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ConfigError(f"Cannot resolve workspace task root: {cwd.parent / 'tasks'}") from exc


def find_query_cli_env_file() -> Path:
    return Path.cwd() / "config" / ".env"


def _resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def resolve_query_logs_root() -> Path:
    internal = Path.cwd()
    logs = internal / DEFAULT_LOGS_ROOT
    try:
        if not logs.resolve().is_relative_to(internal.resolve()):
            raise ConfigError(f"Query logs must remain within _internal: {logs}")
        if logs.exists() and not logs.is_dir():
            raise ConfigError(f"Query log root is not a directory: {logs}")
        return logs
    except ConfigError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ConfigError(f"Cannot resolve query log root: {logs}") from exc


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


def _optional_non_negative_int(name: str, default: int) -> int:
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


def _optional_port(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigError(f"Config {name} must be an integer.") from exc
    if parsed < 1 or parsed > 65535:
        raise ConfigError(f"Config {name} must be between 1 and 65535.")
    return parsed


def _optional_log_level(name: str, default: str) -> str:
    value = _optional_str(name, default).upper()
    if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError(
            f"Config {name} must be one of DEBUG, INFO, WARNING or ERROR."
        )
    return value
