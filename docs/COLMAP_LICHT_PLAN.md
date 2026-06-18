# xPano COLMAP / LICHT Field Studio Plan

## Goal
Extend the verified Metashape workflow into a backend-pluggable reconstruction pipeline so the same GUI and CLI can drive Metashape, COLMAP, and optional LICHT Field Studio post-processing.

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
5. Add LICHT Field Studio CLI integration as a post-COLMAP algorithm stage.
6. Parameterize tunable steps such as point count, bilateral grid, and similar algorithm knobs.
7. Expand verification with regression tests for each backend and stage.

## Current status
- Metashape workflow exists and is verified.
- GUI exists and drives the shared manifest pipeline.
- COLMAP backend is implemented as an experimental native backend:
  - builds a COLMAP image set from xPano dual-fisheye manifest frames,
  - runs `feature_extractor`, `exhaustive_matcher`, and `mapper`,
  - validates `database.db` and sparse model outputs.
- LICHT Field Studio CLI integration is implemented as an optional post-COLMAP stage:
  - supports executable path selection,
  - supports point count and bilateral grid parameters,
  - is reachable from both GUI and CLI.
- GUI supports backend selection, COLMAP executable selection, LICHT executable selection, LICHT parameter entry, and environment checks.
- CLI supports `--backend colmap`, `--colmap`, `--run-lichtfield`, `--lichtfield`, `--lichtfield-point-count`, `--lichtfield-bilateral-grid`, `--check-env`, and strict dependency checking.
- Dependency checks and command planning are covered by regression tests.
- COLMAP can now be bundled under `tools/colmap`; the GUI and CLI resolve this project-local copy before falling back to `PATH`.
- `scripts/install_colmap.ps1` can download the official Windows No-CUDA or CUDA release into the project-local bundle directory.

## Remaining verification gap
- The Metashape path is the stable reference path.
- The COLMAP and LICHT paths are code-complete enough for command execution, but still need a real local end-to-end run once `colmap` and `lichtfield-studio` are installed or configured.
- On the current development machine, `ffmpeg` and Metashape are discoverable. COLMAP no longer needs to be on PATH if the `tools/colmap` bundle is installed. LICHT Field Studio still needs either a selected executable, environment variable, or PATH entry.

