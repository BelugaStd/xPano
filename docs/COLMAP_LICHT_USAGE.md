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

The software can use plain command names from `PATH`, manually selected executable paths, or these environment variables:

```powershell
$env:XPANO_COLMAP="C:\Path\To\COLMAP\colmap.exe"
$env:XPANO_LICHTFIELD="C:\Path\To\LICHT Field Studio\lichtfield-studio.exe"
```

The GUI also exposes executable path fields under advanced parameters.

## CLI: COLMAP Only

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --output "D:\path\to\output_colmap" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1 `
  --colmap "C:\Path\To\COLMAP\colmap.exe"
```

Expected native COLMAP backend output:

```text
output_colmap/
  work/
    xpano_manifest.json
  colmap/
    database.db
    colmap_images/
      000001_left.jpg
      000001_right.jpg
      ...
    sparse/
      0/
        cameras.bin
        images.bin
        points3D.bin
  xpano_run_summary.json
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
4. Open advanced parameters.
5. Confirm or locate the COLMAP executable.
6. Optional: enable `LICHT Field Studio` post-processing and enter point count / bilateral grid.
7. Click `Check Environment`.
8. Run the job once all required dependencies show `OK`.

## Current Limitation

The verified production path remains the Metashape Station-to-Folder workflow. The COLMAP and LICHT path has command planning, dependency checks, GUI/CLI wiring, and regression tests, but still requires a real local end-to-end validation with installed COLMAP and LICHT Field Studio.
