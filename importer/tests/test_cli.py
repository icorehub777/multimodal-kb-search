import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from kbsearch_importer.__main__ import main
from kbsearch_importer.errors import ImporterError


class CliTests(unittest.TestCase):
    def test_main_returns_zero_when_probe_config_succeeds(self):
        with patch("kbsearch_importer.__main__.load_importer_config") as load_config, redirect_stdout(StringIO()):
            self.assertEqual(main(["probe-config"]), 0)
            load_config.assert_called_once()

    def test_main_returns_nonzero_when_probe_config_fails(self):
        with patch(
            "kbsearch_importer.__main__.load_importer_config",
            side_effect=RuntimeError("bad"),
        ), redirect_stderr(StringIO()):
            self.assertEqual(main(["probe-config"]), 1)

    def test_sync_runs_orchestrator_and_prints_summary(self):
        class FakeOrchestrator:
            def run(self):
                return type(
                    "Summary",
                    (),
                    {"imported": 1, "deleted": 2, "reimported": 3, "skipped": 4},
                )()

        with patch("kbsearch_importer.__main__.load_importer_config") as load_config, patch(
            "kbsearch_importer.__main__.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ) as create_orchestrator, redirect_stdout(StringIO()) as stdout:
            self.assertEqual(main(["sync"]), 0)

        create_orchestrator.assert_called_once_with(load_config.return_value)
        self.assertIn("imported=1", stdout.getvalue())
        self.assertIn("deleted=2", stdout.getvalue())
        self.assertIn("reimported=3", stdout.getvalue())
        self.assertIn("skipped=4", stdout.getvalue())

    def test_sync_returns_nonzero_for_domain_error(self):
        class FakeOrchestrator:
            def run(self):
                raise ImporterError("sync failed")

        with patch("kbsearch_importer.__main__.load_importer_config"), patch(
            "kbsearch_importer.__main__.create_sync_orchestrator",
            return_value=FakeOrchestrator(),
        ), redirect_stderr(StringIO()) as stderr:
            self.assertEqual(main(["sync"]), 1)

        self.assertIn("sync failed", stderr.getvalue())

    def test_probe_services_runs_service_probe(self):
        with patch("kbsearch_importer.__main__.load_importer_config") as load_config, patch(
            "kbsearch_importer.__main__.probe_external_services",
            return_value={
                "google_documents": 1,
                "dashscope_dimension": 3,
                "qdrant_documents": 2,
            },
        ) as probe_services, redirect_stdout(StringIO()) as stdout:
            self.assertEqual(main(["probe-services"]), 0)

        probe_services.assert_called_once_with(load_config.return_value)
        self.assertIn("google_documents=1", stdout.getvalue())

    def test_probe_services_returns_nonzero_for_domain_error(self):
        with patch("kbsearch_importer.__main__.load_importer_config"), patch(
            "kbsearch_importer.__main__.probe_external_services",
            side_effect=ImporterError("probe failed"),
        ), redirect_stderr(StringIO()) as stderr:
            self.assertEqual(main(["probe-services"]), 1)

        self.assertIn("probe failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
