import logging
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kbsearch_importer.logging_config import (
    LOGGER_NAME,
    build_run_log_file_path,
    cleanup_old_log_files,
    configure_importer_logging,
)


class LoggingConfigTests(unittest.TestCase):
    def test_build_run_log_file_path_uses_timestamp_filename(self) -> None:
        started_at = datetime(2026, 6, 9, 14, 30, 52, 123456)
        log_path = build_run_log_file_path(Path("logs"), started_at, process_id=1234)

        self.assertEqual(log_path, Path("logs") / "importer-20260609-143052-123456-p1234.log")

    def test_build_run_log_file_path_differs_for_same_second_different_microsecond(self) -> None:
        base = datetime(2026, 6, 9, 14, 30, 52)
        path_a = build_run_log_file_path(Path("logs"), base.replace(microsecond=1), process_id=100)
        path_b = build_run_log_file_path(Path("logs"), base.replace(microsecond=2), process_id=100)

        self.assertNotEqual(path_a, path_b)

    def test_build_run_log_file_path_differs_for_same_timestamp_different_process_id(self) -> None:
        started_at = datetime(2026, 6, 9, 14, 30, 52, 123456)
        path_a = build_run_log_file_path(Path("logs"), started_at, process_id=100)
        path_b = build_run_log_file_path(Path("logs"), started_at, process_id=200)

        self.assertNotEqual(path_a, path_b)

    def test_configure_importer_logging_uses_file_handler_for_run_log(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "importer-20260609-143052.log"

        logger = configure_importer_logging(log_path)

        handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename) == log_path.resolve()
        ]

        self.assertEqual(len(handlers), 1)
        self.assertEqual(logger.level, logging.INFO)

    def test_configure_importer_logging_uses_requested_level_and_utc_timestamps(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "importer.log"

        logger = configure_importer_logging(log_path, "DEBUG")

        self.assertEqual(logger.level, logging.DEBUG)
        self.assertTrue(all(handler.level == logging.DEBUG for handler in logger.handlers))
        self.assertTrue(all(handler.formatter.converter is __import__("time").gmtime for handler in logger.handlers))

    def test_build_run_log_file_path_uses_utc_by_default(self) -> None:
        with unittest.mock.patch("kbsearch_importer.logging_config.datetime") as datetime_module:
            datetime_module.now.return_value = datetime(2026, 6, 9, 6, 30, tzinfo=timezone.utc)
            path = build_run_log_file_path(Path("logs"), process_id=1)

        datetime_module.now.assert_called_once_with(timezone.utc)
        self.assertIn("20260609-063000", path.name)

    def test_configure_importer_logging_writes_stdout_without_propagating_to_root(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "importer-20260609-143052.log"

        logger = configure_importer_logging(log_path)

        stdout_handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, logging.FileHandler)
            and handler.stream is sys.stdout
        ]

        self.assertFalse(logger.propagate)
        self.assertEqual(len(stdout_handlers), 1)

    def test_configure_importer_logging_replaces_previous_run_file_handler(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        first_log_path = temp_dir / "logs" / "importer-20260609-143052-000001.log"
        second_log_path = temp_dir / "logs" / "importer-20260609-143052-000002.log"

        logger = configure_importer_logging(first_log_path)
        logger = configure_importer_logging(second_log_path)

        file_handlers = [
            handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)
        ]
        self.assertEqual(len(file_handlers), 1)
        self.assertEqual(Path(file_handlers[0].baseFilename), second_log_path.resolve())

    def test_cleanup_old_log_files_removes_logs_older_than_retention_days(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_dir = temp_dir / "logs"
        log_dir.mkdir()
        old_log = log_dir / "importer-20260101-000000.log"
        recent_log = log_dir / "importer-20260608-000000.log"
        old_log.write_text("old", encoding="utf-8")
        recent_log.write_text("recent", encoding="utf-8")
        old_time = (datetime(2026, 6, 9) - timedelta(days=30)).timestamp()
        recent_time = (datetime(2026, 6, 9) - timedelta(days=1)).timestamp()
        import os

        os.utime(old_log, (old_time, old_time))
        os.utime(recent_log, (recent_time, recent_time))

        removed = cleanup_old_log_files(log_dir, 14, now=datetime(2026, 6, 9))

        self.assertEqual(removed, 1)
        self.assertFalse(old_log.exists())
        self.assertTrue(recent_log.exists())

    def test_cleanup_old_log_files_skips_when_retention_days_is_zero(self) -> None:
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_dir = temp_dir / "logs"
        log_dir.mkdir()
        old_log = log_dir / "importer-20260101-000000.log"
        old_log.write_text("old", encoding="utf-8")

        removed = cleanup_old_log_files(log_dir, 0, now=datetime(2026, 6, 9))

        self.assertEqual(removed, 0)
        self.assertTrue(old_log.exists())

    def _create_temp_dir_with_log_cleanup(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(self._close_log_handlers)
        return Path(temp_dir.name)

    def _close_log_handlers(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
