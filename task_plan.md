# Task Plan: 阶段 3/4、真实全流程与可自举安装器

## Goal
在保留现有用户改动的前提下，完整实现 `docs/UI_WORKSPACE_REDESIGN_SPEC.md` 的阶段 3（对齐工作区）和阶段 4（成果与后处理），使用 `D:\3DRegistration\test` 的真实素材打通抽帧、对齐、点云预览和致密化；随后实现可重复、可诊断、安装即用的 Windows 安装器。CUDA、torch、Open3D 等致密化大依赖不随包发布，缺失时按受控镜像源自动配置；本任务期间禁止实际下载大包，使用下载计划、假源和小型探针验收。

## Current Phase
Phase 66 complete

## Phases

### Phase 21: LichtFeld Studio 单阶段高斯训练集成
- [x] 提交点云预览性能优化，隔离新功能改动
- [x] 审查 xPano 工作流、任务模型、项目产物与 LichtFeld 运行时能力/许可
- [x] 定义单阶段训练参数、输入输出、GUI 默认启动、进度和取消协议
- [x] 测试先行实现 Rust 训练任务与前端“高斯训练”工作区
- [x] 将 LichtFeld Studio 运行时纳入仓库资源和后续打包清单
- [x] 使用真实工程启动训练并验证进度读取、取消和结果恢复
- [x] 跑全量测试、构建与代码审查，不生成发布安装包
- **Status:** complete

### Phase 20: 点云预览加载与主线程响应优化
- [x] 停止被新请求取代的安装器构建，确认不再发布
- [x] 对 Rust 读取、IPC 传输、JS 转换、场景准备和 GPU 上传建立分段基线
- [x] 写失败回归测试证明同步读取与 JSON 大数组路径会阻塞/放大数据
- [x] 将磁盘解析移出 Tauri UI 线程并改用紧凑二进制 IPC
- [x] 将前端场景准备移入 Web Worker，同时保持完整点数、精度与画质
- [x] 用真实工程前后对比加载时间、长任务和交互响应，并跑全量测试/构建
- **Status:** complete

### Phase 19: 单行标题栏与底部工作流控制坞
- [x] 提交阶段 3/4、发布运行时和导出进度修复基线
- [x] 建立现有布局的浏览器 RED 尺寸基线
- [x] 合并工程状态、环境状态和打开工程到单行标题栏
- [x] 将三个工作区入口移入底部控制坞
- [x] 将任务进度压缩为不抢占导航的紧凑区域
- [x] 验证 1024、1366、1920 宽度、交互状态、测试与生产构建
- **Status:** complete

### Phase 18: 导出阶段执行图状态稳定性修复
- [x] 核对截图、真实任务事件、前端 reducer 与执行计划 stageId
- [x] 先增加前端无 stage 事件覆盖与后端 stageId 抖动的失败回归测试
- [x] 统一 Metashape 导出阶段为计划内 `export.images`
- [x] 保留同阶段计数状态，并在显式阶段切换时清理旧计数
- [x] 运行前端、Python、Rust、构建与 diff 验收
- **Status:** complete

### Phase 1: 基线、架构与故障定位
- [x] 确认用户目标、工作区状态和执行约束
- [x] 梳理 UI、Tauri、Python/外部进程三层架构
- [x] 复现或构造最小测试证明三个故障
- [x] 建立导入/预览性能基线并记录瓶颈
- **Status:** complete

### Phase 2: 方案设计与回归测试
- [x] 明确根因与最小可行改动
- [x] 先补回归测试，验证测试在修复前失败
- [x] 记录性能优化边界和验收指标
- **Status:** complete

### Phase 3: 实现
- [x] 默认进入素材导入区
- [x] 修复照片文件夹预览
- [x] 修复抽帧任务 stdout/GBK/退出码 120
- [x] 优化扫描、缩略图、长列表与任务进程性能
- **Status:** complete

### Phase 4: 验证与性能验收
- [x] 运行相关单测、集成测试和完整构建
- [x] 验证照片文件夹、视频、长素材关键流程
- [x] 对比优化前后指标并检查内存/主线程风险
- **Status:** complete

### Phase 5: 最终审查与交付
- [x] 按正确性、简洁性、架构、安全、性能复审改动
- [x] 检查未完成项、残余风险与用户工作区冲突
- [x] 更新文档并交付结果
- **Status:** complete

### Phase 6: 导入确认按钮无响应回归
- [x] 读取运行时日志并稳定复现点击后的真实失败
- [x] 定位 `confirmImport → create_project → commit_import` 中断层
- [x] 修复素材准备完成后对齐页仍判定“素材未就位”
- [x] 素材全部就绪后增加“下一步：对齐与重建”引导
- [x] 先补失败回归测试，再实现最小修复
- [x] 运行导入→准备→进入对齐端到端、前端构建与相关全量测试
- **Status:** complete

### Phase 7: 媒体任务完成后轨道仍停留 running
- [x] 保存当前工程、任务结果和截图证据
- [x] 复现并定位 `pipeline:complete → finalize_media_job` 状态提交中断
- [x] 先补失败回归测试，再实现最小修复
- [x] 修复当前遗留 running 工程并验证下一步可用
- [x] 运行前端、Rust 与关键流程回归
- **Status:** complete

### Phase 8: 对齐完成后的成果工作区闭环
- [x] 核对 docs 阶段 4 契约与当前结果页实现差距
- [x] 复现并定位对齐产物、工程状态和结果页加载链路断点
- [x] 先补失败回归测试，再实现最小闭环
- [x] 验证对齐完成后自动进入成果页且点云可见
- [x] 运行前端、Rust、Python 相关回归与构建验收
- **Status:** complete

### Phase 9: 抽帧硬件解码与照片预览渐进加载
- [x] 固化 CUDA/D3D11VA/软件解码命令选择与回退测试
- [x] 实现正式抽帧自动硬解、可观察回退和日志记录
- [x] 移除照片预览路径数量上限，扫描一次返回完整路径集合
- [x] 实现视口触底逐批追加、单图进入视口才加载、已加载不卸载
- [x] 用真实双路 4K OSV 对比性能和输出一致性
- [x] 用大照片目录验证首屏请求数、滚动追加和完整可达性
- [x] 修复长任务完成时无害总 revision 变化导致的结果提交失败，并兼容恢复已完成的旧结果
- [x] 运行 Python、Rust、前端测试、lint、build 与最终代码审查
- **Status:** complete

### Phase 10: 新目标范围审计与基线
- [x] 精确提取规格阶段 3/4 的功能、数据模型、事务和验收条款
- [x] 绘制 React → Tauri → Python/Metashape/COLMAP/LichtFeld 的真实调用图
- [x] 盘点 `D:\3DRegistration\test` 素材、已有产物、工具链和磁盘预算
- [x] 审计现有 Tauri bundle、NSIS hook、release/configure 脚本和依赖来源
- [x] 为每项显式要求绑定权威验收证据，禁止用窄测试代替全流程结论
- **Status:** complete

### Phase 11: 完整实现规格阶段 3——对齐工作区
- [x] 补齐配置向导、执行计划、后端能力和输入兼容性契约
- [x] 补齐任务状态、取消、恢复、进度、日志和工程事务
- [x] 保证对齐产物结构、revision、manifest 和结果工作区闭环
- [x] 先写失败回归，再完成 Rust/Python/前端实现与全量验证
- **Status:** complete

### Phase 12: 完整实现规格阶段 4——成果与后处理
- [x] 拆分查看器 viewport、几何事务、致密化任务与点云版本状态
- [x] 实现 canonical/world 变换、相机外参/点云同步和投影不变量测试
- [x] 实现永久 standard、多 densified 版本、预览、删除和可逆训练点云选择
- [x] 致密化结果注册为新版本，不再覆盖后删除候选；所有写盘原子且可恢复
- [x] 完成结果页、重开工程、任务中断和大点云性能验收
- **Status:** complete

### Phase 13: 第一轮真实全流程验收
- [x] 固定真实测试输入、参数、输出目录和产物清单
- [x] 用 OSV + 照片完成抽帧与素材准备
- [x] 完成真实对齐并校验相机、图像、点数、manifest 和工程状态
- [x] 在应用结果链路加载点云并验证相机、版本与完整读取性能
- [x] 使用既有 CUDA/torch/Open3D 环境运行受控致密化，全程未下载大包
- **Status:** complete

### Phase 14: 安装器与运行时自举设计
- [x] 定义随包资源、系统前置、按需下载依赖和明确非目标
- [x] 设计版本锁定、架构/GPU 检测、镜像优先级、哈希校验、断点/缓存、离线错误语义
- [x] 统一应用 Python、FFmpeg/ffprobe、COLMAP、Metashape、LichtFeld 和致密化环境解析
- [x] 设计 full app + on-demand dense runtime 的单一优雅安装体验，不制造多余平台适配
- [x] 写出安装、升级、卸载、缓存与失败恢复事务
- **Status:** complete

### Phase 15: 安装器与依赖自举实现
- [x] 实现可复现 Tauri/NSIS 构建，杜绝复用旧 EXE 或遗漏资源
- [x] 实现结构化环境探针、异步流式日志、取消和幂等配置
- [x] 实现镜像源下载计划与校验器；torch/CUDA/Open3D 等大包只生成/验证计划
- [x] 实现安装后首次启动检查、按需配置、缓存复用和明确错误提示
- [x] 生成可安装产物并完成静态内容、签名状态和资源清单审计
- **Status:** complete

### Phase 16: 常见环境模拟与安装器验收
- [x] 模拟无 runtime、缓存命中、CPU/CUDA、缺失基础工具和已安装基础工具等场景
- [x] 使用临时目录、假 pip/镜像和本地小文件验证自动下载分支，不访问大包网络
- [x] 验证中文/空格路径、非管理员安装、升级、卸载、取消、断网、HTTP 错误、校验失败和磁盘不足
- [x] 验证第二次启动不重复下载，失败后保留旧 active 且不留下半安装状态
- **Status:** complete

### Phase 17: 最终真实验收与发布审查
- [x] 使用安装器版本再次打开 `D:\3DRegistration\test` 真实工程并逐阶段验证素材、对齐、标准点云与致密版本
- [x] 对照阶段 3/4、真实流程、安装器和环境矩阵逐条完成证据审计
- [x] 运行 Python、Rust、前端、PowerShell、构建、安装器和代码质量全量门
- [x] 输出安装器、版本/依赖清单、测试证据、已知边界和使用说明
- **Status:** complete

## Key Questions
1. 默认页面状态由哪个组件/持久化状态决定，是否存在旧状态恢复覆盖？
2. 照片目录从选择、扫描、IPC 返回到前端预览的哪一层丢失或阻塞？
3. 抽帧任务如何启动 Python/外部进程，stdout 为何在 Windows GBK 环境关闭时触发退出码 120？
4. 导入卡顿来自同步目录遍历、媒体探测、缩略图解码、全量 DOM 渲染还是重复状态更新？
5. 阶段 3 的配置/执行/恢复契约哪些已落地，哪些仍由旧 `PipelinePage` 或临时兼容层承担？
6. 阶段 4 的 canonical/world 几何、点云版本和训练输入物化是否存在任何覆盖/删除式旧路径？
7. 真实测试将使用 Metashape 还是 COLMAP 后端，当前机器许可和可执行文件是否可用？
8. 致密化运行时当前已安装哪些模块；在不下载大包前提下能否完成真实运行，不能时如何保留完整证据而不缩小目标？
9. 安装器随包携带与按需下载的边界、版本锁、镜像、哈希、缓存和回滚如何形成一个事务？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先复现并测试，再改实现 | 三个问题横跨 UI、IPC 与子进程，猜测式修复容易只遮蔽症状 |
| 优先局部修正与有证据的性能改造 | 当前工作树已有大量用户改动，避免无依据的大重构和冲突 |
| 不清理任何不确定的已有改动或死代码 | 工作树非干净状态，所有现有变更均视为用户资产 |
| 启动通配路由改到 `/project/media`，保留已有工程的 `activeWorkspace` 恢复 | 分离“软件默认入口”和“恢复工程工作区”两个需求，避免扩大行为变更 |
| 照片目录单次扫描完成计数与有界抽样，消除分析后预览的第二次全量扫描 | 直接针对已观测的重复 I/O 和全量排序，保持现有返回契约不变 |
| 在 Tauri 子进程边界统一设置 Python UTF-8 环境，脚本入口再显式重配输出 | 同时覆盖媒体准备和后续 Python 任务，修复 Windows GBK/退出码 120 的根因 |
| 将实时素材项改为批量、有界预览缓存 | 实时 UI 不需要保存所有项；避免每项一次 React 更新和 O(N²) 数组复制 |
| 将目录扫描包装为 async command + `spawn_blocking` | Tauri 2.11.3 官方 API提供专用 blocking executor，避免大目录 I/O 占用异步执行线程 |
| 不根据“按钮没反应”直接猜 UI 事件问题 | 截图证明按钮可用、预览已成功；先读取 Tauri/前端真实异常，重点检查工程创建与导入 IPC |
| 新增 `open_or_create_project` 深模块入口，保留严格 `create_project` | 调用方无需理解默认根目录与已有工程竞态；后端集中保证不覆盖既有工程 |
| 素材页与对齐页共用 `evaluateMediaReadiness` | 将轨道状态、选中项和 alignment manifest 三个不变量集中到一个可测试接口，避免页面判定漂移 |
| 媒体结果由 Rust 子进程退出边界先提交，再发送完成事件 | 工程持久化不能依赖前端监听是否在线；前端仅执行幂等同步与遗留恢复 |
| 最终提交使用专用校验而非通用媒体编辑锁 | 通用锁应继续禁止用户编辑，但必须允许任务自身完成 `running → ready` 状态迁移 |
| 重建结果同样在 Rust 子进程退出边界提交 | 产物与工程状态必须形成一个后端权威事务，不能依赖结果页或前端监听补写 |
| 首轮成果闭环复用现有根目录 `sparse/0` 查看器契约 | 当前真实 pipeline 已稳定产出该结构；立即搬迁为 `colmap/sparse/0` 会扩大算法、路径与兼容性变更，先用相对路径 `.` 登记，后续再按阶段 4 迁移版本模型 |
| 自动跳转仅绑定本页面实际启动的重建任务 | 避免已完成工程用户手动返回对齐页时被无条件强制跳回成果页 |
| 硬解优先级采用 CUDA → D3D11VA → 软件 | 当前 RTX 4060 实测 CUDA 15.02s、D3D11VA 20.06s、软件 51.49s；按收益排序并保留跨设备回退 |
| 图片路径扫描一次完整返回，图片资源按视口渐进请求 | 文件路径字符串远小于图片解码成本，可消除重复目录扫描；前端只追加视口需要的 DOM，并让单图进入视口才设置 `src` |
| 已追加预览不卸载 | 明确遵循用户浏览连续性要求，滚回上方不重新请求或解码；代价是持续滚到底时 DOM 会增长，这是本需求接受的权衡 |
| 新目标以 UI 规格阶段 3/4 为权威，不复用旧计划同名阶段的“complete”结论 | 两组阶段名称相同但范围完全不同；必须逐条按规格重新审计 |
| 大依赖下载只验证计划与小型假源，不实际下载 torch/CUDA/Open3D | 用户明确使用手机流量；功能实现必须覆盖下载路径，但本轮禁止产生大流量 |
| 安装器先限定当前产品支持的 Windows x64，不为假想平台增加适配 | 用户要求避免打包疏漏，不要求扩展平台支持；复杂度必须由真实约束拉动 |
| 真实流程与模拟环境分开验收 | 算法正确性需要真实素材/真实工具，下载与缺失环境分支需要可重复的假源测试，二者不能互相替代 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Phase 12 transform RED 因累计世界变换事务不存在而编译失败 | RED phase | 预期失败；实现 images/points 双文件原子事务后转 GREEN |
| Phase 12 Cargo 验证再次并列传入两个 TESTNAME，被 CLI 拒绝 | 1 | 使用同一隔离 target 分两次运行，禁止组合位置过滤器 |
| Phase 12 geometry RED 因 5 个版本事务函数不存在而编译失败 | RED phase | 预期失败；实现深 geometry 模块后转 GREEN |
| New workflow regression tests fail on missing `mediaReadiness.ts` and `open_or_create_project_impl` | RED phase | Expected failure; implement the minimal shared readiness module and atomic backend entry next. |
| create_goal 提示已有未完成目标 | 1 | 使用 get_goal 确认现有目标就是本次请求并继续，不重复创建 |
| PowerShell/Windows 下给 rg 传入 `dir/*.ext` 导致路径语法错误 | 1 | 改用 `rg pattern dir -g '*.ext'` |
| Cargo 基线测试构建 `libresource.a` 时 os error 32 文件占用 | 1 | 不复用被锁 target；后续指定独立 `.codex_tmp/cargo-target-media-fix` |
| Windows 子进程最小复现首次缺少 PYTHONPATH，脚本无法 import `scripts` | 1 | 按 Tauri 实际启动环境补充仓库根目录到 PYTHONPATH 后重试 |
| cargo test 一次传入两个 TESTNAME 过滤器被拒绝 | 1 | 改为运行 `cargo test --lib`，一次编译并覆盖两个新增测试 |
| Playwright Chrome 启动后 code 13/TargetClosed | 1 | 改用 Microsoft Edge channel，完成素材→对齐运行时验收 |
| 当前 Rust GNU toolchain 未安装 cargo-fmt/rustfmt | 1 | 不改工具链；使用编译测试、git diff --check 与人工格式审查替代 |
| 当前 Codex 线程未挂接截图中的应用终端 | 1 | 改查素材目录工程副作用、运行进程和前后端状态传播 |
| 首次更新 Phase 8 时因 PowerShell 默认编码显示为乱码，补丁上下文不匹配 | 1 | 使用 UTF-8 重新读取文件并以真实中文上下文应用补丁 |
| Phase 8 RED 测试因 `finalize_reconstruction_job_impl` 不存在而编译失败 | RED phase | 这是预期失败，证明重建成功退出后没有工程提交入口；下一步实现最小后端事务 |
| lifecycle 测试错误假设失败时应清空旧 `colmapPath` | GREEN phase | 规格要求失败保留旧有效结果，修正测试为验证路径保持不变，不修改实现 |
| legacy recovery 测试未设置 active alignment manifest | GREEN phase | 补齐与真实工程一致的 manifest 配置，使测试验证 summary 与当前输入 revision 的匹配保护 |
| 项目 `.venv` 执行全量测试时缺少 pytest | verification | 确认仓库实际使用标准库 `unittest`，不安装依赖、不修改用户环境，改用 `unittest discover` 并记录到 `.learnings/ERRORS.md` |
| 使用 `--exact` 过滤 Rust 零点模型测试时匹配到 0 个测试 | review RED phase | 改用唯一测试名子串重新运行，确认测试在收紧校验前真实失败 |
| Phase 9 三组 RED 测试分别因新接口不存在而失败 | RED phase | 预期失败，证明正式抽帧仍无硬解回退、后端仍截断路径、前端仍无累进批次逻辑 |
| PowerShell 组合 rg 模式时双引号未闭合 | implementation | 拆成单引号模式和更小的搜索命令，避免在一条命令中混合多层引号 |
| Phase 9 首次真实自动抽帧三档候选最终以 Windows -2 退出 | acceptance attempt 1 | 最小诊断证明原基准 OSV 已不存在，三档均正确报告 missing input；切换到当前可用 OSV，不修改实现 |
| oxlint 报告渐进加载 effect 缺少 visibleCount 依赖 | verification | 改为使用派生 `totalPaths`，避免闭包读取当前计数并保持 effect 依赖稳定 |
| Playwright CLI 默认 Chrome 启动 code 13 / TargetClosed | browser acceptance | 复用已知解决方案，切换 Microsoft Edge 通道，不重复启动 Chrome |
| 抽帧 100% 后结果提交报 `project revision changed from 2 to 4` | user acceptance | 总 revision 包含工作区/名称变更，改为任务标记 + media revision 校验，并为已丢失 marker 的旧失败结果增加严格恢复条件 |
| Windows `rg` 直接接收 `README*` 路径导致 os error 123 | Phase 10 audit | 改用目录参数与 `-g 'README*'`，并用 `Promise.allSettled` 防止单个空结果中断其余审计 |
| 审计命令读取不存在的 `ReconstructionWizard.tsx` | Phase 10 audit | 以实际 module map 为准改读 `ReconstructionSetupDialog.tsx`，不再根据规格建议文件名假设实现已存在 |
| 读取旧验收工程 `D:\3DRegistration\test\xPano` 失败 | Phase 10 audit | 旧工程已被外部流程移除；重新搜索当前 `xpano_project.json`，若无则创建全新隔离验收工程 |
| PowerShell 工具列表脚本出现 empty pipe element | Phase 10 audit | 将对象创建与 Format-Table 拆开，避免在 foreach 闭合处形成空管道元素 |
| COLMAP 官方文档站请求连接关闭 | Phase 10 source audit | 改取 COLMAP 官方 GitHub 仓库 raw 文档；仍只使用官方来源 |
| Rust RED 测试首次使用全新隔离 target 编译依赖耗时约 80 秒 | Phase 11 jobs RED | 编译最终按预期失败于缺少 `mark_cancel_requested`；后续复用同一隔离 target，避免重复全量构建 |
| schema 搜索包含不存在的 `xpano-ui/src-tauri/schemas` 导致 rg exit 1 | Phase 11 audit | 改读仓库根 `schemas/`，并使用 allSettled 保留其余检查结果 |
| Phase 11 前端构建把 `setLogs` 的数组参数误当 progress 读取 `.phase` | GREEN integration | 改为取消日志不从日志数组推导阶段；Rust 49/49、Node 15/15 与 lint 已先通过 |
| Playwright 首次仍启动 Chrome 并以 code 13/TargetClosed 退出 | Phase 11 UI acceptance | 按已验证路径将 `--browser=msedge` 放到 URL 前，Edge 会话成功启动 |
| Playwright CLI 经 Windows cmd 传递含 `&running=1` URL 时拆成第二条命令 | Phase 11 UI acceptance | 不把该失败当应用问题；静态 phase3 用单参数 URL 验收，running/cancelling 由 reducer、Rust supervisor 和 durable recovery 测试证明 |
| Playwright `eval` 中带 button 查询的函数被 CLI 参数解析破坏 | Phase 11 UI acceptance | 改用 snapshot 确认按钮可达，eval 仅检查 viewport/overflow 数值 |
| 独立致密化 runner 的 `--help` 冷启动超过 30 秒 | Phase 12 full regression | 帮助/环境探针改为 AST 只提取插件 `build_argparser`，不导入 Torch/Open3D；真实帮助降至约 0.1 秒 |
| 新增轻量帮助测试漏导入 `sys` | Phase 12 regression fix | 补齐测试导入后定向 2/2、Python 全量 136/136 通过 |
| Phase 14 审计脚本再次在 `foreach` 后直接管道导致 empty pipe element | 1 | 改为先累积 `$rows`，循环结束后单独 `Format-Table`；不重复该 PowerShell 结构 |
| NSIS 静默安装返回 2 并回滚 | Phase 15 installed acceptance | WebView2 版本在 32 位注册表视图；hook 改为 64/32 位双探测并在安装器非零后重新探测 |
| 安装版 EXE 运行但无窗口 | Phase 15 installed acceptance | 安装目录遗漏 `WebView2Loader.dll`；fresh Cargo prebuild 后将 DLL 纳入 staging/hash/Tauri root resources |
| 卸载后残留 Python `__pycache__` | Phase 15 uninstall acceptance | post-uninstall 删除专属 `$INSTDIR`，保持素材旁项目目录不受影响 |
| PowerShell wheel hash inventory again used a pipeline directly after `foreach` | Phase 23 audit | Reused the recorded safe pattern: accumulate rows first, then pipe once. |
| First runtime-readiness CLI launch could not import sibling `scripts` modules | Phase 23 RED | Added a self-contained project-root bootstrap and a regression launching `--help` from an unrelated working directory. |
| Existing `runtime/pip.pyz` rejected Metashape Python 3.9 because it required Python 3.10+ | Phase 23 real acceptance | Rebuilt the bundled zipapp from pip 25.0.1, verified Python >=3.8 metadata and executed it with isolated Metashape Python 3.9. |
| PowerShell `Compress-Archive` rejected a `.pyz` destination | Phase 23 pip asset update | Created a `.zip`, then copied the verified ZIP archive to `runtime/pip.pyz`. |
| A one-second shell timeout killed the first full release staging attempt | Phase 23 staging acceptance | Safely removed only verified workspace staging remnants and reran with a normal timeout. |
| Combined frontend/Rust verification invoked Cargo from `xpano-ui` instead of `src-tauri` | Phase 23 verification | Reran the complete Rust suite from the correct crate directory; 78/78 passed without warnings. |
| First formal 0.2.0 build used a one-second nested shell timeout | Phase 24 release | Confirmed no staging/artifact was produced and reran with a 20-minute timeout; the build completed successfully. |
| `git check-attr` was called with explicit attributes and `--all` together | Phase 24 LFS audit | Reran with explicit `filter diff merge` attributes only. |
| Vendored runtime triggered upstream whitespace/conflict-marker checks | Phase 24 source packaging | Marked the complete LichtFeld directory `-diff -text` while retaining binary LFS filters, preserving upstream bytes and excluding vendored content from product whitespace policy. |
| Installed Git LFS does not support `git lfs ls-files --cached` | Phase 24 LFS audit | Used staged pointer inspection, `git lfs ls-files` and `git lfs fsck`; every expected binary path is an LFS pointer and fsck passed. |
| Broad secret-scan PowerShell command had an unterminated quoted regex | Phase 24 review | Split inventory and secret scanning into simpler commands; no release secret was found. |

## Notes
- 每两个查看/搜索操作后将关键发现写入 findings.md。
- 重大设计决定前重新读取本文件。
- 所有行为改动遵循 RED → GREEN → REFACTOR。
# Phase 21 follow-up: authoritative LichtFeld training progress
- [x] Reproduce the 253-vs-26 mismatch from real LichtFeld logs and MCP state.
- [x] Add regression coverage separating loss-buffer records from optimizer iterations.
- [x] Poll official embedded Python trainer accessors through MCP and emit low-noise heartbeat progress.
- [x] Run focused, full-suite, frontend, Rust, and real-training verification.

# Phase 22: retain and stabilize point-cloud preview
- [x] Measure real project sizes and isolate repeated first-load triggers.
- [x] Add failing tests for in-flight load deduplication and session retention.
- [x] Keep the results viewer mounted across workspace navigation and pause hidden rendering.
- [x] Stabilize preview dependencies and remove component-local eviction behavior.
- [x] Verify first load, leave/return, variant switching, responsiveness, and full regression gates.
- **Status:** complete; user accepted the preview on 2026-07-11.

# Phase 23: offline release runtime readiness

## Goal

Ship every normal xPano runtime inside the Windows installer and make it callable offline. Metashape remains an externally installed licensed application, but all xPano-required Metashape Python wheels must ship with xPano and be installed automatically when missing. Only the densification environment may be downloaded after installation.

## Runtime boundary

- Immutable bundled resources: app Python and imports, FFmpeg/ffprobe, COLMAP, LichtFeld Studio training runtime, WebView2 support assets, Metashape dependency wheels, runtime manifests and `pip.pyz`.
- External dependency: Metashape application/license only.
- Downloadable runtime: densification CPU/CUDA environment and model artifacts only.
- Mutable state: versioned runtimes under `%LOCALAPPDATA%\com.xpano.app`; never under the application install directory.

## Implementation plan

- [x] Freeze the supported Metashape ABI matrix and exact dependency artifact profiles (`cp39`, `cp310`, `cp311`, `cp312`, Windows x64); record exact filenames, sizes, SHA-256 hashes and license notices in a bundled runtime manifest.
- [x] Add RED packaging tests proving formal staging contains every required wheel/profile and rejects missing wheels, altered hashes, incompatible ABI assignments, unsupported platforms, forbidden densification payloads and missing notices.
- [x] Update `scripts/release_staging.py` so the authoritative installer chain stages both wheelhouses, the bundled runtime manifest and notices. Staging validation is the build gate used by `scripts/build_installer.ps1`.
- [x] Deepen `scripts/runtime_bootstrap.py` with verified local bundled artifacts/runtime namespaces while preserving the existing densification behavior.
- [x] Implement the Metashape Adapter: resolve executable and embedded Python ABI; probe existing imports; otherwise install exact verified wheels with bundled `runtime/pip.pyz` into LocalAppData staging; probe; atomically activate; reuse valid versions; preserve the previous active version on failure.
- [x] Replace `tools/metashape-python/active_path.txt` with an explicit resolved path returned to Rust and injected as `XPANO_METASHAPE_SITE_PACKAGES` only into the reconstruction supervisor/Metashape child process.
- [x] Reduce `scripts/configure_environment.ps1` to a developer/compatibility wrapper over Runtime Readiness. Remove online fallback, app-runtime self-repair, mutable writes under the install root and dependence on Metashape-provided pip.
- [x] Make Rust preflight consume structured JSON progress/results/error codes and retain cancellation, heartbeat and process-tree control.
- [x] Consolidate runtime probes and title-bar environment state onto Runtime Readiness results; existing pipeline executable checks remain a narrow post-readiness guard.
- [x] Update environment UI to distinguish bundled corruption, Metashape absent/dependencies missing/unsupported, environment ready and densification downloadable/ready.
- [x] Run unit, integration and packaging verification, including a copied Metashape Python 3.9 with site-packages removed, offline installation into a Unicode/space LocalAppData-style path, reuse, and a 3,756-file before/after hash inventory.
- [x] Run simulated clean-machine acceptance from the final formal release staging directory. No installer was built or published.

## Acceptance gates

- [x] All non-densification runtimes resolve from staged resources; Metashape installation uses `--no-index` and exact file hashes.
- [x] Metashape with missing NumPy/cv2 is repaired offline without admin rights and without writing to the Metashape or xPano install directory.
- [x] A Metashape Python without pip is repaired through bundled Python-3.9-compatible `pip.pyz`.
- [x] Supported ABIs select only compatible exact hashed wheel profiles; unsupported ABIs fail visibly without online fallback.
- [x] Interrupted, concurrent, corrupt or failed installs never activate a partial runtime and never destroy the last valid runtime.
- [x] App Python, COLMAP, FFmpeg and LichtFeld corruption fails visibly; installed resources are not self-modified.
- [x] Formal release staging contains no Torch/Open3D/model cache or `.venv-densify` payload.
- **Status:** complete; implementation and staged-runtime acceptance passed. NSIS build remains intentionally deferred until requested.

# Phase 24: xPano 0.2.0 release

- [x] Select semantic version 0.2.0 for Gaussian training, offline Runtime Readiness and retained preview sessions.
- [x] Align Cargo, Cargo lock, Tauri and frontend package versions.
- [x] Add release changelog and Git LFS rules for the bundled LichtFeld binary payload.
- [x] Run final review and complete release gates.
- [x] Commit the reproducible release source and create tag `v0.2.0`.
- [x] Build the formal NSIS installer and SHA-256 sidecar.
- [x] Install the produced package into an isolated current-user directory and verify installed hashes/runtime probes.
- **Status:** complete; release artifact, source commit and annotated tag are ready locally.

# Phase 25: xPano 0.2.0 full offline release

## Goal

Produce a separate Windows installer that retains the validated xPano 0.2.0 product and bundles every redistributable runtime needed for offline use, including both CPU and CUDA densification profiles. Installation and first use must not require network access; Metashape itself remains an external licensed application, while its xPano-required Python dependencies remain bundled and auto-provisioned offline.

## Plan

- [ ] Audit the densification manifests, artifact cache and release staging boundary; prove the complete CPU/CUDA artifact closure is locally available and hash-valid.
- [ ] Add the smallest packaging variant needed to stage full offline payloads without changing the standard 0.2.0 installer.
- [ ] Add or update packaging regressions for full-offline inclusion, hashes, naming and standard-package exclusion.
- [ ] Build a separately named full-offline NSIS installer and SHA-256 sidecar.
- [ ] Install into an isolated Unicode/space path with network unavailable to the app, verify runtime readiness and CPU/CUDA offline provisioning, launch responsiveness, then uninstall.
- [ ] Record release metadata and create a dedicated local annotated tag without moving `v0.2.0`.
- **Status:** paused by a release-blocking clean-machine DLL incident; the verified artifact cache remains local and reusable.

# Phase 26: Windows loader dependency closure and 0.2.1 rerelease

## Goal

Eliminate the reported `libunwind.dll` startup failure at its toolchain root, add a generic release gate for unresolved non-system PE imports, and ship a clean-machine-verified patch release.

## Plan

- [x] Reproduce the issue from the 0.2.0 release EXE import table and identify the actual Rust host/toolchain.
- [x] Add RED regression coverage for static gnullvm runtime linkage and mandatory import-closure validation.
- [x] Implement static unwind/CRT linkage and a recursive PE dependency-closure verifier in the formal installer chain.
- [x] Build from clean release outputs and prove `libunwind.dll` is absent from the EXE import table.
- [x] Bump to 0.2.1, run full tests/review, commit and tag.
- [x] Build, install and start under a sanitized PATH without toolchain directories; verify runtime resources and uninstall.
- **Status:** complete; clean installed runtime and Windows loader acceptance passed.

# Phase 27: installed extraction entrypoints and frames-per-second migration

## Goal

Fix the installed-user extraction failure caused by package-root import assumptions, eliminate the same class across every shipped Python entrypoint, replace the user-facing and persisted extraction control from seconds-per-frame to frames-per-second with safe legacy migration, and ship the next fully installed-accepted patch release.

## Plan

- [x] Reproduce the installed `ModuleNotFoundError: scripts` and inventory every shipped Python entrypoint/import boundary.
- [x] Trace extraction configuration from React through project JSON, Rust contracts, Python CLI, FFmpeg filters, frame estimates and progress.
- [x] Add RED tests for unrelated-working-directory launches, isolated Python, every runtime entrypoint, FPS semantics, frame-limit interaction and legacy project migration.
- [x] Implement the entrypoint bootstrap contract and migrate the extraction model/API/UI to frames per second without ambiguous double conversion.
- [x] Run synthetic and real-video extraction for panoramic and ordinary inputs, including Unicode/space paths and clean installed environment.
- [x] Review, bump version, commit, build NSIS, install, run extraction and verify manifest/runtime/uninstall before tagging.
- **Status:** complete; commit `37a630e`, tag `v0.2.2`, installer and installed extraction acceptance passed.

# Phase 28: explicit Metashape path and environment-resolution hardening

## Goal

Make a user-selected Metashape executable authoritative across readiness, dependency provisioning, reconstruction planning and process launch; then audit and harden every other runtime/tool resolution boundary so installed behavior does not silently depend on the developer machine.

## Plan

- [x] Reproduce the manual Metashape-path failure and trace UI -> project config -> readiness -> plan -> child process.
- [x] Inventory all external/bundled tool resolvers, persisted overrides, PATH fallbacks and child-process environment injection.
- [x] Add RED tests for explicit-path precedence, quoted/Unicode paths, invalid selections, persistence, readiness/execution agreement and sanitized environments.
- [x] Implement the smallest shared resolution contract needed to keep probes and execution on the same resolved executable/runtime.
- [x] Run focused and full Python/Rust/frontend gates plus clean installed-style runtime probes; do not build a release installer unless requested.
- **Status:** complete; explicit Metashape selection is authoritative and persisted, runtime resolution is hardened, all product gates passed, and no installer was built.

# Phase 29: re-export from completed Metashape PSX

## Goal

Add a stable `从 PSX 重新导出` action beside the alignment button for completed Metashape projects. It must reuse the saved PSX, skip extraction/matching/alignment, preserve manual camera corrections, and participate in the existing plan, job, cancellation, progress, artifact validation and results-refresh lifecycle.

## Plan

- [x] Trace the existing legacy re-export backend and the active reconstruction job lifecycle.
- [x] Add RED tests for re-export plan stages, eligibility, missing PSX rejection and pipeline arguments.
- [x] Add a dedicated re-export execution plan and start path without duplicating the pipeline engine.
- [x] Add the completed-project button and explicit disabled/error states to the active monitor UI.
- [x] Run focused and full Python/Rust/frontend gates plus a real saved-PSX re-export acceptance without rebuilding alignment or an installer.
- **Status:** complete.

## Phase 27 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Broad `rg` call passed `requirements*.txt` as a Windows path argument | 1 | Retain useful results and rerun narrowed searches without shell-style wildcard path arguments. |

## Phase 25 errors

| Error | Attempt | Resolution |
|---|---:|---|
| PowerShell passed wildcard paths such as `*.ps1` directly to `rg`, which Windows rejected as an invalid path | 1 | Switched to repository-wide `rg --files` enumeration followed by narrowed searches; no product files were changed. |
| A diagnostic import used bundled app Python before Runtime Bootstrap and could not import `torchvision` | 1 | Confirmed this is the intended environment boundary; inspected `.venv-densify` separately and did not use it as a release source. |
| The locked PyTorch CDN URLs under `download-r2.pytorch.org` returned HTTP 403 | 1 | Replaced only the transport URLs with the official `download.pytorch.org` endpoints; filenames, sizes and SHA-256 locks remain unchanged and official HEAD responses match expected sizes. |
| A broad recursive search under all of LocalAppData ran too long | 1 | Terminated it safely and narrowed inspection to `%LOCALAPPDATA%\tauri\NSIS`; confirmed NSIS v3.11. |
| Google lookup for an NSIS size-limit snippet timed out | 1 | Stopped relying on search snippets; final container choice will be verified with the actual 5.38 GB locked payload. |
| Terminating the PowerShell download cell left its Python child alive, and a concurrent curl resume corrupted the CUDA partial | 1 | Identified and stopped only the exact orphan PID, rejected the oversized/hash-mismatched partial and kept it out of the verified cache. |
| `cargo fmt` resolved through a different rustup GNU toolchain and reported rustfmt missing | 1 | Used the formatter beside the active custom gnullvm Cargo; it exposed a pre-existing repository-wide formatting baseline, so review stayed limited to changed hunks instead of rewriting unrelated code. |
| Installed acceptance retained only six files even though staging and installer sizes were complete | 1 | Reproduced in Unicode and ASCII paths, traced it to `NSIS_HOOK_PREINSTALL` changing `$INSTDIR` mid-install, removed the conflicting hook and added a regression contract. |

# Phase 30: lossless export acceleration and stable fallback

## Goal

Accelerate first-time Metashape image export and repeated PSX re-export without reducing resolution or JPEG quality, while keeping the release offline-capable, dependency-light, observable, and safe on machines without working GPU acceleration.

## Evidence baseline

- Previous real export: about 21 minutes for 1,013 cameras.
- 642 fisheye cameras consumed about 18 minutes 21 seconds; 371 frame cameras consumed about 2 minutes 28 seconds; COLMAP binary writing consumed about 10 seconds.
- Current NumPy remap averages below one CPU core, copies each source image five times, and reads the same camera projection collection five times.
- The formal offline runtime already provisions hashed OpenCV wheels for supported Metashape Python ABIs, so OpenCV is not a new release dependency.

## Plan

- [x] Finish auditing the active re-export transaction, exporter contracts, packaged OpenCV capabilities and current live-job state.
- [x] Define the pure cache/signature foundation covering source, sensor, strategy and image-contract version.
- [x] Add RED tests for cache hits, selective invalidation, missing/corrupt outputs, exporter-version changes, legacy projects and interrupted publication.
- [x] Change re-export publication to staging plus validation and marker-backed atomic model activation while retaining reusable images in place.
- [x] Add exporter-side byte-identical image reuse for unchanged signatures; regenerate only invalidated cameras or sensors.
- [x] Add RED performance/correctness tests for compiled remap backend selection and observable fallback.
- [x] Implement measured auto-selection across OpenCV CPU and OpenCL/UMat, with existing NumPy as the observable compatibility fallback.
- [x] Remove redundant source-image copies, fetch camera projections once, and add per-stage/backend/cache timing events.
- [x] Validate output dimensions, JPEG quality policy, pixel deltas and COLMAP semantics against the current exporter; retain strict NumPy when accelerated validation fails.
- [x] Run focused and full Python/Rust/frontend suites plus a real PSX before/after benchmark. No installer was built.
- **Status:** complete.

## Phase 30 errors

| Error | Attempt | Resolution |
|---|---:|---|
| A multi-file planning patch expected a Phase 29 heading that was absent from `findings.md` | 1 | Inspected each real file tail and appended Phase 30 independently; no product code changed. |
| A parallel audit included nonexistent `scripts/runtime_manifest.json`, causing the wrapper to reject the combined result | 1 | Split the checks and used the authoritative `runtime/bundled-runtime-manifest.json`; no product code changed. |
| A repository search passed PowerShell-style wildcard paths directly to `rg` | 1 | Reran against concrete `scripts` and `tests` directories; retained only valid output. |
| The initial cache test suite failed to import the intentionally missing module | 1 | Expected TDD RED state; implemented the minimal pure cache module and all six tests now pass. |
| Four remap backend tests failed because the selector/engine did not exist | 1 | Expected TDD RED state; implemented measured selection and fallback, then passed all seven exporter tests. |
| Re-export transaction tests initially failed because recovery/staging APIs did not exist | 1 | Expected TDD RED state; implemented marker-backed staging/publication/recovery and reached 3/4 passing tests. |
| The successful-stage test helper wrote the cache manifest before creating its parent directory | 1 | Fixed the test fixture to model the exporter contract; all four transaction tests pass. |
| A monolithic exporter-loop patch could not match historical mojibake comment lines | 1 | Split the edit around stable code boundaries and applied the cache integration incrementally; no unrelated lines were rewritten. |
| The camera signature test failed because the helper did not exist | 1 | Expected TDD RED state; implemented source/sensor/strategy signatures that exclude pose and the focused test passed. |
| Directly importing `export_colmap` under Metashape's standalone `python.exe` failed because that interpreter does not expose the application-only `Metashape` module | 1 | Isolated the pure remap benchmark with a test stub; OpenCV/runtime behavior was then measured successfully. |
| The first real Metashape probe failed before output because `export_colmap.py` used `Path` without importing it | 1 | Added the missing standard-library import; source PSX was never saved or modified, and the probe will be rerun from a clean temporary output. |
| Full Python regression found one legacy fake exporter that rejected the existing `show_dialog=False` keyword | 1 | Updated only the test double to accept exporter keyword arguments; product code was unchanged. |
| The first 1,013-camera benchmark wrapper inherited a 10-second nested shell timeout and terminated the launched process | 1 | Confirmed no orphan process remained, marker/staging cleanup completed, and all 3,581 live images/COLMAP counts were restored; rerun will use a long nested timeout with yielded monitoring. |
| Metadata-fast-path cache tests failed because records always rehashed and `source_record` had no cached input | 1 | Expected TDD RED state; added mtime-guarded SHA fallback and cached source reuse, then passed all eight cache tests. |
| Scalar tie-point projection improved speed but changed `images.bin` bytes | 1 | Rejected the optimization under the no-loss contract, restored the NumPy reference calculation and removed the allocation-avoidance test. |
| Remap selector test still patched `export_colmap` after the engine moved to `export_remap` | 1 | Updated the test seam to the owning module; product behavior was unchanged. |

# Phase 31: xPano 0.2.3 stable application release

## Goal

Produce a versioned Windows installer that includes the complete application runtime, all supported Metashape offline wheels, and the new accelerated export/cache modules. Verify the exact installer through release gates, dependency closure, isolated installation, offline runtime probes and hashes before committing and tagging the release. Densification remains the established separately provisioned large-runtime exception because NSIS cannot safely carry its multi-gigabyte CUDA payload.

## Plan

- [x] Audit version sources, changelog, full-offline artifact closure and formal installer command.
- [x] Bump every authoritative version source to 0.2.3 and document user-visible changes.
- [x] Run full source gates and build the formal NSIS installer with every non-densification dependency embedded.
- [x] Verify installer hash, staged manifest, required scripts/wheels/artifacts and PE DLL closure.
- [x] Install into an isolated Unicode/space path and validate startup, bundled runtime readiness, installed entrypoints and offline resources.
- [x] Uninstall the acceptance copy, perform final review, commit, and create annotated tag `v0.2.3`.
- **Status:** complete.

## Phase 31 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Initial parallel release audit included an optional missing directory command that returned exit 1, causing the wrapper to discard the other parallel results | 1 | Re-ran the repository, version and build-script audits independently; no product or release files were modified. |
| The runtime bootstrap downloader timed out after receiving 515,637,248 bytes of the 3.46 GB CUDA torch wheel | 1 | Preserved the verified partial download and switched to curl's resumable transfer with retry-all-errors; final size and SHA-256 will still be checked against the signed manifest before staging. |
| PowerShell `ConvertFrom-Json` rejected the large npm lockfile because dependency paths create names its legacy object converter cannot represent | 1 | Verified the two authoritative lockfile version lines directly and will rely on npm's parser during the frozen-install release gate. |
| Full-offline NSIS staging passed, but `makensis` could not memory-map the single 3.46 GB CUDA torch wheel | 1 | Kept the verified artifact store intact and returned to the product's established stable boundary: one formal installer containing every normal/Metashape dependency, with the optional densification runtime separately provisioned. |
| Silent acceptance install returned 0 but the requested `/D` path was absent | 1 | Confirmed NSIS correctly treated the existing registered xPano as an upgrade and installed 0.2.3 into its prior controlled Unicode/space acceptance location; all verification now targets the registry-authoritative path. |
| `pnpm audit` failed because the configured npmmirror registry does not implement npm's security-audit endpoint | 1 | Re-run the read-only audit against the official npm registry without changing the project's lockfile or persistent registry configuration. |
| A planning-file patch used PowerShell's mojibake rendering instead of the UTF-8 source text and did not match | 1 | Re-read the section explicitly as UTF-8 and applied the completion update against the real text. |

# Phase 32: Metashape NumPy self-repair for panorama alignment

## Goal

Prevent panorama alignment from failing when the user-selected Metashape Python lacks xPano's required NumPy/OpenCV runtime. The normal-photo path must remain unaffected, and any unsupported installation state must produce actionable diagnostics rather than a child-process traceback.

## Plan

- [x] Trace the panorama-only execution path from `run_xpano_tracks_job.py` through Metashape import to its runtime checks and child environment.
- [x] Reproduce the missing-NumPy state with a minimal fake Metashape runtime and record the exact current failure boundary.
- [x] Add failing regression coverage for automatic offline provisioning before panorama alignment starts.
- [x] Implement a single authoritative readiness/provisioning gate shared by all Metashape alignment modes, with structured diagnostics and no online dependency.
- [x] Run Python/Rust/frontend regression suites and an installed-style missing-runtime acceptance check.
- [x] Bump the release version, rebuild the offline installer and verify its hashes, import closure and clean-machine installation.
- **Status:** complete.

## Phase 32 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Foreground formal build exceeded the terminal's 120-second supervisory timeout while NSIS was still compressing | 1 | Confirmed `makensis` remained active, then restarted the formal build as a hidden process with captured logs and waited for its successful final output; only the second, timestamped installer is accepted. |

# Phase 33: Metashape script-local runtime activation

## Goal

Repair the 0.2.4 regression exposed by Metashape build 22170, where `metashape.exe -r` does not expose `PYTHONPATH` to the probe script. Ensure the offline runtime is activated within both scripts before `cv2`/NumPy-dependent imports, preserving the hash-locked offline provisioning contract.

## Plan

- [x] Preserve and localize the user runner traceback.
- [x] Add a RED test for script-local site-packages and DLL activation without `PYTHONPATH`.
- [x] Activate the verified runtime at the first executable lines of both the probe and alignment script.
- [x] Run focused/full source gates and prove the actual Metashape runner can activate an external runtime with `PYTHONPATH` removed.
- [x] Build the 0.2.5 installer and run installed resource, Metashape-runtime and restricted-GUI acceptance against the controlled release-install location.
- **Status:** complete.

## Phase 33 errors

| Error | Attempt | Resolution |
|---|---:|---|
| 0.2.4 Metashape build 22170 still raised `ModuleNotFoundError: cv2` in the runner probe | 1 | Rejected the `PYTHONPATH`-only assumption; replacing it with script-local `sys.path` and Windows DLL-directory activation. |
| Source-root `runtime_readiness probe` reported missing FFmpeg/ffprobe during parallel verification | 1 | Expected because source checkout does not contain formal staged binaries; isolated this check from the Metashape runner acceptance and will run it only after installer staging. |
| Broad recursive search for an installed acceptance executable timed out | 1 | Replaced it with the xPano uninstall registry key, which identified the controlled acceptance directory without scanning LocalAppData. |
| First silent installer invocation upgraded the pre-existing controlled 0.2.4 acceptance registration instead of creating the requested new directory | 1 | Kept the existing controlled test installation, verified its installed 0.2.5 manifest and runtime end-to-end, and did not touch the unrelated 0.1.1 user installation. |
| First GUI harness returned shell code 1 after reporting an alive process | 1 | Corrected the harness to preserve its explicit assertion result through cleanup; the second restricted-environment launch remained alive, had a main window, and responded after 12 seconds. |

# Phase 34: Metashape runtime path transport without environment inheritance

## Goal

Eliminate the remaining build-22170 failure by removing all correctness dependence on custom environment-variable inheritance between xPano and `metashape.exe -r`. Carry the verified site-packages path explicitly into both the probe and production pipeline, validate it before native imports, and emit actionable diagnostics when the path is absent or invalid.

## Plan

- [x] Preserve the second build-22170 traceback and identify the still-unproven transport assumption.
- [x] Trace every probe and production Metashape command constructor and argument parser.
- [x] Add RED coverage that removes all custom environment variables at the runner boundary.
- [x] Implement explicit runtime-path transport for probe and pipeline with fail-fast diagnostics.
- [ ] Run focused/full tests and a hostile-runner acceptance that strips inherited custom variables.
- [ ] Bump the patch version, rebuild the installer and validate the installed package before release.
- **Status:** in_progress.

## Phase 34 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Initial combined repository search used an incorrectly escaped alternation and `rg` rejected the unclosed group | 1 | Re-run with separate `-e` patterns rather than a composed regular expression. |
| New hostile-runner tests failed in five places against 0.2.5 | 1 | Expected RED state: the probe command omitted the path argument, both production commands omitted it, the probe could not import fake Metashape, and re-export had no activation hook. |
| First GREEN run had one assertion compare a Windows path against JSON-escaped output text | 1 | Parsed the structured probe JSON before comparing resolved module paths; product code was already behaving correctly. |
| Active Python did not include pytest | 1 | Used the repository's unittest suite, which is also the formal release gate. |
| A PowerShell wildcard and one over-complex audit regex were invalid for `rg` | 1 | Replaced both with repository-root searches and simpler patterns. |

## Phase 34 continuation checklist

- [x] Replace Tauri-to-Python environment-only runtime transport with an explicit CLI argument.
- [x] Persist the verified path in both multi-track and legacy Python job configurations.
- [x] Prefer the job-scoped path for alignment and PSX re-export while retaining old-entrypoint fallback.
- [x] Complete full repository audit and regression gates.
- [x] Build version 0.2.6 installer and complete installed hostile-runner acceptance.

## Phase 34 completion

- [x] Explicit runtime path crosses Tauri, xPano Python job configuration and every production Metashape runner.
- [x] Environment inheritance is compatibility-only and hostile-runner coverage removes both relevant variables.
- [x] Offline wheel provisioning, release staging, installed resources, DLL closure, GUI startup and entrypoints are verified.
- [x] Version 0.2.6 installer and checksum are published under `dist`.
- **Status:** complete.

# Phase 35: post-release clean-machine dependency audit

## Goal

Re-audit xPano 0.2.6 for environment-dependent failures that can be hidden by the development machine. This phase is review-only; no product source changes are authorized.

## Plan

- [x] Inventory all external process and runtime entrypoints.
- [x] Recheck explicit Metashape runtime transport and script-local activation.
- [x] Smoke-test staged Python, FFmpeg, ffprobe and COLMAP with a system-only PATH.
- [x] Audit native PE imports for embedded Python, COLMAP and LichtFeld Studio.
- [x] Recheck optional densification bootstrap and runner activation under isolated Python semantics.
- [x] Classify confirmed defects, residual OS prerequisites and test gaps.
- **Status:** complete; confirmed defects require a follow-up implementation turn.

## Phase 35 errors

| Error | Attempt | Resolution |
|---|---:|---|
| LichtFeld Studio does not exit for `--help`, so the loader smoke harness timed out | 1 | Confirmed no process remained; used process survival plus recursive PE import closure instead of treating it as a conventional CLI. |
| A PowerShell `Expand-Archive` probe rejected a `.whl` extension | 1 | Used the already staged wheel contents and direct PE inspection; no audit artifact remained. |
| Several broad `rg`/parallel wrappers returned exit 1 when an optional search had no matches | 1 | Re-ran required checks independently and preserved only successful evidence. |

# Phase 36: deterministic clean-machine runtime hardening

## Goal

Eliminate the confirmed cross-machine dependency failures with one durable contract: every non-inbox native dependency is hash-locked and app-local, every external tool is actually started during readiness, external Python package roots are activated explicitly rather than through environment inheritance, and release acceptance disables user site-packages.

## Plan

- [x] Add RED tests for COLMAP/MSVC staging, deterministic inbox classification, densification isolation and real tool probes.
- [x] Add a dedicated hash-locked Windows x64 runtime payload and deploy the required DLLs beside both COLMAP and embedded Python.
- [x] Replace densification `PYTHONPATH` correctness dependence with script-local activation and retain DLL-directory handles.
- [x] Disable user site-packages for every bundled Python child process.
- [x] Make Runtime Readiness execute bounded FFmpeg, ffprobe, COLMAP and LichtFeld loader probes with actionable diagnostics.
- [x] Extend formal release validation to recursive PE closure for embedded Python, COLMAP and LichtFeld using a fixed Windows inbox allowlist.
- [x] Run focused/full tests, build a fresh release staging tree, and verify under a system-only PATH with user site disabled. Do not build an installer in this phase.
- **Status:** complete; source and release staging are accepted, installer intentionally not built.

## Phase 36 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Direct execution of `release_staging.py` could not import the new sibling runtime module | 1 | Added script-root activation and an unrelated-working-directory entrypoint regression test. |
| Recursive PE audit found additional true Windows inbox imports (`msi`, `wsock32`, `authz`, `xmllite`, `avicap32`) | 1 | Added only Windows components to the fixed allowlist; the six VC/OpenMP DLLs remain explicitly non-inbox. |
| LichtFeld imports NVIDIA's driver-provided `nvcuda.dll` | 1 | Classified it separately as a hardware-driver dependency rather than calling it Windows inbox or bundling a vendor driver. |
| Isolated embedded Python exposed an ambient `tqdm` dependency used by the shipped extractor | 1 | Added the offline wheel, embedded package, readiness import and isolated entrypoint coverage. |

# Phase 37: xPano 0.2.7 installer release

## Goal

Publish a versioned Windows x64 installer containing the completed deterministic runtime hardening, then verify the installer hash and staged runtime contract without embedding the separately managed multi-gigabyte densification payload.

## Plan

- [x] Advance all authoritative application metadata and changelog to 0.2.7.
- [x] Run the formal installer build with its full Python, frontend, Rust, staging and PE dependency gates.
- [x] Verify the release-stage manifest, installer SHA-256 and versioned output names.
- [x] Perform a silent controlled installation and restricted installed-runtime acceptance, then cleanly uninstall it.
- **Status:** complete.

## Phase 37 errors

| Error | Attempt | Resolution |
|---|---:|---|
| Legacy PowerShell rejected `ConvertFrom-Json -AsHashtable` during a pre-build version audit | 1 | Used Node's JSON parser for the large lockfile and direct PowerShell matching for Cargo metadata. |
| The first hidden GUI acceptance returned shell code 1 after proving the process alive and responsive | 1 | Preserved the assertion result across cleanup explicitly; the repeated acceptance returned 0 with a responsive main window. |
# Phase 38: Metashape build-22170 mixed-resolution assertion repair plan

## Goal

Produce an implementation-ready plan that replaces the backbone workflow's repeated stateful matching with one unified match and staged panorama/flat alignment, while keeping execution plans, UI stages, sensor validation, tests, and real-runner acceptance consistent.

## Plan

- [x] Preserve and rank the incident evidence and root-cause boundary.
- [x] Define exact behavior for mixed, panorama-only, flat-only, advanced mixed, and legacy modes.
- [x] Enumerate Python, Rust, frontend fixture, documentation, and evidence-gated EXIF changes.
- [x] Define RED tests, complete source gates, and build-20221/build-22170 acceptance matrices.
- [x] Document forbidden shortcuts and common implementation-agent mistakes.
- [x] Publish the implementation handoff in `docs/METASHAPE_SINGLE_MATCH_BACKBONE_FIX_PLAN.md` without changing business code.
- **Status:** complete; implementation is not part of this planning turn.

# Phase 39: Metashape single-match backbone implementation and acceptance

## Goal

Land the one-match/two-stage-alignment implementation and prove it through source gates and real Metashape runs, without claiming build-22170 compatibility until that exact native runner and large incident dataset complete successfully.

## Plan

- [x] Replace the repeated backbone `matchPhotos` calls with one fresh-chunk unified match and staged panorama/flat alignment.
- [x] Add pre-native camera/sensor validation and incompatible source-sensor rejection.
- [x] Synchronize the durable backend execution graph, development UI fixtures, workflow docs, and tests.
- [x] Complete code review and source gates: Python 260/260, Rust 89/89, frontend 44/44, lint, production build, Python compilation, and diff check.
- [x] Complete a real Metashape 2.2.1 build 20221 default-40,000-keypoint acceptance in a fresh temporary output directory; reopen the resulting PSX and verify exports. The medium case contains 334 fisheye and 138 flat cameras; all 472 aligned and 1,808 exported images were present.
- [x] Add a read-only Backbone acceptance verifier for captured native logs, PSX presence, alignment summaries, and COLMAP exports; prove it against the corrected build-21778 472/472 acceptance output.
- [ ] Complete the authoritative build 22170 run against the incident-scale mixed-resolution dataset; record one-match log, memory/time, per-type aligned counts, PSX reopen, and export validation.
- [ ] Resolve any build-22170-only result before a release/version bump.
- **Status:** in progress; source, build-20221, and nearby build-21778 evidence are green, but the build-22170 gate remains mandatory.

# Phase 40: xPano 0.2.8 acceptance hardening and release

## Goal

Ship the single-match mixed-resolution repair in a new 0.2.8 installer, with evidence bound to the exact PSX, per-type alignment quality gates, error-path state restoration coverage, and installed-artifact verification.

## Plan

- [x] Add RED regression tests for per-type alignment metrics, panorama quality loss, unrelated PSX rejection, mandatory acceptance expectations, and flat-camera state restoration after panorama alignment failure.
- [x] Implement the smallest production changes in the Metashape summary, project diagnostic, authoritative acceptance verifier, and bounded panorama solve stabilization.
- [ ] Run focused and full Python/Rust/frontend/build quality gates and review the complete pending release diff.
- [ ] Advance all authoritative metadata and changelog entries from 0.2.7 to 0.2.8.
- [ ] Build the formal self-contained Windows installer from source and verify the staged manifest/script hash and single-match invariant.
- [ ] Perform a controlled silent install, verify the installed script/runtime/GUI contract, then commit the complete intended release state.
- **Status:** in progress.

# Phase 41: Metashape alignment fidelity root-cause study

## Goal

Explain why material that aligns correctly through Metashape's GUI can become unaligned or geometrically chaotic through xPano, using the exact current pipeline plus official Metashape 2.2/2.3 manuals, Python API references, and official tutorials. This phase is analysis-only: no product code, packaging, or release changes.

## Plan

- [x] Trace media preparation, manifest construction, sensor/calibration grouping, camera groups, matching, alignment, optimization, auto-leveling, and COLMAP export end to end.
- [x] Build an exact xPano-versus-Metashape-GUI parameter/state comparison for panorama-only, flat-only, ordinary-video, and mixed inputs.
- [x] Extract authoritative 2.2 and 2.3 semantics and recommendations from official manuals, Python API references, and Agisoft tutorials.
- [x] Correlate user symptoms and retained real-run evidence with each divergence; separate native misalignment from export/view-transform corruption.
- [x] Rank confirmed defects, strong risks, and unverified hypotheses, then propose a test matrix and repair direction without implementing it.
- **Status:** complete; analysis only, with no product, version, package, or installer changes.
# Phase 42: xPano 0.1.0 vs current Metashape alignment regression audit

## Goal
Identify the exact post-0.1.0 behavioral changes that can explain why the same material aligns correctly in the downloaded 0.1.0 build but produces large geometric errors in the current build. This phase is diagnosis-only: no product code, release metadata, or installer changes.

## Steps
- [x] Verify the downloaded 0.1.0 source against the repository tag.
- [x] Compare import/calibration, Station lifecycle, matching/alignment/optimization, component acceptance, and export behavior.
- [x] Trace material deltas to introducing commits where repository history contains the change.
- [x] Separate confirmed causal regressions from pre-existing defects and unrelated changes.
- [x] Report the most likely cause, triggering dataset characteristics, and evidence limits.

## Errors Encountered
- `session-catchup.py` found unsynced context but its console rendering stopped on a GBK `UnicodeEncodeError`; recovered from the existing planning files and git state instead.
- The first native fisheye probe used a nonexistent `Metashape.app.build` property and stopped before model comparison; the retry uses the supported `Metashape.app.version` property while the executable banner supplies the build number.

# Phase 43: truthful alignment completion and Component-isolated export

## Goal

Prevent failed Metashape runs from being recovered as successful reconstructions, export exactly one user-visible Component, and restore a simple Station-preserving panorama-only path without imposing an alignment-rate gate.

## Plan

- [x] Require a structured successful alignment/export report before Rust can finalize a Metashape reconstruction.
- [x] Preserve a failed run's PSX and allow only an explicit re-export action to transition it back to completion.
- [x] Inventory Components, select the largest aligned Component by default, and filter every exported camera to that Component.
- [x] Persist alignment rate, Component selection, and warnings; expose them in the reconstruction monitor.
- [x] Route panorama-only Backbone work through whole-chunk match/alignment while retaining Station constraints.
- [x] Run Python, Rust, TypeScript, and production-build static/mock acceptance without launching Metashape.
- **Status:** complete; real Metashape/material testing intentionally deferred by user instruction.

# Phase 44: retain panorama Station constraints in mixed alignment

## Goal

Keep every dual-fisheye panorama group as a Metashape Station through panorama optimization, flat-camera attachment, and final global optimization in both Backbone mixed-material and explicit Mixed modes.

## Plan

- [x] Add RED mock regressions proving mixed-material optimization never converts panorama groups to Folder.
- [x] Remove the two mixed-path Station-to-Folder transitions while preserving the existing single-match and staged camera solve.
- [x] Keep the existing stage graph but describe the step as Station-constraint handling rather than release.
- [x] Update workflow documentation and planning findings without adding repair heuristics or alignment-rate gates.
- [x] Run focused/full Python tests, Rust/frontend static gates, and code review; do not run Metashape or real materials.
- **Status:** complete; static/mock acceptance passed and real Metashape/material testing was intentionally not run.

# Phase 45: xPano 0.2.9-preview installer

## Goal

Version the reviewed alignment/runtime/UI changes as `0.2.9-preview` and produce a fresh standard Windows x64 NSIS installer through the authoritative release pipeline.

## Plan

- [x] Audit the complete pending release diff, version sources, required runtime inputs, and prerelease-version compatibility.
- [x] Update synchronized package/Tauri/Cargo versions and add the `0.2.9-preview` changelog entry.
- [x] Run full Python, Rust, frontend, packaging, and five-axis release review gates.
- [x] Build a fresh standard installer through `scripts/build_installer.ps1` without skipping verification.
- [x] Verify the exact installer name, size, SHA-256 sidecar, release manifest version, and staged dependency closure.
- **Status:** complete; the reviewed `0.2.9-preview` standard Windows x64 installer and matching SHA-256 sidecar are ready in `dist`.

## Errors Encountered

- A combined prerequisite probe exited nonzero because standalone `makensis.exe` was not on `PATH`; Tauri manages the NSIS toolchain itself, so release readiness will be determined by the authoritative Tauri build rather than this optional shell lookup.
- PowerShell `ConvertFrom-Json` again rejected the large npm lockfile during a version-consistency probe; use Node/npm's JSON parser for this file, as already established by the earlier release audit.

# Phase 46: mixed-photo import geometry recovery

## Goal

Allow valid panorama-plus-photo projects to pass the Metashape import boundary when one declared photo sensor group yields multiple actual Metashape sensor geometries, without forcing incompatible photos onto one calibration sensor.

## Plan

- [x] Add a RED regression reproducing landscape/portrait geometry inside one declared photo sensor group.
- [x] Partition imported cameras by actual Metashape source-sensor geometry and create one Frame sensor per partition.
- [x] Preserve fail-fast behavior for missing source sensors and downstream invalid dimensions; emit one bounded split diagnostic.
- [x] Update workflow findings and replace the obsolete rejection contract in documentation.
- [x] Run focused/full Python, Rust/frontend static gates and five-axis review; do not package unless separately requested.

## Errors Encountered

- A parallel verification command returned exit code 1 because `rg` correctly found none of the obsolete rejection phrases. Re-ran the check with `Select-String`, which confirmed zero matches without treating the empty result as failure.

**Status:** complete; source and documentation are corrected and statically accepted. The exact user's original photo dataset remains unavailable for a native Metashape rerun, and the existing installer predates this fix.

# Phase 47: xPano 0.2.9-preview-7142057camerafix installer

## Goal

Publish the accepted mixed-photo sensor-geometry recovery as the exact standard Windows x64 release version `0.2.9-preview-7142057camerafix`.

## Plan

- [x] Synchronize Cargo, Tauri, npm/lockfile version metadata and add a narrowly scoped changelog entry.
- [x] Verify prerelease parsing and run source/release preflight gates against the versioned tree.
- [x] Build a fresh standard NSIS installer through `scripts/build_installer.ps1` without skipping verification.
- [x] Verify the release manifest, staged Camera fix, PE metadata, installer filename, size, and SHA-256 sidecar.
- [x] Complete the five-axis release review and record remaining acceptance limits.

**Status:** complete; the verified standard Windows x64 installer and SHA-256 sidecar are ready in `dist`.

## Errors Encountered

- A combined `rg` inspection returned exit code 1 because `pnpm-lock.yaml` intentionally contains no application-version field. Re-ran with `Select-String`; the lockfile is dependency-only and needs no version edit.

# Phase 48: repeated mixed-photo import failure root-cause audit

## Goal

Determine why `0.2.9-preview-7142057camerafix` still fails at `metashape.frame.import` using the new user evidence, without changing product code or publishing another package.

## Plan

- [x] Preserve and transcribe the new screenshot evidence, including the actual source-sensor partitions.
- [x] Trace the imported Fisheye/Frame partitions through sensor creation, calibration copying and Backbone validation.
- [x] Inspect manifest preparation and Metashape import behavior to determine why one ordinary-photo identity group contains both source types.
- [x] Separate confirmed root cause from hypotheses that require the uncropped inner exception or original workspace.
- [x] Deliver a precise causal explanation and the correct repair boundary; make no code changes.

**Status:** complete.

## Errors Encountered

- An initial combined source search used a nonexistent file and a PowerShell-incompatible `scripts/*.py` argument, causing `rg` to exit before returning the other reads. Re-ran with `--glob '*.py'` and explicit existing paths.
- A workspace-evidence search returned exit code 1 when no matching local filenames were found, which cancelled the combined read. Re-ran through `Select-String`; the user's `E:\20260702LGGY\X5\xPano` workspace is not mounted on this machine.
- A source query guessed a nonexistent fisheye function name and returned no match, cancelling its combined read. Re-ran with `Select-String` over the real `_apply_exif` call sites.
- A broad recursive search for additional `metashape.exe` copies returned exit code 1 without results and cancelled its first parallel probe. Re-ran commands independently; the authoritative local runner is Metashape 2.2.1 build 20221 and its packaged NumPy/OpenCV runtime probe passes.
- The first native Phase 48 probe intentionally exited 1 after reproducing the production validation failure. It produced the required full traceback and is diagnostic evidence, not an unexpected probe failure.

# Phase 49: stable mixed-material camera identity import

## Goal

Replace the two order-dependent Metashape camera selectors with one readable key-based import contract so panorama, ordinary-video and photo tracks retain their true camera identities after native `addPhotos` reordering.

## Plan

- [x] Add a RED regression whose fake Metashape chunk deliberately reorders cameras after each `addPhotos` call.
- [x] Identify newly imported cameras by camera-key difference and validate requested/imported count and paths.
- [x] Return imported cameras directly from panorama/photo track functions and remove the second positional track slice.
- [x] Run focused tests, the native Metashape mixed-material probe, full source gates and five-axis review.
- [x] Record verification and remaining limits; do not build or publish an installer unless separately requested.

**Status:** complete.

## Errors Encountered

- The first parallel context read failed because `rg` returned exit code 1 for the absence of a root `AGENTS.md`. The retry used independent PowerShell reads; only an unrelated nested LichtFeld source contract exists outside the files in scope.
- A recursive PowerShell `AGENTS.md` search timed out after reaching the unrelated `.codex_tmp` tree. No applicable nested contract exists under `scripts/` or `tests/`.
- A final test-count filtering command returned exit code 1 because PowerShell handled unittest's stderr stream separately; its captured output still reported `Ran 23 tests` and `OK`, matching the preceding direct successful test run.

# Phase 50: xPano 0.2.9-preview-cameraidentityfix installer

## Goal

Publish the accepted stable Camera-key import repair as a fresh standard Windows x64 installer named `0.2.9-preview-cameraidentityfix`.

## Plan

- [x] Synchronize npm, Cargo, Tauri and lockfile versions and add a narrowly scoped changelog entry.
- [x] Run version/release preflight and confirm the authoritative build prerequisites.
- [x] Build a fresh standard NSIS installer through `scripts/build_installer.ps1` without skipping verification.
- [x] Verify staged source identity, release manifest, PE version metadata, installer filename, size and SHA-256 sidecar.
- [x] Complete the five-axis release review and record remaining distribution limits.

**Status:** complete.

## Errors Encountered

- The first parallel training-UI read used an `rg` pattern beginning with `--xp-`, which `rg` parsed as an option and rejected. Retried with the `--` option terminator and independent result handling.

# Phase 51: LichtFeld training workspace UI redesign

## Goal

Audit the existing embedded LichtFeld training workspace and define a clear, maintainable UI redesign that removes developer-facing explanatory copy and gives configuration, execution, progress, and results an explicit product workflow. This phase is design-only and must not change product implementation.

## Plan

- [x] Inventory the current training components, layout, responsive behavior, state model, and shared xPano visual tokens.
- [x] Separate user decisions and task states from diagnostic/developer information.
- [x] Define the recommended information architecture, page regions, component hierarchy, interaction states, and responsive rules.
- [x] Compare simpler alternative layouts and document why the recommended structure is the best fit for a desktop production tool.
- [x] Produce an implementation sequence and acceptance checklist without editing UI code.

**Status:** complete; design-only plan recorded in `docs/LFS_TRAINING_WORKSPACE_UI_REDESIGN_PLAN.md`, with no product UI implementation changed.

## Errors Encountered

- The first post-refactor TypeScript gate found two unused Lucide imports in `TrainingTaskView.tsx`. Removed the imports before any runtime verification and reran the gates independently.

# Phase 52: LichtFeld training workspace UI implementation

## Goal

Implement the approved state-adaptive LichtFeld workspace without changing the training backend or parameter protocol, then verify logic, frontend quality and real rendered layouts across supported desktop viewports and themes.

## Plan

- [x] Add RED tests for preset derivation, workspace mode and actionable start blockers.
- [x] Implement the pure training view model and keep existing defaults/protocol unchanged.
- [x] Replace the fixed split dashboard with setup, running, result and recovery views plus a bounded diagnostics drawer.
- [x] Add explicit custom-preset behavior, submitted-config locking, result-folder action and stop confirmation.
- [x] Add deterministic development preview states for visual verification without affecting production runtime.
- [x] Run focused and full frontend tests, lint, production build, screenshot/console/layout checks and final five-axis review.

**Status:** complete; user accepted the rendered UI and requested close-out. No release package was built.

## Errors Encountered

- The Playwright `.sh` wrapper could not run because Bash is unavailable in this Windows PowerShell environment. Used its equivalent direct `npx --package @playwright/cli playwright-cli` command instead.
- Headed Chrome exited with code 13 before opening. Headless Edge succeeded with zero console warnings and produced the required 1280x800 and 1024x720 acceptance screenshots.

# Phase 53: installed LichtFeld runtime failure diagnosis

## Goal

Determine why LichtFeld Studio trains correctly from the source workspace but the installed xPano at `E:\FastProgram\xPano` repeatedly fails to load `rmlui/rendering.rml`, renders an incomplete UI and cancels training. This phase is diagnosis-only: preserve evidence and identify the exact packaging or launch boundary before changing product code or rebuilding an installer.

## Plan

- [x] Inventory the installed, repository, release-stage and original LichtFeld runtime trees, including the exact relative path and hashes for `rendering.rml` and neighboring assets.
- [x] Trace release staging and installer inclusion rules to determine whether assets are omitted, flattened or copied under the wrong root.
- [x] Trace the source and installed launch paths, working directory and environment to determine whether runtime lookup differs after installation.
- [x] Reproduce the installed failure with the smallest direct launch and compare it with a known-good runtime launch.
- [x] State the confirmed root cause, affected layer and minimal repair boundary without modifying product code or publishing a package.

**Status:** complete; root cause confirmed as an extended-prefix path passed into the MinGW LFS runtime, causing mixed-separator `std::filesystem` lookups to miss existing assets. No product code or release artifact was changed.

## Errors Encountered

- The first planning-file update targeted a heading that does not exist in `progress.md`, so the atomic patch was rejected without changing any file. Retried against the actual file tails.
- The first parallel runtime inventory used a PowerShell `foreach (...) { ... } |` construct that this host rejected as an empty pipe element. It produced no inventory; the retry collects results into an explicit array before formatting.
- A parallel source-read batch was cancelled when the broad `rg getExecutableDir` pipeline returned exit code 1 after emitting matches. No files were changed; subsequent reads use settled independent calls and narrower exact files.
- No additional errors after narrowing the probes. The direct normal/extended LFS comparison and native filesystem probe completed successfully and established the root cause.

# Phase 54: xPano 1.0.0-preview Windows installer

## Goal

Ship the accepted training UI and camera/runtime fixes as `1.0.0-preview`, including a regression-guarded repair that prevents bundled LichtFeld Studio from receiving a Windows verbatim executable path that breaks its MinGW resource lookup.

## Plan

- [x] Add a RED Rust regression for drive and UNC verbatim executable paths, then implement the smallest Windows child-path normalization at the LichtFeld launch boundary.
- [x] Run focused Rust tests and reproduce the installed LFS resource lookup with the normalized path.
- [x] Synchronize npm, Cargo, Tauri and lockfile versions to `1.0.0-preview` and add a focused changelog entry.
- [x] Run version/release preflight and the complete source verification gates.
- [x] Build the standard Windows x64 NSIS installer and verify manifest contents, versions, hashes and staged source identity.
- [x] Complete the five-axis release review and report the final artifact; do not commit, tag or publish externally.

**Status:** complete; the verified `1.0.0-preview` Windows x64 installer and matching SHA-256 sidecar are ready in `dist`.

## Errors Encountered

- The first post-fix source search passed an `rg` pattern beginning with `--executable` before the option terminator, so `rg` rejected it as a flag. Retried with a literal search form.
- `cargo fmt --check` is unavailable because `rustfmt` is not installed for `stable-x86_64-pc-windows-gnu`. This is a local tooling gap, not a source failure; verification will use an available formatter toolchain if present plus compiler and diff checks.

# Phase 55: 0.1.0/current alignment-quality differential and Component inventory diagnosis

## Goal

Establish evidence-backed root causes for current xPano producing lower Metashape alignment quality than `0.1.0` with the same Metashape version. Audit the complete import-to-export behavior and independently determine why a PSX with two Components is represented as one Component in xPano. This phase is diagnosis-only and must not change product behavior.

## Plan

- [x] Inventory the authoritative `0.1.0` and current entrypoints, manifests, extraction scripts, defaults, and persisted reconstruction artifacts.
- [x] Build an exact behavior matrix for import grouping, image dimensions/encoding/EXIF, sensor creation, camera model/group assignment, Metashape match/alignment/optimization calls, retries, and camera state transitions.
- [x] Compare available old-good and new-bad workspaces to distinguish input/preprocessing differences from solver-policy differences.
- [x] Trace Component enumeration from Metashape PSX through summary/report persistence, Rust project state, and frontend selector rendering.
- [x] Rank confirmed causes and contributing risks by evidence and blast radius; explicitly separate proven defects from hypotheses.
- [x] Report the smallest maintainable correction boundaries and required regression coverage without editing product code or packaging.

**Status:** complete; the current solver contract and Component inventory/export defects are isolated with native Metashape 2.3 evidence. No product behavior or release artifact was changed.

## Errors Encountered

- The first calibration probe used a raw Windows string ending in a backslash and failed at parse time. The path was split at a safe boundary and the probe then ran successfully under Metashape 2.3.0.
- A local Metashape 2.2.1 runner does not expose `EquidistantFisheye`; the compatibility comparison was rerun with the installed 2.3.0 build used by the old-good/current-bad evidence.

# Phase 56: restore 0.1.0 Metashape alignment contract and progress truthfulness

## Goal

Restore the proven `0.1.0` panorama calibration bootstrap and panorama-first incremental alignment behavior, while making the execution plan, stage events and frontend progress display describe the actual Metashape calls. Component inventory/export is intentionally outside this phase.

## Plan

- [x] Add failing regression tests for legacy-compatible panorama calibration, panorama-only behavior, and mixed-material incremental call ordering.
- [x] Add failing plan/progress tests proving mixed reconstruction exposes separate panorama match/align and flat incremental match/align stages.
- [x] Implement the smallest compatibility helper and sequential alignment flow without adding a second solver abstraction.
- [x] Synchronize backend execution plans, development preview stages and user-facing stage labels with the restored flow.
- [x] Run focused tests, complete Python/frontend/Rust gates appropriate to the touched layers, static compile checks and diff hygiene.
- [x] Perform a five-axis review and record remaining risks; do not build or publish a release.

**Status:** complete; the `0.1.0` calibration/alignment contract and truthful progress graph are restored. Static and automated source gates passed; no installer was built.

# Phase 57: correct Component inventory, selection and re-export plan

## Goal

Design the smallest maintainable repair that makes xPano enumerate every Metashape Component correctly, lets the user select a Component based on real per-Component camera counts, exports the selected Component reliably, and refreshes stale PSX-derived state without mixing Component logic into alignment.

## Plan

- [x] Re-audit the Python Component helper, alignment report writer, initial export and PSX re-export call sites against Metashape's active-Component semantics.
- [x] Re-audit Rust persistence and frontend selector behavior, including when reports become stale after manual PSX edits.
- [x] Define one activation/restoration boundary and exact failure semantics for missing, empty or changed Components.
- [x] Specify data-contract changes, stage/progress changes and backward compatibility for existing projects.
- [x] Specify RED tests and static/native acceptance cases in implementation order.
- [x] Record a complete implementation plan with explicit non-goals and common implementation mistakes; do not change product behavior in this phase.

**Status:** complete; implementation plan recorded in `docs/METASHAPE_COMPONENT_REPAIR_PLAN.md`. No product behavior or release artifact was changed.

# Phase 58: implement Component inventory, selection and export repair

## Goal

Implement the approved Phase 57 design end to end: truthful active-Component inventory, selected-Component leveling/export, live PSX inspection before re-export, strict key revalidation, truthful progress stages and regression coverage. Do not package a release.

## Plan

- [x] Add RED Python tests for active-scoped inventory, restoration, strict selection and selected export behavior.
- [x] Implement the Python activation/inventory boundary and integrate initial/re-export reporting and export.
- [x] Add the read-only PSX inspection entrypoint and release-staging guard.
- [x] Add RED Rust tests, then implement validated asynchronous inspection and execution-plan stages.
- [x] Add frontend view-model tests, then implement live inspection and conditional Component confirmation UI.
- [x] Run focused and full Python/Rust/frontend gates, native read-only inspection where available, diff hygiene and five-axis review.

**Status:** complete; Component inventory, selection and export now use the live active-Component contract end to end. No installer was built.

## Errors Encountered

- The first new release-staging regression called a nonexistent `self.fixture` helper. It was corrected to use the file's existing `make_fixture` pattern before confirming the intended missing-resource RED failure.
- The first focused Rust run correctly exposed one older exact-stage-list assertion that had not yet included `metashape.component.select`; the expectation was updated and the full reconstruction module returned green.
- `rustup` is not available on this machine, so no new formatter component could be queried or installed. Compiler, tests, lint, production build and `git diff --check` all passed without rewriting unrelated files.

# Phase 59: package 2.0.0-preview Windows release

## Goal

Synchronize the application version to `2.0.0-preview`, run the repository's full release gates, build a new dependency-complete Windows x64 installer containing the restored alignment and Component repairs, and independently verify its manifest and SHA-256. Do not commit, tag or publish externally.

## Plan

- [x] Audit every authoritative version source and the existing standard release command.
- [x] Add/execute version-consistency evidence, then update only authoritative version files to `2.0.0-preview`.
- [x] Run Python, Rust and frontend source gates plus release-staging coverage.
- [x] Build the standard dependency-complete Windows x64 installer with the existing release pipeline.
- [x] Independently verify installer name/version/hash, staged manifest closure and critical Component scripts.
- [x] Perform the five-axis release review and record final artifact details.

**Status:** complete; the verified `2.0.0-preview` standard dependency-complete Windows x64 installer and SHA-256 sidecar are ready in `dist`. No commit, tag or external publication was performed.

## Errors Encountered

- A PowerShell `rg` version probe parsed embedded quotes as path fragments and failed after the npm/Tauri values had already been printed. Retried Cargo versions with `Select-String`; all six authoritative values are `2.0.0-preview`.
- Two PowerShell runtime inventory attempts used a `foreach (...) { ... } |` construct rejected by this host as an empty pipe element. No files changed; subsequent inventory stores loop output in an explicit array before formatting.
- The first installer build passed source tests and Rust release compilation but release staging rejected `tools/offline-wheels/metashape/numpy-1.26.4-cp39-cp39-win_amd64.whl` as missing or corrupt. No installer was produced; the exact manifest artifact is being restored from a hash-matching local payload before retrying.
- A diagnostic wheel-tree inventory repeated the host-incompatible `foreach (...) { ... } |` PowerShell shape and failed without changing files. A manifest-driven retry found all five required Metashape wheels absent and verified exact size/SHA-256 matches for all five in the prior local full-offline payload.
- The second installer attempt passed bundled-wheel validation but failed closed on `runtime/windows-x64/msvcp140.dll`. This revealed a broader source-payload cleanup; the entire Windows runtime manifest will be audited and restored in one pass before another build attempt.
- The first combined source-closure probe had a PowerShell/Python nested-quote syntax error and changed nothing. The corrected probe validated both manifests, then found three further source omissions: bundled `python.exe`, bundled `tqdm` and the app `tqdm` wheel. The complete bundled Python tree is being compared before missing-only restoration.

# Phase 60: investigate original LUT restoration support

## Goal

Determine exactly how the updated upstream `pano_extractor_GUI.py` implements LUT restoration, whether the behavior can be integrated into xPano without regressing extraction speed, preview consistency or alignment inputs, and produce a maintainable implementation plan. This phase is research/design only and must not change product behavior.

## Plan

- [x] Reverse-engineer the upstream LUT file contract, validation, image transform and GUI state flow.
- [x] Trace xPano's current panorama import, extraction, thumbnail, manifest and alignment-input boundaries.
- [x] Compare dependencies, color/depth/geometry behavior, hardware acceleration constraints and large-media performance.
- [x] Select the smallest integration boundary and define compatibility, fallback and failure semantics.
- [x] Record an implementation sequence, regression tests and static/runtime acceptance criteria with explicit non-goals.

**Status:** complete; feasibility is confirmed and the implementation sequence is recorded in `docs/LUT_RESTORATION_INTEGRATION_PLAN.md`. No product code or behavior was changed.

## Errors Encountered

- The first synthetic FFmpeg LUT probe decoded subprocess stderr with the Windows GBK default. FFmpeg echoed the Unicode/special-character test path as UTF-8, causing `UnicodeDecodeError` and then a diagnostic-only `None.strip()` failure. No product files changed; the probe will be rerun with explicit UTF-8 replacement decoding.
- The first identity-LUT pixel comparison used blue-fastest cube ordering, which is not the `.cube` red-fastest ordering expected by FFmpeg and produced an intentional-looking channel swap. The test fixture was corrected before drawing any color-fidelity conclusion.
- A source read targeted nonexistent `scripts/prepare_project.py`; repository search identified the actual project media entrypoint as `scripts/run_xpano_prepare_project.py`. No files changed; subsequent tracing uses the registered entrypoint.

# Phase 61: implement per-video LUT restoration

## Goal

Implement the approved LUT restoration plan end to end while preserving the exact no-LUT extraction path, existing decoder fallback, preview/alignment consistency and project v3 compatibility. Do not package or publish a release.

## Plan

- [x] Add RED Rust contract, validation and track-invalidation tests.
- [x] Add RED Python filter, safe-path snapshot, fallback and project-propagation tests.
- [x] Implement the minimal Rust and Python data/extraction path and turn focused tests green.
- [x] Add RED frontend helper tests, then implement video-only LUT selection/edit/clear controls.
- [x] Run focused and full Python/Rust/frontend gates, build, diff hygiene and final code review.

**Status:** complete; LUT restoration is implemented and verified across contracts, extraction, project preparation and media UI. Baseline source commit `6157b7e` remains the pre-feature checkpoint; no installer was built.

# Phase 62: bundled camera LUT presets

## Goal

Extend the completed per-video LUT feature so a user can enable one simple color-restoration switch while importing an `.osv` panorama video. It selects an xPano-bundled DJI Osmo 360 D-Log M -> Rec.709 preset. `.insv` remains manual-LUT-only. Never store an installation-specific resource path in a project, and fail visibly if the selected bundled resource is absent or corrupt.

## Plan

- [x] Inspect the existing per-track LUT contract, import type detection, resource resolver, release staging and the upstream reference implementation.
- [x] Obtain the user-supplied DJI D-Log M -> Rec.709 `.cube` asset and record its source/hash. Its header identifies Mavic 3 Pro rather than Osmo 360; retain that caveat in the bundled LUT documentation.
- [x] Add a stable builtin preset identifier to the project contract alongside the existing manual path, with strict mutual-exclusion, old-project compatibility and stale/invalidation tests.
- [x] Resolve builtin identifiers only at runtime through the packaged resource resolver; validate the selected resource hash before the media job becomes running.
- [x] Update panorama import and track editing UI: restoration switch is available for `.osv` panorama tracks only and defaults off; enabling assigns the DJI builtin preset. `.insv` keeps the current manual selection control and no automatic preset.
- [x] Stage the LUT assets into the release resources and add release-manifest coverage.
- [x] Run full suites, production build and static packaging checks. A real FFmpeg extraction through the bundled LUT has passed.

## Decisions

| Decision | Rationale |
|----------|-----------|
| Switch defaults off; automatic preset applies only to `.osv` | User explicitly scoped automatic restoration to DJI Osmo 360 D-Log M. `.insv` stays manual because Insta360's official download page ships distinct LUT archives by model. |
| Persist `builtin:<id>` rather than a packaged path | Application resources move between development, NSIS installation and upgrades. A stable ID keeps projects portable and lets the runtime resolve the local installed asset. |
| Builtin and custom selections are mutually exclusive | One effective LUT is easy to explain and prevents accidental LUT stacking. |
| Missing/tampered builtin LUT fails the job | Continuing without selected restoration would silently create different pixels than the project configuration promises. |

**Status:** complete. The supplied LUT is packaged exactly as provided and bound to the `.osv` switch by product decision; its non-Osmo 360 header remains disclosed in `luts/README.md`. No installer was built.

## Errors Encountered

- A read-only PowerShell size inventory used a host-incompatible `foreach (...) { ... } |` pipeline and failed without changing files. Commit scope was verified instead through Git status and explicit staging.
- The first focused Cargo command passed two test filters even though Cargo accepts one; it changed nothing and was rerun with the shared `color_lut` filter, which produced the intended RED failure.
- A repository search used Unix-style wildcard path arguments that Windows `rg` rejected. The retry used `-g '*.rs'` and found the complete Rust literal surface.
- The first project-propagation test returned a mocked frame outside the project root, correctly triggering the existing artifact-containment guard. The fixture was moved under `work/frames`; product code was unchanged.
- The first real special-path probe sent literal Chinese characters through a PowerShell stdin encoding boundary, turning them into Windows-invalid `?` characters before Python ran. The retry used ASCII `\u` escapes, created the intended Unicode path, and completed successfully.
- Playwright's default Chrome channel exited during startup with code 13. The same CLI workflow was rerun with the installed Edge channel and completed desktop-width UI inspection and screenshots.
- `cargo fmt --check` remains unavailable because `cargo-fmt.exe` is not installed for `stable-x86_64-pc-windows-gnu`. Rust compilation and all 104 Rust tests pass; no toolchain component was installed or repository formatting rewritten.

# Phase 63: restoration and style LUT chain

## Goal

Allow every video track to apply one optional user-selected style LUT. An `.osv` panorama track may additionally apply the existing bundled restoration preset first. Non-Log video must be able to use only the style LUT. Preserve old projects that use `colorLutPath`, keep the no-LUT path unchanged, and limit the product to two ordered transforms rather than an arbitrary LUT graph.

## Design

| Layer | Stored setting | Applies to | Order |
|-------|----------------|------------|-------|
| Restoration | existing `colorLutPreset` | `.osv` panorama only | first |
| Style | new `styleLutPath` | panorama and ordinary video | second |

`colorLutPath` is the old single-manual-LUT key. It migrates to `styleLutPath` when an old project is read or next saved. `colorLutPreset` remains the existing stable packaged-resource identifier, avoiding a needless rename of the portable preset contract.

The FFmpeg graph is conditional: `fps -> [restore lut3d] -> [style lut3d] -> yuvj420p`. A non-Log source with only a style LUT uses `fps -> style lut3d -> yuvj420p`; a source with neither LUT retains the current `fps`-only graph and no temporary LUT directory.

## Plan

- [ ] Add RED contract/migration tests: old `colorLutPath` becomes `styleLutPath`, serializes only the new key, and restoration may coexist with style.
- [ ] Replace the single manual-path field across Rust, TypeScript and Python with `styleLutPath`, retaining old-key read compatibility and clearing both layers when a track becomes non-video.
- [ ] Keep strict preflight: style must be an existing `.cube` on a video track; restoration remains `.osv`-only and hash-checked; failures occur before status/marker mutation.
- [ ] Propagate separate restoration/style paths through project preparation and track builders.
- [ ] Replace the one-file extractor staging with one safe temporary bundle (`restore.cube`, `style.cube`), validate each through FFmpeg, and reuse the ordered graph for both panorama eyes/streams and normal-video frames.
- [ ] Redesign media controls: `.osv` gets a default-off restoration toggle plus style picker; `.insv` and ordinary video get only the style picker. Leaving eligible `.osv` clears restoration but preserves style.
- [ ] Test direct style usage, restoration-plus-style order, legacy migration, special paths, no-LUT baseline, eye parity, and preflight non-mutation; then run all gates and a real two-stage FFmpeg smoke extraction.

## Decisions

| Decision | Rationale |
|----------|-----------|
| Maximum two stages | Covers the real workflow without an unbounded, slow and hard-to-explain LUT graph. |
| Fixed restoration-before-style order | Style LUTs are normally authored for display-referred Rec.709/sRGB imagery, not camera Log input. |
| Style works without restoration | Required for Rec.709/non-Log footage; it does not impose a D-Log transform. |
| Preserve the no-LUT fast path | LUT processing is CPU work; material without either option keeps current extraction cost and output behavior. |

**Status:** planned only. No Phase 63 product code has been written and no release build is in scope.

# Phase 66: user-facing README

## Goal

Replace the repository README with a concise Chinese guide written from the perspective of an xPano user. It must explain the normal workflow, major capabilities, project/output layout, supported inputs, external-tool requirements, and safety/quality limits without documenting developer implementation details.

## Plan

- [x] Inventory current user-visible workflows from UI, Tauri commands, scripts, packaging resources, and existing product documents.
- [x] Cross-check import types, processing stages, project artifacts, environment dependencies, and recovery boundaries against source code.
- [x] Draft the root README with task-oriented sections: prerequisites, quick start, feature map, project files, and important notes.
- [x] Review every factual statement against source, then run Markdown and repository-status checks.

## Decisions

| Decision | Rationale |
|----------|-----------|
| Write for end users, not developers | The requested document should help a new user complete a project instead of exposing internal architecture. |
| Document current limitations explicitly | Alignment quality, external Metashape ownership, and on-demand densification setup affect whether a user can finish safely. |
| Keep the guide concise | The README should be a first-use guide; advanced implementation detail belongs in `docs/`. |

**Status:** complete. The root README is now a concise source-backed Chinese user guide. No application code, package, or release artifact changed.
# Phase 67: LFS launch and packaging reliability hardening

## Goal

Make the bundled LichtFeld Studio v0.5.3 runtime reproducible, isolated, diagnosable, and release-gated on Windows x64. Keep Gaussian training and on-demand densification as separate runtime chains. Do not change LFS training semantics or upgrade the upstream runtime during this phase.

## Detailed Plan

### A. Freeze the LFS supply chain and release boundary

- [x] Baseline the exact v0.5.3 archive, upstream commit, license, complete portable layout, and current parameter/progress behavior as regression fixtures.
- [x] Replace the untracked-directory build input with a pinned, content-addressed archive and tracked manifest. The manifest records the upstream commit, archive name/size/SHA-256, sentinels, and the filtered per-file inventory.
- [x] Route installer assembly through one staging contract. The former portable assembler delegates to the installer path so no package variant can silently omit `runtime/lichtfeld-studio`.
- [x] Make staging fail closed for missing, modified, extra, non-portable, or incomplete LFS files; retain PE import-closure, architecture, license, resource-layout, and relocated-tree checks.
- [ ] Add an explicit release-signing gate. A production release must either carry the configured signing identity or fail; an unsigned development build must be visibly marked and excluded from promotion.

### B. Establish one production runtime boundary

- [ ] Introduce a small Rust `LichtfeldRuntime` resolver used by readiness, start-training, and diagnostics. It returns only the packaged executable, bundled supervisor Python/scripts, resource root, profile root, normal Windows executable path, and the manifest version.
- [ ] Move duplicated path/file checks out of `run_lichtfeld_preflight`, `training_readiness_blocking`, and `start_training_job_blocking` into that resolver. Keep `plain_windows_path` on the third-party executable and its working directory; do not reintroduce `\\?\\` paths.
- [ ] Make production resolution package-first and non-overridable. Development overrides remain available only behind an explicit development-build switch, never through ordinary environment variables or the user PATH.
- [ ] Launch the bundled Python supervisor with an allowlisted child environment: remove Conda/venv/Python/plugin/DLL-injection variables, keep Windows system variables and GPU-driver discovery, set only the required UTF-8 and user-site controls, and record the sanitized launch contract in diagnostics without serializing the environment itself.

### C. Isolate persistent LFS state without breaking normal GUI use

- [ ] Verify the upstream-supported config/profile controls with a native LFS launch before changing ownership. Do not invent unsupported command-line flags or modify the bundled LFS tree at runtime.
- [ ] Keep xPano-owned LFS state under `%LOCALAPPDATA%\\xPano\\lichtfeld-studio\\<manifest-version>`, separate from any globally installed LichtFeld profile. Split stable GUI preferences from per-run temporary state so a stale training session cannot affect the next run.
- [ ] Allocate per-job launch metadata and log directories under the existing project training run. Clean only xPano-created stale lock/process metadata after proving the owning process has exited; never erase a user LFS profile or previous training artifacts.
- [ ] Add an upgrade rule: a manifest-version change creates a fresh xPano profile, preserves the prior one for rollback, and gives a deterministic migration/cleanup notice rather than sharing incompatible state.

### D. Make readiness one authoritative, bounded protocol

- [ ] Keep full hashing in staging; at runtime hash only the manifest sentinels and verify the executable's normal-path resource layout. Cache a successful check by manifest version plus sentinel metadata, then invalidate it if the install changes.
- [ ] Expand `runtime_readiness.py lichtfeld-probe` into the sole structured preflight: manifest/resource mismatch, executable `--version`, CUDA driver load/device count, Vulkan loader/device count, valid COLMAP input, writable output, profile creation, and child startability.
- [ ] Give every terminal preflight failure a stable public code, a concise recovery action, and raw technical detail for the diagnostic bundle. Distinguish runtime corruption, missing VC/DLL dependency, driver missing, unsupported GPU, Vulkan failure, bad dataset, and unwritable output.
- [ ] Have AppShell and the training workspace consume the same cached result. The start action must rerun the fast critical checks immediately before writing job state, then fail before `begin_job_impl` on a non-ready runtime.

### E. Make launch, progress, cancellation, and restart robust

- [ ] Preserve the current GUI-first command and MCP-based parameter application. Do not retry or restart a native LFS process automatically after a crash or user close.
- [ ] Replace the absolute 120-second start limit with an inactivity watchdog. Valid stdout, log growth, MCP listener availability, dataset-load completion, parameter acknowledgement, and runtime progress refresh activity; a live but slow large dataset is allowed to continue.
- [ ] Retain a separate hard upper bound for a completely silent child and configurable short graceful-shutdown/kill bounds for cancel. A timeout always records the last meaningful activity, elapsed idle time, process ID, and native exit code.
- [ ] Treat manual LFS-window closure and child exit as one terminal state. Drain final stdout/log bytes, capture exit code, mark the project job failed or interrupted exactly once, release the pipeline lock, and leave the next Start action enabled.
- [ ] Keep progress polling non-fatal. MCP failures remain visible diagnostics while stdout/log progress continues; training only fails on explicit LFS fatal output, native exit, inactivity timeout, or missing completed artifact.

### F. Add actionable diagnostics and support artifacts

- [ ] Write a per-run structured launch record before spawning: app/LFS/manifest versions, resolved normal paths, selected GPU probe result, command flags with data paths redacted to project-relative form, profile generation, timestamps, and preflight result.
- [ ] On failure, collect bounded stdout/stderr tail, LFS log tail, exit status, watchdog history, sentinel outcomes, GPU/Vulkan diagnostics, and process-tree information. Do not collect user environment variables, unrelated file names, or complete media paths.
- [ ] Provide one UI action to open/export this diagnostic bundle, and map public failure codes to recovery text that never claims a DLL is missing when the true fault is a driver, asset, stale state, or process crash.

### G. Keep densification isolated and validate the installed product

- [ ] Do not merge LFS GUI training with the on-demand Torch/Open3D densification runtime. The two have independent manifests, Python activators, logs, cache roots, and recovery messages.
- [ ] On densification startup, revalidate the selected CPU/CUDA profile and issue a CUDA probe only for the CUDA profile; retain CPU fallback semantics where the task remains meaningful.
- [ ] Add regression tests before each implementation boundary, then run unit/integration tests for Python, Rust, and frontend contracts; use staged-layout tests rather than source-only tests for packaging claims.
- [ ] Run installed/relocated smoke tests from paths containing spaces and Chinese characters, with a polluted host Python/PATH and pre-existing user LFS state; cover a missing sentinel, DLL/driver failure, invalid Vulkan, manual close, silent timeout, slow-progress startup, rerun after failure, and upgrade/profile-version separation.
- [ ] Only after all gates pass: construct a signed preview installer, verify the staged and installed manifests, retain the previous installer plus hashes for rollback, collect a small preview cohort's diagnostic bundles, and promote only if no runtime-class failure remains unexplained.

## Decisions

| Decision | Rationale |
|----------|-----------|
| Pin v0.5.3 instead of upgrading LFS | The observed defects are packaging, isolation, readiness, and diagnostics failures. An upstream upgrade would add an unrelated compatibility variable. |
| One staging implementation for installer and portable outputs | Duplicate packagers already produce different LFS capabilities and are a direct release risk. |
| Full validation at build time, fast sentinel validation at startup | Hashing the entire 576 MB runtime on every page visit is unnecessary; build-time closure plus cached critical-file verification gives reliability without startup regressions. |
| Fail fast on corrupt bundled files or unsupported GPU | Continuing can only crash or produce an invalid training run; there is no semantically equivalent fallback for GUI LFS training. |
| Do not bundle `nvcuda.dll` or install a CUDA toolkit | `nvcuda.dll` belongs to the NVIDIA display driver. Copying it app-local would hide the real driver incompatibility and is not a valid repair. |
| No automatic training retry | Retrying native crashes can duplicate GPU allocations or create competing output writers without correcting the cause. |

**Status:** supply-chain/staging work is implemented in the active worktree and has focused packaging acceptance. Runtime-boundary, isolation, watchdog, diagnostics, release signing, and installed-product acceptance remain planned; no new installer may be produced before those items pass.
