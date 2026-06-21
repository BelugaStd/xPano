# xPano Workbench Redesign Direction

## Product Summary
xPano is a reconstruction workbench for panorama video, ordinary video, photo folders, Metashape, COLMAP, and COLMAP export workflows.

## Audience
3D reconstruction users, 3DGS creators, drone/action-camera operators, and technical artists who need reliable batch automation without losing process visibility.

## Primary Workflow
Import tracks, configure extraction settings per track, monitor frame extraction with live previews, run alignment/reconstruction, inspect cameras and point clouds, then export COLMAP-ready output.

## Design DNA
Primary: 3D / Interactive Site.
Supporting: Operational Dashboard, AI Tools, Mobile-First App.

## Visual Direction
- Mature desktop workbench, not a utility dialog.
- Apple-inspired rounded geometry, layered surfaces, clear hierarchy, subtle motion.
- Left inspector for track-bound parameters; right preview/stage for images, cameras, point clouds, and logs.
- Adjustable columns and persistent workspace layout.
- Iconography from bundled SVG symbol assets, not emoji.

## Layout Principles
- Top command bar: project, import, run, pause, stop, export, environment status.
- Left sidebar: workflow steps and track list.
- Center/right stage: extraction preview, reconstruction viewer, output summary.
- Inspector: selected track or selected run stage parameters.
- Bottom console/timeline: collapsible logs, progress, warnings, and task history.

## Component Priorities
- Track cards with per-track extraction profile.
- Split panes with draggable dividers.
- Live dual-fisheye preview during extraction.
- 3D camera/point-cloud viewport during COLMAP and after Metashape export.
- Per-stage progress with truthful fallback when backend cannot expose fine progress.

## Constraints
- Keep Python processing code reusable.
- Do not copy Apple, DJI, Postshot, or Metashape branding.
- Prefer a PySide6/Qt workbench shell over deep Tkinter theming.
- Maintain portable Windows packaging.
