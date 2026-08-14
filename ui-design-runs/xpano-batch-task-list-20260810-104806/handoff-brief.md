# UI Image Design Handoff

## Product Direction

- Product / feature: xPano 独立顶层批量任务页。
- Audience: 夜间串行处理多个摄影测量与高斯训练工程的 Windows 用户。
- Primary workflow: 新增并配置任务 → 排队 → 串行执行 → 扫描进度/耗时/异常 → 进入任务详情。
- Design DNA blend: Operational Dashboard + AI Tool process clarity + restrained spatial desktop tool。
- Overall tone: 最新 xPano 的浅色液态玻璃桌面工具；紧凑、可靠、克制，不做传统管理后台。

## Source UI References

- Latest media workspace: `reference-latest-media.png`
- Latest reconstruction workspace: `reference-latest-reconstruction.png`
- Latest training workspace: `reference-latest-training.png`
- Latest source dark theme: `latest-xpano-source-maximized.png`

## Generated Images

- Desktop: blocked — 当前宿主没有可用的内置 `image_gen` 工具。
- Mobile portrait: blocked — 同上；该稿仅作为窄窗口压力测试。
- Mobile landscape: blocked — 同上；该稿仅作为窄窗口压力测试。

未擅自切换 CLI 生成，因为 CLI 需要额外 API key 且用户未授权。三份独立英文 prompt 已完成，可在图像工具可用后分别生成。

## Visual Tokens

- Color palette: light `#F8FAFC`, brand `#0C3868`, data `#18A7B5`; dark `#060E18`, brand `#6EA7DB`, data `#35D0D8`; success `#16A36F`, warning `#B7791F`, danger `#D64550`.
- Typography: 复用 xPano 中文 sans 栈；计时、百分比和序号使用等宽数字。
- Spacing: 4px 基础，常用 8/12/16/20/24px。
- Border radius: 控件 8–10px，主面板 14–16px。
- Elevation / shadow: 低对比边框、柔和面板阴影；运行态不用强发光。
- Iconography: Lucide 风格 14–16px 线性图标。
- Motion intent: 140–260ms，状态、折叠、行重排和进度变化；支持 reduced-motion。

## Layout System

- Desktop: 单行标题栏 + 单一全高队列账本 + 单行批量模式底栏。
- Mobile portrait: 任务行上下分层，路径与日志渐进披露，底栏变两层操作区。
- Mobile landscape: 每行左右两块，无水平滚动，底栏保持全局状态和动作。

## Component Inventory

- Navigation: 顶层批量页标题栏；批量模式不显示手动四工作区切换。
- Primary work area: 固定表头、可滚动任务列表、空状态。
- Task row: 重排、身份、三阶段链、进度、时间、错误摘要、详情箭头。
- Controls: 新增任务、开始/继续批量、条件式停止队列、不使用任务模式。
- Menus: 仅任务允许时提供编辑、重新入队、移除；不做常驻按钮墙。
- States: empty, draft, queued, running, complete, failed, interrupted, cancelled。

## Responsive Rules

- Shared elements: 任务身份、阶段含义、失败含义、全局队列状态和主动作。
- Desktop-only elements: 完整路径摘要和独立时间列。
- Portrait adaptation: 两层任务行、底部两层动作区。
- Landscape adaptation: 身份/阶段与状态/进度左右分块。
- xPano 产品最低目标仍为桌面 1024px；两张移动稿不是移动端产品承诺。

## Implementation Notes for web-design-engineer

- Build target: React 19 + Tailwind/CSS，复用现有 `AppShell` token、`liquid-topbar`、`app-bottom-dock`、`glass-control` 和 motion classes。
- Assets needed: 不新增插画或品牌图；继续使用 xPano 图标和 Lucide 图标。
- Interactions: 行聚焦/Enter 打开、拖拽排序、错误展开、更多菜单、开始/停止确认、退出批量模式。
- Accessibility: 状态不只靠颜色；明确焦点环；禁用原因；键盘上移/下移；可靠 ETA 才显示。
- Verification: 1280x720、1440x900、1024x720；浅/深主题；空/多任务/长路径/失败/运行；底栏不溢出。

## Open Questions

- 无阻塞产品问题。图像生成待宿主提供内置工具后再完成三次独立生成。
