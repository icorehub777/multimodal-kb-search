import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_importer.config import ConfigError, load_google_drive_sources, load_importer_config


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

    def test_load_importer_config_rejects_vector_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=128",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "must match"):
                    load_importer_config(env_file)

    def test_load_importer_config_rejects_missing_required_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "DASHSCOPE_API_KEY"):
                    load_importer_config(env_file)

    def test_load_importer_config_sets_importer_root_from_env_file_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            importer_root = Path(temp_dir) / "importer"
            config_dir = importer_root / "config"
            config_dir.mkdir(parents=True)
            source_config = config_dir / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = config_dir / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "GOOGLE_DRIVE_SOURCE_CONFIG=./config/google_drive_sources.yaml",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_importer_config(env_file)

        self.assertEqual(config.importer_root, importer_root)
        self.assertEqual(config.google_drive_source_config, source_config)

    def test_load_importer_config_reads_required_absolute_libreoffice_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_importer_config(env_file)

        self.assertEqual(config.libreoffice_command, "C:\\Program Files\\LibreOffice\\program\\soffice.exe")
        self.assertEqual(config.cjk_font_path, Path("C:\\Windows\\Fonts\\msjh.ttc"))

    def test_load_importer_config_rejects_missing_libreoffice_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "LIBREOFFICE_COMMAND"):
                    load_importer_config(env_file)

    def test_load_importer_config_rejects_relative_libreoffice_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=soffice",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "absolute path"):
                    load_importer_config(env_file)

    def test_load_importer_config_rejects_missing_cjk_font_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "KBSEARCH_CJK_FONT_PATH"):
                    load_importer_config(env_file)

    def test_load_importer_config_rejects_relative_cjk_font_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=msjh.ttc",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "absolute path"):
                    load_importer_config(env_file)

    def test_load_importer_config_reads_work_file_retention_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                        "IMPORTER_KEEP_SUCCESS_WORK_FILES=false",
                        "IMPORTER_KEEP_FAILED_WORK_FILES=true",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_importer_config(env_file)

        self.assertFalse(config.keep_success_work_files)
        self.assertTrue(config.keep_failed_work_files)

    def test_load_importer_config_rejects_invalid_work_file_retention_setting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_config = temp_path / "google_drive_sources.yaml"
            source_config.write_text(
                "\n".join(
                    [
                        "sources:",
                        "  - name: belltaih-shared-drive",
                        "    type: shared_drive",
                        "    drive_id: drive-1",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = temp_path / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        f"GOOGLE_DRIVE_SOURCE_CONFIG={source_config}",
                        "GOOGLE_SERVICE_ACCOUNT_EMAIL=svc@example.com",
                        "GOOGLE_DWD_SUBJECT_EMAIL=user@example.com",
                        "DASHSCOPE_API_KEY=secret",
                        "DASHSCOPE_EMBEDDING_MODEL=qwen3-vl-embedding",
                        "DASHSCOPE_VECTOR_SIZE=2560",
                        "QDRANT_URL=https://qdrant.example.com",
                        "QDRANT_API_KEY=secret",
                        "QDRANT_COLLECTION=kbsearch",
                        "QDRANT_VECTOR_SIZE=2560",
                        "LIBREOFFICE_COMMAND=C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                        "KBSEARCH_CJK_FONT_PATH=C:\\Windows\\Fonts\\msjh.ttc",
                        "IMPORTER_KEEP_SUCCESS_WORK_FILES=maybe",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "IMPORTER_KEEP_SUCCESS_WORK_FILES"):
                    load_importer_config(env_file)


if __name__ == "__main__":
    unittest.main()
