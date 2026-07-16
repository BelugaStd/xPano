import unittest
from types import SimpleNamespace

from scripts.component_selection import (
    camera_belongs_to_component,
    component_inventory,
    component_membership_is_ambiguous,
    select_component_key,
)


def camera(component_key, *, aligned=True):
    return SimpleNamespace(
        component=SimpleNamespace(key=component_key),
        transform=object() if aligned else None,
    )


class ComponentSelectionTests(unittest.TestCase):
    def test_largest_aligned_component_is_the_default(self):
        cameras = [camera(1), camera(1), camera(2), camera(2, aligned=False), camera(2, aligned=False)]

        inventory = component_inventory(cameras)

        self.assertEqual([item["componentKey"] for item in inventory], ["1", "2"])
        self.assertEqual(select_component_key(inventory), "1")

    def test_explicit_existing_component_overrides_default(self):
        inventory = component_inventory([camera(1), camera(1), camera(2)])

        self.assertEqual(select_component_key(inventory, "2"), "2")
        self.assertEqual(select_component_key(inventory, "missing"), "1")

    def test_tie_point_count_breaks_equal_camera_count_ties(self):
        components = [
            SimpleNamespace(key=1, tie_points=SimpleNamespace(points=[1])),
            SimpleNamespace(key=2, tie_points=SimpleNamespace(points=[1, 2, 3])),
        ]

        inventory = component_inventory([camera(1), camera(2)], components)

        self.assertEqual(select_component_key(inventory), "2")
        self.assertEqual(inventory[0]["tiePointCount"], 3)

    def test_export_membership_never_mixes_components(self):
        first = camera(1)
        second = camera(2)

        self.assertTrue(camera_belongs_to_component(first, "1"))
        self.assertFalse(camera_belongs_to_component(second, "1"))

    def test_multiple_native_components_without_camera_membership_are_ambiguous(self):
        components = [SimpleNamespace(key=1), SimpleNamespace(key=2)]
        cameras = [SimpleNamespace(component=None, component_id=None, transform=object())]

        inventory = component_inventory(cameras, components)

        self.assertTrue(component_membership_is_ambiguous(inventory))


if __name__ == "__main__":
    unittest.main()
