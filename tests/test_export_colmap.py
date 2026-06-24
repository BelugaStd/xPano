import builtins
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class ExportColmapTests(unittest.TestCase):
    def test_module_import_does_not_require_cv2(self):
        previous_metashape = sys.modules.get("Metashape")
        sys.modules.pop("scripts.export_colmap", None)
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


if __name__ == "__main__":
    unittest.main()
