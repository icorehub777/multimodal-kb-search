import logging
import sys
import tempfile
import time
import unittest
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from kbsearch_backend.logging_config import LOGGER_NAME, configure_backend_logging


class LoggingConfigTests(unittest.TestCase):
    def test_configure_backend_logging_uses_daily_rotating_file_handler(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "secure_backend.log"

        logger = configure_backend_logging(log_path, "DEBUG")

        handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, TimedRotatingFileHandler)
            and Path(handler.baseFilename) == log_path.resolve()
        ]

        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0].when, "MIDNIGHT")
        self.assertEqual(handlers[0].backupCount, 14)
        self.assertTrue(handlers[0].utc)
        self.assertEqual(logger.level, logging.DEBUG)
        self.assertIs(handlers[0].formatter.converter, time.gmtime)

    def test_configure_backend_logging_writes_stdout_without_propagating_to_root(self):
        temp_dir = self._create_temp_dir_with_log_cleanup()
        log_path = temp_dir / "logs" / "secure_backend.log"

        logger = configure_backend_logging(log_path)

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
