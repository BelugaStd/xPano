import math
from dataclasses import dataclass
from pathlib import Path

from scripts.colmap_backend import (
    _qvec_to_rotmat,
    find_sparse_model_path,
    read_colmap_cameras,
    read_colmap_images,
    read_colmap_points3d_file,
)
from scripts.colmap_dense_merge import read_binary_little_endian_ply_vertices


@dataclass(frozen=True)
class ColoredPoint:
    xyz: tuple[float, float, float]
    rgb: tuple[int, int, int]


@dataclass(frozen=True)
class CameraPose:
    name: str
    position: tuple[float, float, float]
    wxyz: tuple[float, float, float, float]
    fov: float
    aspect: float


@dataclass(frozen=True)
class ReconstructionScene:
    sparse_points: tuple[ColoredPoint, ...]
    dense_points: tuple[ColoredPoint, ...]
    cameras: tuple[CameraPose, ...]
    sparse_path: Path | None = None
    dense_path: Path | None = None

    @property
    def has_dense_comparison(self):
        return bool(self.dense_points)

    @property
    def final_points(self):
        return self.dense_points or self.sparse_points


def _sample_sequence(items, max_items):
    items = list(items)
    if max_items <= 0 or len(items) <= max_items:
        return tuple(items)
    step = len(items) / max_items
    return tuple(items[int(index * step)] for index in range(max_items))


def _point_from_colmap(point):
    return ColoredPoint(
        xyz=tuple(float(value) for value in point["xyz"]),
        rgb=tuple(int(value) for value in point["rgb"]),
    )


def _point_from_ply_vertex(vertex):
    return ColoredPoint(
        xyz=tuple(float(value) for value in vertex["xyz"]),
        rgb=tuple(int(value) for value in vertex["rgb"]),
    )


def _read_points_file(path, max_points):
    points = (_point_from_colmap(point) for point in read_colmap_points3d_file(path))
    return _sample_sequence(points, max_points)


def _read_dense_ply(path, max_points):
    points = (_point_from_ply_vertex(vertex) for vertex in read_binary_little_endian_ply_vertices(path))
    return _sample_sequence(points, max_points)


def _camera_center(qvec, tvec):
    rot = _qvec_to_rotmat(qvec)
    return tuple(
        -sum(rot[col][row] * tvec[col] for col in range(3))
        for row in range(3)
    )


def _camera_fov_and_aspect(camera):
    width = max(float(camera.get("width", 1)), 1.0)
    height = max(float(camera.get("height", 1)), 1.0)
    params = tuple(float(value) for value in camera.get("params", ()))
    fy = params[1] if len(params) > 1 and params[1] > 0 else max(width, height)
    return 2.0 * math.atan2(height / 2.0, fy), width / height


def _camera_pose_from_colmap(image, cameras):
    camera = cameras.get(image["camera_id"], {})
    fov, aspect = _camera_fov_and_aspect(camera)
    qw, qx, qy, qz = image["qvec"]
    return CameraPose(
        name=image["name"],
        position=_camera_center(image["qvec"], image["tvec"]),
        wxyz=(float(qw), float(-qx), float(-qy), float(-qz)),
        fov=float(fov),
        aspect=float(aspect),
    )


def resolve_colmap_scene_root(path):
    path = Path(path)
    candidates = [
        path,
        path.parent,
        path.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "sparse" / "0" / "cameras.bin").exists():
            return candidate
        if all((candidate / name).exists() for name in ["cameras.bin", "images.bin", "points3D.bin"]):
            return candidate.parent.parent
        if (candidate / "colmap" / "sparse" / "0" / "cameras.bin").exists():
            return candidate
        if (candidate / "colmap" / "snapshots" / "0" / "cameras.bin").exists():
            return candidate
        if (candidate / "snapshots" / "0" / "cameras.bin").exists():
            return candidate
    raise FileNotFoundError(f"No COLMAP scene root was found for {path}")


def _resolve_sparse_model(output_dir, prefer_snapshots=False):
    output_dir = resolve_colmap_scene_root(output_dir)
    sparse_dirs = []
    if prefer_snapshots:
        sparse_dirs.extend([
            output_dir / "colmap" / "snapshots",
            output_dir / "snapshots",
        ])
    sparse_dirs.extend([output_dir / "sparse", output_dir / "colmap" / "sparse"])
    for sparse_dir in sparse_dirs:
        if sparse_dir.exists():
            try:
                return find_sparse_model_path(sparse_dir)
            except Exception:
                pass
    raise FileNotFoundError(f"No COLMAP sparse model was found under {output_dir}")


def load_reconstruction_scene(output_dir, max_sparse_points=120_000, max_dense_points=220_000, prefer_snapshots=False):
    sparse_model = _resolve_sparse_model(output_dir, prefer_snapshots=prefer_snapshots)
    points_path = sparse_model / "points3D.bin"
    backup_path = sparse_model / "points3D_sparse_original.bin"
    dense_bin_path = sparse_model / "points3D_dense.bin"
    dense_ply_path = sparse_model / "points3D_dense.ply"

    sparse_source = backup_path if backup_path.exists() else points_path
    sparse_points = _read_points_file(sparse_source, max_sparse_points)
    dense_points = ()
    dense_path = None
    if backup_path.exists():
        dense_points = _read_points_file(points_path, max_dense_points)
        dense_path = points_path
    elif dense_bin_path.exists():
        dense_points = _read_points_file(dense_bin_path, max_dense_points)
        dense_path = dense_bin_path
    elif dense_ply_path.exists():
        ply_points = _read_dense_ply(dense_ply_path, max_dense_points)
        dense_points = _sample_sequence([*sparse_points, *ply_points], max_dense_points)
        dense_path = dense_ply_path

    cameras = read_colmap_cameras(sparse_model)
    images = read_colmap_images(sparse_model)
    camera_poses = tuple(_camera_pose_from_colmap(image, cameras) for image in images)
    return ReconstructionScene(
        sparse_points=sparse_points,
        dense_points=tuple(dense_points),
        cameras=camera_poses,
        sparse_path=sparse_source,
        dense_path=dense_path,
    )
