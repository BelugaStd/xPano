import math
import tempfile
import unittest
from pathlib import Path

from xpano_workbench.media_import import (
    PANORAMA_EXTENSIONS,
    estimate_photo_selection,
    estimate_video_frame_count,
    iter_valid_photo_folder,
    sample_evenly,
)
from xpano_workbench.models import ExtractionSettings


class MediaImportTests(unittest.TestCase):
    def test_accepts_nested_folder_when_every_file_is_photo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.jpg").write_bytes(b"jpg")
            nested = root / "nested"
            nested.mkdir()
            (nested / "b.png").write_bytes(b"png")

            photos = iter_valid_photo_folder(root)

            self.assertEqual([path.name for path in photos], ["a.jpg", "b.png"])

    def test_rejects_photo_folder_with_non_photo_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.jpg").write_bytes(b"jpg")
            (root / "notes.txt").write_text("not a photo", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "only contain photos"):
                iter_valid_photo_folder(root)

    def test_estimates_video_frames_from_duration_and_limits(self):
        settings = ExtractionSettings(seconds_per_frame=1.0, max_frames=20)

        self.assertEqual(estimate_video_frame_count(50.0, settings), 20)

    def test_estimates_video_frames_from_start_and_end(self):
        settings = ExtractionSettings(seconds_per_frame=2.0, start_time_seconds=10.0, end_time_seconds=21.0)

        self.assertEqual(estimate_video_frame_count(50.0, settings), math.ceil(11.0 / 2.0))

    def test_estimates_photo_selection_with_minimum_and_total(self):
        self.assertEqual(estimate_photo_selection(total=150, requested=59), (59, 150))
        self.assertEqual(estimate_photo_selection(total=150, requested=1), (10, 150))
        self.assertEqual(estimate_photo_selection(total=6, requested=1), (6, 6))

    def test_samples_evenly_when_photo_limit_is_below_total(self):
        values = list(range(10))

        self.assertEqual(sample_evenly(values, 4), [0, 3, 6, 9])

    def test_panorama_tracks_only_accept_osv_and_insv(self):
        self.assertEqual(PANORAMA_EXTENSIONS, {".osv", ".insv"})
        self.assertNotIn(".mp4", PANORAMA_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
