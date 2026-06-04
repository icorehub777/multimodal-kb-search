import unittest
from pathlib import Path

from app.metadata import build_page_vector_metadata
from app.models import WorkspaceDocument


class MetadataTests(unittest.TestCase):
    def test_build_page_vector_metadata_contains_required_spec_fields(self) -> None:
        document = WorkspaceDocument(
            file_id="file-1",
            name="Spec.pdf",
            location="/drive/Specs/Spec.pdf",
            web_url="https://drive.google.com/file/d/file-1",
            version="7",
            modified_time="2026-05-24T00:00:00Z",
            mime_type="application/pdf",
        )

        metadata = build_page_vector_metadata(
            document=document,
            page_number=3,
        )

        self.assertEqual(
            metadata.to_payload(),
            {
                "google_file_id": "file-1",
                "source_name": "Spec.pdf",
                "source_location": "/drive/Specs/Spec.pdf",
                "source_url": "https://drive.google.com/file/d/file-1",
                "google_drive_version": "7",
                "google_drive_modified_time": "2026-05-24T00:00:00Z",
                "page_number": 3,
            },
        )


if __name__ == "__main__":
    unittest.main()
