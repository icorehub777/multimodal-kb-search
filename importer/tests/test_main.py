import logging
import sys
import tempfile
import unittest
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from app.config import ConfigError
from app.errors import ImporterError
from app.logging_config import LOGGER_NAME, configure_importer_logging
from main import main


class MainTests(unittest.TestCase):
    def test_main_runs_startup_probe_and_sync(self):
        class FakeOrchestrator:
            def run(self):
                return type(
                    "Summary",
                    (),
                    {"imported": 1, "deleted": 2, "reimported": 3, "skipped": 4},
                )()

        with patch("main.load_importer_config") as load_config, patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main"),
        ), patch("main._run_startup_probe"), patch(
            "main.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ) as create_orchestrator:
            self.assertEqual(main(), 0)

        create_orchestrator.assert_called_once_with(load_config.return_value)

    def test_main_returns_nonzero_when_config_load_fails(self):
        with patch(
            "main.load_importer_config",
            side_effect=ConfigError("missing key"),
        ):
            self.assertEqual(main(), 1)

    def test_main_returns_nonzero_when_sync_fails(self):
        class FakeOrchestrator:
            def run(self):
                raise ImporterError("sync failed")

        with patch("main.load_importer_config"), patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main.fail"),
        ), patch("main._run_startup_probe"), patch(
            "main.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ):
            self.assertEqual(main(), 1)

    def test_main_returns_nonzero_when_startup_probe_fails(self):
        with patch("main.load_importer_config"), patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main.probe"),
        ), patch(
            "main._run_startup_probe",
            side_effect=ImporterError("probe failed"),
        ), patch("main.create_sync_orchestrator") as create_orchestrator:
            self.assertEqual(main(), 1)

        create_orchestrator.assert_not_called()


class LoggingConfigTests(unittest.TestCase):
    def test_configure_importer_logging_uses_daily_rotating_file_handler(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "importer.log"

        logger = configure_importer_logging(log_path)

        handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, TimedRotatingFileHandler)
            and Path(handler.baseFilename) == log_path.resolve()
        ]

        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0].when, "MIDNIGHT")
        self.assertEqual(handlers[0].backupCount, 14)
        self.assertEqual(logger.level, logging.INFO)

    def test_configure_importer_logging_writes_stdout_without_propagating_to_root(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "importer.log"

        logger = configure_importer_logging(log_path)

        stdout_handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, TimedRotatingFileHandler)
            and handler.stream is sys.stdout
        ]

        self.assertFalse(logger.propagate)
        self.assertEqual(len(stdout_handlers), 1)

    def _create_temp_dir_with_log_cleanup(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(self._close_log_handlers)
        return Path(temp_dir.name)

    def _close_log_handlers(self):
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
