import unittest
import tomllib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


class DeploymentLayoutTests(unittest.TestCase):
    def test_project_tests_are_grouped_under_repository_tests(self):
        for project in ("importer", "secure_backend", "query_cli"):
            with self.subTest(project=project):
                self.assertTrue((REPO_ROOT / "tests" / project).is_dir())
                self.assertFalse((REPO_ROOT / project / "tests").exists())

    def test_service_images_use_explicit_debian_release(self):
        for project in ("importer", "secure_backend"):
            with self.subTest(project=project):
                dockerfile = (REPO_ROOT / "docker" / f"Dockerfile.{project}").read_text(encoding="utf-8")
                self.assertEqual(dockerfile.splitlines()[0], "FROM python:3.12-slim-bookworm")

    def test_importer_installs_headless_office_packages(self):
        dockerfile = (REPO_ROOT / "docker/Dockerfile.importer").read_text(encoding="utf-8")
        for component in ("writer", "impress", "calc"):
            self.assertIn(f"libreoffice-{component}-nogui", dockerfile)
        self.assertIn("fonts-noto-cjk", dockerfile)
        self.assertIn("fonts-wqy-zenhei", dockerfile)

    def test_importer_build_supports_explicit_debian_mirror(self):
        dockerfile = (REPO_ROOT / "docker/Dockerfile.importer").read_text(encoding="utf-8")
        self.assertIn("ARG DEBIAN_MIRROR=http://deb.debian.org/debian", dockerfile)
        self.assertIn("${DEBIAN_MIRROR}", dockerfile)
        self.assertNotIn("trusted=yes", dockerfile)
        launcher = (REPO_ROOT / "docker/docker_build_importer.ps1").read_text(encoding="utf-8")
        self.assertIn("$DebianMirror", launcher)
        self.assertIn("--build-arg", launcher)

    def test_build_launchers_are_available(self):
        for project in ("importer", "secure_backend"):
            launcher = REPO_ROOT / "docker" / f"docker_build_{project}.ps1"
            self.assertTrue(launcher.is_file())

    def test_qdrant_has_explicit_open_file_limits(self):
        service = yaml.safe_load(
            (REPO_ROOT / "deploy/qdrant/docker-compose.yml").read_text(encoding="utf-8")
        )["services"]["qdrant"]
        self.assertEqual(service["ulimits"]["nofile"], {"soft": 65536, "hard": 65536})

    def test_python_projects_have_independent_package_definitions(self):
        for project, package in (
            ("importer", "kbsearch_importer"),
            ("secure_backend", "kbsearch_backend"),
            ("query_cli", "kbsearch_cli"),
        ):
            with self.subTest(project=project):
                root = REPO_ROOT / project
                metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
                self.assertEqual(metadata["project"]["requires-python"], ">=3.12,<3.13")
                self.assertEqual(metadata["tool"]["setuptools"]["packages"]["find"]["include"], [package + "*"])
                self.assertEqual(metadata["tool"]["setuptools"]["packages"]["find"]["where"], ["src"])
                self.assertTrue((root / "src" / package / "__init__.py").is_file())
                self.assertTrue((root / "LICENSE").is_file())
                self.assertFalse((root / "requirements.txt").exists())

    def test_runtime_compose_uses_image_and_service_local_directories(self):
        service = yaml.safe_load(
            (REPO_ROOT / "deploy/importer/docker-compose.yml").read_text(encoding="utf-8")
        )["services"]["importer"]
        self.assertEqual(service["image"], "kbsearch-importer")
        self.assertNotIn("build", service)
        self.assertEqual(service["volumes"], [
            "./config:/app/config:ro", "./logs:/app/logs", "./work:/app/work",
        ])

    def test_dev_override_mounts_only_current_source_readonly(self):
        service = yaml.safe_load(
            (REPO_ROOT / "deploy/importer/docker-compose.dev.yml").read_text(encoding="utf-8")
        )["services"]["importer"]
        self.assertEqual(service["volumes"], [
            "../../importer/src/kbsearch_importer:/app/kbsearch_importer:ro",
        ])
        self.assertNotIn("command", service)

    def test_backend_dev_override_uses_backend_package(self):
        service = yaml.safe_load(
            (REPO_ROOT / "deploy/secure_backend/docker-compose.dev.yml").read_text(encoding="utf-8")
        )["services"]["secure-backend"]
        self.assertEqual(service["volumes"], [
            "../../secure_backend/src/kbsearch_backend:/app/kbsearch_backend:ro",
        ])
        self.assertEqual(service["command"][1], "kbsearch_backend.__main__:app")

    def test_service_runtime_roots_do_not_depend_on_installation_location(self):
        from kbsearch_importer.config import APP_ROOT

        self.assertEqual(APP_ROOT, Path("/app"))

    def test_images_install_dependencies_before_copying_source(self):
        for project, package in (("importer", "kbsearch_importer"), ("secure_backend", "kbsearch_backend")):
            with self.subTest(project=project):
                dockerfile = (REPO_ROOT / "docker" / f"Dockerfile.{project}").read_text(encoding="utf-8")
                self.assertIn("COPY pyproject.toml .", dockerfile)
                self.assertLess(dockerfile.index("RUN python -c"), dockerfile.index(f"COPY src/{package}/"))

    def test_build_launchers_use_docker_build_with_independent_contexts(self):
        self.assertFalse((REPO_ROOT / "docker/docker-compose.yml").exists())
        for project, image in (("importer", "kbsearch-importer"), ("secure_backend", "kbsearch-secure-backend")):
            with self.subTest(project=project):
                launcher = (REPO_ROOT / "docker" / f"docker_build_{project}.ps1").read_text(encoding="utf-8")
                self.assertIn("& docker build", launcher)
                self.assertNotIn("docker compose", launcher)
                self.assertIn(f"'../{project}'", launcher)
                self.assertIn(f"'Dockerfile.{project}'", launcher)
                self.assertIn(f"-t {image}", launcher)
                self.assertIn("exit $LASTEXITCODE", launcher)
                self.assertFalse((REPO_ROOT / project / "docker").exists())

    def test_template_uses_container_paths(self):
        from dotenv import dotenv_values

        template = dotenv_values(REPO_ROOT / "deploy/importer/config/.env.example")
        self.assertEqual(template["QDRANT_URL"], "http://qdrant:6333")
        self.assertEqual(template["KBSEARCH_VECTOR_SIZE"], "2560")
        for name in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_DRIVE_SOURCE_CONFIG", "KBSEARCH_CJK_FONT_PATH", "DASHSCOPE_VECTOR_SIZE", "QDRANT_VECTOR_SIZE"):
            self.assertNotIn(name, template)


if __name__ == "__main__":
    unittest.main()
