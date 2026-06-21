from dataclasses import dataclass
from pathlib import Path

from app import MultiTrackJobConfig, run_multi_track_pipeline
from scripts.pipeline_backends import METASHAPE_BACKEND, normalize_backend
from xpano_workbench.models import AERIAL_PHOTOS, ORDINARY_VIDEO, PANORAMA_VIDEO, STANDARD_PHOTOS, WorkbenchTrack


@dataclass(frozen=True)
class WorkbenchRunConfig:
    tracks: tuple
    output_dir: Path
    backend: str = METASHAPE_BACKEND
    metashape_exe: str = "metashape.exe"
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


class WorkbenchEventSink:
    def progress(self, value):
        pass

    def log(self, text):
        pass

    def preview(self, left_path, right_path):
        pass

    def done(self, result=None):
        pass

    def error(self, exc):
        pass


def _selected_tracks(tracks, backend):
    backend = normalize_backend(backend)
    selected = []
    for track in tracks:
        if backend == "metashape" and not track.enabled_for_metashape:
            continue
        if backend == "colmap" and not track.enabled_for_colmap:
            continue
        selected.append(track.validate())
    return selected


def build_pipeline_job(config: WorkbenchRunConfig):
    backend = normalize_backend(config.backend)
    selected = _selected_tracks(config.tracks, backend)
    if not selected:
        raise ValueError("No enabled tracks are available for the selected backend")

    extraction = selected[0].extraction
    panorama_videos = []
    ordinary_videos = []
    standard_photo_tracks = []
    aerial_photo_tracks = []
    track_extraction_settings = {}

    for track in selected:
        paths = [Path(path).resolve() for path in track.paths]
        for path in paths:
            track_extraction_settings[str(path)] = {
                "seconds_per_frame": track.extraction.seconds_per_frame,
                "max_frames": track.extraction.max_frames,
            }
        if track.track_type == PANORAMA_VIDEO:
            panorama_videos.extend(paths)
        elif track.track_type == ORDINARY_VIDEO:
            ordinary_videos.extend(paths)
        elif track.track_type == STANDARD_PHOTOS:
            standard_photo_tracks.append((track.label, paths))
        elif track.track_type == AERIAL_PHOTOS:
            aerial_photo_tracks.append((track.label, paths))
        else:
            raise ValueError(f"Unsupported workbench track type: {track.track_type}")

    return MultiTrackJobConfig(
        panorama_videos=panorama_videos,
        ordinary_video_tracks=ordinary_videos,
        standard_photo_tracks=standard_photo_tracks,
        aerial_photo_tracks=aerial_photo_tracks,
        output_dir=Path(config.output_dir).resolve(),
        seconds_per_frame=extraction.seconds_per_frame,
        max_frames=extraction.max_frames,
        metashape_exe=config.metashape_exe,
        backend=backend,
        colmap_exe=config.colmap_exe,
        colmap_density_preset=config.colmap_density_preset,
        colmap_use_gpu=config.colmap_use_gpu,
        run_lichtfield=config.run_lichtfield,
        lichtfield_exe=config.lichtfield_exe,
        lichtfield_point_count=config.lichtfield_point_count,
        lichtfield_bilateral_grid=config.lichtfield_bilateral_grid,
        run_lfs_densify=config.run_lfs_densify,
        lfs_densify_python=config.lfs_densify_python,
        lfs_densify_plugin=config.lfs_densify_plugin,
        lfs_densify_roma=config.lfs_densify_roma,
        lfs_densify_num_refs=config.lfs_densify_num_refs,
        lfs_densify_max_points=config.lfs_densify_max_points,
        track_extraction_settings=track_extraction_settings,
    )


def run_workbench_pipeline(config: WorkbenchRunConfig, sink=None, runner=run_multi_track_pipeline):
    sink = sink or WorkbenchEventSink()
    try:
        job = build_pipeline_job(config)
        result = runner(job, sink.progress, sink.preview, sink.log)
        sink.done(result)
        return result
    except Exception as exc:
        sink.error(exc)
        raise
