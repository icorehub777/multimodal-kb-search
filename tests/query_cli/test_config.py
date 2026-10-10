import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.config import ConfigError, find_query_cli_env_file, load_query_cli_config, load_viewer_config


class QueryCliConfigTests(unittest.TestCase):
    def test_log_root_is_fixed_even_when_environment_supplies_another_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            internal = Path(temp_dir) / "_internal"
            with patch("pathlib.Path.cwd", return_value=internal), patch.dict(os.environ, {
                "KBSEARCH_SECURE_BACKEND_BASE_URL": "http://127.0.0.1:8000",
                "KBSEARCH_SECURE_BACKEND_API_KEY": "test-key",
                "GOOGLE_OAUTH_CLIENT_CONFIG": "config/oauth_client.json",
                "KBSEARCH_CJK_FONT_PATH": "C:/Windows/Fonts/msjh.ttc",
                "KBSEARCH_QUERY_LOGS_ROOT": "C:/outside",
            }, clear=True):
                config = load_query_cli_config(internal / "config" / ".env")
                self.assertEqual(config.query_logs_root, internal / "logs")
                self.assertFalse(config.query_logs_root.exists())

    def test_log_root_rejects_link_outside_internal_directory(self):
        from kbsearch_cli.config import resolve_query_logs_root

        with tempfile.TemporaryDirectory() as temp_dir:
            internal = Path(temp_dir) / "_internal"
            logs = internal / "logs"
            original_resolve = Path.resolve
            with patch("pathlib.Path.cwd", return_value=internal), patch.object(Path, "resolve", autospec=True,
                side_effect=lambda path: Path(temp_dir) / "outside" if path == logs else original_resolve(path)):
                with self.assertRaisesRegex(ConfigError, "within _internal"):
                    resolve_query_logs_root()

    def setUp(self):
        cwd_patch = patch("pathlib.Path.cwd", return_value=Path.cwd() / "_internal")
        cwd_patch.start()
        self.addCleanup(cwd_patch.stop)

    def test_tasks_root_is_fixed_even_when_environment_supplies_another_path(self):
        from kbsearch_cli.config import resolve_workspace_tasks_root

        with tempfile.TemporaryDirectory() as temp_dir:
            internal = Path(temp_dir) / "_internal"
            with patch("pathlib.Path.cwd", return_value=internal), patch.dict(os.environ, {"KBSEARCH_TASKS_ROOT": "C:/outside"}):
                self.assertEqual(resolve_workspace_tasks_root(), internal.parent / "tasks")
                self.assertFalse((internal.parent / "tasks").exists())

    def test_tasks_root_rejects_wrong_working_directory(self):
        from kbsearch_cli.config import resolve_workspace_tasks_root

        with patch("pathlib.Path.cwd", return_value=Path("C:/workspace")):
            with self.assertRaisesRegex(ConfigError, "_internal"):
                resolve_workspace_tasks_root()

    def test_tasks_root_rejects_link_outside_workspace(self):
        from kbsearch_cli.config import resolve_workspace_tasks_root

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            tasks = workspace / "tasks"
            original_resolve = Path.resolve
            with patch("pathlib.Path.cwd", return_value=workspace / "_internal"), patch.object(
                Path, "resolve", autospec=True,
                side_effect=lambda path: Path(temp_dir) / "outside" if path == tasks else original_resolve(path),
            ):
                with self.assertRaisesRegex(ConfigError, "within the workspace"):
                    resolve_workspace_tasks_root()

    def test_load_query_cli_config_reads_required_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            internal_root = Path(temp_dir) / "agent_runtime" / "_internal"
            config_dir = internal_root / "config"
            config_dir.mkdir(parents=True)
            env_file = config_dir / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=config/oauth_client.json",
                        "KBSEARCH_VIEWER_PORT=8502",
                        "KBSEARCH_QUERY_LOG_RETENTION_DAYS=30",
                        "KBSEARCH_LOG_LEVEL=DEBUG",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), patch(
                "pathlib.Path.cwd", return_value=internal_root
            ):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.secure_backend_base_url, "http://127.0.0.1:8000")
        self.assertEqual(config.secure_backend_api_key, "backend-secret")
        self.assertEqual(config.query_logs_root, internal_root / "logs")
        self.assertEqual(config.tasks_root, internal_root.parent / "tasks")
        self.assertEqual(config.query_log_retention_days, 30)
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.cjk_font_path, Path("C:/Windows/Fonts/msjh.ttc"))

    def test_load_query_cli_config_defaults_runtime_paths_to_cwd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )
            cwd = Path(temp_dir) / "_internal"
            cwd.mkdir()

            with patch.dict(os.environ, {}, clear=True), patch("pathlib.Path.cwd", return_value=cwd):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.query_logs_root, cwd / "logs")
        self.assertEqual(config.tasks_root, cwd.parent / "tasks")
        self.assertEqual(config.query_log_retention_days, 14)
        self.assertEqual(config.log_level, "INFO")

    def test_load_viewer_config_rejects_invalid_viewer_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_VIEWER_PORT=70000",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_VIEWER_PORT"):
                    with patch("kbsearch_cli.config.find_query_cli_env_file", return_value=env_file):
                        load_viewer_config()

    def test_load_query_cli_config_accepts_zero_log_retention_days(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_QUERY_LOG_RETENTION_DAYS=0",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_query_cli_config(env_file)

        self.assertEqual(config.query_log_retention_days, 0)

    def test_load_query_cli_config_rejects_negative_log_retention_days(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_QUERY_LOG_RETENTION_DAYS=-1",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    ConfigError,
                    "KBSEARCH_QUERY_LOG_RETENTION_DAYS",
                ):
                    load_query_cli_config(env_file)

    def test_find_query_cli_env_file_uses_current_working_directory_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "agent_runtime" / "_internal"
            env_file = cwd / "config" / ".env"
            env_file.parent.mkdir(parents=True)
            env_file.write_text("", encoding="utf-8")

            with patch("pathlib.Path.cwd", return_value=cwd):
                self.assertEqual(find_query_cli_env_file(), env_file)

    def test_load_query_cli_config_rejects_missing_backend_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_SECURE_BACKEND_BASE_URL"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_missing_backend_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_SECURE_BACKEND_API_KEY"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_missing_cjk_font_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_CJK_FONT_PATH"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_relative_cjk_font_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_CJK_FONT_PATH=msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "absolute path"):
                    load_query_cli_config(env_file)

    def test_load_query_cli_config_rejects_invalid_log_level(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KBSEARCH_SECURE_BACKEND_BASE_URL=http://127.0.0.1:8000",
                        "KBSEARCH_SECURE_BACKEND_API_KEY=backend-secret",
                        "GOOGLE_OAUTH_CLIENT_CONFIG=client.json",
                        "KBSEARCH_LOG_LEVEL=TRACE",
                        "KBSEARCH_CJK_FONT_PATH=C:/Windows/Fonts/msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_LOG_LEVEL"):
                    load_query_cli_config(env_file)


if __name__ == "__main__":
    unittest.main()
