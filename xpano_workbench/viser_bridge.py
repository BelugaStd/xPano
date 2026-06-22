from pathlib import Path
import tempfile
import time
import uuid

from xpano_workbench.reconstruction_scene import ReconstructionScene


def _points_arrays(points):
    import numpy as np

    xyz = np.array([point.xyz for point in points], dtype=np.float32)
    rgb = np.array([point.rgb for point in points], dtype=np.uint8)
    if xyz.size == 0:
        xyz = np.zeros((0, 3), dtype=np.float32)
        rgb = np.zeros((0, 3), dtype=np.uint8)
    return xyz, rgb


def build_viser_html(scene: ReconstructionScene, compare_dense=False):
    import numpy as np
    import viser

    server = viser.ViserServer(verbose=False)
    server.scene.world_axes.visible = True
    server.scene.configure_default_lights()
    if compare_dense and scene.has_dense_comparison:
        sparse_xyz, sparse_rgb = _points_arrays(scene.sparse_points)
        dense_xyz, dense_rgb = _points_arrays(scene.dense_points)
        server.scene.add_point_cloud(
            "/before/sparse_points",
            sparse_xyz - np.array([2.5, 0.0, 0.0], dtype=np.float32),
            sparse_rgb,
            point_size=0.018,
            point_shape="rounded",
            point_shading="flat",
        )
        server.scene.add_point_cloud(
            "/after/dense_points",
            dense_xyz + np.array([2.5, 0.0, 0.0], dtype=np.float32),
            dense_rgb,
            point_size=0.012,
            point_shape="rounded",
            point_shading="flat",
        )
        server.scene.add_label("/before/label", "Before densify", position=(-2.5, 0.0, 0.0))
        server.scene.add_label("/after/label", "After densify", position=(2.5, 0.0, 0.0))
    else:
        points = scene.final_points
        xyz, rgb = _points_arrays(points)
        server.scene.add_point_cloud(
            "/reconstruction/points",
            xyz,
            rgb,
            point_size=0.014 if scene.has_dense_comparison else 0.02,
            point_shape="rounded",
            point_shading="flat",
        )

    camera_positions = []
    for index, camera in enumerate(scene.cameras):
        position = camera.position
        camera_positions.append(position)
        server.scene.add_camera_frustum(
            f"/cameras/{index:05d}",
            fov=camera.fov,
            aspect=camera.aspect,
            scale=0.18,
            line_width=1.5,
            color=(96, 165, 250),
            wxyz=camera.wxyz,
            position=position,
        )
    if len(camera_positions) >= 2:
        points = np.array(camera_positions, dtype=np.float32)
        segments = np.stack([points[:-1], points[1:]], axis=1)
        server.scene.add_line_segments(
            "/cameras/path",
            points=segments,
            colors=(34, 197, 94),
            line_width=2.0,
        )
    html = server.scene.as_html(dark_mode=True)
    stop = getattr(server, "stop", None)
    if callable(stop):
        stop()
    return html


def write_viser_html(scene: ReconstructionScene, compare_dense=False, output_path=None):
    output_path = (
        Path(output_path)
        if output_path
        else Path(tempfile.gettempdir()) / f"xpano_viser_scene_{time.time_ns()}_{uuid.uuid4().hex[:8]}.html"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_viser_html(scene, compare_dense=compare_dense), encoding="utf-8")
    return output_path
