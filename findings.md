# Findings & Decisions

## 2026-07-13 Metashape panorama NumPy incident

- User reports multiple machines fail only while aligning panorama material with `RuntimeError: Metashape Python could not load NumPy`; another machine using ordinary photos succeeds. This localizes the observed failure to the panorama/Metashape backend branch, not the app Python or generic photo-import flow.
- The current 0.2.3 release already embeds hash-locked NumPy/OpenCV wheels for supported Metashape ABIs and has a Runtime Readiness module. The investigation must therefore prove whether the alignment launcher calls it before importing Metashape, whether its state is injected into the child process, and whether old installed copies/selected executables bypass the gate.
- The reconstruction job does invoke `runtime_readiness.py ensure` and carries `sitePackages` through Rust as `XPANO_METASHAPE_SITE_PACKAGES`; the failure is not explained by a missing preflight call.
- The readiness gate currently proves imports only through `Metashape/python/python.exe -c`. The actual workload launches `metashape.exe -r scripts/metashape_pipeline.py`, which imports `export_colmap` before argument handling. Those are distinct execution modes and the readiness probe never verifies that its `PYTHONPATH`/DLL environment survives the real Metashape runner.
- `pipeline_core.metashape_process_env` currently owns the child environment transformation. It strips app-local GUI paths then prepends the provisioned site-packages path. A real runner probe must use this exact transformation, otherwise the check can still validate a different environment from the launched alignment process.
- The actual offline NumPy wheel carries its native BLAS DLL in `numpy.libs`; the OpenCV wheel carries `cv2.pyd` and `opencv_videoio_ffmpeg4100_64.dll` in `cv2`. Supplying only `PYTHONPATH` is not sufficient evidence on Windows, so the shared child environment prepends both directories to `PATH` before launching Metashape.
- Direct acceptance against the local Metashape 2.2.1 runner passed in 3.6 seconds and reported `NumPy 1.26.4` plus `OpenCV 4.10.0` from `metashape.exe -r`, not from the standalone Python interpreter.
- The non-mutating readiness status command was also changed to run the real probe. This prevents a healthy-looking UI status from masking the same runner-only import failure that would otherwise be repaired only when a job begins.

## 2026-07-13 Metashape external-site activation regression

- User evidence from Metashape build 22170 shows `metashape_runtime_probe.py` fails on `import cv2` even after the 0.2.4 runtime gate. This invalidates the prior assumption that the Metashape runner honors the injected `PYTHONPATH` in every supported build.
- The preflight subprocess captured this traceback rather than allowing it to crash xPano directly, but the offline site-packages path was not visible to the runner, so provisioning could not repair the import. The correct boundary is script-local activation before importing `cv2`, `numpy`, `align_ground_plane` or `export_colmap`.
- The repair must explicitly insert `XPANO_METASHAPE_SITE_PACKAGES` into `sys.path` and register the `numpy.libs`/`cv2` DLL directories through `os.add_dll_directory`, retaining the returned handles. This does not rely on environment processing performed by Metashape's launcher.
- Real acceptance used a freshly installed external cp39 NumPy/OpenCV site-packages directory, with `PYTHONPATH` removed. `metashape.exe -r metashape_runtime_probe.py` loaded both modules from that external directory, and `metashape.exe -r metashape_pipeline.py --help` reached its argument parser after importing `export_colmap`. This demonstrates the actual user failure path is repaired without modifying Metashape's installation.
- The local runner is Metashape 2.2.1 build 20221. The repair is intentionally build-agnostic: the activated script directly controls `sys.path` and the Windows native DLL lookup directories instead of relying on a launcher-specific environment inheritance behavior.
- The final 0.2.5 standard installer is `dist/xPano-0.2.5-windows-x64-setup.exe` (728,585,253 bytes, SHA-256 `6abbdcf91e1eb343abc3d6f943f6fe56c9ccfbb787c7cd1a82a790e37d9e1f20`). It contains 2,137 manifest resources including the runtime activation/probe scripts and cp39 NumPy plus abi3 OpenCV offline wheels. Installed resource verification found no missing or modified file after excluding the deliberate post-install deletion of the WebView2 bootstrap installer.
- Installed acceptance executed the packaged probe and actual alignment script from an unrelated working directory with `PYTHONPATH` removed. Both loaded NumPy/OpenCV from the external runtime; the installed Runtime Readiness command reported every bundled tool ready. Under a system-only PATH with Python/CUDA environment values cleared, the packaged GUI stayed alive, created a window, and reported responsive after 12 seconds.

## 2026-07-13 Metashape build 22170 custom-environment stripping

- The second user traceback is from the 0.2.5 probe layout: `import cv2` is now line 12, proving the new script shipped and executed but `activate_metashape_runtime()` did not obtain a usable runtime path.
- 0.2.5 removed reliance on `PYTHONPATH` but still reads `XPANO_METASHAPE_SITE_PACKAGES` from the child environment. The local build 20221 preserved that variable, while the user's build 22170 evidently does not. The previous acceptance therefore tested the wrong compatibility boundary.
- The fix must carry the verified runtime path in the `metashape.exe -r` argument vector (or another file-backed channel controlled by xPano), not in any environment variable. The same transport must be used by readiness probing and the production alignment/export command.
- The actual production chain has two process boundaries: Rust launches xPano's bundled Python with an explicit environment block, then Python launches the external Metashape runner. Only the second, externally owned boundary is observed to sanitize variables. The smallest complete fix is therefore to convert the verified environment value to `--xpano-site-packages <path>` before every Metashape launch while retaining environment injection only as backward-compatible DLL-path assistance.
- `reexport_colmap_from_project.py` was an uncovered third Metashape entrypoint: it imported `export_colmap` before any runtime activation. It now follows the same explicit pre-import activation contract as the readiness probe and main pipeline.
- With both custom environment variables removed, the real Metashape 2.2.1 runner accepted the explicit path and loaded external NumPy/OpenCV for the probe; the main alignment and PSX re-export scripts both reached their argument parsers. This directly validates the new transport channel rather than the build-20221 environment behavior that invalidated 0.2.5 acceptance.

## 2026-07-11 点云预览性能根因
- `read_colmap_points` 是同步 `#[tauri::command]`，直接执行文件 I/O、逐点解析、相机读取和 serde 序列化；调用期间会占据 Tauri 命令处理线程，解释了“整个软件无法操作”。
- 400k 点需要传输约 240 万个浮点数（坐标和颜色）。当前 JSON 路径会把 9.6MB 原始 f32 扩大为数十 MB 文本，并在 Rust 序列化、WebView JSON 解析和 `Float32Array` 构造中产生多次完整复制。
- 前端场景初始化至少分配 positions/x/y/z、增强颜色、主题颜色等多个全量数组，并对 x/y/z 各排序一次、对点云多轮扫描；这些全部在单个 React effect 中同步执行，构成长任务并阻止输入和重绘。
- 优化边界：不采样、不减少点数、不降低坐标精度、不关闭颜色增强/相机/抗锯齿策略；只改变执行线程、传输格式、内存复制次数和任务切片方式。

## 2026-07-11 单行标题栏与底部工作流控制坞
- 三个固定顺序工作区适合使用底部导航；为避免与动态任务状态竞争，底栏采用“弹性工作区导航 + 固定上限任务区”，而不是四块等权按钮。
- 1024px 下环境状态自动收为盾牌图标、任务耗时隐藏、导航仍保留完整文字；1366px 运行态进度条约 177px；1920px 下任务区仍不超过 440px，因此额外宽度优先分配给工作区导航和主内容。
- 空闲状态保留低透明度短轨道以稳定布局；运行态显示消息、百分比、ETA/耗时、日志和停止按钮；日志抽屉继续从控制坞上方展开。

## 2026-07-11 导出执行图进度闪烁
- 右侧总进度正常是因为 `sanitizeProgress` 对 `percent` 做了单调保护；但它用每条新事件覆盖整个 progress。同阶段的纯 `PROGRESS:98` 事件不带 `stage/current/total`，会清空刚收到的 `export.images` 和计数。
- `ExecutionGraph` 只用 `progress.stage` 查找当前节点；stage 缺失或不在计划中时 `currentIndex` 为 `-1`，所有节点都会渲染为“等待”。
- Metashape 子脚本发出计划内 `export.images`，而 `pipeline_core.py` 的逐相机进度发出计划外 `export.cameras`，持久事件因此在两个 id 间切换并反复完成/重启节点。
- 最小完整修复必须覆盖两端：正常导出和重导出均统一为 `export.images`；前端对同阶段/同节点的部分事件保留 scope 与计数，但显式切换节点时清理旧计数。
- 代码质量复审结论为通过：没有新增依赖、I/O、异步任务或渲染循环；进度合并仍是常数时间，仅从 hook 抽成可独立测试的纯函数。显式 phase/stage/track/total 变化都会切断继承，避免把旧节点计数泄漏到新节点。

## 2026-07-10 阶段 3/4 与安装器新目标审计
- 2026-07-11 继续阶段 3：规划文件的 Phase 11 已是 `in_progress`，但 `Current Phase` 仍停在 Phase 10，现已同步为 Phase 11。下一纵切以规格中的 `get_job_snapshot`、`cancel_job`、每秒 heartbeat、durable log/progress 与重开工程恢复为验收面；不能仅依赖当前进程内 `PipelineState.pid` 和前端事件缓存。
- 规格与当前实现的具体差距：`contracts.rs` 已定义 `JobSnapshot`/`JobEvent`，`XpanoProjectV2.jobs` 也存在，但启动媒体/重建任务并未创建或更新 jobs，仓库没有 `get_job_snapshot`/按 jobId 的 `cancel_job`；当前 heartbeat 只通过 Tauri 事件发往在线页面，不写 `work/jobs/<jobId>/events.ndjson`，重开后无法恢复阶段、序列、日志或最后进度。
- `run_preflight_environment_check` 当前使用同步 `Command::output()`，在真正启动 job 前阻塞 Tauri command，期间不可取消且没有 PID/状态；它只发通用 `pipeline:progress`，不属于统一 JobEvent 协议。这是阶段 3 下一纵切的首要 seam。
- 阶段 3 前端仍通过全局 `usePipeline()` 的 `pipeline:progress/complete/error` 管理 running、日志和自动跳转；`ReconstructionWorkspace` 挂载时不会调用 `get_job_snapshot`，也没有 jobId。当前取消按钮只调用全局 `cancel_pipeline`，无法验证请求是否对应当前工程/任务。后端已经有足够的 JobSnapshot/JobEvent 类型，可在不复制流程判断的前提下加深为持久化 job 模块。
- 取消路径还有一个直接正确性问题：`PipelineState::cancel()` 立即 `take()` 掉 pid/job，子进程 watcher 随后判断 `is_current_pipeline(pid) == false`，因此跳过 cancelled 分支及工程失败/中断结算。UI 会先显示“已取消”，但磁盘上的 reconstruction 可能继续保持 running。这必须在新增按 jobId 取消前先以回归测试修正为 `cancelling → watcher observes exit → cancelled/interrupted`。
- Phase 11 durable job 第一纵切已落地：重建启动创建 `work/jobs/<jobId>/{snapshot.json,events.ndjson,job.log}`，所有事件在进程内全局锁下严格递增；pipeline 的结构化进度、普通日志和每秒 heartbeat 会持久化并发 `job:event`，终态同步回 `xpano_project.json.jobs`。`get_job_snapshot/read_job_events/get_job_recovery/cancel_job/recover_job_state` 已注册。
- 重开工程时前端先订阅事件，再读取 durable recovery；若后端无活动进程而快照仍 queued/running/cancelling，恢复命令将 job 与 reconstruction 标记 interrupted。取消 UI 保持 running/cancelling，直到 watcher 观察到进程树退出；不再提前显示 stopped。
- 仍需补齐：Metashape 脚本目前主要发 overall percent，没有完整映射到 ExecutionPlan 的稳定 stageId；COLMAP/pipeline_core 已覆盖多数 stageId。同步 PowerShell preflight 仍在 job 创建之前，是阶段 3 当前最大未完成项。
- 复核脚本后修正上述判断：`metashape_pipeline.py` 的 backbone/mixed 主路径已经发出大部分稳定 stageId，缺口主要是 `export.images`/`export.colmap` 显式节点和 skip 事件，而非整个 Metashape 流程。PowerShell preflight 现已注册到同一 PipelineState/jobId，可每秒 heartbeat 且按 jobId 取消；真实 `-CheckOnly` 探针确认 App Python、FFmpeg/ffprobe、Metashape Python 全部就绪且未下载任何包。
- 当前 `start_reconstruction_job` 仍是同步 Tauri command，虽然前端 invoke 是 Promise，长 preflight 仍可能占用命令执行线程。下一步改为 async command + `spawn_blocking`，保持窗口事件循环和 cancel command 可并行响应。
- `start_reconstruction_job` 已改为 async Tauri command + `spawn_blocking`；PowerShell preflight 与 Python supervisor 均不占用 UI 事件循环。ExecutionPlan 中有 skipReason 的节点会在 job 启动时写 `stage.skipped`；Metashape 导出补齐 `export.images` 与 `export.colmap` 稳定 stageId。
- Playwright/Edge 运行态 UI 证据：1366x768 与 1920x1080 均渲染左参数/中流程/右监控三栏，16 个后端 plan 节点完整可达，“一键启动对齐”固定在右栏底部；1024x768 自动降级为左+中布局并通过底部监控入口访问，页面无横向溢出。三种尺寸控制台均 0 error/0 warning。

## 2026-07-11 阶段 4 实现审计
- Phase 12 最终运行时验收通过：拆分后的 `DensificationPanel` 在本地 phase4 预览可打开、展开高级参数、滚动、关闭并重开；1028×908 窄视口与训练点云面板不重叠，控制台 0 error/0 warning。
- 全量 Python 回归暴露环境探针会通过插件 `--help` 导入 NumPy/PyCOLMAP/RoMa/Torch/Open3D，冷启动超过 30 秒；这会让安装后首次环境检查看似卡死。runner 现用 AST 仅执行插件的 `build_argparser` 函数，帮助内容仍取自插件权威定义，但完全绕过重依赖导入。
- 轻量 runner 帮助在真实 `.venv-densify` + 真实插件上约 0.1 秒返回；新增隔离测试确保即使插件顶层主动抛错，`--help` 仍可用。真正运行路径仍按原方式加载完整插件，不改变致密化行为。

## 2026-07-11 Phase 14 安装器与自举设计审计
- 栈版本已从工程文件确认：Tauri/Rust 2.11.3、Tauri CLI 2.11.3、React 19.2.7、Vite 8.1.0、内置 Python 3.12.3；发布目标继续限定 Windows x64。
- 当前存在两套漂移的安装链：Tauri `bundle.nsis` 与 `build_light_installer.ps1` 的 Inno Setup。后者默认调用 `build_release.ps1 -SkipTauriBuild`，会把旧 release EXE 打进新安装器；截图问题正说明该风险已实际发生。正式发布必须只保留一个权威入口，并默认强制从当前源码构建。
- 当前 `tauri.conf.json` 的 `../binaries/` 从 `xpano-ui/src-tauri` 解析到不存在的 `xpano-ui/binaries`，真实根目录应是 `../../binaries/`；现有手工 portable staging 掩盖了该 Tauri bundle 资源遗漏。
- 正式安装器选择 Tauri NSIS：它与应用版本、EXE、resources、WebView2 和卸载 hook 同一配置源，删除 Inno 的第二套安装语义。安装模式采用 `currentUser`，不要求管理员；WebView2 使用仓库已有 Evergreen Offline Installer，不在构建或安装时额外下载约 127–194MB 文件。
- Tauri 官方文档确认 NSIS/WiX 是 Windows bundler，WebView2 `offlineInstaller` 会嵌入安装器并推荐离线环境；官方配置支持 `installerHooks`、`installMode`、`resources`。来源：https://v2.tauri.app/distribute/windows-installer/ 与 https://v2.tauri.app/reference/config/#nsisconfig 。
- 基础随包边界：内置应用 Python（约 0.19 GiB）、COLMAP（约 0.409 GiB）、FFmpeg/ffprobe、运行所需 Python 脚本、7MB LichtFeld 插件源码、依赖/运行时 manifest、WebView2 offline installer。明确排除 `.venv-densify` 7.636 GiB 与 `tools/torch-cache` 1.034 GiB。
- 当前 FFmpeg 来自 WinGet 符号链接，实际为 8.0.1 full build：ffmpeg 211,091,968 bytes、ffprobe 210,895,360 bytes；发布 staging 必须解析链接后复制真实文件并记录 SHA-256，不能把 0-byte link 本身打包。
- Python 官方说明 embeddable distribution 几乎与用户系统、环境变量、注册表和已安装包隔离，适合随应用携带；但它不是可依赖的 venv/pip 主机，因此应用 Python只运行基础管线，致密化环境另建于用户缓存。来源：https://docs.python.org/3/using/windows.html#the-embeddable-package 。
- pip 官方安全安装建议 `--require-hashes` 与 `--only-binary :all:`；按需致密化自举将使用锁定 wheel/URL/SHA-256 manifest，不允许源码构建或未校验包。来源：https://pip.pypa.io/en/stable/topics/secure-installs/ 。
- PyTorch 官方安装器按 Windows + pip + CPU/CUDA 变体给出独立官方 index；自举 manifest 需要把 CPU/CUDA wheel 组显式锁定，不能只把清华镜像设为任意 fallback。来源：https://pytorch.org/get-started/locally/ 。
- `ResultsWorkspace` 目前只是把 reconstruction.colmapPath 传给 1800 行 `PointCloudViewer`；查看器同时承担 Three.js viewport、轴写回、致密化环境/任务、候选预览、应用/丢弃和提示状态，locality 很差。
- 现有 `apply_lfs_densify_result` 直接备份并覆盖兼容 `points3D.bin`，`discard_lfs_densify_result` 删除候选；这与规格“standard 永久保留、每次 densify 注册新版本、预览不改变训练输入、切换可逆”正面冲突。
- 当前工程数据已有 transform/activeVariantId/variants，但 PointCloudVariant 缺少 checksum、transformRevision、status；重建成功也没有把标准 `points3D.bin` 物化到 `work/geometry/variants/standard/` 或保存不可变 `base_images.bin`。阶段 4 首个纵切应先建立独立 `geometry.rs` 的版本注册/物化事务，再改 UI；否则继续在 Viewer 内加状态只会扩大浅接口。
- 轴按钮仍调用旧 `apply_colmap_axis_flip`，虽然 Python 已把单轴镜像改成 180° 合法旋转，但接口仍只能三个预设、直接写盘、无预览/gizmo/累计 worldFromCanonical，也没有所有点云版本同步事务。
- 阶段 3 第一切片已落地：`build_execution_plan` 将后端生成的 active plan 原子写入 `work/plans/reconstruction_active.json`；启动事务验证 planId、projectId、alignment input revision、backend 和 alignmentMode 后才进入 running。
- 前端启动时先持久化完整配置，再用返回的新 project revision 重建 plan，最后调用专用 `start_reconstruction_job`；通用 `start_pipeline` 不再承担工程化重建的权威启动。
- `PipelineState` 已移除“启动前自动 cancel 旧任务”，活动任务返回 `ALREADY_RUNNING` 且保留原 PID；这满足阶段 3/环境状态机的关键不变量，但同步预检、runId 和可取消 preflight 仍待后续切片。
- 新测试覆盖 plan 注册启动、alignment revision 变化拒绝、flat-only/mixed 实际 stage graph、第二次启动保护和前端命令路由。
- COLMAP 官方仓库 `doc/format.rst` 确认 image pose 是从 world 到 camera 的 Hamilton quaternion + translation，ID 是无序且不连续的标识；阶段 4 校验必须比较 ID 集合而不是只比较计数。
- 官方来源：https://raw.githubusercontent.com/colmap/colmap/main/doc/format.rst；Tauri 来源：https://v2.tauri.app/develop/calling-rust/、https://v2.tauri.app/distribute/windows-installer/、https://v2.tauri.app/reference/config/#nsisconfig 。
- `build_light_installer.ps1` 默认调用 `build_release.ps1 -SkipTauriBuild -SkipDensifyVenv`；这意味着“构建安装器”并不构建当前源码，可能把旧 EXE 打进新安装器，必须改为默认强制新构建，仅允许显式开发调试跳过且做源码/二进制一致性校验。
- 当前环境配置脚本只有 `CheckOnly`，没有设计文档要求的 `EmitEvents`、结构化错误码、可测试函数入口和假源测试；安装/预检无法被 UI 可靠观察、取消或模拟。
- 当前 Inno light installer 是 per-user/non-admin，包含 WebView2 离线安装探测，方向合理；但发布链和 Tauri 自带 NSIS 并存，需要选择一个权威安装器，避免双配置漂移。
- Tauri 2.11.3 官方 Calling Rust、Windows Installer 和 NSIS 配置文档均可访问，后续实现以这些版本化官方页面为准。
- COLMAP 官方文档站在本机首次请求连接关闭；将改取 COLMAP 官方 GitHub 仓库原始 format 文档，不使用博客或二手资料。
- 当前 `build_release.ps1` 默认复制 `.venv-densify` 成可移植运行时，除非显式 `-SkipDensifyVenv`；这与新目标“致密化 CUDA/torch 等不随包发布”相反，必须把轻量自举模式变成唯一正式发布路径，而不是易漏开的开关。
- 发布脚本会复制整个 scripts/docs/plugin/torch-cache，且允许 `-SkipTauriBuild`；需要改为显式 allowlist + 新构建产物哈希/时间戳验证，防止旧 EXE 和开发资源混入。
- 仓库同时存在 `package-lock.json` 与 `pnpm-lock.yaml`，发布脚本固定 pnpm；需选定唯一权威锁文件和包管理器并在干净构建验证，不能让两套依赖解析漂移。
- 安装器不应把 7.6 GiB `.venv-densify` 或 torch cache 打包；应随包提供小型 runtime bootstrap manifest、plugin 源码/模型元数据和下载器，实际 wheel 由首次使用时按 GPU/ABI 选择。
- 系统 PATH 有 WinGet FFmpeg/ffprobe，但仓库 `binaries/`/`tools/` 未找到 ffmpeg.exe；当前源码测试成功依赖本机 PATH，现有 bundle 在干净机器上不能保证抽帧可用。
- `.venv-densify` 约 7.636 GiB，确认不应随安装包发布；其中 torch/open3d 可用，但 cv2/roma 探针缺失，需要核对插件真实 requirements 和当前 resolver 是否误选不完整环境。
- 当前无 `makensis`，Tauri CLI 可能自带/下载 NSIS 工具链，也可能导致离线发布机失败；发布脚本必须明确构建前置和缓存策略。
- `tool_resolver` 支持 bundled→环境变量→PATH→硬编码回退，但没有版本/架构/哈希验证；同名错误二进制可能被接受，安装器自举需要升级为“解析 + 探针”而非仅 exists。
- 当前测试树没有 `xpano_project.json` 或 COLMAP bin 产物，真实验收必须从源素材创建全新隔离工程，不能依赖恢复旧输出。
- 当前机器有 `E:\FastProgram\Metashape\metashape.exe`、`tools\colmap\bin\colmap.exe`、`tools\lichtfeld-densification-plugin\densify.py`、`.venv-densify` 和 RTX 4060 8GB；D 盘约 255 GiB 可用，满足受控真实测试。
- 应用内置 Python 3.12 已有 numpy/cv2/Pillow/torch，但没有 open3d；必须单独检查 `.venv-densify`，且不得因为缺模块自动启动真实大包下载。
- 预期的 `binaries/ffmpeg/bin` 路径不存在，现有 FFmpeg 实际位置需按 `tool_resolver` 当前规则重新定位；这是安装资源清单的重点风险。
- 工程 schema 已预留 `worldFromCanonical`、active variant 和 variants，但 variant 缺少规格要求的校验和、transform revision、状态；重建完成也尚未把标准点云/基准 images 物化到 `work/geometry` 并更新 point count。
- 当前 `postprocess_colmap_axis.py` 对单轴坐标取负、只更新相机中心对应 tvec，却不更新 qvec；这是 det=-1 的镜像且不满足规格的 `R'=R*G^T`，会破坏投影关系，必须移除写盘入口或替换为严格旋转事务。
- 当前轴向写盘直接修改 `images.bin/points3D.bin`，仅做一次备份，没有 tmp+校验+原子替换、ID/记录数检查或投影误差测试；不满足阶段 4 原子性。
- 当前 `apply_lfs_densify_result` 复制候选覆盖 `points3D.bin` 后删除 dense bin/ply；必须替换为 canonical 版本注册和活动版本原子物化。
- 阶段 4 环境、运行、持久化、预览和应用仍全部位于 `lib.rs`/`PointCloudViewer.tsx`；工程化命令没有 projectRoot/expectedGeometryRevision，viewer-only 与工程模式也未明确分流。
- 先前真实工程 `D:\3DRegistration\test\xPano` 在本轮审计时已不存在，不能复用旧验收状态；需要重新搜索当前工程或创建隔离的新验收工程。
- 阶段 3 后端 plan 测试覆盖不足：当前只有“全景且平面分支跳过”、COLMAP 混合禁用和无选择项拒绝，没有仅平面、全景+平面骨架、Metashape mixed 的完整节点/依赖回归。
- Python 的 Metashape/COLMAP stageId 基本覆盖计划节点，heartbeat 由 Rust 每秒复制最近事件；但 plan 与进程启动没有绑定，真实启动前不会验证 planId、plan backend、配置或锁定的输入 revision。
- 当前 `PipelineState::start` 会先无条件 `cancel()` 旧任务，直接违反规格“第二次启动返回 ALREADY_RUNNING 且原任务不变”；这也是阶段 3 的任务可靠性缺口，不只是安装器问题。
- `start_pipeline` 仍同步执行环境预检后再取得 pipeline 锁，现有 `ARCHITECTURE_HARDENING_PHASES_0_2.md` 所述异步、流式、可取消预检尚未落地；阶段 3 长任务的启动/取消/恢复不能在此基础上宣称完成。
- Metashape 脚本对自动地平校正异常仅打印 WARN 后继续导出；规格把对齐/几何高影响操作定义为无安全 fallback 时 fail fast，需要区分“自动建议失败可继续”与“产物几何已被不完整修改”的边界。
- 阶段 3 存在关键架构断点：前端虽然请求 `build_execution_plan`，启动时却仍调用通用 `useJob.start`/`start_pipeline`，没有使用规格中的 `start_reconstruction_job(planId, expectedRevision)`；因此 planId 失效、锁定输入 revision 和后端权威启动契约未闭环。
- 2026-07-10 现场抽帧完成后提交失败并非解码问题：截图显示 138/138 索引与 manifest 均完成，最终报 `project revision changed from 2 to 4`。成功进程的提交错误会触发前端 `pipeline:error` 监听器再次调用 `fail_media_job`，删除 `work/media_job.json`；随后旧格式 result（无 `inputMediaRevision`）只能进入 legacy 恢复分支。该分支错误要求 `revisions.media == inputRevision`，但总 revision 会被工作区导航推进，因此正常工程也无法恢复。
- 修复后的任务结算所有权保持在 Rust 后端：进程退出时后端负责成功提交或失败落盘，前端事件监听只重新读取持久化状态。无 marker 的历史 result 只在目标轨道未被重新使用、产物完整且修订计数满足单调边界时恢复；真正推进过 media revision 的旧结果继续被拒绝。
- `ExecutionGraph` 已支持 counted/indeterminate、stageId、heartbeat 展示，COLMAP 混合素材也在 UI 禁用；但必须核实真实事件 stageId 是否覆盖四类流程、heartbeat 是否每秒、失败是否持久化到具体节点。
- 规格中的 job 快照/`jobs.rs` 未实现为独立权威模块；当前工程有 `jobs` 字段，但页面恢复主要依赖全局 pipeline 事件和 reconstruction result 同步，尚不能证明中断/重开恢复日志与节点状态。
- 结果工作区目前只是从工程取 `colmapPath` 后把路径交给旧 `ViewerPage/PointCloudViewer`；没有项目化 point variant、geometry revision 或后处理命令入口。
- 阶段 3 验收不是“能启动对齐”即可：四种输入组合必须生成正确 ExecutionPlan，长节点每秒 heartbeat，无真实计数节点必须 indeterminate，失败需定位节点，COLMAP 混合在回归通过前必须禁用。
- 阶段 4 的权威几何模型是不可变 canonical 基准 + `worldFromCanonical`；应用旋转必须同时更新 images 外参和所有点云版本，并通过记录数、ID、有限值、投影不变量和故障注入原子性测试。
- 点云版本必须永久保留 `standard` 并允许多个 `densified_<id>`；预览与“设为训练点云”分离，外部兼容入口仅原子物化当前版本，不能把候选合并后删除。
- `docs/COLMAP_DENSIFICATION.md` 仍描述“应用后合并到标准点并删除候选”的旧流程，与 UI 规格阶段 4 冲突；实现阶段必须同步更新该文档，不能继续把它当最终契约。
- 规格建议的后端 `jobs.rs`、`geometry.rs` 和前端 `ThreeViewport/LevelingGizmo/PointCloudVariants/DensifyPanel` 尚未出现；当前关键职责仍集中在 `lib.rs` 与约 1800 行 `PointCloudViewer.tsx`。
- 当前 Tauri 配置把整个 `binaries/`、整个 `scripts/` 和 requirements 直接打入资源，目标为 `all`；需要审计是否包含开发垃圾、测试脚本、旧运行时和不应发布的大依赖。
- `tauri.conf.json` 的 `beforeBuildCommand` 使用 `pnpm build`，但当前验证和项目脚本主要使用 npm；必须确认锁文件和发布机包管理器，否则干净机器构建会直接失败。
- 权威范围来自 `docs/UI_WORKSPACE_REDESIGN_SPEC.md`：阶段 3 是完整对齐工作区，阶段 4 是成果查看、几何后处理、致密化版本和训练点云选择；旧 `task_plan.md` 的同名阶段只对应早期导入修复，不能证明规格完成。
- 当前阶段 4 明确存在反例：`apply_lfs_densify_result` 仍复制致密点到 `points3D.bin` 并删除候选文件，与“永久 standard + 多 densified 版本 + 可逆训练点云”契约冲突。
- 当前 `PointCloudViewer.tsx` 仍同时承担 Three.js、点云读取、几何校正、致密化、日志和结果应用，规格要求的 viewport/geometry/densification/version 边界尚未完成。
- `D:\3DRegistration\test` 共有 139 个文件、约 3.887 GiB；核心 OSV 为约 3.18 GiB，照片目录约 138 张，适合真实混合素材验收，但必须为每次运行固定输出目录和磁盘预算。
- 已有 `docs/ARCHITECTURE_HARDENING_PHASES_0_2.md` 明确指出当前 release 仍可能通过 `-SkipTauriBuild` 复用旧 EXE，且安装器/full-light/干净机器验收尚未完成；新目标必须先验证该文档所述 Phase 0-2 当前状态，再进入发布实现。
- 大依赖不得真实下载；安装器验收将使用假 pip、假镜像、本地小文件、哈希与缓存模拟，真实致密化只复用机器上已存在的环境。

## 2026-07-10 硬解与照片渐进预览
- 用户现场证明抽帧和照片索引均成功，最终失败仅发生在 Rust 结果提交：任务以总 revision 2 启动，工作区等无害写入把总 revision 推到 4，旧提交逻辑因此误判冲突。
- 正确并发边界是 `revisions.media` 与任务目标轨道，而不是工程总 revision；素材运行期间所有正式素材编辑命令已由 `ensure_project_writable` 锁定。
- 真实工程 `D:\3DRegistration\test\xPano` 仍保留完整 result/manifest：两个结果轨道分别 167/138 项，工程 media revision 与旧 inputRevision 均为 2；旧错误监听仅把轨道标成 failed 并删除 marker，没有删除结果。
- 新任务同时在后端 marker 和 Python result 中记录 `inputMediaRevision`；旧无 marker 结果只在目标轨道 failed/running/interrupted、items 为空且 media revision 未变化时恢复，避免覆盖后续用户编辑。
- 正式抽帧当前由 `scripts/xpano_extract.py` 构造 FFmpeg 命令，没有 `-hwaccel`；D3D11VA 只存在于预览/缩略图路径。
- 同一段 30.77 秒双路 3840×3840 Main10 HEVC 基准：软件 51.49s、D3D11VA 20.06s、CUDA 15.02s，CUDA 抽样 JPEG 与软件输出哈希一致。
- 照片预览当前后端 `scan_photo_paths` 只保留有界样本，前端 `PhotoFolderPreview` 只能显示该样本；需要同时解除后端路径上限和前端一次性渲染。
- 交互沿用现有网格和设计 token：触底追加批次，单图由 IntersectionObserver 在进入视口时设置资源地址，已加载元素保持挂载。
- 实际限制来自两层：Rust `scan_photo_paths(sample_limit)` 只保留前 8/24 条路径，React `PhotoFolderPreview` 又按 `count=12` 或导入弹窗 `count=8` 截断；仅修改 `loading="lazy"` 不能让其余照片可达。
- `analyze_import_paths` 已经遍历全目录统计数量，因此在同一次遍历中保留完整路径不会增加目录 I/O；主要新增成本是路径字符串内存，图片网络/解码仍由视口观察器控制。
- 正式抽帧的双路和单路命令都集中在 `xpano_extract.py`，适合抽出统一命令候选与回退执行器，避免三处分别拼接硬解参数。
- 照片预览位于已有 `overflow-y-auto` 的导入详情栏和轨道编辑栏中，使用 root=null 的 IntersectionObserver 会同时受窗口与祖先滚动裁剪约束，无需传递滚动容器 ref。
- 前端应移除 `count` prop：导入分析得到全量路径时直接复用；只有缺少 initialPaths 的轨道恢复场景才调用 `preview_photo_folder`，避免第二次扫描。
- 硬解参数属于 FFmpeg 输入选项；双文件 INSV 必须在每个 `-i` 前分别插入 `-hwaccel`，单文件双流 OSV 只需插入一次。
- 当前可用真实 OSV 同样是双路 3840×3840 Main10 HEVC；新代码 30.77 秒段完成 31 对/62 张 JPEG，15.154 秒，日志明确选中 CUDA。
- 新代码对 3 秒片段的 CUDA 与软件输出生成 6 张 JPEG，SHA-256 文件哈希逐一完全一致。
- 回退只应处理硬解初始化/执行失败；缺文件、权限、磁盘不足和明确输入损坏必须立即传播，不能把同一业务错误重复执行三遍。

## 2026-07-10 成果工作区续作
- 现有任务阶段 1-7 只闭环了素材准备与对齐就绪，没有实现重构规格中的阶段 4“成果与后处理”。
- 本次必须同时检查对齐输出持久化、工程 revision/artifact 登记、完成后路由跳转和查看器加载；不能只在空结果页上补一个表面占位。
- 规格明确要求对齐成功后自动进入 `/project/results`，结果页主体从工程状态加载点云；当前源码虽然已有 `ResultsWorkspace.tsx`，但仍直接复用旧 `ViewerPage/PointCloudViewer`。
- 规格阶段 4 的完整 gizmo、原子坐标变换与多点云版本仍未实现；本轮先完成用户当前可见的最小纵向闭环：有效对齐产物被登记并可在成果页加载，随后再评估是否需要扩大到全部后处理能力。
- `ResultsWorkspace` 只在 `project.reconstruction.colmapPath` 或 viewer-only 路径存在时挂载查看器；Metashape 对齐即使成功，只要工程状态未登记 `colmapPath`，页面必然显示空态。
- `ProjectProvider` 当前只对 `jobKind === 'media'` 的完成/失败事件执行工程同步；没有 reconstruction 完成后的状态刷新、成果登记或自动导航责任。
- 真实工程 `D:/3DRegistration/test/xPano` 已生成 `sparse/0/{cameras,images,points3D}.bin`、`images/`、`work/xpano.psx` 和对齐摘要，但 `xpano_project.json` 仍为 `reconstruction.status=stale`、`revisions.alignment=0`、`inputRevision=0`、`projectPath=null`、`colmapPath=null`、`activeWorkspace=media`。
- 根因位于 reconstruction 子进程成功退出后的提交边界：`pipeline.rs` 仅为 media job 调用 settlement，reconstruction job 直接发完成事件；因此算法产物存在但工程权威状态永远未更新，结果页无法推导数据路径。
- 重建失败或取消必须保留上一次有效 `projectPath/colmapPath`；生命周期测试最初要求清空路径与规格“失败保留旧结果”冲突，已修正测试而非实现。
- 旧版本遗留成果只在 `xpano_run_summary.json.manifest` 与当前 `alignmentManifestPath` 匹配时允许恢复，避免把旧点云错误登记到新的素材选择 revision。
- 当前 viewer 的 `find_bin` 会从传入工程根目录继续查找 `sparse/0`，因此将现有稳定输出登记为项目相对路径 `.` 可直接加载 38,626 点模型，无需搬迁大文件。
- 最终提交校验读取 COLMAP `cameras.bin/images.bin/points3D.bin` 的 8 字节记录数头；空文件、截断文件或零点模型不会被登记为成功成果。
- 本轮完成的是 docs 阶段 4 的必要入口闭环；完整的旋转 gizmo、canonical 几何基准、原子外参变换和多致密化版本仍是后续阶段，不应宣称整个阶段 4 已完成。

## Requirements
- 软件启动默认显示“导入素材”区域，而不是“对齐”。
- 导入照片文件夹后必须及时出现可用预览。
- 导入任意素材后“开始抽帧”不能再因 stdout/GBK 异常以退出码 120 结束，且能进入下一阶段。
- 大量照片和长视频导入时减少 UI 卡顿、CPU/内存峰值和无界工作量。
- 完成架构审查、方案设计、实现、自动化验证与关键流程验收。
- 修复导入确认按钮对已有相邻工程无响应的问题，并让错误/忙碌状态在弹窗内可见。
- 素材准备完成后，对齐页必须立即识别素材已就位并允许启动。
- 素材页全部就绪后，右下角必须提供明确的下一步按钮进入对齐与重建。

## Research Findings
- 2026-07-10 workflow screenshot confirms the photo preview is already visible (8 of 138), the import action is enabled, and the modal covers page-level notifications. The apparent no-op therefore occurs after confirmation, not during preview generation or button hit-testing.
- The real `D:\\3DRegistration\\test\\photo\\xPano\\xpano_project.json` contains one failed panoramic-video track and no items. Reusing this project is safe, but alignment must report that exact failed track instead of the generic "media not ready" message.
- The current media footer renders only one permanently disabled "prepared" button after work completes. There is no navigation affordance even when an alignment manifest and selected items are available.
- 工作树已存在大量已修改和未跟踪文件，集中在 Python pipeline、Tauri 后端及 React 新架构目录；必须基于现状增量工作，不能重置或覆盖。
- 线程已有与本次请求一致的 active goal；首次 create_goal 失败不是项目故障。
- 未发现仓库内 AGENTS.md 文件；本轮遵循用户消息中提供的工作合同。
- 前端同时存在旧的 `components/pipeline/PipelinePage.tsx` 与新的 `app/`、`features/media/`、`features/reconstruction/` 模块，当前工作树明显处于工作区架构迁移中；后续必须先确认真实入口，避免修复旧页面。
- Tauri 后端已有独立 `media.rs`、`project.rs`、`reconstruction.rs`，而旧 `pipeline.rs` 仍负责 Python 子进程和 stdout/stderr 读取；故障很可能跨越新前端状态层与旧任务执行层。
- `tests/test_prepare_project.py` 已包含“首张缩略图应在扫描第二张照片元数据前出现”、照片预览产物和排除工程生成物等测试，说明当前未提交改动已尝试解决渐进预览/性能问题，需要验证这些测试和实际 IPC 消费端是否闭环。
- `pipeline.rs` 以 piped stdout/stderr 启动 Python，并在独立线程读取；`run_xpano_tracks_job.py` 直接操作 `sys.stdout/sys.stderr`，是退出码 120/GBK 关闭异常的重点边界。
- `xpano-ui` 没有前端测试脚本，目前可用的质量门主要是 TypeScript 构建、oxlint、Rust 测试和 Python 测试；UI 行为需补可测试纯逻辑或做运行时验收。
- 默认入口根因已直接定位：`App.tsx` 的通配路由无条件 `<Navigate to="/project/reconstruction" replace />`，启动时必然进入“对齐与重建”；将默认重定向改为 `/project/media` 即可满足无工程启动场景，不需要新增状态或路由抽象。
- `AppShell` 的显式工作区点击会持久化 `activeWorkspace`，打开已有工程时会恢复该工程最后工作区；这与“软件默认入口”是不同语义，当前不应擅自取消工程级恢复行为。
- 拖放普通素材时，`AppShell` 会 `queueDropPaths(paths)` 后导航到 `/project/media`，说明新素材导入链路确实以 `MediaWorkspace` 为当前生效入口。
- `PhotoFolderPreview` 每次接收目录都会调用 Tauri `preview_photo_folder`，返回前一直显示加载态；若后端先全量递归统计再返回，照片越多等待越久，用户表现就是“预览一直不出现”。组件本身已使用 `loading="lazy"` 与 `decoding="async"`，图片 DOM 不是首要阻塞点。
- 导入确认只保存轨道元数据，照片轨道在 `items.length === 0` 时继续用 `PhotoFolderPreview`；因此“导入前对话框预览”和“导入后轨道预览”共用同一后端命令，修复该边界可覆盖两个场景。
- 前端已有 `listTrackItems(trackId, cursor, limit, filter)` IPC，但 `TrackEditor` 完全没有使用：它从 `project.tracks[].items` 读取全量数组，再在浏览器端过滤/切片；`TrackList` 和 `MediaWorkspace` 也对每条轨道反复全量 `filter`。当照片/视频帧很多时，工程 JSON、React 状态复制和渲染前计算都会线性放大。
- `MediaWorkspace` 在任务运行时用 `mediaItems[track.id]` 替换轨道 items；若 `JobProvider` 无界累积每个 preview item，会在抽帧期间持续增大 React 状态，需检查事件聚合策略。
- `ProjectProvider.commitImport` 在无工程时顺序执行“创建工程 + 提交导入”，这是合理的低频操作；当前卡顿更可能来自分析目录、预览扫描与项目 items 数据体积，而非该控制流。
- 实际任务状态由旧 `hooks/usePipeline.ts` 提供并通过 `JobProvider` 注入；`mediaItems` 在该 hook 内维护，需要重点检查事件监听是否对每张照片/每帧做数组复制。
- Tauri `pipeline.rs` 启动任务时设置了 `PYTHONPATH` 和 FFmpeg 路径，但搜索结果未显示为此任务设置 `PYTHONIOENCODING`/`PYTHONUTF8`；`lib.rs` 的另一个 Python 命令已设置 `utf-8:replace` 和 UTF-8 模式，说明项目已有可复用的 Windows 编码处理惯例，当前媒体任务遗漏该边界的可能性很高。
- 后端 `media.rs` 已实现分页 `list_track_items_impl` 和原子化 `finalize_media_job_impl`，说明架构设计本身倾向于分页/最终提交；前端未消费分页 API 是实现闭环缺口，而不是需要新增后端抽象。
- 照片预览“不出现”的直接性能根因已确认：`analyze_import_paths` 对目录调用 `collect_photo_paths` 全量递归、排序并计数；随后 `preview_photo_folder` 又重复同样的全量递归和排序，只有第二次扫描全部结束后才返回最多 24 张路径。大目录/慢盘上加载态会长时间不结束。
- `collect_photo_paths` 为了均匀抽样而先持有并排序全部路径，预览需求却只需要少量代表样本；应把“精确总数扫描”和“快速首批预览”分开，至少复用分析结果或让预览在有限扫描内返回。由于 UI 显示总数，推荐单次扫描同时用有界样本算法收集最多 N 张，避免存储/排序所有 PathBuf。
- 当前 `list_track_items_impl` 虽限制返回 250 项，但每次仍先读取包含全量 items 的工程 JSON，并把所有匹配项收集到 `Vec<&...>`；前端也没有调用它。若启用分页，应同时把过滤实现改为流式 `skip/take` + 计数，避免额外 O(n) 引用数组。
- 媒体准备完成时 `finalize_media_job_impl` 会把全部 `prepared.items` 写回 `xpano_project.json` 并通过 `project:updated`/最终 invoke 返回整个项目；这是大量照片/长视频时 IPC 与 React 内存的结构性上限。短期可先控制任务期间无界状态和重复计算；若基准显示最终提交仍不可接受，才考虑把 items 外置为索引文件（该方案改动面更大）。
- 抽帧退出码 120 的首要根因已定位：重建入口 `run_xpano_tracks_job.py` 会在 `main()` 开始调用 `configure_console_output()`，把 stdout/stderr 重配为 UTF-8 + replace；新媒体准备入口 `run_xpano_prepare_project.py` 没有该配置。Tauri `pipeline.rs` 也没有统一设置 `PYTHONIOENCODING`/`PYTHONUTF8`，导致该脚本继承 Windows GBK 文本流。
- `run_xpano_prepare_project.py.emit_line()` 把 errno 9/22/32 转成 `SystemExit(0)` 不能可靠解决关闭阶段错误：CPython 在解释器最终 flush stdout 失败时会把原本的成功退出改成 120，正好吻合用户日志。正确边界应是父进程统一提供 UTF-8 管道环境，并让脚本显式重配输出；不能用“吞掉并假装成功”掩盖断管。
- `usePipeline` 对每个 `pipeline:media-item` 执行 `findIndex` + `map`/展开 + 顶层对象复制，并立即 `setState`；准备 N 个素材项会产生近似 O(N²) 的数组工作与 N 次 React 更新。该状态仅用于任务期间预览，适合做有界缓存和批量刷新。
- `usePipeline.logs` 虽有重复去除/抽帧分桶，但总体仍是无界数组；长任务可能积累大量非进度日志。可设置足够大的环形上限（保留最近日志），避免长视频运行数小时后持续增长。
- Python 照片准备当前逐张执行：读取 EXIF → 硬链接/复制源图 → 生成缩略图 → 发 item/progress 事件。I/O 与解码本身不可避免，但实时事件应节流/批处理；缩略图尺寸已限制为 320，JPEG 还使用 draft 降采样，图像处理实现方向合理。
- `resolve_python` 只选择 `python.exe`/`python`，未选择 `pythonw.exe`；因此无效 stdout 不是 pythonw 选错，而是 Windows 子进程文本流/关闭边界未统一配置。
- 当前相关代码大多是工作树中尚未提交的新架构改动：`App.tsx` 已切到工作区路由，`pipeline.rs` 新增 media item 事件，`usePipeline.ts` 新增实时 items 累积。此次修复应直接完善这些改动，不能回退到旧 PipelinePage。
- 父进程编码修复适合抽成一个小 helper，并用 `std::process::Command::get_envs()` 做 Rust 单测；脚本侧可用伪 stdout/stderr 测试 `reconfigure(encoding="utf-8", errors="replace")`，形成双层回归保护。
- 新前端中 `photoCount` 只用于导入信息文本/有效性，真正的有效性已有独立 `valid` 字段；因此可以把“快速识别可导入目录”与“精确总数”解耦，而不破坏导入决策。
- 为兼顾快速首屏和准确总数，推荐最小方案：`analyze_import_paths` 对照片目录做有上限的快速探测并随结果返回首批 `previewPaths`；导入对话框直接展示这些路径，不再二次扫描。轨道编辑器的独立预览命令也采用有界扫描并将 `total` 标记为可选/近似，避免为显示一个数字阻塞图片。
- 旧 `PipelinePage.tsx` 仍消费同一 `analyze_import_paths` 返回结构，但 serde/TypeScript 对新增字段向后兼容；保留现有 `photoCount` 字段即可避免旧代码编译受影响。
- 照片路径协议本身配置正确：后端 `web_path()` 已把 Windows 反斜杠转为正斜杠，Tauri 启用了 `protocol-asset` 且 scope 为 `**`，前端使用 `convertFileSrc`。因此“始终加载”优先归因于命令未及时返回，而不是 asset 权限或路径格式。
- `lib.rs` 已有照片扫描单测并验证排除嵌套 xPano 工程，可在同一测试模块追加“预览扫描有界、仍能识别目录”的回归测试，无需引入新测试框架。
- 基线结果：`tests.test_prepare_project` 当前 8/8 通过，前端 `npm run build` 通过；这说明现有测试没有覆盖媒体准备入口的 stdout 编码配置，也没有覆盖默认路由/大目录扫描性能。
- 前端基线产物：应用主 chunk 约 78.30 kB gzip，React 约 59.65 kB gzip，Three.js 约 135.45 kB gzip；本次改动不应新增依赖或显著增加 bundle。
- 默认 Cargo target 正被运行中的 `xpano-ui.exe`/cargo 进程占用，Rust 测试需使用独立 target 目录；不应终止用户正在运行的软件。
- 现有 `test_closed_progress_pipe_stops_quietly` 把 stdout OSError 断言为 `SystemExit(0)`，这验证的是当前 workaround 而非正确性：输出通道失效却成功退出会让任务产生“假完成”。本轮应改成验证 UTF-8 输出配置，并让不可恢复的输出错误保持可见。
- 在补齐 cwd 与 PYTHONPATH 后，`.venv/python.exe + CREATE_NO_WINDOW + stdout/stderr PIPE` 的最小用例退出码为 0，本机未复现 120；因此该故障可能还依赖运行中 App/具体路径或环境。但缺失 UTF-8 父子配置是可证实差异，且新增测试能锁住该边界。
- RED 已验证：Python 测试因 `configure_console_output` 缺失失败；Node 测试因 `pipelineBuffers.ts` 缺失失败；Rust 测试因 `configure_python_io` 与 `scan_photo_paths` 缺失而编译失败。
- 实时 items 旧算法微基准：5,000 项 54.7ms、10,000 项 277.5ms、20,000 项 1,586.3ms，且未计入逐项 React setState/渲染；验收目标是 20,000 项合并计算降到近线性、固定保留窗口并显著低于 100ms。
- 新实时缓存微基准：5,000 项 4.1ms、10,000 项 6.1ms、20,000 项 10.9ms，固定保留 240 项；20,000 项纯合并耗时较旧算法下降约 99.3%，同时 React 更新从逐项改为每 80ms 一批。
- 前端构建和 oxlint 均通过；主应用 gzip 从 78.30 kB 增至 78.70 kB（约 +0.40 kB），没有新增依赖。
- Playwright 的 headed/headless Chrome 均在页面加载前以 code 13 退出，无法完成截图验收；已停止由本机浏览器环境导致的重复失败，并新增 `DEFAULT_PROJECT_PATH` 单元测试覆盖默认入口。
- 长视频时间轴已有明确性能边界：前端按约 3% 间隔抽样且最多 40 帧，拖动时只使用最近缓存缩略图，松手后才做一次 200ms 防抖的精确抽帧。
- Tauri `thumbgen` 每个视频只启动一个顺序后台批次，切换视频会设置取消标志并终止当前 FFmpeg 进程树；不会按视频时长线性创建线程或无界缩略图。该部分已有合理设计，无需额外复杂化。
- 项目版本已确认：Tauri 2.11.3、React 19.2.7。Tauri 2.11.3 官方 API 说明 `tauri::async_runtime::spawn_blocking` 会把函数放到“专用于阻塞操作的 executor”上；大目录 `read_dir` 扫描应使用该边界，而不是占用 async executor。
- React 官方 `useRef` 文档明确“Changing a ref does not trigger a re-render”，支持用 ref 暂存高频媒体 item 与 timer ID，再按 80ms 批量转入 state；可视数据最终仍保存在 state，符合官方区分。
- 最终工程全量 items 的结构性基准可接受：20,000 项 JSON 约 2.66MB、解析 6.2ms；100,000 项约 13.42MB、解析 27.9ms、一次筛选 2.3ms（本机 Node 24）。因此当前瓶颈主要是任务期间逐项 React 更新，而不是最终一次性工程载入；无需引入 items 外置/schema 迁移的高复杂度方案。
- 真实媒体准备子进程验收通过：中文轨道名、`CREATE_NO_WINDOW`、piped stdout/stderr、Tauri 等价 UTF-8 环境下退出码 0，生成 3 个 items、发出 `media.complete`，stderr 为空。
- Tauri binary 入口 `cargo check --bins` 通过；仅报告 6 个既有 warning（1 个未使用 import、5 个尚未接入生产的 job event 合同），与本次改动无关，未擅自删除用户正在建设的契约代码。
- 新回归截图将问题定位到确认阶段：`analyze_import_paths`、有效性判断、预览路径和图片 asset 协议均已成功。
- 当前 `MaterialImportDialog` 支持 `busy` 并能显示“正在导入…”，但 `MediaWorkspace` 从未维护或传入 busy；点击后即使 IPC 正在等待或失败，弹窗按钮文字、禁用状态都不变化，用户会感知为“没反应”。
- `ProjectProvider.commitImport` 吞掉具体 Tauri 异常，只返回 `false`；`MediaWorkspace` 仅弹通用 toast“请查看工程栏错误”。该 toast 很可能被高 z-index 模态框遮挡，而工程栏只用一个小圆点表示 error，导致真实错误不可见。
- 截图源目录存在且精确包含 138 个文件；首次粗查未发现 `xpano_project.json`，需要用精确路径继续确认 `photo/xPano` 是否由点击创建。
- 精确检查确认 `D:\3DRegistration\test\photo\xPano\xpano_project.json` 存在：revision 4、已有 1 条 `panoramic_video` 轨道，状态 `failed`，源为同一测试目录中的 OSV。当前照片目录旁已经有合法工程，因此再次从无工程 UI 导入照片时，`create_project` 必然返回 `project_exists`。
- 根因链路已闭环：前端初始 state 不会自动发现 source 子目录下的 `xPano` → `commitImport` 无条件 create → Rust `ensure_project_root_available` 拒绝已有工程 → Provider 吞成 false → 模态框无 busy/内联 error，toast 又不可见 → 用户看到“点击没反应”。
- 正确行为应是：无当前工程时先解析默认工程根；若 `source/xPano` 已存在则打开并向该工程追加导入，只有不存在时才创建。不能删除或覆盖已有工程。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 先检查当前 diff 与新旧架构入口，再选择修改点 | 大量未提交改动可能正处于迁移中，需避免修到已废弃路径 |
| 性能优化必须记录基线和改后数据 | 用户明确要求“性能优秀”，需要证据而不是仅凭代码观感 |
| 不外置 project items | 100,000 项基准仍在可接受范围；外置会引入 schema、事务与恢复复杂度，当前没有证据证明收益高于成本 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 目标创建操作失败：已有 active goal | 读取现有目标并复用；已记录到 .learnings/ERRORS.md |
| PowerShell 下 `rg path/*.rs` 被解释为非法 Windows 路径，产生部分搜索错误 | 后续使用目录参数配合 `-g '*.rs'`，不再把通配符放在路径位置 |

## Resources
- `xpano-ui/src/`：React 前端
- `xpano-ui/src-tauri/src/`：Tauri/Rust 后端
- `scripts/`：Python 管线与素材准备脚本
- `tests/`：Python 回归测试
- Tauri 2.11.3 `spawn_blocking`: https://docs.rs/tauri/2.11.3/tauri/async_runtime/fn.spawn_blocking.html
- Tauri v2 async commands: https://v2.tauri.app/develop/calling-rust/#async-commands
- React 19 `useRef`: https://react.dev/reference/react/useRef

## Visual/Browser Findings
- 2026-07-10 用户截图：导入对话框已识别 `D:\3DRegistration\test\photo` 中 138 张图片，8 张快速预览均正常显示，素材配置为有效，底部“导入有效素材”按钮处于启用状态；故障发生在点击确认之后，而非路径分析、预览或按钮禁用样式。
- 2026-07-10 Playwright/Edge 运行时验收：素材页控制台 0 error/0 warning；2/2 轨道和 130/140 选中项时显示“下一步：对齐与重建”；点击后路由进入 `/project/reconstruction`，16 步后端计划正常呈现，“一键启动对齐”可用。
- 首次浏览器验收暴露 `TrackEditor` 在非 Tauri 环境无条件调用 `convertFileSrc` 的崩溃；统一 `assetSource` 后页面不再崩溃，非 Tauri 对绝对本地路径显示占位而不发起 195 个无效 `file://` 请求。
- 2026-07-10 最新运行日志给出精确提交错误：`project media cannot change while a job is running`。`finalize_media_job_impl` 在轨道仍为 `running` 时错误调用通用 `ensure_project_writable`，把合法的 `running → ready` 提交当成并发编辑拒绝。
- 失败现场的 `media_prepare_result.json`、41/45 个素材项和 `media_full.json` 均完整，证明抽帧没有失败；失败仅发生在工程状态原子提交。
- 修复后真实工程 `D:\3DRegistration\test\xPano` 已验证：revision 4、轨道 `ready`、31 items、alignment manifest 存在，result/job marker 均已清理。
- 2026-07-11 复核用户最新截图：图片创建于 2026-07-10 22:48，错误为 `任务结果提交失败: project revision changed from 2 to 4`；修复源码 `media.rs` 写入于 23:57，定向测试产物生成于 23:58，当前桌面 EXE 于 00:55 重新构建并启动，因此截图明确属于修复前版本。
- 该故障只发生在媒体准备完成后的工程提交：138/138 已索引、manifest/result 均已生成。根因是把会被工作区导航/重命名合法推进的全局 `project.revision` 当成媒体输入版本。当前实现用 `revisions.media` + `inputMediaRevision` 判定真实素材并发变化，并为缺字段/缺 marker 的遗留完整结果保留严格恢复路径。
- 当前代码仍拒绝真正的媒体 revision 变化；它只放行非媒体全局 revision 变化，不是无条件吞掉并发冲突。
- Phase 12 架构复核：仓库当前没有 `CONTEXT.md` 或 `docs/adr/` 决策文件；`docs/UI_WORKSPACE_REDESIGN_SPEC.md` 已明确 `geometry.rs` 承担点云版本、旋转事务和 COLMAP 校验。选择把它做成深模块：少量版本/变换接口后集中实现二进制解析、checksum、canonical/world 归一化、原子物化与工程 revision，提供 locality 和调用方 leverage，不引入只有单一 adapter 的假 seam。
- 多代理探索与当前工作合同冲突（未获用户授权不得 spawn sub-agent），因此本轮按同一架构审查词汇由主代理直接检查；不影响实现范围。
- geometry 深模块采用流式 COLMAP points3D 读写而非整文件载入：内存与点数无关；每条记录校验 finite XYZ/error、track 长度和文件尾，切换前 parse-back。活动物化使用 rollback 文件 + transaction marker，崩溃后按工程 activeVariantId 判定提交或恢复旧 points3D.bin。
- 2026-07-11 再次核对用户这张抽帧失败截图与运行态：截图写入时间 22:48，当前正在运行的 `target/debug/xpano-ui.exe` 构建于 01:51，二进制已包含 `inputMediaRevision`、媒体 revision 冲突提示和遗留结果恢复逻辑。该截图不能代表当前进程仍在执行旧提交逻辑。
- Stage 4 浏览器验收发现 1366/1024 宽度下点云版本面板会遮挡水平校正面板；1920 不受影响。水平校正面板在宽度不超过 1500px 时改放左上角后，三个视口均无面板/任务栏/查看器控制重叠。
- Stage 4 事务审查发现失败回滚会忽略 restore 错误并提前删除 marker，可能让下次打开失去恢复依据。回滚现集中到 `rollback_active_geometry_files`，只有 points/images 全部恢复成功后才清 marker；中途失败会保留 marker 供下次恢复。
- Phase 13 真实工程 `D:\3DRegistration\test\xPano-phase13` 已由最新版 Tauri 命令链创建。OSV 取 0-30 秒、1 秒/帧、上限 31，实际得到 30 个逻辑帧（60 张鱼眼图）；照片轨完整处理 138 张。两轨均 ready，最终 result/marker 已清理，证明 `revision 2→4` 类收尾故障不再出现。
- Metashape backbone 混合对齐约 6.5 分钟完成：438 张导出图、438 个 COLMAP image、11 个 camera、377,707 个稀疏点，`verify_xpano_output.py --expect-single-sparse` 通过。standard canonical、base images 和活动 sparse 文件均已物化。
- 应用后端完整读取 377,707 点和 438 相机约 3.44 秒；工程打开约 45ms，29MB standard 版本完整解析+SHA-256 约 1 秒。结果页所需点云/相机数据可在当前硬件上稳定载入。
- 使用既有 `.venv-densify`（未下载依赖）运行 Turbo/front/10% refs/1000 matches/10 steps/10万点上限，37.3 秒生成 22,632 个新增点，合并版本 400,339 点。永久 densified 版本注册后候选仍存在；dense→standard 双向切换点数分别为 400,339/377,707，活动文件 hash 最终重新匹配 standard。
- 2026-07-11 安装器真实验收发现两个仅在目标机出现的发布缺口：WebView2 Runtime 版本位于 32 位注册表视图 `HKLM\Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F301...}`，旧 NSIS hook 只查当前 64 位视图，误触发离线安装并因退出码 2 回滚；修复为同时查 64/32 位视图，并在安装器非零退出后重新探测，只有运行时仍缺失才失败。
- 安装目录资源哈希与工具探针通过后，安装版 EXE 无窗口而 target release EXE 正常。二者差异证明安装目录遗漏 `WebView2Loader.dll`；该 DLL 由 `webview2-com-sys` 在 Cargo release 构建时生成，正式链现先执行 fresh `cargo build --release`，再将生成 DLL 纳入 release staging/hash manifest，并通过 Tauri resource mapping 安装到 EXE 同级。
- NSIS 默认卸载只删除已登记文件；手工 Python 探针生成的 `__pycache__` 会留下整个 `binaries` 目录。由于预安装 hook 保证应用位于专属 `xPano` 子目录，post-uninstall 现递归删除 `$INSTDIR`，项目仍位于素材旁而不受影响。
# 2026-07-11: extraction completed but final submission reported revision 2 -> 4

- The screenshot is a false failure after successful work: photo indexing reached 138/138 and `素材准备完成` before finalization rejected the result.
- Root cause: the legacy finalizer used the project's global revision as the media concurrency token. Navigation/workspace/name changes legitimately advance the global revision even though media inputs remain unchanged.
- Correct invariant: a media result conflicts only when `project.revisions.media` changed after job start. The active marker/result now carries `inputMediaRevision`; markerless legacy results are recovered only when target tracks are still untouched and revision ordering is safe.
- The real acceptance project is intact and ready: panorama 30 items, photos 138 items, project revision 10, media revision 2.
- Release EXE and installer were built after the fix; installer SHA-256 is `87366E0B3D1A482AEA5523BA31A5B03A49E3BC007688ECB0D4C7E84BDCDD7C09`.

# 2026-07-11 final release audit

- Final post-review installer SHA-256 is `874AD452E38FB98800DA6956567D70D15237E11F0CA152B948953257BBEC8262`; the earlier hashes are superseded.
- Formal build passed 169 Python tests, 21 Node tests, oxlint, Vite, release Cargo prebuild, Tauri release build, and NSIS. Separate Rust suite passed 69 tests; bootstrap matrix passed 26 tests.
- Installed release manifest contains 869 entries. All installed retained files match size/SHA-256; the WebView2 offline installer is intentionally removed after runtime detection/installation.
- Staging contains no `.venv-densify`, torch cache, Torch/TorchVision/Open3D/PyCOLMAP wheels, or RoMa model payload. No real large-package URL was opened during the fake-source matrix.
- Installer and application are currently unsigned (`NotSigned`). This is a certificate/provenance boundary, not a functional failure; signing requires a real publisher certificate outside the repository.
- Metashape remains an explicit proprietary prerequisite when that backend is selected; bundled COLMAP covers the free backend. System Python, FFmpeg, COLMAP, Git, CUDA Toolkit, and administrator rights are not required.
# 2026-07-11 Phase 20 point-cloud preview performance
- Root causes were synchronous Tauri file parsing, JSON serialization of millions of numbers, and coordinate/color/bounds processing on the WebView main thread.
- Standard cloud (631,855 points): backend+IPC improved from about 4.76s to 0.33s; Worker preparation is about 0.27s; total preparation before GPU scene creation is about 0.60s.
- Dense cloud (3,148,444 points): backend+IPC about 1.46s; Worker preparation about 1.40s; all points retained; maximum measured UI heartbeat gap about 108ms.
- The optimized packet uses a 64-byte header, f32 XYZ, lossless u8 RGB, and fixed 48-byte camera records. No point sampling is used by the viewer.
- Sequential buffered track skipping is required for performance and is guarded by a two-point, non-empty-track parser regression test.
- Valid zero-point packets now return an empty result instead of producing infinite bounds.
# 2026-07-11 Phase 21 LichtFeld initial inventory
- Source runtime is `D:\FastPrograms\LichtFeld-Studio-windows-v0.5.3` with top-level `bin`, `DLLs`, `extensions`, `Lib`, `share`, and `LICENSE`; it is a self-contained Windows distribution rather than a single executable.
- The runtime includes Python libraries, USD plugins, application assets/locales, and third-party license files, so integration must preserve the directory layout and notices.
- Existing xPano code already has durable job/pipeline/reconstruction modules and result variants; the new training flow should reuse those task semantics instead of creating a second ad-hoc process system.
- Existing repository tests mention `test_colmap_lichtfield_cli.py`; inspect this before defining new parameter names because earlier CLI groundwork may already exist.
# 2026-07-11 Phase 21 official runtime contract
- Bundled `LichtFeld-Studio.exe --help` for v0.5.3 is authoritative: dataset `--data-path`, output `--output-path`, auto-start `--train`, iterations `--iter`, strategy `--strategy`, SH degree, max Gaussian cap, resize/max-width/cache options, rendering toggles, `--python-script`, and `--log-file` are supported. GUI is the default because visualization is disabled only by explicit `--headless`.
- Runtime build info reports v0.5.3, commit `d8c50c6a`, official repository `https://github.com/MrNeRF/LichtFeld-Studio`, and website `https://lichtfeld.io`.
- Official embedded Python API exposes decorators `on_training_start`, `on_iteration_start`, `on_pre_optimizer_step`, `on_post_step`, and `on_training_end`, plus metric getters for current/total iteration, loss, elapsed time, ETA, splat count, state, and errors.
- Preferred progress contract: pass an xPano-owned bridge through `--python-script`; callbacks emit versioned `XPANO_TRAIN_EVENT:` JSON lines. This is more stable and structured than parsing human log text and works while the GUI remains visible.
- Runtime defaults discovered directly from `OptimizationParams`: 30,000 iterations, strategy `mrnf`, SH degree 3, max cap 1,000,000, DSSIM 0.2, error/edge maps enabled, CPU and filesystem caches enabled, GUI/headless flag false.
- Existing `scripts/lichtfield_cli.py` is obsolete for v0.5.3 (`--input-colmap`, `--image-dir`, `--output`, `--point-count`, `--bilateral-grid`) and should be replaced or rewritten rather than used as the production integration.
- The complete v0.5.3 runtime was copied without trimming to `runtime/lichtfeld-studio`: 1,450 files, 576,058,136 bytes. Bundled executable SHA-256 is `8825D3AE6149089B5BEA307F74EC06848EE9572944046786F9A84DFEE75E770E`.
- `scripts/release_staging.py` already stages the complete repository `runtime/` tree, so this location automatically participates in a future release build without changing the current no-installer constraint.
# Phase 21 progress-channel correction (2026-07-11)

- LichtFeld Studio v0.5.3 visible-GUI auto-training does not execute the supplied `--python-script`; the callback bridge cannot be the production progress channel.
- `--log-file` is active in visible GUI mode. Verified native records include planned iterations, one `Loss updated` record per observed optimizer iteration, checkpoint iteration/Gaussian count, and explicit success.
- The supervisor now tails appended log bytes, emits throttled structured progress, requires both native success and a real output artifact, then closes the managed GUI.
- The obsolete callback bridge was removed from runtime invocation and release-staging requirements.
# Phase 21 manual-test corrections (2026-07-11)

- Real 1,808-image logs proved xPano CLI values were received (`iter=30000`, `max_width=3840`), but LichtFeld v0.5.3 auto-multiplied schedules by `images/300`, producing about 181k iterations.
- `--steps-scaler` is applied before the dataset auto-scaler and cannot disable it. The reliable visible-GUI path is: load dataset without `--train`, connect to the built-in MCP server, reapply final parameters through `editor.run`, then call `training.start`.
- Real MCP acceptance produced exactly 30/30 iterations, `resize_factor=8`, `max_width=512`, and a checkpoint marked `+bilateral` on the 1,808-image project.
- Manual GUI termination advances the durable project revision. Frontend terminal-event handling must reopen the project before another workspace builds a revision-bound plan.
- Structured Tauri errors must use their `message` field; `String(error)` renders `[object Object]`.
# 2026-07-11 LichtFeld real-step progress diagnosis
- Real evidence showed `Loss updated (... buffer size: 26)` while the GUI was around iteration 253; the loss buffer size is not an iteration counter.
- LichtFeld v0.5.3's MCP `training.get_state` returned an all-zero snapshot in xPano's GUI-started training path and therefore cannot be trusted here.
- The authoritative live source is the embedded Python trainer API (`trainer_current_iteration`, total, loss, and splat count) invoked through MCP `editor.run`; file logs remain useful for startup, checkpoints, errors, and completion.

# 2026-07-11 repeated point-cloud loading diagnosis
- The active standard cloud has 631,855 points; the dense variant has 3,148,444 points. Synthetic processing measured about 212 ms and 1,184 ms respectively, so the Worker computation alone does not explain repeated multi-second hangs.
- The debug app runs under React StrictMode, which intentionally remounts effects. The point-cloud cache currently lives inside `PointCloudViewer`, so StrictMode remounts and route navigation discard it.
- `ResultsWorkspace` creates `variantPreview` inline, while the loading effect depends on the object identity. Project/job re-renders can therefore start another load before the first finishes.
- There is no shared in-flight Promise, so duplicate triggers concurrently repeat Rust parsing, raw IPC transfer, Worker processing, memory allocation, and GPU preparation for the same cloud.
- The smallest complete fix is session-level resolved/in-flight caching plus a persistent results surface in `AppShell`; this preserves the existing parser, Worker, full point count, colors, camera overlays, transforms, and Three.js rendering.

# 2026-07-11 offline release runtime audit

- User-defined release boundary: all normal xPano capabilities must be bundled and offline-callable; Metashape itself remains external/licensed; xPano-required Metashape Python dependencies ship as wheels and auto-install; densification alone may download a large environment.
- The authoritative installer chain is `scripts/build_installer.ps1` -> `scripts/release_staging.py` -> `xpano-ui/src-tauri/tauri.release.conf.json` -> Tauri NSIS.
- Direct release blocker: `release_staging.py` copies bundled Python, scripts, COLMAP, densification plugin, the whole `runtime/`, FFmpeg, WebView2 and requirements files, but does not copy `tools/offline-wheels`. The older non-authoritative `build_release.ps1` does copy them, which can hide the formal installer defect during repository testing.
- Current wheel inventory already covers Metashape's required NumPy/OpenCV for Windows x64 Python `cp39`, `cp310`, `cp311` and `cp312` when the app and Metashape wheel directories are considered together. OpenCV is an ABI3 wheel. The formal package currently omits all of these files.
- Approximate payload sizes: bundled Python 194.5 MiB, COLMAP 419.1 MiB, app wheels 124.4 MiB, Metashape wheels 66.8 MiB, LichtFeld Studio 549.4 MiB. Installer size/compression and license review are therefore release concerns, but not reasons to weaken offline guarantees.
- `configure_environment.ps1` installs Metashape packages into `<app root>/tools/metashape-python/<abi>/site-packages`, writes `<app root>/tools/metashape-python/active_path.txt`, invokes `<Metashape Python> -m pip`, and falls back from local wheels to Tsinghua/default PyPI. This mutates packaged resources, assumes Metashape has pip, is non-deterministic and violates the offline-only contract.
- `pipeline_core.metashape_process_env()` searches app/internal roots for `active_path.txt`; Rust preflight only observes PowerShell text/exit status, and the later pipeline process receives no explicit resolved Metashape dependency path. The Interface is spread across PowerShell, Python and Rust and lacks Locality.
- Backend/UI probes currently treat finding `metashape.exe` as Metashape readiness and finding either Metashape or COLMAP as global environment readiness. They do not represent dependency installation, unsupported ABI, bundled corruption or optional densification state.
- `runtime_bootstrap.py` already provides the required hard parts for densification: manifest/hash validation, resumable artifacts, disk preflight, cancellation, live/stale lock handling, staging, probe, atomic activation and rollback. A second independent installer would duplicate correctness-critical Implementation.
- Recommended architecture: deepen that Module behind `probe(runtime)`, `ensure(runtime)` and `resolved_environment(runtime)`. Use three Adapters at the same Seam: immutable bundled probe-only resources, bundled-wheel Metashape provisioning, and downloadable densification.
- Metashape state should live under `%LOCALAPPDATA%/com.xpano.app/runtimes/metashape/<metashape-fingerprint>-<python-abi>-<bundle-version>/`; the fingerprint must include executable identity/version, ABI and dependency bundle version so upgrades and multiple installations cannot alias stale packages.
- Runtime installation should select exact manifest-listed wheel filenames and hashes, use bundled `runtime/pip.pyz --no-index --require-hashes --only-binary`, stage and probe before activation, and inject the resulting site-packages only into the Metashape child via `XPANO_METASHAPE_SITE_PACKAGES`.
- App Python and bundled executables should be validated at build time and probed at runtime, but never repaired by pip in the installed application. Corruption is a visible reinstall/repair failure; only the external Metashape add-on runtime is auto-provisioned.
- Requirements files alone are insufficient as the release contract: `requirements.txt` leaves Pillow unpinned and pip resolution can select unintended artifacts. The shipped runtime contract needs exact artifact profiles plus hashes and notices.
- One audit command combined a valid AppShell read with Windows wildcard `rg` paths and exited 1; the useful output was retained and the search was rerun with explicit directories. This was a command-shape issue, not a code failure.

# 2026-07-11 offline runtime implementation and acceptance

- Added `runtime/bundled-runtime-manifest.json` with exact cp39/cp310/cp311/cp312 Windows x64 NumPy profiles, shared OpenCV ABI3, sizes, SHA-256 hashes and license identifiers. Runtime loading and release staging reject incompatible wheel/profile assignments.
- Formal release staging now copies the app and Metashape wheelhouses plus the bundled manifest and notices. Final staging contained 2,132 manifest entries and 13 wheel files with all four supported ABI tags.
- Replaced mutable app-root `active_path.txt` with LocalAppData state and explicit `XPANO_METASHAPE_SITE_PACKAGES` injection. `pipeline_core` sanitizes xPano Python/Qt paths and prepends only that resolved directory to the Metashape child.
- `bootstrap_local_runtime` reuses lock, hash, disk, staging, probe, activation and rollback mechanics. It cleans abandoned staging directories only while holding the shared bootstrap lock.
- `configure_environment.ps1` is now a compatibility wrapper over `runtime_readiness.py`; it has no PyPI/Tsinghua fallback and does not invoke Metashape `-m pip`.
- Real acceptance found the previous bundled pip zipapp required Python >=3.10. It was replaced with a pip 25.0.1 zipapp whose metadata supports Python >=3.8 and which executed successfully under Metashape Python 3.9.
- A copied Metashape Python 3.9 environment with `Lib/site-packages` excluded failed `import numpy, cv2` before provisioning, then installed NumPy 1.26.4 and OpenCV 4.10.0 entirely from staged wheels. The second ensure reused the active runtime.
- The simulated Metashape tree contained 3,756 files before and after provisioning; per-file path/size/SHA-256 comparison reported zero differences. Runtime state lived under a Unicode-and-space LocalAppData analogue.
- Final staged resources successfully provisioned the isolated Metashape Python and imported NumPy/cv2. They contained runtime readiness, pip, notices and all wheels, with zero forbidden densification payload entries.
- Five-axis review verdict: approve. No unresolved Critical or Important finding remains; no installer was built.

# 2026-07-11 release 0.2.0 findings

- Version 0.2.0 is appropriate because the release adds a Gaussian-training workspace, a new runtime-provisioning contract and materially changes packaged dependencies; reusing 0.1.x would understate upgrade semantics.
- The formal installer is 694.8 MiB and expands to about 1,497.2 MiB because it includes LichtFeld Studio, COLMAP, embedded Python and offline wheels. This is expected under the offline-runtime requirement.
- Git LFS is required for reproducible source versioning: three LichtFeld files exceed 50 MiB and `slang-llvm.dll` exceeds 100 MiB. The release commit stores relevant binary types as LFS pointers.
- The installed manifest exactly matched retained installed resources. The only absent file was the WebView2 offline installer intentionally deleted by the NSIS hook after successful installation.
- Tauri's warning that `com.xpano.app` ends in `.app` concerns macOS bundle naming. Windows x64 is the supported release platform, and changing the identifier would break Windows upgrade/runtime-state continuity, so it remains unchanged.
- The npm `url.parse()` deprecation warning comes from package tooling and did not affect tests or the built application.
- The release is intentionally unsigned because no Authenticode publisher certificate is configured. Windows reputation prompts remain until signing is added.

# 2026-07-11 full offline release boundary

- The existing 0.2.0 installer already contains app Python, FFmpeg/ffprobe, COLMAP, LichtFeld Studio, WebView2 support, runtime manifests, pip and Metashape cp39-cp312 offline wheels.
- Phase 23 deliberately excluded only the densification CPU/CUDA environment and model artifacts. A genuinely full offline variant therefore needs to close that existing manifest/cache boundary, not invent a second runtime architecture.
- The compatibility-first default is to bundle both CPU and CUDA profiles and retain runtime capability selection, at the cost of a substantially larger installer.
- The locked densification manifest defines 71 artifacts per profile. A full package should carry the union once under SHA-256 names; common dependencies are shared between CPU and CUDA.
- The local `.venv-densify` is CUDA 12.8 (`torch 2.8.0+cu128`, torchvision 0.23.0, Open3D 0.19.0, PyCOLMAP 4.0.4) but is an Anaconda-derived development environment and is not a valid formal release source.
- The existing product Python intentionally lacks densification-only imports such as torchvision until Runtime Bootstrap activates a verified site-packages tree.
- The union is 73 artifacts / 5,375,693,470 bytes. CPU is 1,906,768,780 bytes; CUDA is 4,754,740,087 bytes. The CUDA Torch wheel alone is 3,461,384,651 bytes, so the final container must be validated with real payload sizes rather than assumed to fit NSIS.
- The four PyTorch manifest URLs pointed at `download-r2.pytorch.org` and returned 403, while official `download.pytorch.org` endpoints returned 200 with exact locked Content-Length values. Artifact hashes and versions did not change.

# 2026-07-11 libunwind clean-machine incident

- The released `xpano-ui.exe` directly imports `libunwind.dll`; neither release staging nor the installed app root contains it.
- Cargo and rustc are a custom `x86_64-pc-windows-gnullvm` 1.94 toolchain. The existing `.cargo/config.toml` only configures `x86_64-pc-windows-msvc`, so those linker settings never applied to normal builds.
- The developer toolchain provides `libunwind.dll` beside `rustc.exe`, masking the missing app-local dependency during local and installed acceptance when PATH is inherited.
- A same-toolchain minimal probe proves `-C target-feature=+crt-static` removes `libunwind.dll` from the PE import table. This is preferable to shipping a toolchain DLL, but a generic import-closure gate is still required for future dependencies.
- Installed acceptance exposed a second root cause: `NSIS_HOOK_PREINSTALL` rewrote `$INSTDIR` after Tauri had already selected the installation root. The launcher/manifest landed in the original root while resources/uninstaller moved under an added `xPano` child; WebView2 postinstall then aborted and rolled resources back, leaving only six files. Removing the hook restores Tauri's single-root contract.

# 2026-07-11 installed extraction import incident

- User evidence shows installed `run_xpano_prepare_project.py` fails at line 12 on `from scripts import xpano_tracks` with `ModuleNotFoundError: scripts` before extraction begins.
- Python sets `sys.path[0]` to the script directory when launched by absolute path. In an installation such as `%LOCALAPPDATA%\xPano\scripts\run_xpano_prepare_project.py`, importing the top-level `scripts` package requires the application root (the parent of `scripts`) on `sys.path`; developer launches from the repository root can mask this boundary.
- The project currently stores `secondsPerFrame`/`seconds_per_frame` through React, Rust contracts, project JSON, Python CLIs and track planning, then converts it to FFmpeg FPS using `1 / seconds_per_frame`. The requested FPS model therefore crosses every layer and needs an explicit legacy migration rather than a label-only UI change.
- Bundled Python uses `python312._pth`, so ambient `PYTHONPATH` and working-directory assumptions are not a valid repair. The preparation entrypoint now inserts its resolved application root before package imports, and every shipped runtime entrypoint is probed from an unrelated working directory with the isolated interpreter.
- Extraction is now canonical FPS end to end: project schema v3 uses `framesPerSecond`, Rust/Python use `frames_per_second`, FFmpeg receives the value directly, estimates use the same value, and timestamps advance by `1 / fps`. Schema v2 intervals migrate atomically with `fps = 1 / secondsPerFrame`.
- Real installed-style acceptance found an additional Windows boundary: UTF-8 BOM project JSON previously failed before extraction. Rust and Python project readers now accept BOM while writers remain canonical BOM-free UTF-8.
- Synthetic 5-second ordinary MP4 and dual-stream OSV at 2 FPS each produced exactly 10 items with timestamps 0.0 through 4.5 under bundled isolated Python, no `PYTHONPATH`, sanitized PATH and Unicode/space paths.
- Formal 0.2.2 installation retained 2,132/2,133 manifest files with zero size/hash mismatches; the sole missing file was the intentionally deleted WebView2 installer. Installed entrypoints, app startup and real extraction passed before uninstall.

# 2026-07-12 explicit Metashape path and environment audit

- The active `ReconstructionWorkspace` configuration model has no executable-path fields. It calls `probe_reconstruction_backends` without overrides, persists no path, and builds the launch `PipelineConfig` from auto-detected probe paths. The older `PipelinePage` still contains a file picker, but that is not the active project reconstruction flow.
- Rust `detect_metashape()` checks `XPANO_METASHAPE` and two Program Files locations, then returns the bare string `metashape.exe`; it does not resolve PATH. `command_available()` may nevertheless treat that bare command as available through `where.exe`, while `runtime_readiness.py` calls `Path(...).resolve()` and rejects it as a missing current-directory file. Probe and execution can therefore disagree.
- The real local Metashape is at `E:\FastProgram\Metashape\metashape.exe`, outside the hard-coded detection locations, reproducing the user's need for manual selection.
- Explicit invalid paths must fail visibly and must never fall back to an auto-detected executable. The chosen executable must be the same value used by backend probe, project persistence, runtime dependency provisioning, execution-plan identity and final process launch.
- Other relevant environment boundaries: `resolve_python(explicit)` silently falls back when an explicit path is invalid; Rust `locate_tool` prefers bundled files before environment overrides; release readiness correctly validates canonical bundled paths and therefore prevents a corrupt installed bundle from being masked by developer PATH.
- The active flow now persists the selected executable and sends the same normalized value through backend probing, execution planning, readiness provisioning and final process arguments.
- Explicit values are authoritative across UI configuration, `XPANO_METASHAPE`, Python dependency checks and explicit Python selection. Missing explicit values fail visibly instead of selecting another local installation.
- Quoted paths, surrounding whitespace, Unicode directories, spaces and PATH-only `metashape.exe` resolution are normalized and regression-tested.
- New execution plans record the concrete Metashape executable, reject unavailable paths before start and become invalid if the configured executable changes.
- Bundled Python/FFmpeg/COLMAP/LichtFeld remain package-first; no new dependency or environment manager was introduced.
- A source-root readiness CLI probe reported missing FFmpeg because the checkout lacks the formal staged FFmpeg layout. The actual selected Metashape resolved under a sanitized PATH as cp39, and both required offline wheel artifacts were present.

# 2026-07-12 Phase 30 acceleration architecture

- Hardware acceleration is feasible; the current limitation is implementation-specific because `export_colmap.py` performs custom NumPy remapping outside FFmpeg.
- The existing offline Runtime Readiness contract already bundles and provisions OpenCV 4.10 wheels for supported Metashape ABIs. Reusing `cv2.remap` and optional OpenCL/UMat introduces no new runtime family and is safer than adding PyTorch, CuPy or a custom CUDA runtime.
- A CUDA-only OpenCV build would add a large, fragile DLL closure. Treat it as a later evidence-driven option only if the existing OpenCL or compiled CPU backend cannot meet the target.
- Strict byte identity is achievable for PSX re-export by reusing existing JPEG files. Recomputed GPU or compiled interpolation may differ from NumPy by small rounding amounts, so accelerated recomputation needs a golden-image gate and observable fallback.
- The current re-export transaction moves `images`, `sparse`, `colmap` and the run summary out before export. That guarantees cache misses and relies on Python `finally` for restoration; hard termination can leave a persistent backup and partial new outputs.
- The real re-export completed successfully at 16:03 local time. Image processing ran from 15:41:19 to 16:03:06 (about 21 minutes 47 seconds), COLMAP writing/validation completed by 16:03:22, and the temporary backup directory was removed.
- The authoritative bundled runtime manifest provisions `opencv_python_headless-4.10.0.84` for cp39-cp312 with a locked 38,754,031-byte wheel and SHA-256. This confirms the compiled backend can remain within the existing offline environment contract.
- Re-export cannot safely update invalidated images in place while keeping the old sparse model: a failure could leave old COLMAP metadata paired with partially new pixels. The stable boundary is a staging directory under the same output volume, hardlink or copy only verified cache hits into staging, generate misses there, validate the complete staged dataset, then publish directories with a persistent transaction marker and rollback recovery.
- Hardlinked cache hits must never be opened for overwrite because that would mutate the live image through the shared file record. The exporter must decide reuse before scheduling writes; only misses receive new files.
- Cache identity must exclude camera transform and tie-point changes because those do not alter pixels, but include source identity, full sensor calibration, export geometry, frame/cubemap strategy, JPEG policy and image algorithm version. This preserves manual pose corrections while invalidating calibration or source changes.
- Existing tests currently assert that successful re-export removes stale images by moving the entire image directory away. Phase 30 must replace that contract with verified selective reuse and add crash-recovery coverage before changing the transaction.
- The active development Python reports OpenCV 4.13 with OpenCL enabled through `NVD3D11`; this proves the existing headless OpenCV family can expose a hardware path on the RTX 4060 without CUDA-specific packages. The exact locked 4.10 wheel still needs an isolated probe before release claims.
- No activated Metashape dependency runtime was found under the current LocalAppData state, so acceptance must explicitly provision/probe the locked wheel rather than relying on the developer `.venv` installation.
- A real 2,094 x 2,094 RGB face benchmark measured current NumPy remap at about 1.009 s, OpenCV OpenCL after warm-up at about 0.022 s, and OpenCV CPU at about 0.004 s on this machine. The compiled CPU backend is currently faster than GPU because GPU upload/download dominates this per-face workload.
- OpenCV CPU and OpenCL differed from the current NumPy interpolation by at most 4 intensity levels with mean absolute difference about 0.36. OpenCV `remap` rejects `INTER_LINEAR_EXACT`, so OpenCV cannot provide strict pixel identity with the current NumPy implementation.
- Therefore `auto` must choose the measured fastest validated backend rather than blindly prefer GPU. OpenCL remains a real hardware backend and can win on other devices or future batched/resident-grid implementations, but the current machine should select compiled CPU.
- The strict no-change path remains image cache reuse. Accelerated first-time recomputation preserves geometry, dimensions and JPEG quality but is not byte/pixel identical to the legacy NumPy interpolation; this distinction must stay observable in backend metadata and acceptance results.
- `verify_output` validates staged `images`, a single `sparse/0`, and the three binary counts without requiring the PSX inside staging, so it is suitable for the new pre-publication gate.
- Runtime Readiness can provision the exact locked OpenCV wheel through `runtime_readiness.py ensure`; source-checkout acceptance must supply actual FFmpeg/ffprobe/COLMAP overrides because the formal staged tool layout is not present in the checkout.
- Focused Python compilation and 19 cache/export/transaction tests pass after exporter integration; real Metashape execution and full suites remain the authoritative next gates.
- Formal Runtime Readiness reports the real Metashape cp39 environment ready from Metashape itself with OpenCV 4.10.0 and NumPy 1.26.4; no additional LocalAppData install or new dependency was needed on this machine.
- The exact Metashape OpenCV 4.10 build exposes OpenCL through `NVD3D11`. Its auto probe selected OpenCL, then remapped the real 2,094 x 2,094 face in about 0.0147 s versus 1.0386 s for legacy NumPy, a roughly 70x kernel speedup with the same maximum 4-level interpolation delta.
- Backend choice legitimately differs by OpenCV build: developer OpenCV 4.13 selected compiled CPU, while Metashape OpenCV 4.10 selected OpenCL. This validates runtime benchmarking instead of a hard-coded preference.
- The available `D:\3DRegistration\test\xPano` project is a real mixed 1,808-image PSX (1,670 cubemap faces, 138 frame images, 631,855 points), so a full duplicate run is unnecessarily expensive for the first gate. A temporary in-memory camera-selection probe can exercise the real PSX without saving or modifying it.
- Bounded real Metashape acceptance selected 2 fisheye and 2 frame cameras. First export completed with OpenCL and wrote 10 cube plus 2 frame JPEGs and a cache manifest; the second export reported `reused=4, regenerated=0` and completed in 5.686 seconds wall time including project load and tie-point processing.
- All 12 reused JPEG SHA-256 hashes were identical between exports. `cameras.bin`, `images.bin` and `points3D.bin` were also byte-identical; both outputs validated as 11 cameras, 12 COLMAP images and 11,197 referenced points.
- The 1,013-camera first accelerated export completed in 367.606 seconds versus the measured legacy roughly 1,263 seconds, a 3.44x overall speedup. It regenerated all cameras using OpenCL/frame warp, published atomically, and validated 3,581 images plus 1,235,942 points.
- The first full cache-hit re-export completed in 114.755 seconds with `reused=1013, regenerated=0`. This is an 11x improvement over legacy but slower than the tens-of-seconds target because the current strict path rehashes every source once, every cached output during verification, and every staged output again while rewriting the cache manifest.
- Safe next optimization: retain the SHA-256 recorded at cache creation, use unchanged size plus nanosecond mtime as the fast validation guard, fall back to SHA-256 whenever metadata differs, and carry verified output records into the next manifest instead of hashing hardlinked bytes twice. This preserves corruption detection while eliminating normal-case multi-gigabyte rereads.
- The cache migration run dropped to 72.450 seconds, and the following stable metadata-fast-path run dropped to 59.961 seconds with 1,013/1,013 hits. Remaining time is no longer image decoding/remap/hash; it is dominated by tie-point extraction/reprojection, 3,581 hardlink/stat operations, COLMAP binary serialization and per-camera logging.
- Instrumented full hot-cache run: sensor scan 0.115 s, 3D point scan 7.237 s, per-camera image/observation loop 50.243 s, COLMAP binary writing 10.942 s, cache manifest write 0.040 s, exporter total 68.775 s. The remaining bottleneck is conclusively the cached per-camera observation loop, not cache JSON, remap or final serialization.
- In the cubemap observation loop, every projected tie point currently constructs a NumPy array and performs a tiny matrix multiplication inside `project_track_to_pinhole`; this occurs once per face and produces millions of small allocations. Replacing it with equivalent scalar float arithmetic is the simplest evidence-backed next optimization.
- The scalar projection experiment reduced the measured observation loop from 50.243 s to 38.968 s, but changed `images.bin` bytes while `cameras.bin` and `points3D.bin` remained identical. The difference is floating-point evaluation order in 2D coordinates. It was rejected and reverted under the strict no-loss gate.
- After reverting the scalar experiment, the full reference hashes were restored: `cameras.bin` `7948C819...F73AD4`, `images.bin` `ACCF91F5...7C27DD`, and `points3D.bin` `E50B485F...3D8155`. Final output validates 3,581 images and 1,235,942 points with no transaction marker.
- The final cache contains 1,013 camera entries; every entry has a source fingerprint and every output record has nanosecond mtime metadata plus its creation-time SHA-256.
# Phase 31 release findings

- The current authoritative application version is 0.2.2 in `package.json`, `package-lock.json`, `Cargo.toml`, the root package record in `Cargo.lock`, and `tauri.conf.json`.
- `scripts/build_installer.ps1 -FullOffline` is the formal release path. It runs Python/frontend gates, performs two release DLL-closure checks, stages immutable resources, embeds the complete CPU/CUDA densification artifact closure, builds a fresh NSIS installer and writes a SHA-256 sidecar.
- Formal staging copies every portable Python module and now explicitly rejects a package missing `export_remap.py` or `export_image_cache.py`.
- Existing `dist` artifacts are historical and will not be reused as the 0.2.3 deliverable; the installer script requires a fresh NSIS artifact timestamp.
- The full-offline manifest references 73 unique CPU/CUDA artifact ids. The local content-addressed store contains 72; the missing artifact is the official 3,461,384,651-byte `torch-2.8.0+cu128-cp312-cp312-win_amd64.whl` with expected SHA-256 `0ad925202387f4e7314302a1b4f8860fa824357f9b1466d7992bf276370ebcff`.
- Targeted searches of pip/xPano/user caches, common download locations and the repository found no existing copy. D: has about 235.7 GB free, enough for the verified download, staging and installer build.
- NSIS cannot safely embed the single 3.46 GB CUDA torch wheel; the formal stable installer therefore follows the documented product boundary and excludes optional densification artifacts while embedding every normal application and Metashape dependency.
- The final 0.2.3 installer has no known npm production dependency vulnerability and passes content hashes, PE import closure and isolated installed-runtime checks. It is not Authenticode-signed because no publisher certificate is available.

# Phase 34 explicit runtime transport findings

- The remaining upstream gap was confirmed in `xpano-ui/src-tauri/src/pipeline.rs`: Runtime Readiness returned `sitePackages`, but the Python job launch only exported `XPANO_METASHAPE_SITE_PACKAGES`. No CLI value reached `run_xpano_tracks_job.py`, so the job object could not preserve the verified path independently of environment inheritance.
- RED coverage proved all missing boundaries: Tauri command args, tracks entrypoint parsing, `MultiTrackJobConfig` persistence, legacy `JobConfig` persistence, alignment launch and PSX re-export launch.
- The explicit transport is now two-stage by design: Tauri passes `--metashape-site-packages` to xPano's Python entrypoint; Python stores that path in the job config and passes `--xpano-site-packages` to each `metashape.exe -r` script. Environment values remain compatibility-only.
- Repository audit found only two production Metashape runner entrypoints that import xPano native dependencies: `metashape_pipeline.py` and `reexport_colmap_from_project.py`; both activate before importing `Metashape`/export modules. `metashape_runtime_probe.py` does the same. Other direct `Metashape` imports are diagnostic/development scripts or modules imported after activation.
- Installed acceptance proves the complete packaged path rather than only source behavior: the two hash-locked cp39 wheels can build a fresh runtime offline, and all three installed Metashape scripts work with custom environment variables removed.
- No correctness, architecture, security or performance blocker remains in Phase 34. Authenticode signing is the only release-hardening gap, and requires an external publisher certificate rather than a code change.

# Phase 35 clean-machine dependency findings

- Confirmed core release defect: the formal installer staging copies `tools/colmap` unchanged and the 2,137-file 0.2.6 manifest contains zero COLMAP MSVC runtime DLLs. The bundled COLMAP imports `MSVCP140.dll`, `MSVCP140_1.dll`, `MSVCP140_2.dll`, `VCOMP140.DLL`, `VCRUNTIME140.dll` and `VCRUNTIME140_1.dll`. It starts on this machine only because those redistributables are installed in System32.
- The old portable builder is not a complete fallback: it copies only `MSVCP140.dll`, `VCOMP140.DLL`, `VCRUNTIME140.dll` and `VCRUNTIME140_1.dll`, omitting the `_1` and `_2` MSVCP imports used by the current COLMAP build.
- The formal DLL gate checks only the Tauri executable plus WebView2Loader. Its system predicate accepts any DLL present in the build machine's System32, which incorrectly treats separately installed VC redistributables as guaranteed Windows inbox components.
- Confirmed optional densification defect: the embedded Python `_pth` configuration ignores `PYTHONPATH`, but both bootstrap and readiness probes rely on `PYTHONPATH` to expose the downloaded `site-packages`. With `PYTHONNOUSERSITE=1`, the raw probe cannot import Torch; the standalone runner's explicit activation succeeds.
- The development machine's roaming Python site is enabled in embedded Python and contains Torch. That can mask missing-package defects and makes the current acceptance environment materially different from a clean user profile.
- Densification also imports exact-name `MSVCP140.dll` and `VCOMP140.DLL` from Torch/Open3D while embedded Python bundles only `VCRUNTIME140.dll` and `VCRUNTIME140_1.dll`; clean machines without VC++ Runtime remain exposed even after the Python path issue is repaired.
- Runtime Readiness reports COLMAP and LichtFeld ready from non-empty file existence only. A restricted staged probe returned ready without launching COLMAP, so it cannot catch the confirmed VC runtime defect.
- Embedded app Python, FFmpeg and ffprobe passed restricted-environment startup/import tests. COLMAP passed only on the current VC-runtime-equipped machine. LichtFeld Studio stayed alive under a system-only PATH and its recursive PE closure contains all non-system imports, including its app-local MSVC/UCRT files.
- Metashape explicit CLI path transport, script-local `sys.path` activation, retained DLL-directory handles and hostile-runner acceptance remain sound. No regression equivalent to the build-22170 environment-filtering issue was found in that chain.
- Residual OS-edition risk: the bundled OpenCV `cv2.pyd` directly imports `MFPlat.dll`, `MF.dll` and `MFReadWrite.dll`. Windows N/KN without Media Feature Pack can still fail at `import cv2`; the current package has no alternative OpenCV build or targeted prerequisite diagnostic.
- The installer remains unsigned, so SmartScreen/publisher trust is still an external release risk rather than a dependency-loader defect.

# Phase 36 implementation decisions

- Use a dedicated `runtime/windows-x64` payload with a hash manifest instead of copying arbitrary System32 files during release. The currently bundled LichtFeld runtime provides a complete, newer 14.44.35211 MSVC/OpenMP set suitable for seeding this dedicated payload.
- Copy the fixed runtime set beside both `colmap.exe` and embedded `python.exe`; this covers current COLMAP plus Torch/Open3D exact-name imports without requiring a machine-wide VC++ installation.
- Treat only a maintained Windows inbox allowlist and API-set names as system dependencies. Presence in the build machine's System32 is not proof of availability on a clean target.
- Use one script-local densification activator for bootstrap probes, readiness probes and the production runner. Environment variables may carry the path but must not be the Python import mechanism.
- Set `PYTHONNOUSERSITE=1` on every bundled Python launch and in nested probes so developer/user packages cannot satisfy missing release dependencies.
- A conventional LichtFeld `--help` probe is unsuitable because the GUI remains open. Its readiness probe should use bounded loader survival or a purpose-built non-training invocation and must terminate the probe process.

# Phase 36 completion findings

- The fixed Windows payload contains all six COLMAP/Torch runtime imports at version 14.44.35211.0 with source and destination SHA-256 validation. Formal and legacy staging deploy it beside both `colmap.exe` and embedded `python.exe`.
- Every bundled Python child disables the roaming user site. Reconstruction entrypoints no longer receive `PYTHONPATH`; Metashape and densification package roots are carried explicitly and activated inside the target script before native imports.
- Runtime Readiness now starts FFmpeg, ffprobe, COLMAP and LichtFeld Studio with bounded probes. Missing loader dependencies are preserved in the UI diagnostic instead of being reduced to a false ready state.
- Recursive PE validation passed for 420 staged Python, COLMAP and LichtFeld executables/libraries using a fixed system allowlist. VC/OpenMP runtimes remain non-inbox; `nvcuda.dll` is explicitly classified as an NVIDIA driver dependency.
- Windows N/KN Media Foundation is the only confirmed non-redistributable OpenCV OS prerequisite. Readiness now checks the three required DLLs before import and names the Media Feature Pack remediation.
- The isolated audit found one further ambient dependency: shipped `pano_extractor.py` imports `tqdm`, but the app wheelhouse and embedded Python omitted it. The 4.68.3 wheel is now offline, embedded and checked by readiness/entrypoint acceptance.
- A fresh release resource tree passed a system-only PATH with `PYTHONNOUSERSITE=1`: embedded imports, FFmpeg, ffprobe, COLMAP, LichtFeld, Metashape cp39 runner and explicit densification CPU imports all succeeded. No installer was built.

# Phase 37 release findings

- The normal 0.2.7 installer is the correct stable boundary: every application, Metashape and native dependency is embedded, while the optional CPU/CUDA densification runtime remains separately provisioned because its CUDA wheel cannot be safely embedded by NSIS.
- Formal staging now contains 2,199 hashed files, including all six app-local VC/OpenMP runtime DLLs beside COLMAP and Python, plus the explicit Metashape/densification activators and offline `tqdm` dependency.
- Installed acceptance under a system-only PATH proved real Python, FFmpeg, ffprobe, COLMAP, LichtFeld and Metashape loader behavior rather than file existence. The GUI also remained responsive with a real main window.
- The installer is content-verifiable through its SHA-256 sidecar and per-resource manifest. It remains Authenticode-unsigned because no publisher certificate is configured; this affects publisher trust, not runtime dependency completeness.
# 2026-07-14 Metashape build-22170 mixed-resolution assertion planning findings

- The robust replacement is one unified `matchPhotos` pass after all cameras are imported, followed by panorama-only alignment, Station release/panorama optimization, flat-only alignment, and global optimization. Matching all once does not change the staged backbone solve.
- The backend execution graph must change with the runtime: new backbone plans use `pano.import -> frame.import -> pano.station -> all.match -> pano.align -> pano.release -> pano.optimize -> frame.align -> all.optimize`. Keeping the old `pano.match/frame.match` graph would make durable progress state false.
- Metashape 2.2.1 API help confirms both matching and alignment camera filters are integer key lists and that `keep_keypoints` only controls storage. The new one-pass backbone no longer needs to store raw keypoints for a later match.
- EXIF orientation remains a secondary, unproven risk. The implementation plan requires a real Metashape orientation probe before changing sensor grouping semantics, plus import-time rejection of incompatible source sensor geometry.
- A real build-22170 run with the failing large dataset is the authoritative acceptance gate; mock tests and build 20221 cannot establish full compatibility alone.

# 2026-07-14 single-match backbone verification findings

- Review confirmed the implementation now imports both material classes before the sole backbone `matchPhotos` call, preserves staged `alignCameras` key sets, releases Station groups only after panorama alignment, and leaves advanced `mixed` plus legacy paths unchanged.
- Added regression coverage for duplicate chunk keys, panorama/flat overlap, incomplete camera-set coverage, missing sensors, and non-positive sensor dimensions. The focused suite is now 15/15.
- Full source verification passed: Python 260/260, Rust 89/89, frontend 44/44, oxlint, TypeScript/Vite production build, `python -m compileall scripts`, and `git diff --check`.
- A fresh build-20221 run used the real default 40,000 keypoint limit with six 3840x3840 fisheye images and eight 4096x3072 flat photos. It completed, wrote the PSX, image/COLMAP outputs and summary, and the PSX reopened with 14 cameras and three sensors. Six panorama cameras aligned; the eight flat photos have no visual overlap with the three selected panorama stations and remained unaligned, which is an input-property result rather than an execution failure.
- This machine provides Metashape builds 20221 and 21778 but no build 22170. The original approximately 4,600-photo, 2880x2880 plus 6000x4000 incident acceptance remains unverified and cannot honestly be replaced by the local result.

## Medium real-runner acceptance

- A fresh `C:\Users\Beluga\AppData\Local\Temp\xpano-single-match-20221-medium` project ran build 20221 against 167 real panorama stations (334 fisheye images) plus 138 real flat photos from the retained test manifest, using `keypoint_limit=40000` and `tiepoint_limit=0`.
- The captured native log reports exactly one `MatchPhotos` call after all 472 cameras were imported, one panorama alignment stage, one flat alignment stage, output validation, and zero `Assertion`, `Traceback`, or `Exception:` markers.
- The matching stage completed feature detection in 52.639 seconds. Peak observed private process memory was about 5.75 GB during matching, below the available 31.8 GB RAM.
- Metashape first solved all 334 panorama cameras, released Station constraints, then incorporated all 138 flat cameras. The saved PSX reopens with 472/472 aligned cameras and three expected sensors (two Fisheye `3840x3840`, one Frame `4096x3072`).
- Export completed through OpenCL image remapping: 472 camera images produced 1,808 JPEG outputs plus the three COLMAP binary files, with `output.validate` emitted. The export timing payload recorded 133.459 seconds.

## Nearby build-21778 regression and correction

- Build 2.3.0 build 21778 is the closest local runner to the incident's build 22170. The first 472-camera one-pass run did not assert and exported successfully, but reopened with only 459 aligned cameras: all 138 flat cameras aligned while 12 left and one right fisheye camera did not.
- A matched panorama-only baseline on the same build aligned/exported all 334 fisheye cameras. The mixed result was therefore a real backbone-quality regression, not an unavoidable source-data limitation.
- The correction keeps the single visual match but preserves the staged-solve boundary more strongly: it snapshots Frame `enabled` states, disables Frame cameras through panorama alignment and panorama optimization, then restores the snapshots before Frame alignment. A regression test fails without that isolation and verifies that only panorama cameras are enabled during the first solve.
- The corrected build-21778 472-camera run reopened with 472/472 aligned cameras: 167 left Fisheye, 167 right Fisheye, and 138 Frame. It emitted one matching stage, one panorama stage, one frame stage, `output.validate`, zero native assertion/traceback markers, 1,808 JPEG exports and the three COLMAP binary files.

# 2026-07-14 single-match backbone implementation findings

- The old mocked mixed-backbone test reproduced the faulty architecture exactly: panorama-only import/match/align/optimize occurred before flat-photo import and a second state-preserving match.
- The new backbone implementation calls `matchPhotos` once after all selected cameras are imported, then calls `alignCameras` with disjoint panorama and flat key sets. It leaves advanced mixed and legacy paths untouched.
- `keep_keypoints=False` is scoped to the new one-pass backbone call; this removes stored-keypoint retention that no later backbone match needs, without changing defaults for other modes.
- Photo-track import now rejects an incompatibly sized/type source sensor group before assigning every photo to the first camera's replacement sensor.
- A real Metashape 2.2.1 build 20221 probe imported a `600x400` JPEG with EXIF Orientation 1, 6, and 8; all three received the same raw `600x400` Frame sensor geometry. The preparation grouping must therefore retain raw dimensions on this supported build. No speculative EXIF width/height swap was implemented.

# Phase 40 release findings

- The fixed source `scripts/metashape_pipeline.py` uses one unrestricted `matchPhotos` call with `keep_keypoints=False`, but the existing 0.2.7 installer, release staging tree, target resources, offline tree, and installed copy all still contain the old repeated-match crash path. A new 0.2.8 build is mandatory.
- The current acceptance summary only records aggregate camera/alignment counts. It can hide complete panorama alignment loss when flat-camera totals compensate, so authoritative evidence needs panorama and frame counts separately.
- The acceptance verifier checks that a supplied PSX is nonempty but does not bind the summary's `project=` value to that PSX. Stale output from another project can therefore be accepted.
- The panorama solve already restores flat-camera `enabled` values in a `finally`, but no regression test proves restoration or proves that downstream flat alignment/optimization stop after a native panorama failure.
- Build 21778 completed the available 472-camera mixed case with 472/472 aligned and valid exports. Exact build 22170 and the approximately 4,600-photo incident dataset remain unavailable locally and must not be claimed as tested.

# Phase 41 Metashape fidelity findings

## Investigation boundary

- xPano does not merely automate Metashape's default Align Photos dialog. It prepares new image files, builds its own calibration groups, creates replacement sensors, assigns camera-group types, seeds calibration values, selects a non-default staged solve order, modifies the chunk coordinate transform through auto-leveling, and finally converts cameras/images to COLMAP. Any of those boundaries can make the xPano result differ from importing the source images directly in the GUI.
- A user-visible "chaotic" result has two distinct possible origins: camera transforms are already wrong inside the saved PSX, or the PSX is correct and corruption is introduced by auto-level/COLMAP/remap/viewer conversion. The audit must not infer the first from the final viewer alone.
- Current code contains explicit sensor/calibration overrides (`Fisheye` versus `Frame`, pixel/focal defaults, `user_calib`, fixed parameters), per-frame Station groups for panorama pairs, one all-camera match, staged panorama/flat solves, and post-alignment auto-level/export. These are material differences from a generic GUI alignment and are the primary review surface.

## Confirmed current behavior from source

- Every imported image uses `load_xmp_accuracy=True`. xPano then discards Metashape's imported sensor assignment and assigns replacement sensors of its own.
- Every panorama hemisphere is forced to `Sensor.Type.Fisheye`, `2.4 um` pixel size, `2.5 mm` focal length, and fixed `B1`, `B2`, and `K4`; all left images share one sensor and all right images share another. These values are product assumptions, not values derived from each source file in the alignment script.
- Every flat/ordinary-video replacement sensor is forced to `Sensor.Type.Frame` and receives a new `Calibration` assigned to both `sensor.calibration` and `sensor.user_calib`. Ordinary-video profiles seed a synthetic horizontal FOV (`standard=70 deg`, `wide=105 deg`); photo tracks copy only the first source sensor's intrinsics/distortion into the replacement group.
- For photo groups, the current validation proves only sensor type and pixel dimensions agree. It does not itself prove camera make/model, lens, focal length, zoom state, focus distance, rolling-shutter behavior, or distortion coefficients agree before all photos are forced onto one replacement sensor.
- The PSX is saved before `align_ground_plane.main()` runs. Export therefore consumes an in-memory chunk coordinate transform that is not represented by the saved project. A correct PSX and a differently oriented exported COLMAP result can coexist; this is a confirmed observability/reproducibility gap even if the auto-level transform is rigid.

## Refined calibration and export findings

- Upstream `build_photo_sensor_groups` does split standard/aerial photos by width, height, camera make/model, lens make/model, focal length, and 35 mm equivalent focal length when those EXIF tags exist. The risk is concentrated in files with missing/stripped/incorrect EXIF, variable focus/distortion at the same reported identity, and ordinary-video frames, which always share one synthetic calibration group.
- Ordinary video defaults to the `wide` profile and therefore a synthetic 105-degree horizontal FOV. The UI choice is not an observation from the file's coded metadata or lens model. A materially wrong initial focal estimate can make an automated solve converge differently from the GUI's imported/estimated calibration.
- The automatic ground-plane step is not an alignment operation from Metashape. It runs an unseeded random RANSAC over global sparse tie points, assumes the largest plane is the ground, selects a second perpendicular plane as forward direction, and applies the result without a support/confidence threshold. Facades, walls, ceilings, roofs, or planar photo sets can therefore be selected instead of ground, and repeated runs can choose different orientations.
- Auto-level replaces `chunk.transform.matrix` with a new unit-scale rigid matrix instead of composing with the existing chunk transform. This discards any existing scale/georeference/local-frame transform in the in-memory export state. It cannot change relative internal camera geometry by itself, but it can materially change exported world coordinates, scale, orientation, and reproducibility.
- `export_colmap.get_coord_transform` additionally derives a local frame from `chunk.crs`, region center, and the current chunk transform. Thus the final COLMAP coordinate frame is produced by two custom transform layers after Metashape alignment. A clean PSX is not sufficient evidence that the xPano viewer/training coordinate output is correct.

# 2026-07-14 Phase 41 Metashape fidelity conclusions

## Official 2.2/2.3 contract

- The 2.2 and 2.3 manuals both require separate calibration estimation for different physical cameras and recommend separate groups per survey. Both warn that a substantially wrong initial focal estimate can cause incorrect alignment or complete failure.
- The 2.2 and 2.3 Python references both define `Sensor.user_calib` as an initial calibration, not a fixed or verified calibration. Both default `addPhotos(load_xmp_accuracy=False)`, while xPano explicitly passes `True`.
- The 2.2 and 2.3 `matchPhotos` defaults are High accuracy, generic and reference preselection enabled, stationary-point filtering enabled, 40,000 keypoints, 4,000 tie points and guided matching disabled. xPano keeps High/generic/40,000/guided defaults but disables reference preselection and stationary-point filtering and defaults tie points to unlimited (`0`). The manual recommends a 10,000 tie-point limit.
- Both manuals define a Station as cameras whose center distances are negligible compared with the nearest object distance. The official spherical-panorama tutorial keeps the group as Station through alignment and saves after checking/updating orientation. It does not release the Station to Folder and optimize independent camera centers.
- Both manuals describe synchronized rigid multi-camera systems using a multi-camera layout, master/slave sensors and optional relative offset/orientation estimation. xPano instead approximates every dual-fisheye capture as a zero-baseline Station, never establishes a rigid master/slave rig, and later removes even the Station constraint.
- Metashape 2.3 adds explicit `EquidistantFisheye` and `EquisolidFisheye` sensor types. xPano uses the legacy generic `Fisheye` model for every supported panorama source and never selects projection by device.
- The 2.3 manual says video import can retain supported DJI, GoPro, MISB and other geographic metadata and offers motion-relative automatic extraction steps of roughly 3%, 7% or 14% of image width. xPano samples by a fixed time rate (default 1 FPS) and writes JPEGs containing only synthetic make/model tags, discarding original video navigation/calibration metadata.

## Confirmed fidelity defects

- Default Backbone mode matches all cameras once but disables every Frame camera while solving the panorama cameras. It therefore forces the panorama subset to define global geometry even when the flat-photo network is the stronger, better-connected network. Flat cameras are only attached in a later `alignCameras(cameras=...)` call. This is not equivalent to the normal all-camera Align Photos operation, and the UI incorrectly recommends it for mixed inputs.
- After the panorama solve, xPano changes all panorama groups from Station to Folder and runs bundle optimization. This releases the only same-center constraint while no rigid-rig constraint exists to replace it.
- A retained real 2.2.1 small-run PSX proves the release defect is observable, not theoretical. Three former panorama stations were saved as Folder groups. Their left/right center baselines are approximately `0.000001`, `0.863243`, and `1.916056`; the aligned component region diagonal is only `16.293069`, so the worst split is 11.76% of the scene scale. The pipeline still accepted and exported the run.
- The same retained PSX contains two Metashape components, each with transformed cameras. Official documentation defines components as independently aligned photogrammetric networks that must be connected and merged. xPano never gates on component count or camera component membership.
- Export selects every enabled camera with a transform but reads `chunk.tie_points` without restricting cameras to the active component. Multiple independently aligned components can therefore be serialized into one COLMAP model even though their coordinate frames are not proven connected.
- Alignment acceptance records only camera transform counts, sensor counts and raw station baselines. It has no component-count gate, normalized station-baseline threshold, reprojection RMS, connectivity, cross-type tie coverage, calibration plausibility or camera-path continuity check. Thus 100% `aligned` is not evidence of a coherent block.
- The production pipeline does not even require a minimum aligned-camera rate before export. The retained small run exported 30 cubemap images after aligning only 6 of 14 source cameras, so a badly incomplete native solve can be reported as a completed xPano job instead of failing before export.

## Strong input/model risks

- All panorama devices receive the same 2.5 mm focal length, 2.4 um pixel pitch and fixed B1/B2/K4 values. These are not derived from source metadata, a device profile or a calibration certificate.
- Ordinary video defaults to a synthetic 105-degree horizontal FOV. A 70-degree alternative is user-selectable, but neither value is inferred from the stream. The official warning about wrong initial focal values applies directly.
- Standard/aerial photo grouping is reasonable when EXIF is complete, but files with empty or wrong EXIF can still be collapsed by dimensions and blank identity. Replacement sensors also discard imported sensor attributes outside the small copied subset.
- Loading XMP accuracy while leaving imported camera reference measurements enabled changes bundle weights from API defaults. This can over-constrain datasets carrying stale, optimistic or inconsistent XMP accuracy.
- Disabling stationary-point filtering removes the documented safeguard against sensor/lens artifacts. Disabling reference preselection also discards useful camera-location pairing for referenced aerial data. Unlimited tie points is another material departure from both API defaults and the manual recommendation.
- `.osv` extraction assumes streams `0:0` and `0:1` are the two fisheye views; INSV pairing is based on filename convention and index-aligned independent decodes. There is no stream-role, timestamp-synchronization, projection or optical-calibration validation.

## Post-alignment distinction

- The saved PSX is written before custom auto-level. Therefore a wrong saved PSX points to import/calibration/grouping/matching/alignment/optimization; a correct PSX with a wrong xPano result points to auto-level/export/remap/viewer.
- Auto-level is unseeded random RANSAC, has no plane-support confidence gate, assumes the dominant plane is ground, and replaces rather than composes `chunk.transform.matrix`. This cannot by itself alter relative internal camera geometry, but it can make export orientation, scale and georeferencing disagree with the saved PSX.

## Phase 44 decision

- Station membership is an intra-rig constraint and does not conflict with attaching ordinary photos as Folder cameras. Panorama groups should therefore remain Station throughout mixed-material alignment and global optimization.
- Releasing Station does not create a controlled fine adjustment of a rigid dual-fisheye rig; it removes the only available rigidity model and permits the two hemispheres to acquire independent camera centers.
- The scoped fix changes only group lifecycle. Matching, camera subsets, retry behavior, optimization parameters, partial-alignment reporting, and Component selection remain unchanged.

## Repair direction for a future implementation turn

- First make a Metashape-native fidelity mode reproduce normal all-camera alignment: preserve correct imported calibration groups, use device-backed fisheye profiles, retain Station or establish a real rigid rig, and do not force panorama-first geometry.
- Treat multiple components, implausible normalized station baselines and high reprojection error as hard alignment failures before export. Report per-type and cross-type connectivity rather than transform counts alone.
- Separate alignment acceptance from coordinate/export acceptance: save the exact post-transform project or make export transforms deterministic and explicit, then validate COLMAP reprojection consistency independently.
- Use controlled A/B datasets to isolate one variable at a time: native GUI baseline, xPano import-only PSX, all-camera solve, Station-retained solve, device calibration profile, default matching flags, and final export.
# Phase 42 findings: downloaded 0.1.0 versus current alignment behavior

## Baseline identity

- `C:\Users\Beluga\Downloads\xPano-0.1.0` is not byte-identical to the repository tag `v0.1.0-portable`; the five alignment/extraction scripts have different Git blob hashes. The downloaded directory is therefore the authoritative old behavior for this comparison, not the tag.
- The downloaded source was timestamped 2026-07-08 and contains a two-phase pipeline: import/match/align panorama cameras as Stations, release and optimize, then import flat photos, match panorama-plus-flat cameras, incrementally align, and optimize.
- The current 0.2.7 release-stage Backbone pipeline uses the same broad two-phase intent, but the current 0.2.8 source (the active worktree) changed this to import all cameras, perform one all-camera match, disable flat cameras during the panorama solve, retry only unaligned panorama cameras, then align flat cameras.

## Confirmed non-cause

- The old source sets panorama sensors to `Metashape.Sensor.Type.EquidistantFisheye`; the current source sets `Metashape.Sensor.Type.Fisheye`.
- A native probe on Metashape 2.3.0 build 21778 projected identical rays at 15, 30, 45, 60, 75 and 89 degrees to identical pixel coordinates for both enum values when `f=2.5 mm`, pixel size `0.0024 mm`, and zero distortion. Metashape 2.2.1 exposes only `Fisheye`. This enum spelling is not the source of the large geometry regression.

## Confirmed behavioral deltas

1. The old pipeline's first `matchPhotos` sees only panorama cameras. The active 0.2.8 pipeline matches the complete mixed-resolution chunk before the panorama solve. Even with flat cameras temporarily disabled for `alignCameras`, their matches/tie-point tracks exist in the chunk and can influence the native solve. This is the strongest direct explanation for dataset-dependent large errors: high-texture planar photos can add false or weak cross-links to a dual-fisheye backbone, while a panorama-only first solve cannot be contaminated by them.
2. The old pipeline calls `alignCameras()` without a camera subset during the second phase and explicitly preserves the existing alignment (`reset_alignment=False` where supported). The 0.2.7 Backbone calls `alignCameras(cameras=frame_keys)` and the 0.2.8 Backbone keeps the panorama camera set isolated, then optimizes globally. These are not equivalent when cross-track matches are weak: the new path can leave a locally wrong flat component fixed long enough for the final global optimization to pull the panorama solution.
3. The old source disables Metashape CPU compute after selecting dedicated GPUs. Current source no longer forces `cpu_enable=False`; logs show mixed CPU/GPU feature extraction. This is a reproducibility/performance delta, not sufficient evidence for a scene-scale error by itself, and should be treated as a secondary contributor.
4. Current Backbone imports and matches flat photos before the panorama solve, whereas the old source imports them only after the panorama solve. This changes Metashape's matching workload and tie-point graph even when the final camera list is identical. The current acceptance log confirms the all-camera match generated two native matching batches and 1,045,621 tie points on the medium project; the old first phase generated a panorama-only batch before any flat cameras were present.

## Shared defects (not a version-only regression)

- Both old and current pipelines release Stations to Folders and run `optimizeCameras`; without a rigid-rig replacement, paired hemispheres can drift. A retained current PSX already measured a worst former-station baseline of 1.916 against a component diagonal of 16.293 (11.76%). This defect can make a dataset fail in both versions, but a changed mixed tie-point graph can make it appear only in the new version.
- Both export all transformed cameras without requiring a single Metashape Component. Multiple disconnected components can therefore be rendered together as one scene. This is a separate export acceptance bug, not proof that the native alignment itself failed.

## Evidence limits

- A same-manifest old-pipeline native rerun was started on Metashape 2.3.0 build 21778 but exceeded 20 minutes inside native `alignCameras`; it was terminated before producing a PSX. Its logs are not used as correctness evidence.
- The available current medium acceptance proves camera counts and export completeness, not reprojection-error quality. Therefore the final causal ranking is source-grounded and dataset-sensitive, not a claim that every new run must be wrong.
# Workspace evidence: C:\\Users\\Beluga\\Downloads\\test

- The workspace contains `run_summary.json` schema-1 fields (`seconds_per_frame`), `alignment_summary.txt` under the legacy name, and a manifest with one `panorama_video` track. This is legacy/0.1.x-style output, not the current schema-3/0.2.8 summary format; the files alone cannot prove a current-version regression.
- The run imported one OSV, extracted 440 frames / 880 fisheye cameras, and reported 880/880 cameras aligned. It exported 4,400 cubemap images and 465,171 COLMAP points.
- The decisive geometry evidence is `station_baseline_min_max_avg=0.005527333,0.053258617,0.027253915`: the same physical dual-fisheye baseline varies by about 9.6x across Stations. A 100% transform count therefore masked a severe rig-geometry error.
- `ground_alignment_summary.json` reports a well-fitted plane and only 1.21 degrees of pre-correction tilt; this validates the postprocess plane fit, not camera alignment. The bad result is likely already present in the Metashape camera geometry before ground leveling.
- No PSX, Metashape stdout/stderr log, Component inventory, per-camera residuals, or source frame files were included. The evidence identifies the failure class (rig baseline drift) but cannot attribute it to a specific match pair or compare old/new binaries.
# Workspace evidence correction: `C:\\Users\\Beluga\\Downloads\\false`

- `false` is the current schema-3/Backbone output. It contains `xpano_run_summary.json`, `xpano_alignment_summary.txt`, and `xpano_project.json`.
- The input is the same single OSV as the legacy `test` workspace: 440 frames, 880 fisheye cameras, 1 FPS, identical source fingerprint.
- The current alignment summary reports only `436/880` cameras aligned and exports 2,180 cubemap images / 110,048 points (436 cameras x 5 faces). This is a partial alignment, not a complete but lower-quality result.
- `xpano_project.json.jobs` is internally contradictory: the reconstruction job is `state=failed` at `stageId=metashape.pano.match`, while a later `export.images` job is `state=completed` and `reconstruction.status` is `complete`. The application therefore accepted/exported a partially aligned PSX after the native panorama match stage failed.
- This explains the user-visible regression more directly than Station baseline statistics: the new run failed before completing the backbone, then the export path bypassed the failure. The first remediation boundary is job-state propagation and export gating, not automatic camera repair.
- The legacy `test` workspace reports `880/880` and 4,400 cubemap images, but its summary has no job failure record. The two workspaces are now directly comparable: same source/material, old completed alignment versus new failed-at-match partial export.

# Phase 44 Station-retention findings

- Both mixed-material Backbone and explicit Mixed modes removed the panorama shared-center constraint immediately before optimization by converting panorama groups to Folder.
- The correct boundary is per group type: panorama dual-fisheye groups remain Station, while ordinary video/photo/aerial groups remain Folder.
- Retaining Station requires no new match, solve, retry, heuristic, or optimization pass. The existing `metashape.pano.release` stage ID remains for persisted execution-plan compatibility, but its user-visible meaning is now Station-constraint handling.

# Phase 45 release audit

- The authoritative installer version comes from `xpano-ui/src-tauri/Cargo.toml`; `scripts/build_installer.ps1` requires it to match `tauri.conf.json`, passes the value into the staged release manifest, and names the final installer from it.
- npm package metadata and both lockfiles also carry the application version and must be synchronized to avoid a source/artifact identity mismatch.
- `0.2.9-preview` is valid Cargo/npm semantic-version prerelease syntax. The NSIS release path does not coerce it to a four-part Windows MSI version because this build targets NSIS only.
- FFmpeg, ffprobe, pnpm, Cargo, the bundled runtime payloads, offline wheels, and prior installer artifacts are present. A standalone `makensis.exe` lookup is not authoritative because Tauri provisions/invokes its NSIS toolchain.
- The current release delta spans the accumulated post-0.2.3 runtime hardening, UI/workflow fixes, truthful Metashape completion and Component export, single-pass alignment, and Station retention. These changes already have focused/full static coverage; the release pipeline will repeat its own gates against the versioned source.
- Release review found one missing staging assertion for `scripts/component_selection.py`, a direct dependency of the production Metashape/export paths. A RED test reproduced the gap; the required-resource allowlist now rejects staging when that module is absent.
- The authoritative build produced a 728,693,656-byte NSIS installer with both Windows `ProductVersion` and `FileVersion` set to `0.2.9-preview`.
- The final staged manifest identifies `0.2.9-preview`, contains 2,201 files, includes every newly required Metashape/component/runtime resource, and passed full size plus SHA-256 verification for every entry.
- Final installer SHA-256 is `3c8f1719a604d9f3878bf583474e62dab685a998023c7a6fe67bcbc8865a27f7`; the generated sidecar matches exactly.
- The release remains intentionally unsigned. Tauri's `.app` identifier warning is macOS-specific and does not affect this Windows-only NSIS artifact; the Node `url.parse()` warning comes from the package-manager toolchain rather than shipped application code.

# Phase 46 mixed-photo import incident

- The user screenshot matches `0.2.9-preview` source line 796 (`run_backbone_alignment`) and line 859 (`main`) exactly, confirming the report is from the new package rather than an older binary.
- The execution plan fails at `metashape.frame.import` after panorama import succeeds and before Station setup or matching. The incident is therefore in flat-camera import/sensor normalization, not matching or Station retention.
- The screenshot omits the innermost traceback line, but the newly added incompatible-geometry rejection is the only new fail-fast boundary immediately after the shown successful `AddPhotos` operations.
- Manifest grouping uses raw file dimensions and EXIF camera identity, while Metashape may expose different effective sensor geometry after interpreting image orientation or metadata. Rejecting the whole job is unnecessary because a semantically equivalent recovery exists: partition by Metashape's actual source-sensor geometry and retain a separate Frame calibration sensor per partition.
- The two supplied photos confirm the UI fails specifically at `metashape.frame.import`: panorama import is complete, ordinary-photo import turns red, and Station setup plus matching remain pending. The visible traceback enters `run_backbone_alignment` immediately after the final ordinary-photo `AddPhotos` calls.
- The recovery remains inside each manifest-declared camera/lens identity group. It does not merge unrelated lenses, create one sensor per photo, rotate source media, or alter matching and alignment semantics.
- Five-axis review found no blocking correctness, simplicity, architecture, security, or performance issue. The import pass is linear in the number of newly imported cameras, retains at most one list entry per camera, and caps the geometry preview in its single diagnostic.
- The existing `0.2.9-preview` installer was built before this recovery and is therefore stale. Source acceptance does not make that artifact suitable for distribution.

# Phase 47 release audit

- The requested version `0.2.9-preview-7142057camerafix` is a valid SemVer prerelease: the complete prerelease identifier is `preview-7142057camerafix`, and hyphens are allowed inside it.
- The standard installer boundary is unchanged from Phase 45. This build embeds the application, Metashape support payload, COLMAP, FFmpeg and LichtFeld resources, but does not add the optional multi-gigabyte full-offline densification payload.
- The authoritative build script derives the output name and staging manifest version from Cargo metadata after requiring an exact Tauri-version match, then writes a SHA-256 sidecar.
- The authoritative build completed in 742 seconds and produced a 728,670,865-byte installer. Both Windows `ProductVersion` and `FileVersion` are `0.2.9-preview-7142057camerafix`.
- The release manifest identifies the exact version and all 2,201 entries passed independent existence, size and SHA-256 verification. The staged `metashape_pipeline.py` exactly matches source SHA-256 `b0325d1c7b81a7924b234c3007c19d06fa546ed330f29a2a53b592995c47b0d9` and contains the Camera geometry partition.
- Final installer SHA-256 is `b8b5441ed5f243754f85847852c7edb664066d7c9db3de570d46f399443db92b`; the sidecar matches exactly.
- Five-axis release review found no blocker: no new dependency or privilege surface was introduced, the fix remains linear in imported cameras, and the existing staging/DLL-closure architecture was reused. The package remains intentionally unsigned, and exact user-material native Metashape acceptance remains outside the available evidence.

# Phase 48 repeated import failure evidence

- The new package is definitely running the Phase 46 code because the task log contains `Splitting photo sensor group by imported geometry`.
- The failing declared group is split into `(Metashape.Sensor.Type.Fisheye, 3840, 3840)` and `(Metashape.Sensor.Type.Frame, 3840, 3840)`. This is a source projection-type conflict, not the landscape/portrait dimension mismatch represented by the Phase 46 regression.
- The UI still fails before `metashape.pano.station` and `metashape.all.match`, so matching quality, Station retention and Component export are not involved in this incident.
- The installed traceback line numbers exactly match current source: line 803 is the call to `run_backbone_alignment` and line 866 is `main()`. The innermost exception and line remain outside the screenshot, so the exact throwing statement is not yet visible.
- Backbone imports panorama tracks first, prunes only unused sensors, then imports all Frame-track types into the same fresh chunk. Used xPano panorama Fisheye sensors therefore remain available when Metashape imports later 3840x3840 ordinary frames.
- Phase 46 grouped later cameras by their current `camera.sensor.type`, but that value can describe a sensor Metashape reused from the already-mutated chunk. It is not necessarily an intrinsic property read from the source JPEG.
- Phase 46 then unconditionally asks `make_track_sensor` to create a Frame sensor for every partition, including a partition whose source sensor is Fisheye. This contradicts the earlier interpretation that each partition represented a compatible Frame calibration group.
- `track_004_..._frame` is conclusively an ordinary-video sensor label: `build_ordinary_video_track` creates exactly that suffix, puts every extracted frame in one declared sensor group, and supplies a Frame camera profile.
- Ordinary-video extraction writes every frame with the same synthetic EXIF Make `xPano` and Model `<track_id>_frame`. Therefore the source-type split is not explained by mixed physical cameras or different declared photo identities inside that track.
- The exact `E:\20260702LGGY\X5\xPano` workspace and original task log are unavailable locally. The screenshot still crops the innermost traceback line, so the final throwing assignment/API call cannot yet be named with certainty.
- Panorama extraction writes distinct Make/Model identities (`DJI`/`Insta360`, `<track>_left`, `<track>_right`), while ordinary-video extraction writes `xPano`, `<track>_frame`. The manifest itself therefore does not intentionally ask Metashape to share those sensors.
- The Phase 46 fake regression cannot reproduce this incident: every fake imported camera gets a brand-new sensor whose type defaults to `None`; the test varies only width/height. Its later Fisheye validation test bypasses `import_photo_track` entirely. Passing 280 tests therefore never exercised a same-size Fisheye/Frame source partition or Metashape sensor reuse.
- Official 2.2.2 and 2.3.0 API/manual text snapshots are available under `tmp/pdfs` for checking the native camera/sensor contract.
- Official `Chunk.addPhotos` defaults to `layout=UndefinedLayout`, `load_xmp_calibration=True`, and `load_xmp_orientation=True`. xPano overrides only `load_xmp_accuracy`, leaving Metashape in control of native calibration-group assignment during each import.
- The local Metashape 2.2.1 build 20221 runner is available at `E:\FastProgram\Metashape\metashape.exe`; its real runner runtime probe passes with the retained cp39 site-packages. This permits an isolated native import experiment without altering product code.
- A native minimal reproduction using uniform synthetic EXIF and same-size panorama/ordinary frames produced the user's exact diagnostic split and then failed at `validate_backbone_camera_sets` with `Panorama and flat camera sets overlap or contain duplicate camera keys`.
- The reproduction proves the actual root defect: `add_photos_get_new` snapshots only `len(chunk.cameras)` and returns `list(chunk.cameras)[before:]`. Metashape reorders `chunk.cameras` during `addPhotos`, so this slice can contain old panorama cameras and omit newly added ordinary frames.
- The wrong old cameras are then partitioned and reassigned to newly created Frame sensors. That mutation explains why the diagnostic contains a Fisheye partition and why formerly panorama cameras appear under the ordinary track's sensor label.
- A second positional assumption compounds the error: `_new_cameras_since` also slices `chunk.cameras` by the old length when building per-track camera sets. The resulting `frame_cameras` contains keys already present in `pano_cameras`, and the safety validator correctly stops the job before matching.
- The same native probe showed that the bug can already leave a later panorama image on a Frame sensor during repeated pair imports. Panorama-only success is data/order-dependent, not proof that positional slicing is valid.
- The enhanced native trace records the exact reorder. Before the second panorama pair, camera order is `[0, 1]`; after `addPhotos` it is `[0, 2, 1, 3]`. The production slice from the old count selects keys `[1, 3]`, while the key-set difference correctly selects `[2, 3]`.
- The ordinary-frame import makes the defect deterministic in the minimal case: after adding frame keys `[4, 5, 6, 7]`, Metashape orders them before panorama keys `[0, 2, 1, 3]`. `list(chunk.cameras)[4:]` therefore returns all four old panorama cameras and none of the newly imported ordinary frames.
- With production behavior preserved, Phase 46 partitions those four wrongly selected panorama cameras into Fisheye/Frame groups and reassigns them to ordinary Frame sensors. The actual ordinary frames remain correctly imported but are omitted from `new_cameras`.
- A second native run temporarily returned the correct key-difference selection only from `add_photos_get_new`. Sensor assignment then remained correct, but `_new_cameras_since(chunk, start_index)` independently selected the four old panorama cameras for `frame_entries`. Validation still raised the same overlap exception. Both positional assumptions must therefore be removed together.
- A repository-wide Python search found exactly two production camera-import position slices: `add_photos_get_new` and `_new_cameras_since`, both in `metashape_pipeline.py`. Other `len(chunk.cameras)` uses are counts/metrics, not identity selection.
- The previous Camera fix addressed the symptom, not the cause: it treated the unexpected Fisheye/Frame split as legitimate source geometry and split it into new Frame sensors. In reality, the Fisheye members were old panorama cameras accidentally included by position.
- Correct repair boundary: snapshot camera keys before every `addPhotos`, select new cameras by key-set difference, verify returned keys/paths/count against the request, propagate the returned camera objects through each track import, and remove `_new_cameras_since`. Keep overlap/coverage/type validation because it prevented wrong matching rather than causing the failure.
- The two new screenshots add no contradictory evidence: they show Phase 46's geometry diagnostic and the outer traceback at current lines 866/803, while the native minimal reproduction supplies the cropped inner exception exactly: `Panorama and flat camera sets overlap or contain duplicate camera keys`.

# Phase 49 stable camera identity repair

- One import boundary now owns camera identity: it snapshots existing camera keys, calls native `addPhotos`, and selects only keys absent from the snapshot. Native list order is no longer part of the contract.
- The same boundary validates both imported count and normalized source-photo paths. A partial or substituted native import fails visibly before sensor mutation or matching.
- Panorama and flat-track import functions return the exact camera objects they imported. `import_manifest_tracks_by_type` no longer re-discovers cameras from a second chunk-list slice, so the duplicate positional assumption has been deleted rather than patched.
- A reordering fake that moves every new batch before all existing cameras reproduces the original overlap error on the old code and passes after the repair. It verifies mixed panorama/photo identity and sensor projection types by source path.
- The real Metashape 2.2.1 build 20221 minimal mixed-material probe now passes. It reports four correct panorama keys on two Fisheye sensors and four correct ordinary-frame keys on one Frame sensor, with no overlap or missing cameras.
- The implementation adds no dependency, cache or persistent state. Import selection and validation are linear apart from sorting path lists for an order-independent comparison; matching and alignment cost remains unchanged.

# Phase 50 camera identity release audit

- The standard installer pipeline produced `xPano-0.2.9-preview-cameraidentityfix-windows-x64-setup.exe` at 728,709,031 bytes. Its independently recomputed SHA-256 is `981e94cb384b4da8400bbc5222333f985bbd4a317c06995afdd73d44afc26035`, identical to the generated sidecar.
- Both PE version fields and the staged manifest identify the exact release `0.2.9-preview-cameraidentityfix`.
- Every one of the 2,201 declared staged files passed independent existence, size and SHA-256 verification. The staged Metashape pipeline is byte-identical to source and contains the key-based import contract shipped by this release.
- Five-axis review found no blocker: the import boundary fails before sensor mutation when native results are incomplete or substituted, direct Camera-object propagation removes the second positional lookup, and matching/alignment/export behavior remains unchanged.
- The fix adds no dependency, privilege, persistent state or shell boundary. Its set-difference and path-sort work is bounded by the imported camera batch and negligible beside native image import.
- The package is intentionally unsigned. The Node `url.parse()` deprecation and Tauri `.app` identifier messages observed during packaging are toolchain/macOS warnings and do not invalidate this Windows NSIS artifact.

# Phase 51 LichtFeld workspace UI audit

- The redesign is for an operational desktop workspace, not a marketing page. Its primary jobs are choosing a training profile, adjusting only necessary parameters, starting/stopping training, monitoring real progress, and opening the produced artifact.
- Existing training behavior already exposes persisted configuration and structured progress metrics; the UI problem should be solved by reorganizing this state rather than introducing a second task model.
- Developer explanations must move out of the default visual path. Short user-facing validation or recovery messages remain necessary, while implementation/runtime details belong in contextual help or a collapsible diagnostics surface.
- `TrainingWorkspace.tsx` currently renders two competing full-height bordered panels. The left panel contains readiness, presets, basic fields and nested advanced cards; the right panel contains state, progress, four metric cards, a permanently visible terminal and the primary action. Because both halves use the same visual weight, there is no dominant workflow.
- The page heavily nests card-like surfaces: three readiness cards, three preset cards, control fields, an advanced card, a progress card, four metric cards and a terminal inside two outer cards. This creates the fragmented partitioning the user reported.
- Core text is undersized for a desktop production tool: several labels and explanations are 8-10 px, and uppercase English eyebrows add hierarchy noise without helping Chinese users complete the task.
- Developer-facing copy appears in the primary path: LFS version/ownership details, raw runtime/dataset paths, GUI implementation language, output-directory behavior and a permanently visible raw log terminal.
- The start action is physically separated from the configuration it commits. A disabled start button has no nearby user-facing reason, while readiness problems are represented only by three small technical cards near the top.
- All configuration controls remain editable while training is running. Even if backend snapshots the submitted config, the screen can visually imply that changing controls affects the active run.
- Preset selection is local state initialized to `balanced`; loading a saved or custom config does not derive the matching preset, so the highlighted preset can disagree with actual values. The redesigned interaction needs an explicit `自定义` state.
- The fixed two-column minimums require roughly 836 px before the containing application shell is considered and have no explicit responsive collapse. This is fragile at the narrower desktop widths already supported by xPano.
- The monitor shows empty metric boxes, an empty terminal and an output placeholder before training starts. The idle state therefore looks like a failed dashboard rather than a clear next action.
- The enclosing AppShell reserves a single title bar and bottom workspace/job dock and enforces a 1024x720 minimum window. The training page should therefore behave as a dense inner workspace, not add another hero-style product header or duplicate global environment status.
- Global runtime readiness already lives in the title bar. Repeating three technical readiness cards inside training duplicates chrome; the page only needs a compact training-input gate and actionable recovery when something is missing.
- xPano already defines coherent brand, semantic, surface, border, motion and light/dark tokens. The redesign should reuse those tokens and Lucide rather than introduce a new LFS-specific palette, gradients or icon system.
- Browser tooling is available (`npx` 11.8, Node 24.13). A live browser inspection still requires a project fixture because the training component intentionally renders only a project-required empty state without Tauri project context.
- Existing 1024x720 and 1280x800 acceptance screenshots visually confirm the diagnosis. At 1024x720 the parameter panel becomes a clipped scroll region while the idle log consumes most of the right half; at 1280x800 the page still reads as two large empty containers rather than one training workflow.
- The screenshots show weak contrast between section boundaries, repeated pale rectangles, and excessive empty monitor space in the idle state. The black terminal becomes the strongest object on the page even though it is diagnostic rather than primary.
- The title bar and bottom dock already communicate project, environment and global task state. Internal English eyebrows (`GAUSSIAN TRAINING`, `TRAINING MONITOR`) and the raw `idle` badge duplicate status without adding user meaning.
- Backend state supports the required product states: idle, running, complete, failed and interrupted; it persists submitted config, output path, artifact path, iteration, loss, splat count and error. The redesign can be state-driven without backend expansion.
- The existing `open_output_folder` command can support a completed-state `打开结果目录` action. No new shell behavior is required for that UI affordance.
- Readiness is a three-part gate (runtime, COLMAP dataset, active geometry). In the default path it should collapse to one concise readiness row; only missing parts need individual recovery text.
- Existing UI specifications explicitly limit a workspace to three primary panels, prefer dividers over nested cards, require one visual primary action and route parameter explanations through contextual help. The current training page diverges from all four rules.
- The recommended solution is a state-adaptive workspace rather than a fixed dashboard: setup is dominant before a run, live progress during a run, and artifact actions after completion.
- No backend protocol expansion is necessary for the redesign. Existing state and `open_output_folder` cover the intended UI; missing embedded Gaussian preview remains outside this UI-only scope.
- The complete design, state matrix, wireframes, responsive rules, component boundaries and acceptance gates are recorded in `docs/LFS_TRAINING_WORKSPACE_UI_REDESIGN_PLAN.md`.

# Phase 52 LFS UI implementation findings

- The current test boundary already covers training defaults, preset application, readiness and progress isolation; new view-model behaviors can be proven as small pure tests before React restructuring.
- `TrainingStatus` includes `idle`, `ready`, `running`, `complete`, `stale`, `failed` and `interrupted`. The view model must map idle/ready/stale to setup, live or persisted running to running, and preserve the three terminal states separately.
- The current browser preview fixture supplies an idle training project, while `usePipeline` only supports an alignment-running preview. Deterministic training preview query modes are needed for running and terminal-state visual acceptance, but must remain guarded by `import.meta.env.DEV`.
- RED evidence is established: `trainingConfig.test.ts` fails at module instantiation on the missing `deriveTrainingPreset` export before implementation.
- The refactor can remain within three concrete component files: `TrainingWorkspace` owns state/commands, `TrainingSetupView` owns editable configuration, and `TrainingTaskView` owns running/terminal states plus diagnostics. No generic card abstraction is required.
- Persisted project config is the authoritative read-only summary during a run; the editable draft is only rendered in setup mode. This removes the previous implication that changing controls mutates an active run.
- Visual acceptance fixtures are isolated behind `import.meta.env.DEV` and query parameters, allowing exact state screenshots without weakening Tauri readiness or training commands.
- Final review verdict is approve. Correctness is covered by 47 frontend tests and production build; readability is improved through setup/task/orchestrator boundaries; architecture reuses existing project/job contracts; security adds no untrusted execution path; performance keeps logs bounded and introduces no heavy rendering or dependency.
- The accepted 1024x720 layout keeps the start action fixed and reachable while only the configuration column scrolls. The 1280x800 layout preserves the same hierarchy without expanding into empty monitoring space.

# Phase 53 installed LichtFeld runtime diagnosis

- Preserved screenshot signature: installed `LichtFeld-Studio.exe` resolves its executable directory as `E:\FastProgram\xPano\runtime\lichtfeld-studio\bin` and repeatedly cannot find `share\LichtFeld-Studio\assets\rmlui\rendering.rml`; its remaining fallback paths point at LichtFeld's CI/build source tree and cannot be valid on an end-user machine.
- Because the LichtFeld process reaches RmlUI initialization, this is not presently a missing-DLL or process-launch failure. The open question is whether xPano omitted/misplaced the asset tree or launches a correctly packaged runtime through a path form that LFS cannot resolve.
- The missing-file hypothesis is disproved: `rendering.rml` exists at the exact installed path shown in the error, with length 39,100 bytes. The repository runtime, release stage, Tauri release bundle and original `D:\FastPrograms\LichtFeld-Studio-windows-v0.5.3` all contain the same relative path and length.
- The installed LFS root has the expected `bin`, `DLLs`, `extensions`, `Lib` and `share` siblings. The failure is therefore in runtime path resolution/access, not gross installer omission or a flattened LFS directory tree.
- The screenshot specifically reports the executable directory with a Windows extended-length prefix (`\\?\E:\...`), while the on-disk asset exists under the corresponding normal drive path. This prefix difference is now the leading causal hypothesis and must be tied to xPano's launch code or LFS's own executable-path normalization before a fix is chosen.
- SHA-256 of installed, repository, release-stage and original `rendering.rml` is identical: `5E79FF017B5FAE3F0B42FAD4DAFB935D0C8EC1AA3B418874054B2D64C3ACCA80`.
- Each `share` tree contains exactly 302 files totaling 40,026,080 bytes. PowerShell can read the installed asset through both the normal `E:\...` path and the `\\?\E:\...` path, so filesystem ACLs, file corruption and generic Windows long-path support are ruled out. Any prefix failure must be inside LFS's own path-to-string/resource-search logic or in the exact process context.
- Native reproduction is conclusive. Launching the installed `LichtFeld-Studio.exe` for eight seconds with a normal path loads themes from `E:\FastProgram\xPano\runtime\lichtfeld-studio\share\...` with no resource error. Launching the same byte-identical executable with an extended path reports `Locale file not found: \\?\E:\.../locales/en.json` and `Cannot find asset: icon/color-picker.png`, although both files exist.
- A MinGW C++ probe matches the failure exactly: `std::filesystem::exists` returns true for the normal path and for an extended path using backslashes, but returns false (without an error code) for the mixed form produced by LFS (`\\?\E:\...\\locales/en.json` and `\\?\E:\...\\assets\\rmlui/rendering.rml`). LFS creates that mixed form because `getAssetPath()` appends slash-bearing asset names and `LocalizationManager` builds `locales_dir + "/" + language + ".json"`.
- The xPano launch chain is the affected boundary: Tauri resolves `runtime/lichtfeld-studio/bin/LichtFeld-Studio.exe` to a `PathBuf`, Python then calls `config.executable.resolve(strict=False)`, and the child inherits the verbatim extended executable path. The source/manual launch uses a normal drive path and therefore does not trigger the LFS/MinGW mixed-separator bug.
- The minimal repair boundary is xPano's Windows child-process launch: convert bundled executable, script and working-directory paths from the `\\?\` form to normal drive/UNC syntax before invoking Python/LFS, while retaining extended paths for user data where needed. Patching the third-party LFS resource code would be broader and would not fix other bundled tools that receive the same path form.

# Phase 66 README research

- The README must describe the product as an xPano project workflow, not as a standalone Metashape or LichtFeld wrapper.
- Current source and release evidence confirm that core application, FFmpeg, COLMAP, bundled Python, LFS, and Metashape helper wheels ship with the application; Metashape itself remains an external licensed installation.
- Densification is a separate on-demand runtime. The standard package does not include its large Torch/RoMa payload, so the guide must say that first use requires a network connection and free space instead of claiming offline availability.
- The current root `README.md` is a long, stale technical/release document. It still refers to retired light/full packages and an old one-pass mixed workflow, so it must be replaced rather than incrementally edited.
- Product-facing reference material is concentrated in `GUI_QUICKSTART.md`, `docs/VERIFIED_WORKFLOW.md`, `docs/MULTI_TRACK_BACKEND.md`, `docs/COLMAP_DENSIFICATION.md`, and the current UI/source implementation.
- The normal GUI path is: import materials -> prepare frames/photos -> align and export -> inspect point cloud/results -> optionally densify or train. A finished xPano project retains the Metashape `.psx`, manifest, generated images, COLMAP `sparse/0`, and run summary under the selected output folder.
- Panorama material is processed as original dual-fisheye imagery, not ERP/cubemap during alignment. Mixed projects use a panorama-first incremental Metashape workflow; ordinary photos/videos are added afterward as Frame cameras.
- The old documentation contains developer CLI, test fixture, and release-build instructions. The replacement README should link to the GUI workflow and omit those details.
- Current UI confirms four material categories: panoramic `.osv`/`.insv`, ordinary video, standard photos, and aerial photos. Ordinary video exposes a wide/standard initial-view choice; all imported visual tracks can use a style `.cube` LUT, while the bundled restoration LUT is only for `.osv` panorama material.
- The product has four user workspaces: materials, reconstruction, results/point-cloud management, and Gaussian training. The default route is the materials workspace.
- Densification is explicitly non-destructive: it first loads a candidate preview, then the user may save it as a version. Gaussian training is separately gated by runtime, prepared dataset, and a selected usable point-cloud version.
- Source confirms the user path for manual Metashape correction: open the generated PSX, save edits in Metashape, then use the reconstruction workspace's PSX re-export action. When more than one usable Component exists, xPano asks the user to choose one and defaults to the largest.
- The COLMAP backend is intentionally blocked for mixed material in the current UI. README wording must present Metashape as the supported choice for panorama-plus-photo/video projects and COLMAP as the bundled panorama-only alternative.
- The style-LUT chain is active in the source: restoration is applied first, then the user style LUT. The bundled DJI restoration preset is valid only for `.osv` panorama material.
- Packaging/source configuration sets the supported release boundary to Windows 10/11 x64. The application bundles its base Python, FFmpeg, COLMAP and WebView2; it does not require system Python, FFmpeg, COLMAP, CUDA Toolkit, Git, or administrator rights for the core workflow.
- Metashape itself is intentionally external and licensed by the user. The package has the helper wheels needed by the Metashape script chain; xPano should be documented as automatically checking/configuring this support rather than asking the user to manually install Python packages into Metashape.
- Project design keeps artifacts relative to the selected project root and preserves job snapshots/logs under `work/`. The user guide should advise retaining the complete project directory and using the built-in project-open path rather than moving isolated output files.
- An xPano project persists its state in `xpano_project.json`; it also exposes compatible previously generated projects through `xpano_manifest.json`, `xpano_run_summary.json`, `work/xpano_manifest.json`, or `work/xpano.psx`. The standard reopen instruction can therefore be "open or drag the project root folder".
- Source creation currently places a new project directory beside the first material unless it is explicitly created/opened elsewhere. README must tell users to plan a dedicated project/output location before importing a large job.
- Gaussian training defaults to the LichtFeld Studio GUI (`gui: true`) and its normal presets are 10k / 30k / 60k iterations. The README should mention the GUI launch and progress display, not imply that xPano provides an embedded training viewer.

## Phase 66 README verification

- The rewritten README has 124 UTF-8 lines. It contains the required user-facing workflow, input categories, backend boundary, project persistence, LUT, densification, and training guidance.
- All three internal reference links exist. Required terminology and sections were programmatically checked; `git diff --check` passed.
- No application source, package configuration, installer artifact, or untracked runtime payload was changed.
- Windows 10/11 x64 is the supported product boundary. The packaged app includes its basic Python, FFmpeg, COLMAP, LFS, and Metashape helper wheels; it does not include Metashape itself or the large densification runtime.
- Source contracts treat project artifacts as relative paths beneath the chosen project directory, including reconstruction output, training output, and point-cloud variants. The README should instruct users to keep the entire output directory intact and move/copy it as one unit.

# Phase 59 release findings

- The standard `scripts/build_installer.ps1` path produces the dependency-complete release used for `1.0.0-preview`; `-FullOffline` only adds the optional densification payload and is not required for this release request.
- All six authoritative version values now read `2.0.0-preview`: npm package, npm lock top-level, npm lock root package, Cargo manifest, xPano Cargo lock package and Tauri configuration.
- Release staging copies the complete `runtime` tree but explicitly rejects a stage missing `runtime/lichtfeld-studio/bin/LichtFeld-Studio.exe` or `LICENSE`. The current source runtime is incomplete, while `D:/FastPrograms/LichtFeld-Studio-windows-v0.5.3` is the canonical complete payload.
- Runtime restoration must be missing-only from the canonical payload. Existing source files may contain xPano-specific additions or deliberate changes and must not be replaced; staging independently filters `.git`, `__pycache__`, `_downloads`, bytecode and debug-symbol files.
- The source runtime has 235 files and is an exact hash-identical subset of the 1,450-file canonical runtime: zero source-only files and zero common-file hash differences. It lacks 1,215 canonical files, including the executable, license and resource tree.
- The previous valid stage differs from canonical only by 205 generated/excluded files plus its stage-only `XPANO_BUNDLE_INFO.md`; the sampled omissions are `__pycache__`/`.pyc`, matching release filters. This confirms the canonical payload plus current staging filters reproduces the known-good runtime shape.
- Missing-only hydration completed with 1,215 copies and 235 preserved files. A full post-copy SHA-256 comparison reports zero missing or different files, and the restored executable is 25,724,928 bytes.
- The bundled runtime manifest declares five Metashape artifacts: four ABI-specific NumPy wheels (cp39-cp312) and one OpenCV abi3 wheel. All five are absent from the source wheel directory, while `dist/xPano-full-offline` contains exact filename, size and SHA-256 matches for every artifact. Restoring these immutable, manifest-addressed files repairs the offline dependency closure without weakening validation.
- The Windows runtime manifest declares six VC++ 14.44.35211.0 x64 DLLs, and the source `runtime/windows-x64` payload is empty. Both the installed `E:/FastProgram/xPano/runtime/windows-x64` payload and Windows System32 provide exact size/hash matches for all six; the installed xPano runtime is the cleanest package-shaped recovery source.
- After applying the same staging filters, the bundled Python source contains only 49 of the 667 files present in the installed, known-working xPano runtime. All 49 common portable files are hash-identical; 618 files are missing and can be restored without overwriting any source file.
- The app offline-wheel source contains only 2 of the 11 wheels in the installed package. The installed set includes the required `tqdm` wheel plus NumPy cp39-cp312, OpenCV abi3, piexif and Pillow cp39-cp312, so missing-only hydration restores the full offline app repair set rather than merely satisfying one required-file check.

## 2.0.0-preview release acceptance

- The installer is 728,701,363 bytes with ProductVersion/FileVersion `2.0.0-preview` and SHA-256 `5A4A39C7594B68114D7D1D41B92EE4CABE83BF2726D06E7F2444E04A89648C68`; the independently read sidecar matches.
- The staged manifest is `2.0.0-preview`/`windows-x86_64` with 2,201 declared and 2,201 actual files. Independent existence, size and SHA-256 verification found zero failures.
- Six critical Metashape/Component scripts in stage are byte-identical to source. The staged LFS payload has 1,245 portable files totaling 570,680,012 bytes, all ten sampled runtime-closure resources exist, and no cache/debug/forbidden payload entered stage.
- Staged Python imports OpenCV, NumPy, Pillow, piexif and tqdm successfully; staged Windows and bundled-runtime manifest validators also pass. The installer is Authenticode `NotSigned`, so Windows may show an unknown-publisher prompt.
- Five-axis review found no release blocker. Correctness is covered by 288 Python, 100 Rust and 50 frontend tests plus full manifest verification; the existing release architecture remains unchanged; restored payloads are immutable/hash-validated; no new security or performance surface was introduced.

# Phase 60 LUT restoration investigation

- The supplied upstream file is 20,514 bytes/476 lines, SHA-256 `06FAA3EFC96578694ADD314B5BB294316D616667D42BDC71F7079D0A601A2CAF`.
- Its “LUT restoration” is a color transform, not a geometric remap: the UI accepts one `.cube` 3D LUT and appends FFmpeg `lut3d=file='...'` after the `fps` filter.
- The same LUT is applied independently to every left/right video stream before JPEG encoding, so stereo/fisheye geometry and dimensions are intentionally unchanged.
- Upstream validates only that the selected path exists and, in drag/drop, that its suffix is `.cube`. It does not parse/validate cube headers or dimensions before processing, expose interpolation/intensity, persist the choice, or distinguish an invalid LUT from a general FFmpeg extraction failure.
- The `-hwaccel cuda` option affects input decoding only; the shown `fps,lut3d` filter chain is not itself a CUDA implementation. Performance and fallback behavior must therefore be evaluated against xPano's current decode/filter pipeline rather than copied verbatim.
- The upstream script parses successfully under Python AST. Its LUT state is process-local GUI state only: browse/drop sets a path, start-time checks existence, and one shared path is passed to every concurrent FFmpeg task.
- xPano currently has no product LUT field or `.cube` handling. The active extractor is `scripts/xpano_extract.py`, which already centralizes FFmpeg command construction, streamed progress, output polling and decoder fallback (`cuda` -> `d3d11va` -> software on Windows).
- `scripts/pano_extractor.py` is a separate older utility and must not be patched as the integration point. Product extraction is invoked through the multi-track job chain, while Rust also owns separate lightweight video-thumbnail commands that should not silently diverge from prepared-media semantics.
- Both panorama and ordinary-video extraction already converge on command factories in `scripts/xpano_extract.py`; their only image filter today is `fps=<rate>`. The hardware fallback rebuilds and retries the full command, so a deterministic LUT filter added at this boundary would automatically survive CUDA/D3D11/software decoder fallback.
- FFmpeg writes the final JPEGs directly into the track workspace; extraction polling and preview callbacks observe those generated files, and the alignment manifest later references them. Applying LUT before JPEG encoding at this boundary therefore keeps prepared preview and Metashape input byte-consistent without a second image-processing pass.
- The durable owner should be per-video `ExtractionSettings`, not a global project flag: xPano already stores trim/FPS/frame-limit per track and supports multiple panorama/ordinary-video sources that may require different camera LUTs.
- Rust compares the complete extraction settings when a track is edited; a LUT field there will naturally mark only that track stale, advance the media revision and invalidate downstream reconstruction. This is the required behavior, unlike camera-profile changes which intentionally preserve extracted pixels.
- The CLI already represents per-track settings as repeated, arity-checked `--pano-*` and `--ordinary-*` options mapped by resolved source path. LUT propagation can extend this existing contract without a second configuration channel.
- The project schema is currently v3. An optional LUT path can remain backward-compatible if Rust/TypeScript/Python all treat omission/null as “no LUT”; a schema bump is unnecessary unless the implementation makes LUT mandatory or changes existing field meaning.
- The bundled release FFmpeg exposes the `lut3d` video filter with slice threading and nearest/trilinear/tetrahedral/pyramid/prism interpolation; its default is tetrahedral. No new native dependency is required.
- A Unicode/special-path feasibility probe exposed an upstream robustness gap before filter validation: `subprocess(..., text=True)` can decode FFmpeg diagnostics with GBK and fail when FFmpeg echoes a UTF-8 path. xPano should explicitly read FFmpeg output as UTF-8 with replacement semantics so the real parser error remains visible.
- The upstream direct-path escaping is not sufficient for the full Windows path domain: a `.cube` path containing Chinese text, spaces, comma, brackets and an apostrophe was mis-decoded/rewritten by FFmpeg and could not be opened. A temporary safe basename (`lut.cube`) with `cwd` set to its directory succeeded, giving a simpler and more reliable integration boundary than expanding ad hoc escaping rules.
- With corrected red-fastest `.cube` ordering, an identity LUT changed only 2 of 12,288 RGB bytes by a maximum of 1 level, confirming `lut3d` is geometrically neutral and essentially color-neutral for an identity transform.
- A synthetic 3840x3840, six-frame JPEG run took 0.371 s without LUT and 0.797 s with default tetrahedral LUT (2.15x for this filter/encode microbenchmark, still 7.53 output fps). The LUT branch produced materially larger JPEGs, so output pixel-format negotiation must be inspected and explicitly stabilized before integration; the raw LUT transform itself does not explain that size increase.
- Pixel-format diagnosis confirmed the upstream filter alone changes MJPEG output from existing `yuvj420p` to `yuvj444p`, increasing a 384x384 test JPEG from 13,946 to 21,206 bytes. Appending `format=yuvj420p` after `lut3d` restores the existing output format and near-baseline size (13,759 bytes). The LUT-enabled branch must explicitly end in the existing 4:2:0 JPEG format; the no-LUT branch must remain byte-for-byte command-equivalent to today.
- The actual project media-preparation entrypoint is `scripts/run_xpano_prepare_project.py`, started by Rust `media::start_media_job`. `run_xpano_tracks_job.py` is not the primary GUI preparation path, so the plan must flow LUT from persisted project tracks through this entrypoint rather than only adding legacy CLI flags.
- xPano's active `_run_ffmpeg` already sets `encoding="utf-8", errors="replace"`; the GBK diagnostic failure belongs to the upstream standalone script and does not require a new xPano encoding fix. It does need an optional `cwd` parameter so the filter can reference a controlled ASCII LUT basename.
- `run_xpano_prepare_project.py` is the right propagation boundary because it reads the target track's persisted extraction settings. The shared extractor should own the temporary LUT snapshot so every panorama/ordinary-video caller gets the same path-safe behavior; staging must always copy rather than hardlink so source edits cannot change later frames within one extraction.
- Project media preparation reads extraction settings directly from `xpano_project.json`; no new Tauri command-line argument is required for the primary GUI path. The LUT field must propagate project JSON -> prepare entrypoint -> panorama/ordinary builder -> shared extractor.
- A repeated 3840x3840 JPEG microbenchmark with explicit `yuvj420p` measured 0.649 s/9.25 fps without LUT and 1.079 s/5.56 fps with tetrahedral LUT (1.66x), while total JPEG bytes stayed near baseline. This is a synthetic filter/encode ceiling, not an end-to-end video benchmark, but it establishes that enabled LUT work is material and no-LUT command identity must be preserved.
- Because `fps` precedes `lut3d`, LUT cost scales with selected output frames rather than every decoded source frame. At xPano's common 1 fps setting, the measured single-stream filter throughput leaves useful headroom; dual-eye processing will still be slower and must remain visibly optional.
- Current project-open validation reports missing primary media sources only. The smallest reliable behavior is to validate a chosen LUT on import/update and recheck targeted LUTs synchronously before a media job is marked running; expanding the global validation-report schema is not required for the first implementation.
- Existing Python, Rust and frontend test surfaces already cover extractor commands/fallback, track building, project preparation, media invalidation and pure frontend helpers. The feature can be regression-tested without introducing a new test framework.
- Feasibility is confirmed. The maintainable first implementation is an optional per-video-track `colorLutPath`, propagated through the existing project preparation chain and applied in the shared extractor as `fps -> lut3d(tetrahedral) -> yuvj420p`. The source LUT is copied to a temporary ASCII basename and prevalidated with bundled FFmpeg; invalid LUTs fail visibly and never fall back to ungraded extraction.
- The complete implementation order, file-level changes, regression matrix, runtime acceptance criteria and explicit non-goals are recorded in `docs/LUT_RESTORATION_INTEGRATION_PLAN.md`.

# Phase 61 LUT restoration implementation

- Project schema remains v3. Rust `ExtractionSettings` now deserializes a missing `colorLutPath` as `None` and omits `None` during serialization, so old projects retain their existing JSON shape.
- LUT ownership is per panorama/ordinary-video track. Import/update validates a regular `.cube` file; photo tracks reject LUT state; editing or clearing the LUT uses existing extraction equality and stales only the target track plus downstream reconstruction.
- Media-job preflight rechecks the selected LUT before writing `work/media_job.json` or changing track status, so a moved/deleted LUT cannot leave a false running state.
- The shared extractor copies the selected file to one temporary `lut.cube`, validates that snapshot with FFmpeg, and retains the same working directory through CUDA, D3D11VA and software attempts. Temporary content is removed on success or failure.
- The enabled filter is exactly `fps=<rate>,lut3d=file=lut.cube:interp=tetrahedral,format=yuvj420p`; the no-LUT filter remains exactly `fps=<rate>` with no temporary snapshot or changed working directory.
- Prepared panorama eyes use identical filter graphs. Ordinary-video frames, streamed prepared previews, generated thumbnails and later alignment inputs all derive from the same transformed JPEG files.
- The existing ready-track settings button now opens a real edit state. Both import and edit surfaces provide one compact video-only LUT picker/clear control; cancelling restores persisted values.

# Phase 62 bundled camera LUT presets

- The current upstream reference does not bundle or identify camera-specific LUTs; it accepts one manually selected `.cube` path for all jobs.
- The repository and `C:\Users\Beluga\Downloads` contain no `.cube` or `.3dl` LUT asset available for packaging.
- Existing panorama extension detection is reliable at the family level: `.insv` maps to Insta360 and `.osv` maps to DJI/Osmo. It is not proof of a clip's capture color profile, so it cannot safely auto-enable a Log/Flat restoration LUT.
- The current release path already has the required primitives: `tool_resolver::resolve_resource_path` resolves Tauri resources and portable roots, while `scripts/release_staging.py` copies a staged tree and hashes every release file in `release-manifest.json`.
- The durable design is a stable builtin preset ID resolved at runtime, not a path under an installation-specific Tauri resource directory. Manual `colorLutPath` remains an explicit advanced override.
- Official source evidence: `https://www.insta360.com/cn/download/i-log` publishes separate I-Log LUT archives for multiple camera models, including ONE X, ONE X2, X3, X5, ONE R and ONE RS. This confirms that `.insv` is not a sufficient key for a single correct builtin LUT.
- DJI's initial direct product-download URL resolved to an official 404 page, so no DJI LUT file or redistribution term was accepted into the project. This failed lookup is logged; it must not be replaced by an unofficial mirror.
- User narrowed the product scope: `.insv` stays manual LUT selection; only `.osv` maps to the DJI Osmo 360 D-Log M -> Rec.709 builtin preset when the user enables restoration.
- Asset retrieval attempts failed independently: DJI product/download paths did not expose a LUT asset, direct GitHub raw/API requests timed out, the configured `127.0.0.1:7897` proxy is unavailable, and a shallow Git clone could not connect. No LUT was added to the repository. The implementation is blocked until the user supplies the approved `.cube` file or a reachable official source.
- Real FFmpeg acceptance succeeded with a Unicode/space/comma/apostrophe source path, two extracted frames and `yuvj420p` output. Full gates passed with 296 Python, 104 Rust and 52 frontend tests plus lint/build/compile/diff checks.

# Phase 55 alignment-quality and Component investigation

- The old `0.1.0` source tree is locally available, so the investigation can compare executable behavior and exact parameter construction rather than infer from release history.
- Alignment-quality diagnosis and Component-selector diagnosis are separate evidence tracks. A selector that only exposes the chosen export Component can hide other Components without itself causing the solver to split; conversely, a multi-Component solve can be real even if the UI inventory is wrong.
- The current default `backbone` workflow is not behaviorally equivalent to `0.1.0`. Old mixed alignment first imports/matches/aligns panorama cameras with `keep_keypoints=True`, then adds flat photos, matches again and aligns incrementally with reset disabled. Current `backbone` imports both classes before one global match, disables flat cameras only after that match, solves the panorama subset, then solves flat cameras from the same global graph. The optional current `mixed` mode also imports everything before a single global match/solve. Neither preserves the old incremental contract documented by Metashape 2.3.
- Disabling flat cameras after global matching cannot undo candidate-pair selection and geometric filtering already influenced by the flat-image population. This is the primary mixed-material regression boundary and explains why the current staging can be worse even though the numeric `matchPhotos` limits look unchanged.
- The official 2.3 manual requires key points to be kept before initial processing and reset alignment to remain unchecked when extra photos are later subaligned. Old `0.1.0` follows that workflow; current `backbone` explicitly uses `keep_keypoints=False` and never performs the documented add-then-incremental-match sequence.
- The pure-panorama path also changed before its first solve. On the same 3840x3840 frame, old initialization produces `Sensor.Type.EquidistantFisheye` with a copied Frame calibration at `f=6275.7163`; current initialization produces legacy `Sensor.Type.Fisheye` with Fisheye calibration at `f=1041.6667`. Metashape 2.3 exposes the enums as distinct even though direct projection and distortion probes give the same numeric equations. The regression boundary is therefore the complete calibration/model bootstrap, not image resolution.
- For panorama-only alignment, `keep_keypoints` only controls descriptor persistence and Station-to-Folder release happens after the initial `alignCameras`; neither can explain Components already created by that first solve. The materially different pre-solve state is the sensor/calibration bootstrap. The exact field within that coupled bootstrap still requires a controlled full-data A/B before changing production semantics.
- Old-good and new-bad summaries for the same named OSV both contain 880 3840x3840 fisheye images and two sensors. Old reports 880/880 in one reconstruction; current reports only the active 458-camera Component. Extraction defaults remain 1 fps with no frame limit, and sampled CUDA/software JPEG decodes are pixel-identical. Resolution reduction, hardware decode and JPEG quality are ruled out as general causes.
- Standard photo imports are staged by hardlink/copy without resizing. Current grouping uses dimensions, make/model, lens and focal EXIF and then partitions unexpected geometry. This is not the general regression. The removed old MPF-JPEG sanitization remains a narrow compatibility risk for multi-picture JPEGs only.
- Ordinary-video frames are a new path absent from old `0.1.0`; current code forces a guessed 70-degree or 105-degree initial horizontal FOV, defaulting to 105 degrees. A wrong user/default profile can degrade that track, but it cannot explain the confirmed single-panorama regression.
- Native Metashape 2.3 inspection of `D:\3DRegistration\test\xPano\work\xpano.psx` finds three real Components with 458, 221 and 177 member cameras plus 24 unassigned cameras. Thus 856/880 cameras are aligned within some Component; xPano's reported 458/880 counts only the active Component and conflates global connectivity with camera alignment.
- Metashape exposes `camera.transform` and the active tie-point cloud only for `chunk.component`. Switching the active Component changes visible transform counts from 458 to 221 to 177 and tie-point counts from 132270 to 94262 to 74148. Current inventory never activates each Component, so inactive Components are serialized as zero aligned and every Component tie-point count is incorrectly zero.
- Component export has the same defect: selecting a key does not assign `chunk.component` before filtering `camera.transform`. An inactive valid Component can therefore export no cameras. The correct boundary is to activate the requested Component, inventory/export it in that context, and restore the original active Component afterward.
- The frontend reads only the persisted `project.reconstruction.config.alignmentReport`; it never inspects the PSX live. Components created, merged or changed manually in Metashape are invisible until xPano regenerates the report. This explains a PSX visibly containing two Components while xPano still displays the older one-Component report.
- The maintainable correction boundaries are: restore a true panorama-first incremental solver contract; separately baseline the old pure-panorama calibration bootstrap before altering it; and centralize active-Component inspection/export behind one helper. Do not patch this with UI-only counts, transform summation without activation, or another post-match enable/disable retry.

# Phase 56 restored alignment contract

- Panorama sensors now copy the calibration imported by Metashape and use `EquidistantFisheye` when the installed API exposes it, reproducing the `0.1.0` bootstrap while retaining a `Fisheye` fallback for older supported builds.
- Runtime order is again panorama import -> Station -> retained-keypoint match -> align -> Folder -> optimize, followed by Frame import -> retained-keypoint match -> non-resetting incremental align -> global optimize.
- The one-pass `mixed` implementation and its execution-plan graph were removed. Existing persisted/CLI `mixed` values remain accepted but normalize to `backbone`, so old projects do not fail and cannot silently re-enter the regressed path.
- Stage events, Rust execution-plan nodes, development previews and active workflow documentation now describe the same native calls. The UI exposes one stable Metashape strategy rather than a second misleading route.
- Component enumeration and component-scoped export remain a separate known defect; this phase intentionally does not alter report or export selection behavior.

# Phase 57 Component planning findings

- `component_selection.component_inventory` assumes `camera.component`/`component_id` and `camera.transform` are simultaneously meaningful for every Component. Native Metashape evidence disproves that assumption: transforms and tie points reflect only `chunk.component`, so inactive Components are reported with zero aligned cameras and zero tie points.
- Both initial alignment reporting and PSX re-export call the same invalid inventory helper without activating each Component. The defect therefore exists before Rust persistence or frontend rendering; a UI-only fix cannot recover the missing counts.
- `export_colmap.run_mixed_export` chooses a key and filters `camera.transform` without first assigning `chunk.component`. Selecting an inactive valid Component can consequently produce no cameras or export the wrong active state.
- Rust correctly persists the report it receives and validates that the selected key exists with a positive aligned count. The frontend correctly renders the persisted list, but it has no command that re-inspects the current PSX; manual Metashape changes remain invisible until a re-export job regenerates the report.
- The repair should centralize temporary Component activation and restoration in the Python Metashape layer. Inventory, selection validation, alignment counts, tie-point counts and export must all use that same active-Component boundary instead of teaching Rust or React Metashape-specific semantics.
- Rust finalization requires the selected key to exist in `components` with `alignedCameraCount > 0`; once Python emits truthful inventory, this validation can remain unchanged and becomes useful corruption protection.
- The current selector is populated only from `project.reconstruction.config.alignmentReport`. A manual PSX edit cannot update it before the user chooses a Component, so a correct flow needs an explicit PSX inspection step separate from export, or a re-export preflight that returns refreshed inventory before committing a selected export.
- Existing re-export publication is transactional: it stages new outputs and rolls back failed publication while preserving the PSX. Component work should reuse this job boundary rather than add direct frontend filesystem inspection.
- Current unit tests model camera membership as globally visible and therefore cannot reproduce Metashape's active-Component behavior. New tests need a fake chunk whose `camera.transform` and `chunk.tie_points` change when `chunk.component` changes, plus restoration assertions on success and failure.
- Initial alignment does not pass a prior Component key, so it can safely auto-select the largest newly discovered Component. PSX re-export does pass the user's selected key and must reject a now-missing key rather than silently export another Component.
- `align_ground_plane.main` reads `chunk.tie_points`, so it is also active-Component-scoped. The selected Component must be activated before auto-level and remain active through COLMAP/image export; fixing only the export camera filter would still orient from the wrong Component.
- Initial alignment saves the PSX before auto-level/export. Temporary Component activation can therefore be restored after export without changing which Component is persisted as active, while exported coordinates remain based on the selected Component.
- The cleanest stale-PSX UX is preflight-on-action: clicking “从 PSX 重新导出” first runs a read-only Metashape inspection, then shows a Component confirmation only when multiple Components exist. Re-export must independently revalidate the key to close the time-of-check/time-of-use gap.
- A read-only async Tauri command is feasible with existing `spawn_blocking`, tool-resolution and hidden-process patterns. It should return inspection data without mutating the project; the successful transactional re-export remains the only operation that replaces outputs and persists the new alignment report.
- The monitor should distinguish “当前已导出的 Component” from “下一次重新导出的目标”. Reusing a stale persisted dropdown as if it described the live PSX is the current conceptual UI bug.
- Release staging copies every `.py` under `scripts`, so a new inspection entrypoint would be included automatically. It should still be added to the required-file validation and staging regression fixture so a partial package fails before release.
- Existing pipeline code already has Windows hidden-process and Metashape runtime argument helpers, but they are private to `pipeline.rs`. The implementation should extract only the minimal shared command configuration needed by the new read-only inspector rather than duplicate environment/console behavior.

# Phase 58 Component implementation findings

- A single `activated_component` context now owns Metashape's mutable active-Component boundary. Inventory activates each native Component, reads transforms and `chunk.tie_points`, and restores the original even when inspection or export raises.
- Schema-v2 inventory counts the global aligned population as a union of camera keys rather than a sum. This preserves the meaning of 856/880 even when one camera can appear in more than one Component.
- Initial leveling and export run while the selected Component is active. Explicit PSX re-export keys are strict, so a Component removed after UI inspection fails before transactional publication rather than silently switching targets.
- The read-only inspector imports no OpenCV or NumPy, never saves the document, writes UTF-8 JSON atomically, and is now a required staged resource.
- Rust validates revision, current PSX, selected executable, schema version, totals, unique keys and usable default before returning live inventory. The external Metashape process runs inside `spawn_blocking`, uses discrete arguments for Unicode/space-bearing paths, hides its console on Windows, and removes its temporary JSON on both success and failure.
- Persisted `alignmentReport` remains the description of the currently published result. Live inspection is transient frontend state and does not overwrite project configuration.
- The monitor now displays the currently exported Component as read-only state. Re-export always inspects the live PSX; one usable Component proceeds directly, while multiple Components open a radio-row confirmation dialog with the largest result preselected.
- Native Metashape 2.2.1 and 2.3.0 inspections both returned the exact known baseline: Components 458/221/177, global aligned 856/880, unaligned 24 and tie points 132270/94262/74148. The PSX descriptor timestamp and SHA-256 remained unchanged after both runs.
- Final five-axis review found no blocker: activation/restoration and strict failure semantics cover correctness; the Python/Rust/React boundaries remain narrow; commands use validated discrete arguments without a shell; inspection is off the UI thread; and inventory work is linear in cameras times the small native Component list.

## 1.0.0-preview release acceptance

- The final installer is `dist/xPano-1.0.0-preview-windows-x64-setup.exe`, 728,650,129 bytes, SHA-256 `F9AA3E252E57232DC1C040C80EAB4CA76804370B5304A10ACE442F5ADAFE0D89`; its sidecar contains the same digest.
- The final release manifest is version `1.0.0-preview` with 2,201 declared files. Independent existence, size and SHA-256 verification reported zero failures.
- The staged production Python entrypoints used by Metashape, runtime readiness, LFS and export paths are byte-identical to their source counterparts for the checked set. No installer-builder process remains active.
- Five-axis release review found no blocker: the fix is localized to path normalization at the bundled-tool launch boundary, preserves extended paths for user data, adds no dependency or privilege surface, and is covered by drive/UNC regressions plus the full source gates. The package remains unsigned because no Authenticode certificate is configured.
- Native reproduction is conclusive. Launching the installed `LichtFeld-Studio.exe` for eight seconds with a normal path loads themes from `E:\FastProgram\xPano\runtime\lichtfeld-studio\share\...` with no resource error. Launching the same byte-identical executable with an extended path reports `Locale file not found: \\?\E:\.../locales/en.json` and `Cannot find asset: icon/color-picker.png`, although both files exist.
- A MinGW C++ probe matches the failure exactly: `std::filesystem::exists` returns true for the normal path and for an extended path using backslashes, but returns false (without an error code) for the mixed form produced by LFS (`\\?\E:\...\\locales/en.json` and `\\?\E:\...\\assets\\rmlui/rendering.rml`). LFS creates that mixed form because `getAssetPath()` appends slash-bearing asset names and `LocalizationManager` builds `locales_dir + "/" + language + ".json"`.
- The xPano launch chain is the affected boundary: Tauri resolves `runtime/lichtfeld-studio/bin/LichtFeld-Studio.exe` to a `PathBuf`, Python then calls `config.executable.resolve(strict=False)`, and the child inherits the verbatim extended executable path. The source/manual launch uses a normal drive path and therefore does not trigger the LFS/MinGW mixed-separator bug.
- The minimal repair boundary is xPano's Windows child-process launch: convert bundled executable, script and working-directory paths from the `\\?\` form to normal drive/UNC syntax before invoking Python/LFS, while retaining extended paths for user data where needed. Patching the third-party LFS resource code would be broader and would not fix other bundled tools that receive the same path form.
# Phase 67 LFS reliability planning findings

- The formal installer currently stages a complete local LFS tree and the present source/stage/installed critical hashes match, so the reliability work must not be framed as one known missing DLL.
- The runtime input is nevertheless an untracked, manually hydrated directory with no LFS-specific immutable artifact manifest; builds are not reproducible from the tracked repository.
- `release_staging.py` checks only the LFS executable and license as required resources. Recursive PE import closure passes for the current tree but cannot validate dynamically loaded DLLs, RML/shader/locale assets, GPU drivers, or Vulkan devices.
- `build_installer.ps1` copies the complete runtime, while the legacy portable `build_release.ps1` does not copy the LFS GUI runtime. The release process therefore has two incompatible assembly contracts.
- General startup readiness runs `LichtFeld-Studio.exe --version`, but training readiness only checks that the executable exists. Neither proves GUI resources, CUDA/Vulkan initialization, or dataset loading.
- Production process resolution can inherit `XPANO_ROOT`, `XPANO_PYTHON`, the host `PATH`, and user-level `~/.lichtfeld/plugins`, creating machine-specific script, Python, DLL, and plugin behavior.
- The training supervisor has an absolute 120-second startup deadline. A healthy large dataset that has not yet reached the dataset-ready marker can be terminated solely for taking longer than two minutes.
- The release manifest is generated but never verified after installation. The unsigned installer and executables leave antivirus quarantine or partial installation indistinguishable from a source packaging defect.
- LFS GUI training directly imports the NVIDIA driver API and Vulkan loader. Driver/hardware incompatibility must be reported separately from bundled-file corruption; `nvcuda.dll` must not be copied from another machine.
- The on-demand densification runtime is a separate versioned Python/Torch chain and should remain separate. Its follow-up gap is CUDA-profile revalidation, not the LFS GUI resource layout.
