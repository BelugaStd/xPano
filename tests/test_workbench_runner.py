import tempfile
import unittest
from pathlib import Path

from xpano_workbench.models import ORDINARY_VIDEO, PANORAMA_VIDEO, STANDARD_PHOTOS, ExtractionSettings, create_track
from xpano_workbench.runner import WorkbenchRunConfig, build_pipeline_job, run_workbench_pipeline


class FakeSink:
    def __init__(self):
        self.events = []

    def progress(self, value):
        self.events.append(("progress", value))

    def log(self, text):
        self.events.append(("log", text))

    def preview(self, left, right):
        self.events.append(("preview", left, right))

    def done(self, result=None):
        self.events.append(("done", result))

    def error(self, exc):
        self.events.append(("error", type(exc).__name__, str(exc)))


class WorkbenchRunnerTests(unittest.TestCase):
    def test_builds_pipeline_job_with_panorama_and_ordinary_video_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "camera.osv"
            ordinary = root / "clip.mp4"
            pano.write_bytes(b"pano")
            ordinary.write_bytes(b"video")
            extraction = ExtractionSettings(seconds_per_frame=2.0, max_frames=12)
            tracks = (
                create_track(1, PANORAMA_VIDEO, "camera", [pano], extraction=extraction),
                create_track(2, ORDINARY_VIDEO, "clip", [ordinary], extraction=extraction),
            )

            job = build_pipeline_job(WorkbenchRunConfig(tracks=tracks, output_dir=root / "out"))

            self.assertEqual(job.panorama_videos, [pano.resolve()])
            self.assertEqual(job.ordinary_video_tracks, [ordinary.resolve()])
            self.assertEqual(job.seconds_per_frame, 2.0)
            self.assertEqual(job.max_frames, 12)

    def test_preserves_different_extraction_settings_per_video_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "camera.osv"
            ordinary = root / "clip.mp4"
            pano.write_bytes(b"pano")
            ordinary.write_bytes(b"video")
            tracks = (
                create_track(
                    1,
                    PANORAMA_VIDEO,
                    "camera",
                    [pano],
                    extraction=ExtractionSettings(seconds_per_frame=1.0, start_time_seconds=3.0),
                ),
                create_track(
                    2,
                    ORDINARY_VIDEO,
                    "clip",
                    [ordinary],
                    extraction=ExtractionSettings(seconds_per_frame=2.0, end_time_seconds=8.0),
                ),
            )

            job = build_pipeline_job(WorkbenchRunConfig(tracks=tracks, output_dir=root / "out"))

            self.assertEqual(job.track_extraction_settings[str(pano.resolve())]["seconds_per_frame"], 1.0)
            self.assertEqual(job.track_extraction_settings[str(pano.resolve())]["start_time_seconds"], 3.0)
            self.assertEqual(job.track_extraction_settings[str(ordinary.resolve())]["seconds_per_frame"], 2.0)
            self.assertEqual(job.track_extraction_settings[str(ordinary.resolve())]["end_time_seconds"], 8.0)

    def test_preserves_photo_limit_for_photo_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "photos"
            photos.mkdir()
            track = create_track(1, STANDARD_PHOTOS, "photos", [photos], photo_limit=59)

            job = build_pipeline_job(WorkbenchRunConfig(tracks=(track,), output_dir=root / "out"))

            self.assertEqual(job.standard_photo_tracks, [("photos", [photos.resolve()], 59)])

    def test_runner_forwards_progress_log_preview_and_done_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "camera.osv"
            pano.write_bytes(b"pano")
            tracks = (create_track(1, PANORAMA_VIDEO, "camera", [pano]),)
            sink = FakeSink()

            def fake_runner(job, progress_cb, preview_cb, log_cb):
                progress_cb(25)
                log_cb("started")
                preview_cb("left.jpg", "right.jpg")
                return {"output_dir": str(job.output_dir)}

            result = run_workbench_pipeline(
                WorkbenchRunConfig(tracks=tracks, output_dir=root / "out"),
                sink=sink,
                runner=fake_runner,
            )

            self.assertEqual(result, {"output_dir": str((root / "out").resolve())})
            self.assertIn(("progress", 25), sink.events)
            self.assertIn(("log", "started"), sink.events)
            self.assertIn(("preview", "left.jpg", "right.jpg"), sink.events)
            self.assertIn(("done", result), sink.events)


if __name__ == "__main__":
    unittest.main()
