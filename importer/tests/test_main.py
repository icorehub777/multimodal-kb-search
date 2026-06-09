import logging
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from app.config import DEFAULT_LOG_DIR, ConfigError
from app.errors import ImporterError
from main import main

SAMPLE_LOG_FILE = Path("logs") / "importer-20260609-143052-123456-p1234.log"


class MainTests(unittest.TestCase):
    def test_main_runs_startup_probe_and_sync(self):
        class FakeOrchestrator:
            def run(self):
                return type(
                    "Summary",
                    (),
                    {"imported": 1, "deleted": 2, "reimported": 3, "skipped": 4, "failed": 0},
                )()

        fake_config = type(
            "Config",
            (),
            {
                "qdrant_collection": "kbsearch",
                "google_drive_sources": (object(),),
                "log_retention_days": 14,
            },
        )()
        started_at = datetime(2026, 6, 9, 14, 30, 52, 123456)
        log_file = SAMPLE_LOG_FILE

        with patch("main.load_importer_config", return_value=fake_config), patch(
            "main.datetime"
        ) as datetime_module, patch(
            "main.build_run_log_file_path",
            return_value=log_file,
        ) as build_log_path, patch(
            "main.cleanup_old_log_files",
            return_value=2,
        ) as cleanup_logs, patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main"),
        ) as configure_logging, patch("main._run_startup_probe"), patch(
            "main.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ) as create_orchestrator:
            datetime_module.now.return_value = started_at
            self.assertEqual(main(), 0)

        build_log_path.assert_called_once()
        cleanup_logs.assert_called_once()
        configure_logging.assert_called_once_with(log_file)
        create_orchestrator.assert_called_once_with(fake_config)

    def test_main_returns_nonzero_when_sync_has_failed_imports(self):
        class FakeOrchestrator:
            def run(self):
                return type(
                    "Summary",
                    (),
                    {"imported": 1, "deleted": 0, "reimported": 0, "skipped": 0, "failed": 1},
                )()

        fake_config = type(
            "Config",
            (),
            {
                "qdrant_collection": "kbsearch",
                "google_drive_sources": (object(),),
                "log_retention_days": 14,
            },
        )()

        with patch("main.load_importer_config", return_value=fake_config), patch(
            "main.build_run_log_file_path",
            return_value=SAMPLE_LOG_FILE,
        ), patch("main.cleanup_old_log_files", return_value=0), patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main.partial"),
        ), patch("main._run_startup_probe"), patch(
            "main.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ):
            self.assertEqual(main(), 1)

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

        fake_config = type(
            "Config",
            (),
            {
                "qdrant_collection": "kbsearch",
                "google_drive_sources": (object(),),
                "log_retention_days": 14,
            },
        )()

        with patch("main.load_importer_config", return_value=fake_config), patch(
            "main.build_run_log_file_path",
            return_value=SAMPLE_LOG_FILE,
        ), patch("main.cleanup_old_log_files", return_value=0), patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main.fail"),
        ), patch("main._run_startup_probe"), patch(
            "main.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ):
            self.assertEqual(main(), 1)

    def test_main_returns_nonzero_when_startup_probe_fails(self):
        fake_config = type(
            "Config",
            (),
            {
                "qdrant_collection": "kbsearch",
                "google_drive_sources": (object(),),
                "log_retention_days": 14,
            },
        )()

        with patch("main.load_importer_config", return_value=fake_config), patch(
            "main.build_run_log_file_path",
            return_value=SAMPLE_LOG_FILE,
        ), patch("main.cleanup_old_log_files", return_value=0), patch(
            "main.configure_importer_logging",
            return_value=logging.getLogger("importer.tests.main.probe"),
        ), patch(
            "main._run_startup_probe",
            side_effect=ImporterError("probe failed"),
        ), patch("main.create_sync_orchestrator") as create_orchestrator:
            self.assertEqual(main(), 1)

        create_orchestrator.assert_not_called()

    def test_main_logs_and_stops_when_log_cleanup_fails(self):
        fake_config = type(
            "Config",
            (),
            {
                "qdrant_collection": "kbsearch",
                "google_drive_sources": (object(),),
                "log_retention_days": 14,
            },
        )()
        logger = Mock(spec=logging.Logger)
        cleanup_error = OSError("cleanup failed")

        with patch("main.load_importer_config", return_value=fake_config), patch(
            "main.build_run_log_file_path",
            return_value=SAMPLE_LOG_FILE,
        ), patch(
            "main.configure_importer_logging",
            return_value=logger,
        ), patch(
            "main.cleanup_old_log_files",
            side_effect=cleanup_error,
        ), patch("main._run_startup_probe") as startup_probe, patch(
            "main.create_sync_orchestrator"
        ) as create_orchestrator:
            self.assertEqual(main(), 1)

        logger.exception.assert_called_once_with(
            "log_cleanup_failed log_dir=%s retention_days=%s error=%s message=%s",
            DEFAULT_LOG_DIR,
            14,
            "OSError",
            cleanup_error,
        )
        startup_probe.assert_not_called()
        create_orchestrator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
