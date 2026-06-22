import tempfile
import unittest
from pathlib import Path

from scripts.colmap_backend import (
    PINHOLE_MODEL_ID,
    write_colmap_cameras,
    write_colmap_images,
    write_colmap_points3d,
)
from xpano_workbench.reconstruction_scene import load_reconstruction_scene, resolve_colmap_scene_root


class ReconstructionSceneTests(unittest.TestCase):
    def _write_minimal_sparse_model(self, root, points):
        sparse = Path(root) / "sparse" / "0"
        self._write_sparse_model_at(sparse, points)
        return sparse

    def _write_sparse_model_at(self, sparse, points, image_count=1):
        sparse = Path(sparse)
        write_colmap_cameras(
            sparse / "cameras.bin",
            [
                {
                    "id": 1,
                    "model_id": PINHOLE_MODEL_ID,
                    "width": 1920,
                    "height": 1080,
                    "params": (900.0, 900.0, 960.0, 540.0),
                }
            ],
        )
        write_colmap_images(
            sparse / "images.bin",
            [
                {
                    "id": image_id,
                    "qvec": (1.0, 0.0, 0.0, 0.0),
                    "tvec": (-float(image_id), -2.0, -3.0),
                    "camera_id": 1,
                    "name": f"{image_id:06d}.jpg",
                    "points2d": [],
                }
                for image_id in range(1, image_count + 1)
            ],
        )
        write_colmap_points3d(sparse / "points3D.bin", points)
        return sparse

    def test_loads_colored_points_and_camera_centers_from_colmap_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_minimal_sparse_model(
                tmp,
                [
                    {
                        "id": 1,
                        "xyz": (1.0, 2.0, 3.0),
                        "rgb": (10, 20, 30),
                        "error": 0.5,
                        "track": [],
                    }
                ],
            )

            scene = load_reconstruction_scene(tmp)

        self.assertEqual(len(scene.sparse_points), 1)
        self.assertEqual(scene.sparse_points[0].rgb, (10, 20, 30))
        self.assertEqual(len(scene.cameras), 1)
        self.assertEqual(scene.cameras[0].position, (1.0, 2.0, 3.0))
        self.assertFalse(scene.has_dense_comparison)

    def test_detects_before_after_densification_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            sparse = self._write_minimal_sparse_model(
                tmp,
                [
                    {
                        "id": 1,
                        "xyz": (0.0, 0.0, 0.0),
                        "rgb": (255, 0, 0),
                        "error": 1.0,
                        "track": [],
                    },
                    {
                        "id": 2,
                        "xyz": (1.0, 0.0, 0.0),
                        "rgb": (0, 255, 0),
                        "error": 1.0,
                        "track": [],
                    },
                ],
            )
            (sparse / "points3D_sparse_original.bin").write_bytes((sparse / "points3D.bin").read_bytes())
            write_colmap_points3d(
                sparse / "points3D.bin",
                [
                    {
                        "id": 1,
                        "xyz": (0.0, 0.0, 0.0),
                        "rgb": (255, 0, 0),
                        "error": 1.0,
                        "track": [],
                    },
                    {
                        "id": 2,
                        "xyz": (1.0, 0.0, 0.0),
                        "rgb": (0, 255, 0),
                        "error": 1.0,
                        "track": [],
                    },
                    {
                        "id": 3,
                        "xyz": (2.0, 0.0, 0.0),
                        "rgb": (0, 0, 255),
                        "error": 1.0,
                        "track": [],
                    },
                ],
            )

            scene = load_reconstruction_scene(tmp)

        self.assertTrue(scene.has_dense_comparison)
        self.assertEqual(len(scene.sparse_points), 2)
        self.assertEqual(len(scene.dense_points), 3)
        self.assertEqual(scene.final_points[-1].rgb, (0, 0, 255))

    def test_resolves_external_colmap_root_from_sparse_zero_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            sparse = self._write_minimal_sparse_model(tmp, [])

            self.assertEqual(resolve_colmap_scene_root(sparse), Path(tmp))
            self.assertEqual(resolve_colmap_scene_root(Path(tmp)), Path(tmp))

    def test_loads_best_sparse_model_for_incremental_colmap_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_sparse_model_at(root / "colmap" / "sparse" / "0", [], image_count=1)
            self._write_sparse_model_at(
                root / "colmap" / "sparse" / "1",
                [
                    {
                        "id": 1,
                        "xyz": (1.0, 2.0, 3.0),
                        "rgb": (10, 20, 30),
                        "error": 0.5,
                        "track": [],
                    }
                ],
                image_count=3,
            )

            scene = load_reconstruction_scene(root)

        self.assertEqual(len(scene.cameras), 3)
        self.assertEqual(len(scene.sparse_points), 1)
        self.assertTrue(str(scene.sparse_path).replace("\\", "/").endswith("colmap/sparse/1/points3D.bin"))

    def test_can_prefer_colmap_mapper_snapshots_for_live_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_sparse_model_at(root / "colmap" / "sparse" / "0", [], image_count=3)
            self._write_sparse_model_at(
                root / "colmap" / "snapshots" / "0",
                [
                    {
                        "id": 1,
                        "xyz": (1.0, 2.0, 3.0),
                        "rgb": (10, 20, 30),
                        "error": 0.5,
                        "track": [],
                    }
                ],
                image_count=458,
            )

            scene = load_reconstruction_scene(root, prefer_snapshots=True)

        self.assertEqual(len(scene.cameras), 458)
        self.assertTrue(str(scene.sparse_path).replace("\\", "/").endswith("colmap/snapshots/0/points3D.bin"))

    def test_live_preview_can_load_snapshot_before_final_sparse_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_sparse_model_at(
                root / "colmap" / "snapshots" / "0",
                [
                    {
                        "id": 1,
                        "xyz": (1.0, 2.0, 3.0),
                        "rgb": (10, 20, 30),
                        "error": 0.5,
                        "track": [],
                    }
                ],
                image_count=42,
            )

            self.assertEqual(resolve_colmap_scene_root(root), root)
            scene = load_reconstruction_scene(root, prefer_snapshots=True)

        self.assertEqual(len(scene.cameras), 42)
        self.assertTrue(str(scene.sparse_path).replace("\\", "/").endswith("colmap/snapshots/0/points3D.bin"))


if __name__ == "__main__":
    unittest.main()
