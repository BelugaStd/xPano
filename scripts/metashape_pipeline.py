import argparse
import json
import math
import os
import sys
from pathlib import Path

try:
    from scripts.metashape_runtime_env import (
        METASHAPE_SITE_PACKAGES_FLAG,
        activate_metashape_runtime,
        metashape_site_packages_from_argv,
    )
except ImportError:
    from metashape_runtime_env import (
        METASHAPE_SITE_PACKAGES_FLAG,
        activate_metashape_runtime,
        metashape_site_packages_from_argv,
    )

activate_metashape_runtime(metashape_site_packages_from_argv())

import Metashape

import align_ground_plane
import export_colmap

try:
    from scripts.component_selection import component_inventory, select_component_key
except ImportError:
    from component_selection import component_inventory, select_component_key

try:
    from scripts.metashape_alignment_modes import (
        ALIGNMENT_MODE_BACKBONE,
        ALIGNMENT_MODE_MIXED,
        SUPPORTED_ALIGNMENT_MODES,
        normalize_alignment_mode,
    )
except ImportError:
    from metashape_alignment_modes import (
        ALIGNMENT_MODE_BACKBONE,
        ALIGNMENT_MODE_MIXED,
        SUPPORTED_ALIGNMENT_MODES,
        normalize_alignment_mode,
    )


FRAME_TRACK_TYPES = {"ordinary_video", "standard_photos", "aerial_photos"}
FRAME_CAMERA_PROFILE_FOV = {
    "standard": 70.0,
    "wide": 105.0,
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(METASHAPE_SITE_PACKAGES_FLAG, help=argparse.SUPPRESS)
    p.add_argument("--input-root")
    p.add_argument("--manifest")
    p.add_argument("--project", required=True)
    p.add_argument("--export-dir", required=True)
    p.add_argument("--max-frames", type=int, default=0)
    p.add_argument("--keypoint-limit", type=int, default=40000)
    p.add_argument("--tiepoint-limit", type=int, default=0)
    p.add_argument("--alignment-mode", default=ALIGNMENT_MODE_BACKBONE, choices=sorted(SUPPORTED_ALIGNMENT_MODES))
    p.add_argument("--up-axis", default="+Y")
    p.add_argument("--component-key")
    return p.parse_args(sys.argv[1:])


def emit_progress(value):
    print(f"PROGRESS:{int(value)}", flush=True)


def emit_pipeline_event(payload):
    print("PIPELINE_EVENT:" + json.dumps(payload, ensure_ascii=True), flush=True)


def emit_stage(stage, message, percent, phase="align", current=None, total=None):
    emit_progress(percent)
    payload = {
        "phase": phase,
        "stage": stage,
        "percent": percent,
        "phasePercent": max(0, min(100, round((percent - 35) / 65 * 100))) if phase == "align" else percent,
        "message": message,
    }
    if current is not None:
        payload["current"] = int(current)
    if total is not None:
        payload["total"] = int(total)
    emit_pipeline_event(payload)


def emit_alignment_rate(chunk, percent=95):
    cameras = list(chunk.cameras)
    total = len(cameras)
    aligned = len([camera for camera in cameras if camera.transform])
    rate = (aligned / total * 100.0) if total else 0.0
    emit_pipeline_event({
        "phase": "align",
        "stage": "align.rate",
        "percent": percent,
        "phasePercent": 100 if total else 0,
        "message": f"Alignment rate {aligned}/{total} ({rate:.1f}%)",
        "alignedCameras": aligned,
        "totalCameras": total,
        "alignmentRate": rate,
    })
    return {"aligned": aligned, "total": total, "rate": rate}


def ensure_project(project_path):
    doc = Metashape.app.document
    doc.save(str(project_path))
    return doc


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def copy_sensor_geometry(dst, src):
    if not src:
        return
    dst.width = src.width
    dst.height = src.height
    dst.pixel_width = src.pixel_width
    dst.pixel_height = src.pixel_height
    dst.focal_length = src.focal_length


def configure_fisheye_sensor(sensor):
    sensor.type = Metashape.Sensor.Type.Fisheye
    sensor.pixel_width = 0.0024
    sensor.pixel_height = 0.0024
    sensor.focal_length = 2.5
    sensor.fixed_params = ["B1", "B2", "K4"]
    calib = sensor.calibration
    if calib:
        try:
            calib.type = Metashape.Sensor.Type.Fisheye
        except Exception:
            pass
        calib.b1 = 0
        calib.b2 = 0
        calib.k4 = 0


def _type_text(value):
    return str(value or "").lower()


def _is_frame_like_source(src_sensor):
    if not src_sensor:
        return False
    sensor_text = _type_text(getattr(src_sensor, "type", ""))
    calib_text = _type_text(getattr(getattr(src_sensor, "calibration", None), "type", ""))
    non_frame_tokens = ("fisheye", "spherical", "cylindrical", "equisolid", "equidistant", "orthographic", "stereographic")
    return not any(token in sensor_text or token in calib_text for token in non_frame_tokens)


def _copy_basic_frame_intrinsics(dst_calib, src_calib):
    if not src_calib:
        return
    for name in ["f", "cx", "cy"]:
        try:
            value = getattr(src_calib, name)
        except Exception:
            continue
        if value is None:
            continue
        try:
            setattr(dst_calib, name, value)
        except Exception:
            pass


def _copy_frame_distortion(dst_calib, src_calib):
    if not src_calib:
        return
    for name in ["b1", "b2", "k1", "k2", "k3", "k4", "p1", "p2"]:
        try:
            value = getattr(src_calib, name)
        except Exception:
            continue
        if value is None:
            continue
        try:
            setattr(dst_calib, name, value)
        except Exception:
            pass


def normalize_frame_camera_profile(value):
    profile = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "normal": "standard",
        "default": "standard",
        "std": "standard",
        "wide_angle": "wide",
        "wideangle": "wide",
    }
    return aliases.get(profile, profile) if profile in FRAME_CAMERA_PROFILE_FOV or profile in aliases else None


def initial_focal_from_horizontal_fov(width, fov_degrees):
    width = max(1.0, float(width or 1.0))
    fov = max(1.0, min(179.0, float(fov_degrees or 70.0)))
    return (width * 0.5) / math.tan(math.radians(fov * 0.5))


def apply_frame_camera_profile(calib, sensor, camera_profile):
    profile = normalize_frame_camera_profile(camera_profile)
    if not profile:
        return
    width = int(getattr(sensor, "width", 0) or getattr(calib, "width", 0) or 0)
    height = int(getattr(sensor, "height", 0) or getattr(calib, "height", 0) or 0)
    calib.width = width
    calib.height = height
    calib.f = initial_focal_from_horizontal_fov(width, FRAME_CAMERA_PROFILE_FOV[profile])
    calib.cx = 0
    calib.cy = 0


def configure_frame_sensor(sensor, source_sensor=None, camera_profile=None):
    sensor.type = Metashape.Sensor.Type.Frame
    try:
        sensor.fixed_params = []
    except Exception:
        pass

    calib = Metashape.Calibration()
    try:
        calib.type = Metashape.Sensor.Type.Frame
    except Exception:
        pass
    calib.width = sensor.width
    calib.height = sensor.height

    if camera_profile:
        apply_frame_camera_profile(calib, sensor, camera_profile)
    else:
        _copy_basic_frame_intrinsics(calib, getattr(source_sensor, "calibration", None))
    if not camera_profile and _is_frame_like_source(source_sensor):
        _copy_frame_distortion(calib, source_sensor.calibration)

    try:
        sensor.calibration = calib
    except Exception:
        pass
    try:
        sensor.user_calib = calib
    except Exception:
        pass


def make_track_sensor(chunk, source_camera, label, sensor_type, camera_profile=None):
    sensor = chunk.addSensor()
    sensor.label = label
    source_sensor = source_camera.sensor if source_camera else None
    copy_sensor_geometry(sensor, source_sensor)
    if sensor_type == Metashape.Sensor.Type.Fisheye:
        configure_fisheye_sensor(sensor)
    elif sensor_type == Metashape.Sensor.Type.Frame:
        configure_frame_sensor(sensor, source_sensor, camera_profile=camera_profile)
    else:
        sensor.type = sensor_type
    return sensor


def camera_path_name(camera):
    try:
        return Path(camera.photo.path).name.lower()
    except Exception:
        return camera.label.lower()


def camera_key(camera):
    return int(getattr(camera, "key", camera))


def camera_keys(cameras):
    # WARN: Metashape matchPhotos/alignCameras expect camera keys, not Camera objects.
    return [camera_key(camera) for camera in cameras]


def normalized_photo_path(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def add_photos_get_new(chunk, paths, group_key=None):
    requested_paths = [str(path) for path in paths]
    existing_keys = {camera_key(camera) for camera in chunk.cameras}
    kwargs = {"load_xmp_accuracy": True}
    if group_key is not None:
        kwargs["group"] = group_key
    # WARN: Metashape may reorder chunk.cameras during addPhotos; camera identity must come from stable keys.
    chunk.addPhotos(requested_paths, **kwargs)
    imported = [camera for camera in chunk.cameras if camera_key(camera) not in existing_keys]
    if len(imported) != len(requested_paths):
        raise RuntimeError(
            "Metashape imported an unexpected camera count: "
            f"requested={len(requested_paths)} imported={len(imported)}"
        )

    requested_normalized = sorted(normalized_photo_path(path) for path in requested_paths)
    try:
        imported_normalized = sorted(normalized_photo_path(camera.photo.path) for camera in imported)
    except Exception as exc:
        raise RuntimeError("Metashape imported a camera without a readable photo path") from exc
    if imported_normalized != requested_normalized:
        missing = sorted(set(requested_normalized) - set(imported_normalized))
        unexpected = sorted(set(imported_normalized) - set(requested_normalized))
        raise RuntimeError(
            "Metashape imported cameras with unexpected photo paths: "
            f"missing={[Path(path).name for path in missing[:5]]} "
            f"unexpected={[Path(path).name for path in unexpected[:5]]}"
        )
    return imported


def import_panorama_track(chunk, track):
    station_groups = []
    imported = []
    left_sensor = None
    right_sensor = None
    left_label = track.get("left_sensor_label", f"{track['track_id']}_left")
    right_label = track.get("right_sensor_label", f"{track['track_id']}_right")

    for frame in track.get("frames", []):
        group = chunk.addCameraGroup()
        group.label = frame.get("group_label", frame.get("frame_id", track["track_id"]))
        group.type = Metashape.CameraGroup.Type.Folder
        station_groups.append(group)

        paths = [frame["left"], frame["right"]]
        new_cameras = add_photos_get_new(chunk, paths, group_key=group.key)
        imported.extend(new_cameras)
        for camera in new_cameras:
            name = camera_path_name(camera)
            if name == Path(frame["left"]).name.lower() or name.endswith("_left.jpg"):
                if left_sensor is None:
                    left_sensor = make_track_sensor(chunk, camera, left_label, Metashape.Sensor.Type.Fisheye)
                camera.sensor = left_sensor
            elif name == Path(frame["right"]).name.lower() or name.endswith("_right.jpg"):
                if right_sensor is None:
                    right_sensor = make_track_sensor(chunk, camera, right_label, Metashape.Sensor.Type.Fisheye)
                camera.sensor = right_sensor

    return station_groups, imported


def import_photo_track(chunk, track):
    group = chunk.addCameraGroup()
    group.label = track.get("group_label", f"{track['track_id']}_photos")
    group.type = Metashape.CameraGroup.Type.Folder

    photo_sensors = track.get("photo_sensors") or []
    if photo_sensors:
        imported = []
        for sensor_group in photo_sensors:
            photos = sensor_group.get("photos", [])
            if not photos:
                continue
            new_cameras = add_photos_get_new(chunk, photos, group_key=group.key)
            if not new_cameras:
                continue
            cameras_by_geometry = {}
            for camera in new_cameras:
                source_sensor = camera.sensor
                if source_sensor is None:
                    raise RuntimeError(
                        f"Photo sensor group has no source sensor: {sensor_group.get('sensor_label', track['track_id'])}"
                    )
                geometry = (
                    source_sensor.type,
                    int(getattr(source_sensor, "width", 0) or 0),
                    int(getattr(source_sensor, "height", 0) or 0),
                )
                cameras_by_geometry.setdefault(geometry, []).append(camera)
            base_label = sensor_group.get(
                "sensor_label",
                track.get("sensor_label", f"{track['track_id']}_frame"),
            )
            if len(cameras_by_geometry) > 1:
                geometry_preview = list(cameras_by_geometry)[:8]
                omitted_count = len(cameras_by_geometry) - len(geometry_preview)
                omitted_suffix = f" (+{omitted_count} more)" if omitted_count else ""
                print(
                    ">>> Splitting photo sensor group by imported geometry: "
                    f"group={base_label!r} partitions={len(cameras_by_geometry)} "
                    f"geometries={geometry_preview}{omitted_suffix}",
                    flush=True,
                )
            for geometry_index, geometry_cameras in enumerate(cameras_by_geometry.values()):
                sensor_label = (
                    base_label if geometry_index == 0 else f"{base_label}_actual_{geometry_index + 1:02d}"
                )
                sensor = make_track_sensor(
                    chunk,
                    geometry_cameras[0],
                    sensor_label,
                    Metashape.Sensor.Type.Frame,
                    camera_profile=sensor_group.get("camera_profile") or track.get("camera_profile"),
                )
                for camera in geometry_cameras:
                    camera.sensor = sensor
            imported.extend(new_cameras)
        return imported

    photos = track.get("photos", [])
    if not photos:
        return []
    new_cameras = add_photos_get_new(chunk, photos, group_key=group.key)
    sensors_by_size = {}
    base_label = track.get("sensor_label", f"{track['track_id']}_frame")
    for camera in new_cameras:
        src = camera.sensor
        key = (getattr(src, "width", 0), getattr(src, "height", 0))
        if key not in sensors_by_size:
            suffix = "" if not sensors_by_size else f"_{len(sensors_by_size) + 1:02d}"
            sensor = make_track_sensor(chunk, camera, f"{base_label}{suffix}", Metashape.Sensor.Type.Frame)
            sensors_by_size[key] = sensor
        camera.sensor = sensors_by_size[key]
    return new_cameras


def import_manifest_tracks(chunk, manifest):
    station_groups = []
    for track in manifest.get("tracks", []):
        track_type = track.get("track_type")
        if track_type == "panorama_video":
            groups, _ = import_panorama_track(chunk, track)
            station_groups.extend(groups)
        elif track_type in {"ordinary_video", "standard_photos", "aerial_photos"}:
            import_photo_track(chunk, track)
        else:
            raise RuntimeError(f"Unsupported track_type: {track_type}")
    prune_unused_sensors(chunk)
    return station_groups


def import_manifest_tracks_by_type(chunk, manifest, track_types):
    station_groups = []
    imported_tracks = []
    for track in manifest.get("tracks", []):
        track_type = track.get("track_type")
        if track_type not in track_types:
            continue
        if track_type == "panorama_video":
            groups, cameras = import_panorama_track(chunk, track)
            station_groups.extend(groups)
        elif track_type in FRAME_TRACK_TYPES:
            cameras = import_photo_track(chunk, track)
        else:
            raise RuntimeError(f"Unsupported track_type: {track_type}")
        imported_tracks.append({"track": track, "cameras": cameras})
    prune_unused_sensors(chunk)
    return station_groups, imported_tracks


def _match_kwargs(args, cameras=None, *, keep_keypoints=True, reset_matches=False):
    kwargs = {
        "downscale": 1,
        "generic_preselection": True,
        "reference_preselection": False,
        "filter_stationary_points": False,
        "guided_matching": False,
        "keep_keypoints": bool(keep_keypoints),
        "reset_matches": bool(reset_matches),
        "keypoint_limit": max(0, int(args.keypoint_limit)),
        "tiepoint_limit": max(0, int(args.tiepoint_limit)),
    }
    if cameras is not None:
        kwargs["cameras"] = camera_keys(cameras)
    return kwargs


def set_groups_type(groups, group_type):
    for group in groups:
        try:
            group.type = group_type
        except Exception:
            pass


def _camera_detail(camera):
    sensor = getattr(camera, "sensor", None)
    return (
        f"camera={getattr(camera, 'label', '<unnamed>')!r} "
        f"key={camera_key(camera)} "
        f"sensor={getattr(sensor, 'label', '<none>')!r} "
        f"sensor_key={getattr(sensor, 'key', '<none>')} "
        f"sensor_type={getattr(sensor, 'type', '<none>')} "
        f"size={getattr(sensor, 'width', '<none>')}x{getattr(sensor, 'height', '<none>')}"
    )


def validate_backbone_camera_sets(chunk, pano_cameras, frame_cameras):
    chunk_cameras = list(chunk.cameras)
    combined = list(pano_cameras) + list(frame_cameras)
    if not chunk_cameras:
        raise RuntimeError("No extracted frame images found")

    chunk_keys = [camera_key(camera) for camera in chunk_cameras]
    combined_keys = [camera_key(camera) for camera in combined]
    if len(chunk_keys) != len(set(chunk_keys)):
        raise RuntimeError("Metashape imported duplicate camera keys into the chunk")
    if len(combined_keys) != len(set(combined_keys)):
        raise RuntimeError("Panorama and flat camera sets overlap or contain duplicate camera keys")
    if set(chunk_keys) != set(combined_keys):
        raise RuntimeError(
            "Imported camera sets do not cover the fresh Metashape chunk: "
            f"chunk={len(chunk_keys)} panorama={len(pano_cameras)} flat={len(frame_cameras)}"
        )

    pano_sensor_keys = set()
    frame_sensor_keys = set()
    for cameras, expected_type, sensor_keys, kind in (
        (pano_cameras, Metashape.Sensor.Type.Fisheye, pano_sensor_keys, "panorama"),
        (frame_cameras, Metashape.Sensor.Type.Frame, frame_sensor_keys, "flat"),
    ):
        for camera in cameras:
            sensor = getattr(camera, "sensor", None)
            if sensor is None:
                raise RuntimeError(f"{kind.title()} camera has no sensor: {_camera_detail(camera)}")
            if sensor.type != expected_type:
                raise RuntimeError(
                    f"{kind.title()} camera has incompatible sensor type; "
                    f"expected={expected_type}, {_camera_detail(camera)}"
                )
            width = int(getattr(sensor, "width", 0) or 0)
            height = int(getattr(sensor, "height", 0) or 0)
            if width <= 0 or height <= 0:
                raise RuntimeError(f"{kind.title()} camera sensor has invalid dimensions: {_camera_detail(camera)}")
            sensor_keys.add(getattr(sensor, "key", id(sensor)))
    if pano_sensor_keys & frame_sensor_keys:
        raise RuntimeError("Panorama and flat cameras share a Metashape sensor")


def emit_backbone_camera_summary(chunk, pano_cameras, frame_cameras):
    counts = {}
    for camera in chunk.cameras:
        sensor = camera.sensor
        key = getattr(sensor, "key", id(sensor))
        if key not in counts:
            counts[key] = {"sensor": sensor, "count": 0}
        counts[key]["count"] += 1
    print(
        ">>> Metashape backbone single-pass match: "
        f"total={len(chunk.cameras)} panorama={len(pano_cameras)} flat={len(frame_cameras)} "
        "keep_keypoints=False reset_matches=False",
        flush=True,
    )
    limit = 20
    for entry in list(counts.values())[:limit]:
        sensor = entry["sensor"]
        print(
            ">>> Metashape sensor: "
            f"label={sensor.label!r} key={sensor.key} type={sensor.type} "
            f"size={sensor.width}x{sensor.height} cameras={entry['count']}",
            flush=True,
        )
    if len(counts) > limit:
        print(f">>> Metashape sensor summary omitted {len(counts) - limit} additional sensors", flush=True)


def run_mixed_alignment(chunk, manifest, args):
    emit_stage("metashape.all.import", "正在导入全部素材", 42)
    station_groups = import_manifest_tracks(chunk, manifest)
    if not chunk.cameras:
        raise RuntimeError("No extracted frame images found")

    emit_stage("metashape.pano.station", "正在设置全景站点", 54)
    set_groups_type(station_groups, Metashape.CameraGroup.Type.Station)

    emit_stage("metashape.all.match", "正在联合匹配全部素材", 60)
    chunk.matchPhotos(**_match_kwargs(args))
    emit_stage("metashape.all.align", "正在联合求解全部相机", 75)
    chunk.alignCameras(adaptive_fitting=True)

    emit_stage("metashape.pano.release", "正在保持全景站点约束", 82)
    # WARN: Mixed-mode optimization must not remove the dual-fisheye shared-center constraint.
    emit_stage("metashape.all.optimize", "正在执行全局相机优化", 86)
    chunk.optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)
    return station_groups


def run_backbone_alignment(chunk, manifest, args):
    has_panorama = any(track.get("track_type") == "panorama_video" for track in manifest.get("tracks", []))
    has_frames = any(track.get("track_type") in FRAME_TRACK_TYPES for track in manifest.get("tracks", []))
    station_groups = []
    pano_cameras = []
    frame_cameras = []

    if has_panorama:
        emit_stage("metashape.pano.import", "正在导入全景双鱼眼与站点", 40)
        station_groups, pano_entries = import_manifest_tracks_by_type(chunk, manifest, {"panorama_video"})
        pano_cameras = [camera for entry in pano_entries for camera in entry["cameras"]]
    if has_frames:
        emit_stage("metashape.frame.import", "正在导入普通帧与照片", 46)
        _, frame_entries = import_manifest_tracks_by_type(chunk, manifest, FRAME_TRACK_TYPES)
        frame_cameras = [camera for entry in frame_entries for camera in entry["cameras"]]

    validate_backbone_camera_sets(chunk, pano_cameras, frame_cameras)
    if pano_cameras and not frame_cameras:
        emit_stage("metashape.pano.station", "Setting panorama Station constraints", 52)
        set_groups_type(station_groups, Metashape.CameraGroup.Type.Station)
        emit_stage("metashape.all.match", "Matching panorama materials", 58)
        chunk.matchPhotos(**_match_kwargs(args, keep_keypoints=False))
        emit_stage("metashape.pano.align", "Solving panorama cameras", 78)
        chunk.alignCameras(adaptive_fitting=True)
        emit_stage("metashape.pano.release", "Retaining panorama Station constraints", 82)
        emit_stage("metashape.pano.optimize", "Optimizing panorama cameras", 90)
        # WARN: Dual-fisheye pairs must remain Stations so bundle adjustment cannot split their shared center.
        chunk.optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)
        return station_groups
    if pano_cameras:
        emit_stage("metashape.pano.station", "正在设置全景站点", 52)
        set_groups_type(station_groups, Metashape.CameraGroup.Type.Station)

    emit_stage("metashape.all.match", "正在联合匹配全部素材", 55)
    # NOTE: Match every camera once, then stage alignment so Metashape never reuses mixed-resolution match state.
    emit_backbone_camera_summary(chunk, pano_cameras, frame_cameras)
    chunk.matchPhotos(**_match_kwargs(args, keep_keypoints=False))

    if pano_cameras:
        frame_enabled_states = [(camera, camera.enabled) for camera in frame_cameras]
        # NOTE: Keep unified matches but exclude flat cameras from the backbone solve on Metashape builds that otherwise alter it.
        try:
            for camera in frame_cameras:
                camera.enabled = False
            emit_stage("metashape.pano.align", "正在求解全景骨架", 74)
            chunk.alignCameras(cameras=camera_keys(pano_cameras), adaptive_fitting=True)
            unaligned_panoramas = [camera for camera in pano_cameras if camera.transform is None]
            if unaligned_panoramas:
                # NOTE: A second solve reuses existing matches; a second match would recreate the mixed-resolution crash path.
                print(
                    ">>> Retrying panorama solve with existing matches: "
                    f"unaligned={len(unaligned_panoramas)}/{len(pano_cameras)}",
                    flush=True,
                )
                chunk.alignCameras(cameras=camera_keys(unaligned_panoramas), adaptive_fitting=True)
            emit_stage("metashape.pano.release", "正在保持全景站点约束", 79)
            # WARN: Keep panorama groups as Stations while flat cameras are attached and globally optimized.
            emit_stage("metashape.pano.optimize", "正在优化全景骨架", 81)
            chunk.optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)
        finally:
            for camera, enabled in frame_enabled_states:
                camera.enabled = enabled

    if frame_cameras:
        emit_stage("metashape.frame.align", "正在增量求解平面相机", 87)
        chunk.alignCameras(cameras=camera_keys(frame_cameras), adaptive_fitting=True)
        emit_stage("metashape.all.optimize", "正在执行全局相机优化", 91)
        chunk.optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)
    return station_groups


def used_sensors(chunk):
    sensors = []
    seen = set()
    for camera in chunk.cameras:
        if camera.sensor and camera.sensor.key not in seen:
            sensors.append(camera.sensor)
            seen.add(camera.sensor.key)
    return sensors


def prune_unused_sensors(chunk):
    used = {sensor.key for sensor in used_sensors(chunk)}
    for sensor in list(chunk.sensors):
        if sensor.key not in used:
            try:
                chunk.remove(sensor)
            except Exception:
                pass


def import_legacy_frames(chunk, input_root, max_frames):
    frame_dirs = sorted(p for p in input_root.iterdir() if p.is_dir())
    if max_frames and max_frames > 0:
        frame_dirs = frame_dirs[: max_frames]
    if not frame_dirs:
        raise RuntimeError("No extracted frames found")

    station_groups = []
    for frame_dir in frame_dirs:
        image_paths = sorted(str(p) for p in frame_dir.glob("*.jpg"))
        if len(image_paths) < 2:
            continue
        group = chunk.addCameraGroup()
        group.label = frame_dir.name
        group.type = Metashape.CameraGroup.Type.Folder
        station_groups.append(group)
        chunk.addPhotos(image_paths[:2], group=group.key, load_xmp_accuracy=True)

    for sensor in chunk.sensors:
        configure_fisheye_sensor(sensor)
    return station_groups


def station_distances(chunk):
    distances = []
    for group in chunk.camera_groups:
        cameras = [camera for camera in chunk.cameras if camera.group == group and camera.transform]
        if len(cameras) != 2:
            continue
        centers = [chunk.transform.matrix.mulp(camera.center) for camera in cameras]
        delta = centers[0] - centers[1]
        distances.append(math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z))
    return distances


def alignment_type_metrics(chunk):
    panorama_cameras = [
        camera
        for camera in chunk.cameras
        if camera.sensor and camera.sensor.type == Metashape.Sensor.Type.Fisheye
    ]
    frame_cameras = [
        camera
        for camera in chunk.cameras
        if camera.sensor and camera.sensor.type == Metashape.Sensor.Type.Frame
    ]
    return {
        "panorama_cameras": len(panorama_cameras),
        "panorama_aligned": sum(camera.transform is not None for camera in panorama_cameras),
        "frame_cameras": len(frame_cameras),
        "frame_aligned": sum(camera.transform is not None for camera in frame_cameras),
    }


def write_alignment_summary(chunk, export_dir, project_path, alignment_mode=None, selected_component_key=None):
    aligned = [camera for camera in chunk.cameras if camera.transform is not None]
    type_metrics = alignment_type_metrics(chunk)
    distances = station_distances(chunk)
    lines = [
        "xPano Metashape alignment summary",
        f"project={project_path}",
        f"cameras={len(chunk.cameras)}",
        f"aligned={len(aligned)}",
        f"panorama_cameras={type_metrics['panorama_cameras']}",
        f"panorama_aligned={type_metrics['panorama_aligned']}",
        f"frame_cameras={type_metrics['frame_cameras']}",
        f"frame_aligned={type_metrics['frame_aligned']}",
        f"groups={len(chunk.camera_groups)}",
        f"sensors={len(used_sensors(chunk))}",
    ]
    if alignment_mode:
        lines.append(f"alignment_mode={alignment_mode}")
    if distances:
        lines.append(
            "station_baseline_min_max_avg="
            f"{min(distances):.9f},{max(distances):.9f},{(sum(distances) / len(distances)):.9f}"
        )
    for sensor in used_sensors(chunk):
        calib = sensor.calibration
        lines.append(
            "sensor="
            f"{sensor.label},type={sensor.type},size={sensor.width}x{sensor.height},"
            f"pixel={sensor.pixel_width},{sensor.pixel_height},focal={sensor.focal_length},"
            f"calib_f={getattr(calib, 'f', None)},fixed={list(sensor.fixed_params)}"
        )
    inventory = component_inventory(chunk.cameras, getattr(chunk, "components", None))
    selected_component_key = select_component_key(inventory, selected_component_key)
    warnings = []
    if len(inventory) > 1:
        warnings.append("Multiple Metashape components found; manual PSX alignment is recommended.")
    if aligned and len(aligned) < len(chunk.cameras):
        warnings.append("Some cameras were not aligned; the completed partial result remains exportable.")
    lines.extend([
        f"selected_component={selected_component_key or ''}",
        f"components={json.dumps(inventory, ensure_ascii=True)}",
    ])
    (export_dir / "xpano_alignment_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "aligned": len(aligned),
        "total": len(chunk.cameras),
        "rate": (len(aligned) / len(chunk.cameras) * 100.0) if chunk.cameras else 0.0,
        "components": inventory,
        "selectedComponentKey": selected_component_key,
        "warnings": warnings,
        **type_metrics,
    }


def export_project_outputs(export_dir, selected_component_key=None):
    emit_stage("export.images", "正在导出训练图像", 97, phase="export")
    export_colmap.run_mixed_export(
        str(export_dir),
        show_dialog=False,
        selected_component_key=selected_component_key,
    )
    emit_stage("export.colmap", "正在写出 COLMAP 模型", 99, phase="export")


def main():
    args = parse_args()
    project_path = Path(args.project)
    export_dir = Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    report_path = export_dir / "xpano_alignment_report.json"
    report_path.write_text(
        json.dumps({"schemaVersion": 1, "processSucceeded": False, "state": "running"}, indent=2),
        encoding="utf-8",
    )

    emit_stage("input.validate", "正在校验重建输入", 36)
    doc = Metashape.app.document
    emit_stage("metashape.project.create", "正在创建 Metashape 工程", 38)
    chunk = doc.addChunk()
    doc.chunk = chunk

    alignment_mode = None
    emit_progress(40)
    if args.manifest:
        manifest = load_manifest(args.manifest)
        mode = normalize_alignment_mode(args.alignment_mode)
        alignment_mode = mode
        print(f">>> Metashape alignment mode: {mode}", flush=True)
        if mode == ALIGNMENT_MODE_MIXED:
            run_mixed_alignment(chunk, manifest, args)
        else:
            run_backbone_alignment(chunk, manifest, args)
    elif args.input_root:
        station_groups = import_legacy_frames(chunk, Path(args.input_root), args.max_frames)
        if not chunk.cameras:
            raise RuntimeError("No extracted frame images found")
        set_groups_type(station_groups, Metashape.CameraGroup.Type.Station)
        emit_progress(55)
        set_groups_type(station_groups, Metashape.CameraGroup.Type.Station)
        emit_progress(60)
        chunk.matchPhotos(**_match_kwargs(args))
        emit_progress(75)
        chunk.alignCameras(adaptive_fitting=True)
        emit_progress(82)
        set_groups_type(station_groups, Metashape.CameraGroup.Type.Folder)
        chunk.optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)
        emit_progress(90)
    else:
        raise RuntimeError("Either --manifest or --input-root is required")

    emit_stage("metashape.project.save", "正在保存 Metashape 工程", 93)
    ensure_project(project_path)
    metrics = write_alignment_summary(
        chunk,
        export_dir,
        project_path,
        alignment_mode=alignment_mode,
        selected_component_key=args.component_key,
    )
    report = {
        "schemaVersion": 1,
        "processSucceeded": False,
        "state": "aligned",
        "projectPath": str(project_path),
        "totalCameras": metrics["total"],
        "alignedCameras": metrics["aligned"],
        "alignmentRate": metrics["rate"],
        "panoramaCameras": metrics["panorama_cameras"],
        "panoramaAligned": metrics["panorama_aligned"],
        "frameCameras": metrics["frame_cameras"],
        "frameAligned": metrics["frame_aligned"],
        "components": metrics["components"],
        "selectedComponentKey": metrics["selectedComponentKey"],
        "warnings": metrics["warnings"],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    emit_alignment_rate(chunk)

    print(">>> 自动地平面校正", flush=True)
    emit_stage("coordinate.auto_level", "正在自动校正地面方向", 96, phase="export")
    try:
        align_ground_plane.main(up_axis=args.up_axis)
    except Exception as exc:
        print(f"WARN: 地平面校正失败，继续导出: {exc}", flush=True)

    print(">>> 导出 COLMAP/Cubemap", flush=True)
    export_project_outputs(export_dir, metrics["selectedComponentKey"])
    report["processSucceeded"] = True
    report["state"] = "complete"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    emit_stage("output.validate", "正在验证输出完整性", 100, phase="export")


if __name__ == "__main__":
    main()
