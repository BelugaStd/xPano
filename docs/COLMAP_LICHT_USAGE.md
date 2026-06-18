# COLMAP / LICHT Field Studio Usage

This document covers the experimental COLMAP backend and optional LICHT Field Studio post-processing path.

## Environment Check

Before running the COLMAP or LICHT path, check the current machine:

```powershell
python scripts\run_xpano_tracks_job.py --check-env --backend colmap --run-lichtfield
```

Use strict mode when you want CI, packaging, or a local smoke test to fail if a required executable is missing:

```powershell
python scripts\run_xpano_tracks_job.py --check-env --backend colmap --run-lichtfield --strict
```

The dependency resolver checks:

- `ffmpeg`
- `colmap`
- `lichtfield-studio` when LICHT post-processing is enabled

The Metashape executable is skipped for the COLMAP backend.

## Executable Discovery

The software prefers a bundled COLMAP executable under `tools/colmap`, so users do not need to install COLMAP globally or edit `PATH`.

Recommended bundled install:

```powershell
INSTALL_COLMAP.bat
```

This downloads the official `colmap-x64-windows-nocuda.zip` release into `tools/colmap`. For the larger CUDA build:

```powershell
INSTALL_COLMAP.bat -Variant cuda
```

Supported bundled layouts include:

```text
tools/colmap/COLMAP.bat
tools/colmap/colmap.exe
tools/colmap/bin/colmap.exe
tools/colmap/<release-folder>/COLMAP.bat
tools/colmap/<release-folder>/bin/colmap.exe
```

The resolver order is:

1. `XPANO_COLMAP`
2. bundled COLMAP under `tools/colmap`
3. `PATH`
4. common system install locations

The software can also use manually selected executable paths or these environment variables:

```powershell
$env:XPANO_COLMAP="C:\Path\To\COLMAP\colmap.exe"
$env:XPANO_LICHTFIELD="C:\Path\To\LICHT Field Studio\lichtfield-studio.exe"
```

The GUI also exposes executable path fields under advanced parameters.

## Optional: LichtFeld Densification Plugin

The workflow can optionally run the external
`Lichtfeld-Densification-Plugin` after a Metashape or COLMAP backend has
produced the standard `images/` plus `sparse/0/` output. The plugin is not
vendored into this repository because it is GPL-3.0-or-later and has heavy
ML dependencies. Instead, install it into the project-local tools directory:

```powershell
INSTALL_LFS_DENSIFY.bat
```

The installer defaults to the Tsinghua PyPI mirror because the required wheels
are large. Override the mirror if needed:

```powershell
INSTALL_LFS_DENSIFY.bat -PipIndex https://mirrors.aliyun.com/pypi/simple
```

By default it installs the verified Windows CPU PyTorch pair
`torch==2.8.0` and `torchvision==0.23.0`, plus `pycolmap==4.0.4` and
`open3d==0.19.0`. This is slower for dense matching but is the most reliable
default for making the plugin importable and testable on Windows. Real
densification with RoMa is computationally heavy; use CUDA PyTorch for practical
large scenes when the local driver/toolchain supports it. To try CUDA PyTorch:

```powershell
INSTALL_LFS_DENSIFY.bat -UseCudaTorch
```

On the current Windows test machine, `-UseCudaTorch` was verified with
`torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, CUDA available, and one GPU
visible to PyTorch.

This installs the external plugin into:

```text
tools/lichtfeld-densification-plugin/
```

and creates a dedicated Python environment at:

```text
.venv-densify/
```

For a source-only install without Python dependencies:

```powershell
INSTALL_LFS_DENSIFY.bat -SkipDeps
```

The densification stage calls a local standalone runner that loads the plugin
source from `tools/lichtfeld-densification-plugin/` and provides the minimal
LichtFeld logging API needed by the algorithm. The plugin itself is not modified
or committed. Output is written as `sparse/0/points3D_dense.ply`; the validated
COLMAP `points3D.bin` is not overwritten.

RoMaV2 model weights are cached project-locally at:

```text
tools/torch-cache/hub/checkpoints/romav2.pt
```

The runner sets `TORCH_HOME` to `tools/torch-cache`, so first-run downloads do
not silently fall back to the user profile. If densification appears to run with
no output, check whether `romav2.pt` or the DINOv3 torch hub repo is still being
downloaded.

The dependency check verifies both the plugin source and the dedicated Python
environment, then loads the standalone runner and checks that the plugin CLI
parameters are visible:

```powershell
python scripts\run_xpano_tracks_job.py --check-env --backend colmap --run-lfs-densify
```

If it reports `MISSING: LichtFeld densification Python`, run
`INSTALL_LFS_DENSIFY.bat`. The dependency install is large because it includes
PyTorch, pycolmap, Open3D, and RoMa-related packages, so the first run may take
several minutes.

You can also inspect the plugin CLI parameters directly:

```powershell
.venv-densify\Scripts\python.exe scripts\run_lichtfeld_densify_standalone.py `
  --plugin-dir tools\lichtfeld-densification-plugin `
  --help
```

## CLI: COLMAP Only

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --output "D:\path\to\output_colmap" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1 `
  --colmap "C:\Path\To\COLMAP\colmap.exe"
```

COLMAP density presets:

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --colmap-density-preset high-density `
  --output "D:\path\to\output_colmap_hd" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1
```

- `stable`: default low-memory pose-first configuration.
- `high-density`: uses more SIFT features, wider sequential matching, and guided matching.
- `experimental-high-density`: also lowers SIFT peak threshold and relaxes mapper filtering; use only for small tests first.

On the 20-frame JiaoShi probe, `high-density` increased COLMAP sparse points from `2191` to `3275` while keeping all `40` source fisheye images registered. Camera-center RMSE against the Metashape reference changed from `0.0269` to `0.0287`, so this preset is denser but slightly less pose-tight than `stable`.

Expected COLMAP backend output:

```text
output_colmap/
  work/
    xpano_manifest.json
  images/
    cube_front_*.jpg
    cube_left_*.jpg
    cube_right_*.jpg
    cube_top_*.jpg
    cube_bottom_*.jpg
  sparse/
    0/
      cameras.bin
      images.bin
      points3D.bin
  colmap/
    database.db
    colmap_images/
      left/
      right/
      ...
    sparse/
      ...
  xpano_run_summary.json
```

The `colmap/` directory is the native COLMAP working cache. The formal downstream
artifact is the same as the Metashape backend: `images/` plus `sparse/0/`.

Verify the COLMAP backend output:

```powershell
python scripts\verify_xpano_output.py `
  --backend colmap `
  --output "D:\path\to\output_colmap" `
  --expect-single-sparse
```

## CLI: COLMAP + LichtFeld Densification

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --run-lfs-densify `
  --lfs-densify-roma fast `
  --lfs-densify-max-points 200000 `
  --output "D:\path\to\output_dense" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1
```

Useful parameters:

- `--lfs-densify-roma`: `turbo`, `fast`, `base`, `high`, or `precise`.
- `--lfs-densify-num-refs`: reference views used for dense matching. Values
  greater than `1` are interpreted as an image count; fractional values below
  `1` are interpreted by the plugin as a fraction.
- `--lfs-densify-max-points`: `0` means unlimited.
- `--lfs-densify-python`: defaults to `.venv-densify\Scripts\python.exe`.
- `--lfs-densify-plugin`: override the default `tools/lichtfeld-densification-plugin`.

After densification, xPano converts the plugin PLY to COLMAP `points3D.bin`,
backs up the original sparse points as `points3D_sparse_original.bin`, and
writes a merged `points3D_dense.bin`. Downstream 3DGS training can continue to
read the standard `sparse/0/points3D.bin`.

Verified local smoke result:

```text
_final_jiaoshi_20_colmap_outputs/colmap-colmap/sparse/0/points3D_dense_10k.ply
_final_jiaoshi_20_colmap_outputs/colmap-colmap/sparse/0/points3D.bin
original sparse points: 2,191
dense added points: 10,000
merged COLMAP points: 12,191
```

Environment check:

```powershell
python scripts\run_xpano_tracks_job.py --check-env --backend colmap --run-lfs-densify
```

## CLI: COLMAP + LICHT Field Studio

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --run-lichtfield `
  --lichtfield "C:\Path\To\LICHT Field Studio\lichtfield-studio.exe" `
  --lichtfield-point-count 120000 `
  --lichtfield-bilateral-grid 16 `
  --output "D:\path\to\output_licht" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1 `
  --colmap "C:\Path\To\COLMAP\colmap.exe"
```

The LICHT command receives:

- COLMAP sparse model path
- COLMAP image directory
- output directory
- point count
- bilateral grid

## GUI

1. Add at least one panorama video track.
2. Select an output folder.
3. Choose `COLMAP` in the backend section.
4. If `tools/colmap` contains the bundled executable, no COLMAP path selection is required.
5. Open advanced parameters only when you want to override the bundled executable.
6. Optional: enable `LICHT Field Studio` post-processing and enter point count / bilateral grid.
7. Optional: enable `Run LichtFeld densification`, choose RoMa quality, and set max dense points.
8. Click `Check Environment`.
9. Run the job once all required dependencies show `OK`.

## Current Limitation

The verified production path remains the Metashape Station-to-Folder workflow. The COLMAP and LICHT path has command planning, dependency checks, GUI/CLI wiring, and regression tests, but still requires a real local end-to-end validation with installed COLMAP and LICHT Field Studio.
