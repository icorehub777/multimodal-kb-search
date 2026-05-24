import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from kbsearch_cli.__main__ import main
from kbsearch_cli.errors import QueryCliError


class CliTests(unittest.TestCase):
    def test_probe_config_returns_zero_when_config_loads(self):
        with patch("kbsearch_cli.__main__.load_query_cli_config") as load_config, redirect_stdout(StringIO()):
            self.assertEqual(main(["probe-config"]), 0)
            load_config.assert_called_once()

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
        ) as create_orchestrator, redirect_stdout(StringIO()) as stdout:
            self.assertEqual(
                main(["query", "--name", "客戶", "--query", "alpha", "--limit", "3", "--min-score", "0.4"]),
                0,
            )

        create_orchestrator.assert_called_once_with(load_config.return_value)
        self.assertEqual(fake_orchestrator.kwargs["query_name"], "客戶")
        self.assertEqual(fake_orchestrator.kwargs["limit"], 3)
        self.assertIn("C:/tmp/query", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
