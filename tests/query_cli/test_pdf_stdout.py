import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas


class PdfStdoutTests(unittest.TestCase):
    def run_pdf_process(self, body):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            internal = workspace / "_internal"
            internal.mkdir()
            document = workspace / "tasks/task/query_results/query/document"
            (document / "pdf").mkdir(parents=True)
            pdf = canvas.Canvas(str(document / "pdf/document.pdf"))
            pdf.drawString(40, 40, "Searchable PDF")
            pdf.save()
            script = """
import builtins
import json
from pathlib import Path
original_import = builtins.__import__
def checked_import(name, *args, **kwargs):
    if name == 'fitz':
        print('warning: legacy fitz import')
    return original_import(name, *args, **kwargs)
builtins.__import__ = checked_import
""" + body
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(sys.path)
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=internal,
                env=environment, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_render_command_stdout_is_only_json_on_first_pdf_import(self):
        result = self.run_pdf_process("""
from kbsearch_cli.__main__ import main
raise SystemExit(main(['render-pdf-pages', '--task-name', 'task',
    '--query-name', 'query', '--document-name', 'document', '--pages', '1']))
""")
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["pages"], [1])

    def test_query_pdf_processing_does_not_contaminate_stdout(self):
        result = self.run_pdf_process("""
from kbsearch_cli.rendering import DocumentPageRenderer
document = Path('../tasks/task/query_results/query/document').resolve()
result = DocumentPageRenderer().process(document / 'pdf/document.pdf',
    'application/pdf', document / 'processed', [1])
print(json.dumps({'text_count': len(result.text_paths), 'page_count': len(result.page_paths)}))
""")
        self.assertEqual(result, {"text_count": 1, "page_count": 1})
