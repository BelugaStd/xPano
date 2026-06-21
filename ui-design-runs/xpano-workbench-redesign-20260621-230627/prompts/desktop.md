Create a polished, production-realistic UI design mockup for xPano Workbench, a desktop reconstruction app for panorama video, ordinary video, Metashape, COLMAP, and COLMAP export workflows.

Audience: 3D reconstruction users, Gaussian splatting creators, drone/action-camera operators, and technical artists.
Primary workflow: import multiple media tracks, configure extraction settings per track, watch live frame previews, run alignment, inspect cameras and point clouds, and export COLMAP-ready output.
Design system direction: Apple-inspired commercial workbench with layered rounded surfaces, restrained dark-neutral palette, clear hierarchy, subtle motion-ready components, and precise SVG iconography.
Design DNA blend: 3D / Interactive Site with supporting cues from Operational Dashboard and AI Tools.

Visual rules:
- Original design, not a copy of any existing brand or website.
- Realistic desktop app interface that can be implemented in PySide6/Qt or React/CSS.
- Clear information hierarchy, readable UI labels, coherent component system.
- Use consistent typography, spacing, border radius, icon style, and color tokens.
- Avoid decorative gradient blobs, random bokeh/orbs, fake unreadable walls of text, and impossible UI geometry.
- Show the actual product interface, not a marketing poster.
- Do not use emoji as icons; use clean line icons.

Viewport: desktop app, 16:9 horizontal composition, approximately 1440x900.
Layout requirements:
- Use a desktop-native workbench layout with a top command bar, a left workflow/track rail, a left inspector panel for selected track parameters, and a large right reconstruction stage.
- Include draggable split panes between parameter/track controls and the preview/reconstruction stage.
- The active screen is the extraction stage: show a selected panorama video track with per-track seconds-per-frame, max frames, camera type, backend role, and output naming settings.
- The right stage shows live dual-fisheye preview cards, a compact extraction timeline, per-track progress, and a collapsible console.
- Include clear run controls: start, pause, stop, environment check, open output, export COLMAP.
- Prioritize efficient scanning, clear action hierarchy, and professional component density.

Output: one single desktop UI screen only. Do not include mobile frames, annotations, browser chrome, or multiple viewport mockups.
