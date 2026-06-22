import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import App, JobConfig, MaterialTrack, MultiTrackJobConfig, collect_runtime_import_versions, material_tracks_to_job_config, run_metashape_pipeline, run_multi_track_pipeline, write_run_summary
from scripts.colmap_backend import read_colmap_points3d, write_colmap_points3d


class FakeProcess:
    def __init__(self):
        self.stdout = ["PROGRESS:100\n"]

    def wait(self):
        return 0


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class AppPipelineTests(unittest.TestCase):
    def test_runtime_import_report_marks_missing_dependency_as_failure(self):
        def fake_import_module(name):
            if name == "cv2":
                raise ImportError("missing cv2")
            return SimpleNamespace(__version__="1.0", __file__=f"{name}.py")

        report = collect_runtime_import_versions(import_module=fake_import_module)

        self.assertFalse(report["ok"])
        self.assertTrue(report["modules"]["numpy"]["ok"])
        self.assertFalse(report["modules"]["cv2"]["ok"])
        self.assertIn("missing cv2", report["modules"]["cv2"]["error"])

    def test_mousewheel_units_supports_windows_and_button_events(self):
        self.assertEqual(App._mousewheel_units(SimpleNamespace(delta=120)), -1)
        self.assertEqual(App._mousewheel_units(SimpleNamespace(delta=-120)), 1)
        self.assertEqual(App._mousewheel_units(SimpleNamespace(num=4, delta=0)), -1)
        self.assertEqual(App._mousewheel_units(SimpleNamespace(num=5, delta=0)), 1)
        self.assertEqual(App._mousewheel_units(SimpleNamespace(delta=0)), 0)

    def test_material_tracks_build_multi_track_job_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            ordinary = root / "clip.mp4"
            phone = root / "phone"
            drone = root / "drone"
            output = root / "out"
            pano.write_bytes(b"video")
            ordinary.write_bytes(b"video")
            phone.mkdir()
            drone.mkdir()

            job = material_tracks_to_job_config(
                tracks=[
                    MaterialTrack(track_type="panorama_video", label="insta", paths=[pano]),
                    MaterialTrack(track_type="ordinary_video", label="clip", paths=[ordinary]),
                    MaterialTrack(track_type="standard_photos", label="phone", paths=[phone]),
                    MaterialTrack(track_type="aerial_photos", label="mavic", paths=[drone]),
                ],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=5,
                metashape_exe="metashape.exe",
            )

            self.assertEqual(job.panorama_videos, [pano.resolve()])
            self.assertEqual(job.ordinary_video_tracks, [ordinary.resolve()])
            self.assertEqual(job.standard_photo_tracks, [("phone", [phone.resolve()])])
            self.assertEqual(job.aerial_photo_tracks, [("mavic", [drone.resolve()])])
            self.assertEqual(job.output_dir, output.resolve())
            self.assertEqual(job.backend, "metashape")

    def test_material_tracks_reject_empty_track(self):
        with self.assertRaisesRegex(ValueError, "must contain at least one path"):
            material_tracks_to_job_config(
                tracks=[MaterialTrack(track_type="panorama_video", label="empty", paths=[])],
                output_dir=Path("out"),
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
            )

    def test_gui_control_mapping_builds_colmap_lichtfield_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            output = root / "out"
            pano.write_bytes(b"video")
            app = object.__new__(App)
            app.material_tracks = [MaterialTrack(track_type="panorama_video", label="pano", paths=[pano])]
            app.output_var = FakeVar(str(output))
            app.backend_var = FakeVar("colmap")
            app.colmap_density_var = FakeVar("high-density")
            app.run_lichtfield_var = FakeVar(True)

            job = App._build_job_from_controls(
                app,
                spf=1.0,
                max_frames=3,
                metashape_exe="metashape.exe",
                colmap_exe="colmap.exe",
                lichtfield_exe="lichtfield-studio.exe",
                licht_point_count=120000,
                licht_grid=16,
            )

            self.assertEqual(job.backend, "colmap")
            self.assertEqual(job.colmap_exe, "colmap.exe")
            self.assertEqual(job.colmap_density_preset, "high-density")
            self.assertTrue(job.run_lichtfield)
            self.assertEqual(job.lichtfield_exe, "lichtfield-studio.exe")
            self.assertEqual(job.lichtfield_point_count, 120000)
            self.assertEqual(job.lichtfield_bilateral_grid, 16)
            self.assertEqual(job.output_dir, output.resolve())

    def test_single_video_gui_pipeline_uses_manifest_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{}", encoding="utf-8")
            video = output / "input.osv"
            video.write_bytes(b"video")
            job = JobConfig(
                input_video=video,
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=10,
                metashape_exe="metashape.exe",
            )

            popen_calls = []

            def fake_popen(cmd, **kwargs):
                popen_calls.append(cmd)
                return FakeProcess()

            with patch("app.build_manifest", return_value=({}, manifest_path)) as build_manifest, \
                patch("app.subprocess.Popen", side_effect=fake_popen), \
                patch("app.write_run_summary"):
                run_metashape_pipeline(job, Mock(), Mock(), Mock())

            build_manifest.assert_called_once()
            self.assertIn("log_cb", build_manifest.call_args.kwargs)
            command = popen_calls[0]
            self.assertIn("--manifest", command)
            self.assertIn(str(manifest_path), command)
            self.assertNotIn("--input-root", command)

    def test_colmap_backend_builds_and_runs_colmap_plan_without_metashape(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            left = output / "left.jpg"
            right = output / "right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_text = """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": [
                    {
                      "track_id": "track_001",
                      "track_type": "panorama_video",
                      "metashape_mode": "dual_fisheye_station",
                      "export_mode": "cubemap",
                      "frames": [
                        {
                          "left": "%s",
                          "right": "%s"
                        }
                      ]
                    }
                  ]
                }""" % (left.as_posix(), right.as_posix())
            manifest_path.write_text(manifest_text, encoding="utf-8")
            job = MultiTrackJobConfig(
                panorama_videos=[],
                standard_photo_tracks=[],
                aerial_photo_tracks=[],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
                backend="colmap",
                manifest_path=manifest_path,
                colmap_density_preset="high-density",
            )

            fake_plan = Mock()
            fake_plan.output_dir = output / "colmap"
            progress = Mock()
            log = Mock()
            with patch("app.subprocess.Popen") as popen, \
                patch("app.build_colmap_plan", return_value=fake_plan) as build_colmap_plan, \
                patch("app.run_colmap_plan") as run_colmap_plan, \
                patch("app.publish_colmap_output", return_value={"image_dir": str(output / "images"), "sparse_model_path": str(output / "sparse" / "0")}), \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, progress, Mock(), log)

            popen.assert_not_called()
            build_colmap_plan.assert_called_once()
            self.assertEqual(build_colmap_plan.call_args.kwargs["config"].max_num_features, 8192)
            self.assertTrue(build_colmap_plan.call_args.kwargs["config"].guided_matching)
            run_colmap_plan.assert_called_once()
            progress.assert_any_call(35)
            progress.assert_any_call(100)

    def test_colmap_backend_resolves_executable_before_building_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            left = output / "left.jpg"
            right = output / "right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": [
                    {
                      "track_id": "track_001",
                      "track_type": "panorama_video",
                      "metashape_mode": "dual_fisheye_station",
                      "export_mode": "cubemap",
                      "frames": [
                        {"left": "%s", "right": "%s"}
                      ]
                    }
                  ]
                }""" % (left.as_posix(), right.as_posix()),
                encoding="utf-8",
            )
            bundled = output / "tools" / "colmap" / "bin" / "colmap.exe"
            job = MultiTrackJobConfig(
                panorama_videos=[],
                standard_photo_tracks=[],
                aerial_photo_tracks=[],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
                backend="colmap",
                manifest_path=manifest_path,
                colmap_exe="colmap",
            )
            fake_plan = Mock()
            fake_plan.output_dir = output / "colmap"

            with patch("app.resolve_executable", return_value=str(bundled)) as resolve_executable, \
                patch("app.build_colmap_plan", return_value=fake_plan) as build_colmap_plan, \
                patch("app.run_colmap_plan"), \
                patch("app.publish_colmap_output", return_value={"image_dir": str(output / "images"), "sparse_model_path": str(output / "sparse" / "0")}), \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, Mock(), Mock(), Mock())

            resolve_executable.assert_called_once_with("colmap", "colmap")
            self.assertEqual(build_colmap_plan.call_args.kwargs["config"].colmap_exe, str(bundled))

    def test_colmap_backend_can_run_lichtfield_postprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            left = output / "left.jpg"
            right = output / "right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": [
                    {
                      "track_id": "track_001",
                      "track_type": "panorama_video",
                      "metashape_mode": "dual_fisheye_station",
                      "export_mode": "cubemap",
                      "frames": [
                        {"left": "%s", "right": "%s"}
                      ]
                    }
                  ]
                }""" % (left.as_posix(), right.as_posix()),
                encoding="utf-8",
            )
            job = MultiTrackJobConfig(
                panorama_videos=[],
                standard_photo_tracks=[],
                aerial_photo_tracks=[],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
                backend="colmap",
                manifest_path=manifest_path,
                run_lichtfield=True,
                lichtfield_exe="lichtfield-studio.exe",
                lichtfield_point_count=120000,
                lichtfield_bilateral_grid=16,
            )

            sparse_model = output / "sparse" / "0"
            image_dir = output / "colmap" / "colmap_images"
            final_image_dir = output / "images"
            fake_plan = Mock()
            fake_plan.output_dir = output / "colmap"
            fake_plan.sparse_dir = output / "colmap" / "sparse"
            fake_plan.image_dir = image_dir
            with patch("app.build_colmap_plan", return_value=fake_plan), \
                patch("app.run_colmap_plan", return_value={"sparse_model_path": str(output / "colmap" / "sparse" / "0")}), \
                patch("app.publish_colmap_output", return_value={"image_dir": str(final_image_dir), "sparse_model_path": str(sparse_model)}), \
                patch("app.run_lichtfield_command") as run_lichtfield_command, \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, Mock(), Mock(), Mock())

            config = run_lichtfield_command.call_args.args[0]
            self.assertEqual(config.executable, "lichtfield-studio.exe")
            self.assertEqual(config.input_colmap, sparse_model)
            self.assertEqual(config.image_dir, final_image_dir)
            self.assertEqual(config.output_dir, output / "lichtfield")
            self.assertEqual(config.point_count, 120000)
            self.assertEqual(config.bilateral_grid, 16)

    def test_colmap_backend_can_run_lfs_densification(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            left = output / "left.jpg"
            right = output / "right.jpg"
            left.write_bytes(b"left")
            right.write_bytes(b"right")
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": [
                    {
                      "track_id": "track_001",
                      "track_type": "panorama_video",
                      "metashape_mode": "dual_fisheye_station",
                      "export_mode": "cubemap",
                      "frames": [
                        {"left": "%s", "right": "%s"}
                      ]
                    }
                  ]
                }""" % (left.as_posix(), right.as_posix()),
                encoding="utf-8",
            )
            job = MultiTrackJobConfig(
                panorama_videos=[],
                standard_photo_tracks=[],
                aerial_photo_tracks=[],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
                backend="colmap",
                manifest_path=manifest_path,
                run_lfs_densify=True,
                lfs_densify_python="python.exe",
                lfs_densify_plugin=Path("plugin"),
                lfs_densify_roma="fast",
                lfs_densify_max_points=50000,
            )

            fake_plan = Mock()
            fake_plan.output_dir = output / "colmap"
            fake_plan.sparse_dir = output / "colmap" / "sparse"
            fake_plan.image_dir = output / "colmap" / "colmap_images"
            sparse_zero = output / "sparse" / "0"

            def fake_densify(config, **kwargs):
                sparse_zero.mkdir(parents=True, exist_ok=True)
                write_colmap_points3d(sparse_zero / "points3D.bin", [])
                (sparse_zero / config.out_name).write_bytes(
                    b"ply\nformat binary_little_endian 1.0\nelement vertex 1\n"
                    b"property float x\nproperty float y\nproperty float z\n"
                    b"property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
                    + struct.pack("<fffBBB", 1.0, 2.0, 3.0, 4, 5, 6)
                )

            with patch("app.build_colmap_plan", return_value=fake_plan), \
                patch("app.run_colmap_plan", return_value={"sparse_model_path": str(output / "colmap" / "sparse" / "0")}), \
                patch("app.publish_colmap_output", return_value={"image_dir": str(output / "images"), "sparse_model_path": str(output / "sparse" / "0")}), \
                patch("app.run_densify_command", side_effect=fake_densify) as run_densify_command, \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, Mock(), Mock(), Mock())

            config = run_densify_command.call_args.args[0]
            self.assertEqual(config.scene_root, output)
            self.assertEqual(config.images_subdir, "images")
            self.assertEqual(config.out_name, "points3D_dense.ply")
            self.assertEqual(config.plugin_dir, Path("plugin"))
            self.assertEqual(config.python_exe, "python.exe")
            self.assertEqual(config.roma_setting, "fast")
            self.assertEqual(config.max_points, 50000)
            self.assertEqual(read_colmap_points3d(sparse_zero), [{"id": 1, "xyz": (1.0, 2.0, 3.0), "rgb": (4, 5, 6), "error": 1.0, "track": []}])

    def test_overwrite_keeps_current_manifest_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": []
                }""",
                encoding="utf-8",
            )
            (output / "images").mkdir()
            (output / "sparse").mkdir()
            (output / "colmap").mkdir()
            (output / "lichtfield").mkdir()

            clear_log = []

            from app import clear_generated_outputs

            clear_generated_outputs(output, clear_log.append, preserve_paths=[manifest_path])

            self.assertTrue(manifest_path.exists())
            self.assertFalse((output / "images").exists())
            self.assertFalse((output / "sparse").exists())
            self.assertFalse((output / "colmap").exists())
            self.assertFalse((output / "lichtfield").exists())

    def test_colmap_summary_uses_colmap_native_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                """{
                  "schema_version": 1,
                  "workflow": "xpano_multi_track",
                  "tracks": []
                }""",
                encoding="utf-8",
            )
            image_dir = output / "images"
            sparse_dir = output / "sparse" / "0"
            image_dir.mkdir()
            sparse_dir.mkdir(parents=True)
            (image_dir / "000001_left.jpg").write_bytes(b"left")
            for name in ["cameras.bin", "images.bin", "points3D.bin"]:
                (sparse_dir / name).write_bytes(b"bin")
            job = MultiTrackJobConfig(
                panorama_videos=[],
                standard_photo_tracks=[],
                aerial_photo_tracks=[],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=0,
                metashape_exe="metashape.exe",
                backend="colmap",
                manifest_path=manifest_path,
            )

            write_run_summary(job)

            summary = json.loads((output / "xpano_run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["backend"], "colmap")
            self.assertEqual(summary["colmap_input_images"], 1)
            self.assertEqual(summary["export_verification"]["sparse_model_path"], str(sparse_dir))

    def test_multi_track_pipeline_passes_all_track_types_to_manifest_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest_path = output / "work" / "xpano_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{}", encoding="utf-8")
            pano_a = output / "a.osv"
            pano_b = output / "b.insv"
            phone_dir = output / "phone"
            drone_dir = output / "drone"
            for path in [pano_a, pano_b]:
                path.write_bytes(b"video")
            phone_dir.mkdir()
            drone_dir.mkdir()
            job = MultiTrackJobConfig(
                panorama_videos=[pano_a, pano_b],
                standard_photo_tracks=[("phone", [phone_dir])],
                aerial_photo_tracks=[("mavic", [drone_dir])],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=5,
                metashape_exe="metashape.exe",
            )

            popen_calls = []

            def fake_popen(cmd, **kwargs):
                popen_calls.append(cmd)
                return FakeProcess()

            with patch("app.build_manifest", return_value=({}, manifest_path)) as build_manifest, \
                patch("app.subprocess.Popen", side_effect=fake_popen), \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, Mock(), Mock(), Mock())

            kwargs = build_manifest.call_args.kwargs
            self.assertEqual(kwargs["panorama_videos"], [pano_a, pano_b])
            self.assertEqual(kwargs["standard_photo_tracks"], [("phone", [phone_dir])])
            self.assertEqual(kwargs["aerial_photo_tracks"], [("mavic", [drone_dir])])
            self.assertIn("log_cb", kwargs)
            command = popen_calls[0]
            self.assertIn("--manifest", command)
            self.assertIn(str(manifest_path), command)


if __name__ == "__main__":
    unittest.main()
