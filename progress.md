# Progress Log

## 2026-07-11 点云预览加载与主线程响应优化
- 用户明确要求先诊断和规划，再实施；禁止生成发布包，除非后续明确要求。上一轮安装器构建被新请求中断，进程复核后已无 build_installer/cargo/rustc/makensis 进程。
- 首次停止构建的 PowerShell 过滤条件把当前诊断命令自身也纳入匹配，导致 shell exit -1；随后改为只读进程复核，确认构建已停止，没有重复执行危险终止命令。
- 初步代码定位：同步 Tauri `read_colmap_points` 逐记录读取完整 `points3D.bin`，返回 `Vec<f32>` JSON；前端再复制为两个 `Float32Array`，随后同步执行坐标转换、三轴数组排序/密度统计、颜色增强与主题适配、Three.js BufferGeometry/GPU 上传。

## 2026-07-11 单行标题栏与底部工作流控制坞
- 用户确认方案后，先提交完整基线：`cb9d7d5 feat: complete reconstruction workflow and release runtime`。本地规划文件未纳入产品提交。
- 设计约束：沿用现有深蓝/品牌蓝 token、8px 间距、12–14px 圆角、56px 单行标题栏、约 60px 底部控制坞；工作区导航为主，任务进度限制约 220px，不新增依赖或业务状态。
- 浏览器 RED 快照（1366×768）确认现状仍是标题栏、工程栏、工作区导航、主区、任务栏五层；`EXPLORER AI`、独立工程栏和顶部工作区导航均可见。首次 Playwright `eval` 因 Windows CLI 引号解析失败，改以无歧义 accessibility snapshot 与现有 CSS `grid-template-rows: 40px 40px 44px 1fr 52px` 作为 RED 证据，不重复该失败表达式。
- GREEN：外壳改为 `52px 标题栏 + 主工作区 + 60px 底部控制坞`；工程状态、环境和打开工程均合并进标题栏；三个工作区入口占底栏主要宽度，任务区上限约 440px，进度条实际约 120–220px。
- 浏览器验收覆盖 1024×720、1366×768、1920×1080，浅色/深色、空闲/运行、导航切换和日志抽屉均正常；控制台 0 error/0 warning。
- 前端 23/23、oxlint、TypeScript/Vite production build、`git diff --check` 通过；审查未发现正确性、安全、性能或死代码问题，并删除了遗留 `PipelinePage` 中的 `EXPLORER AI` 文本。

## 2026-07-11 导出执行图进度闪烁
- 已从保留的截图/事件诊断继续，确认 `usePipeline.ts`、`ExecutionGraph.tsx`、`pipeline_core.py` 与重建执行计划中的两个叠加根因。
- Phase 18 已开始；下一步按 RED 流程增加前端部分进度合并和 Metashape 计划内 stageId 回归测试。
- 首轮 Python RED 中重导出测试按预期观察到 `export.cameras`；正常导出测试先因测试 manifest 过度简化触发 schema 校验，已补为最小合法 manifest 后重跑，不把测试夹具错误当产品失败。
- GREEN：抽出纯函数 `pipelineProgress.ts`；同阶段部分事件继承 stage/track/counters/ETA，显式新 stage 清空旧 scope；Python 正常与重导出均改发 `export.images`。前端 23/23、定向 Python 2/2 通过。
- 全量验收通过：Python 171/171、Rust 69/69、前端 23/23、oxlint、TypeScript/Vite production build、`git diff --check` 均成功。
- 正式安装器重建耗时 494.8 秒并成功完成 release Cargo、staging 与 NSIS。新产物 `dist/xPano-0.1.0-windows-x64-setup.exe`，大小 415,115,164 bytes，SHA-256 `1AF59F81B2CA4E826EED8F8BAABCC6F43E16DB1D18CAEBBFD9C15787F1D0CA59`，sidecar 匹配。
- 发布 staging 中 `export.cameras` 为 0 处、`stage="export.images"` 为 3 处，证明安装包已吸收正常导出和重导出修复。
- 最终 staging 搜索第一次因 PowerShell/rg 引号转义形成未闭合正则；改用 `Select-String -SimpleMatch` 完成核验，未重复同一失败命令。

## 2026-07-10 阶段 3/4、真实全流程与安装器
- Phase 10 审计完成：范围、调用图、真实素材、工具/磁盘、阶段 3/4 缺口、发布与环境脚本风险均已写入 findings/task plan；基线 Rust 41、Python 134、前端 11、lint 全绿。
- Phase 11 启动，第一切片为 ExecutionPlan 权威启动与 ALREADY_RUNNING 保护，先写失败回归。
- Phase 11 第一切片 GREEN：active plan 持久化、planId/revision/config 校验、专用 reconstruction 启动命令和 ALREADY_RUNNING 守卫完成。
- 验证：Rust 45/45、前端 13/13、oxlint、TypeScript/Vite build 全部通过。
- 创建新目标的 8 阶段持久计划（Phase 10-17），保持阶段 3/4、真实算法链路、安装器、自举和环境模拟的完整范围。
- 确认规格阶段 4 尚未完成：当前致密化应用仍覆盖 `points3D.bin` 并删除候选，点云版本模型和可逆训练输入缺失。
- 盘点真实素材：139 文件、约 3.887 GiB，包括 3.18 GiB OSV 与约 138 张照片。
- 记录流量约束：禁止真实下载 torch/CUDA/Open3D 等大包，后续以本地假源和下载计划验证自动配置。
- Phase 10 状态：正在审计阶段 3/4 调用图、现有环境工具、真实产物和 Tauri/NSIS 发布链路。
- 已提取规格验收门：阶段 3 覆盖四类输入、动态 ExecutionPlan、heartbeat/indeterminate/失败节点；阶段 4 覆盖 canonical/world 几何、投影不变量、多点云版本和可逆训练输入。
- 发现文档冲突：`COLMAP_DENSIFICATION.md` 仍描述旧覆盖/删除流程；后续以 UI 规格的版本新增模型为准并同步文档。
- 初步打包风险：Tauri 资源范围过宽、bundle target 为 all、构建命令使用 pnpm 而当前工作流使用 npm，需在 Phase 10 逐项证实并收敛。
- 调用图审计发现阶段 3 的 plan 与启动未绑定：UI 生成 ExecutionPlan 后仍走通用 pipeline，尚未使用 planId/revision 权威启动命令。
- 阶段 4 结果页仍直接嵌入旧 ViewerPage，point variants/geometry 命令与模块均缺失。
- 阶段 3 深审计新增缺口：四组合 plan 测试不完整；通用 pipeline 会取消旧任务；环境预检同步不可取消；planId/revision 未绑定启动。
- 阶段 4 深审计确认旧轴翻转数学错误且非原子，致密化仍是覆盖/删除模型；工程 schema 仅有骨架，没有实际 geometry 事务和版本命令。
- 旧真实工程路径已消失，Phase 10 将重新定位或在测试目录创建隔离工程，所有真实验收从当前磁盘状态开始。
- 当前工具基线：Metashape/内置 COLMAP/致密化插件/.venv-densify/RTX 4060 可见，D 盘 255 GiB 可用；测试树无工程产物，将新建隔离工程。
- 发现干净机发布缺口：仓库未包含 FFmpeg，仅当前系统 PATH 可用；致密化 venv 7.636 GiB 且不完整，符合“按需自举、不可随包发布”的改造方向。
- 发布脚本审计确认正式 full 路径默认携带致密化 venv，并允许 SkipTauriBuild；新安装器必须收敛为轻量、可复现、显式资源清单和按需大依赖自举。
- light installer 默认复用旧 Tauri EXE，环境脚本缺结构化事件/测试；Tauri 官方安装器文档已获取，COLMAP 官方格式文档改走官方仓库原文。

## 2026-07-10 Phase 9 硬解与照片渐进预览
- 用户现场出现抽帧 100% 后 `project revision changed from 2 to 4`；定位为最终提交错误使用工程总 revision，而工作区导航会合法增加该值。
- 复核运行态后确认当前 EXE 与资源脚本均已包含 `inputMediaRevision`；本次截图对应的是遗留 result 的恢复路径。进一步定位到前端在后端提交失败事件后冗余调用 `fail_media_job`，会销毁安全恢复所需 marker；现有 legacy 条件又把 media revision 与总 revision 错误等同。下一步先补 `inputRevision=2 / currentRevision=4 / mediaRevision=1` 的 RED 回归，再修复 marker 保留和 legacy 恢复判定。
- 完成抽帧 100% 后提交失败修复：RED 用例稳定复现 `project revision changed from 2 to 4`；legacy 恢复改为校验目标轨道仍为空且处于 running/failed/interrupted，并要求 `mediaRevision <= inputRevision <= currentRevision`。前端 `pipeline:error` 不再破坏性调用 `fail_media_job`，仅同步后端权威结算结果，因此成功进程提交失败时 marker/result 会保留并可重试。
- 验证：Rust 46/46、Node 13/13、Python prepare 9/9、oxlint、TypeScript/Vite build、`git diff --check` 全部通过。代码质量审查未发现需要阻断的正确性、架构、安全或性能问题；未新增依赖和热路径开销。
- Phase 11 durable jobs RED/GREEN：新增取消回归，证明旧 `cancel()` 会过早清空 PID；修复后取消请求保留活动 PID/Job Object，等待 watcher 结算。新增 `job.rs` 深模块，已通过 2 个磁盘事务测试：创建 UUID job、严格递增事件、stage started/progress/completed 顺序、snapshot/events/job.log 持久化、cancelling 先写盘、重载后快照一致。
- Phase 11 durable jobs 集成：重建命令、pipeline readers/heartbeat/watcher、React JobProvider/usePipeline 已接入持久化 job；增加 orphan interrupted 恢复和终态 snapshot 修复 stale project index 的断电窗口保护。当前验证 Rust 51/51、Node 15/15、oxlint、Vite build 通过。
- Phase 11 cancellable preflight：PowerShell 环境检查在同一 job 下登记 PID/Job Object，`input.validate` 每秒写 heartbeat；取消请求等待预检进程退出后落 cancelled/interrupted。新增断电索引修复和 preflight state 测试后 Rust 53/53；真实 `-CheckOnly` 环境探针 2.5 秒通过，无网络下载。
- Phase 11 stage protocol/UI：补齐 skipped durable events 与 Metashape export stageId；重建命令异步化。验证 Rust 54/54、Metashape 6/6、Node 15/15、lint/build 通过。Playwright Edge 完成 1024/1366/1920 截图，1366/1920 三栏完整、1024 响应式降级、无横向溢出和控制台告警。
- Phase 11 完成：新增用户级 stage timing profile，按 backend/stage/input-size/pixel-scale/GPU 桶保留 21 个样本并取滚动中位数；首次无历史显示“估算中”，后续 plan 注入 estimatedSeconds。最终门：Rust 56/56、Python 135/135、Node 15/15、lint、Vite build、git diff check 全通过。Phase 12 开始。
- RED：新增非素材 revision 变化回归测试，旧实现按预期在 4→6 冲突处失败。
- GREEN：marker/result 记录 media revision，最终提交校验目标轨道与 media revision；新增旧 marker 丢失后的严格恢复路径和真实素材变更拒绝测试。
- 定向验收：Rust finalize 4/4、Python result revision 测试通过；真实失败工程仍有 167/138 项完整结果，可由新版本启动恢复，无需重新抽帧。
- 最终回归：Rust 41/41、Python 134/134、前端 11/11、oxlint、TypeScript/Vite build、`git diff --check` 全部通过。
- 照片预览验收确认 24→48→120/120 渐进追加；单图 `requested` 只在 source 变化时重置，前缀切片与单调 visibleCount 保证已加载节点不卸载。
- 已关闭 Phase 9 Edge 验收会话、停止临时 Vite 服务并删除临时预览入口。
- 根据用户确认启动 CUDA → D3D11VA → 软件回退，以及不限总数的视口渐进照片预览。
- 复用既有性能基线，不引入新前端依赖或新的视觉体系。
- RED：Python 因缺少硬解候选/回退函数导入失败；Node 因缺少渐进预览批次模块失败；Rust 因 `scan_photo_paths` 仍要求 sample_limit 编译失败。
- GREEN 定向测试通过后首次基准失败，经 2 秒最小诊断确认旧 OSV 路径已不存在，并非硬解回退缺陷；已找到当前可用 OSV 继续验收。
- 真实自动抽帧验收通过：CUDA 15.154 秒完成 30.77 秒素材、31 对/62 张 JPEG；3 秒 CUDA/软件 JPEG 哈希完全一致。
- 审查后补充非解码错误不回退的 RED 测试，并实现缺文件/权限/磁盘/输入损坏快速失败。
- 浏览器验收默认 Chrome 命中已知 code 13，按历史解决方案改用 Edge 通道。
- Playwright DOM 计数命令首次因 PowerShell 双引号拆参失败；已记录 ERR-20260710-015，并改用单引号函数参数继续。

## 2026-07-10 成果工作区续作
- 恢复文件计划并与 `docs/UI_WORKSPACE_REDESIGN_SPEC.md` 对照。
- 确认成果与后处理阶段尚未纳入已完成实现，启动 Phase 8 修复对齐到成果展示的闭环。
- 检查真实工程并确认对齐二进制模型已生成；故障不是算法输出为空，而是成功结果未提交到 `xpano_project.json`。
- RED：新增 reconstruction 成功提交与缺失模型拒绝测试；现有代码按预期因缺少 `finalize_reconstruction_job_impl` 编译失败。
- GREEN：实现 reconstruction begin/complete/fail 生命周期、完整 sparse 模型校验、工程原子提交、project update 事件和受控自动跳转；Rust 定向测试 7/7、前端单测 9/9、Vite 构建通过。
- 对真实工程执行 manifest 与产物校验后原子恢复：status=complete、inputRevision=2、alignment revision=1、activeWorkspace=results、colmapPath='.'；保留恢复前 JSON 备份。
- REVIEW：修正事件发送与持久化事务耦合，增加 COLMAP 二进制记录数校验和 reconstruction 完成事件幂等同步；零点模型测试由 RED 转 GREEN。
- 最终验收：Rust 38/38、前端单测 9/9、Python 130/130、oxlint、TypeScript/Vite build、`git diff --check` 全部通过；真实模型为 10 个相机、310 张图像、38,626 个点。

## Session: 2026-07-10

### Phase 1: 基线、架构与故障定位
- **Status:** complete
- **Started:** 2026-07-10 19:27 +08:00
- Actions taken:
  - 确认并复用现有 active goal。
  - 读取文件化计划、系统调试、TDD、性能优化、代码审查和错误复盘技能。
  - 运行会话恢复检查，确认无未同步计划上下文。
  - 检查 git 状态并确认工作树含大量用户改动。
  - 枚举前端、Tauri、Python 与测试文件，定位新旧 UI 架构并搜索导入/预览/抽帧相关符号。
  - 确认默认路由根因，并梳理 ProjectProvider、MediaWorkspace、照片预览和素材网格的数据流。
  - 构造 Windows 无窗口管道复现；完整环境下未复现退出码 120，但确认媒体脚本缺少 UTF-8 配置。
  - 建立实时素材项旧算法微基准：20,000 项需 1,586.3ms（不含 React 更新）。
  - 审查长视频时间轴与 Tauri 缩略图生成：最多 40 帧、单批次、支持取消，确认当前实现已有界。
- Files created/modified:
  - `task_plan.md`（创建）
  - `findings.md`（创建）
  - `progress.md`（创建）
  - `.learnings/ERRORS.md`（记录目标工具错误）

### Phase 2: 方案设计与回归测试
- **Status:** complete
- Actions taken:
  - 选择单次有界照片扫描、复用导入预览、父子进程 UTF-8、批量有界实时缓存方案。
  - 新增 Python、Rust、Node 回归测试并确认均在实现前失败。
- Files created/modified:
  - `tests/test_prepare_project.py`
  - `xpano-ui/tests/pipelineBuffers.test.ts`
  - `xpano-ui/src-tauri/src/lib.rs`
  - `xpano-ui/src-tauri/src/pipeline.rs`
  - `xpano-ui/package.json`

### Phase 3: 实现
- **Status:** complete
- Actions taken:
  - 默认通配路由改为素材工作区，并抽出可测试常量。
  - 照片扫描改为单次精确计数 + 有界预览样本，导入分析直接返回预览路径。
  - 大目录扫描通过 Tauri `spawn_blocking` 执行。
  - Tauri/Python 两端统一 UTF-8 stdout/stderr 配置。
  - 实时素材项改为 80ms 批量、每轨最多 240 项；日志上限 500 行。
  - 素材汇总计算使用 memo，分页后端移除额外全量引用 Vec。
- Files created/modified:
  - `xpano-ui/src/app/routes.ts`
  - `xpano-ui/src/lib/pipelineBuffers.ts`
  - `xpano-ui/src/App.tsx`
  - `xpano-ui/src/hooks/usePipeline.ts`
  - `xpano-ui/src/features/media/*`
  - `xpano-ui/src-tauri/src/lib.rs`
  - `xpano-ui/src-tauri/src/media.rs`
  - `xpano-ui/src-tauri/src/pipeline.rs`
  - `scripts/run_xpano_prepare_project.py`

### Phase 4: 验证与性能验收
- **Status:** complete
- Actions taken:
  - Python 全量 130/130、Rust 32/32、Node 3/3 通过。
  - 前端 build/lint、Tauri binary check、git diff check 通过。
  - 真实无窗口媒体准备子进程退出码 0，生成结果并发出完成事件。
  - 20,000 实时 items 合并从 1,586.3ms 降至 10.9ms；100,000 最终 items JSON 解析 27.9ms。
- Files created/modified:
  - `tests/test_prepare_project.py`
  - `xpano-ui/tests/pipelineBuffers.test.ts`

### Phase 5: 最终审查与交付
- **Status:** complete
- Actions taken:
  - 按正确性、可读性、架构、安全、性能完成复审，无必须修复项。
  - 记录 Playwright/Chrome code 13 的视觉验收环境限制与既有 Rust warnings。
- Files created/modified:
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 6: 导入确认按钮无响应回归
- **Status:** in_progress
- **Started:** 2026-07-10 20:45 +08:00
- Actions taken:
  - 根据用户截图确认分析、预览、有效性判断和按钮启用均正常。
  - 将定位范围收窄到前端确认回调、工程创建和提交导入 IPC。
  - 读取确认回调、ProjectProvider 与 Rust create_project 实现，发现 busy 未接线且具体 IPC 错误被通用 false 隐藏。
  - 精确确认照片目录下已有 revision 4 的 xPano 工程；当前确认流程因重复 create_project 被 `project_exists` 拒绝。
  - 用户补充同一工作流还有两个断点：准备完成后对齐页仍未就位、素材页缺少下一步引导。
- Files created/modified:
  - `task_plan.md`
  - `findings.md`
  - `progress.md`


## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 会话恢复 | session-catchup.py | 获取未同步上下文或空结果 | 空结果，无需恢复 | 通过 |
| Python 媒体准备基线 | `python -m unittest tests.test_prepare_project -v` | 现有测试通过 | 8/8 通过 | 通过 |
| 前端构建基线 | `npm run build` | TypeScript/Vite 构建成功 | 成功，主应用 78.30 kB gzip | 通过 |
| Rust 基线 | 默认 target 的 cargo test | 测试启动 | `libresource.a` 被运行中进程占用 | 改用隔离 target |
| Python RED | 新增 stdout UTF-8 测试 | 修复前失败 | 缺少 `sys`/`configure_console_output` | 预期失败 |
| Node RED | 新增有界缓存测试 | 修复前失败 | `pipelineBuffers.ts` 不存在 | 预期失败 |
| Rust RED | 新增子进程环境与有界扫描测试 | 修复前失败 | 两个 helper 不存在 | 预期失败 |
| Python GREEN | `python -m unittest tests.test_prepare_project -v` | 全部通过 | 9/9 通过 | 通过 |
| Node GREEN | `npm run test:unit` | 缓存/日志测试通过 | 2/2 通过（加入路由测试前） | 通过 |
| Rust GREEN | 隔离 target 下 `cargo test --lib` | 全部通过 | 31/31 通过 | 通过 |
| 前端构建 | `npm run build` | 构建成功且 bundle 无显著增长 | 成功，主应用 78.70 kB gzip | 通过 |
| 前端静态检查 | `npm run lint` | 无错误 | 无输出错误 | 通过 |
| 实时缓存性能 | 20,000 项、32 项/批、窗口 240 | <100ms 且有界 | 10.9ms、保留 240 | 通过 |
| 浏览器运行时 | Playwright headed/headless | 页面加载并截图 | Chrome 导航前 code 13 | 环境限制；改用路由单测 |
| Python 全量回归 | `python -m unittest discover -s tests -v` | 全部通过 | 130/130 通过 | 通过 |
| 默认入口 | Node route test | `/project/media` | 通过 | 通过 |
| 媒体准备 E2E | 中文轨道 + CREATE_NO_WINDOW + pipes | exit 0/result/complete | exit 0、3 items、complete、stderr 空 | 通过 |
| Tauri binary | `cargo check --bins` | 编译通过 | 通过，6 个既有 warning | 通过 |
| 最终模型上限 | 100,000 items JSON | 无明显主线程瓶颈 | 13.42MB，parse 27.9ms，filter 2.3ms | 通过 |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-07-10 19:28 +08:00 | create_goal 因已有 active goal 失败 | 1 | get_goal 确认目标一致，复用现有目标 |
| 2026-07-10 19:53 +08:00 | Cargo/Tauri 生成 libresource.a 时文件占用 (os error 32) | 1 | 改用独立 CARGO_TARGET_DIR，避免复用被占用产物 |
| 2026-07-10 19:58 +08:00 | 子进程复现缺少 PYTHONPATH，ModuleNotFoundError: scripts | 1 | 补齐与 Tauri 相同的 PYTHONPATH 后重试 |
| 2026-07-10 20:17 +08:00 | Playwright headed Chrome code 13 / TargetClosed | 1 | 改用 headless 浏览器会话 |
| 2026-07-10 20:46 +08:00 | 无法读取截图中的应用终端：thread 未挂接 terminal session | 1 | 转查工程文件副作用与代码状态传播 |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 6 已完成，正在最终交付 |
| Where am I going? | 向用户交付修复、验证结果与残余风险 |
| What's the goal? | 修复默认入口、照片预览、抽帧退出码 120，并优化大素材性能 |
| What have I learned? | 见 findings.md |
| What have I done? | 已完成导入、准备、下一步与对齐可用性的实现和全量验收 |
# 2026-07-10 Phase 6 continuation
- Inspected the reported import modal screenshot and the real adjacent project file.
- Added RED regression coverage for atomic open-or-create behavior and shared media readiness semantics.
- Confirmed RED: Node tests fail because `mediaReadiness.ts` does not exist; Rust tests fail because `open_or_create_project_impl` does not exist.
- Implemented safe adjacent-project reuse, modal busy/error feedback, shared readiness evaluation, and the media-to-reconstruction next-step action.
- Browser verification passed with Playwright + Edge: media page rendered with zero console errors, showed `下一步：对齐与重建`, navigated to reconstruction, generated the 16-step plan, and exposed enabled `一键启动对齐`.
- Fixed a browser-preview-only crash caused by unconditional Tauri `convertFileSrc`; local absolute paths now degrade to placeholders outside Tauri without console floods.
- Final verification: Node 8/8, Rust 34/34, Python 130/130, Vite build passed, oxlint passed, `git diff --check` passed.

# 2026-07-10 Phase 7 running-to-ready submission
- Preserved the failing project and confirmed complete result/manifest artifacts existed while the project track stayed `running`.
- Reproduced the exact `job_conflict` by changing the finalization regression fixture from `draft` to the real `running` state.
- Added a dedicated media-result commit guard that permits the job-owned `running → ready` transition while retaining locks against reconstruction and unrelated jobs.
- Moved durable media settlement into the Rust child-exit watcher; frontend completion and startup recovery now use an idempotent sync command.
- Real project acceptance passed: revision 4, status ready, 31 items, alignment manifest present, no result/job marker residue.
- Verification passed: Rust 34/34, Node 8/8, Vite build, oxlint, and `git diff --check`.
# 2026-07-11 抽帧 100% 后提交失败复核
- 读取用户截图并确认失败点在最终工程提交，不在抽帧、照片索引或缩略图生成。
- 时间线核验：截图 22:48；修复源码 23:57；修复测试二进制 23:58；当前运行 EXE 00:55。当前桌面程序已包含修复。
- 定向 Rust 回归通过 3/3：允许非媒体 global revision 变化；恢复无 marker 的遗留完整结果；拒绝真实 media revision 冲突。
- Python 定向回归通过，确认新媒体结果写入 `inputMediaRevision`。
- 当前源码在隔离 `CARGO_TARGET_DIR` 下 `cargo check --lib` 通过；默认 target 因正在运行的桌面 EXE 占用 Tauri `libresource.a`，按既有约定改用隔离 target。
- 截图对应的重复处理风险已消除：若旧 result/manifest 仍在，重新打开工程时 `sync_media_job_result` 会幂等恢复为 ready，无需重新索引 138 张照片。
# 2026-07-11 Phase 12 continuation
- 恢复 active goal、文件化计划和当前 dirty worktree；确认 Phase 12 仍是当前阶段，Phase 13-17 尚未开始。
- 读取 Stage 4 规格、架构审查词汇和现有 geometry RED 状态；决定以单一深 `geometry` 模块集中点云版本与几何事务，不增加假想 adapter 或新依赖层。
- Phase 12 geometry RED 已确认：`cargo test --lib geometry::tests` 因 `materialize/register/set_active/delete/read_points_count` 尚不存在而 10 个编译错误，证明当前没有点云版本持久化实现；这是预期失败，下一步实现最小完整后端事务。
- Phase 12 geometry GREEN：新增 SHA-256、点数/有限 XYZ/track 完整性解析、刚体矩阵校验、canonical/world 双向物化、活动点云切换事务与中断恢复 marker、标准/活动删除保护。
- 定向测试 5/5 通过：版本永久保留与可逆切换、非 identity transform 归一化/重应用、损坏版本不替换活动文件、stale transform revision 拒绝、非活动致密版本删除且原候选保留。
- Phase 12 后端集成回归：Rust 全量 lib 62/62 通过。重建成功现在同时重置 canonical 基准、写 `base_images.bin`、物化永久 standard、将旧 dense 标记 stale；Tauri 已注册 list/preview/set-active/delete/register 命令。
- 旧 `apply_lfs_densify_result` 已改为注册永久 densified 版本，不再覆盖活动 `points3D.bin` 或删除候选；旧 discard 只关闭预览并保留可恢复候选。
- Phase 12 transform RED 已确认：3 个编译错误均为 `apply_world_transform_impl` 不存在；新测试覆盖投影等价/不可变 canonical、det=-1 拒绝、损坏 base images 时旧 world 文件与 revision 不变。
- Point variant UI RED 已确认：Node 15 个既有测试通过，新测试因 `features/results/pointVariants.ts` 不存在而失败；覆盖预览/训练选择分离、激活条件和删除保护。
- 首次 gizmo 前端构建仅因只读 `Matrix4` 元组被当作可写数组而失败；改用内部 `number[]` 计算并在长度固定后收窄，未改变矩阵语义。
- Stage 4 UI 第一闭环：结果页新增独立点云版本面板（预览/设为训练/删除保护），canonical 预览在前端应用当前 world transform 后与世界相机同坐标显示；Node 20/20、Vite build 通过。
- 水平校正新增 Three.js TransformControls 三轴旋转 gizmo、自由/1°/5°/15°吸附、欧拉角只读显示、重置/撤销/应用；拖动期间禁用 OrbitControls。前端将 Three 预览旋转按坐标系转换并左乘累计 worldFromCanonical，后端执行 images/points 双文件事务。
- 致密化旧“应用/丢弃”UI 已改为“保存为版本/关闭预览（保留候选）”，不再把 dense 数据缓存成活动 base，也不会删除候选。
- 当前回归：Rust 64/64、Node 20/20、TypeScript/Vite build 通过；oxlint 仅报 1 个冗余 Boolean，已立即清理。
- 用户再次提交 138/138 后 `project revision changed from 2 to 4` 的旧截图；复核时间戳确认截图早于修复源码与当前 EXE。媒体结算定向 Rust 回归 5/5 通过，Python 素材准备合同 9/9 通过；当前运行 EXE 已包含 media revision 与 legacy recovery 修复。
- Stage 4 Playwright RED：1366/1024 截图确认训练点云面板遮挡水平校正面板；响应式避让修复后重新截图通过。浏览器实测 X 180° 预设显示 180.0°、撤销恢复 0.0°且未应用写盘；控制台 0 error/0 warning。
- Stage 4 代码审查修复几何回滚 marker 过早删除：新增统一回滚入口和中断 transform 恢复测试。geometry 9/9、Rust 全量 65/65 通过；`docs/COLMAP_DENSIFICATION.md` 已改为永久版本注册、预览/训练选择分离和可逆切换语义。
- 修复旧工程结果页标准版本迁移缺口：新增 `materialize_standard_variant` Tauri 命令，completed 且 active=standard 的旧工程进入结果页时自动物化；拒绝从活动 dense 云伪造缺失 standard。Node 定向 4/4、geometry 10/10、Vite build 通过。
- Phase 13 真实全流程完成：Tauri 素材准备 30 OSV 逻辑帧 + 138 照片全部 ready；Metashape 对齐完成并通过独立校验（438 images / 11 cameras / 377,707 points）；应用完整点云读取 3.44s。
- 既有 CUDA 致密化环境探针全绿；受控实跑 37.3s 得到 400,339 点永久版本。真实完成预览读取、dense 激活、standard 回切、候选保留和 hash 恢复验证。Phase 13 标记 complete，Stage 4 仅剩查看器内致密化模块拆分。

# 2026-07-11 抽帧最终提交修复交付复核
- 再次按用户截图复核 138/138 后失败路径，确认抽帧产物正常，失败仅来自旧构建使用全局 project revision 提交结果。
- 当前媒体结果使用 `inputMediaRevision`，允许工作区切换、改名等非媒体操作导致的全局 revision 2 → 4，同时继续拒绝真实媒体版本变化。
- 修复 `reconstruction.rs` 测试模块漏导入 `ProjectTrackType` 的编译阻塞；不改变运行时逻辑。
- 验证通过：媒体结算定向 Rust 5/5、Rust 全量 66/66、Python 素材准备 9/9、前端单测 21/21、Vite build、oxlint、`git diff --check`。
- 已刷新调试程序：`xpano-ui/src-tauri/target/debug/xpano-ui.exe`，SHA-256 `4AF8D938B6183D79E943080AAF622EB38E2DB0D375D6275FD0C3E4A18D058497`；旧 Release EXE 与 `dist/xPano-light-Setup.exe` 仍是 2026-07-09 产物，不包含本修复。

# 2026-07-11 Phase 12 closure
- 完成 `DensificationPanel.tsx` 拆分后的 Playwright/Edge 运行时验收：面板打开、参数展开、滚动、关闭/重开均正常，截图保存在 `output/playwright/`，控制台 0 error/0 warning。
- 全量回归首次发现真实插件 `--help` 超过 30 秒；根因是环境探针为了读取参数帮助加载完整 Torch/Open3D 插件栈。
- 将帮助路径改为 AST 提取并执行插件自身 `build_argparser`，保持参数定义单一来源且不导入重依赖；真实帮助与隔离轻量测试 2/2 通过。
- Phase 12 最终验证：Rust 66/66、Python 136/136、Node 21/21、Vite build、oxlint、Tauri bins check、`git diff --check` 全部通过。
- Phase 12 标记 complete，当前阶段切换到 Phase 14 安装器与运行时自举设计。

# 2026-07-11 Phase 14 installer/bootstrap design
- 按 Tauri 2.11.3、Python embeddable、pip secure installs 和 PyTorch 官方文档完成发布链审计。
- 确认旧 Inno 脚本默认 `-SkipTauriBuild` 与 Tauri NSIS 双链漂移是实际发布风险；正式方案统一为强制当前源码构建的 Tauri NSIS。
- 确认当前 Tauri `../binaries/` 资源路径错误、FFmpeg PATH 命中 0-byte WinGet link、`.venv-densify` 7.636 GiB 和 torch cache 1.034 GiB 均不能直接进入正式包。
- 新增 `docs/WINDOWS_PACKAGING_AND_BOOTSTRAP.md`，固定随包 allowlist、用户缓存运行时、manifest/hash/mirror、CPU/CUDA profile、断点/缓存/取消/回滚、安装升级卸载和环境模拟矩阵。
- Phase 14 标记 complete，进入 Phase 15 实现。
- 2026-07-11 用户再次提供的 138/138 后 `project revision changed from 2 to 4` 截图经文件时间复核为 2026-07-10 22:48，早于 `media.rs` 修复（23:57）、当前运行 EXE（次日 02:37）和安装包（05:26）。当前定向验收：Rust 媒体最终提交 5/5、Python 素材准备 9/9 均通过；当前脚本明确写出 `inputMediaRevision`，安装包 SHA-256 为 `51F7B4D0D9AEF2E29B14507A6120E63D24A99685732E5E21AF17549325CED164`。
- 本轮验证最初误用 `pytest`，本机 Miniconda、嵌入式 Python 和系统 Python 3.12 均未安装该模块；测试文件实际采用标准库 `unittest`，改用 `python -m unittest tests.test_prepare_project -v` 后 9/9 通过，未安装或下载任何依赖。
- Phase 15 安装验收第一轮：旧安装器在中文路径返回 0 但未落盘，停止运行中的测试 EXE 后稳定返回 2。定位为 WebView2 已安装在 32 位注册表视图，hook 误判缺失并运行离线安装器后回滚；新增 `tests.test_windows_packaging` RED/GREEN，修复双视图探测和安装后重检。
- 修复后安装到 `D:\CodeFiles\360gaussain\.codex_tmp\安装 验收\xPano` 成功，868 项 manifest 中 867 项逐文件大小/hash 通过，唯一缺项是按设计安装后删除的 WebView2 installer；内置 Python、FFmpeg/ffprobe（CUDA/D3D11VA 可见）、COLMAP 和致密化 runner `--help` 探针通过。
- 安装版启动验收继续发现 `WebView2Loader.dll` 未随 NSIS 安装：target release 可显示窗口，安装版仅有 2 线程/无 WebView 子进程。已新增 staging/config/build-chain 回归，fresh Cargo prebuild 后把 loader 纳入 manifest 和 EXE 同级资源；同时补卸载递归清理 `$INSTDIR`，避免生成的 `__pycache__` 残留。下一步重新正式构建并复验安装/启动/卸载。
# 2026-07-11 media finalization failure follow-up
- User screenshot confirms extraction/indexing reached 100% for 138/138 photos, then final submission failed with `project revision changed from 2 to 4`.
- The real acceptance project currently remains healthy: project revision 10, media revision 2, panorama track ready with 30 items, photo track ready with 138 items.
- Existing source contains the scoped-revision fix in `media.rs`: media finalization keys conflicts off `revisions.media`, not navigation/name changes to the global revision, with legacy-result recovery tests.
- Verification command note: one Cargo invocation incorrectly supplied two positional test filters and was rejected by Cargo; rerun each filter separately.
- Targeted verification passed: non-media revision changes finalize successfully; legacy failed results can be recovered safely; all 13 `media::tests` passed.
- Build provenance checked: `media.rs` was modified at 2026-07-10 23:57, while the release EXE and current installer were built at 2026-07-11 06:28, so the distributed package contains the fix.

# 2026-07-11 runtime bootstrap environment matrix expansion
- Added TDD coverage and implementation for HTTP-vs-offline errors, resumable Range downloads, servers ignoring Range, preserved partial files, cancellation, disk preflight, BUSY locking, install failure rollback, successful upgrade activation, verified-cache offline rebuild, Unicode/space paths, and explicit CPU/CUDA artifact branches.
- `python -m unittest tests.test_runtime_bootstrap -v`: 20/20 passed using only tiny temporary artifacts and file/mock sources; no production large-package URL was opened.
- Real manifest plan-only validation succeeded without downloads: CPU 71 artifacts / 1,906,768,780 bytes; CUDA 71 artifacts / 4,754,740,087 bytes.
- Product-side profile selection now requires both user CUDA opt-in and a successful `nvidia-smi` driver probe; otherwise it selects CPU and emits an explicit downgrade notice.
- Rust profile-selection regression test passed. `cargo fmt --check` could not run because `cargo-fmt.exe` is absent from the installed GNU toolchain; no network install was attempted, so formatting is being checked manually plus compilation/diff gates.
- Verification command mistake: a combined Python/Rust suite was given a 1-second shell timeout, so the harness killed Python and printed the known GBK stdout finalizer noise. This was a test-runner timeout, not a product failure; rerun suites separately with normal timeouts.
- The first formal installer rebuild invocation repeated that shell-timeout mistake and was terminated after one second before meaningful build work. The next invocation uses a normal command timeout and yields at the orchestration layer instead.

# 2026-07-11 latest installer and installed real-project acceptance
- Formal installer rebuild completed successfully after 565 seconds: Python 166/166, Node 21/21, oxlint, Vite, release Cargo prebuild, Tauri release build, and NSIS all passed.
- Latest installer: `dist/xPano-0.1.0-windows-x64-setup.exe`; SHA-256 `51293F004AD27D93885A5CBCD661A637C390ACCEBEF58A41E6E5B71C0343F94C` and sidecar match.
- Installed silently without elevation to `D:\CodeFiles\360gaussain\.codex_tmp\安装 验收\xPano`; installed manifest has 869 entries, with zero size/hash mismatches and only the intentionally post-install-deleted WebView2 offline installer absent.
- Installed probes passed: bundled Python imports `cv2/numpy/PIL/piexif`; FFmpeg exposes CUDA/D3D11VA; COLMAP 4.1 starts; installed bootstrap plans the CPU profile without downloading anything.
- Opened `D:\3DRegistration\test\xPano-phase13` through the installed app's real native folder dialog. Media workspace reports panorama 30/30 and photos 138/138 ready, 168/168 selected items, and exposes the next-step button.
- Reconstruction workspace restores the completed 100% job and durable log. Results workspace renders the real 377,707-point standard cloud and 400,339-point dense cloud; normal clicks switched standard -> dense -> standard without changing the training variant.
- WebView2 renderer at 1280x800 has document size exactly 1280x800, no buttons outside the viewport, and two DPI-scaled canvases covering the full viewport. Screenshots are under `output/installed-app/`.

# 2026-07-11 final code-quality review fixes
- Review identified and fixed three release-blocking bootstrap edges: midstream HTTP disconnects were not classified as network failures; cancellable pip polling could block on full stdout/stderr pipes; force-killed bootstrap processes could leave a permanent BUSY lock.
- Added regression coverage for interrupted response reads, communicate-with-timeout output draining, live-owner BUSY behavior, and stale-PID lock recovery.
- Disk preflight now budgets missing downloads plus twice the selected artifact size for staging/unpack plus safety margin.
- NVIDIA probing no longer executes a PATH/current-directory `nvidia-smi`; it only checks standard Windows/NVIDIA install locations, preventing executable search-path hijacking.
- Post-review verification: runtime bootstrap 26/26 and Rust 69/69 passed; Python byte-compilation passed.

# 2026-07-11 final release closure
- Final formal build passed 169 Python tests, 21 Node tests, oxlint, Vite, release Cargo prebuild, Tauri release build, and NSIS.
- Final installer SHA-256: `874AD452E38FB98800DA6956567D70D15237E11F0CA152B948953257BBEC8262`; sidecar matches; version is 0.1.0; size is 415,112,039 bytes.
- Final package was installed over the acceptance installation; installed bootstrap hash matches final source. The final installed app again opened the real project and rendered the 377,707-point result with the 400,339-point dense variant registered.
- Final gates: 10 PowerShell scripts parse with zero errors; `git diff --check` has no errors; forbidden dense payload count is zero; bundled dense package count is zero; installed retained manifest mismatches are zero.
- Authenticode status is `NotSigned` for installer and app because no publisher certificate is available. No claim of signing is made.
- Temporary WebView2 debugging process was stopped, uninstall-test runtime/cache sentinels were removed, and the final installed app was relaunched normally and is responding.
# 2026-07-11 Phase 20 closure
- Added async blocking-executor COLMAP parsing and compact binary Tauri IPC.
- Added off-main-thread packet decoding, coordinate conversion, color preparation, bounds, percentile, density, and camera-aware fitting through a Web Worker.
- Preserved full point counts, source color precision, existing display formulas, camera overlays, and view-fit behavior.
- Added Rust parser/packet regressions and frontend packet/processing/empty-cloud regressions.
- Verification passed: Rust 71/71, Node 26/26, Python 171/171, oxlint, TypeScript/Vite production build, and git diff whitespace checks.
- `cargo fmt` remains unavailable because rustfmt is not installed in the existing GNU toolchain; no component was installed.
- Command corrections: an initial frontend targeted-test command used the wrong working-directory path and unavailable `tsx`; reran with native `node --test`. An initial Rust `--exact` filter matched zero tests; reran with the non-exact test-name filter and confirmed 1/1 passed.
- No installer or release package was built.
# 2026-07-11 Phase 21 start
- Committed the completed point-cloud responsiveness work as `dc8737b perf: keep point-cloud preview responsive`.
- Planning a separate single-stage LichtFeld Studio Gaussian training integration; no installer build is authorized.
- Tooling notes: GitHub network lookup failed because the configured local proxy at `127.0.0.1:7897` was unavailable; authoritative evidence was instead taken from the shipped v0.5.3 help, build metadata, GPL license, embedded Python API docstrings, and bundled plugin documentation. A broad parallel `rg` inspection returned exit 1/truncated output; subsequent lookups were narrowed and run independently.
- Copied the complete LichtFeld Studio v0.5.3 distribution into `runtime/lichtfeld-studio`; source and target relative file lists both contain 1,450 files.
# 2026-07-11 Phase 21 continuation

- Added failing log-parser tests, then implemented `LichtfeldLogTracker`; 8 focused tests pass.
- Replaced GUI-incompatible callback progress with incremental native-log parsing.
- Removed `--python-script`/bridge wiring from Python, Rust launch arguments, release staging, and integration docs.
- Next: run a 10-20 iteration visible-GUI probe, then full Python/Rust/frontend/build verification and real app acceptance.
# 2026-07-11 Phase 21 manual acceptance fixes

- Added post-load MCP parameter application and official `training.start`; removed automatic CLI `--train` start.
- Changed bilateral-grid default to enabled across Python, Rust, and UI defaults.
- Added structured command-error formatting and project refresh after all terminal pipeline events.
- Verified exact 30 iterations, max width 512, resize factor 8, bilateral checkpoint, PLY output, and a subsequent fresh 5-iteration restart.
- Next: full suites, build/lint/diff review, then hand off for manual app retest.
# 2026-07-11 LichtFeld real-step progress fix
- Added regression tests proving loss records do not advance iteration and MCP state reports exact iteration/total/loss/Gaussian count; focused suite passed 10/10.
- Rejected v0.5.3's all-zero `training.get_state` snapshot after real probing; wired one-second MCP `editor.run` polling of the official embedded Python trainer accessors instead.
- MCP polling failures degrade observably to log/checkpoint progress and do not abort an otherwise healthy training process.
- One broad `rg` inspection returned exit 1 because optional runtime search paths were absent; narrowed source inspection provided the required MCP response contract.
- Real 300-step acceptance emitted exact live values including 12, 45, 79, 110, 147, 220, 270, and 300 with no polling warning; output PLY was produced successfully.
- Full gates passed: Python 184/184, Rust 75/75, frontend 32/32, oxlint, and TypeScript/Vite production build. No installer was built.

# 2026-07-11 Phase 23 offline release runtime planning

- Marked Phase 22 complete because the user accepted point-cloud preview behavior.
- Audited formal release staging, installer configuration, offline wheel inventory, Metashape provisioning, Python child environment injection, backend probes, title-bar environment state and the existing densification bootstrap.
- Confirmed the formal NSIS staging currently omits `tools/offline-wheels`; no installer build was run.
- Confirmed current Metashape provisioning writes mutable state below the app root, assumes Metashape pip, has online fallbacks and communicates readiness through an app-root text file.
- Selected the simplest stable architecture: deepen the existing atomic runtime bootstrap into one Runtime Readiness Module with immutable, bundled-wheel and downloadable Adapters rather than adding another independent installer.
- Added the ordered implementation and clean-machine acceptance plan to `task_plan.md`. No product code was changed in this planning pass.

# 2026-07-11 Phase 23 implementation complete

- Added bundled runtime manifest/notices, exact ABI/hash validation and formal wheel staging.
- Added local atomic runtime provisioning, Metashape ABI detection, bundled pip installation, import probes, reuse, rollback, disk preflight and structured CLI events/errors.
- Replaced app-root mutable state with LocalAppData activation and explicit Rust -> Python -> Metashape child environment injection.
- Replaced PowerShell environment mutation/online fallback with a compatibility wrapper over Runtime Readiness.
- Added per-feature runtime readiness UI states and a Tauri probe command.
- Replaced incompatible pip.pyz with a Python 3.9-compatible pip 25.0.1 zipapp.
- Verification passed: Python 194/194, Rust 78/78 without warnings, frontend 37/37, oxlint, TypeScript/Vite production build, Python byte compilation, PowerShell parsing and `git diff --check`.
- Final formal release staging passed with 2,132 files, 13 wheels, cp39/cp310/cp311/cp312 coverage, runtime readiness entrypoint/manifest/pip/notices present and zero forbidden densification payloads.
- Final staged-runtime acceptance installed NumPy 1.26.4 and OpenCV 4.10.0 into a fresh Unicode/space LocalAppData-style state for copied dependency-free Metashape Python 3.9. The Metashape copy's 3,756-file hash inventory remained unchanged.
- No NSIS installer or public release package was built.

# 2026-07-11 xPano 0.2.0 release

- Selected semantic version 0.2.0 and aligned Cargo.toml, Cargo.lock, Tauri config, package.json and package-lock.json.
- Added CHANGELOG.md and annotated release metadata for bundled LichtFeld Studio v0.5.3.
- Added Git LFS rules for 272 bundled binary/font/shader paths; LFS fsck passed. Vendored runtime files are stored without Git text conversion.
- Formal build completed in 817.4 seconds: Python 194/194, frontend 37/37, oxlint, Vite, release Cargo, staging and NSIS passed.
- Installer: `dist/xPano-0.2.0-windows-x64-setup.exe`, 728,504,674 bytes (694.8 MiB).
- SHA-256: `a537606661e40d965f590325cc0692a8ef55112e58e8b37c2e61ecb6e48c2acb`; sidecar matched.
- Authenticode status is `NotSigned`; no publisher certificate is configured.
- Isolated Unicode/space-path installation returned exit 0. Installed manifest: 2,132 resources, one expected post-install WebView2 installer deletion, zero unexpected missing files, zero size/hash mismatches and zero forbidden densification payloads.
- Installed runtime readiness reported bundled Python, FFmpeg/ffprobe, COLMAP, LichtFeld, pip, runtime manifest and real Metashape cp39 ready. Installed app version was 0.2.0 and its main window became responsive.
- Isolated uninstall returned exit 0 and removed the acceptance installation.
- Release commit: `42502e23f8831d68abadbdba080a1b5bf14e26d6`; annotated local tag: `v0.2.0`.

# 2026-07-11 Phase 25 full offline release start

- User requested a second, independently named package containing all redistributable dependencies for install-and-use operation without network access.
- The standard xPano 0.2.0 installer remains immutable; the new artifact will add both CPU and CUDA densification profiles while retaining the bundled normal runtimes and Metashape offline wheel provisioning.
- Initial broad `rg` command used PowerShell-incompatible wildcard path arguments and failed before modifying files; subsequent inspection uses repository enumeration and narrowed paths.
- Added RED tests for bundled-cache seeding, corrupt bundled artifacts, exact CPU/CUDA staging closure and incomplete-closure rejection; all failed on the missing behavior as expected.
- Implemented verified bundled-cache seeding, optional `--bundled-cache` runtime wiring, full-offline release staging, Rust resource discovery and a `-FullOffline` installer flavor. Focused Python suites now pass 36/36.

# 2026-07-11 Phase 26 Windows loader incident

- User screenshot reports `xpano-ui.exe` cannot start because `libunwind.dll` is missing.
- Reproduced directly from the 0.2.0 release executable import table; the DLL is absent from release staging.
- Identified the actual Rust host as `x86_64-pc-windows-gnullvm`; current MSVC-only Cargo config does not affect the build.
- Minimal same-toolchain comparison proves static CRT/unwind linkage removes the dependency. Next step is RED regression coverage and a generic recursive import-closure build gate.
- Added static gnullvm CRT/unwind linkage and recursive PE import-closure validation before and after Tauri's own release build.
- Added regression coverage for unresolved toolchain DLLs, recursive app-local DLLs, abnormal import paths, static target configuration and dual formal-build gates.
- Rebuilt the release EXE: `libunwind.dll` is absent and the exact EXE/WebView2Loader closure passes.
- Full gates passed: Python 203/203, Rust 78/78, frontend 37/37, oxlint, TypeScript/Vite, Python byte compilation, PowerShell parsing and diff hygiene.
- First 0.2.1 installed acceptance found only six retained files in both Unicode and ASCII paths. Root cause was the custom NSIS preinstall mutation of `$INSTDIR`, not Tauri resource staging or Unicode paths.
- Added a RED packaging test forbidding preinstall `$INSTDIR` mutation, removed the conflicting hook and kept WebView2/post-uninstall hooks intact.
- Final 0.2.1 build passed the formal chain in 768.2 seconds and produced SHA-256 `1294a493b8623adf44a298856940b29dc416d408881cf46c7ce312abecc8e309`.
- Clean Unicode/space-path installation retained 2,135 files. Manifest verification: 2,133 entries, one expected post-install WebView2 deletion, zero unexpected missing files and zero size/hash mismatches.
- Installed EXE/WebView2Loader dependency closure passed. With PATH restricted to Windows system directories and Rust/LLVM/MinGW/CUDA variables removed, xPano created a responsive main window and remained running.
- Installed Runtime Readiness reported bundled Python, FFmpeg/ffprobe, COLMAP, LichtFeld, pip and runtime manifest ready.

# 2026-07-11 Phase 27 extraction incident start

- Inspected the user screenshot: installed preparation exits immediately because `run_xpano_prepare_project.py` imports `scripts.xpano_tracks` without making the app root importable.
- Began a full inventory of entrypoint imports and extraction-rate semantics. Current configuration is still seconds-per-frame throughout UI, contracts, Rust and Python, with reciprocal conversion immediately before FFmpeg.
- Added RED installed-entrypoint, FPS, timestamp, frame-limit, legacy migration and BOM tests; confirmed failures before implementation.
- Replaced extraction interval semantics across frontend, Rust, Python, FFmpeg command construction, progress estimates, manifests and run summaries.
- Full formal verification passed: Python 210 tests, frontend 39 tests plus lint/build, Rust 81 tests, release DLL closure and NSIS build.
- Built `dist/xPano-0.2.2-windows-x64-setup.exe`, SHA-256 `55d64a270aacbcda5a1e35b621648c59688574da39c3008d14b022ca48a2d5aa`.
- Installed 0.2.2 into the controlled prior acceptance location, verified 2,133 manifest entries with only the designed WebView2-installer deletion, ran all installed entrypoint probes and real dual-track extraction under a sanitized environment, launched the GUI responsively, then uninstalled cleanly.

# 2026-07-12 Phase 28 environment-resolution audit start

- User reports that manually selecting Metashape does not work and requests a full environment-boundary audit.
- Started systematic trace of explicit-path persistence, readiness, provisioning, planning and execution. No release package will be built unless the user requests it.

# 2026-07-12 Phase 28 complete

- Added RED coverage for project-config persistence, explicit-path precedence, missing-path fail-fast, quoted/Unicode paths, PATH-only Metashape discovery, explicit Python fail-fast and execution-plan invalidation.
- Added executable controls to the active reconstruction setup wizard and settings panel. Failed auto-detection no longer prevents selecting Metashape and browsing to the executable.
- Unified path normalization and propagation across React, Tauri probing/planning, Python dependency checks, runtime readiness and `XPANO_METASHAPE` handling.
- Added a backend plan gate so a stale UI probe cannot create a runnable plan for a missing executable.
- Verification passed: Python 213/213, focused environment Python 27/27, Rust 86/86, frontend 42/42, oxlint, TypeScript/Vite production build and `git diff --check`.
- Real local probe resolved quoted `E:\FastProgram\Metashape\metashape.exe`, detected Metashape Python `cp39`, selected two manifest artifacts and confirmed both offline wheels exist under a sanitized PATH.
- `cargo fmt --check` could not run because `cargo-fmt.exe` is absent from the installed GNU toolchain; compilation, lint, whitespace and manual diff review were used instead. No toolchain component or release package was installed or built.
- Command corrections: one plan-file search ran from `xpano-ui`; one invalid wait call was discarded; one PowerShell pipeline had an empty-pipe parse error; the source-root readiness CLI exposed the expected non-staged FFmpeg layout. All were corrected without product-side effects.

# 2026-07-12 Phase 29 start

- User requested a `从 PSX 重新导出` button beside alignment for already-completed Metashape projects.
- The legacy Python/backend path already supports `--reexport-existing-project`, but the active reconstruction workspace has no UI action or re-export-specific execution plan.
- Selected design: reuse the existing job supervisor and pipeline runner with a dedicated export-only plan so cancellation, durable logs, progress and artifact finalization remain consistent.

# 2026-07-12 Phase 30 start

- Restored the unsynced Phase 29 worktree and retained all existing user changes.
- Established the real performance baseline from the completed 1,013-camera export and confirmed the current re-export task was active during diagnosis.
- Selected the dependency-light acceleration direction: existing packaged OpenCV with probed OpenCL/UMat, compiled CPU fallback, then NumPy compatibility fallback. No PyTorch or OpenCV-CUDA dependency is planned without contrary benchmark evidence.
- Added a staged, test-driven implementation and acceptance plan. No installer build is authorized.
- Confirmed the live PSX re-export completed normally and cleanup removed the transaction backup. Its measured duration provides the before baseline for cache and remap work.
- Confirmed OpenCV 4.10 is already a hash-locked Metashape runtime artifact for every supported ABI; no new dependency family is required for the first accelerated backend.
- Defined the safe cache transaction: staged complete output, verified image reuse via hardlinks/copies, no writes through reused hardlinks, full validation, persistent marker, then atomic directory publication with rollback.
- Probed the existing OpenCV family: OpenCL is available and uses the NVIDIA D3D11 interop path on this machine. A locked-wheel isolated probe remains required.
- Benchmarked a real full-size face: OpenCV CPU was about 240x faster than the current NumPy remap kernel, OpenCL warm was about 46x faster, and both stayed within a maximum 4-level interpolation delta. Auto-selection will be evidence-driven rather than GPU-forced.
- Added the pure export-image cache module through RED/GREEN TDD. It now provides deterministic signatures, SHA-256 output records, schema validation, atomic manifest writes, hardlink-first reuse with copy fallback, corruption rejection and traversal protection; 6/6 focused tests pass.
- Added the remap backend engine through RED/GREEN TDD. Auto mode benchmarks OpenCV CPU and validated OpenCL, forced modes degrade safely, runtime failures switch once to NumPy with a visible warning, and five per-camera source copies were removed; 7/7 exporter tests pass.
- Replaced the fragile move-everything re-export transaction with same-volume staging, pre-publish verification, a persistent `work/reexport_transaction.json` marker, directory/cache publication, live verification, committed cleanup and next-run rollback recovery. Four focused transaction/recovery tests pass.
- Integrated signatures and cache reuse into frame/cubemap export, fetched projections once per camera, added required cache manifest publication and passed Python compilation plus 19 focused cache/export/re-export tests.
- Confirmed staged output validation covers the new transaction shape and identified the exact Runtime Readiness command needed to probe the locked OpenCV wheel without relying on the developer environment.
- Passed the real Runtime Readiness/Metashape cp39 probe. The exact OpenCV 4.10 runtime selected NVD3D11 OpenCL and achieved about 70x remap-kernel speedup on a real full-size face while retaining automatic NumPy fallback.
- Selected the existing mixed PSX for a bounded real acceptance: keep a few transformed fisheye/frame cameras enabled only in memory, export twice to separate temporary directories, and compare cached JPEG hashes plus COLMAP validation without saving the source project.
- First real probe exposed a missing `Path` import before any output was written; fixed immediately. This validates the need for application-level Metashape acceptance beyond isolated unit tests.
- Completed bounded real Metashape acceptance: OpenCL first export succeeded, second export reused all four camera image sets, 12/12 JPEG hashes matched, all three COLMAP binaries matched, and both datasets passed structural/count validation.
- Full Python regression reached 227 passing tests and one legacy test-double signature error; corrected the fake to match the already-existing exporter API before rerunning.
- Full Python regression now passes 228/228 after the test-double correction.
- The first large benchmark was interrupted by the orchestration timeout at camera 1. Transaction rollback removed staging/marker state and the original 3,581-image output passed validation unchanged; no product failure or data loss occurred.
- Completed the full benchmark: first accelerated export 367.606 s (3.44x faster than legacy), then a 100% cache-hit export in 114.755 s (11x faster). Both published and validated successfully. Profiling evidence now points to redundant cache hashing as the next bottleneck.
- Added the cache metadata fast path through RED/GREEN TDD: unchanged size plus nanosecond mtime reuses the recorded SHA without rereading bytes, changed metadata falls back to SHA, and verified hardlink records are carried forward instead of rehashed. Eight cache tests pass.
- Real migration benchmark completed in 72.450 s; the next stable 100% cache-hit run completed in 59.961 s. The cache hot path now meets roughly one minute for 3,581 images, and stage timing is needed to target the remaining non-image work.
- Added exporter stage metrics and measured the full hot-cache path: 50.243 s is inside the per-camera observation loop, versus 7.237 s point scan and 10.942 s binary write. Next optimization targets millions of tiny NumPy allocations in cubemap projection.
- Tested scalar tie-point projection on the full project. It saved about 11 s but changed `images.bin`, so it was reverted; strict output determinism takes precedence over that micro-optimization.
- Extracted remap selection, OpenCL/OpenCV execution and NumPy fallback into the dedicated dependency-light `export_remap.py` module, keeping cache logic in `export_image_cache.py` and Metashape orchestration in `export_colmap.py`.
- Revalidated the refactored modules in real Metashape with a 4-camera 100% cache hit. Removed the temporary probe script after acceptance; the full project remains on the deterministic NumPy-reference COLMAP hashes.
- Completed the final cross-layer gates: Python 232/232, Rust 88/88, frontend 44/44, oxlint, TypeScript/Vite production build, Python compilation and `git diff --check` all pass.
- Explicitly enable OpenCL whenever the OpenCL backend is selected; failure remains observable and falls back to compiled OpenCV CPU. Added a regression test for this runtime boundary.
- Added the two new exporter modules to the formal release-staging required-file gate, with a regression test proving an incomplete package is rejected before installer creation.
- Final review found no unresolved correctness, architecture, security or performance blocker. No installer or release package was built.

# 2026-07-12 Phase 31 full offline release start

- User authorized a new safe, stable and environment-complete release package with a version update.
- Selected patch version 0.2.3 and the existing formal `build_installer.ps1 -FullOffline` path, which embeds both CPU and CUDA densification artifact closures in addition to all normal bundled dependencies.
- Session catch-up confirmed Phase 29/30 changes are complete and uncommitted; all of them remain in scope for this release.
- An initial parallel audit wrapper failed because one optional directory probe returned exit 1. Re-ran the important audits independently and recorded the error in `task_plan.md`.
- Downloaded the missing official CUDA torch wheel by resuming the preserved partial transfer. Exact size 3,461,384,651 bytes and SHA-256 `0ad925202387f4e7314302a1b4f8860fa824357f9b1466d7992bf276370ebcff` both match the runtime manifest; the full 73-artifact closure is now locally available.
- Updated package, npm lock root, Cargo package/lock and Tauri versions to 0.2.3 and added the 0.2.3 changelog covering PSX re-export, export acceleration/cache, transaction recovery, Metashape path hardening and full-offline packaging.
- The formal full-offline attempt passed 232 Python tests, 44 frontend tests, lint, release compilation, DLL closure and complete staging, then failed only at NSIS because its generator cannot mmap the 3.46 GB CUDA torch wheel. No incomplete installer was emitted.
- Returning to the established release contract: the formal 0.2.3 installer embeds every normal application and Metashape dependency; optional densification remains separately provisioned because its multi-gigabyte runtime exceeds the safe single-installer format.
- Formal 0.2.3 build completed in 906.6 seconds. Python 232/232, frontend 44/44, oxlint, production frontend build, two release DLL-closure checks, immutable staging and NSIS all passed.
- Installer `dist/xPano-0.2.3-windows-x64-setup.exe` is 728,538,245 bytes with SHA-256 `d56da13f6e7e2e67d68d6aa9837d1e78b4fe9a3bfa514dadfe828bc9f05d4321`; sidecar matches.
- Staging manifest version is 0.2.3 with 2,135 files, 3 Metashape wheels, 10 app wheels, both new export modules present and zero densification payload artifacts.
- Silent upgrade installed 0.2.3 into the controlled Unicode/space acceptance path. Installed manifest audit found zero unexpected missing files, zero size mismatches and zero SHA mismatches; only the designed post-install WebView2 installer deletion occurred.
- All eight installed Python entrypoints launched from an unrelated directory with `PYTHONPATH`/`PYTHONHOME` cleared. Installed EXE/WebView2 DLL closure passed, and bundled runtime readiness reported Python, FFmpeg, ffprobe, COLMAP, LichtFeld, pip and manifest ready.
- Under a PATH restricted to Windows system directories with Python/Rust/CUDA variables removed, the installed 0.2.3 GUI remained running and responsive after 12 seconds.
- Installed app Python imports OpenCV 4.10.0, NumPy 1.26.4, Pillow and piexif. The selected Metashape cp39 Python imports the locked OpenCV/NumPy versions and reports OpenCL available; installed readiness resolves the explicit Metashape executable authoritatively.
- Official npm production dependency audit reports no known vulnerabilities. Authenticode remains `NotSigned` because no publisher certificate is configured; installer SHA-256 and per-resource manifest hashes provide content-integrity evidence but do not replace publisher identity signing.
- Final Rust regression passes 88/88 after the version bump. The controlled acceptance uninstall returned 0, removed the installation directory and removed the registry entry.

# 2026-07-13 Phase 32 Metashape NumPy incident start

- User reports panorama alignment failing on multiple machines because the selected Metashape Python cannot load NumPy, while ordinary-photo processing works on another machine.
- Began evidence-first tracing of the panorama-specific Metashape launcher, Runtime Readiness provisioning and child-process environment injection. The target is automatic offline repair before Metashape imports pipeline scripts, with a reproducible regression test.
- Confirmed both the legacy and workspace reconstruction launchers call `ensure` before starting a job and preserve its `sitePackages` result. The identified gap is different: readiness validates `python.exe -c`, whereas production uses `metashape.exe -r`; their import/DLL environments have not been proven equivalent.
- User has now authorized a new versioned release package. The installer will be rebuilt only after this execution-boundary fix, regression coverage and an installed-style acceptance are complete.
- Added a shared `metashape_runtime_env` builder used by both readiness and production launch, then added a minimal `metashape_runtime_probe.py` executed through `metashape.exe -r`. Native imports are accepted only after this exact runner succeeds; offline wheel installation is committed only after it succeeds with the provisioned site-packages/DLL directories.
- Added RED/GREEN coverage for native runner gating, offline provisioning through the runner, DLL search ordering and release-stage rejection when either runtime probe file is absent. The focused readiness/app/staging suites and full Python suite pass: 236/236.
- Ran the real probe against Metashape 2.2.1: it completed in 3.6 seconds and confirmed NumPy 1.26.4/OpenCV 4.10.0 through the actual `metashape.exe -r` execution mode.
- Also changed the non-mutating Runtime Readiness status command to use the same real runner, so the UI cannot report a standalone-Python false positive while the alignment runner is broken.
- Final 0.2.4 release build passed its internal Python suite (237/237), frontend suite (44/44), oxlint, production build, two release DLL-closure gates and immutable staging. The final installer is `dist/xPano-0.2.4-windows-x64-setup.exe`, 728,549,394 bytes, SHA-256 `edfc4c91ce18d6e3773ddf8015d33075f32e7688b55c632a6b886ef47274fabb`.
- Final staged and installed release manifests both contain 2,137 files with zero unexpected missing files and zero hash/size mismatches. The only post-install removal is the designed WebView2 bootstrap installer.
- Final installed-style acceptance used a fresh temporary directory with cleared Python environment values and a system-only PATH: bundled resources and the explicit Metashape 2.2.1 runner probe were ready, the GUI remained alive after 12 seconds, and silent uninstall removed the temporary installation cleanly.
- Official production npm audit reports no known vulnerabilities. The installer remains unsigned because no Authenticode certificate is configured; SHA-256 and resource hashes establish content integrity but not publisher identity.

# 2026-07-13 Phase 33 Metashape script-local activation regression

- User immediately reported a Metashape build 22170 runner traceback at `import cv2` from the new probe. The first 0.2.4 probe relies on `PYTHONPATH`, which this runner does not apply to its script process.
- Stopped release work and selected a script-local activation path: place the verified site-packages directory directly on `sys.path` and register its native DLL directories before any optional native dependency import. This will be applied to both the readiness probe and the actual alignment script, then released as a new patch only after the user environment failure mode is covered by a regression test.
- Added RED/GREEN coverage proving that a runner-local dependency imports after activation with no `PYTHONPATH`, and that both Metashape scripts activate before optional imports. The focused readiness suite passes 14/14.
- Installed the exact locked cp39 NumPy/OpenCV wheels into a disposable external runtime, cleared `PYTHONPATH`, and launched the real Metashape runner. The probe reported both module paths inside that external runtime; the actual alignment script passed `--help` after importing `export_colmap`. This is the missing acceptance case absent from 0.2.4.
- Source gates now pass: Python 239/239, Rust 88/88, frontend 44/44, oxlint, TypeScript/Vite production build, Python compilation and `git diff --check`. The live Metashape 2.2.1 build 20221 runner also passed the external-runtime probe in 2.7 seconds with `PYTHONPATH` removed; the pipeline reached argument parsing under the same conditions.
- A source-root Runtime Readiness status probe correctly reported missing bundled FFmpeg/ffprobe because those files exist only in the formal staged application. This is not a Metashape failure and will be rechecked against the installed 0.2.5 staging tree.
- Formal 0.2.5 build completed after its own Python/frontend/DLL/staging gates. The new installer is `dist/xPano-0.2.5-windows-x64-setup.exe`, 728,585,253 bytes, SHA-256 `6abbdcf91e1eb343abc3d6f943f6fe56c9ccfbb787c7cd1a82a790e37d9e1f20`; its sidecar hash matches.
- The installer updated the existing controlled temporary 0.2.4 acceptance registration to 0.2.5 without touching the unrelated `E:\FastProgram\xPano` 0.1.1 installation. The 0.2.5 installed release manifest contains 2,137 resources; all expected retained files passed size/SHA verification, and the only absent file is the designed post-install removal of the WebView2 bootstrap installer.
- The packaged scripts passed the no-`PYTHONPATH` real Metashape runner probe and `metashape_pipeline.py --help` from an unrelated directory. Packaged Runtime Readiness reported Python, FFmpeg, ffprobe, COLMAP, LichtFeld, pip, manifest and selected Metashape ready. The GUI launched with a system-only PATH, no Python/CUDA variables, remained alive with a window handle and was responsive after 12 seconds; the test process was then stopped.

# 2026-07-13 Phase 34 build-22170 environment transport failure

- User reports that 0.2.5 still fails at probe line 12 on build 22170. The line number proves script-local activation ran first but had no path to activate. Investigation is now focused on the remaining custom environment variable transport rather than wheel packaging or DLL loading.
- Added RED tests that strip `PYTHONPATH` and `XPANO_METASHAPE_SITE_PACKAGES`, invoke the packaged probe with an explicit runtime argument, and require both alignment and re-export command builders to emit the same argument. All five relevant assertions failed against 0.2.5 as expected.
- Implemented `--xpano-site-packages` parsing/validation in the shared runtime helper, readiness probe, main Metashape pipeline and PSX re-export script. Production command builders now include the verified path explicitly and fail before launch if it does not exist. Focused readiness/pipeline tests pass 38/38.
- Real hostile-environment acceptance removed both custom variables and launched Metashape with only the explicit argument. The probe loaded NumPy 1.26.4/OpenCV 4.10.0 from the external runtime; alignment and re-export scripts both reached `--help` successfully.
- Added RED tests for the remaining Tauri-to-Python transport gap. Four focused Python assertions and one Rust assertion failed for the intended reasons before implementation.
- Tauri pipeline launch now appends `--metashape-site-packages <verified path>` to the Python script command while retaining the compatibility environment value.
- Both Python job dataclasses now retain the resolved Metashape runtime path. The tracks and legacy entrypoints accept the explicit argument, and alignment/re-export prefer the job field over the legacy environment fallback.
- GREEN verification passed: 4/4 focused Python tests, Rust transport test, and Python compilation.
- Tooling corrections: the active Python lacks pytest, so the repository's unittest runner was used; a PowerShell wildcard passed directly to `rg` and one over-complex regex were invalid, then replaced with repository-root searches.
- Release staging now requires the runtime activator, real-runner probe, main Metashape pipeline and PSX re-export entrypoint; its new RED test failed before the gate and the full staging suite now passes 11/11.
- Version metadata and changelog were advanced consistently to 0.2.6.
- Full source gates pass: Python 242/242, Rust 88/88, frontend 44/44, oxlint, production TypeScript/Vite build, Python compileall and `git diff --check`.
- Real hostile-runner acceptance passed with both `PYTHONPATH` and `XPANO_METASHAPE_SITE_PACKAGES` removed: Metashape loaded NumPy 1.26.4/OpenCV 4.10.0 from the explicit runtime path, and both production scripts reached argument parsing.
- Review found one positional-compatibility risk in the new helper/dataclass field placement; moved the new optional value to the end of the existing public parameter order before release.
- Formal 0.2.6 installer build completed in 856.7 seconds. Its internal gates passed Python 242/242, frontend 44/44, lint, production build, two DLL-closure checks, immutable staging and NSIS.
- Installer `dist/xPano-0.2.6-windows-x64-setup.exe` is 728,537,218 bytes with SHA-256 `3a722af3dfd267f2ae1a77258f4f22764628af9d69fd2591832df8a8ba4dad1c`; the sidecar matches.
- Silent upgrade installed 0.2.6 into the controlled acceptance location. Its 2,137-file release manifest had zero unexpected missing files and zero size/SHA mismatches; all four Metashape runtime/production scripts were present.
- Installed cp39 wheels created a fresh offline runtime. With a system-only PATH and no Python/custom runtime variables, real Metashape loaded NumPy 1.26.4/OpenCV 4.10.0 from that explicit path; probe, alignment and PSX re-export entrypoints all exited 0.
- Installed DLL closure passed. The GUI remained alive, responsive and had a main window after 12 seconds in the restricted environment. All eight installed Python entrypoints launched from an unrelated working directory.
- Official npm registry production audit reports no known vulnerabilities. The installer remains `NotSigned` because no publisher certificate is configured.
- Controlled acceptance uninstall exited 0, removed its directory/registry entry and left the unrelated `E:\FastProgram\xPano` 0.1.1 installation untouched.
- Acceptance correction: Runtime Readiness correctly returned an empty `sitePackages` when the local Metashape already imported native dependencies; the first harness incorrectly assumed a provisioned path was mandatory. A fresh packaged-wheel runtime was then created to exercise the missing-dependency branch explicitly.
- Audit correction: the configured npmmirror registry has no audit endpoint; reran the production audit against the official npm registry successfully.

# 2026-07-13 Phase 35 clean-machine dependency audit

- Performed a review-only inventory of every external executable and runtime activation boundary; no product source files were changed.
- Staged FFmpeg, ffprobe, embedded Python imports and COLMAP `-h` were exercised with a system-only PATH. The first three are self-contained; COLMAP success is masked by the build machine's installed VC++ Runtime.
- Recursively inspected 62 embedded-Python, 121 COLMAP and 227 LichtFeld PE files. Python and LichtFeld carry their required app-local runtime files; the formal installer carries none of COLMAP's six imported MSVC/OpenMP runtime DLLs.
- Verified the release manifest contains 2,137 files and zero COLMAP VC runtime files.
- Reproduced the densification isolation gap: embedded Python ignores external `PYTHONPATH`; with user site disabled, the bootstrap-style raw import fails while the standalone runner's script-local activation succeeds.
- Confirmed embedded Python enables the roaming user site by default, and the developer profile's Torch installation can mask clean-machine failures.
- Confirmed Runtime Readiness still reports the staged COLMAP bundle ready because it checks only file presence.
- Focused existing regression suites remain green: 33/33 release-staging, runtime-readiness and Windows-packaging tests. Their passing state does not cover the confirmed clean-machine defects.

# 2026-07-13 Phase 36 deterministic runtime hardening start

- User authorized the full long-term repair rather than another narrow incident patch.
- Selected a layered contract: fixed native payload, explicit Python activation, true readiness probes, recursive release closure, and isolated acceptance.
- Confirmed the bundled LichtFeld directory contains the complete six-file COLMAP runtime set at version 14.44.35211 and recorded their SHA-256 values for a dedicated payload manifest.
- No installer will be built until source and staged acceptance pass; the current turn targets implementation and verification only.

# 2026-07-13 Phase 36 deterministic runtime hardening complete

- Added RED/GREEN coverage for native payload staging, corrupt payload rejection, fixed inbox classification, densification script-local activation, user-site isolation and real tool probes.
- Added and staged the verified six-file Windows runtime payload beside COLMAP and embedded Python; removed the legacy System32 copy fallback.
- Added explicit densification site-packages transport through bootstrap, standalone runner, viewer and Tauri, with retained DLL-directory handles and CPU/CUDA self-tests.
- Changed readiness from existence checks to real bounded process starts and added Media Feature Pack diagnostics.
- Added recursive release-tree PE gates and validated the fresh stage's 420 PE files.
- Found and removed the remaining ambient `tqdm` dependency by adding its verified offline wheel and embedded install contract.
- Passed full Python, Rust and frontend suites, lint/build, PowerShell syntax, diff checks, real Metashape probe, explicit densification import probe and restricted release-stage acceptance.
- Installer creation was intentionally skipped per scope.

# 2026-07-13 xPano 0.2.7 release start

- User approved building the installer after Phase 36 acceptance.
- Advanced package, npm lock root, Cargo package/lock, Tauri and changelog versions to 0.2.7.
- Selected the normal formal installer boundary: all application/Metashape/native dependencies are embedded; the optional multi-gigabyte densification runtime remains separately provisioned as previously designed.

# 2026-07-13 xPano 0.2.7 release complete

- Formal build completed in 988.3 seconds. Python 251/251, frontend 44/44, oxlint, two Rust release builds, application DLL closure, release staging and NSIS all passed.
- Recursive staged PE gates passed for 66 embedded-Python, 127 COLMAP and 227 LichtFeld files.
- Published `dist/xPano-0.2.7-windows-x64-setup.exe`, 728,658,140 bytes, SHA-256 `102935e410182136039142a5171d2b903516be4c91e18e209e72ad50ea44f169`; sidecar matches.
- Release manifest version 0.2.7 contains 2,199 files and includes the complete app-local VC/OpenMP set, runtime activators and offline `tqdm` wheel.
- Silent controlled installation passed all 2,199 size/hash checks except the intentionally removed WebView2 bootstrap installer. No unexpected missing file, size mismatch or hash mismatch was found.
- Installed Runtime Readiness passed COLMAP and explicit Metashape cp39 probes under a system-only PATH with user site disabled. The hidden GUI remained alive, responsive and had a main window after 15 seconds.
- Controlled uninstall returned 0 and removed the acceptance directory while preserving the unrelated `E:\FastProgram\xPano` 0.1.1 installation.
# 2026-07-14 Metashape single-match backbone implementation plan

- Used the planning-with-files workflow and recovered the existing long-running project context without altering current product changes.
- Re-read the Python matching/import path, mocked alignment tests, Rust execution-plan generator, frontend stage fixtures, workflow documentation, and live Metashape API help.
- Produced `docs/METASHAPE_SINGLE_MATCH_BACKBONE_FIX_PLAN.md` with the exact target algorithm, file-by-file edits, test-first sequence, native acceptance matrix, failure rules, and 25 implementation traps.
- No business code, release metadata, runtime payload, or installer was changed or built in this planning turn.

# 2026-07-14 Metashape single-match backbone implementation

- Converted the mixed backbone RED tests from the old two-match sequence to the required single unified match followed by separate panorama and flat-camera alignment.
- Confirmed the RED state against the previous implementation: flat photos were absent before the first match and the emitted stages still named `pano.match` then `frame.match`.
- Implemented a fresh-chunk unified match with `keep_keypoints=False`, panorama-only and flat-only branches, explicit camera-set validation, bounded sensor diagnostics, and an import-boundary rejection for incompatible source sensor geometry.
- Added focused coverage for panorama-only, flat-only, wrong sensor type, and source sensor dimension mismatch. `python -m unittest tests.test_metashape_alignment_modes` passes 10/10.
- Replaced the Rust backbone execution graph's two old match nodes with `frame.import -> pano.station -> all.match`, retained staged panorama/frame alignment, and added a RED/GREEN exact graph, dependency, and weight-sum test.
- Updated development preview stages and workflow/specification documents. A real EXIF Orientation 1/6/8 Metashape probe confirmed that build 20221 uses raw stored sensor geometry, so no orientation grouping rewrite is justified.

# 2026-07-14 Metashape single-match backbone verification

- Completed independent review of the new one-match backbone behavior and expanded validation regression coverage from 10 to 15 focused tests.
- Passed source gates: Python 260/260, Rust 89/89, frontend 44/44, oxlint, production frontend build, `compileall`, and diff check.
- Ran a fresh real Metashape 2.2.1 build 20221 job at default 40,000 keypoints using three panorama stations plus eight flat photos; the project saved and reopened, and image/COLMAP outputs were created in `C:\Users\Beluga\AppData\Local\Temp\xpano-single-match-20221-acceptance`.
- Build 22170 and the incident-scale dataset are not installed on this machine. The implementation is not release-accepted until that explicit native gate is run.

# 2026-07-14 Medium real Metashape acceptance

- Ran build 20221 against the retained `alignment_00000003.json` test manifest in a new temporary project: 167 panorama stations / 334 fisheye cameras plus 138 flat photos.
- Captured log confirms one `MatchPhotos` invocation, staged panorama then flat alignment, no native assertion/traceback, successful project save and `output.validate`.
- Reopened the resulting PSX with the real Metashape runner: 472 cameras, all 472 aligned, three sensors. Export contains 1,808 JPEG images and COLMAP `cameras.bin`, `images.bin`, and `points3D.bin`.
- This materially strengthens source acceptance, but the build 22170 plus incident-scale `2880x2880 + 6000x4000` run remains an explicit pending gate; no release/version update was performed.

# 2026-07-14 Nearby 2.3 build regression correction

- Build 21778 initially avoided the native assertion but produced only 459/472 aligned cameras. A same-build panorama-only baseline aligned all 334 fisheye cameras, establishing a real mixed-backbone quality regression.
- Added a test-first Frame-camera isolation boundary: after the single all-camera match, Frame cameras are disabled during panorama alignment/optimization and their original enabled states are restored before incremental Frame alignment.
- Corrected build-21778 medium acceptance completed with 472/472 aligned cameras, one `MatchPhotos` call, no native exception/assertion, PSX reopen, 1,808 exported JPEGs, COLMAP binaries and `output.validate`.
- Re-ran Python source suite: 260/260 pass. `cargo fmt --check` is unavailable because the installed GNU Rust toolchain lacks `rustfmt`; no toolchain modification was made.

# 2026-07-14 Build-22170 execution-handoff review

- Reconfirmed the production failure boundary from the incident stack trace: the old backbone invoked a second `matchPhotos` on an already-matched mixed-resolution chunk (`2880x2880` panoramas plus `6000x4000` frames), which reaches a Metashape-native assertion. xPano must avoid that call sequence rather than suppressing the native error.
- Reconfirmed the landed source shape and nearby-build evidence: one unrestricted all-camera match, Frame-camera isolation during the panorama solve, then incremental Frame alignment. Build 21778 accepted 472/472 cameras with one native `MatchPhotos` invocation and complete export.
- Prepared a code-agent execution handoff that adds a reusable read-only native-run verifier before claiming build-22170 completion. Exact build 22170 and the incident-scale material remain the unreplaced release gate; no product source, version, package, or installer was changed in this review.

# 2026-07-14 Repeatable Metashape Backbone acceptance evidence

- Added `scripts/verify_metashape_backbone_acceptance.py` with RED/GREEN tests. It requires exactly one native `MatchPhotos:` log line, the staged mixed-Backbone order, no assertion/traceback/exception marker, a non-empty PSX, a Backbone alignment summary with expected counts, and a complete single-sparse COLMAP export.
- The verifier stays intentionally read-only and reuses `verify_xpano_output.py`; existing `diagnose_metashape_project.py` remains the native PSX-reopen check, avoiding a duplicate project parser.
- The focused verifier suite passes 5/5. Full Python suite passes 265/265, `compileall` and `git diff --check` pass.
- The corrected build-21778 real output passes with explicit expected values: 472/472 cameras, 3 sensors, 1,670 cubemap images, 138 Frame images, 1,808 COLMAP images, 11 COLMAP camera models and 578,685 points. Direct CLI execution from an unrelated working directory also passes.
- Updated the build-22170 plan with the exact native-reopen and read-only verifier commands. Build 22170 and the incident-scale material remain unavailable locally, so no release/version change is authorized or claimed.

# 2026-07-14 Phase 40 xPano 0.2.8 release

- Resumed from the prior release audit and confirmed the working tree still contains the cumulative 0.2.4-0.2.7 work on top of commit `40e1f11`.
- Selected version 0.2.8 because every existing 0.2.7 user-facing artifact predates the single-match repair.
- Began the TDD phase for per-type metrics, evidence binding, mandatory expectations, and native-error state restoration.
- RED verification completed: focused tests failed because summaries lacked per-type metrics, the verifier lacked per-type arguments and project binding, and acceptance allowed omitted expectations. The new native-error restoration regression already passed against Terra's existing `finally` implementation.
- Real build-21778 rerun attempt 1 did not enter the script: PowerShell promoted native stderr to a terminating `NativeCommandError` before the wrapper could preserve the traceback. The next attempt uses `Start-Process` with explicit stdout/stderr files and exit-code capture.
- Real build-21778 rerun attempt 2 captured the actual pre-script failure: the selected temporary cp39 NumPy runtime cannot load in this Metashape process (`No module named numpy.core._multiarray_umath`). Before retrying, probe the runner's Python ABI and construct a matching runtime from the repository's locked offline wheels.
- The ABI probe identified Metashape build 21778 as CPython 3.12.12. The first cp312 provisioning command selected the production embedded Python, which intentionally has no pip; switch to the available system Python 3.12 pip while retaining `--no-index`, `--no-deps`, and repository-local wheels.
- The current-source 21778 run completed in 765.4 seconds with one match and full export, but reopened at panorama 325/334 and flat 138/138. A memory-only retry of `alignCameras` for the nine unaligned panorama keys reused existing matches and reached 334/334 in 18 seconds, establishing the minimal stabilization path.
- Added a RED/GREEN regression and bounded production retry for only unaligned panorama keys. The retry stays inside the flat-camera isolation `try/finally`, performs no additional matching, and stops the pipeline if the native retry throws.

# 2026-07-14 Phase 41 Metashape fidelity research

- Paused release work at the user's request. Began an analysis-only audit of xPano's complete alignment/export chain against official Metashape 2.2 and 2.3 documentation.
- The investigation explicitly distinguishes native camera alignment errors from later auto-level/COLMAP/viewer transform errors; these produce similar "chaotic" symptoms but require different fixes.
- Downloaded and extracted the official Metashape Pro 2.2/2.3 manuals and Python API 2.2.2/2.3.0 references, and reviewed Agisoft's official spherical-panorama tutorials.
- Completed a source-to-document comparison for calibration groups, fisheye projections, Station and rigid-rig semantics, matching defaults, video import, components, optimization, reference accuracy and result-quality metrics.
- Found the primary confirmed native defect: xPano releases every dual-fisheye Station to Folder before optimization. A retained real PSX shows former station baselines of 0.863 and 1.916 against a component diagonal of 16.293, proving that paired hemispheres can separate at scene scale while the run is still accepted.
- Found a second confirmed acceptance/export defect: xPano does not reject multiple Metashape components and exports all transformed cameras against the active tie-point cloud. The same retained PSX contains two independently transformed components.
- Confirmed there is no production minimum-alignment gate: the retained 6/14-camera run continued to COLMAP export and wrote 30 cubemap images.
- Ranked the default panorama-first Backbone solve, universal synthetic lens models, fixed-time video sampling/metadata loss and non-default match/reference flags as strong causes of native divergence from a successful GUI workflow.
- No product source, release metadata, package or installer was changed. Phase 41 is complete as an analysis-only audit.
# 2026-07-14 Phase 42 xPano 0.1.0 alignment regression audit start

- Began an analysis-only comparison between `C:\Users\Beluga\Downloads\xPano-0.1.0` and the current worktree.
- The audit targets causal changes in Metashape import/calibration, Station constraints, matching/alignment/optimization order, component validation, and export selection.
- No product source or release artifact will be changed in this phase.
# 2026-07-14 Phase 42 xPano 0.1.0 alignment regression audit complete

- Confirmed the downloaded 0.1.0 directory is not identical to the repository tag, so the comparison used the downloaded source as the old behavioral baseline.
- Compared old and current import, calibration, matching, Station/Folder lifecycle, alignment subsets, optimization, export selection and GPU settings.
- Native 2.2.1/2.3.0 probes show `Fisheye` and `EquidistantFisheye` produce identical zero-distortion projections; the enum rename is not the large-error cause.
- Ranked the active single-pass all-camera matching before panorama solve as the primary regression risk, with changed camera-subset alignment and CPU/GPU policy as secondary differences.
- Recorded shared Station-release drift and multi-Component export defects separately; they are real but not uniquely introduced by the current version.
- Same-manifest old-pipeline rerun was stopped after the diagnostic timeout inside native alignment and is explicitly not treated as acceptance evidence.
- No product source, release metadata, or installer was changed.
# 2026-07-14 Workspace evidence review complete

- Reviewed `C:\Users\Beluga\Downloads\test` without modifying product code or running alignment.
- Found a legacy schema-1 single-OSV run with 440 frames / 880 cameras, 100% transform count, and successful export.
- Found severe Station baseline variation (0.0055 to 0.0533, approximately 9.6x), proving that alignment-rate-only acceptance can hide incorrect dual-fisheye geometry.
- Ground alignment statistics are healthy but do not validate camera poses; no PSX or native log was provided, so exact root-cause localization remains bounded.
# 2026-07-14 Corrected comparison with `false` workspace

- Reclassified `C:\Users\Beluga\Downloads\test` as the user's old correct output and inspected `C:\Users\Beluga\Downloads\false` as the new bad output.
- Confirmed both use the same single OSV, 440 frames and 880 cameras.
- Found the new job failed at `metashape.pano.match` but a subsequent export job completed; the project was incorrectly marked complete despite only 436/880 cameras being aligned.
- The new partial output contains exactly 2,180 cubemap images, consistent with exporting only 436 aligned cameras.
- This is a workflow failure-propagation/export-gating bug first; no automatic bad-camera repair is justified by these files.

# 2026-07-14 Phase 43 implementation complete

- Added a dependency-free Component selection contract shared by normal export, PSX re-export, and structured reporting.
- Metashape jobs now begin with a non-success report and only mark it successful after PSX save and isolated export complete; Rust rejects completion from failed/interrupted state or a missing/non-success report.
- Failed current runs retain `work/xpano.psx` and can enter the explicit PSX re-export plan without allowing automatic recovery from leftover COLMAP files.
- The reconstruction monitor now displays aligned/total cameras, warning text, and a Component selector for re-export when multiple Components exist.
- Panorama-only Backbone matching/alignment is whole-chunk and keeps dual-fisheye groups as Stations during optimization.
- Static/mock acceptance passed: Python unit suite, Rust unit suite, Python compilation, TypeScript compilation, and Vite production build. No Metashape or real material run was executed.

# 2026-07-14 Phase 44 started

- Confirmed both `run_backbone_alignment` with mixed materials and explicit `run_mixed_alignment` still convert panorama groups from Station to Folder before optimization.
- Scope is limited to retaining panorama Station groups and synchronizing tests/stage wording; no native or real-material acceptance will run.

# 2026-07-14 Phase 44 complete

- Added RED regressions for Backbone mixed-material and explicit Mixed optimization, then removed both Station-to-Folder transitions.
- Panorama groups now remain Station through panorama optimization, flat-camera attachment, and final global optimization; flat-camera groups remain Folder.
- Kept matching, staged camera solves, retry behavior, optimization parameters, and stage IDs unchanged; synchronized stage wording and workflow documentation.
- Static/mock acceptance passed: 279 Python tests, 91 Rust tests, 44 frontend unit tests, frontend lint, Python compilation, and the production frontend build.
- Five-axis review found no blocking correctness, simplicity, architecture, security, or performance issue. No Metashape run, real-material test, installer build, or version bump was performed.

# 2026-07-14 Phase 45 started

- User authorized a new installer release identified as `0.2.9-preview`.
- Confirmed the authoritative standard installer pipeline reruns unit/lint gates, release builds, release staging validation, recursive DLL closure checks, NSIS bundling, and SHA-256 generation.
- The standard package retains the project's bundled application, Metashape wheel, COLMAP, FFmpeg, and LichtFeld contracts; the optional multi-gigabyte full-offline densification payload is outside this release request.
- Synchronized Cargo, Tauri, npm and lockfile metadata to `0.2.9-preview` and added the prerelease changelog entry.
- Pre-build gates passed: 279 Python tests, 91 Rust tests, 44 frontend unit tests, and frontend lint.
- Added and verified a staging regression gate for `component_selection.py`; the focused release-staging and Windows-packaging suites now pass 22/22.
- The authoritative installer build passed 280 Python tests, 44 frontend tests, frontend lint/build, Cargo release builds, Tauri bundle creation, and recursive DLL closure for 66 Python, 127 COLMAP, 227 LichtFeld, plus the launcher PE files.
- Produced `dist/xPano-0.2.9-preview-windows-x64-setup.exe` at 728,693,656 bytes with SHA-256 `3c8f1719a604d9f3878bf583474e62dab685a998023c7a6fe67bcbc8865a27f7`.
- Verified all 2,201 release-manifest file sizes and hashes, the staged version, installer/sidecar hash equality, and Windows version metadata. No installation, commit, tag, or full-offline densification package was created.

# 2026-07-14 Phase 46 started

- Triaged the reported panorama-plus-photo failure to the `metashape.frame.import` boundary in the exact `0.2.9-preview` source.
- Selected a general geometry-partition fix instead of removing validation, forcing one sensor, or changing matching/alignment behavior.
- Added a RED regression for landscape and portrait photos in one declared sensor group, then changed import to create one Frame sensor per actual Metashape source-sensor geometry partition.
- Updated the single-match design contract to document geometry partitioning rather than obsolete whole-project rejection.

# 2026-07-14 Phase 46 complete

- Focused Metashape alignment-mode tests pass 20/20, including the geometry split and single bounded diagnostic.
- Full source gates pass: Python 280/280, Rust 91/91, frontend 44/44, frontend lint/build, Python `compileall`, and `git diff --check`.
- Five-axis review found no blocking issue. Matching, Station retention, alignment, optimization, component selection, export, runtime provisioning, and release metadata were not changed by this incident fix.
- No installer was built. The current `dist/xPano-0.2.9-preview-windows-x64-setup.exe` predates Phase 46 and must not be presented as containing this repair.

# 2026-07-14 Phase 47 started

- User authorized the exact release identifier `0.2.9-preview-7142057camerafix`.
- Confirmed the existing `0.2.9-preview` artifact is stale and selected the standard verified NSIS pipeline, not the optional full-offline densification package.
- Synchronized npm, package lock, Cargo, Cargo lock and Tauri metadata to `0.2.9-preview-7142057camerafix`; `pnpm-lock.yaml` has no application-version field.
- Added a changelog entry limited to the mixed-photo actual-geometry partition fix and its accepted test evidence.
- Versioned preflight passed: 42 focused Camera/release tests, 91 Rust tests, exact npm/Cargo/Tauri version parsing, prerequisite discovery, and workspace/disk checks.

# 2026-07-14 Phase 47 complete

- The authoritative standard installer build completed successfully in 742 seconds, rerunning Python 280/280, frontend 44/44, lint/build, two Rust release builds, release staging and NSIS packaging.
- Recursive DLL closure passed for the launcher/WebView pair and for 66 embedded-Python, 127 COLMAP and 227 LichtFeld PE files.
- Published `dist/xPano-0.2.9-preview-7142057camerafix-windows-x64-setup.exe`, 728,670,865 bytes, SHA-256 `b8b5441ed5f243754f85847852c7edb664066d7c9db3de570d46f399443db92b`.
- Independently verified the sidecar, both Windows version fields, all 2,201 manifest entries, and byte-identical staged/source Camera-fix pipeline. No installation, commit, tag, signing, or full-offline densification package was performed.

# 2026-07-14 Phase 48 started

- User reported the Camera-fix package still fails at `metashape.frame.import` and requested analysis only.
- New log evidence proves the geometry split executes but reveals one declared ordinary-photo group with same-size Fisheye and Frame source sensors.
- Confirmed the package traceback maps to current lines 803/866 and traced the import sequence through panorama-first sensor creation, used-sensor retention, flat import, geometry partitioning and Frame normalization.
- Identified the failing label as an ordinary-video track with uniform synthetic EXIF; ruled out mixed camera identity within the manifest as the reason for its Fisheye/Frame source split.
- Audited the prior regression and confirmed it only models dimension differences with isolated fake sensors; it does not model the native Fisheye/Frame conflict now observed.
- Confirmed official addPhotos defaults and validated the local 2.2.1 native runner for a temporary sensor-reuse probe.
- Native 2.2.1 reproduction reached the same split and captured the full downstream exception, identifying positional `chunk.cameras` slicing across Metashape reorder as the root cause.
- Enhanced the temporary diagnostic probe to print camera key/path order before and after every native `addPhotos`, plus positional and key-difference selections. No product code was changed.
- The native trace proved `addPhotos` reorders cameras: the second panorama import changed `[0, 1]` to `[0, 2, 1, 3]`, and the ordinary-frame import placed new keys `[4, 5, 6, 7]` before old panorama keys `[0, 2, 1, 3]`.
- Re-ran the native probe with only the inner selector temporarily corrected. All sensor assignments became correct, but the outer `_new_cameras_since` slice still classified the old panorama keys as the ordinary-frame track and produced the same validation failure. This independently proves both positional defects.
- Audited all Python camera-list position uses and confirmed the repair scope is limited to the two import identity selectors in `metashape_pipeline.py`; no matching, Station, alignment, component or export logic participates in this failure.
- Completed Phase 48 as analysis only. No production source, tests, version metadata, installer or release artifact was modified.

# 2026-07-14 Phase 49 started

- Added a `ReorderingFakeChunk` regression that places each newly imported batch before existing cameras, matching the native Metashape behavior observed in Phase 48.
- The focused mixed panorama-plus-photo test fails on the unmodified implementation with `Panorama and flat camera sets overlap or contain duplicate camera keys`, reproducing the user failure before the fix.
- Replaced both positional selectors with one key-difference import contract and direct return of per-track camera objects. Added fail-fast count and normalized-path validation without changing matching or alignment behavior.
- The three focused RED tests now pass, and the complete Metashape alignment-mode suite passes 23/23.
- The real Metashape 2.2.1 build 20221 probe passes with the production helper: panorama keys 0-3 remain Fisheye, ordinary-frame keys 4-7 remain Frame, and validation reports `PROBE_RESULT:PASS`.
- Full source gates pass: Python 283/283, Rust 91/91, frontend 44/44, frontend lint/build, Python compilation and repository-wide diff checks.
- The existing advanced `mixed` alignment regression now also uses the reordering fake and passes, covering both manifest import entry points.
- Five-axis review found no blocker. The repair is one import-boundary invariant plus direct object propagation, adds no dependency or persistent state, and leaves matching, Station, alignment, component selection and export unchanged.
- Phase 49 is complete. No installer, release artifact, commit or version change was produced.

# 2026-07-14 Phase 50 started

- Selected release identifier `0.2.9-preview-cameraidentityfix` for the stable Camera-key mixed-import repair.
- Confirmed this is the standard Windows x64 installer boundary; the optional multi-gigabyte full-offline densification payload is not part of this request.
- Synchronized npm/package lock, Cargo/Cargo lock and Tauri metadata to `0.2.9-preview-cameraidentityfix` and added the release changelog entry.
- Version parsing, prerequisite discovery, repository diff checks and 45 focused Camera/release tests passed before packaging.

# 2026-07-14 Phase 50 complete

- The authoritative `scripts/build_installer.ps1` pipeline completed in 738.2 seconds and produced `dist/xPano-0.2.9-preview-cameraidentityfix-windows-x64-setup.exe`.
- Packaging reran and passed 283 Python tests, 44 frontend tests, frontend lint/build, two Rust release builds, release staging, recursive DLL closure and NSIS generation; the previously accepted Rust suite remains 91/91.
- Independently recomputed installer SHA-256 `981e94cb384b4da8400bbc5222333f985bbd4a317c06995afdd73d44afc26035`; it exactly matches the generated sidecar.
- Verified the 728,709,031-byte installer has both Windows `FileVersion` and `ProductVersion` set to `0.2.9-preview-cameraidentityfix`.
- Verified all 2,201 release-manifest entries by existence, size and SHA-256, and confirmed the manifest version is exact.
- Confirmed staged `scripts/metashape_pipeline.py` is byte-identical to source at SHA-256 `c65d5bffab0a1b3050ca9fd5d55cfeda0947b27d129c2c95b5312d8bfc7f1a88`, contains key-difference/count/path validation, and contains no `_new_cameras_since` selector.
- Re-ran the 23 focused Metashape alignment tests, Python compilation and repository-wide diff checks successfully after packaging.
- Five-axis release review found no blocking correctness, readability, architecture, security or performance issue. The installer remains unsigned; no installation, commit, tag, push or full-offline densification package was performed.

# 2026-07-15 Phase 51 started

- User redirected work from PR inspection to a design-only LichtFeld training workspace redesign.
- Scope is current UI, information architecture, state presentation, responsive behavior and an implementation plan; no UI code will be changed in this phase.
- Initial search locates the training feature under `xpano-ui/src/features/training` with shared task state in `ProjectProvider`, Tauri contracts and `training.rs`.
- Read the complete 214-line workspace and configuration contract. The current implementation combines configuration, technical readiness, execution monitoring and diagnostics in one always-visible two-panel dashboard.
- Identified the primary design defects as equal visual weight, nested card fragmentation, 8-10 px typography, developer/runtime copy in the default path, a detached primary action, misleading editable controls during runs, and no explicit narrow-layout strategy.
- Audited AppShell and the design tokens. The training workspace sits below a global title/environment bar and above a global workflow/job dock, with a 1024x720 minimum application size and existing light/dark semantic tokens.
- Visually inspected the stored 1024x720 and 1280x800 training screenshots. They confirm that the idle terminal dominates, repeated nested rectangles flatten hierarchy, and the configuration panel clips at minimum size.
- Audited the training backend contract and confirmed the redesign can represent idle/running/complete/failed/interrupted states, persisted metrics and output actions without inventing a second state model.
- Compared fixed split-pane, manual-tab and wizard alternatives. Selected a state-adaptive task workspace because it removes empty monitoring, prevents state/view mismatch and preserves fast repeat training.
- Completed the design-only plan in `docs/LFS_TRAINING_WORKSPACE_UI_REDESIGN_PLAN.md`, including setup/running/completed wireframes, copy cleanup, design tokens, responsive behavior, component boundaries, implementation order and acceptance criteria.
- No product UI, backend behavior, dependency or release artifact was changed in Phase 51.

# 2026-07-15 Phase 52 started

- User approved the recorded LFS training workspace redesign for implementation.
- Confirmed `trainingConfig.test.ts` is the focused small-test boundary and the existing frontend suite uses Node's built-in test runner.
- Confirmed no existing user diff overlaps `TrainingWorkspace.tsx` or `trainingConfig.ts`; unrelated dirty-worktree changes will be preserved.
- Implementation will reuse the existing Tauri training state, progress stream, `open_output_folder` command and AppShell tokens without backend protocol or dependency changes.
- Added RED tests for preset derivation, state-to-view mapping and actionable start blockers. The focused suite fails because the three new exports do not exist, confirming the tests exercise missing behavior rather than passing against current code.
- Implemented the pure view model and extracted setup/task-state components. The first TypeScript gate found only two unused icon imports; they were removed before runtime verification.
- Focused tests, TypeScript and lint then passed. Replaced the fixed training dashboard with a setup view, state-specific task view, bounded diagnostics drawer and an orchestration-only workspace component.
- Added development-only `training`, `training-running`, `training-complete`, `training-failed` and `training-interrupted` fixture modes for deterministic browser acceptance; production runtime behavior is unchanged.
- Full frontend acceptance passed at the source gate: 47/47 unit tests, lint, TypeScript and production Vite build.
- Vite preview started successfully on `http://127.0.0.1:1420`. The first headed Chrome Playwright session exited before opening, so visual acceptance is continuing through a different headless browser path.
- Headless Edge acceptance succeeded with zero browser errors/warnings. The setup view was inspected at 1280x800 and 1024x720; the primary action remains visible at minimum size and advanced settings scroll independently.
- User explicitly accepted the current rendered UI and requested close-out. The Playwright session and Vite server were stopped.
- Final five-axis review found no blocker: state mapping and blockers are tested, component responsibilities are narrow, no backend/dependency/security boundary changed, logs remain bounded to 120 visible entries, and development fixtures are compile-time DEV-only.
- Phase 52 is complete. No installer, version bump, commit or release package was created.

# 2026-07-15 Phase 53 started

- User reports that source-launched LichtFeld trains normally, while the xPano installation at `E:\FastProgram\xPano` repeatedly reports a missing `rmlui/rendering.rml`, renders an incomplete LichtFeld UI and cancels training.
- The screenshot points to a runtime asset-resolution failure after the executable has already started; diagnosis will compare installed, staged, bundled and original LFS layouts before any code or packaging change.
- Scope is diagnosis-only until the exact root cause and minimal repair boundary are established.
- The first parallel inventory failed at PowerShell parse time and changed nothing. The query is being retried with explicit result collection so missing files remain distinguishable from command failure.
- Confirmed all four runtime roots exist. The installed `rendering.rml` is present at the exact path reported missing and has the same size as source, release-stage, Tauri release and original LFS copies.
- The investigation has moved from packaging inclusion to path semantics and launch context, with the installed `\\?\E:\...` executable-directory form as the strongest current lead.
- Verified byte identity of the failing asset and exact file/byte counts across all `share` trees. Normal and extended-length paths are both readable from PowerShell, ruling out omission, corruption and ACL-level denial.
- Reproduced the installed LFS directly: normal-path launch loaded themes successfully; extended-path launch reported missing existing locale and icon files. The same binary and resources were used in both runs.
- A native MinGW `std::filesystem` probe showed the exact mechanism: extended-prefix paths with LFS's mixed forward/backslash separators return `exists=false`; normal paths and all-backslash extended paths succeed.
- Root cause is now confirmed at the xPano child-launch path normalization boundary. No product code or packaging artifact has been modified.

# 2026-07-15 Phase 54 started

- User accepted the current behavior and requested a standard `1.0.0-preview` installer.
- Release scope includes the confirmed LichtFeld verbatim-path launch repair, version synchronization, full source gates, installer construction and artifact verification; no commit, tag or external publication is authorized.
- Added RED Rust regressions for drive and UNC verbatim paths. The focused test failed at compile time because `tool_resolver::plain_windows_path` did not exist, proving the resolver boundary was not yet covered.
- Moved the existing path conversion from `lib.rs` into `tool_resolver`, updated all existing callers, and normalized the LichtFeld `--executable` argument. Both focused regressions now pass.
- `cargo fmt --check` could not run because the active GNU Rust toolchain has no `rustfmt` component. No formatter was installed automatically; formatting will be checked with an available toolchain or by the release compiler.
- Full source gates passed: Rust 93/93, Python 283/283, frontend 47/47, frontend lint and production Vite build. `git diff --check` reported no whitespace errors in the changed product files.
- The available LLVM `rustfmt` binary is a different formatter/toolchain and reports pre-existing formatting differences across the dirty Rust tree; it was not used to rewrite unrelated files. Compilation and tests remain green.

# 2026-07-15 Phase 54 release verification

- Rebuilt the standard Windows x64 NSIS installer after the final path-normalization and regression-test changes. The build completed with the repository's Python, frontend, Rust, staging, DLL-closure and packaging gates.
- Final installer: `dist/xPano-1.0.0-preview-windows-x64-setup.exe`, 728,650,129 bytes, SHA-256 `F9AA3E252E57232DC1C040C80EAB4CA76804370B5304A10ACE442F5ADAFE0D89`; the generated sidecar matches.
- Independently verified `build/release-stage/release-manifest.json`: exact version `1.0.0-preview`, 2,201 entries, zero missing files and zero size/SHA-256 mismatches.
- Rechecked the staged Python entrypoints against source; all selected production scripts are byte-identical. No installer-build, NSIS or LFS process remains active. The already-running installed `xpano-ui.exe` is unrelated to packaging and was left untouched.
- Phase 54 is complete. No commit, tag or external publication was created.

# 2026-07-17 Phase 55 started

- User reports broad field evidence that current xPano aligns worse than `0.1.0` even with the same Metashape version and separately reports that xPano shows only one Component when the PSX contains two.
- Investigation is diagnosis-only and will compare behavior rather than release labels: import manifest, extraction/resolution/EXIF, sensor identity/model/group, match/alignment/optimization stages, camera-state transitions, Component inventory and export filtering.
- Confirmed the old source tree exists at `C:\Users\Beluga\Downloads\xPano-0.1.0`; current source is `D:\CodeFiles\360gaussain`. No source, test, version or package has been modified.

# 2026-07-17 Phase 55 completed

- Compared the full import, extraction, sensor, matching, alignment, optimization, report and export paths against the downloaded `0.1.0` source and official Metashape 2.3 manual/API.
- Ruled out hidden image downscaling, default frame truncation, hardware decode and JPEG pixel differences. Current panorama frames remain 3840x3840; standard photos are not resized.
- Confirmed the primary mixed-material regression: the old documented panorama-first incremental workflow was replaced by one global match graph followed by subset solves. Flat cameras already influence matching before they are disabled.
- Confirmed a separate pure-panorama pre-solve regression boundary in sensor/calibration initialization. Native 2.3 probes show old and current start from materially different model/calibration states despite equivalent tested projection formulas.
- Opened the real PSX through Metashape 2.3 and proved it contains Components of 458, 221 and 177 cameras, with 24 unassigned. xPano reports only 458 because transforms and tie points are active-Component scoped.
- Proved selection/export does not activate the requested Component and the UI relies on a stale persisted report rather than current PSX state. Phase 55 is diagnosis-complete; no product source or package was changed.

# 2026-07-17 Phase 56 started

- User authorized restoring the alignment process and initial calibration to `0.1.0` behavior, and explicitly requested the progress/display chain be updated at the same time.
- Scope is panorama calibration bootstrap, panorama-first incremental alignment, execution-plan/stage truthfulness and regression tests. Component selection remains a separately confirmed defect and is not being mixed into this change.
- RED coverage first proved the current implementation differed from the initial calibration and staged call order. The restored implementation now passes the focused Python and Rust contract tests.
- Removed the reachable one-pass Metashape branch while preserving old `mixed` configuration input as an alias for the stable staged workflow. Updated the settings surfaces and development progress preview so users cannot select or see a graph that the runtime no longer executes.
- Full acceptance passed: Python 284/284 with one intentional skip, Rust 94/94, frontend 47/47, frontend lint, TypeScript/Vite production build, Python compilation and diff whitespace checks. No real dataset alignment or installer build was performed.
- Final correctness/readability/architecture/security/performance review found no blocker. The second match is an intentional restoration of the verified incremental workflow; no new dependency, subprocess boundary or unbounded UI work was introduced.

# 2026-07-17 Phase 56 completed

- Restored the initial-release panorama calibration and staged Metashape execution contract across backend, execution plan and UI progress surfaces.
- Component inventory/export remains the next separate repair boundary and was not changed in this phase.

# 2026-07-17 Phase 57 started

- User requested a concrete optimization plan for the confirmed Component inventory/selection/export defect.
- This phase is design-only. It will trace the current PSX-to-Python-to-Rust-to-frontend contract, then specify the smallest implementation and acceptance sequence without changing runtime behavior.
- Confirmed the primary ownership boundary: Python inventory and export read active-Component-scoped transforms without switching `chunk.component`; Rust and React only preserve and display the resulting incomplete report.
- Confirmed Rust report validation can remain strict once Python inventory is correct, and the existing re-export transaction is the right publication boundary.
- One source search used a PowerShell-incompatible wildcard path (`tests/test_reexport*`) and returned an invalid filename error. No files changed; subsequent searches will use `rg` include globs instead of shell wildcards.
- Confirmed initial alignment has no explicit Component request and should choose the largest automatically; re-export carries an explicit UI selection and requires strict missing-key handling.
- Expanded the activation boundary to include ground-plane leveling because it reads active Component tie points before export.
- Selected the interaction design for the plan: read-only PSX inspection on re-export click, conditional Component confirmation, then strict transactional export of the confirmed key. This avoids both stale selection and an unnecessary first export.
- Release staging will automatically copy a new Python inspector but needs an explicit required-file regression. A search also referenced nonexistent `scripts/build_release.py`; the relevant staging implementation is `scripts/release_staging.py`, which was inspected instead.
- Completed the design in `docs/METASHAPE_COMPONENT_REPAIR_PLAN.md`: one activation/restoration helper, truthful schema-v2 inventory, selected-Component leveling/export, read-only live PSX inspection, conditional selection dialog, strict revalidation and transactional publication.
- Defined Python, Rust, frontend, staging and native acceptance tests, including the known 458/221/177 Component PSX. No runtime code, project output or installer was changed.
- The planning completeness helper still reports older historical release phases as in progress; Phase 57 itself is complete and those unrelated deferred phases were intentionally left unchanged.

# 2026-07-17 Phase 58 started

- User approved implementation of the Component repair plan.
- Work begins with a dynamic fake chunk that reproduces Metashape's active-Component-scoped transforms and tie points before product code changes.
- RED confirmed: `tests.test_component_selection` fails because the active-Component inspection and activation API does not exist. The fake chunk changes transforms and tie points with `chunk.component`, reproducing the native defect boundary.
- Implemented active-scoped Component inventory, global aligned-camera union, strict key resolution and success/failure restoration. Focused Python Component, export and release-staging coverage is green.
- Integrated selected-Component activation into initial alignment, ground leveling, export and PSX re-export. Reports now carry schema-v2 inventory, unaligned counts and selected-Component camera counts.
- Added the read-only `inspect_metashape_components.py` entrypoint and made release staging fail when it is missing.
- Added Rust schema-v2 DTO validation, revision/PSX/executable preflight, hidden asynchronous Metashape inspection, Unicode-safe argument construction, temporary-output cleanup, command registration and truthful select/validate execution-plan nodes.
- Added a pure frontend selection decision, live inspection-on-click, direct single-Component flow, multi-Component confirmation dialog and a read-only current-export display. Frontend unit tests, lint and production build are green.
- RED/GREEN evidence was preserved for the missing Python API, missing staged inspector, Rust DTO/argument API, schema-v2 report validation and frontend selection view model.
- Full source acceptance passed: Python 288/288 with one intentional skip, Rust 100/100, frontend 50/50, frontend lint, TypeScript/Vite production build, Python compilation and diff whitespace checks.
- Native read-only acceptance passed under both Metashape 2.2.1 and 2.3.0 against `D:\3DRegistration\test\xPano\work\xpano.psx`: 458/221/177 Components, 856/880 globally aligned, 24 unaligned and 132270/94262/74148 tie points. The PSX hash and write time did not change.
- Five-axis review found no correctness, readability, architecture, security or performance blocker. Phase 58 is complete; no installer, release, version bump, commit or external publication was created.

# 2026-07-17 Phase 59 started

- User requested a new Windows release package at version `2.0.0-preview` containing the completed alignment and Component fixes.
- Scope is version synchronization, full source/release gates, installer construction and independent artifact verification. No commit, tag or external publication is authorized.
- Synchronized npm, Cargo, lockfile and Tauri versions to `2.0.0-preview` and added the matching changelog entry.
- Reconfirmed the standard dependency-complete release entrypoint. The source LFS payload is missing its executable and must be hydrated before release staging can pass.
- Selected a missing-only restore from the canonical `D:/FastPrograms/LichtFeld-Studio-windows-v0.5.3` tree so existing xPano-specific runtime files are preserved.
- Compared source, prior valid stage and canonical LFS trees. The 235 current files are hash-identical to canonical, with 1,215 canonical files missing and no conflicts; the prior stage's 205 omissions are generated/excluded runtime files.
- Restored all 1,215 missing LFS files from the canonical payload without overwriting the 235 existing files. Independent verification found 1,450/1,450 files, zero missing files and zero SHA-256 differences.
- Confirmed the 205 files absent from the previous valid stage are all explained by the release cache/debug filters, with zero unexpected omissions.
- Re-ran a strict six-source version proof; every value is exactly `2.0.0-preview`.
- Source regression gates passed: Python 288 tests with one intentional skip, Rust 100 tests, frontend 50 tests and frontend lint.
- Frontend production build, Python compile-all and `git diff --check` passed. Release preflight found 140.34 GB free space, no stale `2.0.0-preview` artifact and no active installer/compiler process.
- First installer attempt correctly failed closed during bundled-runtime manifest validation because the cp39 NumPy Metashape wheel is missing or corrupt. Rust release compilation and DLL closure passed; no installer was emitted.
- Manifest audit showed all five required Metashape wheels were absent. Restored the four NumPy ABI wheels and OpenCV abi3 wheel from the local full-offline payload, then independently validated all five against manifest size and SHA-256.
- Second installer attempt advanced past wheel validation and was correctly stopped by the Windows runtime manifest because `msvcp140.dll` is missing or corrupt. No installer was emitted.
- Audited the complete six-DLL Windows runtime manifest. The source payload is empty, while the currently installed xPano runtime contains exact manifest-matching copies of all six files.
- Restored and validated all six Windows runtime DLLs. A broader required-source check then found the bundled Python executable/module and app `tqdm` wheel absent.
- Filter-aware comparison confirmed the installed xPano Python/runtime and app wheel trees are strict supersets of source with no portable-file hash conflicts: 618 Python files and 9 app wheels are missing.
- Restored 618 portable Python files and 9 app wheels missing-only. Post-copy comparison reports zero missing/hash differences; isolated bundled Python imports `cv2`, NumPy, Pillow, piexif and tqdm successfully.
- Full preflight now passes both runtime manifests, all six VC++ DLLs and all 26 required release-source resources.
- Third installer build passed repeated source gates, release staging, 66/127/227-file PE DLL closure checks, Tauri release compilation and NSIS bundling.
- Built `dist/xPano-2.0.0-preview-windows-x64-setup.exe`; build-reported SHA-256 is `5A4A39C7594B68114D7D1D41B92EE4CABE83BF2726D06E7F2444E04A89648C68`.
- Independent installer verification confirmed 728,701,363 bytes, ProductVersion/FileVersion `2.0.0-preview` and a sidecar matching the recomputed SHA-256.
- Independently verified all 2,201 staged manifest records with zero missing, size or hash failures; six critical alignment/Component scripts are byte-identical to source, LFS has 1,245 portable files, and stage contains no forbidden cache/debug payload.
- Final staged smoke tests passed for bundled Python imports, the six-DLL Windows runtime and bundled dependency manifest. No installer/compiler process remains active.
- Five-axis release review found no blocker: behavior is regression-covered; packaging uses the existing narrow staging architecture; immutable runtime payloads are manifest/hash validated; no new execution or privilege surface was added; and runtime performance behavior is unchanged. The remaining distribution risk is that the installer is unsigned.
- Phase 59 complete. No commit, tag, push or external release publication was performed.
- The planning completeness helper still reports an older historical build-22170 phase as in progress; Phase 59 itself is complete and that unrelated deferred gate was not altered.

# 2026-07-20 Phase 60 started

- User provided `C:/Users/Beluga/Downloads/pano_extractor_GUI.py` as the updated upstream reference and requested feasibility research plus an implementation plan for LUT restoration support.
- Scope is diagnosis/design only. Existing dirty worktree and release payloads will be preserved; no product behavior, package or external state will be changed.
- Inspected the complete upstream symbol/LUT surface. The feature is a single `.cube` FFmpeg `lut3d` color transform applied after temporal sampling and before JPEG output on each eye/stream; it is not lens undistortion or coordinate remapping.
- Confirmed the upstream file is syntactically valid and the repository has no existing product LUT contract. Located the active extraction implementation and its hardware-decoder fallback/progress boundaries for deeper tracing.
- Traced the active dual-eye and single-video command factories. A shared optional FFmpeg filter-chain builder is the likely minimal integration point; post-extraction rewriting would add I/O, duplicate JPEG loss and break live prepared-frame previews.
- Traced project persistence and invalidation. Per-track optional LUT state fits the existing extraction settings and repeated CLI argument model, and changing it will correctly stale only the affected prepared track plus downstream reconstruction.
- Confirmed the bundled FFmpeg already includes the slice-threaded `lut3d` filter. The first Unicode-path probe exposed a subprocess diagnostic-decoding issue and will be rerun with explicit UTF-8 handling.
- Verified that upstream-style direct filter-path interpolation fails on a deliberately difficult Windows path, while a safe staged basename succeeds. Corrected the synthetic identity cube channel ordering before fidelity measurements.
- Corrected identity-LUT fidelity is effectively exact (2 byte values differ by one level). A 4K-square microbenchmark confirms meaningful CPU overhead and unexpectedly larger JPEG output, prompting an explicit pixel-format compatibility check before finalizing the plan.
- Confirmed LUT-only filtering negotiates 4:4:4 JPEGs; an explicit trailing 4:2:0 format restores current storage characteristics. Corrected the entrypoint trace to the registered `run_xpano_prepare_project.py` GUI media job.
- Verified xPano already decodes FFmpeg logs as UTF-8 safely. Located the project-aware staging boundary and determined LUT content should be copied to a safe per-track snapshot before extraction, then referenced by basename through an FFmpeg working directory.
- Stabilized the LUT output to current 4:2:0 JPEG semantics and quantified the optional CPU cost. Reviewed project-source validation and existing test surfaces; no new dependency, schema version or test framework is needed.
- Completed a final consistency review against the current Rust extraction contract, project-aware media entrypoint, shared Python extractor, panorama/ordinary-video builders and existing frontend settings surfaces.
- Confirmed the smallest stable ownership split: Rust validates and persists an optional per-video-track path; `run_xpano_prepare_project.py` propagates it; `xpano_extract.py` owns one copied, prevalidated temporary `lut.cube` snapshot across decoder fallback attempts.
- Recorded the implementation plan in `docs/LUT_RESTORATION_INTEGRATION_PLAN.md`, including test-first order, special-path handling, explicit `yuvj420p`, failure semantics, performance limits and non-goals.
- Phase 60 complete. Feasibility is confirmed; no product code, package, version, commit or external state was changed.

# 2026-07-20 Phase 61 started

- Created source baseline commit `6157b7e` (`feat: restore alignment and component workflows`) before LUT implementation.
- The commit contains tracked source plus new Component/LUT design source files; `binaries/`, `runtime/`, `tools/offline-wheels/` and `tmp/` release/local payloads remain untracked.
- Started test-first implementation of the optional per-video-track LUT contract, shared FFmpeg transform and media UI. No installer or external publication is in scope.
- RED was confirmed independently in Rust (missing contract field), Python (missing extractor helpers) and frontend tests (missing pure LUT helper).
- Implemented optional project-v3 `colorLutPath` persistence and validation, target-only stale invalidation, and pre-job missing-file rejection before marker/status mutation.
- Implemented one copied `lut.cube` snapshot per extraction, FFmpeg parse preflight, `fps -> lut3d(tetrahedral) -> yuvj420p`, identical dual-eye filters and stable working-directory propagation across decoder fallback.
- Added import/edit/clear UI for video tracks and made the existing ready-track settings button enter a real editable state. Photo tracks do not expose or retain LUT configuration.
- Focused Rust, Python and frontend tests, frontend lint and production build pass.
- A real FFmpeg probe extracted two frames from a generated MP4 using a `.CUBE` under a Unicode/space/comma/apostrophe path; ffprobe reported `yuvj420p`.
- Full verification passed: 296 Python tests, 104 Rust tests, 52 frontend tests, frontend lint/build, Python compile-all and `git diff --check`.
- Playwright/Edge verified the real media workspace at 1440x900 and 1024x768: the ready-track settings action opens the editor, the LUT row is visible without overlap, and console output contains no application error.
- Final review found no product blocker. No-LUT commands retain `fps=<rate>` and no temporary working directory; LUT failures remain visible and cannot silently publish ungraded frames.
- Phase 61 complete. The Vite development server remains available at `http://127.0.0.1:1420/`; no installer, tag, push or LUT implementation commit was created.

# 2026-07-20 Phase 62 started

- User approved bundled automatic LUT presets for panorama imports. Created Phase 62 plan: opening a color-restoration switch will select the extension-specific bundled preset, while custom LUT selection remains available as an advanced override.
- Verified the upstream reference has no embedded LUT assets and local repository/Downloads inspection found no `.cube` resources. Do not package placeholder, identity or unverified LUT data as color restoration.
- Official Insta360 I-Log download data shows several model-specific LUT archives rather than one universal `.insv` LUT. The Phase 62 plan was corrected to require exact model/profile resolution; extension-only automatic mapping is unsafe and is not being implemented as a false one-click feature.
- User refined Phase 62: keep `.insv` manual-only and auto-select only DJI Osmo 360 D-Log M -> Rec.709 for `.osv` after the user enables restoration. Updated the plan accordingly.
- User supplied `DJI Osmo 360 D-Log M to Rec.709 V1.cube`; copied it as `luts/dji-osmo360-dlogm-rec709-v1.cube` and recorded SHA-256 `b18162854ab47702068410c33afa98a8cb6eef159fc5a04ce0e65fad0fd8947e`.
- Implemented the stable `builtin:dji-osmo360-dlogm-rec709` project setting. Rust rejects non-`.osv`, mutually exclusive manual/preset selections, missing resources and checksum mismatches before it writes the running media-job marker; Python resolves and revalidates the same packaged file before extraction.
- The import/editor UI now presents a default-off restoration toggle for `.osv` tracks, while `.insv` retains only the custom `.cube` picker. Release staging and Tauri resources include `luts/`.
- Fixed the final JSX parse error and the mocked panorama manifest's missing required alignment fields. Focused Python tests (29) and the production frontend build now pass.
- Added a Rust preflight regression proving a valid `.osv` builtin preset is checked and then starts the job. The first FFmpeg smoke invocation lost Python string quotes through PowerShell command nesting and made no product change; the retry used a PowerShell double-quoted Python expression and successfully extracted a real JPEG through the packaged LUT.
- Phase 62 verification complete: Python 299/299, Rust 106/106, frontend 53/53, frontend lint, TypeScript/Vite production build, Python `compileall`, and `git diff --check` all pass. No installer, release artifact, tag, commit or push was created.
- External LUT acquisition is currently blocked: DJI pages did not expose a direct asset and GitHub/CDN retrieval failed across direct API, raw file, proxy and shallow-clone attempts. No code was written that would advertise an approximate or missing LUT as a real restoration preset.
- Phase 63 planned at user request: add independent `styleLutPath` for every video, retain `.osv`-only restoration through `colorLutPreset`, migrate legacy `colorLutPath` to the style layer, and restrict extraction to a fixed restoration-then-style chain. No Phase 63 implementation has started.

# 2026-07-22 Phase 66 started

- User requested a concise end-user README after a source-backed review of the whole product workflow.
- Scope is documentation only. The guide will cover normal use, supported inputs, feature highlights, project artifacts, external dependencies and important limitations; no application behavior, package or release will change.
- Prior release investigation is relevant to wording: Metashape remains external, while densification downloads its large runtime on demand in the standard installer.
- Reviewed the existing README, documentation index, packaging configuration, and repository layout. The current README contains obsolete distribution and alignment claims, so the new document will be a concise replacement.
- A root-level `package.json` lookup was invalid because the frontend package lives under `xpano-ui/`; no files were changed and subsequent inspection will use that location.
- Reviewed the user quickstart, verified Metashape workflow, multi-track behavior, COLMAP/densification documentation, training integration notes, and current frontend feature inventory. The README outline is now grounded in the actual workflow and must avoid obsolete developer-only material.
- Cross-checked current UI code for workspace navigation, material types, LUT behavior, reconstruction controls, results, densification, and Gaussian training. The code confirms a newer restoration/style-LUT chain that the stale planning documents do not yet describe.
- Cross-checked the source contracts, project/reconstruction command surfaces, and current UI guards. The README will explicitly distinguish supported mixed-material reconstruction (Metashape) from the presently blocked COLMAP mixed-material route, and will include the manual PSX re-export recovery path.
- Confirmed the release support boundary and external dependencies from packaging/source. The old README's light/full package, manual system-Python and deprecated workflow sections will not survive the rewrite.
- Confirmed `xpano_project.json` as the native project file and the compatible reopen markers for older/generated project folders. Confirmed the automatic project-location behavior and default LichtFeld GUI launch.
- A search included nonexistent `scripts/run_lichtfeld_training.py`; it made no changes. The actual training entrypoint is `scripts/lichtfeld_training.py`.
- Replaced the obsolete root README with a concise Chinese end-user guide. The draft covers Windows support, bundled/external dependencies, current material types, LUT behavior, the supported reconstruction matrix, non-destructive point-cloud versions, Gaussian training, project reopening, and practical limits.
- README verification passed: UTF-8 decoding, required section/content checks, and internal-link checks all succeeded. `git diff --check` passed; Git only reported existing CRLF normalization warnings. Phase 66 is complete.
- Verified the packaging support boundary and project-relative artifact model. The final document will specify Windows 10/11 x64, external Metashape licensing, and the need to preserve the full selected output directory.
# Phase 67 LFS reliability planning

- Completed a read-only audit of the React -> Tauri -> Python supervisor -> LichtFeld process chain and both installer/staging paths.
- Verified the current local LFS source, release stage, and installed critical files are hash-identical; recursive DLL closure passed for 227 PE files.
- Recorded a phased implementation and acceptance plan. No product code, runtime payload, package, or release artifact was changed.

# 2026-07-23 Phase 67 implementation started

- Baseline source commit is `170d1a7`; the active worktree contains only pre-existing untracked runtime/binary payloads, which remain outside source commits.
- The first RED/GREEN boundary is confirmed: `release_staging.py` copies the LFS tree but validates only the executable and license. Add a pinned LFS runtime manifest and stage-time inventory validation before changing launch behavior.
- The existing Rust launch boundary retains the required normal Windows path conversion. Isolation changes must preserve `plain_windows_path` rather than alter third-party LFS resource lookup.
- Added the tracked `runtime/lichtfeld-studio-manifest.json`: v0.5.3 / `d8c50c6a`, archive name/size/SHA-256, eight GUI/DLL resource sentinels, and hashes for all 1,450 upstream files.
- `release_staging.py` now rejects missing, corrupt, unexpected, or incomplete LFS source/staged trees. A production staging request can rehydrate LFS solely from the pinned ZIP; extracted cache files are discarded before the portable inventory check.
- `build_installer.ps1` now requires `-LichtfeldArchive` or `XPANO_LICHTFELD_ARCHIVE` outside an explicit development build. The former portable assembler is retired and delegates to that installer path.
- Focused packaging tests passed (28). A real archive-driven stage produced 2,205 manifest entries; LFS contains 1,245 portable files, required RML/locale resources, the expected executable SHA-256, and a passing 227-PE DLL closure check.

# 2026-07-23 Phase 67 detailed implementation plan refreshed

- User requested a detailed plan before further product changes. The active plan now separates completed supply-chain/staging work from the remaining runtime-boundary, profile isolation, readiness, lifecycle, diagnostics, densification-isolation, and installed-product acceptance phases.
- No application behavior, runtime payload, installer, or release artifact was changed while preparing this plan.

# 2026-07-23 Phase 67 implementation review

- Reviewed the current runtime-boundary, supervisor-environment, signing-gate, readiness-cache, and terminal-error changes before the requested source commit.
- Replaced version-specific CUDA/Vulkan variable removal with category-based removal in both Rust and Python. This now removes future CUDA Toolkit variables and Vulkan loader overrides while retaining Windows and NVIDIA driver discovery.
- Python (319), Rust (117), frontend unit (54), frontend lint/build, PowerShell parser, Python compileall, and diff-whitespace gates pass. `cargo fmt --check` remains unavailable because the installed Windows GNU toolchain has no rustfmt component.
- A development NSIS build remains in progress; it has not emitted an artifact and is not an acceptance or release result.

# 2026-07-23 Phase 67 installed-runtime correction

- Installed/relocated acceptance exposed a real preflight defect: the LFS inventory contains six legitimate zero-byte marker files, but runtime validation rejected every zero-byte record as corrupt.
- Updated runtime manifest validation to allow zero-byte files while continuing to validate their safe relative path, existence, exact size, and SHA-256. The LFS fixture now includes a zero-byte `py.typed` marker.
- Source manifest parsing confirms all 1,450 LFS entries, including zero-byte markers, are accepted. The complete Python suite passes; a fresh installer is required before repeating installed acceptance.

# 2026-07-23 Phase 67 development installer acceptance

- Built a fresh `xPano-2.0.0-stable-unsigned-dev-windows-x64-setup.exe`. Its SHA-256 sidecar matches, the explicit unsigned marker exists, and Authenticode status is `NotSigned` as required for a development artifact.
- The fresh release stage has 2,205 records with zero invalid, missing, or unexpected files. LFS has 1,450 manifest entries, eight sentinels, and a successful 227-PE DLL dependency closure.
- Installed resources under `E:\FastProgram\xPano` match the corrected runtime-readiness script. A sanitized installed preflight reports LFS v0.5.3, one CUDA device, three Vulkan devices, and only the intentionally empty dataset as `TRAINING_DATASET_INVALID`.
- A complete relocated resource tree under a path containing Chinese characters and spaces produces the same structured preflight result. This proves the packaged LFS resource lookup and normal Windows child path behavior in that path class.
- The first transcripted rebuild overlapped an already-running NSIS compression job and returned a collision failure. The resulting fresh artifact came from the first completed build; all subsequent acceptance uses its new timestamp and verified hash. Do not run installer builds concurrently.
- Final source gates pass: Python 319, Rust 117, frontend unit 54, frontend lint/build, Python compileall, PowerShell parser, and `git diff --check`. `cargo fmt --check` remains unavailable because `stable-x86_64-pc-windows-gnu` lacks rustfmt.
