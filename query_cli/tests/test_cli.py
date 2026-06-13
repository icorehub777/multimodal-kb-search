import json
import logging
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.__main__ import _emit_progress, main
from kbsearch_cli.config import ConfigError
from kbsearch_cli.errors import QueryCliError
from kbsearch_cli.logging_config import LOGGER_NAME, configure_query_cli_logging
from kbsearch_cli.models import DownloadedFileResult, QueryResultBundle, QueryRunResult


def _close_query_cli_log_handlers() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


class CliTests(unittest.TestCase):
    def tearDown(self):
        _close_query_cli_log_handlers()

    def test_query_runs_startup_probe_orchestrator_and_prints_json_summary(self):
        bundle_path = Path("C:/tmp/query/20260531-120000-客戶")
        bundle = QueryResultBundle(
            path=bundle_path,
            query_plan_path=bundle_path / "query_plan.json",
            full_text_results_path=bundle_path / "full_text_results.json",
            vector_results_path=bundle_path / "vector_results.json",
            full_text_results=[],
            vector_results=[],
        )
        run_result = QueryRunResult(
            bundle=bundle,
            full_text_count=1,
            vector_count=2,
            vector_accessible_count=2,
            union_count=1,
            download_count=1,
            downloaded_files=[
                DownloadedFileResult(
                    google_file_id="file-1",
                    name="Alpha.pdf",
                    directory=bundle_path / "Alpha.pdf-file-1",
                    source_path=bundle_path / "Alpha.pdf-file-1" / "Alpha.pdf",
                    page_paths=[bundle_path / "Alpha.pdf-file-1" / "0001.png"],
                )
            ],
        )

        class FakeOrchestrator:
            def run(self, **kwargs):
                self.kwargs = kwargs
                return run_result

        fake_orchestrator = FakeOrchestrator()
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.reserve_output_directory",
        ) as reserve_output_directory, patch(
            "kbsearch_cli.__main__._run_startup_probe",
        ) as run_startup_probe, patch(
            "kbsearch_cli.__main__.create_query_orchestrator",
            return_value=fake_orchestrator,
        ) as create_orchestrator, patch(
            "kbsearch_cli.__main__.configure_query_cli_logging",
        ) as configure_logging, redirect_stdout(StringIO()) as stdout, redirect_stderr(
            StringIO()
        ) as stderr:
            load_config.return_value.query_logs_root = Path("C:/tmp/logs")
            self.assertEqual(
                main(
                    [
                        "query",
                        "--output-dir",
                        bundle_path.as_posix(),
                        "--vector-query",
                        "semantic alpha",
                        "--drive-query",
                        "fullText contains 'alpha' and trashed = false",
                        "--limit",
                        "3",
                        "--min-score",
                        "0.4",
                    ]
                ),
                0,
            )

        configure_logging.assert_called_once_with(Path("C:/tmp/logs"))
        reserve_output_directory.assert_called_once_with(bundle_path)
        run_startup_probe.assert_called_once()
        create_orchestrator.assert_called_once_with(load_config.return_value)
        self.assertEqual(fake_orchestrator.kwargs["output_dir"], bundle_path)
        self.assertIs(fake_orchestrator.kwargs["progress"], _emit_progress)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "finished")
        self.assertEqual(payload["output_dir"], bundle_path.as_posix())
        self.assertEqual(payload["full_text_count"], 1)
        self.assertEqual(payload["vector_count"], 2)
        self.assertEqual(payload["download_count"], 1)
        self.assertIn("Query progress: phase=query status=started", stderr.getvalue())

    def test_query_failure_before_logging_only_prints_stderr(self):
        with redirect_stderr(StringIO()) as stderr:
            with patch(
                "kbsearch_cli.__main__.load_query_cli_config",
                side_effect=ConfigError("Missing required config: KBSEARCH_SECURE_BACKEND_BASE_URL"),
            ):
                exit_code = main(
                    [
                        "query",
                        "--output-dir",
                        "C:/tmp/query/new-query",
                        "--vector-query",
                        "alpha",
                        "--drive-query",
                        "fullText contains 'alpha' and trashed = false",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("Missing required config", stderr.getvalue())

    def test_query_failure_after_logging_started_includes_log_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_root = Path(temp_dir) / "configured-logs"
            config = type("Config", (), {"query_logs_root": log_root})()
            output_dir = Path(temp_dir) / "new-query"
            try:
                with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                    "kbsearch_cli.__main__._run_startup_probe",
                    side_effect=QueryCliError("Secure backend unreachable"),
                ), patch(
                    "kbsearch_cli.__main__.configure_query_cli_logging",
                    side_effect=lambda root: configure_query_cli_logging(root),
                ), redirect_stderr(StringIO()) as stderr:
                    exit_code = main(
                        [
                            "query",
                            "--output-dir",
                            str(output_dir),
                            "--vector-query",
                            "alpha",
                            "--drive-query",
                            "fullText contains 'alpha' and trashed = false",
                        ]
                    )
            finally:
                _close_query_cli_log_handlers()

            self.assertEqual(exit_code, 1)
            self.assertIn("Secure backend unreachable", stderr.getvalue())
            self.assertIn("log=", stderr.getvalue())
            log_text = (log_root / "kbsearch_cli.log").read_text(encoding="utf-8")
            self.assertIn("query failed", log_text)
            self.assertTrue(output_dir.exists())

    def test_query_rejects_existing_output_dir_before_startup_probe_and_logs_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "existing-query"
            output_dir.mkdir()
            log_root = root / "logs"
            config = type("Config", (), {"query_logs_root": log_root})()

            with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                "kbsearch_cli.__main__._run_startup_probe",
            ) as run_startup_probe, patch(
                "kbsearch_cli.__main__.create_query_orchestrator",
            ) as create_orchestrator, patch(
                "kbsearch_cli.__main__.configure_query_cli_logging",
                side_effect=lambda path: configure_query_cli_logging(path),
            ), redirect_stderr(StringIO()) as stderr:
                exit_code = main(
                    [
                        "query",
                        "--output-dir",
                        str(output_dir),
                        "--vector-query",
                        "alpha",
                        "--drive-query",
                        "fullText contains 'alpha' and trashed = false",
                    ]
                )

            self.assertEqual(exit_code, 1)
            run_startup_probe.assert_not_called()
            create_orchestrator.assert_not_called()
            self.assertIn("already exists", stderr.getvalue())
            self.assertIn(
                "output directory already exists",
                (log_root / "kbsearch_cli.log").read_text(encoding="utf-8"),
            )
            _close_query_cli_log_handlers()

    def test_configure_query_cli_logging_uses_daily_rotating_file_in_configured_log_root(self):
        log_root = Path("C:/tmp/kbsearch-query-logs")
        with patch("pathlib.Path.mkdir") as mkdir:
            logger = configure_query_cli_logging(log_root)

        handler = next(
            handler
            for handler in logger.handlers
            if isinstance(handler, TimedRotatingFileHandler)
        )
        self.assertEqual(Path(handler.baseFilename), log_root / "kbsearch_cli.log")
        self.assertEqual(handler.when, "MIDNIGHT")
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        logger.removeHandler(handler)
        handler.close()
        _close_query_cli_log_handlers()


if __name__ == "__main__":
    unittest.main()
