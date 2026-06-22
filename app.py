import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import queue
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from scripts.colmap_backend import COLMAP_DENSITY_PRESETS, colmap_config_for_density_preset, build_colmap_plan, find_sparse_model_path, publish_colmap_output, run_colmap_plan
from scripts.colmap_dense_merge import merge_dense_ply_into_colmap_points
from scripts.dependency_checks import (
    check_pipeline_dependencies,
    format_dependency_report,
    locate_colmap,
    locate_lichtfield,
    resolve_executable,
)
from scripts.lichtfield_cli import LichtfieldStudioConfig, run_lichtfield_command
from scripts.lichtfeld_densify import LichtfeldDensifyConfig, locate_densify_plugin, locate_densify_python, run_densify_command
from scripts.pipeline_backends import COLMAP_BACKEND, METASHAPE_BACKEND, normalize_backend
from scripts.runtime_paths import first_existing, internal_root, locate_ffmpeg
from scripts.verify_xpano_output import verify_output
from scripts.xpano_tracks import build_manifest, load_manifest, validate_manifest


APP_VERSION = "0.1.1-portable"
APP_TITLE = f"xPano 多相机重建 {APP_VERSION}"
TRACK_TYPE_LABELS = {
    "panorama_video": "全景视频",
    "ordinary_video": "普通视频",
    "standard_photos": "普通照片",
    "aerial_photos": "航拍照片",
}
RUNTIME_IMPORTS = ("numpy", "cv2", "PIL", "piexif", "viser")


def collect_runtime_import_versions(import_module=importlib.import_module):
    result = {
        "ok": True,
        "python": sys.version,
        "executable": sys.executable,
        "modules": {},
    }
    for module_name in RUNTIME_IMPORTS:
        try:
            module = import_module(module_name)
            result["modules"][module_name] = {
                "ok": True,
                "version": getattr(module, "__version__", "n/a"),
                "file": getattr(module, "__file__", "n/a"),
            }
        except Exception as exc:
            result["ok"] = False
            result["modules"][module_name] = {
                "ok": False,
                "error": repr(exc),
            }
    return result


def write_runtime_import_report(output_path):
    report = collect_runtime_import_versions()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


@dataclass
class JobConfig:
    input_video: Path
    output_dir: Path
    seconds_per_frame: float
    max_frames: int
    metashape_exe: str
    overwrite_generated: bool = True


@dataclass
class MaterialTrack:
    track_type: str
    label: str
    paths: list


@dataclass
class MultiTrackJobConfig:
    panorama_videos: list
    standard_photo_tracks: list
    aerial_photo_tracks: list
    output_dir: Path
    seconds_per_frame: float
    max_frames: int
    metashape_exe: str
    overwrite_generated: bool = True
    backend: str = METASHAPE_BACKEND
    manifest_path: Path = None
    colmap_exe: str = "colmap"
    colmap_density_preset: str = "stable"
    colmap_use_gpu: bool = False
    run_lichtfield: bool = False
    lichtfield_exe: str = "lichtfield-studio"
    lichtfield_point_count: int = 0
    lichtfield_bilateral_grid: int = 0
    run_lfs_densify: bool = False
    lfs_densify_python: str = None
    lfs_densify_plugin: Path = None
    lfs_densify_roma: str = "fast"
    lfs_densify_num_refs: float = 8.0
    lfs_densify_max_points: int = 0
    ordinary_video_tracks: list = field(default_factory=list)
    track_extraction_settings: dict = field(default_factory=dict)


def material_tracks_to_job_config(
    tracks,
    output_dir,
    seconds_per_frame,
    max_frames,
    metashape_exe,
    overwrite_generated=True,
    backend=METASHAPE_BACKEND,
    colmap_exe="colmap",
    colmap_density_preset="stable",
    colmap_use_gpu=False,
    run_lichtfield=False,
    lichtfield_exe="lichtfield-studio",
    lichtfield_point_count=0,
    lichtfield_bilateral_grid=0,
    run_lfs_densify=False,
    lfs_densify_python=None,
    lfs_densify_plugin=None,
    lfs_densify_roma="fast",
    lfs_densify_num_refs=8.0,
    lfs_densify_max_points=0,
):
    panorama_videos = []
    ordinary_video_tracks = []
    standard_photo_tracks = []
    aerial_photo_tracks = []

    for track in tracks:
        paths = [Path(path).resolve() for path in track.paths]
        if not paths:
            raise ValueError(f"Material track {track.label or track.track_type} must contain at least one path")
        if track.track_type == "panorama_video":
            panorama_videos.extend(paths)
        elif track.track_type == "ordinary_video":
            ordinary_video_tracks.extend(paths)
        elif track.track_type == "standard_photos":
            standard_photo_tracks.append((track.label, paths))
        elif track.track_type == "aerial_photos":
            aerial_photo_tracks.append((track.label, paths))
        else:
            raise ValueError(f"Unsupported material track type: {track.track_type}")

    return MultiTrackJobConfig(
        panorama_videos=panorama_videos,
        ordinary_video_tracks=ordinary_video_tracks,
        standard_photo_tracks=standard_photo_tracks,
        aerial_photo_tracks=aerial_photo_tracks,
        output_dir=Path(output_dir).resolve(),
        seconds_per_frame=seconds_per_frame,
        max_frames=max_frames,
        metashape_exe=metashape_exe,
        overwrite_generated=overwrite_generated,
        backend=backend,
        colmap_exe=colmap_exe,
        colmap_density_preset=colmap_density_preset,
        colmap_use_gpu=colmap_use_gpu,
        run_lichtfield=run_lichtfield,
        lichtfield_exe=lichtfield_exe,
        lichtfield_point_count=lichtfield_point_count,
        lichtfield_bilateral_grid=lichtfield_bilateral_grid,
        run_lfs_densify=run_lfs_densify,
        lfs_densify_python=lfs_densify_python,
        lfs_densify_plugin=Path(lfs_densify_plugin).resolve() if lfs_densify_plugin else None,
        lfs_densify_roma=lfs_densify_roma,
        lfs_densify_num_refs=lfs_densify_num_refs,
        lfs_densify_max_points=lfs_densify_max_points,
    )


def run_lfs_densification_stage(job, progress_cb, log_cb):
    log_cb("开始 LichtFeld densification 致密化")
    dense_ply = job.output_dir / "sparse" / "0" / "points3D_dense.ply"
    run_densify_command(
        LichtfeldDensifyConfig(
            python_exe=job.lfs_densify_python,
            plugin_dir=job.lfs_densify_plugin or locate_densify_plugin(),
            scene_root=job.output_dir,
            images_subdir="images",
            out_name=dense_ply.name,
            roma_setting=job.lfs_densify_roma,
            num_refs=job.lfs_densify_num_refs,
            max_points=job.lfs_densify_max_points,
        ),
        progress_cb=lambda value: progress_cb(min(99, value)),
        log_cb=log_cb,
    )
    merge_result = merge_dense_ply_into_colmap_points(
        sparse_model_dir=job.output_dir / "sparse" / "0",
        dense_ply_path=dense_ply,
        replace_points_bin=True,
    )
    log_cb(
        "LichtFeld dense points merged into COLMAP: "
        f"{merge_result['original_points']} + {merge_result['dense_points']} = {merge_result['merged_points']}"
    )


def locate_metashape():
    candidates = []
    explicit = os.environ.get("XPANO_METASHAPE")
    if explicit and Path(explicit).exists():
        return explicit
    env_path = os.environ.get("Path", "")
    for item in env_path.split(os.pathsep):
        item = item.strip()
        if not item:
            continue
        exe = Path(item) / "metashape.exe"
        if exe.exists():
            candidates.append(str(exe))
    for item in [
        r"E:\FastProgram\Metashape\metashape.exe",
        r"C:\Program Files\Agisoft\Metashape Pro\metashape.exe",
        r"C:\Program Files\Agisoft\Metashape\metashape.exe",
    ]:
        exe = Path(item)
        if exe.exists():
            candidates.append(str(exe))
    if candidates:
        return candidates[0]
    return "metashape.exe"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def generated_output_paths(output_dir: Path):
    return [
        output_dir / "work",
        output_dir / "images",
        output_dir / "sparse",
        output_dir / "colmap",
        output_dir / "lichtfield",
    ]


def _path_is_within(path: Path, parent: Path):
    path = Path(path).resolve()
    parent = Path(parent).resolve()
    try:
        return path == parent or path.is_relative_to(parent)
    except AttributeError:
        return str(path).startswith(str(parent))


def _remove_path_preserving(path: Path, preserve_paths):
    path = Path(path)
    if not path.exists():
        return
    preserve_paths = [Path(item).resolve() for item in (preserve_paths or [])]
    if any(path.resolve() == preserve for preserve in preserve_paths):
        return
    if path.is_dir():
        keep_children = [preserve for preserve in preserve_paths if _path_is_within(preserve, path)]
        if not keep_children:
            shutil.rmtree(path)
            return
        for child in list(path.iterdir()):
            if any(_path_is_within(preserve, child) for preserve in keep_children):
                _remove_path_preserving(child, preserve_paths)
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        path.unlink()


def clear_generated_outputs(output_dir: Path, log_cb, preserve_paths=None):
    for path in generated_output_paths(output_dir):
        if path.exists():
            log_cb(f"清理旧输出: {path}")
            _remove_path_preserving(path, preserve_paths)


def write_run_summary(job: JobConfig):
    backend = normalize_backend(getattr(job, "backend", METASHAPE_BACKEND))
    if backend == COLMAP_BACKEND:
        image_dir = job.output_dir / "images"
        sparse_dir = job.output_dir / "sparse" / "0"
        if not sparse_dir.exists():
            sparse_dir = find_sparse_model_path(job.output_dir / "colmap" / "sparse")
        export_verification = {
            "backend": backend,
            "image_dir": str(image_dir),
            "sparse_model_path": str(sparse_dir),
        }
    else:
        image_dir = job.output_dir / "images"
        sparse_dir = job.output_dir / "sparse" / "0"
        export_verification = verify_output(job.output_dir, expect_single_sparse=True)
    frames_dir = job.output_dir / "work" / "frames"
    manifest_path = getattr(job, "manifest_path", None) or job.output_dir / "work" / "xpano_manifest.json"
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path) if manifest_path.exists() else {"tracks": []}
    input_videos = [str(path) for path in getattr(job, "panorama_videos", [])]
    if not input_videos and hasattr(job, "input_video"):
        input_videos = [str(job.input_video)]
    summary = {
        "workflow": "xpano_multi_track",
        "input_video": input_videos[0] if len(input_videos) == 1 else "",
        "input_videos": input_videos,
        "output_dir": str(job.output_dir),
        "backend": backend,
        "seconds_per_frame": job.seconds_per_frame,
        "max_frames": job.max_frames,
        "track_count": len(manifest.get("tracks", [])),
        "tracks": [
            {
                "track_id": track.get("track_id"),
                "track_type": track.get("track_type"),
                "device_label": track.get("device_label"),
                "frame_count": len(track.get("frames", [])),
                "photo_count": len(track.get("photos", [])),
                "photo_sensor_count": len(track.get("photo_sensors", [])),
            }
            for track in manifest.get("tracks", [])
        ],
        "manifest": str(manifest_path),
        "export_verification": export_verification,
        "frames_jpg": len(list(frames_dir.rglob("*.jpg"))) if frames_dir.exists() else 0,
        "cubemap_images": len(list(image_dir.glob("*.jpg"))) if image_dir.exists() and backend == METASHAPE_BACKEND else 0,
        "colmap_input_images": len(list(image_dir.rglob("*.jpg"))) if image_dir.exists() and backend == COLMAP_BACKEND else 0,
        "colmap_bins": {
            name: (sparse_dir / name).stat().st_size if (sparse_dir / name).exists() else 0
            for name in ["cameras.bin", "images.bin", "points3D.bin"]
        },
        "lfs_densification": {
            "enabled": bool(getattr(job, "run_lfs_densify", False)),
            "output": str(sparse_dir / "points3D_dense.ply"),
            "exists": (sparse_dir / "points3D_dense.ply").exists(),
            "roma": getattr(job, "lfs_densify_roma", ""),
            "max_points": getattr(job, "lfs_densify_max_points", 0),
        },
        "project": str(job.output_dir / "work" / "xpano.psx"),
        "alignment_summary": str(job.output_dir / "xpano_alignment_summary.txt"),
    }
    (job.output_dir / "xpano_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_multi_track_pipeline(job: MultiTrackJobConfig, progress_cb, preview_cb, log_cb):
    backend = normalize_backend(job.backend)
    if job.overwrite_generated:
        preserve_paths = [job.manifest_path] if job.manifest_path else None
        clear_generated_outputs(job.output_dir, log_cb, preserve_paths=preserve_paths)
    work_dir = ensure_dir(job.output_dir / "work")
    project_path = work_dir / "xpano.psx"

    log_cb("开始抽帧")
    if job.manifest_path:
        manifest_path = Path(job.manifest_path).resolve()
        validate_manifest(load_manifest(manifest_path))
    else:
        _, manifest_path = build_manifest(
            output_dir=job.output_dir,
            panorama_videos=job.panorama_videos,
            ordinary_videos=getattr(job, "ordinary_video_tracks", []),
            standard_photo_tracks=job.standard_photo_tracks,
            aerial_photo_tracks=job.aerial_photo_tracks,
            seconds_per_frame=job.seconds_per_frame,
            max_frames=job.max_frames,
            track_extraction_settings=getattr(job, "track_extraction_settings", {}),
            preview_cb=preview_cb,
            progress_cb=lambda cur, total: progress_cb(5 + int(25 * cur / max(total, 1))),
            log_cb=log_cb,
        )
        job.manifest_path = manifest_path

    if backend == COLMAP_BACKEND:
        log_cb("开始 COLMAP 自动处理")
        progress_cb(35)
        job.colmap_exe = resolve_executable(job.colmap_exe, "colmap")
        colmap_config = colmap_config_for_density_preset(job.colmap_density_preset, colmap_exe=job.colmap_exe)
        if job.colmap_use_gpu:
            colmap_config = replace(colmap_config, use_gpu=True)
        plan = build_colmap_plan(
            load_manifest(manifest_path),
            output_dir=job.output_dir / "colmap",
            config=colmap_config,
        )
        result = run_colmap_plan(plan, progress_cb=lambda value: progress_cb(min(95, value)), log_cb=log_cb)
        final_result = publish_colmap_output(plan, job.output_dir)
        if job.run_lichtfield:
            log_cb("开始 LICHT Field Studio 后处理")
            progress_cb(95)
            sparse_model_path = Path(final_result.get("sparse_model_path") or result.get("sparse_model_path") or find_sparse_model_path(plan.sparse_dir))
            run_lichtfield_command(
                LichtfieldStudioConfig(
                    executable=job.lichtfield_exe,
                    input_colmap=sparse_model_path,
                    image_dir=Path(final_result.get("image_dir", plan.image_dir)),
                    output_dir=job.output_dir / "lichtfield",
                    point_count=job.lichtfield_point_count,
                    bilateral_grid=job.lichtfield_bilateral_grid,
                ),
                progress_cb=lambda value: progress_cb(95 + int(4 * value / 100)),
                log_cb=log_cb,
            )
        if job.run_lfs_densify:
            run_lfs_densification_stage(job, progress_cb, log_cb)
        write_run_summary(job)
        progress_cb(100)
        log_cb("完成")
        return

    log_cb("开始 Metashape 自动处理")
    script = first_existing([
        internal_root() / "scripts" / "metashape_pipeline.py",
        Path(__file__).parent / "scripts" / "metashape_pipeline.py",
    ])
    if not script:
        raise FileNotFoundError("metashape_pipeline.py")
    cmd = [
        job.metashape_exe,
        "-r",
        str(script),
        "--manifest",
        str(manifest_path),
        "--project",
        str(project_path),
        "--export-dir",
        str(job.output_dir),
        "--max-frames",
        str(job.max_frames),
    ]
    progress_cb(35)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("PROGRESS:"):
            try:
                value = int(line.split(":", 1)[1].strip())
                progress_cb(max(35, min(95, value)))
            except Exception:
                pass
        else:
            match = re.search(r"处理中 \[(\d+)/(\d+)\]", line)
            if match:
                cur, total = int(match.group(1)), int(match.group(2))
                progress_cb(97 + int(2 * cur / max(total, 1)))
            if line:
                log_cb(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Metashape 处理失败，返回码 {rc}")
    if job.run_lfs_densify:
        run_lfs_densification_stage(job, progress_cb, log_cb)
    write_run_summary(job)
    progress_cb(100)
    log_cb("完成")


def run_metashape_pipeline(job: JobConfig, progress_cb, preview_cb, log_cb):
    multi_job = MultiTrackJobConfig(
        panorama_videos=[job.input_video],
        ordinary_video_tracks=[],
        standard_photo_tracks=[],
        aerial_photo_tracks=[],
        output_dir=job.output_dir,
        seconds_per_frame=job.seconds_per_frame,
        max_frames=job.max_frames,
        metashape_exe=job.metashape_exe,
        overwrite_generated=job.overwrite_generated,
        backend=METASHAPE_BACKEND,
    )
    run_multi_track_pipeline(multi_job, progress_cb, preview_cb, log_cb)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x760")
        self.root.minsize(980, 680)

        self.msg_queue = queue.Queue()
        self.left_preview = None
        self.right_preview = None
        self.material_tracks = []

        self.output_var = tk.StringVar()
        self.spf_var = tk.StringVar(value="1.0")
        self.frames_var = tk.StringVar(value="")
        self.metashape_var = tk.StringVar(value=locate_metashape())
        self.colmap_var = tk.StringVar(value=locate_colmap())
        self.lichtfield_var = tk.StringVar(value=locate_lichtfield())
        self.backend_var = tk.StringVar(value=METASHAPE_BACKEND)
        self.colmap_density_var = tk.StringVar(value="stable")
        self.colmap_use_gpu_var = tk.BooleanVar(value=False)
        self.run_lichtfield_var = tk.BooleanVar(value=False)
        self.licht_point_count_var = tk.StringVar(value="0")
        self.licht_grid_var = tk.StringVar(value="0")
        self.run_lfs_densify_var = tk.BooleanVar(value=False)
        self.lfs_densify_python_var = tk.StringVar(value=locate_densify_python())
        self.lfs_densify_plugin_var = tk.StringVar(value=str(locate_densify_plugin()))
        self.lfs_densify_roma_var = tk.StringVar(value="fast")
        self.lfs_densify_num_refs_var = tk.StringVar(value="8")
        self.lfs_densify_max_points_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="待机")
        self.track_count_var = tk.StringVar(value="0 个素材轨")
        self.advanced_visible = tk.BooleanVar(value=False)
        self.running = False

        self._build_ui()
        self.output_var.trace_add("write", lambda *_: self._sync_start_button_state())
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(16, 12, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.track_count_var).grid(row=0, column=1, sticky="e")

        body = ttk.Frame(self.root, padding=(16, 0, 16, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        tracks_box = ttk.LabelFrame(body, text="素材轨")
        tracks_box.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tracks_box.columnconfigure(0, weight=1)
        self.tracks_tree = ttk.Treeview(
            tracks_box,
            columns=("type", "label", "paths"),
            show="headings",
            height=5,
            selectmode="extended",
        )
        self.tracks_tree.heading("type", text="类型")
        self.tracks_tree.heading("label", text="名称")
        self.tracks_tree.heading("paths", text="路径")
        self.tracks_tree.column("type", width=140, stretch=False)
        self.tracks_tree.column("label", width=160, stretch=False)
        self.tracks_tree.column("paths", width=640, stretch=True)
        self.tracks_tree.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        track_buttons = ttk.Frame(tracks_box)
        track_buttons.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        ttk.Button(track_buttons, text="＋ 全景视频", command=self.add_panorama_track).pack(side="left")
        ttk.Button(track_buttons, text="＋ 普通照片", command=self.add_standard_photo_track).pack(side="left", padx=(8, 0))
        ttk.Button(track_buttons, text="＋ 航拍照片", command=self.add_aerial_photo_track).pack(side="left", padx=(8, 0))
        ttk.Button(track_buttons, text="✕ 删除选中", command=self.remove_selected_track).pack(side="right")

        preview_box = ttk.LabelFrame(body, text="图像预览")
        preview_box.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        preview_box.rowconfigure(1, weight=1)
        self.left_label = ttk.Label(preview_box, text="左鱼眼预览", anchor="center")
        self.left_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.right_label = ttk.Label(preview_box, text="右鱼眼预览", anchor="center")
        self.right_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))

        controls_shell = ttk.Frame(body)
        controls_shell.grid(row=1, column=1, sticky="nsew")
        controls_shell.rowconfigure(0, weight=1)
        controls_shell.columnconfigure(0, weight=1)

        self.controls_canvas = tk.Canvas(controls_shell, borderwidth=0, highlightthickness=0)
        controls_scrollbar = ttk.Scrollbar(controls_shell, orient="vertical", command=self.controls_canvas.yview)
        self.controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        self.controls_canvas.grid(row=0, column=0, sticky="nsew")
        controls_scrollbar.grid(row=0, column=1, sticky="ns")

        controls = ttk.Frame(self.controls_canvas)
        self.controls_window = self.controls_canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", self._on_controls_frame_configure)
        self.controls_canvas.bind("<Configure>", self._on_controls_canvas_configure)
        self.controls_canvas.bind("<Enter>", self._bind_controls_mousewheel)
        self.controls_canvas.bind("<Leave>", self._unbind_controls_mousewheel)
        controls.columnconfigure(0, weight=1)
        controls.rowconfigure(6, weight=1)

        output_box = ttk.LabelFrame(controls, text="输出")
        output_box.grid(row=0, column=0, sticky="ew")
        output_box.columnconfigure(0, weight=1)
        ttk.Entry(output_box, textvariable=self.output_var).grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=10)
        ttk.Button(output_box, text="… 选择", command=self.pick_output).grid(row=0, column=1, padx=(0, 10), pady=10)

        backend_box = ttk.LabelFrame(controls, text="后端")
        backend_box.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        backend_box.columnconfigure(1, weight=1)
        for idx, (label, value) in enumerate([("Metashape", METASHAPE_BACKEND), ("COLMAP", COLMAP_BACKEND)]):
            ttk.Radiobutton(backend_box, text=label, value=value, variable=self.backend_var, command=self._sync_backend_mode).grid(row=0, column=idx, padx=10, pady=10, sticky="w")

        frame_box = ttk.LabelFrame(controls, text="抽帧设置")
        frame_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        frame_box.columnconfigure(1, weight=1)
        ttk.Label(frame_box, text="秒/帧").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        ttk.Entry(frame_box, textvariable=self.spf_var, width=12).grid(row=0, column=1, sticky="w", padx=6, pady=10)
        ttk.Label(frame_box, text="帧数上限").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=10)
        ttk.Entry(frame_box, textvariable=self.frames_var, width=12).grid(row=0, column=3, sticky="w", padx=(0, 6), pady=10)
        ttk.Label(frame_box, text="留空=全部").grid(row=0, column=4, sticky="w", padx=(0, 10), pady=10)

        self.advanced_button = ttk.Button(controls, text="▸ 高级参数", command=self.toggle_advanced)
        self.advanced_button.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.advanced_frame = ttk.LabelFrame(controls, text="高级参数")
        self.advanced_frame.columnconfigure(1, weight=1)
        ttk.Label(self.advanced_frame, text="Metashape").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        ttk.Entry(self.advanced_frame, textvariable=self.metashape_var).grid(row=0, column=1, sticky="ew", padx=6, pady=(10, 4))
        ttk.Button(self.advanced_frame, text="… 定位", command=self.pick_metashape).grid(row=0, column=2, padx=(0, 10), pady=(10, 4))
        ttk.Label(self.advanced_frame, text="COLMAP").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(self.advanced_frame, textvariable=self.colmap_var).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(self.advanced_frame, text="… 定位", command=self.pick_colmap).grid(row=1, column=2, padx=(0, 10), pady=4)
        ttk.Label(self.advanced_frame, text="COLMAP density").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.colmap_density_combo = ttk.Combobox(
            self.advanced_frame,
            textvariable=self.colmap_density_var,
            values=COLMAP_DENSITY_PRESETS,
            state="readonly",
        )
        self.colmap_density_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(6, 10), pady=4)
        self.colmap_gpu_check = ttk.Checkbutton(self.advanced_frame, text="COLMAP CUDA/GPU", variable=self.colmap_use_gpu_var)
        self.colmap_gpu_check.grid(row=3, column=0, columnspan=3, sticky="w", padx=10, pady=(4, 4))
        ttk.Label(self.advanced_frame, text="LICHT").grid(row=4, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(self.advanced_frame, textvariable=self.lichtfield_var).grid(row=4, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(self.advanced_frame, text="… 定位", command=self.pick_lichtfield).grid(row=4, column=2, padx=(0, 10), pady=4)
        self.licht_check = ttk.Checkbutton(self.advanced_frame, text="运行 LICHT Field Studio 后处理", variable=self.run_lichtfield_var, command=self._sync_backend_mode)
        self.licht_check.grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(4, 4))
        self.licht_frame = ttk.Frame(self.advanced_frame)
        self.licht_frame.columnconfigure(1, weight=1)
        ttk.Label(self.licht_frame, text="点数").grid(row=0, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(self.licht_frame, textvariable=self.licht_point_count_var, width=12).grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(self.licht_frame, text="双边网格").grid(row=1, column=0, sticky="w", padx=10, pady=(4, 10))
        ttk.Entry(self.licht_frame, textvariable=self.licht_grid_var, width=12).grid(row=1, column=1, sticky="w", padx=6, pady=(4, 10))

        progress_box = ttk.LabelFrame(controls, text="进度")
        progress_box.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        progress_box.columnconfigure(1, weight=1)
        ttk.Label(progress_box, textvariable=self.status_var).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))
        self.pb = ttk.Progressbar(progress_box, orient="horizontal", mode="determinate", maximum=100)
        self.pb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        self.lfs_densify_check = ttk.Checkbutton(self.advanced_frame, text="Run LichtFeld densification", variable=self.run_lfs_densify_var)
        self.lfs_densify_check.grid(row=7, column=0, columnspan=3, sticky="w", padx=10, pady=(4, 4))
        ttk.Label(self.advanced_frame, text="RoMa").grid(row=8, column=0, sticky="w", padx=10, pady=4)
        self.lfs_densify_roma_combo = ttk.Combobox(
            self.advanced_frame,
            textvariable=self.lfs_densify_roma_var,
            values=("precise", "high", "base", "fast", "turbo"),
            state="readonly",
        )
        self.lfs_densify_roma_combo.grid(row=8, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(self.advanced_frame, text="Max dense points").grid(row=9, column=0, sticky="w", padx=10, pady=(4, 10))
        ttk.Entry(self.advanced_frame, textvariable=self.lfs_densify_max_points_var, width=12).grid(row=9, column=1, sticky="w", padx=6, pady=(4, 10))
        ttk.Label(self.advanced_frame, text="Dense references").grid(row=10, column=0, sticky="w", padx=10, pady=(4, 10))
        ttk.Entry(self.advanced_frame, textvariable=self.lfs_densify_num_refs_var, width=12).grid(row=10, column=1, sticky="w", padx=6, pady=(4, 10))

        self.stage_bars = {}
        for row, (key, label) in enumerate([("extract", "抽帧"), ("align", "重建"), ("export", "后处理")], start=2):
            ttk.Label(progress_box, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=3)
            bar = ttk.Progressbar(progress_box, orient="horizontal", mode="determinate", maximum=100)
            bar.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=3)
            self.stage_bars[key] = bar

        action_bar = ttk.Frame(controls)
        action_bar.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        self.start_button = ttk.Button(action_bar, text="▶ 开始处理", command=self.start)
        self.start_button.pack(side="right")
        ttk.Button(action_bar, text="↗ 打开输出", command=self.open_output).pack(side="right", padx=(0, 8))
        ttk.Button(action_bar, text="检查环境", command=self.check_environment).pack(side="left")
        self._sync_start_button_state()
        self._sync_backend_mode()

        log_box = ttk.LabelFrame(controls, text="运行日志")
        log_box.grid(row=6, column=0, sticky="nsew", pady=(10, 0))
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        self.log = tk.Text(log_box, height=12, wrap="word")
        log_scrollbar = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scrollbar.set)
        self.log.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        log_scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 10), pady=10)

    def _on_controls_frame_configure(self, _event):
        self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all"))

    def _on_controls_canvas_configure(self, event):
        self.controls_canvas.itemconfigure(self.controls_window, width=event.width)

    @staticmethod
    def _mousewheel_units(event):
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        delta = getattr(event, "delta", 0)
        if delta:
            return -int(delta / 120)
        return 0

    def _on_controls_mousewheel(self, event):
        if getattr(event, "widget", None) is self.log:
            return
        units = self._mousewheel_units(event)
        if units:
            self.controls_canvas.yview_scroll(units, "units")

    def _bind_controls_mousewheel(self, _event):
        self.root.bind_all("<MouseWheel>", self._on_controls_mousewheel)
        self.root.bind_all("<Button-4>", self._on_controls_mousewheel)
        self.root.bind_all("<Button-5>", self._on_controls_mousewheel)

    def _unbind_controls_mousewheel(self, _event):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _add_material_track(self, track_type, label, paths):
        paths = [Path(path) for path in paths]
        if not paths:
            return
        self.material_tracks.append(MaterialTrack(track_type=track_type, label=label, paths=paths))
        self._refresh_tracks_tree()

    def _refresh_tracks_tree(self):
        for item in self.tracks_tree.get_children():
            self.tracks_tree.delete(item)
        for index, track in enumerate(self.material_tracks):
            display_paths = "; ".join(str(path) for path in track.paths)
            track_type = TRACK_TYPE_LABELS.get(track.track_type, track.track_type)
            self.tracks_tree.insert("", "end", iid=str(index), values=(track_type, track.label, display_paths))
        self.track_count_var.set(f"{len(self.material_tracks)} 个素材轨")
        self._sync_start_button_state()

    def _sync_start_button_state(self):
        if not hasattr(self, "start_button"):
            return
        if self.running or not self.material_tracks or not self.output_var.get().strip():
            self.start_button.configure(state="disabled")
        else:
            self.start_button.configure(state="normal")

    def _sync_backend_mode(self):
        if not hasattr(self, "licht_frame"):
            return
        is_colmap = self.backend_var.get() == COLMAP_BACKEND
        if hasattr(self, "licht_check"):
            self.licht_check.configure(state="normal" if is_colmap else "disabled")
        if hasattr(self, "colmap_density_combo"):
            self.colmap_density_combo.configure(state="readonly" if is_colmap else "disabled")
        if hasattr(self, "colmap_gpu_check"):
            self.colmap_gpu_check.configure(state="normal" if is_colmap else "disabled")
        if is_colmap and self.run_lichtfield_var.get():
            self.licht_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        else:
            self.licht_frame.grid_remove()

    def toggle_advanced(self):
        if self.advanced_visible.get():
            self.advanced_frame.grid_remove()
            self.advanced_button.configure(text="▸ 高级参数")
            self.advanced_visible.set(False)
        else:
            self.advanced_frame.grid(row=4, column=0, sticky="ew", pady=(6, 0))
            self.advanced_button.configure(text="▾ 高级参数")
            self.advanced_visible.set(True)

    def add_panorama_track(self):
        paths = filedialog.askopenfilenames(filetypes=[("Panorama video", "*.osv *.insv *.mp4"), ("All", "*.*")])
        for path in paths:
            video = Path(path)
            self._add_material_track("panorama_video", video.stem, [video])

    def add_standard_photo_track(self):
        path = filedialog.askdirectory(title="Select standard photo folder")
        if path:
            folder = Path(path)
            self._add_material_track("standard_photos", folder.name or "standard_photos", [folder])

    def add_aerial_photo_track(self):
        path = filedialog.askdirectory(title="Select aerial photo folder")
        if path:
            folder = Path(path)
            self._add_material_track("aerial_photos", folder.name or "aerial_photos", [folder])

    def remove_selected_track(self):
        selected = sorted((int(item) for item in self.tracks_tree.selection()), reverse=True)
        for index in selected:
            if 0 <= index < len(self.material_tracks):
                del self.material_tracks[index]
        self._refresh_tracks_tree()

    def pick_output(self):
        p = filedialog.askdirectory()
        if p:
            self.output_var.set(p)

    def pick_metashape(self):
        p = filedialog.askopenfilename(filetypes=[("Metashape", "metashape.exe"), ("Executable", "*.exe")])
        if p:
            self.metashape_var.set(p)

    def pick_colmap(self):
        p = filedialog.askopenfilename(filetypes=[("COLMAP", "colmap.exe"), ("Executable", "*.exe")])
        if p:
            self.colmap_var.set(p)

    def pick_lichtfield(self):
        p = filedialog.askopenfilename(filetypes=[("LICHT Field Studio", "*.exe"), ("Executable", "*.exe")])
        if p:
            self.lichtfield_var.set(p)

    def open_output(self):
        if not self.output_var.get():
            messagebox.showinfo("输出文件夹", "请先选择输出文件夹")
            return
        output = Path(self.output_var.get())
        try:
            output.mkdir(parents=True, exist_ok=True)
            os.startfile(str(output))
        except Exception as exc:
            messagebox.showerror("打开输出失败", str(exc))

    def check_environment(self):
        checks = check_pipeline_dependencies(
            backend=self.backend_var.get(),
            metashape_exe=self.metashape_var.get(),
            colmap_exe=self.colmap_var.get(),
            lichtfield_exe=self.lichtfield_var.get(),
            run_lichtfield=self.run_lichtfield_var.get(),
            run_lfs_densify=self.run_lfs_densify_var.get(),
            lfs_densify_python=self.lfs_densify_python_var.get(),
            lfs_densify_plugin=self.lfs_densify_plugin_var.get(),
        )
        report = format_dependency_report(checks)
        if hasattr(self, "log"):
            self.log.insert("end", "环境检查:\n" + report + "\n")
            self.log.see("end")
        if all(check.ok or not check.required for check in checks):
            messagebox.showinfo("环境检查", report)
        else:
            messagebox.showwarning("环境检查", report)

    def _build_job_from_controls(
        self,
        spf,
        max_frames,
        metashape_exe,
        colmap_exe,
        lichtfield_exe,
        licht_point_count,
        licht_grid,
    ):
        backend = normalize_backend(self.backend_var.get())
        def control_value(name, default):
            var = getattr(self, name, None)
            return var.get() if var is not None else default

        lfs_plugin = control_value("lfs_densify_plugin_var", "")
        return material_tracks_to_job_config(
            tracks=self.material_tracks,
            output_dir=Path(self.output_var.get()),
            seconds_per_frame=spf,
            max_frames=max_frames,
            metashape_exe=metashape_exe,
            backend=backend,
            colmap_exe=colmap_exe,
            colmap_density_preset=self.colmap_density_var.get(),
            colmap_use_gpu=control_value("colmap_use_gpu_var", False),
            run_lichtfield=backend == COLMAP_BACKEND and self.run_lichtfield_var.get(),
            lichtfield_exe=lichtfield_exe,
            lichtfield_point_count=licht_point_count,
            lichtfield_bilateral_grid=licht_grid,
            run_lfs_densify=control_value("run_lfs_densify_var", False),
            lfs_densify_python=control_value("lfs_densify_python_var", locate_densify_python()),
            lfs_densify_plugin=Path(lfs_plugin) if str(lfs_plugin).strip() else None,
            lfs_densify_roma=control_value("lfs_densify_roma_var", "fast"),
            lfs_densify_num_refs=float(str(control_value("lfs_densify_num_refs_var", "8")).strip() or "8"),
            lfs_densify_max_points=int(str(control_value("lfs_densify_max_points_var", "0")).strip() or "0"),
        )

    def start(self):
        if self.running:
            return
        if not self.material_tracks or not self.output_var.get():
            messagebox.showerror("缺少路径", "请先添加素材轨并选择输出文件夹")
            return
        try:
            spf = float(self.spf_var.get())
            if spf <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("参数错误", "请检查秒/帧输入，必须是大于 0 的数字")
            return
        try:
            max_text = self.frames_var.get().strip()
            max_frames = int(max_text) if max_text else 0
            if max_frames < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("参数错误", "帧数上限必须留空，或填写大于等于 0 的整数")
            return
        try:
            licht_point_count = int(self.licht_point_count_var.get().strip() or "0")
            licht_grid = int(self.licht_grid_var.get().strip() or "0")
            if licht_point_count < 0 or licht_grid < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("参数错误", "LICHT 点数和双边网格必须是大于等于 0 的整数")
            return

        try:
            lfs_densify_max_points = int(self.lfs_densify_max_points_var.get().strip() or "0")
            if lfs_densify_max_points < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Parameter error", "LichtFeld densification max points must be >= 0")
            return
        try:
            lfs_densify_num_refs = float(self.lfs_densify_num_refs_var.get().strip() or "8")
            if lfs_densify_num_refs <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Parameter error", "LichtFeld densification references must be > 0")
            return

        output_dir = Path(self.output_var.get())
        backend = normalize_backend(self.backend_var.get())
        metashape_exe = self.metashape_var.get().strip() or "metashape.exe"
        colmap_exe = self.colmap_var.get().strip() or "colmap"
        lichtfield_exe = self.lichtfield_var.get().strip() or "lichtfield-studio"
        for track in self.material_tracks:
            for path in track.paths:
                if not Path(path).exists():
                    messagebox.showerror("输入不存在", str(path))
                    return
        try:
            if backend == METASHAPE_BACKEND:
                metashape_exe = resolve_executable(metashape_exe, "metashape.exe")
            if backend == COLMAP_BACKEND:
                colmap_exe = resolve_executable(colmap_exe, "colmap")
            if backend == COLMAP_BACKEND and self.run_lichtfield_var.get():
                lichtfield_exe = resolve_executable(lichtfield_exe, "lichtfield-studio")
        except Exception as exc:
            messagebox.showerror("程序不可用", str(exc))
            return
        ffmpeg_path = locate_ffmpeg()
        if not Path(ffmpeg_path).exists() and not shutil.which("ffmpeg"):
            messagebox.showerror("ffmpeg 不可用", "没有在 PATH 中找到 ffmpeg，请先安装 ffmpeg 并加入 PATH。")
            return
        stale = [path for path in generated_output_paths(output_dir) if path.exists()]
        if stale:
            names = "\n".join(str(path) for path in stale)
            if not messagebox.askyesno("覆盖旧输出", f"将清理以下旧输出后重新生成：\n{names}\n\n继续吗？"):
                return

        job = self._build_job_from_controls(
            spf=spf,
            max_frames=max_frames,
            metashape_exe=metashape_exe,
            colmap_exe=colmap_exe,
            lichtfield_exe=lichtfield_exe,
            licht_point_count=licht_point_count,
            licht_grid=licht_grid,
        )

        self.running = True
        self.start_button.configure(state="disabled")
        self.start_button.configure(text="处理中...")
        self.pb["value"] = 0
        for bar in getattr(self, "stage_bars", {}).values():
            bar["value"] = 0
        self.log.delete("1.0", "end")
        self.log.insert("end", "开始处理\n")
        self.status_var.set("运行中")
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()

    def _run_job(self, job):
        try:
            run_multi_track_pipeline(job, self._set_progress, self._show_preview, self._log)
            self.msg_queue.put(("done", "完成"))
        except Exception as exc:
            self._log(traceback.format_exc())
            self.msg_queue.put(("error", str(exc)))

    def _set_progress(self, value):
        self.msg_queue.put(("progress", value))

    def _update_stage_progress(self, value):
        if not hasattr(self, "stage_bars"):
            return
        if value >= 100:
            for bar in self.stage_bars.values():
                bar["value"] = 100
            return
        stages = {
            "extract": max(0, min(100, int((value - 5) * 100 / 30))),
            "align": max(0, min(100, int((value - 35) * 100 / 60))),
            "export": max(0, min(100, int((value - 95) * 100 / 5))),
        }
        for key, stage_value in stages.items():
            self.stage_bars[key]["value"] = stage_value

    def _progress_status_text(self, value):
        value = int(value)
        if value < 35:
            stage = "抽帧/生成清单"
        elif value < 95:
            stage = "重建/对齐"
        else:
            stage = "导出/收尾"
        return f"{stage} · {value}%"

    def _show_preview(self, left_path, right_path):
        self.msg_queue.put(("preview", left_path, right_path))

    def _log(self, text):
        self.msg_queue.put(("log", text))

    def _poll_queue(self):
        try:
            while True:
                item = self.msg_queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    self.pb["value"] = item[1]
                    self._update_stage_progress(item[1])
                    self.status_var.set(self._progress_status_text(item[1]))
                elif kind == "log":
                    self.log.insert("end", item[1] + "\n")
                    self.log.see("end")
                elif kind == "preview":
                    self._update_preview(item[1], item[2])
                elif kind == "done":
                    self.running = False
                    self.start_button.configure(text="▶ 开始处理")
                    self._sync_start_button_state()
                    self.status_var.set(item[1])
                    self.pb["value"] = 100
                    self._update_stage_progress(100)
                    messagebox.showinfo("完成", "处理完成")
                elif kind == "error":
                    self.running = False
                    self.start_button.configure(text="▶ 开始处理")
                    self._sync_start_button_state()
                    self.status_var.set("失败")
                    messagebox.showerror("错误", item[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _update_preview(self, left_path, right_path):
        def load(path, target):
            img = Image.open(path).convert("RGB")
            img.thumbnail(target)
            return ImageTk.PhotoImage(img)

        try:
            self.left_preview = load(left_path, (460, 260))
            self.right_preview = load(right_path, (460, 260))
            self.left_label.configure(image=self.left_preview, text="")
            self.right_label.configure(image=self.right_preview, text="")
        except Exception as exc:
            self.log.insert("end", f"预览更新失败: {exc}\n")
            self.log.see("end")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test-imports")
    args, _unknown = parser.parse_known_args(argv)
    if args.self_test_imports:
        report = write_runtime_import_report(args.self_test_imports)
        return 0 if report["ok"] else 1

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        log_path = Path(__file__).with_name("xpano_gui_error.log")
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("xPano 启动失败", f"错误已写入:\n{log_path}")
            root.destroy()
        except Exception:
            pass
        raise
