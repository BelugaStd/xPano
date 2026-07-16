from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.runtime_bootstrap import (
    BootstrapError,
    bootstrap_local_runtime,
    install_verified_wheels,
)
from scripts.metashape_runtime_env import build_metashape_process_env, metashape_runtime_cli_args


class RuntimeReadinessError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise RuntimeReadinessError(code, message)


def _wheel_supports_abi(filename, target_abi):
    try:
        _prefix, python_tag, abi_tag, platform_tag = filename[:-4].rsplit("-", 3)
    except ValueError:
        return False
    if platform_tag == "any" and abi_tag == "none":
        return True
    python_tags = python_tag.split(".")
    if target_abi in python_tags and abi_tag in {target_abi, "abi3"}:
        return True
    if abi_tag == "abi3":
        target_version = int(target_abi[2:])
        return any(
            tag.startswith("cp") and tag[2:].isdigit() and int(tag[2:]) <= target_version
            for tag in python_tags
        )
    return False


def load_bundled_runtime_manifest(path, resource_root):
    path = Path(path)
    resource_root = Path(resource_root).resolve()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail("MANIFEST_INVALID", f"Failed to read bundled runtime manifest: {exc}")
    if manifest.get("schemaVersion") != 1:
        _fail("MANIFEST_INVALID", "Unsupported bundled runtime manifest schema")
    if manifest.get("platform") != "windows-x86_64":
        _fail("UNSUPPORTED_PLATFORM", "Bundled runtime manifest is not for Windows x64")
    if not isinstance(manifest.get("runtimeVersion"), str) or not manifest["runtimeVersion"]:
        _fail("MANIFEST_INVALID", "Bundled runtime version is missing")
    metashape = manifest.get("metashape")
    profiles = metashape.get("profiles") if isinstance(metashape, dict) else None
    artifacts = metashape.get("artifacts") if isinstance(metashape, dict) else None
    if not isinstance(profiles, dict) or not profiles:
        _fail("MANIFEST_INVALID", "Metashape profiles are missing")
    if not isinstance(artifacts, list) or not artifacts:
        _fail("MANIFEST_INVALID", "Metashape artifacts are missing")
    by_id = {}
    for item in artifacts:
        if not isinstance(item, dict):
            _fail("MANIFEST_INVALID", "Metashape artifact must be an object")
        artifact_id = item.get("id")
        filename = item.get("filename")
        relative = item.get("path")
        digest = str(item.get("sha256", "")).lower()
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in by_id:
            _fail("MANIFEST_INVALID", "Metashape artifact ids must be unique")
        if not isinstance(filename, str) or not filename.endswith(".whl"):
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} is not a wheel")
        if not (filename.endswith("-win_amd64.whl") or filename.endswith("-any.whl")):
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} is not Windows x64 compatible")
        relative_path = Path(relative) if isinstance(relative, str) else Path()
        if not relative or relative_path.is_absolute() or ".." in relative_path.parts:
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} path is invalid")
        source = (resource_root / relative_path).resolve()
        try:
            source.relative_to(resource_root)
        except ValueError:
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} escapes resources")
        if not isinstance(item.get("size"), int) or item["size"] <= 0:
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} size is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} SHA-256 is invalid")
        if not isinstance(item.get("license"), str) or not item["license"].strip():
            _fail("MANIFEST_INVALID", f"Metashape artifact {artifact_id} license is missing")
        normalized = dict(item)
        normalized["sha256"] = digest
        normalized["source"] = source
        by_id[artifact_id] = normalized
    for abi, ids in profiles.items():
        if not re.fullmatch(r"cp\d{2,3}", str(abi)):
            _fail("MANIFEST_INVALID", f"Invalid Metashape ABI profile: {abi}")
        if not isinstance(ids, list) or not ids or not all(item in by_id for item in ids):
            _fail("MANIFEST_INVALID", f"Metashape ABI profile {abi} references invalid artifacts")
        incompatible = [by_id[item]["filename"] for item in ids if not _wheel_supports_abi(by_id[item]["filename"], abi)]
        if incompatible:
            _fail(
                "MANIFEST_INVALID",
                f"Metashape ABI profile {abi} contains incompatible wheels: {', '.join(incompatible)}",
            )
    manifest["_metashapeArtifactsById"] = by_id
    manifest["_resourceRoot"] = resource_root
    return manifest


def metashape_profile(manifest, abi):
    profiles = manifest["metashape"]["profiles"]
    if abi not in profiles:
        raise RuntimeReadinessError(
            "UNSUPPORTED_ABI",
            f"Metashape Python {abi} is unsupported; supported ABIs: {', '.join(sorted(profiles))}",
        )
    by_id = manifest["_metashapeArtifactsById"]
    return [by_id[item] for item in profiles[abi]]


def _run_python(python, code):
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(python), "-c", code],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _probe_tool(executable, arguments, expected_marker):
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    try:
        completed = subprocess.run(
            [str(executable), *arguments],
            cwd=str(Path(executable).resolve().parent),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    if completed.returncode != 0:
        return False, output or f"process exited with code {completed.returncode}"
    if expected_marker.casefold() not in output.casefold():
        return False, output or f"expected marker was not found: {expected_marker}"
    return True, output


def _missing_media_foundation_dlls():
    if os.name != "nt":
        return []
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    return [name for name in ("MFPlat.dll", "MF.dll", "MFReadWrite.dll") if not (system32 / name).is_file()]


def metashape_python(metashape_exe):
    requested = str(metashape_exe).strip()
    if len(requested) >= 2 and requested.startswith('"') and requested.endswith('"'):
        requested = requested[1:-1].strip()
    resolved = shutil.which(requested) if requested and Path(requested).name == requested else None
    metashape_exe = Path(resolved or requested).resolve()
    if not metashape_exe.is_file():
        raise RuntimeReadinessError("METASHAPE_MISSING", f"Metashape executable was not found: {metashape_exe}")
    python = metashape_exe.parent / "python" / "python.exe"
    if not python.is_file():
        raise RuntimeReadinessError("METASHAPE_PYTHON_MISSING", f"Metashape Python was not found: {python}")
    return metashape_exe, python


def python_abi(python):
    completed = _run_python(python, "import sys; print(f'cp{sys.version_info[0]}{sys.version_info[1]}')")
    value = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"cp\d{2,3}", value):
        raise RuntimeReadinessError(
            "ABI_PROBE_FAILED",
            (completed.stderr or completed.stdout or "Failed to detect Metashape Python ABI").strip(),
        )
    return value


def _probe_metashape_runtime(metashape_exe, resource_root, site_packages=None):
    probe_script = Path(resource_root) / "scripts" / "metashape_runtime_probe.py"
    command = [str(metashape_exe), "-r", str(probe_script)]
    command.extend(metashape_runtime_cli_args(site_packages))
    try:
        completed = subprocess.run(
            command,
            env=build_metashape_process_env(resource_root, site_packages),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Unable to start Metashape runtime probe: {exc}"
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    return completed.returncode == 0 and "XPANO_METASHAPE_RUNTIME_READY:" in completed.stdout, output


def probe_metashape_runtime(metashape_exe, resource_root, site_packages=None):
    ready, _detail = _probe_metashape_runtime(metashape_exe, resource_root, site_packages)
    return ready


def _metashape_runtime_id(metashape_exe, python, abi, bundle_version):
    exe_stat = metashape_exe.stat()
    python_stat = python.stat()
    identity = json.dumps(
        {
            "exe": str(metashape_exe).casefold(),
            "exeSize": exe_stat.st_size,
            "exeMtimeNs": exe_stat.st_mtime_ns,
            "pythonSize": python_stat.st_size,
            "pythonMtimeNs": python_stat.st_mtime_ns,
            "abi": abi,
            "bundleVersion": bundle_version,
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"{fingerprint}-{abi}-{bundle_version}"


def ensure_metashape_runtime(resource_root, state_root, metashape_exe, event=None, cancelled=None):
    resource_root = Path(resource_root).resolve()
    manifest = load_bundled_runtime_manifest(
        resource_root / "runtime" / "bundled-runtime-manifest.json",
        resource_root,
    )
    metashape_exe, python = metashape_python(metashape_exe)
    abi = python_abi(python)
    artifacts = metashape_profile(manifest, abi)
    native_ready, _native_detail = _probe_metashape_runtime(metashape_exe, resource_root)
    if native_ready:
        return {
            "status": "ready",
            "source": "metashape",
            "metashapePath": str(metashape_exe),
            "pythonAbi": abi,
            "sitePackages": "",
            "reused": True,
        }
    runtime_id = _metashape_runtime_id(
        metashape_exe, python, abi, manifest["runtimeVersion"]
    )
    pip_pyz = resource_root / "runtime" / "pip.pyz"
    last_probe_detail = ""

    def probe(site):
        nonlocal last_probe_detail
        ready, last_probe_detail = _probe_metashape_runtime(metashape_exe, resource_root, site)
        return ready

    try:
        result = bootstrap_local_runtime(
            runtime_name="metashape",
            runtime_id=runtime_id,
            runtime_version=manifest["runtimeVersion"],
            state_root=state_root,
            artifacts=artifacts,
            install=lambda wheels, site: install_verified_wheels(
                python, pip_pyz, wheels, site, cancelled=cancelled
            ),
            probe=probe,
            event=event,
            cancelled=cancelled,
        )
    except BootstrapError as exc:
        if exc.code == "PROBE_FAILED" and last_probe_detail:
            raise BootstrapError(
                "METASHAPE_RUNNER_IMPORT_FAILED",
                "Metashape could not import xPano's verified NumPy/OpenCV runtime: " + last_probe_detail,
            ) from exc
        raise
    return {
        "status": "ready",
        "source": "xpano",
        "metashapePath": str(metashape_exe),
        "pythonAbi": abi,
        "sitePackages": result["sitePackages"],
        "reused": result["reused"],
    }


def probe_bundled_resources(resource_root):
    root = Path(resource_root)
    def configured_path(name, fallback):
        value = os.environ.get(name, "").strip()
        return Path(value) if value else fallback

    required = {
        "python": root / "binaries/python/python.exe",
        "ffmpeg": configured_path("XPANO_FFMPEG", root / "tools/ffmpeg/bin/ffmpeg.exe"),
        "ffprobe": configured_path("XPANO_FFPROBE", root / "tools/ffmpeg/bin/ffprobe.exe"),
        "colmap": configured_path("XPANO_COLMAP", root / "tools/colmap/bin/colmap.exe"),
        "lichtfeld": root / "runtime/lichtfeld-studio/bin/LichtFeld-Studio.exe",
        "pip": root / "runtime/pip.pyz",
        "manifest": root / "runtime/bundled-runtime-manifest.json",
    }
    resources = {
        name: {"status": "ready" if path.is_file() and path.stat().st_size > 0 else "corrupt", "path": str(path)}
        for name, path in required.items()
    }
    if resources["python"]["status"] == "ready":
        missing_media = _missing_media_foundation_dlls()
        if missing_media:
            resources["python"] = {
                "status": "corrupt",
                "path": str(required["python"]),
                "detail": (
                    "Windows Media Foundation is missing ("
                    + ", ".join(missing_media)
                    + "). Install the Media Feature Pack on Windows N/KN."
                ),
            }
        else:
            imports = _run_python(required["python"], "import cv2, numpy, PIL, piexif, tqdm")
        if not missing_media and imports.returncode != 0:
            detail = (imports.stderr or imports.stdout).strip()
            if any(name in detail.casefold() for name in ("mfplat.dll", "mf.dll", "mfreadwrite.dll")):
                detail += "\nWindows Media Feature Pack is required on Windows N/KN editions."
            resources["python"] = {
                "status": "corrupt",
                "path": str(required["python"]),
                "detail": detail,
            }
    probes = {
        "ffmpeg": (["-version"], "ffmpeg version"),
        "ffprobe": (["-version"], "ffprobe version"),
        "colmap": (["-h"], "COLMAP"),
        "lichtfeld": (["--version"], "LichtFeld Studio v"),
    }
    for name, (arguments, marker) in probes.items():
        if resources[name]["status"] != "ready":
            continue
        ready, detail = _probe_tool(required[name], arguments, marker)
        if not ready:
            resources[name] = {
                "status": "corrupt",
                "path": str(required[name]),
                "detail": detail,
            }
    return resources


def _emit(prefix, payload):
    print(prefix + json.dumps(payload, ensure_ascii=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe and prepare xPano runtime dependencies")
    parser.add_argument("command", choices=["probe", "ensure"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--backend", choices=["metashape", "colmap"], required=True)
    parser.add_argument("--metashape", default="metashape.exe")
    args = parser.parse_args(argv)
    try:
        bundled = probe_bundled_resources(args.root)
        corrupt = [name for name, value in bundled.items() if value["status"] != "ready"]
        if corrupt:
            details = [
                f"{name}: {bundled[name].get('detail', 'missing or empty')}"
                for name in corrupt
            ]
            raise RuntimeReadinessError(
                "BUNDLED_RUNTIME_CORRUPT",
                "Bundled runtime is missing or corrupt: " + "; ".join(details),
            )
        result = {"status": "ready", "backend": args.backend, "resources": bundled, "sitePackages": ""}
        if args.backend == "metashape":
            if args.command == "ensure":
                result["metashape"] = ensure_metashape_runtime(
                    args.root,
                    args.state_root,
                    args.metashape,
                    event=lambda phase, message, progress: _emit(
                        "RUNTIME_EVENT:",
                        {"phase": phase, "message": message, "progress": progress},
                    ),
                )
                result["sitePackages"] = result["metashape"]["sitePackages"]
            else:
                metashape_exe, python = metashape_python(args.metashape)
                abi = python_abi(python)
                manifest = load_bundled_runtime_manifest(
                    Path(args.root) / "runtime/bundled-runtime-manifest.json", args.root
                )
                metashape_profile(manifest, abi)
                result["metashape"] = {
                    "status": "ready" if probe_metashape_runtime(metashape_exe, Path(args.root)) else "dependencies_missing",
                    "metashapePath": str(metashape_exe),
                    "pythonAbi": abi,
                }
        _emit("RUNTIME_RESULT:", result)
        return 0
    except (RuntimeReadinessError, BootstrapError) as exc:
        _emit("RUNTIME_ERROR:", {"code": exc.code, "message": str(exc)})
        return 2
    except Exception as exc:
        _emit("RUNTIME_ERROR:", {"code": "READINESS_FAILED", "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
