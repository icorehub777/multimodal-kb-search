import tomllib
import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_wheel_build_tool_is_development_only(self):
        project_root = Path(__file__).resolve().parents[2] / "src" / "query_cli"
        with (project_root / "pyproject.toml").open("rb") as source:
            project = tomllib.load(source)["project"]
        self.assertEqual(project["optional-dependencies"]["dev"], ["build==1.5.0"])
        self.assertFalse(any(item.startswith("build") for item in project["dependencies"]))

    def test_python_support_matches_validated_minor_version(self):
        project_root = Path(__file__).resolve().parents[2] / "src" / "query_cli"
        with (project_root / "pyproject.toml").open("rb") as source:
            metadata = tomllib.load(source)
        self.assertEqual(metadata["project"]["requires-python"], ">=3.12,<3.13")


if __name__ == "__main__":
    unittest.main()
