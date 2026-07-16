"""Small, dependency-free helpers for selecting one Metashape component."""

from __future__ import annotations


DEFAULT_COMPONENT_KEY = "__all__"


def _tie_point_count(component):
    tie_points = getattr(component, "tie_points", None)
    points = getattr(tie_points, "points", None)
    try:
        return len(points) if points is not None else 0
    except TypeError:
        return 0


def component_key_for_camera(camera):
    """Return a stable string key for a camera's Metashape component."""
    component = getattr(camera, "component", None)
    key = getattr(component, "key", component)
    if key is None:
        key = getattr(camera, "component_id", None)
    return str(key) if key is not None else DEFAULT_COMPONENT_KEY


def component_inventory(cameras, components=()):
    """Build a serializable inventory from aligned cameras only.

    Metashape versions expose component membership either as ``camera.component``
    or ``camera.component_id``.  The fallback key keeps single-component PSX
    files exportable when the native object does not expose a component list.
    """
    entries = {}
    for component in components or ():
        key = getattr(component, "key", component)
        if key is None:
            continue
        key = str(key)
        entries.setdefault(key, {
            "componentKey": key,
            "alignedCameraCount": 0,
            "totalCameraCount": 0,
            "tiePointCount": _tie_point_count(component),
        })

    for camera in cameras:
        key = component_key_for_camera(camera)
        entry = entries.setdefault(key, {
            "componentKey": key,
            "alignedCameraCount": 0,
            "totalCameraCount": 0,
            "tiePointCount": 0,
        })
        entry["totalCameraCount"] += 1
        if getattr(camera, "transform", None) is not None:
            entry["alignedCameraCount"] += 1

    return sorted(
        entries.values(),
        key=lambda item: (
            -item["alignedCameraCount"],
            -item.get("tiePointCount", 0),
            -item["totalCameraCount"],
            item["componentKey"],
        ),
    )


def select_component_key(inventory, requested=None):
    """Use an explicit key when valid, otherwise choose the largest component."""
    keys = {item["componentKey"] for item in inventory}
    if requested is not None and str(requested) in keys:
        return str(requested)
    return inventory[0]["componentKey"] if inventory else None


def component_membership_is_ambiguous(inventory):
    native_components = [item for item in inventory if item["componentKey"] != DEFAULT_COMPONENT_KEY]
    fallback = next((item for item in inventory if item["componentKey"] == DEFAULT_COMPONENT_KEY), None)
    return len(native_components) > 1 and fallback is not None and fallback["alignedCameraCount"] > 0


def camera_belongs_to_component(camera, selected_key):
    return selected_key in (None, DEFAULT_COMPONENT_KEY) or component_key_for_camera(camera) == str(selected_key)
