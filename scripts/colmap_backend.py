import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ColmapBackendConfig:
    colmap_exe: str = "colmap"
    camera_model: str = "OPENCV_FISHEYE"
    image_extension: str = ".jpg"
    max_image_size: int = 0
    single_camera: bool = False


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

    image_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)

    image_entries = []
    for index, frame in enumerate(frames, 1):
        left = Path(frame["left"])
        right = Path(frame["right"])
        if not left.exists() or not right.exists():
            raise FileNotFoundError(f"Missing panorama frame images for COLMAP plan: {frame}")
        for side, source in [("left", left), ("right", right)]:
            target_name = f"{index:06d}_{side}{config.image_extension}"
            target = image_dir / target_name
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
            "--SiftExtraction.max_image_size",
            str(config.max_image_size),
        ],
        [
            config.colmap_exe,
            "exhaustive_matcher",
            "--database_path",
            str(database_path),
        ],
        [
            config.colmap_exe,
            "mapper",
            "--database_path",
            str(database_path),
            "--image_path",
            str(image_dir),
            "--output_path",
            str(sparse_dir),
        ],
    ]

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
