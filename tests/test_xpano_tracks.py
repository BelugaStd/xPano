import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import piexif
from PIL import Image

from scripts.xpano_tracks import build_manifest, build_ordinary_video_track, build_panorama_track, build_photo_track
from scripts.xpano_tracks import validate_manifest


def write_jpeg(path, size, make, model, lens, focal_num):
    path = Path(path)
    image = Image.new("RGB", size, (32, 64, 96))
    image.save(path, "JPEG")
    exif = {
        "0th": {
            piexif.ImageIFD.Make: make.encode("utf-8"),
            piexif.ImageIFD.Model: model.encode("utf-8"),
        },
        "Exif": {
            piexif.ExifIFD.LensModel: lens.encode("utf-8"),
            piexif.ExifIFD.FocalLength: (focal_num, 10),
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    piexif.insert(piexif.dump(exif), str(path))
    return path


class PhotoTrackTests(unittest.TestCase):
    def test_rejects_mp4_as_panorama_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "clip.mp4"
            video.write_bytes(b"video")

            with self.assertRaisesRegex(ValueError, "Unsupported panorama video"):
                build_panorama_track(
                    1,
                    video,
                    root / "work",
                    seconds_per_frame=1.0,
                    max_frames=1,
                )

    def test_builds_ordinary_video_track_as_frame_photo_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "clip.mp4"
            video.write_bytes(b"video")
            frame = root / "frame.jpg"
            Image.new("RGB", (100, 80), (32, 64, 96)).save(frame, "JPEG")

            with patch("scripts.xpano_tracks.extract_single_video_frames", return_value=[frame]) as extract:
                track = build_ordinary_video_track(
                    1,
                    video,
                    root / "work",
                    seconds_per_frame=2.0,
                    max_frames=5,
                )

            extract.assert_called_once()
            self.assertEqual(track["track_type"], "ordinary_video")
            self.assertEqual(track["seconds_per_frame"], 2.0)
            self.assertEqual(track["max_frames"], 5)
            self.assertEqual(track["metashape_mode"], "pinhole_video_frames")
            self.assertEqual(track["photos"], [str(frame.resolve())])
            validate_manifest({"schema_version": 1, "workflow": "xpano_multi_track", "tracks": [track]})

    def test_manifest_applies_video_track_specific_extraction_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pano = root / "camera.osv"
            ordinary = root / "clip.mp4"
            pano.write_bytes(b"pano")
            ordinary.write_bytes(b"video")
            calls = []

            def fake_pano(**kwargs):
                calls.append(
                    (
                        "pano",
                        kwargs["seconds_per_frame"],
                        kwargs["max_frames"],
                        kwargs["start_time_seconds"],
                        kwargs["end_time_seconds"],
                    )
                )
                return {
                    "track_id": "pano",
                    "track_type": "panorama_video",
                    "metashape_mode": "dual_fisheye_station",
                    "export_mode": "cubemap",
                    "frames": [{"left": str(pano), "right": str(pano)}],
                }

            def fake_ordinary(**kwargs):
                calls.append(
                    (
                        "ordinary",
                        kwargs["seconds_per_frame"],
                        kwargs["max_frames"],
                        kwargs["start_time_seconds"],
                        kwargs["end_time_seconds"],
                    )
                )
                return {
                    "track_id": "ordinary",
                    "track_type": "ordinary_video",
                    "metashape_mode": "pinhole_video_frames",
                    "export_mode": "undistorted_frame",
                    "photos": [str(ordinary)],
                    "photo_sensors": [{"sensor_label": "ordinary_frame", "photos": [str(ordinary)]}],
                }

            settings = {
                str(pano.resolve()): {
                    "seconds_per_frame": 1.0,
                    "max_frames": 10,
                    "start_time_seconds": 3.0,
                    "end_time_seconds": 8.0,
                },
                str(ordinary.resolve()): {
                    "seconds_per_frame": 2.0,
                    "max_frames": 20,
                    "start_time_seconds": 4.0,
                    "end_time_seconds": 12.0,
                },
            }
            with patch("scripts.xpano_tracks.build_panorama_track", side_effect=fake_pano), \
                patch("scripts.xpano_tracks.build_ordinary_video_track", side_effect=fake_ordinary):
                build_manifest(
                    root / "out",
                    panorama_videos=[pano],
                    ordinary_videos=[ordinary],
                    seconds_per_frame=9.0,
                    max_frames=99,
                    track_extraction_settings=settings,
                )

            self.assertEqual(calls, [("pano", 1.0, 10, 3.0, 8.0), ("ordinary", 2.0, 20, 4.0, 12.0)])

    def test_splits_same_size_photos_by_exif_camera_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            phone = write_jpeg(root / "phone.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
            drone = write_jpeg(root / "drone.jpg", (100, 80), "DroneCo", "Air 3", "Main", 240)

            track = build_photo_track(1, "mixed", [phone, drone], "standard_photos")

            self.assertEqual(len(track["photos"]), 2)
            self.assertEqual(len(track["photo_sensors"]), 2)
            grouped = [sensor["photos"] for sensor in track["photo_sensors"]]
            self.assertEqual(sorted(len(paths) for paths in grouped), [1, 1])
            labels = {sensor["sensor_label"] for sensor in track["photo_sensors"]}
            self.assertEqual(len(labels), 2)

    def test_groups_matching_exif_photos_into_one_sensor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_jpeg(root / "first.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
            second = write_jpeg(root / "second.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)

            track = build_photo_track(1, "phone", [first, second], "standard_photos")

            self.assertEqual(len(track["photos"]), 2)
            self.assertEqual(len(track["photo_sensors"]), 1)
            self.assertEqual(len(track["photo_sensors"][0]["photos"]), 2)

    def test_photo_track_uses_even_sampling_when_max_photos_is_below_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = [
                write_jpeg(root / f"image_{index:02d}.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
                for index in range(10)
            ]

            track = build_photo_track(1, "phone", photos, "standard_photos", max_photos=4)

            self.assertEqual(
                [Path(path).name for path in track["photos"]],
                ["image_00.jpg", "image_03.jpg", "image_06.jpg", "image_09.jpg"],
            )
            self.assertEqual(track["photo_count_total"], 10)
            self.assertEqual(track["photo_count_selected"], 4)

    def test_validates_photo_sensor_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_jpeg(root / "first.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
            second = write_jpeg(root / "second.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
            track = build_photo_track(1, "phone", [first, second], "standard_photos")
            track["photo_sensors"][0]["photos"] = [str(first)]
            manifest = {"schema_version": 1, "workflow": "xpano_multi_track", "tracks": [track]}

            with self.assertRaisesRegex(ValueError, "photo_sensors must cover exactly"):
                validate_manifest(manifest)

    def test_rejects_duplicate_track_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_jpeg(root / "first.jpg", (100, 80), "PhoneCo", "Pocket 1", "Wide", 240)
            track = build_photo_track(1, "phone", [first], "standard_photos")
            manifest = {"schema_version": 1, "workflow": "xpano_multi_track", "tracks": [track, dict(track)]}

            with self.assertRaisesRegex(ValueError, "Duplicate track_id"):
                validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
