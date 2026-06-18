import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import JobConfig, MaterialTrack, MultiTrackJobConfig, material_tracks_to_job_config, run_metashape_pipeline, run_multi_track_pipeline


class FakeProcess:
    def __init__(self):
        self.stdout = ["PROGRESS:100\n"]

    def wait(self):
        return 0


class AppPipelineTests(unittest.TestCase):
    def test_material_tracks_build_multi_track_job_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            phone = root / "phone"
            drone = root / "drone"
            output = root / "out"
            pano.write_bytes(b"video")
            phone.mkdir()
            drone.mkdir()

            job = material_tracks_to_job_config(
                tracks=[
                    MaterialTrack(track_type="panorama_video", label="insta", paths=[pano]),
                    MaterialTrack(track_type="standard_photos", label="phone", paths=[phone]),
                    MaterialTrack(track_type="aerial_photos", label="mavic", paths=[drone]),
                ],
                output_dir=output,
                seconds_per_frame=1.0,
                max_frames=5,
                metashape_exe="metashape.exe",
            )

            self.assertEqual(job.panorama_videos, [pano.resolve()])
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
            )

            fake_plan = Mock()
            fake_plan.output_dir = output / "colmap"
            progress = Mock()
            log = Mock()
            with patch("app.subprocess.Popen") as popen, \
                patch("app.build_colmap_plan", return_value=fake_plan) as build_colmap_plan, \
                patch("app.run_colmap_plan") as run_colmap_plan, \
                patch("app.write_run_summary"):
                run_multi_track_pipeline(job, progress, Mock(), log)

            popen.assert_not_called()
            build_colmap_plan.assert_called_once()
            run_colmap_plan.assert_called_once()
            progress.assert_any_call(35)
            progress.assert_any_call(100)

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

            clear_log = []

            from app import clear_generated_outputs

            clear_generated_outputs(output, clear_log.append, preserve_paths=[manifest_path])

            self.assertTrue(manifest_path.exists())
            self.assertFalse((output / "images").exists())
            self.assertFalse((output / "sparse").exists())

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
