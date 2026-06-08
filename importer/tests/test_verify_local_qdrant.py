import unittest
from unittest.mock import patch

from verify_local_qdrant import main


class VerifyLocalQdrantTests(unittest.TestCase):
    def test_main_cleans_up_collection_when_importer_check_fails(self) -> None:
        with patch(
            "verify_local_qdrant._run_importer_checks",
            side_effect=RuntimeError("import failed"),
        ), patch("verify_local_qdrant._cleanup_probe") as cleanup_probe:
            with self.assertRaisesRegex(RuntimeError, "import failed"):
                main()

        cleanup_probe.assert_called_once_with(None)

    def test_main_cleans_up_probe_when_secure_backend_check_fails(self) -> None:
        with patch(
            "verify_local_qdrant._run_importer_checks",
            return_value=([1.0], "probe-file"),
        ), patch(
            "verify_local_qdrant._run_secure_backend_checks",
            side_effect=RuntimeError("search failed"),
        ), patch("verify_local_qdrant._cleanup_probe") as cleanup_probe:
            with self.assertRaisesRegex(RuntimeError, "search failed"):
                main()

        cleanup_probe.assert_called_once_with("probe-file")


if __name__ == "__main__":
    unittest.main()
