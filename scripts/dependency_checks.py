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


def _project_root():
    return Path(__file__).resolve().parents[1]


def _bundled_colmap_candidates(project_root=None):
    root = Path(project_root) if project_root else _project_root()
    base_dirs = [
        root / "tools" / "colmap",
        root / "third_party" / "colmap",
    ]
    candidates = []
    for base in base_dirs:
        candidates.extend(
            [
                base / "COLMAP.bat",
                base / "colmap.bat",
                base / "colmap.exe",
                base / "bin" / "colmap.exe",
            ]
        )
        if base.exists():
            for child in sorted(path for path in base.iterdir() if path.is_dir()):
                candidates.extend(
                    [
                        child / "COLMAP.bat",
                        child / "colmap.bat",
                        child / "colmap.exe",
                        child / "bin" / "colmap.exe",
                    ]
                )
    return candidates


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


def locate_colmap(project_root=None):
    explicit = os.environ.get("XPANO_COLMAP")
    if explicit and Path(explicit).exists():
        return explicit
    bundled = _first_existing(_bundled_colmap_candidates(project_root=project_root))
    if bundled:
        return bundled
    return locate_executable(
        "colmap",
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
    if default_name.lower().startswith("colmap") and executable.lower() in {"colmap", "colmap.exe", "colmap.bat"}:
        bundled = _first_existing(_bundled_colmap_candidates())
        if bundled:
            return bundled
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
