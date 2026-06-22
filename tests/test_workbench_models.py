import unittest
from pathlib import Path

from xpano_workbench.models import (
    ORDINARY_VIDEO,
    PANORAMA_VIDEO,
    STANDARD_PHOTOS,
    ExtractionSettings,
    create_track,
)


class WorkbenchModelTests(unittest.TestCase):
    def test_creates_track_with_track_bound_extraction_settings(self):
        track = create_track(
            1,
            PANORAMA_VIDEO,
            "Camera A",
            [Path("a.osv")],
            extraction=ExtractionSettings(seconds_per_frame=2.0, max_frames=50),
        )

        self.assertEqual(track.track_id, "track_001_camera_a")
        self.assertEqual(track.extraction.seconds_per_frame, 2.0)
        self.assertEqual(track.extraction.max_frames, 50)

    def test_supports_ordinary_video_track_type(self):
        track = create_track(2, ORDINARY_VIDEO, "Phone clip", [Path("clip.mp4")])

        self.assertEqual(track.track_type, ORDINARY_VIDEO)
        self.assertEqual(track.display_type, "Ordinary video")

    def test_rejects_invalid_extraction_settings(self):
        with self.assertRaisesRegex(ValueError, "seconds_per_frame"):
            create_track(
                1,
                STANDARD_PHOTOS,
                "photos",
                [Path("photos")],
                extraction=ExtractionSettings(seconds_per_frame=0),
            )

    def test_updates_track_extraction_without_mutating_original(self):
        track = create_track(1, ORDINARY_VIDEO, "clip", [Path("clip.mp4")])
        updated = track.with_extraction(seconds_per_frame=0.5, max_frames=10)

        self.assertEqual(track.extraction.seconds_per_frame, 1.0)
        self.assertEqual(updated.extraction.seconds_per_frame, 0.5)
        self.assertEqual(updated.extraction.max_frames, 10)

    def test_creates_photo_track_with_track_bound_photo_limit(self):
        track = create_track(1, STANDARD_PHOTOS, "photos", [Path("photos")], photo_limit=59)

        self.assertEqual(track.photo_limit, 59)


if __name__ == "__main__":
    unittest.main()
