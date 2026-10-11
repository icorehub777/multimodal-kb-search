import json
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from logging import FileHandler
from pathlib import Path
from unittest.mock import ANY, patch

from kbsearch_cli.__main__ import _emit_progress, main
from kbsearch_cli.config import ConfigError
from kbsearch_cli.errors import ExternalServiceError, QueryCliError
from kbsearch_cli.logging_config import (
    LOGGER_NAME,
    QueryLogContext,
    configure_query_cli_logging,
    create_query_log_context,
    cleanup_old_query_log_files,
)
from kbsearch_cli.models import DownloadedFileResult, QueryResultBundle, QueryRunResult


def _close_query_cli_log_handlers() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


class CliTests(unittest.TestCase):
    def test_query_rejects_image_paths_before_loading_config(self):
        for name in ("../photo.png", "nested/photo.png", "nested\\photo.png", "C:\\photo.png", "/photo.png"):
            with self.subTest(name=name), patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
                "kbsearch_cli.__main__.configure_query_cli_logging"
            ) as logging_setup, patch("kbsearch_cli.__main__._run_startup_probe") as probe, redirect_stderr(StringIO()) as stderr:
                self.assertEqual(main(["query", "--task-name", "task", "--query-name", "query", "--image", name]), 1)
                self.assertIn("--image", stderr.getvalue())
                self.assertIn("input_or_config", stderr.getvalue())
                load_config.assert_not_called()
                logging_setup.assert_not_called()
                probe.assert_not_called()

    def test_missing_query_image_fails_before_logs_or_external_calls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve() / "tasks"
            config = type("Config", (), {"tasks_root": root})()
            with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                "kbsearch_cli.__main__.configure_query_cli_logging"
            ) as logging_setup, patch("kbsearch_cli.__main__._run_startup_probe") as probe, redirect_stderr(StringIO()) as stderr:
                self.assertEqual(main(["query", "--task-name", "task", "--query-name", "query", "--image", "missing.png"]), 1)
                self.assertIn(str(root / "task" / "missing.png"), stderr.getvalue())
                self.assertIn("input_or_config", stderr.getvalue())
                logging_setup.assert_not_called()
                probe.assert_not_called()
                self.assertFalse(root.exists())

    def test_query_creates_missing_task_root_and_result_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            tasks_root = root / "tasks"
            output = tasks_root / "task" / "query_results" / "search"
            config = type("Config", (), {"tasks_root": tasks_root, "query_logs_root": root / "logs", "query_log_retention_days": 14, "log_level": "INFO"})()
            with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                "kbsearch_cli.__main__._run_startup_probe"
            ) as probe, patch("kbsearch_cli.__main__.create_query_orchestrator") as factory, redirect_stdout(StringIO()) as stdout, redirect_stderr(StringIO()):
                probe.side_effect = lambda *args, **kwargs: self.assertFalse(tasks_root.exists())
                factory.return_value.run.return_value = self._make_empty_run_result(output)
                exit_code = main(["query", "--task-name", "task", "--query-name", "search", "--drive-query", "x"])
            _close_query_cli_log_handlers()
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_dir())
            self.assertEqual(json.loads(stdout.getvalue())["output_dir"], output.as_posix())

    def test_query_invalid_names_have_no_side_effects(self):
        for option in ("--task-name", "--query-name"):
            with self.subTest(option=option), patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
                "kbsearch_cli.__main__.configure_query_cli_logging"
            ) as configure_logging, redirect_stderr(StringIO()) as stderr:
                argv = ["query", "--task-name", "task", "--query-name", "query", "--drive-query", "x"]
                argv[argv.index(option) + 1] = "../outside"
                self.assertEqual(main(argv), 1)
                self.assertIn(option, stderr.getvalue())
                self.assertIn("input_or_config", stderr.getvalue())
                load_config.assert_not_called()
                configure_logging.assert_not_called()

    def tearDown(self):
        _close_query_cli_log_handlers()

    def test_help_describes_commands_and_query_options(self):
        with self.assertRaises(SystemExit) as root_exit, redirect_stdout(StringIO()) as root_help:
            main(["--help"])
        with self.assertRaises(SystemExit) as query_exit, redirect_stdout(StringIO()) as query_help:
            main(["query", "--help"])

        self.assertEqual(root_exit.exception.code, 0)
        self.assertEqual(query_exit.exception.code, 0)
        self.assertIn("login", root_help.getvalue())
        self.assertIn("Google Drive OAuth", root_help.getvalue())
        self.assertIn("執行前不得存在", query_help.getvalue())
        self.assertIn("secure_backend", query_help.getvalue())

    def test_login_stores_credentials_and_prints_json(self):
        config = object()
        with patch(
            "kbsearch_cli.__main__.load_login_config", return_value=config
        ), patch("kbsearch_cli.__main__.login_google_drive") as login, redirect_stdout(
            StringIO()
        ) as stdout:
            exit_code = main(["login"])

        self.assertEqual(exit_code, 0)
        login.assert_called_once_with(config)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "finished"})

    def test_query_input_failure_has_error_kind_and_no_side_effects(self):
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.configure_query_cli_logging"
        ) as configure_logging, redirect_stderr(StringIO()) as stderr:
            exit_code = main(["query", "--task-name", "task-01", "--query-name", "new-output", "--limit", "0", "--drive-query", "x"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error_kind=input_or_config", stderr.getvalue())
        load_config.assert_not_called()
        configure_logging.assert_not_called()

    def test_query_rejects_non_finite_min_score_without_side_effects(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), patch(
                "kbsearch_cli.__main__.load_query_cli_config"
            ) as load_config, patch(
                "kbsearch_cli.__main__.configure_query_cli_logging"
            ) as configure_logging, redirect_stderr(StringIO()) as stderr:
                exit_code = main(
                    [
                        "query",
                        "--task-name",
                        "task-01",
                        "--query-name",
                        "new-output",
                        "--drive-query",
                        "x",
                        f"--min-score={value}",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("error_kind=input_or_config", stderr.getvalue())
            self.assertIn("--min-score must be a finite number", stderr.getvalue())
            load_config.assert_not_called()
            configure_logging.assert_not_called()

    def test_view_results_loads_only_viewer_config_without_path_arguments(self):
        config = type(
            "Config",
            (),
            {"tasks_root": Path("C:/runtime/tasks"), "viewer_port": 8502},
        )()

        with patch("kbsearch_cli.__main__.load_viewer_config", return_value=config) as load_config, patch(
            "kbsearch_cli.__main__.run_viewer",
            return_value=0,
        ) as run_viewer:
            exit_code = main(["view-results"])

        self.assertEqual(exit_code, 0)
        load_config.assert_called_once_with()
        run_viewer.assert_called_once_with(
            host="127.0.0.1",
            port=8502,
        )

    def test_query_runs_startup_probe_orchestrator_and_prints_json_summary(self):
        bundle_path = Path("C:/tmp/query/task-01/query_results/20260531-120000-客戶")
        bundle = QueryResultBundle(
            path=bundle_path,
            query_plan_path=bundle_path / "query_plan.json",
            full_text_results_path=bundle_path / "full_text_results.json",
            vector_results_path=bundle_path / "vector_results.json",
            downloaded_files_path=bundle_path / "downloaded_files.json",
            full_text_results=[],
            vector_results=[],
            download_failures_path=bundle_path / "download_failures.json",
            warnings_path=bundle_path / "warnings.json",
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
                    pdf_path=bundle_path / "Alpha.pdf-file-1" / "Alpha.pdf",
                    text_paths=[bundle_path / "Alpha.pdf-file-1" / "text" / "0001.txt"],
                    page_paths=[bundle_path / "Alpha.pdf-file-1" / "0001.png"],
                )
            ],
            download_failure_count=0,
            download_failures=[],
            warning_count=0,
            warnings=[],
        )

        class FakeOrchestrator:
            def run(self, **kwargs):
                self.kwargs = kwargs
                return run_result

        fake_orchestrator = FakeOrchestrator()
        log_context = QueryLogContext(
            run_id="run12345",
            log_path=Path("C:/tmp/logs/kbsearch-20260622-083000-run12345.log"),
        )
        call_order = []
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.reserve_output_directory",
        ) as reserve_output_directory, patch(
            "kbsearch_cli.__main__._run_startup_probe",
        ) as run_startup_probe, patch(
            "kbsearch_cli.__main__.create_query_orchestrator",
            return_value=fake_orchestrator,
        ) as create_orchestrator, patch(
            "kbsearch_cli.__main__.new_query_run_id",
            return_value="run12345",
        ), patch(
            "kbsearch_cli.__main__.create_query_log_context",
            return_value=log_context,
        ), patch(
            "kbsearch_cli.__main__.configure_query_cli_logging",
        ) as configure_logging, patch(
            "kbsearch_cli.__main__.cleanup_old_query_log_files",
            return_value=2,
        ) as cleanup_logs, redirect_stdout(StringIO()) as stdout, redirect_stderr(
            StringIO()
        ) as stderr:
            load_config.return_value.tasks_root = Path("C:/tmp/query")
            load_config.return_value.query_logs_root = Path("C:/tmp/logs")
            load_config.return_value.query_log_retention_days = 14
            load_config.return_value.log_level = "INFO"
            run_startup_probe.side_effect = lambda *args, **kwargs: call_order.append("probe")
            reserve_output_directory.side_effect = lambda *args, **kwargs: call_order.append("reserve")
            self.assertEqual(
                main(
                    [
                        "query",
                        "--task-name",
                        "task-01",
                        "--query-name",
                        bundle_path.name,
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

        configure_logging.assert_called_once_with(log_context, "INFO")
        cleanup_logs.assert_called_once_with(
            Path("C:/tmp/logs"),
            14,
            now=ANY,
        )
        reserve_output_directory.assert_called_once_with(bundle_path)
        run_startup_probe.assert_called_once()
        self.assertEqual(call_order, ["probe", "reserve"])
        create_orchestrator.assert_called_once_with(load_config.return_value)
        self.assertEqual(fake_orchestrator.kwargs["output_dir"], bundle_path)
        self.assertIsNotNone(fake_orchestrator.kwargs["progress"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "finished")
        self.assertEqual(payload["run_id"], "run12345")
        self.assertEqual(payload["log_path"], log_context.log_path.as_posix())
        self.assertEqual(payload["output_dir"], bundle_path.as_posix())
        self.assertEqual(payload["full_text_count"], 1)
        self.assertEqual(payload["vector_count"], 2)
        self.assertEqual(payload["download_count"], 1)
        self.assertEqual(
            payload["downloaded_files"],
            [
                {
                    "google_file_id": "file-1",
                    "name": "Alpha.pdf",
                    "directory": (bundle_path / "Alpha.pdf-file-1").as_posix(),
                    "source_path": (
                        bundle_path / "Alpha.pdf-file-1" / "Alpha.pdf"
                    ).as_posix(),
                    "pdf_path": (
                        bundle_path / "Alpha.pdf-file-1" / "Alpha.pdf"
                    ).as_posix(),
                    "text_paths": [
                        (
                            bundle_path
                            / "Alpha.pdf-file-1"
                            / "text"
                            / "0001.txt"
                        ).as_posix(),
                    ],
                    "page_paths": [
                        (
                            bundle_path / "Alpha.pdf-file-1" / "0001.png"
                        ).as_posix(),
                    ],
                }
            ],
        )
        self.assertEqual(payload["download_failure_count"], 0)
        self.assertEqual(payload["download_failures"], [])
        self.assertEqual(payload["warning_count"], 0)
        self.assertEqual(payload["warnings_path"], (bundle_path / "warnings.json").as_posix())
        self.assertEqual(payload["warnings"], [])
        first_stderr_line = stderr.getvalue().splitlines()[0]
        started_event = json.loads(first_stderr_line)
        self.assertEqual(
            started_event,
            {
                "event": "query_started",
                "status": "started",
                "run_id": "run12345",
                "output_dir": bundle_path.as_posix(),
                "log_path": log_context.log_path.as_posix(),
                "monitor": "log",
                "stdout": "final_json_on_success",
            },
        )
        self.assertIn(
            "Query progress: phase=query status=started run_id=run12345",
            stderr.getvalue(),
        )
        self.assertIn(
            "Query progress: phase=query status=finished run_id=run12345",
            stderr.getvalue(),
        )
        self.assertIn("warning_count=0", stderr.getvalue())

    def _run_query_with_mocks(
        self,
        *,
        argv: list[str],
        run_result: QueryRunResult,
        log_context: QueryLogContext,
    ) -> tuple[int, "FakeOrchestrator", StringIO, StringIO, "unittest.mock.MagicMock"]:
        class FakeOrchestrator:
            def run(self, **kwargs):
                self.kwargs = kwargs
                return run_result

        fake_orchestrator = FakeOrchestrator()
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.reserve_output_directory",
        ), patch(
            "kbsearch_cli.__main__._run_startup_probe",
        ) as run_startup_probe, patch(
            "kbsearch_cli.__main__.create_query_orchestrator",
            return_value=fake_orchestrator,
        ), patch(
            "kbsearch_cli.__main__.new_query_run_id",
            return_value=log_context.run_id,
        ), patch(
            "kbsearch_cli.__main__.create_query_log_context",
            return_value=log_context,
        ), patch(
            "kbsearch_cli.__main__.configure_query_cli_logging",
        ), patch(
            "kbsearch_cli.__main__.cleanup_old_query_log_files",
            return_value=0,
        ), patch(
            "pathlib.Path.is_file", return_value=True,
        ), redirect_stdout(StringIO()) as stdout, redirect_stderr(StringIO()) as stderr:
            load_config.return_value.tasks_root = Path("C:/tmp/query")
            load_config.return_value.query_logs_root = Path("C:/tmp/logs")
            load_config.return_value.query_log_retention_days = 14
            load_config.return_value.log_level = "INFO"
            exit_code = main(argv)
        return exit_code, fake_orchestrator, stdout, stderr, run_startup_probe

    def _make_empty_run_result(self, bundle_path: Path) -> QueryRunResult:
        bundle = QueryResultBundle(
            path=bundle_path,
            query_plan_path=bundle_path / "query_plan.json",
            full_text_results_path=bundle_path / "full_text_results.json",
            vector_results_path=bundle_path / "vector_results.json",
            downloaded_files_path=bundle_path / "downloaded_files.json",
            full_text_results=[],
            vector_results=[],
            download_failures_path=bundle_path / "download_failures.json",
            warnings_path=bundle_path / "warnings.json",
        )
        return QueryRunResult(
            bundle=bundle,
            full_text_count=0,
            vector_count=0,
            vector_accessible_count=0,
            union_count=0,
            download_count=0,
            downloaded_files=[],
            download_failure_count=0,
            download_failures=[],
            warning_count=0,
            warnings=[],
        )

    def test_query_accepts_only_vector_query_and_probes_secure_backend(self):
        bundle_path = Path("C:/tmp/query/task-01/query_results/20260708-100000-vector-only")
        run_result = self._make_empty_run_result(bundle_path)
        log_context = QueryLogContext(
            run_id="runvec001",
            log_path=Path("C:/tmp/logs/kbsearch-20260708-100000-runvec001.log"),
        )

        exit_code, orchestrator, _stdout, _stderr, run_startup_probe = self._run_query_with_mocks(
            argv=[
                "query",
                "--task-name",
                "task-01",
                "--query-name",
                bundle_path.name,
                "--vector-query",
                "semantic only",
            ],
            run_result=run_result,
            log_context=log_context,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(orchestrator.kwargs["vector_query"], "semantic only")
        self.assertIsNone(orchestrator.kwargs["drive_query"])
        self.assertEqual(
            run_startup_probe.call_args.kwargs.get("probe_secure_backend"),
            True,
        )

    def test_query_accepts_only_drive_query_and_skips_secure_backend_probe(self):
        bundle_path = Path("C:/tmp/query/task-01/query_results/20260708-100000-drive-only")
        run_result = self._make_empty_run_result(bundle_path)
        log_context = QueryLogContext(
            run_id="rundrv001",
            log_path=Path("C:/tmp/logs/kbsearch-20260708-100000-rundrv001.log"),
        )

        exit_code, orchestrator, _stdout, _stderr, run_startup_probe = self._run_query_with_mocks(
            argv=[
                "query",
                "--task-name",
                "task-01",
                "--query-name",
                bundle_path.name,
                "--drive-query",
                "fullText contains 'alpha'",
            ],
            run_result=run_result,
            log_context=log_context,
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(orchestrator.kwargs["vector_query"])
        self.assertEqual(
            orchestrator.kwargs["drive_query"],
            "fullText contains 'alpha'",
        )
        self.assertEqual(orchestrator.kwargs["image_paths"], [])
        self.assertEqual(
            run_startup_probe.call_args.kwargs.get("probe_secure_backend"),
            False,
        )

    def test_query_accepts_only_image_and_probes_secure_backend(self):
        bundle_path = Path("C:/tmp/query/task-01/query_results/20260708-100000-image-only")
        run_result = self._make_empty_run_result(bundle_path)
        log_context = QueryLogContext(
            run_id="runimg001",
            log_path=Path("C:/tmp/logs/kbsearch-20260708-100000-runimg001.log"),
        )

        exit_code, orchestrator, _stdout, _stderr, run_startup_probe = self._run_query_with_mocks(
            argv=[
                "query",
                "--task-name",
                "task-01",
                "--query-name",
                bundle_path.name,
                "--image",
                "user-01.png",
            ],
            run_result=run_result,
            log_context=log_context,
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(orchestrator.kwargs["vector_query"])
        self.assertIsNone(orchestrator.kwargs["drive_query"])
        self.assertEqual(
            orchestrator.kwargs["image_paths"],
            [Path("C:/tmp/query/task-01/user-01.png")],
        )
        self.assertEqual(
            run_startup_probe.call_args.kwargs.get("probe_secure_backend"),
            True,
        )

    def test_query_rejects_when_no_search_route_provided(self):
        with redirect_stderr(StringIO()) as stderr:
            exit_code = main(
                [
                    "query",
                    "--task-name",
                    "task-01",
                    "--query-name",
                    "none",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("--vector-query", stderr.getvalue())
        self.assertIn("--drive-query", stderr.getvalue())
        self.assertIn("--image", stderr.getvalue())

    def test_query_rejects_blank_drive_query_as_missing_route(self):
        with redirect_stderr(StringIO()) as stderr:
            exit_code = main(
                [
                    "query",
                    "--task-name",
                    "task-01",
                    "--query-name",
                    "blank-drive",
                    "--drive-query",
                    "   ",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("--drive-query", stderr.getvalue())

    def test_query_rejects_blank_vector_query_without_image(self):
        with redirect_stderr(StringIO()) as stderr:
            exit_code = main(
                [
                    "query",
                    "--task-name",
                    "task-01",
                    "--query-name",
                    "blank-vector",
                    "--vector-query",
                    "   ",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("--vector-query", stderr.getvalue())
        self.assertIn("--image", stderr.getvalue())

    def test_query_treats_blank_vector_query_as_none_when_image_provided(self):
        bundle_path = Path("C:/tmp/query/task-01/query_results/20260709-blank-vector-with-image")
        run_result = self._make_empty_run_result(bundle_path)
        log_context = QueryLogContext(
            run_id="runimgblank",
            log_path=Path("C:/tmp/logs/kbsearch-20260709-010000-runimgblank.log"),
        )

        exit_code, orchestrator, _stdout, _stderr, run_startup_probe = self._run_query_with_mocks(
            argv=[
                "query",
                "--task-name",
                "task-01",
                "--query-name",
                bundle_path.name,
                "--vector-query",
                "   ",
                "--image",
                "user-01.png",
            ],
            run_result=run_result,
            log_context=log_context,
        )

        self.assertEqual(exit_code, 0)
        self.assertIsNone(orchestrator.kwargs["vector_query"])
        self.assertEqual(orchestrator.kwargs["image_paths"], [Path("C:/tmp/query/task-01/user-01.png")])
        self.assertEqual(
            run_startup_probe.call_args.kwargs.get("probe_secure_backend"),
            True,
        )

    def test_render_pdf_pages_renders_selected_pages_without_loading_query_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            document = root / "tasks" / "task" / "query_results" / "query" / "document"
            (document / "pdf").mkdir(parents=True)
            pdf_path = document / "pdf" / "document.pdf"
            pdf_path.write_bytes(b"pdf")
            output_dir = document / "pages"
            output_dir.mkdir()
            (output_dir / "0002.png").write_bytes(b"existing")
            rendered_paths = [output_dir / "0002.png", output_dir / "0004.png"]

            with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
                "kbsearch_cli.__main__.resolve_workspace_tasks_root", return_value=root / "tasks",
            ), patch(
                "kbsearch_cli.__main__.DocumentPageRenderer.render_pdf_pages",
                return_value=rendered_paths,
            ) as render_pages, redirect_stdout(StringIO()) as stdout, redirect_stderr(
                StringIO()
            ) as stderr:
                exit_code = main(
                    [
                        "render-pdf-pages",
                        "--task-name", "task", "--query-name", "query",
                        "--document-name", "document",
                        "--pages",
                        "2,4",
                    ]
                )

        self.assertEqual(exit_code, 0)
        load_config.assert_not_called()
        render_pages.assert_called_once_with(pdf_path, output_dir, [2, 4])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["pages"], [2, 4])
        self.assertEqual(payload["page_paths"], [path.as_posix() for path in rendered_paths])
        self.assertIn("status=started", stderr.getvalue())
        self.assertIn("status=finished", stderr.getvalue())

    def test_render_pdf_pages_rejects_invalid_page_expression(self):
        with redirect_stderr(StringIO()) as stderr:
            exit_code = main(
                [
                    "render-pdf-pages",
                    "--task-name", "task", "--query-name", "query",
                    "--document-name", "document",
                    "--pages",
                    "3-1",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Render PDF pages failed", stderr.getvalue())
        self.assertIn("error_kind=input_or_config", stderr.getvalue())
        self.assertIn("--pages", stderr.getvalue())

    def test_query_failure_before_logging_only_prints_stderr(self):
        with redirect_stderr(StringIO()) as stderr:
            with patch(
                "kbsearch_cli.__main__.load_query_cli_config",
                side_effect=ConfigError("Missing required config: KBSEARCH_SECURE_BACKEND_BASE_URL"),
            ):
                exit_code = main(
                    [
                        "query",
                        "--task-name",
                        "task-01",
                        "--query-name",
                        "new-query",
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
            log_root = Path(temp_dir).resolve() / "configured-logs"
            config = type(
                "Config",
                (),
                {"tasks_root": Path(temp_dir).resolve(), "query_logs_root": log_root, "query_log_retention_days": 14, "log_level": "INFO"},
            )()
            output_dir = Path(temp_dir).resolve() / "task-01" / "query_results" / "new-query"
            log_context = QueryLogContext(
                run_id="run12345",
                log_path=log_root / "kbsearch-20260622-083000-run12345.log",
            )
            try:
                with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                    "kbsearch_cli.__main__._run_startup_probe",
                    side_effect=ExternalServiceError("Secure backend unreachable"),
                ), patch(
                    "kbsearch_cli.__main__.new_query_run_id",
                    return_value="run12345",
                ), patch(
                    "kbsearch_cli.__main__.create_query_log_context",
                    return_value=log_context,
                ), patch(
                    "kbsearch_cli.__main__.configure_query_cli_logging",
                    side_effect=lambda context, level: configure_query_cli_logging(context, level),
                ), redirect_stderr(StringIO()) as stderr:
                    exit_code = main(
                        [
                            "query",
                            "--task-name",
                            "task-01",
                            "--query-name",
                            output_dir.name,
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
            self.assertIn("error_kind=external_service", stderr.getvalue())
            self.assertIn("log=", stderr.getvalue())
            self.assertIn(
                "Query progress: phase=query status=failed run_id=run12345",
                stderr.getvalue(),
            )
            log_text = log_context.log_path.read_text(encoding="utf-8")
            self.assertIn("query failed", log_text)
            self.assertIn("run_id=run12345", log_text)
            self.assertFalse(output_dir.exists())
            self.assertFalse((Path(temp_dir).resolve() / "task-01").exists())

    def test_query_rejects_existing_output_dir_before_logging_or_startup_probe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            output_dir = root / "task-01" / "query_results" / "existing-query"
            output_dir.mkdir(parents=True)
            log_root = root / "logs"
            config = type(
                "Config",
                (),
                {"tasks_root": Path(temp_dir).resolve(), "query_logs_root": log_root, "query_log_retention_days": 14, "log_level": "INFO"},
            )()
            log_context = QueryLogContext(
                run_id="run12345",
                log_path=log_root / "kbsearch-20260622-083000-run12345.log",
            )

            with patch(
                "kbsearch_cli.__main__.load_query_cli_config", return_value=config
            ) as load_config, patch(
                "kbsearch_cli.__main__._run_startup_probe",
            ) as run_startup_probe, patch(
                "kbsearch_cli.__main__.create_query_orchestrator",
            ) as create_orchestrator, patch(
                "kbsearch_cli.__main__.new_query_run_id",
                return_value="run12345",
            ), patch(
                "kbsearch_cli.__main__.create_query_log_context",
                return_value=log_context,
            ), patch(
                "kbsearch_cli.__main__.configure_query_cli_logging",
                side_effect=lambda context, level: configure_query_cli_logging(context, level),
            ), redirect_stderr(StringIO()) as stderr:
                exit_code = main(
                    [
                        "query",
                        "--task-name",
                        "task-01",
                        "--query-name",
                        output_dir.name,
                        "--vector-query",
                        "alpha",
                        "--drive-query",
                        "fullText contains 'alpha' and trashed = false",
                    ]
                )

            self.assertEqual(exit_code, 1)
            run_startup_probe.assert_not_called()
            load_config.assert_called_once_with()
            create_orchestrator.assert_not_called()
            self.assertIn("already exists", stderr.getvalue())
            self.assertFalse(log_context.log_path.exists())
            _close_query_cli_log_handlers()

    def test_query_stops_when_log_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_root = Path(temp_dir).resolve() / "logs"
            config = type(
                "Config",
                (),
                {"tasks_root": Path(temp_dir).resolve(), "query_logs_root": log_root, "query_log_retention_days": 14, "log_level": "INFO"},
            )()
            log_context = QueryLogContext(
                run_id="run12345",
                log_path=log_root / "kbsearch-20260622-083000-run12345.log",
            )

            with patch("kbsearch_cli.__main__.load_query_cli_config", return_value=config), patch(
                "kbsearch_cli.__main__.new_query_run_id",
                return_value="run12345",
            ), patch(
                "kbsearch_cli.__main__.create_query_log_context",
                return_value=log_context,
            ), patch(
                "kbsearch_cli.__main__.configure_query_cli_logging",
                side_effect=lambda context, level: configure_query_cli_logging(context, level),
            ), patch(
                "kbsearch_cli.__main__.cleanup_old_query_log_files",
                side_effect=OSError("cleanup failed"),
            ), patch(
                "kbsearch_cli.__main__._run_startup_probe",
            ) as run_startup_probe, redirect_stderr(StringIO()) as stderr:
                exit_code = main(
                    [
                        "query",
                        "--task-name",
                        "task-01",
                        "--query-name",
                        "query",
                        "--vector-query",
                        "alpha",
                        "--drive-query",
                        "fullText contains 'alpha'",
                    ]
                )

            self.assertEqual(exit_code, 1)
            run_startup_probe.assert_not_called()
            self.assertIn("status=failed", stderr.getvalue())
            log_text = log_context.log_path.read_text(encoding="utf-8")
            self.assertIn("log_cleanup_failed", log_text)
            _close_query_cli_log_handlers()

    def test_create_query_log_context_uses_timestamp_and_run_id(self):
        context = create_query_log_context(
            Path("C:/tmp/kbsearch-query-logs"),
            run_id="run12345",
            timestamp="20260622-083000-123456",
        )

        self.assertEqual(context.run_id, "run12345")
        self.assertEqual(
            context.log_path,
            Path("C:/tmp/kbsearch-query-logs/kbsearch-20260622-083000-123456-run12345.log"),
        )

    def test_cleanup_old_query_log_files_removes_only_expired_query_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_root = Path(temp_dir).resolve()
            old_log = log_root / "kbsearch-20260101-000000-old.log"
            recent_log = log_root / "kbsearch-20260621-000000-recent.log"
            unrelated_log = log_root / "other.log"
            old_log.write_text("old", encoding="utf-8")
            recent_log.write_text("recent", encoding="utf-8")
            unrelated_log.write_text("other", encoding="utf-8")
            old_time = (datetime(2026, 6, 22) - timedelta(days=30)).timestamp()
            recent_time = (datetime(2026, 6, 22) - timedelta(days=1)).timestamp()
            os.utime(old_log, (old_time, old_time))
            os.utime(recent_log, (recent_time, recent_time))

            removed = cleanup_old_query_log_files(
                log_root,
                14,
                now=datetime(2026, 6, 22),
            )

            self.assertEqual(removed, 1)
            self.assertFalse(old_log.exists())
            self.assertTrue(recent_log.exists())
            self.assertTrue(unrelated_log.exists())

    def test_cleanup_old_query_log_files_skips_when_retention_is_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_root = Path(temp_dir).resolve()
            old_log = log_root / "kbsearch-20260101-000000-old.log"
            old_log.write_text("old", encoding="utf-8")

            removed = cleanup_old_query_log_files(
                log_root,
                0,
                now=datetime(2026, 6, 22),
            )

            self.assertEqual(removed, 0)
            self.assertTrue(old_log.exists())

    def test_configure_query_cli_logging_uses_run_specific_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = QueryLogContext(
                run_id="run12345",
                log_path=Path(temp_dir).resolve() / "kbsearch-20260622-083000-run12345.log",
            )
            logger = configure_query_cli_logging(context)
            logger.info("query finished status=finished")
            for handler in logger.handlers:
                handler.flush()

            handler = next(
                handler
                for handler in logger.handlers
                if isinstance(handler, FileHandler)
            )
            self.assertEqual(Path(handler.baseFilename), context.log_path)
            log_text = context.log_path.read_text(encoding="utf-8")
            self.assertIn("run_id=run12345", log_text)
            self.assertIn("query finished status=finished", log_text)
            self.assertRegex(log_text, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z INFO")
            _close_query_cli_log_handlers()

    def test_configure_query_cli_logging_respects_level(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = QueryLogContext(
                run_id="run12345",
                log_path=Path(temp_dir).resolve() / "debug.log",
            )
            logger = configure_query_cli_logging(context, "DEBUG")
            logger.debug("debug details")
            for handler in logger.handlers:
                handler.flush()

            self.assertIn("debug details", context.log_path.read_text(encoding="utf-8"))
            _close_query_cli_log_handlers()

    def test_progress_output_failure_does_not_fail_query(self):
        logger = logging.getLogger(LOGGER_NAME)
        with patch("builtins.print", side_effect=OSError(22, "Invalid argument")):
            _emit_progress("download", {"status": "started"}, logger=logger)


if __name__ == "__main__":
    unittest.main()
