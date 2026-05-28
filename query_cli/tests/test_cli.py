import logging
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.__main__ import main, setup_logging
from kbsearch_cli.errors import QueryCliError


class CliTests(unittest.TestCase):
    def test_probe_config_returns_zero_when_config_loads(self):
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.setup_logging",
        ) as mock_setup_logging, redirect_stdout(StringIO()):
            self.assertEqual(main(["probe-config"]), 0)
            load_config.assert_called_once()
            mock_setup_logging.assert_called_once_with(load_config.return_value.query_logs_root)

    def test_probe_config_returns_nonzero_when_config_fails(self):
        with patch(
            "kbsearch_cli.__main__.load_query_cli_config",
            side_effect=QueryCliError("bad config"),
        ), redirect_stderr(StringIO()) as stderr:
            self.assertEqual(main(["probe-config"]), 1)

        self.assertIn("bad config", stderr.getvalue())

    def test_query_runs_orchestrator_and_prints_bundle_path(self):
        class FakeBundle:
            path = "C:/tmp/query"

        class FakeOrchestrator:
            def run(self, **kwargs):
                self.kwargs = kwargs
                return FakeBundle()

        fake_orchestrator = FakeOrchestrator()
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, patch(
            "kbsearch_cli.__main__.create_query_orchestrator",
            return_value=fake_orchestrator,
        ) as create_orchestrator, patch(
            "kbsearch_cli.__main__.setup_logging",
        ) as mock_setup_logging, redirect_stdout(StringIO()) as stdout:
            self.assertEqual(
                main(
                    [
                        "query",
                        "--name",
                        "客戶",
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

        create_orchestrator.assert_called_once_with(load_config.return_value)
        mock_setup_logging.assert_called_once_with(load_config.return_value.query_logs_root)
        self.assertEqual(fake_orchestrator.kwargs["query_name"], "客戶")
        self.assertEqual(fake_orchestrator.kwargs["vector_query"], "semantic alpha")
        self.assertEqual(fake_orchestrator.kwargs["drive_query"], "fullText contains 'alpha' and trashed = false")
        self.assertEqual(fake_orchestrator.kwargs["limit"], 3)
        self.assertIn("C:/tmp/query", stdout.getvalue())

    def test_setup_logging_uses_daily_rotating_file_in_configured_log_root(self):
        log_root = Path("C:/tmp/kbsearch-query-logs")
        with patch("pathlib.Path.mkdir") as mkdir:
            handler = setup_logging(log_root)

        self.assertIsInstance(handler, TimedRotatingFileHandler)
        self.assertEqual(Path(handler.baseFilename), log_root / "kbsearch_cli.log")
        self.assertEqual(handler.when, "MIDNIGHT")
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        logging.getLogger().removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    unittest.main()
