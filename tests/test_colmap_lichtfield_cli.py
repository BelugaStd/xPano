import json
import tempfile
import unittest
from pathlib import Path

from scripts.colmap_backend import (
    ColmapBackendConfig,
    ColmapCommandPlan,
    build_colmap_plan,
    run_colmap_plan,
)
from scripts.lichtfield_cli import LichtfieldStudioConfig, build_lichtfield_command, run_lichtfield_command


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
            self.assertEqual([cmd[1] for cmd in plan.commands], ["feature_extractor", "sequential_matcher", "mapper"])
            self.assertIn("--ImageReader.camera_model", plan.commands[0])
            self.assertIn("OPENCV_FISHEYE", plan.commands[0])
            self.assertIn("--FeatureExtraction.max_image_size", plan.commands[0])
            self.assertIn("1600", plan.commands[0])
            self.assertNotIn("--SiftExtraction.max_image_size", plan.commands[0])
            self.assertIn("--SiftExtraction.max_num_features", plan.commands[0])
            self.assertIn("4096", plan.commands[0])
            self.assertIn("--FeatureExtraction.num_threads", plan.commands[0])
            self.assertIn("4", plan.commands[0])
            self.assertIn("--FeatureExtraction.use_gpu", plan.commands[0])
            self.assertIn("--ImageReader.single_camera_per_folder", plan.commands[0])
            self.assertIn("--FeatureMatching.use_gpu", plan.commands[1])
            self.assertIn("--SequentialMatching.overlap", plan.commands[1])
            self.assertTrue((plan.image_dir / "left" / "000001.jpg").exists())
            self.assertTrue((plan.image_dir / "right" / "000001.jpg").exists())
            image_manifest = json.loads(plan.image_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual([item["side"] for item in image_manifest], ["left", "right"])

    def test_colmap_plan_rebuild_clears_stale_generated_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "frame_left.jpg"
            right = root / "frame_right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            output = root / "out"
            stale_image_dir = output / "colmap_images"
            stale_sparse_dir = output / "sparse" / "0"
            stale_image_dir.mkdir(parents=True)
            stale_sparse_dir.mkdir(parents=True)
            (stale_image_dir / "999999_left.jpg").write_bytes(b"stale")
            (output / "database.db").write_bytes(b"stale-db")
            (stale_sparse_dir / "cameras.bin").write_bytes(b"stale")

            manifest = {
                "schema_version": 1,
                "workflow": "xpano_multi_track",
                "tracks": [
                    {
                        "track_id": "track_001_osmo",
                        "track_type": "panorama_video",
                        "metashape_mode": "dual_fisheye_station",
                        "export_mode": "cubemap",
                        "frames": [{"left": str(left), "right": str(right)}],
                    }
                ],
            }

            plan = build_colmap_plan(manifest, output_dir=output, config=ColmapBackendConfig())

            self.assertFalse((plan.image_dir / "999999_left.jpg").exists())
            self.assertFalse((plan.sparse_dir / "0" / "cameras.bin").exists())
            self.assertFalse(plan.database_path.exists())
            self.assertEqual(sorted(str(path.relative_to(plan.image_dir)).replace("\\", "/") for path in plan.image_dir.rglob("*.jpg")), ["left/000001.jpg", "right/000001.jpg"])

    def test_colmap_plan_can_use_exhaustive_matcher_when_requested(self):
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
                        "metashape_mode": "dual_fisheye_station",
                        "export_mode": "cubemap",
                        "frames": [{"left": str(left), "right": str(right)}],
                    }
                ],
            }

            plan = build_colmap_plan(
                manifest,
                output_dir=root / "out",
                config=ColmapBackendConfig(matcher="exhaustive"),
            )

            self.assertEqual(plan.commands[1][1], "exhaustive_matcher")

    def test_colmap_plan_validates_inputs_before_clearing_old_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            stale_image_dir = output / "colmap_images"
            stale_image_dir.mkdir(parents=True)
            stale_image = stale_image_dir / "999999_left.jpg"
            stale_image.write_bytes(b"stale")
            manifest = {
                "schema_version": 1,
                "workflow": "xpano_multi_track",
                "tracks": [
                    {
                        "track_id": "track_001_osmo",
                        "track_type": "panorama_video",
                        "metashape_mode": "dual_fisheye_station",
                        "export_mode": "cubemap",
                        "frames": [{"left": str(root / "missing_left.jpg"), "right": str(root / "missing_right.jpg")}],
                    }
                ],
            }

            with self.assertRaises(FileNotFoundError):
                build_colmap_plan(manifest, output_dir=output, config=ColmapBackendConfig())

            self.assertTrue(stale_image.exists())

    def test_rejects_manifest_without_panorama_frames(self):
        manifest = {"schema_version": 1, "workflow": "xpano_multi_track", "tracks": []}

        with self.assertRaisesRegex(ValueError, "panorama frames"):
            build_colmap_plan(manifest, output_dir=Path("out"), config=ColmapBackendConfig())

    def test_runs_colmap_commands_and_reports_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = ColmapCommandPlan(
                output_dir=root,
                database_path=root / "database.db",
                image_dir=root / "colmap_images",
                sparse_dir=root / "sparse",
                commands=[
                    ["colmap", "feature_extractor"],
                    ["colmap", "exhaustive_matcher"],
                    ["colmap", "mapper"],
                ],
            )
            plan.image_dir.mkdir()
            plan.sparse_dir.mkdir()

            calls = []
            logs = []
            progress = []

            def fake_runner(command, **kwargs):
                calls.append(command)
                if command[1] == "feature_extractor":
                    plan.database_path.write_bytes(b"db")
                if command[1] == "mapper":
                    sparse_zero = plan.sparse_dir / "0"
                    sparse_zero.mkdir()
                    (sparse_zero / "cameras.bin").write_bytes(b"cameras")
                    (sparse_zero / "images.bin").write_bytes(b"images")
                    (sparse_zero / "points3D.bin").write_bytes(b"points")
                return type("Result", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})()

            run_colmap_plan(
                plan,
                progress_cb=progress.append,
                log_cb=logs.append,
                runner=fake_runner,
            )

            self.assertEqual(calls, plan.commands)
            self.assertEqual(progress, [53, 71, 90])
            self.assertTrue(any("feature_extractor" in line for line in logs))

    def test_fails_when_colmap_command_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = ColmapCommandPlan(
                output_dir=root,
                database_path=root / "database.db",
                image_dir=root / "colmap_images",
                sparse_dir=root / "sparse",
                commands=[["colmap", "feature_extractor"]],
            )
            plan.image_dir.mkdir()
            plan.sparse_dir.mkdir()

            def fake_runner(command, **kwargs):
                return type("Result", (), {"returncode": 7, "stdout": "", "stderr": "bad flags"})()

            with self.assertRaisesRegex(RuntimeError, "feature_extractor"):
                run_colmap_plan(plan, runner=fake_runner)

    def test_fails_when_colmap_sparse_output_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = ColmapCommandPlan(
                output_dir=root,
                database_path=root / "database.db",
                image_dir=root / "colmap_images",
                sparse_dir=root / "sparse",
                commands=[["colmap", "feature_extractor"]],
            )
            plan.image_dir.mkdir()
            plan.sparse_dir.mkdir()

            def fake_runner(command, **kwargs):
                plan.database_path.write_bytes(b"db")
                return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with self.assertRaisesRegex(RuntimeError, "sparse"):
                run_colmap_plan(plan, runner=fake_runner)


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

    def test_runs_lichtfield_command_and_reports_progress(self):
        calls = []
        logs = []
        progress = []

        def fake_runner(command, **kwargs):
            calls.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "trained\n", "stderr": ""})()

        command = run_lichtfield_command(
            LichtfieldStudioConfig(
                executable="lichtfield-studio.exe",
                input_colmap=Path("out/sparse/0"),
                image_dir=Path("out/images"),
                output_dir=Path("out/licht"),
                point_count=1000,
                bilateral_grid=8,
            ),
            progress_cb=progress.append,
            log_cb=logs.append,
            runner=fake_runner,
        )

        self.assertEqual(calls, [command])
        self.assertEqual(progress, [80, 100])
        self.assertTrue(any("LICHT Field Studio" in line for line in logs))

    def test_fails_when_lichtfield_command_returns_nonzero(self):
        def fake_runner(command, **kwargs):
            return type("Result", (), {"returncode": 9, "stdout": "", "stderr": "bad input"})()

        with self.assertRaisesRegex(RuntimeError, "LICHT Field Studio"):
            run_lichtfield_command(
                LichtfieldStudioConfig(
                    input_colmap=Path("out/sparse/0"),
                    image_dir=Path("out/images"),
                    output_dir=Path("out/licht"),
                ),
                runner=fake_runner,
            )


if __name__ == "__main__":
    unittest.main()
