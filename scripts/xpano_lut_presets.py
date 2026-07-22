from __future__ import annotations

import hashlib
from pathlib import Path


DJI_OSMO_360_DLOGM_REC709_PRESET = "builtin:dji-osmo360-dlogm-rec709"
DJI_OSMO_360_DLOGM_REC709_RELATIVE_PATH = Path("luts") / "dji-osmo360-dlogm-rec709-v1.cube"
DJI_OSMO_360_DLOGM_REC709_SHA256 = "b18162854ab47702068410c33afa98a8cb6eef159fc5a04ce0e65fad0fd8947e"


def resolve_color_lut_path(app_root, extraction, expected_sha256=DJI_OSMO_360_DLOGM_REC709_SHA256):
    manual_path = str(extraction.get("colorLutPath") or "").strip()
    preset = str(extraction.get("colorLutPreset") or "").strip()
    if manual_path and preset:
        raise ValueError("color LUT path and preset cannot both be set")
    if not preset:
        return Path(manual_path) if manual_path else None
    if preset != DJI_OSMO_360_DLOGM_REC709_PRESET:
        raise ValueError(f"unknown color LUT preset: {preset}")
    path = Path(app_root) / DJI_OSMO_360_DLOGM_REC709_RELATIVE_PATH
    if not path.is_file():
        raise ValueError(f"bundled DJI color LUT is missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError("bundled DJI color LUT checksum does not match")
    return path
