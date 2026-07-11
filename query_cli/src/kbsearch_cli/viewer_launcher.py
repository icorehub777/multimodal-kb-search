from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode


def build_viewer_url(
    *,
    host: str,
    port: int,
    task_name: str | None = None,
    query_name: str | None = None,
) -> str:
    url_host = "127.0.0.1" if host in {"", "0.0.0.0"} else host
    params: dict[str, str] = {}
    if task_name:
        params["task"] = task_name
    if query_name:
        params["query"] = query_name
    suffix = f"?{urlencode(params)}" if params else ""
    return f"http://{url_host}:{port}/{suffix}"


def build_task_query_url_example(*, host: str, port: int) -> str:
    return f"{build_viewer_url(host=host, port=port)}?task=<task-name>&query=<query-name>"


def _address_uses_port(address: str, port: int) -> bool:
    return address.rsplit(":", 1)[-1] == str(port)


def _find_listening_pids(port: int) -> list[int]:
    if os.name != "nt":
        return _find_listening_pids_posix(port)

    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []

    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[-2].upper() != "LISTENING":
            continue
        if not _address_uses_port(parts[1], port):
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return sorted(pids)


def _find_listening_pids_posix(port: int) -> list[int]:
    completed = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        try:
            pids.add(int(line.strip()))
        except ValueError:
            continue
    return sorted(pids)


def _get_process_command_line(pid: int) -> str:
    if os.name != "nt":
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _is_kbsearch_viewer_command(command_line: str) -> bool:
    normalized = command_line.replace("\\", "/").lower()
    if "kbsearch_cli.__main__" in normalized and "view-results" in normalized:
        return True
    if "kbsearch.exe" in normalized and "view-results" in normalized:
        return True
    return "streamlit" in normalized and "viewer_app.py" in normalized


def _terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return
    os.kill(pid, signal.SIGTERM)


def _wait_for_port_release(port: int, *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _find_listening_pids(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Viewer port {port} is still in use after stopping the previous viewer.")


def restart_existing_viewer_on_port(port: int) -> int:
    restarted = 0
    for pid in _find_listening_pids(port):
        if pid == os.getpid():
            continue
        command_line = _get_process_command_line(pid)
        if not _is_kbsearch_viewer_command(command_line):
            raise RuntimeError(
                f"Port {port} is already used by another process. "
                "Set KBSEARCH_VIEWER_PORT to another available port."
            )
        _terminate_process_tree(pid)
        restarted += 1
    if restarted:
        _wait_for_port_release(port)
    return restarted


def run_viewer(
    *,
    tasks_dir: Path,
    host: str,
    port: int,
) -> int:
    try:
        from streamlit.web import cli as streamlit_cli
    except ImportError as exc:
        raise RuntimeError(
            "Streamlit is required for 'kbsearch view-results'. "
            "Install kbsearch-cli with the viewer dependencies."
        ) from exc

    resolved_tasks_dir = tasks_dir.resolve()
    os.environ["KBSEARCH_VIEWER_TASKS_DIR"] = str(resolved_tasks_dir)
    app_path = Path(__file__).with_name("viewer_app.py")
    url = build_viewer_url(host=host, port=port)
    task_query_url_example = build_task_query_url_example(host=host, port=port)
    restarted_process_count = restart_existing_viewer_on_port(port)
    print(
        json.dumps(
            {
                "status": "starting",
                "viewer_url": url,
                "task_query_url_example": task_query_url_example,
                "tasks_dir": str(resolved_tasks_dir),
                "restarted_process_count": restarted_process_count,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    return int(streamlit_cli.main() or 0)
