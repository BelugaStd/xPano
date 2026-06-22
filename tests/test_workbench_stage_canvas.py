import unittest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - system Python may not have Qt installed.
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class StageCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["test"])

    def test_colmap_runtime_log_updates_registered_camera_count(self):
        from xpano_workbench.main import StageCanvas

        stage = StageCanvas()

        stage.append_log(
            "|20260622 15:43:11.347451 58560 incremental_pipeline.cc:524] "
            "Registering image #436 (num_reg_frames=458)"
        )

        self.assertEqual(stage._runtime_camera_count, 458)
        self.assertIn("458", stage.stage_subtitle.text())
        self.assertIn("458", stage.viewer_placeholder.text())

    def test_live_scene_preview_updates_without_loading_webengine(self):
        from xpano_workbench.main import StageCanvas
        from xpano_workbench.reconstruction_scene import CameraPose, ColoredPoint, ReconstructionScene

        stage = StageCanvas()
        scene = ReconstructionScene(
            sparse_points=(ColoredPoint((0.0, 0.0, 0.0), (255, 255, 255)),),
            dense_points=(),
            cameras=(
                CameraPose("a.jpg", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 1.0, 1.0),
                CameraPose("b.jpg", (1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 1.0, 1.0),
            ),
        )

        stage.set_reconstruction_scene(scene, live_only=True)

        self.assertIs(stage.live_preview.scene, scene)
        self.assertFalse(stage.viewer_placeholder.isVisible())

    def test_live_preview_camera_frustum_visibility_can_toggle(self):
        from xpano_workbench.main import LiveReconstructionPreview

        preview = LiveReconstructionPreview()

        preview.set_camera_frustums_visible(False)
        self.assertFalse(preview.show_camera_frustums)

        preview.set_camera_frustums_visible(True)
        self.assertTrue(preview.show_camera_frustums)

    def test_live_preview_projects_green_y_axis_downward(self):
        from xpano_workbench.main import LiveReconstructionPreview

        origin = LiveReconstructionPreview._project_world_to_preview(
            (0.0, 0.0, 0.0), center_x=0.0, center_y=0.0, scale=20.0, width=400, height=300
        )
        y_positive = LiveReconstructionPreview._project_world_to_preview(
            (0.0, 1.0, 0.0), center_x=0.0, center_y=0.0, scale=20.0, width=400, height=300
        )

        self.assertGreater(y_positive[1], origin[1])


if __name__ == "__main__":
    unittest.main()
