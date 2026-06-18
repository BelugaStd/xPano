import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.run_xpano_tracks_job import main, validate_run_args


class RunXpanoTracksJobTests(unittest.TestCase):
    def test_rejects_negative_max_frames(self):
        with self.assertRaisesRegex(ValueError, "--max-frames"):
            validate_run_args(seconds_per_frame=1.0, max_frames=-1)

    def test_rejects_non_positive_seconds_per_frame(self):
        with self.assertRaisesRegex(ValueError, "--seconds-per-frame"):
            validate_run_args(seconds_per_frame=0, max_frames=0)

    def test_check_env_does_not_require_output_or_run_pipeline(self):
        argv = [
            "run_xpano_tracks_job.py",
            "--check-env",
            "--backend",
            "colmap",
            "--run-lichtfield",
        ]

        with patch.object(sys, "argv", argv), \
            patch("scripts.run_xpano_tracks_job.run_multi_track_pipeline") as runner, \
            patch("builtins.print") as print_fn:
            main()

        runner.assert_not_called()
        output = print_fn.call_args.args[0]
        self.assertIn("COLMAP", output)
        self.assertIn("LICHT Field Studio", output)

    def test_main_delegates_material_tracks_to_app_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano_a = root / "a.osv"
            pano_b = root / "b.insv"
            phone = root / "phone"
            drone = root / "drone"
            output = root / "out"
            for path in [pano_a, pano_b]:
                path.write_bytes(b"video")
            phone.mkdir()
            drone.mkdir()

            argv = [
                "run_xpano_tracks_job.py",
                "--output",
                str(output),
                "--metashape",
                sys.executable,
                "--seconds-per-frame",
                "1.5",
                "--max-frames",
                "7",
                "--pano",
                str(pano_a),
                "--pano",
                str(pano_b),
                "--standard-track",
                "phone",
                str(phone),
                "--aerial-track",
                "mavic",
                str(drone),
            ]

            with patch.object(sys, "argv", argv), patch("scripts.run_xpano_tracks_job.run_multi_track_pipeline") as runner:
                main()

            job = runner.call_args.args[0]
            self.assertEqual(job.panorama_videos, [pano_a.resolve(), pano_b.resolve()])
            self.assertEqual(job.standard_photo_tracks, [("phone", [phone.resolve()])])
            self.assertEqual(job.aerial_photo_tracks, [("mavic", [drone.resolve()])])
            self.assertEqual(job.output_dir, output.resolve())
            self.assertEqual(job.seconds_per_frame, 1.5)
            self.assertEqual(job.max_frames, 7)
            self.assertEqual(job.metashape_exe, sys.executable)
            self.assertEqual(job.backend, "metashape")

    def test_main_accepts_backend_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            output = root / "out"
            pano.write_bytes(b"video")

            argv = [
                "run_xpano_tracks_job.py",
                "--output",
                str(output),
                "--metashape",
                "missing-metashape.exe",
                "--backend",
                "colmap",
                "--colmap",
                sys.executable,
                "--seconds-per-frame",
                "1.0",
                "--max-frames",
                "1",
                "--pano",
                str(pano),
            ]

            with patch.object(sys, "argv", argv), patch("scripts.run_xpano_tracks_job.run_multi_track_pipeline") as runner:
                main()

            job = runner.call_args.args[0]
            self.assertEqual(job.backend, "colmap")
            self.assertEqual(job.colmap_exe, sys.executable)

    def test_main_accepts_lichtfield_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            output = root / "out"
            pano.write_bytes(b"video")

            argv = [
                "run_xpano_tracks_job.py",
                "--output",
                str(output),
                "--backend",
                "colmap",
                "--colmap",
                sys.executable,
                "--run-lichtfield",
                "--lichtfield",
                sys.executable,
                "--lichtfield-point-count",
                "120000",
                "--lichtfield-bilateral-grid",
                "16",
                "--pano",
                str(pano),
            ]

            with patch.object(sys, "argv", argv), patch("scripts.run_xpano_tracks_job.run_multi_track_pipeline") as runner:
                main()

            job = runner.call_args.args[0]
            self.assertTrue(job.run_lichtfield)
            self.assertEqual(job.lichtfield_exe, sys.executable)
            self.assertEqual(job.lichtfield_point_count, 120000)
            self.assertEqual(job.lichtfield_bilateral_grid, 16)

    def test_metashape_backend_ignores_lichtfield_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "a.osv"
            output = root / "out"
            pano.write_bytes(b"video")

            argv = [
                "run_xpano_tracks_job.py",
                "--output",
                str(output),
                "--metashape",
                sys.executable,
                "--run-lichtfield",
                "--lichtfield",
                "missing-lichtfield.exe",
                "--pano",
                str(pano),
            ]

            with patch.object(sys, "argv", argv), patch("scripts.run_xpano_tracks_job.run_multi_track_pipeline") as runner:
                main()

            job = runner.call_args.args[0]
            self.assertEqual(job.backend, "metashape")
            self.assertFalse(job.run_lichtfield)


if __name__ == "__main__":
    unittest.main()
