import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ColmapBackendConfig:
    colmap_exe: str = "colmap"
    camera_model: str = "OPENCV_FISHEYE"
    image_extension: str = ".jpg"
    max_image_size: int = 1600
    max_num_features: int = 4096
    num_threads: int = 4
    single_camera: bool = False
    single_camera_per_folder: bool = True
    use_gpu: bool = False
    matcher: str = "sequential"
    sequential_overlap: int = 6


@dataclass(frozen=True)
class ColmapCommandPlan:
    output_dir: Path
    database_path: Path
    image_dir: Path
    sparse_dir: Path
    commands: list = field(default_factory=list)
    image_manifest_path: Path = None
    manifest_path: Path = None


def _collect_panorama_frames(manifest):
    frames = []
    for track in manifest.get("tracks", []):
        if track.get("track_type") != "panorama_video":
            continue
        frames.extend(track.get("frames", []))
    return frames


def build_colmap_plan(manifest, output_dir, config=None):
    config = config or ColmapBackendConfig()
    output_dir = Path(output_dir)
    image_dir = output_dir / "colmap_images"
    sparse_dir = output_dir / "sparse"
    database_path = output_dir / "database.db"

    frames = _collect_panorama_frames(manifest)
    if not frames:
        raise ValueError("COLMAP plan requires panorama frames in the manifest")

    frame_sources = []
    for index, frame in enumerate(frames, 1):
        left = Path(frame["left"])
        right = Path(frame["right"])
        if not left.exists() or not right.exists():
            raise FileNotFoundError(f"Missing panorama frame images for COLMAP plan: {frame}")
        frame_sources.append((index, frame, left, right))

    if image_dir.exists():
        shutil.rmtree(image_dir)
    if sparse_dir.exists():
        shutil.rmtree(sparse_dir)
    if database_path.exists():
        database_path.unlink()
    image_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    image_entries = []
    for index, frame, left, right in frame_sources:
        for side, source in [("left", left), ("right", right)]:
            target_name = f"{side}/{index:06d}{config.image_extension}"
            target = image_dir / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            image_entries.append(
                {
                    "frame_id": frame.get("frame_id", f"frame_{index:06d}"),
                    "side": side,
                    "source": str(source),
                    "image": target_name,
                }
            )

    commands = [
        [
            config.colmap_exe,
            "feature_extractor",
            "--database_path",
            str(database_path),
            "--image_path",
            str(image_dir),
            "--ImageReader.camera_model",
            config.camera_model,
            "--ImageReader.single_camera",
            "1" if config.single_camera else "0",
            "--ImageReader.single_camera_per_folder",
            "1" if config.single_camera_per_folder else "0",
            "--FeatureExtraction.max_image_size",
            str(config.max_image_size),
            "--FeatureExtraction.num_threads",
            str(config.num_threads),
            "--FeatureExtraction.use_gpu",
            "1" if config.use_gpu else "0",
            "--SiftExtraction.max_num_features",
            str(config.max_num_features),
        ],
    ]
    if config.matcher == "sequential":
        commands.append(
            [
                config.colmap_exe,
                "sequential_matcher",
                "--database_path",
                str(database_path),
                "--FeatureMatching.num_threads",
                str(config.num_threads),
                "--FeatureMatching.use_gpu",
                "1" if config.use_gpu else "0",
                "--SequentialMatching.overlap",
                str(config.sequential_overlap),
                "--SequentialMatching.expand_rig_images",
                "1",
            ]
        )
    elif config.matcher == "exhaustive":
        commands.append(
            [
                config.colmap_exe,
                "exhaustive_matcher",
                "--database_path",
                str(database_path),
                "--FeatureMatching.num_threads",
                str(config.num_threads),
                "--FeatureMatching.use_gpu",
                "1" if config.use_gpu else "0",
            ]
        )
    else:
        raise ValueError(f"Unsupported COLMAP matcher: {config.matcher}")
    commands.append(
        [
            config.colmap_exe,
            "mapper",
            "--database_path",
            str(database_path),
            "--image_path",
            str(image_dir),
            "--output_path",
            str(sparse_dir),
        ]
    )

    manifest_path = output_dir / "xpano_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    image_manifest_path = output_dir / "colmap_images.json"
    image_manifest_path.write_text(json.dumps(image_entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return ColmapCommandPlan(
        output_dir=output_dir,
        database_path=database_path,
        image_dir=image_dir,
        sparse_dir=sparse_dir,
        commands=commands,
        image_manifest_path=image_manifest_path,
        manifest_path=manifest_path,
    )


def _command_name(command):
    if len(command) >= 2:
        return command[1]
    if command:
        return Path(command[0]).name
    return "COLMAP"


def _popen_creationflags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_command_streaming(command, cwd, log_cb):
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_popen_creationflags(),
    )
    output_lines = []
    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        if line:
            output_lines.append(line)
            log_cb(line)
    rc = proc.wait()
    return subprocess.CompletedProcess(command, rc, stdout="\n".join(output_lines), stderr="")


def _has_sparse_model(sparse_dir):
    sparse_dir = Path(sparse_dir)
    candidates = [sparse_dir, sparse_dir / "0"]
    required = ["cameras.bin", "images.bin", "points3D.bin"]
    return any(all((candidate / name).exists() for name in required) for candidate in candidates)


def find_sparse_model_path(sparse_dir):
    sparse_dir = Path(sparse_dir)
    candidates = [sparse_dir / "0", sparse_dir]
    required = ["cameras.bin", "images.bin", "points3D.bin"]
    for candidate in candidates:
        if all((candidate / name).exists() for name in required):
            return candidate
    raise RuntimeError(f"COLMAP sparse model output is missing: {sparse_dir}")


def run_colmap_plan(plan, progress_cb=None, log_cb=None, runner=None):
    progress_cb = progress_cb or (lambda value: None)
    log_cb = log_cb or (lambda text: None)

    total = len(plan.commands)
    if total == 0:
        raise ValueError("COLMAP plan has no commands to run")

    for index, command in enumerate(plan.commands, 1):
        name = _command_name(command)
        log_cb(f"COLMAP {name}: {' '.join(str(part) for part in command)}")
        if runner is None:
            result = _run_command_streaming(command, plan.output_dir, log_cb)
        else:
            result = runner(
                command,
                cwd=str(plan.output_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for stream in [getattr(result, "stdout", ""), getattr(result, "stderr", "")]:
                for line in (stream or "").splitlines():
                    if line:
                        log_cb(line)
        if getattr(result, "returncode", 0) != 0:
            raise RuntimeError(f"COLMAP {name} failed with return code {result.returncode}")
        progress_cb(35 + int(55 * index / total))

    if not Path(plan.database_path).exists():
        raise RuntimeError(f"COLMAP database output is missing: {plan.database_path}")
    sparse_model_path = find_sparse_model_path(plan.sparse_dir)

    return {
        "database_path": str(plan.database_path),
        "image_dir": str(plan.image_dir),
        "sparse_dir": str(plan.sparse_dir),
        "sparse_model_path": str(sparse_model_path),
    }
