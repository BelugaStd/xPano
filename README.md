# xPano

[简体中文](README.zh-CN.md)

xPano is a Windows desktop workflow for turning panoramic video, ordinary video, and photographs into a COLMAP reconstruction, point-cloud variants, and LichtFeld Gaussian-training data.

It keeps the normal workflow in one project folder:

```text
Import materials -> Prepare frames/photos -> Reconstruct -> Inspect results -> Densify or train
```

## What You Can Do

- Import DJI/Insta360 dual-fisheye panorama video, ordinary video, standard photos, and aerial photos.
- Sample video, prepare original fisheye/frame images, and preview photo folders progressively.
- Align panorama material with a panorama-first Metashape workflow; add ordinary photos/videos incrementally afterward.
- Export a standard COLMAP dataset (`images/` and `sparse/0/`) and inspect the point cloud in the app.
- Reopen an existing xPano project, open its Metashape PSX for manual correction, then re-export from PSX.
- Preview LichtFeld densification before saving it as a separate point-cloud version.
- Launch bundled LichtFeld Studio Gaussian training with progress, logs, presets, and advanced settings.

## Before You Start

| Item | Requirement |
|---|---|
| System | Windows 10/11 x64 |
| Core tools | xPano includes its Python runtime, FFmpeg, COLMAP, and WebView2 support. No system Python, FFmpeg, COLMAP, Git, CUDA Toolkit, or administrator permission is required for the core workflow. |
| Metashape | Required for the recommended panorama and mixed-material reconstruction workflow. Install and license Agisoft Metashape Professional yourself, then select its executable in xPano if it is not detected automatically. |
| Storage | Use a dedicated local project folder with sufficient free space. Extracted frames, generated images, point clouds, and training output can be much larger than the original material. |
| Network | The first use of LichtFeld densification may need to download its large runtime. It is not included in the standard installer. |

## Quick Start

1. Open xPano. The default screen is **Materials**.
2. Add files or a photo folder. Import one material source as one track. The first import creates an `xPano` project folder beside that source, so place source material on a drive with enough space before starting.
3. Review the track settings, especially sampling rate, time range, and optional LUTs.
4. Click **Start Frame Extraction**. When all tracks are ready, click **Next: Alignment and Reconstruction**.
5. Choose a reconstruction backend and start the job.
6. Review the point cloud in **Results**. Continue with densification or Gaussian training only after the reconstruction is acceptable.

### Supported Materials

| Track | Recommended input | Notes |
|---|---|---|
| Panorama video | `.osv`, `.insv` | Use the original dual-fisheye source. Keep paired `.insv` files together in the same folder. xPano aligns original fisheye imagery rather than ERP or manually cut cubemaps. |
| Ordinary video | `.mp4`, `.mov`, `.avi`, `.mkv` | Choose the initial view angle that best matches the footage. |
| Standard photos | JPG/JPEG, PNG, TIF/TIFF, BMP | Select a folder or supported image files. Photos from different cameras are separated automatically when metadata differs. |
| Aerial photos | JPG/JPEG, PNG, TIF/TIFF, BMP | Import as a separate aerial-photo track. |

Keep source files in their original location until material preparation has completed. Do not rename, move, or delete the source folder while a task is running.

### Color LUTs

- A custom `.cube` style LUT can be applied to imported videos and photos.
- For DJI `.osv` footage, enable the bundled restoration LUT only when the source is D-Log M footage that needs Rec.709 restoration.
- Insta360 `.insv` restoration remains manual: select a LUT that matches the camera and capture profile.
- When both are used, xPano applies restoration first and the style LUT second.

## Reconstruction

### Metashape: Recommended

Use **Metashape** for panorama projects and all mixed-material projects.

xPano first aligns panorama stations, then adds ordinary video frames, standard photos, or aerial photos incrementally. This preserves the panorama solution as the reconstruction backbone. The generated Metashape project is saved at:

```text
work/xpano.psx
```

You can open this PSX in Metashape to make manual corrections. Save the PSX, return to xPano, and use **Re-export from PSX** in the reconstruction workspace. When Metashape contains several usable Components, select the one to export; the largest is selected by default.

### COLMAP: Panorama Only

COLMAP is bundled and does not require a separate installation. In the current product, it is intended for panorama-only reconstruction. xPano blocks the COLMAP mixed-material path because it has not passed the required regression validation.

## Results, Densification, and Training

### Point Cloud and Versions

The Results workspace opens the reconstruction point cloud and keeps the standard result intact. You can preview a saved point-cloud version and choose which usable version is used for training.

### LichtFeld Densification

Open the densification panel from Results, configure its runtime if required, then run it on the current reconstruction.

The densified output is a candidate preview first. Inspect it before choosing **Save as Version**. Saving creates a separate point-cloud version; it does not overwrite the standard reconstruction. Closing the preview also keeps the candidate for later review.

### Gaussian Training

Open **Gaussian Training** after reconstruction has exported a training dataset and a usable point-cloud version is selected. Choose a preset or adjust the parameters, then start training.

LichtFeld Studio launches with its GUI by default while xPano reports progress and logs. The default standard preset uses 30,000 iterations; faster and higher-quality presets are also available. Training time and GPU memory usage grow with image resolution, iteration count, and the maximum number of Gaussians.

## Project Files and Reopening

An xPano project is the entire selected project folder, not one output file. Typical contents are:

```text
MyProject/
  xpano_project.json          # xPano project state
  work/
    xpano_manifest.json       # prepared-material manifest
    xpano.psx                 # Metashape project, when Metashape is used
    jobs/                     # recoverable task logs and snapshots
  images/                     # exported training/reconstruction images
  sparse/0/
    cameras.bin
    images.bin
    points3D.bin
  xpano_run_summary.json      # reconstruction summary
```

Some folders appear only after their corresponding stage completes. To reopen work, use **Open Project** or drag the complete project root folder into xPano. Keep the folder structure together when copying, backing up, or moving a project.

## Important Notes

- Start with a short sample or a lower sampling rate for long videos. More frames improve coverage only when they add useful viewpoint change; they also increase extraction, matching, memory, and storage cost.
- Good reconstruction depends on sharp, well-exposed footage with sufficient overlap and limited moving subjects. xPano cannot guarantee that every source will align correctly.
- If alignment splits into multiple Components, inspect the result before exporting or training. Choose the main Component, usually the one with the most aligned cameras, or correct the PSX manually in Metashape and re-export.
- Do not manually replace files inside `images/`, `sparse/0/`, or `work/` while xPano is running. Use the in-app re-export and point-cloud version actions so project state stays consistent.
- Metashape is not distributed with xPano. You are responsible for a valid Metashape Professional installation and license.
- xPano, Metashape, COLMAP, FFmpeg, LichtFeld Studio, RoMa, and other bundled components remain subject to their respective licenses and notices.

For implementation-level reference, see [GUI_QUICKSTART.md](GUI_QUICKSTART.md), [docs/VERIFIED_WORKFLOW.md](docs/VERIFIED_WORKFLOW.md), and [docs/COLMAP_DENSIFICATION.md](docs/COLMAP_DENSIFICATION.md).
