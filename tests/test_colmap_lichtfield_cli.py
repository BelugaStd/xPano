import json
import tempfile
import unittest
from pathlib import Path

from scripts.colmap_backend import ColmapBackendConfig, ColmapCommandPlan, build_colmap_plan
from scripts.lichtfield_cli import LichtfieldStudioConfig, build_lichtfield_command


class ColmapBackendPlanTests(unittest.TestCase):
    def test_builds_colmap_command_plan_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "frame_left.jpg"
            right = root / "frame_right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            manifest = {
                "schema_version": 1,
                "workflow": "xpano_multi_track",
                "tracks": [
                    {
                        "track_id": "track_001_osmo",
                        "track_type": "panorama_video",
                        "device_label": "osmo",
                        "metashape_mode": "dual_fisheye_station",
                        "export_mode": "cubemap",
                        "frames": [
                            {
                                "frame_id": "frame_00001",
                                "group_label": "frame_00001",
                                "left": str(left),
                                "right": str(right),
                            }
                        ],
                    }
                ],
            }

            plan = build_colmap_plan(
                manifest,
                output_dir=root / "out",
                config=ColmapBackendConfig(colmap_exe="colmap.exe"),
            )

            self.assertIsInstance(plan, ColmapCommandPlan)
            self.assertEqual(plan.database_path.name, "database.db")
            self.assertEqual(plan.image_dir.name, "colmap_images")
            self.assertEqual(plan.sparse_dir.name, "sparse")
            self.assertEqual([cmd[0] for cmd in plan.commands], ["colmap.exe", "colmap.exe", "colmap.exe"])
            self.assertEqual([cmd[1] for cmd in plan.commands], ["feature_extractor", "exhaustive_matcher", "mapper"])
            self.assertIn("--ImageReader.camera_model", plan.commands[0])
            self.assertIn("OPENCV_FISHEYE", plan.commands[0])
            self.assertTrue((plan.image_dir / "000001_left.jpg").exists())
            self.assertTrue((plan.image_dir / "000001_right.jpg").exists())
            image_manifest = json.loads(plan.image_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual([item["side"] for item in image_manifest], ["left", "right"])

    def test_rejects_manifest_without_panorama_frames(self):
        manifest = {"schema_version": 1, "workflow": "xpano_multi_track", "tracks": []}

        with self.assertRaisesRegex(ValueError, "panorama frames"):
            build_colmap_plan(manifest, output_dir=Path("out"), config=ColmapBackendConfig())


class LichtfieldStudioCliTests(unittest.TestCase):
    def test_builds_lichtfield_command_with_tunable_parameters(self):
        command = build_lichtfield_command(
            LichtfieldStudioConfig(
                executable="lichtfield-studio.exe",
                input_colmap=Path("out/sparse/0"),
                image_dir=Path("out/images"),
                output_dir=Path("out/lichtfield"),
                point_count=120000,
                bilateral_grid=16,
                extra_args=["--quality", "high"],
            )
        )

        self.assertEqual(command[0], "lichtfield-studio.exe")
        self.assertIn("--input-colmap", command)
        self.assertIn(str(Path("out/sparse/0")), command)
        self.assertIn("--point-count", command)
        self.assertIn("120000", command)
        self.assertIn("--bilateral-grid", command)
        self.assertIn("16", command)
        self.assertEqual(command[-2:], ["--quality", "high"])

    def test_rejects_negative_lichtfield_parameters(self):
        with self.assertRaisesRegex(ValueError, "greater than or equal to 0"):
            build_lichtfield_command(
                LichtfieldStudioConfig(
                    input_colmap=Path("out/sparse/0"),
                    image_dir=Path("out/images"),
                    output_dir=Path("out/lichtfield"),
                    point_count=-1,
                )
            )


if __name__ == "__main__":
    unittest.main()
