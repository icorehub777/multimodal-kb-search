import tomllib
import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_python_support_matches_validated_minor_version(self):
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as source:
            metadata = tomllib.load(source)
        self.assertEqual(metadata["project"]["requires-python"], ">=3.12,<3.13")


if __name__ == "__main__":
    unittest.main()
