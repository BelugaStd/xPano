import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.dependency_checks import (
    check_executable,
    check_pipeline_dependencies,
    format_dependency_report,
    locate_colmap,
    locate_lichtfield,
    require_dependency_checks,
    resolve_executable,
)


class DependencyChecksTests(unittest.TestCase):
    def test_resolves_explicit_executable_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "tool.exe"
            exe.write_bytes(b"")

            self.assertEqual(resolve_executable(str(exe), "tool.exe"), str(exe))

    def test_locates_colmap_from_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "colmap.exe"
            exe.write_bytes(b"")

            with patch.dict("scripts.dependency_checks.os.environ", {"XPANO_COLMAP": str(exe)}, clear=False):
                self.assertEqual(locate_colmap(), str(exe))

    def test_locates_lichtfield_from_path(self):
        with patch("scripts.dependency_checks.shutil.which", return_value=r"C:\Tools\lichtfield-studio.exe"):
            self.assertEqual(locate_lichtfield(), r"C:\Tools\lichtfield-studio.exe")

    def test_reports_missing_required_executable(self):
        with patch("scripts.dependency_checks.shutil.which", return_value=None):
            check = check_executable("COLMAP", "colmap", "colmap", required=True)

        self.assertFalse(check.ok)
        self.assertTrue(check.required)
        self.assertIn("PATH", check.message)

    def test_skips_optional_executable(self):
        check = check_executable("Metashape", "metashape.exe", "metashape.exe", required=False)

        self.assertTrue(check.ok)
        self.assertFalse(check.required)

    def test_colmap_lichtfield_dependency_requirements(self):
        def fake_which(command):
            return f"C:/Tools/{command}.exe"

        with patch("scripts.dependency_checks.shutil.which", side_effect=fake_which):
            checks = check_pipeline_dependencies(
                backend="colmap",
                metashape_exe="missing-metashape.exe",
                colmap_exe="colmap",
                lichtfield_exe="lichtfield-studio",
                run_lichtfield=True,
            )

        by_name = {check.name: check for check in checks}
        self.assertFalse(by_name["Metashape"].required)
        self.assertTrue(by_name["COLMAP"].required)
        self.assertTrue(by_name["LICHT Field Studio"].required)
        require_dependency_checks(checks)

    def test_formats_failure_report(self):
        with patch("scripts.dependency_checks.shutil.which", return_value=None):
            checks = check_pipeline_dependencies(backend="metashape", metashape_exe="metashape.exe")

        report = format_dependency_report(checks)
        self.assertIn("MISSING", report)
        self.assertIn("ffmpeg", report)


if __name__ == "__main__":
    unittest.main()
