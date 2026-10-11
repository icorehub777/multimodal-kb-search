import os
from pathlib import Path
import tempfile
import unittest

from kbsearch_cli.errors import QueryInputError
from kbsearch_cli.paths import require_scoped_path


def _short_path(path):
    if os.name != "nt":
        return path
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = kernel.GetShortPathNameW
    function.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    function.restype = wintypes.DWORD
    size = function(str(path), None, 0)
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(size)
    if not function(str(path), buffer, size):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value)


class ScopedPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.root = self.workspace / "task workspace"
        self.root.mkdir()

    def test_short_path_for_existing_file_is_accepted(self):
        target = self.root / "document.txt"
        target.write_text("test", encoding="utf-8")
        self.assertEqual(require_scoped_path(_short_path(target), self.root), target)

    def test_short_path_for_missing_output_is_accepted_without_creating_it(self):
        target = self.root / "new" / "pages" / "0001.png"
        path = _short_path(self.root) / "new" / "pages" / "0001.png"
        self.assertEqual(require_scoped_path(path, self.root), target)
        self.assertFalse(target.parent.exists())

    def test_short_boundary_is_accepted(self):
        target = self.root / "document.txt"
        target.touch()
        self.assertEqual(require_scoped_path(target, _short_path(self.root)), target)

    def test_external_path_is_rejected(self):
        target = self.workspace / "private.txt"
        target.touch()
        with self.assertRaises(QueryInputError):
            require_scoped_path(_short_path(target), self.root)

    def test_short_paths_do_not_allow_directory_redirection(self):
        for location in (self.root / "inside", self.workspace / "outside"):
            with self.subTest(location=location):
                location.mkdir()
                link = self.root / "linked"
                if os.name == "nt":
                    import _winapi
                    _winapi.CreateJunction(str(location), str(link))
                else:
                    link.symlink_to(location, target_is_directory=True)
                try:
                    with self.assertRaises(QueryInputError):
                        require_scoped_path(_short_path(link) / "new.txt", self.root)
                finally:
                    if os.name == "nt":
                        link.rmdir()
                    else:
                        link.unlink()
