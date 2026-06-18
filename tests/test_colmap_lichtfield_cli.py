import json
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.colmap_backend import (
    ColmapBackendConfig,
    ColmapCommandPlan,
    build_colmap_plan,
    colmap_config_for_density_preset,
    find_sparse_model_path,
    publish_colmap_output,
    read_colmap_points3d,
    run_colmap_plan,
    write_colmap_cameras,
    write_colmap_images,
    write_colmap_points3d,
)
from scripts.lichtfield_cli import LichtfieldStudioConfig, build_lichtfield_command, run_lichtfield_command
from scripts.colmap_dense_merge import merge_dense_ply_into_colmap_points
from scripts.lichtfeld_densify import LichtfeldDensifyConfig, build_densify_command, locate_densify_plugin, locate_densify_python, run_densify_command
from PIL import Image


def write_count_header(path, count):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", count))


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
            self.assertIn("--ImageReader.camera_params", plan.commands[0])
            self.assertIn("1041.6666666667,1041.6666666667,1920,1920,0,0,0,0", plan.commands[0])
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
            self.assertIn("--FeatureMatching.guided_matching", plan.commands[1])
            self.assertIn("--SequentialMatching.overlap", plan.commands[1])
            self.assertTrue((plan.image_dir / "left" / "000001.jpg").exists())
            self.assertTrue((plan.image_dir / "right" / "000001.jpg").exists())
            image_manifest = json.loads(plan.image_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual([item["side"] for item in image_manifest], ["left", "right"])

    def test_high_density_preset_adds_more_features_and_guided_matching(self):
        config = colmap_config_for_density_preset("high-density", colmap_exe="colmap.exe")

        self.assertEqual(config.colmap_exe, "colmap.exe")
        self.assertEqual(config.max_num_features, 8192)
        self.assertEqual(config.sequential_overlap, 10)
        self.assertTrue(config.guided_matching)

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

    def test_selects_sparse_model_with_most_registered_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sparse = root / "sparse"
            for model, cameras, images, points in [
                ("0", 1, 2, 171),
                ("1", 2, 40, 1786),
            ]:
                write_count_header(sparse / model / "cameras.bin", cameras)
                write_count_header(sparse / model / "images.bin", images)
                write_count_header(sparse / model / "points3D.bin", points)

            self.assertEqual(find_sparse_model_path(sparse), sparse / "1")

    def test_publishes_best_sparse_model_to_standard_colmap_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / "native"
            final = root / "final"
            image_dir = native / "colmap_images"
            for rel in ["left/000001.jpg", "right/000001.jpg"]:
                path = image_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (32, 32), (64, 96, 128)).save(path)
            write_count_header(native / "sparse" / "0" / "cameras.bin", 1)
            write_count_header(native / "sparse" / "0" / "images.bin", 1)
            write_count_header(native / "sparse" / "0" / "points3D.bin", 0)
            write_colmap_cameras(
                native / "sparse" / "1" / "cameras.bin",
                [
                    {"id": 1, "model_id": 5, "width": 32, "height": 32, "params": (16, 16, 16, 16, 0, 0, 0, 0)},
                    {"id": 2, "model_id": 5, "width": 32, "height": 32, "params": (16, 16, 16, 16, 0, 0, 0, 0)},
                ],
            )
            write_colmap_images(
                native / "sparse" / "1" / "images.bin",
                [
                    {
                        "id": 1,
                        "qvec": (1, 0, 0, 0),
                        "tvec": (0, 0, 0),
                        "camera_id": 1,
                        "name": "left/000001.jpg",
                        "points2d": [],
                    },
                    {
                        "id": 2,
                        "qvec": (1, 0, 0, 0),
                        "tvec": (0, 0, 0),
                        "camera_id": 2,
                        "name": "right/000001.jpg",
                        "points2d": [],
                    },
                ],
            )
            write_colmap_points3d(native / "sparse" / "1" / "points3D.bin", [])
            plan = ColmapCommandPlan(
                output_dir=native,
                database_path=native / "database.db",
                image_dir=image_dir,
                sparse_dir=native / "sparse",
            )

            result = publish_colmap_output(plan, final)

            self.assertEqual(Path(result["sparse_model_path"]), final / "sparse" / "0")
            self.assertEqual(Path(result["native_sparse_model_path"]), native / "sparse" / "1")
            self.assertEqual(len(list((final / "images").glob("cube_*.jpg"))), 10)
            self.assertEqual((final / "sparse" / "0" / "cameras.bin").read_bytes()[:8], struct.pack("<Q", 10))
            self.assertEqual((final / "sparse" / "0" / "images.bin").read_bytes()[:8], struct.pack("<Q", 10))

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


class LichtfeldDensifyCliTests(unittest.TestCase):
    def test_locates_default_project_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "tools" / "lichtfeld-densification-plugin"
            plugin.mkdir(parents=True)
            (plugin / "densify.py").write_text("print('ok')", encoding="utf-8")

            self.assertEqual(locate_densify_plugin(root), plugin)

    def test_locates_project_densify_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_exe = root / ".venv-densify" / "Scripts" / "python.exe"
            python_exe.parent.mkdir(parents=True)
            python_exe.write_bytes(b"")

            self.assertEqual(locate_densify_python(root), str(python_exe))

    def test_builds_densify_command_with_parameters(self):
        config = LichtfeldDensifyConfig(
            python_exe="python.exe",
            plugin_dir=Path("tools/lichtfeld-densification-plugin"),
            scene_root=Path("out"),
            images_subdir="images",
            out_name="points3D_dense.ply",
            roma_setting="fast",
            num_refs=0.5,
            nns_per_ref=3,
            matches_per_ref=8000,
            certainty_thresh=0.2,
            reproj_thresh=1.5,
            sampson_thresh=5.0,
            min_parallax_deg=0.5,
            max_points=100000,
            seed=7,
        )

        command = build_densify_command(config)

        self.assertTrue(command[1].endswith(str(Path("scripts") / "run_lichtfeld_densify_standalone.py")))
        self.assertIn("--plugin-dir", command)
        self.assertIn(str(Path("tools/lichtfeld-densification-plugin")), command)
        self.assertIn("--scene_root", command)
        self.assertIn(str(Path("out")), command)
        self.assertIn("--images_subdir", command)
        self.assertIn("images", command)
        self.assertIn("--max_points", command)
        self.assertIn("100000", command)

    def test_integer_one_num_refs_is_passed_as_count_not_fraction(self):
        command = build_densify_command(
            LichtfeldDensifyConfig(
                python_exe="python.exe",
                plugin_dir=Path("plugin"),
                scene_root=Path("out"),
                num_refs=1.0,
            )
        )

        self.assertEqual(command[command.index("--num_refs") + 1], "1.01")

    def test_merges_dense_ply_into_colmap_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sparse = root / "sparse" / "0"
            write_colmap_points3d(
                sparse / "points3D.bin",
                [{"id": 7, "xyz": (1.0, 2.0, 3.0), "rgb": (4, 5, 6), "error": 0.5, "track": []}],
            )
            ply = sparse / "dense.ply"
            ply.write_bytes(
                b"ply\nformat binary_little_endian 1.0\nelement vertex 2\n"
                b"property float x\nproperty float y\nproperty float z\n"
                b"property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
                + struct.pack("<fffBBB", 10.0, 20.0, 30.0, 1, 2, 3)
                + struct.pack("<fffBBB", 40.0, 50.0, 60.0, 7, 8, 9)
            )

            result = merge_dense_ply_into_colmap_points(sparse, ply, replace_points_bin=True)
            merged = read_colmap_points3d(sparse)

            self.assertEqual(result["original_points"], 1)
            self.assertEqual(result["dense_points"], 2)
            self.assertEqual(len(merged), 3)
            self.assertTrue((sparse / "points3D_sparse_original.bin").exists())

    def test_runs_densify_command_and_reports_progress(self):
        calls = []
        logs = []
        progress = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return type("Result", (), {"returncode": 0, "stdout": "Done! 12,345 points\n", "stderr": ""})()

        command = run_densify_command(
            LichtfeldDensifyConfig(
                python_exe="python.exe",
                plugin_dir=Path("plugin"),
                scene_root=Path("out"),
                images_subdir="images",
            ),
            progress_cb=progress.append,
            log_cb=logs.append,
            runner=fake_runner,
        )

        self.assertEqual(calls[0][0], command)
        self.assertEqual(progress, [90, 100])
        self.assertTrue(any("LichtFeld densification" in line for line in logs))

    def test_standalone_runner_forwards_plugin_help(self):
        plugin = Path.cwd() / "tools" / "lichtfeld-densification-plugin"
        if not (plugin / "densify.py").exists():
            self.skipTest("LichtFeld densification plugin is not installed")
        python_exe = Path(locate_densify_python())
        if not python_exe.exists():
            self.skipTest("LichtFeld densification Python environment is not installed")

        result = subprocess.run(
            [
                str(python_exe),
                str(Path.cwd() / "scripts" / "run_lichtfeld_densify_standalone.py"),
                "--plugin-dir",
                str(plugin),
                "--help",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--roma_setting", result.stdout)
        self.assertIn("--scene_root", result.stdout)


if __name__ == "__main__":
    unittest.main()
