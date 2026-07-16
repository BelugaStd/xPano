import builtins
import importlib
import sys
import types
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np


class ExportColmapTests(unittest.TestCase):
    def _load_module_with_metashape(self, metashape):
        previous_metashape = sys.modules.get("Metashape")
        sys.modules.pop("scripts.export_colmap", None)
        sys.modules["Metashape"] = metashape
        try:
            return importlib.import_module("scripts.export_colmap")
        finally:
            if previous_metashape is None:
                sys.modules.pop("Metashape", None)
            else:
                sys.modules["Metashape"] = previous_metashape

    def test_module_import_does_not_require_cv2(self):
        previous_metashape = sys.modules.get("Metashape")
        sys.modules.pop("scripts.export_colmap", None)
        sys.modules.pop("scripts.export_remap", None)
        sys.modules["Metashape"] = types.SimpleNamespace()

        real_import = builtins.__import__

        def import_without_cv2(name, *args, **kwargs):
            if name == "cv2":
                raise ModuleNotFoundError("No module named 'cv2'")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=import_without_cv2):
                module = importlib.import_module("scripts.export_colmap")
        finally:
            sys.modules.pop("scripts.export_colmap", None)
            if previous_metashape is None:
                sys.modules.pop("Metashape", None)
            else:
                sys.modules["Metashape"] = previous_metashape

        self.assertTrue(hasattr(module, "remap_bilinear"))

    def test_frame_sensor_type_wins_over_stale_fisheye_calibration_type(self):
        metashape = types.SimpleNamespace(
            Sensor=types.SimpleNamespace(Type=types.SimpleNamespace(Frame="Frame", Fisheye="Fisheye"))
        )
        module = self._load_module_with_metashape(metashape)
        sensor = types.SimpleNamespace(
            type=metashape.Sensor.Type.Frame,
            calibration=types.SimpleNamespace(type="Fisheye"),
        )

        self.assertFalse(module.sensor_is_fisheye_like(sensor))

    def test_cubemap_save_failure_is_not_silent(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "missing" / "face.jpg"

            with self.assertRaises(Exception):
                module.threaded_remap_and_save(None, None, None, output)

    def test_remap_backend_uses_numpy_when_opencv_is_missing(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())

        self.assertEqual(module.select_remap_backend(None, "auto"), "numpy")

    def test_auto_remap_backend_chooses_measured_fastest_valid_backend(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        fake_cv2 = types.SimpleNamespace(
            ocl=types.SimpleNamespace(haveOpenCL=lambda: True),
        )

        with patch(
            "scripts.export_remap.benchmark_remap_backends",
            return_value={"opencv": 0.004, "opencl": 0.020},
        ):
            self.assertEqual(module.select_remap_backend(fake_cv2, "auto"), "opencv")

        with patch(
            "scripts.export_remap.benchmark_remap_backends",
            return_value={"opencv": 0.040, "opencl": 0.010},
        ):
            self.assertEqual(module.select_remap_backend(fake_cv2, "auto"), "opencl")

    def test_forced_opencl_falls_back_to_compiled_cpu_when_unavailable(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        fake_cv2 = types.SimpleNamespace(
            ocl=types.SimpleNamespace(haveOpenCL=lambda: False),
        )

        self.assertEqual(module.select_remap_backend(fake_cv2, "opencl"), "opencv")

    def test_opencl_backend_explicitly_enables_opencl_execution(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        enabled = []
        fake_cv2 = types.SimpleNamespace(
            ocl=types.SimpleNamespace(
                haveOpenCL=lambda: True,
                setUseOpenCL=enabled.append,
            ),
        )

        engine = module.RemapEngine(fake_cv2, "opencl")

        self.assertEqual(engine.backend, "opencl")
        self.assertEqual(enabled, [True])

    def test_accelerated_remap_failure_falls_back_observably_to_numpy(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        source = np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3)
        mx, my = np.meshgrid(
            np.linspace(0.2, 6.8, 6, dtype=np.float32),
            np.linspace(0.4, 6.6, 6, dtype=np.float32),
        )
        warnings = []
        fake_cv2 = types.SimpleNamespace(
            INTER_LINEAR=1,
            BORDER_CONSTANT=0,
            remap=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("driver failed")),
        )
        engine = module.RemapEngine(fake_cv2, "opencv", warnings.append)

        result = engine.remap(source, mx, my)

        np.testing.assert_array_equal(result, module.remap_bilinear(source, mx, my))
        self.assertEqual(engine.backend, "numpy")
        self.assertEqual(len(warnings), 1)
        self.assertIn("driver failed", warnings[0])

    def test_camera_image_signature_ignores_pose_but_invalidates_pixel_inputs(self):
        module = self._load_module_with_metashape(types.SimpleNamespace())
        calibration = types.SimpleNamespace(
            width=100,
            height=80,
            f=50.0,
            cx=0.1,
            cy=-0.2,
            k1=0.01,
            k2=0.0,
            k3=0.0,
            k4=0.0,
            p1=0.0,
            p2=0.0,
            b1=0.0,
            b2=0.0,
            type="Fisheye",
        )
        sensor = types.SimpleNamespace(key=7, type="Fisheye", calibration=calibration)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.jpg"
            source.write_bytes(b"source-a")
            camera = types.SimpleNamespace(
                key=3,
                transform="pose-a",
                photo=types.SimpleNamespace(path=str(source)),
                sensor=sensor,
            )
            strategy = {"type": "Cubemap", "opt_W": 100, "info_str": "Fisheye"}
            source_cache = {}

            baseline = module.camera_image_signature(camera, strategy, source_cache)
            camera.transform = "pose-b"
            self.assertEqual(baseline, module.camera_image_signature(camera, strategy, source_cache))

            calibration.f = 51.0
            self.assertNotEqual(baseline, module.camera_image_signature(camera, strategy, source_cache))
            calibration.f = 50.0
            source.write_bytes(b"source-b")
            source_cache.clear()
            self.assertNotEqual(baseline, module.camera_image_signature(camera, strategy, source_cache))
            source.write_bytes(b"source-a")
            source_cache.clear()
            self.assertNotEqual(
                baseline,
                module.camera_image_signature(camera, {**strategy, "opt_W": 102}, source_cache),
            )



if __name__ == "__main__":
    unittest.main()
