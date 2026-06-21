# UI Image Design Handoff

## Product Direction
- Product / feature: xPano Workbench redesign.
- Audience: 3D reconstruction users, 3DGS creators, drone/action-camera operators, and technical artists.
- Primary workflow: import tracks, configure per-track extraction, preview extraction live, monitor alignment, inspect cameras/point clouds, export COLMAP.
- Design DNA blend: 3D / Interactive Site, Operational Dashboard, AI Tools, Mobile-First App.
- Overall tone: mature commercial software, Apple-inspired but original.

## Generated Images
- Desktop: not generated in this environment.
- Mobile portrait: not generated in this environment.
- Mobile landscape: not generated in this environment.

## Visual Tokens
- Color palette: deep neutral base, graphite panels, soft white text, blue/cyan status accent, amber warning, red destructive actions.
- Typography: system UI family, medium weights for controls, larger scene titles only in stage header.
- Spacing: compact professional workbench density, 8/12/16/24 px rhythm.
- Border radius: 8-14 px depending on control scale.
- Elevation / shadow: subtle layered surfaces; avoid floating card piles.
- Iconography: bundled SVG line icons, no emoji.
- Motion intent: short fades, pane transitions, progress morphing, preview crossfades.

## Layout System
- Desktop: top command bar, left workflow rail, left inspector, right stage, bottom log/timeline.
- Mobile portrait: monitor mode with latest preview and collapsed tracks/log tabs.
- Mobile landscape: compact split monitor view.

## Component Inventory
- Navigation: workflow step rail, top command bar, tabbed stage modes.
- Primary work area: extraction preview, reconstruction viewport, output summary.
- Secondary panels: track inspector, backend settings, environment checks, logs.
- Cards / tables / lists: track rows, output artifacts, warning list.
- Controls: icon buttons, segmented backend selector, sliders/spinboxes, checkboxes, comboboxes.
- Loading / empty / error states: import placeholder, backend missing, running stage, failed stage.

## Responsive Rules
- Desktop is the primary target.
- Mobile views are optional companion/monitor views, not full creation flow.
- Split ratios persist per project or app settings.

## Implementation Notes
- Recommended shell: PySide6/Qt workbench rather than extending Tkinter.
- Real-time extraction preview requires changing extraction from post-process preview to file-pair watching or image pipe streaming.
- COLMAP live viewer should parse stdout for registered camera progress and poll sparse model files when available.
- Metashape live mode can expose true progress through API progress callbacks where supported; otherwise log/stage progress remains truthful.

## Open Questions
- Whether mobile companion views are part of this release or only design direction.
- Whether to use PySide6 Widgets, Qt Quick/QML, or a hybrid with embedded WebGL.
