# xPano Multi-Track GUI

xPano Multi-Track GUI 是一个面向 360 全景视频、普通视频、普通照片和航拍照片的重建工作流工具。它把原始 `.osv` / `.insv` 双鱼眼素材、Metashape / COLMAP 对齐、COLMAP 格式导出、点云预览和可选 LichtFeld 致密化封装到一个 Tauri / React 桌面 GUI 中。

本 fork 延续原始 xPano 的核心思想：**对齐阶段直接使用原始左右鱼眼帧，不先拼接 ERP，也不先切 cubemap**。在 Metashape 后端中，全景帧先按 `Station` 约束完成初始空三，再释放为 `Folder` 做保守优化，最后导出适合 3D Gaussian Splatting、NeRF 和其它重建/训练工具使用的 COLMAP 目录。

## 本 Fork 的主要更新

- 新增 Tauri / React 桌面 GUI，替代早期脚本式或旧 GUI 操作。
- 新增素材轨工作流：全景视频、普通视频、普通照片、航拍照片可以在同一个项目中管理。
- 全景轨道只接受 `.osv` / `.insv`，避免把普通视频误导入为双鱼眼全景。
- 新增 Metashape / COLMAP 双后端。
- COLMAP、ffmpeg、内置 Python 随发布包携带，用户不需要额外配置 PATH。
- Metashape 后端仍要求用户本机安装并授权 Metashape，但 xPano 会把所需 Python 依赖安装到自身目录，再通过 `PYTHONPATH` 注入给 Metashape，不改写 Metashape 安装目录。
- 新增项目文件夹复用：xPano 输出目录可再次拖入 GUI，复用抽帧、manifest 和 Metashape `.psx`，支持手动调整工程后重新导出。
- 新增内置点云预览和相机视锥显示。
- 新增 LichtFeld densification 插件接入，可在 Metashape 或 COLMAP 输出后生成更密的 COLMAP 点云。
- 新增两种发布包：完整离线包和轻量增强包。

## 发布包选择

### `xPano-full-offline.zip`

完整离线包。适合给没有 Python、COLMAP、ffmpeg、torch 环境的用户直接使用。

包含：

- GUI 可执行文件和 `WebView2Loader.dll`
- 内置 Python 与基础依赖
- ffmpeg / ffprobe
- COLMAP
- Metashape Python 离线 wheels
- LichtFeld densification plugin
- RoMa / DINO 模型缓存
- `.venv-densify` 致密化 Python 运行时

无网情况下可用能力：

- GUI 启动
- OSV / INSV 抽帧
- Metashape 后端，前提是用户本机已安装并授权 Metashape
- COLMAP 后端
- 点云预览
- LichtFeld 致密化

### `xPano-light-colmap-densify-ready.zip`

轻量增强包。它仍然内置 COLMAP、ffmpeg、基础 Python、致密化插件和模型缓存，但不内置完整 torch / Open3D 致密化运行时。

包含：

- GUI 可执行文件和 `WebView2Loader.dll`
- 内置 Python 与基础依赖
- ffmpeg / ffprobe
- COLMAP
- Metashape Python 离线 wheels
- LichtFeld densification plugin
- RoMa / DINO 模型缓存

无网情况下可用能力：

- GUI 启动
- OSV / INSV 抽帧
- Metashape 后端，前提是用户本机已安装并授权 Metashape
- COLMAP 后端
- 点云预览

无网情况下，light 包的致密化只有在用户电脑已有兼容 Python 环境时才可用。该环境需要能导入：

```text
torch
torchvision
pycolmap
PIL
scipy
tqdm
einops
rich
open3d
```

如果没有这些依赖，light 包需要联网配置致密化环境，或者改用 full 包。
联网配置 light 包致密化环境时，目标电脑需要已有支持 `venv` 的 Python 3.10-3.12。发布包内置的 `binaries/python/python.exe` 是给 xPano 主流程使用的 embeddable Python，不包含 `pip` / `venv`，不能直接用于创建 torch / Open3D 致密化环境。

### `xPano-light-Setup.exe`

轻量增强安装器。推荐给普通 Windows 用户分发，内容与 `xPano-light-colmap-densify-ready.zip` 基本一致，但会通过安装向导完成解包、快捷方式和卸载项创建。

安装器特点：

- 默认安装到 `%LOCALAPPDATA%\Programs\xPano`，不需要管理员权限。
- 自动创建开始菜单快捷方式，可选创建桌面快捷方式。
- 内置 Microsoft Edge WebView2 Evergreen Standalone Installer；安装时会检测 WebView2，缺失时自动静默安装。
- 内置 COLMAP、ffmpeg / ffprobe、基础 Python、Metashape Python 离线 wheels、LichtFeld densification plugin 和模型缓存。
- Metashape 本体不随安装器分发，Metashape 后端仍要求用户本机已安装并授权 Metashape。

无网情况下，安装器版本可直接使用 GUI、OSV / INSV 抽帧、COLMAP 后端、点云预览，以及已安装 Metashape 时的 Metashape 后端。light 安装器不包含完整 torch / Open3D 致密化运行时；如果用户电脑没有兼容环境，致密化需要联网配置或改用 full 包。
联网配置致密化时同样需要系统中已有支持 `venv` 的 Python 3.10-3.12。

## 快速开始

解压发布包后运行：

```bat
RUN_XPANO.bat
```

调试启动：

```bat
RUN_XPANO_DEBUG.bat
```

GUI 基本流程：

1. 添加素材轨。
2. 全景素材放入全景轨道，只支持 `.osv` / `.insv`。
3. 普通视频、普通照片、航拍照片放入对应轨道。
4. 选择输出文件夹。
5. 选择后端：`Metashape` 或 `COLMAP`。
6. 设置抽帧间隔，单位是“秒/帧”，建议先用 `1.0`。
7. 可选设置帧数上限；留空表示按所选时间范围抽取全部帧。
8. 点击开始，等待输出 `images/` 与 `sparse/0/`。

## 后端说明

### Metashape 后端

这是当前最重要、最稳定的全景工作流。用户需要自行安装并授权 Agisoft Metashape Professional。

xPano 会自动寻找：

1. GUI 中指定的 Metashape 路径
2. `XPANO_METASHAPE`
3. PATH 中的 `metashape.exe`
4. 常见安装目录

Metashape Python 依赖处理方式：

- xPano 不再把 `numpy` / `cv2` 安装进 Metashape 安装目录。
- 首次运行时，xPano 会按 Metashape 自带 Python 版本创建：

```text
tools/metashape-python/cpXX/site-packages
```

- 然后通过 `PYTHONPATH` 注入给 Metashape 子进程。
- 这样可以避免 `C:\Program Files` 权限问题，也不会污染用户的 Metashape 安装。

### COLMAP 后端

发布包已内置 COLMAP，GUI 和 CLI 会优先使用：

```text
tools/colmap/bin/colmap.exe
```

用户不需要安装 COLMAP，也不需要配置 PATH。

COLMAP 后端适合不想依赖 Metashape 的场景。它会输出同样的 COLMAP 结构：

```text
images/
sparse/0/cameras.bin
sparse/0/images.bin
sparse/0/points3D.bin
```

当前内置 COLMAP 为 Windows no-CUDA 构建。GPU/CUDA 相关能力仍取决于用户本机驱动和所使用的外部环境。

## 已锁定的 Metashape 全景流程

全景 `.osv` / `.insv` 轨道必须遵守以下流程：

1. 每个采样时刻生成一个文件夹，内部包含左右两张原始鱼眼图。
2. 每个文件夹作为一个 Metashape CameraGroup。
3. 匹配和初始对齐前，CameraGroup 类型设为 `Station`。
4. 全景 sensor 类型设为 `Metashape.Sensor.Type.Fisheye`。
5. 像元尺寸设为 `0.0024 mm`，焦距设为 `2.5 mm`。
6. 初始 `b1`、`b2`、`k4` 设为 `0`。
7. 固定参数必须是大写 `["B1", "B2", "K4"]`。
8. `matchPhotos` 使用 `tiepoint_limit=0`，关闭 `filter_stationary_points`，启用 `keep_keypoints=True`。
9. `alignCameras(adaptive_fitting=True)`。
10. 对齐后把 CameraGroup 从 `Station` 改回 `Folder`。
11. `optimizeCameras(fit_b1=False, fit_b2=False, fit_k4=False)`。
12. 保存 `work/xpano.psx`。
13. 执行地面方向校正和 COLMAP / cubemap 导出。

混合素材默认使用 `backbone` 策略：

1. 先只导入并对齐全景双鱼眼轨道。
2. 释放全景 Station 到 Folder，并做保守优化。
3. 再导入普通视频帧、普通照片、航拍照片等 Frame 相机。
4. 不假设不同素材之间有时间或帧号对应关系。
5. 让 Metashape 按图像内容把新增 Frame 相机注册到已有全景骨架上。
6. 最后做轻量全局优化。

旧的一阶段混合流程仍可通过高级参数或 CLI 的 `--metashape-alignment-mode mixed` 使用。

## 为什么不先拼接 ERP

传统 360 重建流程通常是：

1. 原始双鱼眼视频先拼接成 ERP 全景图。
2. ERP 再切成多张透视图。
3. 用这些透视图做 SfM / 3DGS。

这个流程容易引入非物理形变：拼接软件为了视觉无缝可能做光流拉伸，ERP 顶底区域也有严重极区拉伸。把这些图交给摄影测量软件做 bundle adjustment，相当于让优化器拟合已经被非刚性处理过的图像，容易导致点云漂移、轨迹弯曲和接缝附近重影。

xPano 采用相反策略：

1. 对齐阶段只使用原始左右鱼眼。
2. 同一时刻左右鱼眼先设为 Metashape `Station`。
3. 初始对齐完成后释放为 `Folder`。
4. 对齐完成后才做 cubemap / undistort 导出。

这样可以减少对齐图像数量，避免 ERP / 拼接形变进入空三，并让导出的透视图继承已经优化好的相机姿态。

## 项目文件夹复用

xPano 输出目录也是 xPano 工程目录。一个有效工程通常包含：

```text
output/
  work/
    frames/
    xpano_manifest.json
    xpano.psx
  images/
  sparse/
    0/
      cameras.bin
      images.bin
      points3D.bin
  xpano_run_summary.json
```

把这个输出目录拖入 GUI 后，xPano 会进入项目页，而不是只进入点云预览页。用户可以：

- 复用已抽取帧
- 复用 manifest
- 复用 Metashape `.psx`
- 手动在 Metashape 中调整工程后重新导出 COLMAP
- 只选择部分步骤重新执行

只有当拖入的是普通 COLMAP 文件夹、且不是 xPano 工程目录时，GUI 才直接进入点云预览。

## LichtFeld 致密化

xPano 集成 LichtFeld densification plugin，用于把 Metashape 或 COLMAP 输出后的稀疏 COLMAP 点云变得更密。

full 包：

- 内置致密化 Python 运行时。
- 无网可直接运行致密化。

light 包：

- 内置插件源码和模型缓存。
- 不内置 torch / Open3D 等大型运行时。
- 会优先复用用户已有兼容环境。
- 如果无兼容环境，需要联网配置，或改用 full 包。

输出会合并到 COLMAP `sparse/0/points3D.bin`，并保留原始稀疏点备份。

## CLI 示例

单个全景视频，Metashape 后端：

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend metashape `
  --output "D:\path\to\output" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1 `
  --metashape "C:\Path\To\Metashape\metashape.exe"
```

限制前 50 帧：

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend metashape `
  --output "D:\path\to\output_50" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1 `
  --max-frames 50 `
  --metashape "C:\Path\To\Metashape\metashape.exe"
```

COLMAP 后端：

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend colmap `
  --output "D:\path\to\output_colmap" `
  --pano "D:\path\to\camera.osv" `
  --seconds-per-frame 1
```

混合普通视频：

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend metashape `
  --output "D:\path\to\mixed_output" `
  --pano "D:\path\to\camera.osv" `
  --ordinary-video "D:\path\to\phone_video.mp4" `
  --ordinary-view wide `
  --seconds-per-frame 1
```

重新导出已有 Metashape 工程：

```powershell
python scripts\run_xpano_tracks_job.py `
  --backend metashape `
  --output "D:\path\to\xpano_project" `
  --reexport-existing-project `
  --metashape "C:\Path\To\Metashape\metashape.exe"
```

## 从源码运行

开发模式启动 GUI：

```bat
RUN_XPANO_UI.bat
```

手动环境检查：

```bat
CHECK_ENV.bat -Backend colmap
CHECK_ENV.bat -Backend metashape -MetashapeExe "C:\Path\To\Metashape\metashape.exe"
CHECK_ENV.bat -Backend colmap -IncludeDensify
```

打包前准备内置 Python 和离线 wheels：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\download_offline_wheels.ps1 -Root .
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_embedded_python.ps1 -Root .
```

构建发布目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release.ps1 `
  -ReleaseName xPano-light-colmap-densify-ready `
  -Version 0.1.1-light-colmap-densify-ready `
  -SkipDensifyVenv

powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release.ps1 `
  -ReleaseName xPano-full-offline `
  -Version 0.1.1-full-offline
```

压缩为单文件 ZIP：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package_release.ps1 `
  -ReleaseName xPano-light-colmap-densify-ready `
  -NoSplit
```

构建轻量安装器：

```powershell
winget install --id JRSoftware.InnoSetup --exact

powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_light_installer.ps1 `
  -Version 0.1.1
```

安装器输出到：

```text
dist/xPano-light-Setup.exe
dist/xPano-light-Setup.SHA256SUMS.txt
```

轻量安装器使用 Inno Setup 构建。之前测试过 NSIS，但 light 包包含较大的模型和运行资源，NSIS 在大文件打包时可靠性不足，因此当前发布路径固定为 Inno Setup。

## 常见问题

### 提示找不到 `WebView2Loader.dll`

说明发布包不完整，`WebView2Loader.dll` 必须和 `xPano.exe` 在同一目录。新版打包脚本会强制复制该 DLL。

### Metashape 找不到 `cv2` 或 `numpy`

新版不再要求用户手动给 Metashape Python 安装依赖。运行任务前环境检查会创建：

```text
tools/metashape-python/cpXX/site-packages
```

如果仍失败，优先检查发布包中是否存在：

```text
tools/offline-wheels/metashape/
tools/offline-wheels/app/
```

### light 包无网不能致密化

这是预期行为。light 包包含插件和模型缓存，但不包含完整 torch / Open3D 运行时。无网致密化请使用 full 包。

### COLMAP 模式内存占用高

先降低抽帧数量或使用更大的秒/帧间隔。COLMAP 特征提取和匹配会随图片数量快速增长，尤其是高分辨率双鱼眼输入。

## 第三方组件与许可

- 原始 xPano：MIT License。
- COLMAP、ffmpeg、Agisoft Metashape、LichtFeld densification plugin、RoMa / DINO 等第三方组件遵守各自许可证。
- Metashape 本体不随 xPano 分发，用户必须自行安装并持有合法授权。
- 若发布包含 RoMa / DINO 模型缓存，请保留对应第三方 license / notice。

## 相关文档

- `docs/VERIFIED_WORKFLOW.md`：已锁定的 Metashape 工作流。
- `docs/MULTI_TRACK_BACKEND.md`：多素材轨道和后端设计。
- `docs/COLMAP_DENSIFICATION.md`：当前 COLMAP / LichtFeld 致密化工作流与已知边界。
- `docs/ARCHITECTURE_HARDENING_PHASES_0_2.md`：环境与运行架构加固前三阶段执行规范。
- `GUI_QUICKSTART.md`：新 GUI 快速启动说明。
