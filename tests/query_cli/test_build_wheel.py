import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "build_scripts" / "build_wheel_query_cli.ps1"
NEW_WHEEL = "kbsearch_cli-0.1.0-py3-none-any.whl"
OLD_WHEEL = "kbsearch_cli-0.0.1-py3-none-any.whl"


class WheelBuildTests(unittest.TestCase):
    def _run_build(self, mode):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve() / "repo with spaces"
        script = root / "build_scripts" / BUILD_SCRIPT.name
        script.parent.mkdir(parents=True)
        shutil.copy2(BUILD_SCRIPT, script)
        (root / "query_cli").mkdir()
        packages = root / "agent_runtime" / "_internal" / "packages"
        packages.mkdir(parents=True)
        (packages / OLD_WHEEL).write_bytes(b"existing delivery")
        (packages / NEW_WHEEL).write_bytes(b"previous same version")
        (packages / "other_package-1.0-py3-none-any.whl").write_bytes(b"unrelated")
        (packages / ".gitkeep").touch()
        elsewhere = root / "another working directory"
        elsewhere.mkdir()
        environment = os.environ.copy()
        environment["WHEEL_TEST_MODE"] = mode
        environment["WHEEL_TEST_PROJECT"] = str(root / "query_cli")
        environment["WHEEL_TEST_SCRIPT"] = str(script)
        command = r'''
function global:python {
    if ($args[0] -ne '-m' -or $args[1] -ne 'build' -or
        $args[2] -ne $env:WHEEL_TEST_PROJECT -or $args[3] -ne '--wheel' -or
        $args[4] -ne '--outdir') { throw 'Unexpected build invocation.' }
    $destination = $args[5]
    if ($env:WHEEL_TEST_MODE -ne 'missing') {
        [IO.File]::WriteAllText((Join-Path $destination 'kbsearch_cli-0.1.0-py3-none-any.whl'), 'new delivery')
    }
    if ($env:WHEEL_TEST_MODE -eq 'multiple') {
        [IO.File]::WriteAllText((Join-Path $destination 'kbsearch_cli-0.2.0-py3-none-any.whl'), 'extra delivery')
    }
    $global:LASTEXITCODE = 0
    if ($env:WHEEL_TEST_MODE -eq 'failure') { $global:LASTEXITCODE = 7 }
}
& $env:WHEEL_TEST_SCRIPT
'''
        shell = shutil.which("pwsh") or shutil.which("powershell")
        self.assertIsNotNone(shell, "PowerShell is required for Windows CLI build tests.")
        result = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=elsewhere, env=environment, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(list(packages.glob(".wheel-build-*")), [])
        self.assertEqual((packages / "other_package-1.0-py3-none-any.whl").read_bytes(), b"unrelated")
        self.assertTrue((packages / ".gitkeep").is_file())
        self.assertFalse((root / "agent_runtime" / "_internal" / ".venv").exists())
        return result, packages

    def test_success_publishes_one_cli_wheel_without_installing(self):
        result, packages = self._run_build("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((packages / NEW_WHEEL).read_bytes(), b"new delivery")
        self.assertFalse((packages / OLD_WHEEL).exists())

    def test_failed_build_preserves_existing_wheels(self):
        result, packages = self._run_build("failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("query_cli wheel build failed (exit code 7)", result.stderr)
        self.assertEqual((packages / OLD_WHEEL).read_bytes(), b"existing delivery")
        self.assertEqual((packages / NEW_WHEEL).read_bytes(), b"previous same version")

    def test_missing_wheel_preserves_existing_delivery(self):
        result, packages = self._run_build("missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly one kbsearch_cli wheel", result.stderr)
        self.assertEqual((packages / OLD_WHEEL).read_bytes(), b"existing delivery")
        self.assertEqual((packages / NEW_WHEEL).read_bytes(), b"previous same version")

    def test_ambiguous_wheels_preserve_existing_delivery(self):
        result, packages = self._run_build("multiple")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly one kbsearch_cli wheel", result.stderr)
        self.assertEqual((packages / OLD_WHEEL).read_bytes(), b"existing delivery")
        self.assertEqual((packages / NEW_WHEEL).read_bytes(), b"previous same version")


if __name__ == "__main__":
    unittest.main()
