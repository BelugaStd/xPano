import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from scripts.pipeline_backends import COLMAP_BACKEND, METASHAPE_BACKEND, normalize_backend


@dataclass(frozen=True)
class ExecutableCheck:
    name: str
    requested: str
    required: bool
    ok: bool
    resolved: str = ""
    message: str = ""


def _first_existing(paths):
    for path in paths:
        path = Path(path)
        if path.exists():
            return str(path)
    return ""


def locate_executable(default_name, env_var=None, path_names=None, candidate_paths=None):
    if env_var:
        explicit = os.environ.get(env_var)
        if explicit and Path(explicit).exists():
            return explicit
    for name in path_names or [default_name]:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    found = _first_existing(candidate_paths or [])
    return found or default_name


def locate_colmap():
    return locate_executable(
        "colmap",
        env_var="XPANO_COLMAP",
        path_names=["colmap.exe", "colmap", "COLMAP.bat"],
        candidate_paths=[
            r"C:\Program Files\COLMAP\colmap.exe",
            r"C:\Program Files\COLMAP\COLMAP.bat",
            r"C:\Program Files (x86)\COLMAP\colmap.exe",
            r"D:\Program Files\COLMAP\colmap.exe",
            r"E:\FastProgram\COLMAP\colmap.exe",
        ],
    )


def locate_lichtfield():
    return locate_executable(
        "lichtfield-studio",
        env_var="XPANO_LICHTFIELD",
        path_names=[
            "lichtfield-studio.exe",
            "lichtfield-studio",
            "LICHT Field Studio.exe",
            "LICHT.exe",
        ],
        candidate_paths=[
            r"C:\Program Files\LICHT Field Studio\lichtfield-studio.exe",
            r"C:\Program Files\LICHT Field Studio\LICHT Field Studio.exe",
            r"C:\Program Files\LICHT\lichtfield-studio.exe",
            r"D:\Program Files\LICHT Field Studio\lichtfield-studio.exe",
            r"E:\FastProgram\LICHT Field Studio\lichtfield-studio.exe",
        ],
    )


def resolve_executable(executable, default_name):
    executable = (executable or "").strip() or default_name
    if Path(executable).is_absolute() or any(sep in executable for sep in ["\\", "/"]):
        if not Path(executable).exists():
            raise FileNotFoundError(executable)
        return str(Path(executable))
    resolved = shutil.which(executable)
    if not resolved:
        raise RuntimeError(f"{executable} was not found in PATH")
    return resolved


def check_executable(name, executable, default_name, required=True):
    requested = (executable or "").strip() or default_name
    if not required:
        return ExecutableCheck(name=name, requested=requested, required=False, ok=True, message="Not required")
    try:
        resolved = resolve_executable(requested, default_name)
        return ExecutableCheck(name=name, requested=requested, required=True, ok=True, resolved=resolved)
    except Exception as exc:
        return ExecutableCheck(name=name, requested=requested, required=True, ok=False, message=str(exc))


def check_pipeline_dependencies(
    backend,
    metashape_exe="metashape.exe",
    colmap_exe="colmap",
    lichtfield_exe="lichtfield-studio",
    run_lichtfield=False,
):
    backend = normalize_backend(backend)
    checks = [
        check_executable("ffmpeg", "ffmpeg", "ffmpeg", required=True),
        check_executable("Metashape", metashape_exe, "metashape.exe", required=backend == METASHAPE_BACKEND),
        check_executable("COLMAP", colmap_exe, "colmap", required=backend == COLMAP_BACKEND),
        check_executable(
            "LICHT Field Studio",
            lichtfield_exe,
            "lichtfield-studio",
            required=backend == COLMAP_BACKEND and run_lichtfield,
        ),
    ]
    return checks


def format_dependency_report(checks):
    lines = []
    for check in checks:
        if not check.required:
            status = "SKIP"
            detail = check.message
        elif check.ok:
            status = "OK"
            detail = check.resolved
        else:
            status = "MISSING"
            detail = check.message
        lines.append(f"{status}: {check.name} ({check.requested}) {detail}".rstrip())
    return "\n".join(lines)


def require_dependency_checks(checks):
    failures = [check for check in checks if check.required and not check.ok]
    if failures:
        raise RuntimeError(format_dependency_report(failures))
    return checks
