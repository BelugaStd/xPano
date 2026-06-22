from dataclasses import dataclass, field, replace
from pathlib import Path


PANORAMA_VIDEO = "panorama_video"
ORDINARY_VIDEO = "ordinary_video"
STANDARD_PHOTOS = "standard_photos"
AERIAL_PHOTOS = "aerial_photos"

VIDEO_TRACK_TYPES = {PANORAMA_VIDEO, ORDINARY_VIDEO}
PHOTO_TRACK_TYPES = {STANDARD_PHOTOS, AERIAL_PHOTOS}
TRACK_TYPES = VIDEO_TRACK_TYPES | PHOTO_TRACK_TYPES

TRACK_TYPE_LABELS = {
    PANORAMA_VIDEO: "Panorama video",
    ORDINARY_VIDEO: "Ordinary video",
    STANDARD_PHOTOS: "Standard photos",
    AERIAL_PHOTOS: "Aerial photos",
}


@dataclass(frozen=True)
class ExtractionSettings:
    seconds_per_frame: float = 1.0
    max_frames: int = 0
    start_time_seconds: float = 0.0
    end_time_seconds: float = 0.0

    def validate(self):
        if self.seconds_per_frame <= 0:
            raise ValueError("seconds_per_frame must be greater than 0")
        if self.max_frames < 0:
            raise ValueError("max_frames cannot be negative")
        if self.start_time_seconds < 0:
            raise ValueError("start_time_seconds cannot be negative")
        if self.end_time_seconds < 0:
            raise ValueError("end_time_seconds cannot be negative")
        if self.end_time_seconds and self.end_time_seconds <= self.start_time_seconds:
            raise ValueError("end_time_seconds must be greater than start_time_seconds")
        return self


@dataclass(frozen=True)
class WorkbenchTrack:
    track_id: str
    track_type: str
    label: str
    paths: tuple
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    photo_limit: int = 0
    media_duration_seconds: float = None
    enabled_for_metashape: bool = True
    enabled_for_colmap: bool = True

    def validate(self):
        if self.track_type not in TRACK_TYPES:
            raise ValueError(f"Unsupported track_type: {self.track_type}")
        if not self.paths:
            raise ValueError(f"Track {self.label or self.track_id} must contain at least one path")
        self.extraction.validate()
        if self.photo_limit < 0:
            raise ValueError("photo_limit cannot be negative")
        if self.photo_limit and self.track_type not in PHOTO_TRACK_TYPES:
            raise ValueError("photo_limit is only supported for photo tracks")
        if self.media_duration_seconds is not None and self.media_duration_seconds <= 0:
            raise ValueError("media_duration_seconds must be greater than 0")
        return self

    @property
    def display_type(self):
        return TRACK_TYPE_LABELS.get(self.track_type, self.track_type)

    @property
    def primary_path(self):
        return Path(self.paths[0])

    def with_extraction(self, **changes):
        return replace(self, extraction=replace(self.extraction, **changes)).validate()

    def with_photo_limit(self, photo_limit):
        return replace(self, photo_limit=int(photo_limit or 0)).validate()


def make_track_id(index, label):
    safe = "".join(ch if ch.isalnum() else "_" for ch in label.strip()).strip("_").lower()
    while "__" in safe:
        safe = safe.replace("__", "_")
    return f"track_{index:03d}_{safe or 'track'}"


def create_track(index, track_type, label, paths, extraction=None, photo_limit=0, media_duration_seconds=None):
    normalized_paths = tuple(str(Path(path)) for path in paths)
    track = WorkbenchTrack(
        track_id=make_track_id(index, label),
        track_type=track_type,
        label=label,
        paths=normalized_paths,
        extraction=extraction or ExtractionSettings(),
        photo_limit=int(photo_limit or 0),
        media_duration_seconds=media_duration_seconds,
    )
    return track.validate()
