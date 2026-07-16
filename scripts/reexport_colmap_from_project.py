import argparse
import json
from pathlib import Path

try:
    from scripts.metashape_runtime_env import (
        METASHAPE_SITE_PACKAGES_FLAG,
        activate_metashape_runtime,
        metashape_site_packages_from_argv,
    )
except ImportError:
    from metashape_runtime_env import (
        METASHAPE_SITE_PACKAGES_FLAG,
        activate_metashape_runtime,
        metashape_site_packages_from_argv,
    )

activate_metashape_runtime(metashape_site_packages_from_argv())

import Metashape

import export_colmap

try:
    from scripts.component_selection import component_inventory, select_component_key
except ImportError:
    from component_selection import component_inventory, select_component_key


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(METASHAPE_SITE_PACKAGES_FLAG, help=argparse.SUPPRESS)
    parser.add_argument("--project", required=True)
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--reuse-images-dir")
    parser.add_argument("--image-cache-path")
    parser.add_argument("--image-cache-output")
    parser.add_argument("--component-key")
    return parser.parse_args()


def main():
    args = parse_args()
    doc = Metashape.app.document
    doc.open(str(Path(args.project)))
    chunk = doc.chunk
    inventory = component_inventory(chunk.cameras, getattr(chunk, "components", None))
    selected_component_key = select_component_key(inventory, args.component_key)
    export_colmap.run_mixed_export(
        str(Path(args.export_dir)),
        show_dialog=False,
        reuse_images_dir=args.reuse_images_dir,
        image_cache_path=args.image_cache_path,
        image_cache_output=args.image_cache_output,
        selected_component_key=selected_component_key,
    )
    aligned = sum(camera.transform is not None for camera in chunk.cameras)
    warnings = []
    if len(inventory) > 1:
        warnings.append("Multiple Metashape components found; manual PSX alignment is recommended.")
    if aligned < len(chunk.cameras):
        warnings.append("Some cameras were not aligned; the completed partial result remains exportable.")
    report = {
        "schemaVersion": 1,
        "processSucceeded": True,
        "state": "complete",
        "projectPath": str(Path(args.project)),
        "totalCameras": len(chunk.cameras),
        "alignedCameras": aligned,
        "alignmentRate": (aligned / len(chunk.cameras) * 100.0) if chunk.cameras else 0.0,
        "components": inventory,
        "selectedComponentKey": selected_component_key,
        "warnings": warnings,
    }
    (Path(args.export_dir) / "xpano_alignment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
