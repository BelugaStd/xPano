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
