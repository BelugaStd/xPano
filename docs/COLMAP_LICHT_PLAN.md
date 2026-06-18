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
  - runs memory-capped CPU `feature_extractor`, `sequential_matcher`, and `mapper`,
  - keeps native COLMAP intermediates under `colmap/`,
  - publishes the best native sparse model as the same downstream artifact shape
    used by Metashape: cubemap `images/` and `sparse/0`.
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
- The COLMAP path has been smoke-tested locally on 20 sampled panorama frames.
  It now matches the Metashape output structure, but remains less accurate/sparser
  than the verified Metashape Station workflow on the same test.
  A 20-frame exhaustive-matcher probe was worse than the default sequential setup
  on this dataset, so the low-memory sequential configuration remains the safer
  default.
  A probe with `Mapper.tri_ignore_two_view_tracks=0` also regressed to a tiny
  two-image reconstruction on this dataset, so that option is not enabled by
  default despite the thinner sparse point cloud.
  A COLMAP rig-configurator probe following the official two-stage flow
  completed successfully and increased sparse points from `1949` to `2404`, but
  camera-center agreement with the Metashape reference became worse
  (`0.0368` RMSE vs `0.0208` for the default run after similarity alignment).
  Since downstream reconstruction is highly pose-sensitive, the rig probe is
  not the default yet.
  The accepted comparison run produced matching downstream structure
  (`200` cubemap images, `10` PINHOLE cameras, `200` registered images), but
  sparse geometry remained much thinner than Metashape (`1949` vs `15126`
  points). Camera centers still matched the Metashape trajectory after similarity
  alignment with about `0.0208` RMSE on `40` source fisheye camera centers, so the
  COLMAP path is usable as a structural/backend alternative but not yet as an
  accuracy-equivalent replacement for the Metashape Station workflow.
- LICHT still needs a real local end-to-end run once `lichtfield-studio` is installed or configured.
- On the current development machine, `ffmpeg` and Metashape are discoverable. COLMAP no longer needs to be on PATH if the `tools/colmap` bundle is installed. LICHT Field Studio still needs either a selected executable, environment variable, or PATH entry.

