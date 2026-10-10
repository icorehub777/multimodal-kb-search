import unittest
from unittest.mock import patch

from kbsearch_cli.viewer_launcher import (
    _is_kbsearch_viewer_command,
    build_task_query_url_example,
    build_viewer_url,
    restart_existing_viewer_on_port,
)


class ViewerLauncherTests(unittest.TestCase):
    def test_build_viewer_url_includes_selected_task_and_query(self):
        self.assertEqual(
            build_viewer_url(
                host="127.0.0.1",
                port=8501,
                task_name="task 1",
                query_name="query/alpha",
            ),
            "http://127.0.0.1:8501/?task=task+1&query=query%2Falpha",
        )

    def test_build_viewer_url_uses_loopback_for_wildcard_host(self):
        self.assertEqual(
            build_viewer_url(host="0.0.0.0", port=8502),
            "http://127.0.0.1:8502/",
        )

    def test_build_task_query_url_example_uses_readable_placeholders(self):
        self.assertEqual(
            build_task_query_url_example(host="127.0.0.1", port=8501),
            "http://127.0.0.1:8501/?task=<task-name>&query=<query-name>",
        )

    def test_is_kbsearch_viewer_command_accepts_cli_and_streamlit_processes(self):
        self.assertTrue(
            _is_kbsearch_viewer_command(
                r"C:\Python\python.exe -m kbsearch_cli.__main__ view-results"
            )
        )
        self.assertTrue(
            _is_kbsearch_viewer_command(
                r"C:\Python\python.exe C:\runtime\.venv\Scripts\kbsearch.exe view-results"
            )
        )
        self.assertTrue(
            _is_kbsearch_viewer_command(
                r"streamlit run C:\repo\query_cli\src\kbsearch_cli\viewer_app.py"
            )
        )
        self.assertFalse(_is_kbsearch_viewer_command("python -m http.server 8501"))

    def test_restart_existing_viewer_on_port_stops_kbsearch_viewer(self):
        with patch(
            "kbsearch_cli.viewer_launcher._find_listening_pids",
            side_effect=[[1234], []],
        ), patch(
            "kbsearch_cli.viewer_launcher._get_process_command_line",
            return_value=r"C:\Python\python.exe -m kbsearch_cli.__main__ view-results",
        ), patch(
            "kbsearch_cli.viewer_launcher._terminate_process_tree"
        ) as terminate:
            restarted = restart_existing_viewer_on_port(8501)

        self.assertEqual(restarted, 1)
        terminate.assert_called_once_with(1234)

    def test_restart_existing_viewer_on_port_rejects_non_viewer_process(self):
        with patch(
            "kbsearch_cli.viewer_launcher._find_listening_pids",
            return_value=[1234],
        ), patch(
            "kbsearch_cli.viewer_launcher._get_process_command_line",
            return_value="python -m http.server 8501",
        ), patch("kbsearch_cli.viewer_launcher._terminate_process_tree") as terminate:
            with self.assertRaisesRegex(RuntimeError, "KBSEARCH_VIEWER_PORT"):
                restart_existing_viewer_on_port(8501)

        terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
