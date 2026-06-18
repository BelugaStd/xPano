import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.dependency_checks import (
    ExecutableCheck,
    check_executable,
    check_lfs_densify_imports,
    check_lfs_densify_runner,
    check_pipeline_dependencies,
    format_dependency_report,
    locate_colmap,
    locate_ffmpeg,
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

    def test_locates_bundled_colmap_before_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundled = root / "tools" / "colmap" / "COLMAP.bat"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("@echo off\n", encoding="utf-8")

            with patch("scripts.dependency_checks.shutil.which", return_value=r"C:\Tools\colmap.exe"):
                self.assertEqual(locate_colmap(project_root=root), str(bundled))

    def test_locates_nested_bundled_colmap_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundled = root / "tools" / "colmap" / "colmap-x64-windows-nocuda" / "bin" / "colmap.exe"
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"")

            with patch("scripts.dependency_checks.shutil.which", return_value=None):
                self.assertEqual(locate_colmap(project_root=root), str(bundled))

    def test_locates_bundled_ffmpeg_before_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundled = root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"")

            with patch("scripts.runtime_paths.shutil.which", return_value=r"C:\Tools\ffmpeg.exe"):
                self.assertEqual(locate_ffmpeg(root=root), str(bundled))

    def test_locates_lichtfield_from_path(self):
        with patch("scripts.dependency_checks.shutil.which", return_value=r"C:\Tools\lichtfield-studio.exe"):
            self.assertEqual(locate_lichtfield(), r"C:\Tools\lichtfield-studio.exe")

    def test_reports_missing_required_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.dependency_checks._project_root", return_value=Path(tmp)), \
                patch("scripts.dependency_checks.shutil.which", return_value=None):
                check = check_executable("COLMAP", "colmap", "colmap", required=True)

        self.assertFalse(check.ok)
        self.assertTrue(check.required)
        self.assertIn("PATH", check.message)

    def test_resolve_colmap_command_can_use_bundled_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundled = root / "tools" / "colmap" / "COLMAP.bat"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("@echo off\n", encoding="utf-8")

            with patch("scripts.dependency_checks._project_root", return_value=root), \
                patch("scripts.dependency_checks.shutil.which", return_value=None):
                self.assertEqual(resolve_executable("colmap", "colmap"), str(bundled))

    def test_skips_optional_executable(self):
        check = check_executable("Metashape", "metashape.exe", "metashape.exe", required=False)

        self.assertTrue(check.ok)
        self.assertFalse(check.required)

    def test_colmap_lichtfield_dependency_requirements(self):
        def fake_which(command):
            suffix = "" if str(command).lower().endswith(".exe") else ".exe"
            return f"C:/Tools/{command}{suffix}"

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

    def test_lfs_densification_checks_python_and_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            python_exe = root / "python.exe"
            plugin.mkdir()
            (plugin / "densify.py").write_text("print('ok')", encoding="utf-8")
            python_exe.write_bytes(b"")

            with patch("scripts.dependency_checks.shutil.which", return_value="C:/Tools/tool.exe"), \
                patch("scripts.dependency_checks.check_lfs_densify_imports") as import_check:
                import_check.return_value = ExecutableCheck(
                    name="LichtFeld densification dependencies",
                    requested=str(python_exe),
                    required=True,
                    ok=True,
                    resolved=str(python_exe),
                )
                with patch("scripts.dependency_checks.check_lfs_densify_runner") as runner_check:
                    runner_check.return_value = ExecutableCheck(
                        name="LichtFeld densification runner",
                        requested=str(plugin),
                        required=True,
                        ok=True,
                        resolved=str(plugin),
                    )
                    checks = check_pipeline_dependencies(
                        backend="colmap",
                        colmap_exe="colmap",
                        run_lfs_densify=True,
                        lfs_densify_python=str(python_exe),
                        lfs_densify_plugin=str(plugin),
                    )

        by_name = {check.name: check for check in checks}
        self.assertTrue(by_name["LichtFeld densification plugin"].ok)
        self.assertTrue(by_name["LichtFeld densification Python"].ok)
        self.assertTrue(by_name["LichtFeld densification dependencies"].ok)
        self.assertTrue(by_name["LichtFeld densification runner"].ok)

    def test_lfs_import_check_reports_missing_dependency(self):
        result = type("Result", (), {"returncode": 1, "stdout": "", "stderr": "No module named pycolmap"})()

        with patch("scripts.dependency_checks.subprocess.run", return_value=result):
            check = check_lfs_densify_imports("python.exe")

        self.assertFalse(check.ok)
        self.assertIn("pycolmap", check.message)

    def test_lfs_runner_check_requires_plugin_cli_help(self):
        result = type("Result", (), {"returncode": 0, "stdout": "--scene_root\n--roma_setting\n", "stderr": ""})()

        with patch("scripts.dependency_checks.subprocess.run", return_value=result):
            check = check_lfs_densify_runner("python.exe", Path("plugin"))

        self.assertTrue(check.ok)

    def test_formats_failure_report(self):
        with patch("scripts.dependency_checks.shutil.which", return_value=None):
            checks = check_pipeline_dependencies(backend="metashape", metashape_exe="metashape.exe")

        report = format_dependency_report(checks)
        self.assertIn("MISSING", report)
        self.assertIn("ffmpeg", report)


if __name__ == "__main__":
    unittest.main()
