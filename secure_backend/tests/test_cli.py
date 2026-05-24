import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from kbsearch_secure_backend.__main__ import main
from kbsearch_secure_backend.config import ConfigError


class CliTests(unittest.TestCase):
    def test_probe_config_returns_zero_when_config_loads(self):
        with patch("kbsearch_secure_backend.__main__.load_backend_config") as load_config, redirect_stdout(StringIO()):
            self.assertEqual(main(["probe-config"]), 0)
            load_config.assert_called_once()

    def test_probe_config_returns_nonzero_when_config_fails(self):
        with patch(
            "kbsearch_secure_backend.__main__.load_backend_config",
            side_effect=ConfigError("bad config"),
        ), redirect_stderr(StringIO()) as stderr:
            self.assertEqual(main(["probe-config"]), 1)

        self.assertIn("bad config", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
