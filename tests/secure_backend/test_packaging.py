import tomllib
import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_test_client_dependency_is_development_only(self):
        project_root = Path(__file__).resolve().parents[2] / "src" / "secure_backend"
        with (project_root / "pyproject.toml").open("rb") as source:
            project = tomllib.load(source)["project"]
        self.assertEqual(project["optional-dependencies"]["dev"], ["httpx2==2.13.1"])
        self.assertFalse(any(item.startswith("httpx") for item in project["dependencies"]))


if __name__ == "__main__":
    unittest.main()
