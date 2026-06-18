# xPano COLMAP / Lightfield Studio Plan

## Goal
Extend the current verified Metashape workflow into a backend-pluggable reconstruction pipeline so the same GUI can later drive COLMAP and Lightfield Studio CLI.

## Principles
- Keep the verified Metashape path as the stable default.
- Introduce backend abstraction without changing current user-visible behavior.
- Add one backend at a time, with tests at each layer.
- Prefer a single shared material-track manifest and a single GUI workflow.

## Phases
1. Stabilize the current Metashape pipeline as the reference implementation.
2. Add a backend interface and route the GUI/CLI through it.
3. Implement a COLMAP backend that mirrors the same material-track workflow.
4. Add export/interop adapters so COLMAP can emit the same downstream artifacts.
5. Add Lightfield Studio CLI integration as a post-COLMAP algorithm stage.
6. Parameterize tunable steps such as point count, bilateral grid, and similar algorithm knobs.
7. Expand verification with regression tests for each backend and stage.

## Current status
- Metashape workflow exists and is verified.
- GUI exists and drives the shared manifest pipeline.
- COLMAP backend is not yet implemented.
- Lightfield Studio CLI integration is not yet implemented.
