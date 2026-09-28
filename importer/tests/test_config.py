import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app.config import APP_ROOT, ConfigError, load_google_drive_sources, load_importer_config

_SOURCE_YAML = "\n".join(
    [
        "sources:",
        "  - name: belltaih-shared-drive",
        "    type: shared_drive",
        "    drive_id: drive-1",
    ]
)

_BASE_ENV = "\n".join(
    [
        "GOOGLE_APPLICATION_CREDENTIALS=placeholder-gcp-adc.json",
        "GOOGLE_DRIVE_SOURCE_CONFIG=placeholder-google_drive_sources.yaml",
        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
        "DASHSCOPE_API_KEY=secret",
        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
        "DASHSCOPE_VECTOR_SIZE=2560",
        "DASHSCOPE_IMAGE_MAX_BYTES=9728000",
        "DASHSCOPE_JPEG_QUALITY=95",
        "QDRANT_URL=http://127.0.0.1:6333",
        "QDRANT_API_KEY=",
        "QDRANT_COLLECTION=kbsearch",
        "QDRANT_VECTOR_SIZE=2560",
        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
        "IMPORTER_PDF_RENDER_TARGET_DPI=200",
        "IMPORTER_PDF_RENDER_MAX_PIXELS=80000000",
    ]
)


class ConfigTests(unittest.TestCase):
    def test_load_google_drive_sources_supports_shared_drive_and_folder_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_config = Path(temp_dir) / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                        "  - name: project-folder",
                        "    type: folder",
                        "    folder_id: folder-1",
                    ]
                ),
                encoding="utf-8",
            )

            sources = load_google_drive_sources(source_config)

        self.assertEqual(sources[0].name, "belltaih-shared-drive")
        self.assertEqual(sources[0].type, "shared_drive")
        self.assertEqual(sources[0].drive_id, "drive-1")
        self.assertIsNone(sources[0].folder_id)
        self.assertEqual(sources[1].name, "project-folder")
        self.assertEqual(sources[1].type, "folder")
        self.assertEqual(sources[1].folder_id, "folder-1")
        self.assertIsNone(sources[1].drive_id)

    def test_load_google_drive_sources_rejects_missing_required_source_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_config = Path(temp_dir) / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: invalid-shared-drive",
                        "    type: shared_drive",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "requires drive_id"):
                load_google_drive_sources(source_config)

    def test_load_google_drive_sources_rejects_invalid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_config = Path(temp_dir) / "google_drive_sources.yaml"
            source_config.write_text("sources: [", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "Unable to parse"):
                load_google_drive_sources(source_config)

    def test_load_google_drive_sources_rejects_duplicate_names_and_identifiers(self) -> None:
        cases = (
            ("name", "  - name: duplicate\n    type: folder\n    folder_id: folder-2"),
            ("identifier", "  - name: second\n    type: folder\n    folder_id: drive-1"),
        )
        for expected, second_source in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp_dir:
                source_config = Path(temp_dir) / "google_drive_sources.yaml"
                source_config.write_text(
                    "\n".join(
                        [
                            "sources:",
                            "  - name: duplicate",
                            "    type: shared_drive",
                            "    drive_id: drive-1",
                            second_source,
                        ]
                    ),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ConfigError, expected):
                    load_google_drive_sources(source_config)

    def test_load_importer_config_allows_empty_qdrant_api_key(self) -> None:
        with self._config_context("QDRANT_API_KEY=") as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertIsNone(config.qdrant_api_key)

    def test_load_importer_config_rejects_vector_size_mismatch(self) -> None:
        with self._config_context("QDRANT_VECTOR_SIZE=128") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "must match"):
                load_importer_config(env_file)

    def test_load_importer_config_rejects_non_positive_vector_sizes(self) -> None:
        for setting in ("DASHSCOPE_VECTOR_SIZE=0", "QDRANT_VECTOR_SIZE=-1"):
            with self.subTest(setting=setting):
                with self._config_context(setting) as (env_file, source_config):
                    with self.assertRaisesRegex(ConfigError, "positive integer"):
                        load_importer_config(env_file)

    def test_load_importer_config_rejects_missing_required_config(self) -> None:
        with self._config_context("DASHSCOPE_API_KEY=") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "DASHSCOPE_API_KEY"):
                load_importer_config(env_file)

    def test_load_importer_config_reads_env_file_with_utf8_bom(self) -> None:
        with self._config_context() as (env_file, source_config):
            raw = env_file.read_bytes()
            if not raw.startswith(b"\xef\xbb\xbf"):
                env_file.write_bytes(b"\xef\xbb\xbf" + raw)
            with patch.dict(os.environ, {}, clear=True):
                config = load_importer_config(env_file)

        self.assertEqual(config.google_dwd_subject_email, "user@example.com")

    def test_load_importer_config_rejects_missing_google_application_credentials(self) -> None:
        with self._config_context("GOOGLE_APPLICATION_CREDENTIALS=") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "GOOGLE_APPLICATION_CREDENTIALS"):
                load_importer_config(env_file)

    def test_load_importer_config_rejects_missing_google_drive_source_config(self) -> None:
        with self._config_context("GOOGLE_DRIVE_SOURCE_CONFIG=") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "GOOGLE_DRIVE_SOURCE_CONFIG"):
                load_importer_config(env_file)

    def test_load_importer_config_uses_fixed_app_root_and_source_config(self) -> None:
        with self._config_context() as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertEqual(config.app_root, APP_ROOT)
        self.assertEqual(config.google_drive_source_config, source_config)

    def test_load_importer_config_reads_required_absolute_cjk_font_path(self) -> None:
        with self._config_context() as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertEqual(config.cjk_font_path, Path("C:\\Windows\\Fonts\\msjh.ttc"))

    def test_load_importer_config_rejects_missing_cjk_font_path(self) -> None:
        with self._config_context("KBSEARCH_CJK_FONT_PATH=") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "KBSEARCH_CJK_FONT_PATH"):
                load_importer_config(env_file)

    def test_load_importer_config_rejects_relative_cjk_font_path(self) -> None:
        with self._config_context("KBSEARCH_CJK_FONT_PATH=msjh.ttc") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "absolute path"):
                load_importer_config(env_file)

    def test_load_importer_config_reads_work_file_retention_settings(self) -> None:
        with self._config_context(
            "IMPORTER_KEEP_SUCCESS_WORK_FILES=false",
            "IMPORTER_KEEP_FAILED_WORK_FILES=true",
        ) as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertFalse(config.keep_success_work_files)
        self.assertTrue(config.keep_failed_work_files)

    def test_load_importer_config_uses_safe_work_file_retention_defaults(self) -> None:
        with self._config_context() as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertFalse(config.keep_success_work_files)
        self.assertTrue(config.keep_failed_work_files)

    def test_load_importer_config_reads_and_validates_log_level(self) -> None:
        with self._config_context("IMPORTER_LOG_LEVEL=debug") as (env_file, source_config):
            config = load_importer_config(env_file)
        self.assertEqual(config.log_level, "DEBUG")

        with self._config_context("IMPORTER_LOG_LEVEL=verbose") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "IMPORTER_LOG_LEVEL"):
                load_importer_config(env_file)

    def test_load_importer_config_reads_pdf_render_and_dashscope_image_settings(self) -> None:
        with self._config_context(
            "IMPORTER_PDF_RENDER_TARGET_DPI=240",
            "IMPORTER_PDF_RENDER_MAX_PIXELS=70000000",
            "DASHSCOPE_IMAGE_MAX_BYTES=9000000",
            "DASHSCOPE_JPEG_QUALITY=90",
        ) as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertEqual(config.pdf_render_target_dpi, 240)
        self.assertEqual(config.pdf_render_max_pixels, 70_000_000)
        self.assertEqual(config.dashscope_image_max_bytes, 9_000_000)
        self.assertEqual(config.dashscope_jpeg_quality, 90)

    def test_load_importer_config_rejects_image_settings_outside_safe_ranges(self) -> None:
        invalid_settings = (
            "IMPORTER_PDF_RENDER_TARGET_DPI=71",
            "IMPORTER_PDF_RENDER_MAX_PIXELS=90000000",
            "DASHSCOPE_IMAGE_MAX_BYTES=10485761",
            "DASHSCOPE_JPEG_QUALITY=101",
        )
        for invalid_setting in invalid_settings:
            with self.subTest(invalid_setting=invalid_setting):
                with self._config_context(invalid_setting) as (env_file, source_config):
                    with self.assertRaises(ConfigError):
                        load_importer_config(env_file)

    def test_load_importer_config_reads_log_retention_days(self) -> None:
        with self._config_context("IMPORTER_LOG_RETENTION_DAYS=30") as (env_file, source_config):
            config = load_importer_config(env_file)

        self.assertEqual(config.log_retention_days, 30)

    def test_load_importer_config_rejects_negative_log_retention_days(self) -> None:
        with self._config_context("IMPORTER_LOG_RETENTION_DAYS=-1") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "IMPORTER_LOG_RETENTION_DAYS"):
                load_importer_config(env_file)

    def test_load_importer_config_rejects_invalid_work_file_retention_setting(self) -> None:
        with self._config_context("IMPORTER_KEEP_SUCCESS_WORK_FILES=maybe") as (env_file, source_config):
            with self.assertRaisesRegex(ConfigError, "IMPORTER_KEEP_SUCCESS_WORK_FILES"):
                load_importer_config(env_file)

    @contextmanager
    def _config_context(self, *overrides: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(_SOURCE_YAML, encoding="utf-8")
            env_file = temp_path / ".env"
            env_lines = dict(line.split("=", 1) for line in _BASE_ENV.splitlines())
            adc_file = temp_path / "gcp-adc.json"
            adc_file.write_text('{"client_email": "svc@example.com"}', encoding="utf-8")
            env_lines["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc_file)
            env_lines["GOOGLE_DRIVE_SOURCE_CONFIG"] = str(source_config)
            for override in overrides:
                key, value = override.split("=", 1)
                env_lines[key] = value
            env_file.write_text("\n".join(f"{key}={value}" for key, value in env_lines.items()), encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                yield env_file, source_config


if __name__ == "__main__":
    unittest.main()
