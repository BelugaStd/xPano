import math
import subprocess
from pathlib import Path

from xpano_workbench.models import ExtractionSettings


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
PANORAMA_EXTENSIONS = {".osv", ".insv"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def is_photo_path(path):
    return Path(path).suffix.lower() in PHOTO_EXTENSIONS


def iter_valid_photo_folder(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Photo material must be a folder: {folder}")
    photos = []
    invalid = []
    for path in sorted(folder.rglob("*")):
        if path.is_dir():
            continue
        if is_photo_path(path):
            photos.append(path.resolve())
        else:
            invalid.append(path)
    if invalid:
        raise ValueError(f"Photo folders may only contain photos. First invalid file: {invalid[0]}")
    if not photos:
        raise ValueError(f"No photos found in folder: {folder}")
    return photos


def estimate_video_frame_count(duration_seconds, settings: ExtractionSettings):
    settings.validate()
    if duration_seconds is None or duration_seconds <= 0:
        return None
    end = settings.end_time_seconds if settings.end_time_seconds > 0 else duration_seconds
    end = min(end, duration_seconds)
    start = min(settings.start_time_seconds, end)
    frame_count = int(math.ceil(max(0.0, end - start) / settings.seconds_per_frame))
    if settings.max_frames > 0:
        frame_count = min(frame_count, settings.max_frames)
    return frame_count


def estimate_photo_selection(total, requested=0):
    total = max(0, int(total))
    requested = int(requested or 0)
    if total <= 0:
        return 0, 0
    if requested <= 0:
        return total, total
    minimum = min(10, total)
    return max(minimum, min(requested, total)), total


def sample_evenly(items, limit):
    items = list(items)
    limit = int(limit or 0)
    if limit <= 0 or limit >= len(items):
        return items
    if limit <= 1:
        return [items[0]]
    last = len(items) - 1
    return [items[round(index * last / (limit - 1))] for index in range(limit)]


def probe_video_duration(path, ffprobe_exe="ffprobe"):
    path = Path(path)
    try:
        result = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None
