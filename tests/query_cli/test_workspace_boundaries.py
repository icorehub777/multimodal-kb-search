import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kbsearch_cli.errors import QueryInputError
from kbsearch_cli.output import resolve_query_output_directory
from kbsearch_cli.viewer_app import (
    discover_query_results, find_condition_images, find_page_image,
    read_json, resolve_recorded_path, viewer_tasks_dir,
)


class WorkspaceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.internal = self.workspace / '_internal'
        self.internal.mkdir()
        self.tasks = self.workspace / 'tasks'
        self.query = self.tasks / 'task' / 'query_results' / 'query'
        self.document = self.query / 'document'
        (self.document / 'pdf').mkdir(parents=True)
        self.pdf = self.document / 'pdf' / 'document.pdf'
        self.pdf.write_bytes(b'pdf')

    def redirected(self, source, target):
        original = Path.resolve
        return patch.object(Path, 'resolve', autospec=True,
                            side_effect=lambda path: target if path == source else original(path))

    def test_query_rejects_result_redirect_to_another_task(self):
        output = self.tasks / 'task' / 'query_results' / 'new'
        with self.redirected(output, self.tasks / 'other' / 'query_results' / 'new'):
            with self.assertRaises(QueryInputError):
                resolve_query_output_directory(self.tasks, 'task', 'new')

    def test_task_root_cannot_redirect_to_internal_config(self):
        from kbsearch_cli.config import resolve_workspace_tasks_root
        from kbsearch_cli.errors import ConfigError
        with patch('pathlib.Path.cwd', return_value=self.internal), self.redirected(self.tasks, self.internal / 'config'):
            with self.assertRaises(ConfigError):
                resolve_workspace_tasks_root()

    def test_real_directory_link_is_rejected_without_reading_external_files(self):
        outside = self.workspace / 'outside'
        (outside / 'query_results' / 'private').mkdir(parents=True)
        link = self.tasks / 'linked-task'
        try:
            if os.name == 'nt':
                import _winapi
                _winapi.CreateJunction(str(outside), str(link))
            else:
                link.symlink_to(outside, target_is_directory=True)
        except PermissionError:
            self.skipTest('Directory link creation is not permitted in this environment')
        with self.assertRaises(QueryInputError):
            discover_query_results(self.tasks)
        self.assertTrue((outside / 'query_results' / 'private').is_dir())

    def test_render_resolves_fixed_document_locations_without_creating_pages(self):
        from kbsearch_cli.output import resolve_render_paths
        pdf, pages = resolve_render_paths(self.tasks, 'task', 'query', 'document')
        self.assertEqual(pdf, self.pdf)
        self.assertEqual(pages, self.document / 'pages')
        self.assertFalse(pages.exists())

    def test_render_rejects_names_and_redirected_pdf_or_output(self):
        from kbsearch_cli.output import resolve_render_paths
        for name in ('../outside', 'nested/doc', 'C:\\outside', 'NUL'):
            with self.subTest(name=name), self.assertRaises(QueryInputError):
                resolve_render_paths(self.tasks, 'task', 'query', name)
        for source in (self.pdf, self.document / 'pages'):
            with self.subTest(source=source), self.redirected(source, self.workspace / 'outside'):
                with self.assertRaises(QueryInputError):
                    resolve_render_paths(self.tasks, 'task', 'query', 'document')

    def test_render_rejects_png_redirect_before_writing(self):
        from kbsearch_cli.rendering import DocumentPageRenderer
        pages = self.document / 'pages'
        target = pages / '0001.png'
        with self.redirected(target, self.workspace / 'outside.png'):
            with self.assertRaises(QueryInputError):
                DocumentPageRenderer().render_pdf_pages(self.pdf, pages, [1])
        self.assertFalse(pages.exists())

    def test_viewer_ignores_tasks_override(self):
        with patch('pathlib.Path.cwd', return_value=self.internal), patch.dict(
            os.environ, {'KBSEARCH_VIEWER_TASKS_DIR': str(self.workspace / 'outside')}
        ):
            self.assertEqual(viewer_tasks_dir(), self.tasks)

    def test_viewer_rejects_redirected_query_directory(self):
        with self.redirected(self.query, self.workspace / 'outside'):
            with self.assertRaises(QueryInputError):
                discover_query_results(self.tasks)

    def test_viewer_rejects_external_and_other_query_recorded_paths(self):
        for file in (self.workspace / 'outside.png', self.tasks / 'other' / 'file.png'):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'image')
            with self.subTest(file=file), self.assertRaises(QueryInputError):
                resolve_recorded_path(self.query, str(file))

    def test_viewer_resolves_relative_path_only_from_query(self):
        self.assertEqual(resolve_recorded_path(self.query, 'document/pdf/document.pdf'), self.pdf)

    def test_viewer_rejects_json_link_without_reading_target(self):
        path = self.query / 'query_plan.json'
        with self.redirected(path, self.workspace / 'outside.json'), patch.object(Path, 'read_text') as read:
            state = read_json(path, {}, boundary=self.query)
        self.assertFalse(state.ok)
        self.assertIn('boundary', state.error)
        read.assert_not_called()

    def test_viewer_checks_image_boundary_at_read(self):
        from kbsearch_cli.viewer_app import image_to_data_uri
        outside = self.workspace / 'outside.png'
        with patch.object(Path, 'read_bytes') as read, self.assertRaises(QueryInputError):
            image_to_data_uri(outside, boundary=self.query)
        read.assert_not_called()

    def test_viewer_rejects_traversal_relative_paths(self):
        for path in ('../../outside.png', '../other/pages/0001.png', 'C:/outside.png'):
            with self.subTest(path=path), self.assertRaises(QueryInputError):
                resolve_recorded_path(self.query, path)

    def test_viewer_does_not_guess_condition_images_from_query_directory(self):
        (self.query / 'photo.png').write_bytes(b'image')
        self.assertEqual(find_condition_images(self.query, {'image_paths': ['photo.png']}), [])

    def test_viewer_requires_documents_to_be_direct_query_children(self):
        from kbsearch_cli.viewer_app import find_document_dir
        mapping = {'file-1': {'directory': str(self.document / 'pdf')}}
        with self.assertRaises(QueryInputError):
            find_document_dir(self.query, {'google_file_id': 'file-1'}, mapping)

    def test_viewer_condition_images_stay_in_task(self):
        photo = self.tasks / 'task' / 'photo.png'
        photo.write_bytes(b'image')
        self.assertEqual(find_condition_images(self.query, {'image_paths': [str(photo)]}), [photo])
        outside = self.workspace / 'outside.png'
        outside.write_bytes(b'image')
        with self.assertRaises(QueryInputError):
            find_condition_images(self.query, {'image_paths': [str(outside)]})

    def test_viewer_page_paths_stay_in_mapped_document_pages(self):
        other = self.query / 'other' / 'pages' / '0001.png'
        other.parent.mkdir(parents=True)
        other.write_bytes(b'image')
        mapping = {'file-1': {'directory': str(self.document), 'page_paths': [str(other)]}}
        with self.assertRaises(QueryInputError):
            find_page_image(self.query, {'google_file_id': 'file-1'}, 1, mapping)

    def test_login_and_viewer_load_only_their_settings(self):
        from kbsearch_cli.config import load_login_config, load_viewer_config
        with patch('pathlib.Path.cwd', return_value=self.internal), patch.dict(os.environ, {
            'GOOGLE_OAUTH_CLIENT_CONFIG': 'config/oauth_client.json',
            'KBSEARCH_VIEWER_PORT': '8502',
        }, clear=True):
            self.assertEqual(load_login_config().google_oauth_client_config,
                             self.internal / 'config' / 'oauth_client.json')
            self.assertEqual(load_viewer_config().viewer_port, 8502)

    def test_viewer_works_without_credentials_or_query_settings(self):
        from kbsearch_cli.config import load_viewer_config
        with patch('pathlib.Path.cwd', return_value=self.internal), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_viewer_config().viewer_port, 8501)

    def test_query_does_not_require_login_or_viewer_settings(self):
        from kbsearch_cli.config import load_query_cli_config
        with patch('pathlib.Path.cwd', return_value=self.internal), patch.dict(os.environ, {
            'KBSEARCH_SECURE_BACKEND_BASE_URL': 'http://localhost:8000',
            'KBSEARCH_SECURE_BACKEND_API_KEY': 'test-key',
            'KBSEARCH_CJK_FONT_PATH': 'C:/Windows/Fonts/msjh.ttc',
            'KBSEARCH_VIEWER_PORT': 'not-a-port',
        }, clear=True):
            self.assertEqual(load_query_cli_config().tasks_root, self.tasks)
