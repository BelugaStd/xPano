# xPano

[English](README.md)

xPano 是一套 Windows 桌面工作流，用于将全景视频、普通视频和照片处理为 COLMAP 重建、点云版本与 LichtFeld 高斯训练数据。

整个常用流程都围绕一个工程目录进行：

```text
导入素材 -> 准备帧和照片 -> 对齐与重建 -> 查看成果 -> 致密化或高斯训练
```

## 可以做什么

- 导入 DJI/Insta360 双鱼眼全景视频、普通视频、标准照片和航拍照片。
- 对视频抽帧、准备原始鱼眼/普通帧，并渐进加载照片文件夹预览。
- 使用以全景为骨架的 Metashape 流程进行对齐，再增量加入普通照片或视频。
- 导出标准 COLMAP 数据集：`images/` 与 `sparse/0/`，并在软件内查看点云。
- 重新打开 xPano 工程；在 Metashape 中手动修改 PSX 后，从 xPano 重新导出。
- 先预览 LichtFeld 致密化结果，再将其保存为独立点云版本。
- 使用内置 LichtFeld Studio 启动高斯训练，并查看进度、日志、预设和高级参数。

## 开始前

| 项目 | 要求 |
|---|---|
| 系统 | Windows 10/11 x64 |
| 核心工具 | xPano 已包含 Python 运行时、FFmpeg、COLMAP 与 WebView2 支持。基础流程不要求系统 Python、FFmpeg、COLMAP、Git、CUDA Toolkit 或管理员权限。 |
| Metashape | 推荐的全景与混合素材重建需要 Agisoft Metashape Professional。请自行安装并持有授权；若未自动检测到，请在 xPano 中选择其可执行文件。 |
| 磁盘 | 请使用空闲空间充足的本地位置。抽取帧、生成图像、点云和训练产物可能远大于原始素材。 |
| 网络 | 首次使用 LichtFeld 致密化可能需要下载大型运行时；标准安装器不包含该运行时。 |

## 快速开始

1. 打开 xPano，默认进入**素材**工作区。
2. 添加文件或照片文件夹。每个素材来源作为一条素材轨道导入。首次导入会在首个素材旁自动创建 `xPano` 工程目录，因此开始前请确认素材所在磁盘有足够空间。
3. 检查轨道设置，重点是抽帧频率、时间范围和可选 LUT。
4. 点击**开始抽帧**。全部素材就绪后，点击**下一步：对齐与重建**。
5. 选择重建后端并开始任务。
6. 在**成果**中检查点云。确认重建质量后，再继续致密化或高斯训练。

### 支持的素材

| 轨道 | 推荐输入 | 说明 |
|---|---|---|
| 全景视频 | `.osv`、`.insv` | 使用原始双鱼眼素材。配对的 `.insv` 文件必须保留在同一文件夹；xPano 使用原始鱼眼图像对齐，而不是 ERP 或手工切分的 cubemap。 |
| 普通视频 | `.mp4`、`.mov`、`.avi`、`.mkv` | 选择与实际素材相符的初始视角。 |
| 标准照片 | JPG/JPEG、PNG、TIF/TIFF、BMP | 可选择文件夹或单独图片。不同相机的照片会在元数据不同时自动分组。 |
| 航拍照片 | JPG/JPEG、PNG、TIF/TIFF、BMP | 作为单独的航拍照片轨道导入。 |

素材准备完成前，请保持源文件位于原始位置。任务进行时不要移动、改名或删除源文件夹。

### 色彩 LUT

- 可为导入的视频和照片套用自定义 `.cube` 风格 LUT。
- 对 DJI `.osv` 素材，只有在源素材确实为 D-Log M 且需要还原到 Rec.709 时，才启用内置还原 LUT。
- Insta360 `.insv` 仍需手动选择与相机和拍摄配置对应的 LUT。
- 同时启用时，xPano 先执行还原 LUT，再执行风格 LUT。

## 对齐与重建

### Metashape：推荐方案

全景工程和包含普通视频/照片的混合工程，请使用 **Metashape**。

xPano 会先对齐全景 Station，再增量加入普通视频帧、标准照片或航拍照片，使全景解作为整体重建骨架。生成的 Metashape 工程位于：

```text
work/xpano.psx
```

你可以在 Metashape 中打开 PSX 手动修正。保存 PSX 后，回到 xPano 的对齐工作区使用**从 PSX 重新导出**。如果 PSX 中有多个可用 Component，需要选择一个进行导出；默认选中相机数最多的 Component。

### COLMAP：仅全景素材

COLMAP 已随 xPano 提供，无需单独安装。当前产品中，它用于全景素材的重建。由于尚未完成必要的回归验收，xPano 会阻止 COLMAP 的混合素材流程。

## 成果、致密化与训练

### 点云与版本

成果工作区会打开重建点云，同时保留标准结果。你可以预览已保存的点云版本，并选择可用版本作为训练点云。

### LichtFeld 致密化

在成果工作区打开致密化面板；必要时先配置运行时，再对当前重建执行致密化。

致密化结果会先作为候选预览。检查后再点击**保存为版本**。保存会创建独立点云版本，不会覆盖标准重建；关闭预览也会保留候选结果，方便之后继续查看。

### 高斯训练

当重建已导出训练数据，并且已选择有效训练点云后，进入**高斯训练**。选择预设或调整参数，再开始训练。

默认会拉起 LichtFeld Studio 图形界面，xPano 同时显示进度和日志。标准预设默认 30,000 步，另有快速和高质量预设。图像分辨率、迭代次数和最大高斯数量越高，训练时间与显存占用越大。

## 工程文件与重新打开

xPano 工程是完整的工程目录，而不是单个输出文件。常见结构如下：

```text
MyProject/
  xpano_project.json          # xPano 工程状态
  work/
    xpano_manifest.json       # 已准备素材的清单
    xpano.psx                 # 使用 Metashape 时生成的工程
    jobs/                     # 可恢复的任务日志与快照
  images/                     # 导出的训练/重建图像
  sparse/0/
    cameras.bin
    images.bin
    points3D.bin
  xpano_run_summary.json      # 重建摘要
```

部分目录只会在相应阶段完成后出现。重新打开时，请使用**打开工程**，或将完整工程根目录拖入 xPano。备份、复制或移动工程时，请保持完整目录结构。

## 注意事项

- 对长视频，建议先使用短片段或更低的抽帧频率测试。更多帧只有在带来有效视角变化时才有价值，同时会增加抽帧、匹配、内存和磁盘成本。
- 重建质量依赖清晰、曝光稳定、覆盖充分且动态物体较少的素材。xPano 无法保证所有素材都能正确对齐。
- 如果对齐结果分裂为多个 Component，请先检查再导出或训练。通常选择相机数最多的主 Component；也可以在 Metashape 中手动修正 PSX 后重新导出。
- xPano 运行期间，不要手动替换 `images/`、`sparse/0/` 或 `work/` 内的文件。请使用软件内的重新导出和点云版本操作，保证工程状态一致。
- Metashape 不随 xPano 分发；你需要自行准备合法的 Metashape Professional 安装与授权。
- xPano、Metashape、COLMAP、FFmpeg、LichtFeld Studio、RoMa 等组件遵循各自的许可证和声明。

需要实现层面的参考时，请查看 [GUI_QUICKSTART.md](GUI_QUICKSTART.md)、[docs/VERIFIED_WORKFLOW.md](docs/VERIFIED_WORKFLOW.md) 与 [docs/COLMAP_DENSIFICATION.md](docs/COLMAP_DENSIFICATION.md)。
