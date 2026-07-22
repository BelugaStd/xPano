import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.xpano_lut_presets import (
    DJI_OSMO_360_DLOGM_REC709_PRESET,
    resolve_color_lut_path,
)


class XpanoLutPresetTests(unittest.TestCase):
    def test_resolves_the_bundled_dji_osmo_lut_and_rejects_tampering(self):
        payload = b"LUT_3D_SIZE 2\n0 0 0\n1 1 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "luts" / "dji-osmo360-dlogm-rec709-v1.cube"
            path.parent.mkdir()
            path.write_bytes(payload)

            self.assertEqual(
                resolve_color_lut_path(
                    root,
                    {"colorLutPreset": DJI_OSMO_360_DLOGM_REC709_PRESET},
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                ),
                path,
            )

            path.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum"):
                resolve_color_lut_path(
                    root,
                    {"colorLutPreset": DJI_OSMO_360_DLOGM_REC709_PRESET},
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                )

