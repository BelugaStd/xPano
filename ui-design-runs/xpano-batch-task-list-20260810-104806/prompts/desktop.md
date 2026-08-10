Create a polished, production-realistic desktop UI mockup for the xPano Windows batch-processing task queue.

Audience: photogrammetry and Gaussian-splatting users who queue multiple projects overnight.
Primary workflow: scan all queued projects, see each project's media preparation, alignment, and training state, start or stop the serial queue, and open a task for details.
Design system direction: faithfully extend the current xPano 2.0.1 source UI — a slim single-line frameless title bar, full-height workspace, slim bottom dock, translucent liquid-glass panels, restrained navy brand actions, cyan data progress, compact Chinese desktop typography, low-contrast borders, and soft shadows. The default theme is very light blue-white, not a conventional dark admin dashboard.
Design DNA blend: Operational Dashboard with supporting cues from AI Tools and a restrained spatial desktop tool.

Visual rules:
- Original design, not a copy of any existing brand or website.
- Realistic React/CSS desktop application, not a marketing poster.
- Use Simplified Chinese interface labels exactly where specified.
- Preserve the visual language of the provided current xPano source references: `reference-latest-media.png`, `reference-latest-reconstruction.png`, and `reference-latest-training.png`.
- Use consistent typography, spacing, 8–16px radii, Lucide-style outline icons, subtle translucency, and precise alignment.
- Avoid KPI card walls, a left navigation sidebar, a permanent right detail panel, nested cards, decorative gradients, neon glow, large empty areas, fake charts, or developer-facing explanations.

Viewport: one desktop Windows application screen, 16:9, approximately 1440x900.

Layout requirements:
- Top frameless title bar: xPano icon and wordmark on the left, a divider, then `批量任务`; on the right show `环境就绪`, theme controls, and window controls. Do not show `打开工程` on this multi-project page.
- Main workspace: one large translucent queue panel filling the space between title bar and bottom dock.
- Queue panel header: left title `任务列表` with compact inline text `共 6 项 · 1 项运行 · 3 项等待 · 1 项失败`; right side has the only primary creation button `新增任务`.
- Fixed table header and a scrollable list of six realistic task rows.
- Each task row contains: reorder handle and sequence number; project name plus shortened folder path and media count; a three-node stage chain labeled `素材准备`, `对齐重建`, `高斯训练`; progress/message; elapsed time and ETA; one chevron detail entry.
- Show varied states: one active alignment task at 63% with a thin cyan progress bar, three queued tasks, one completed task, and one failed task with a readable red summary `训练启动失败 · 已跳过，队列继续`.
- The active row uses only a faint navy tint and a 3px left marker. Completed rows are quieter. Do not render meaningless 0% bars for waiting tasks.
- Bottom dock: left queue state `正在运行第 2 / 6 项`; center current project name, global thin progress bar, `38%`, and `剩余 06:42:18`; right side buttons `停止队列`, primary `开始批量` or `继续批量` as appropriate, and the far-right secondary button `不使用任务模式`.
- Make hierarchy and button reachability obvious without adding any search, filter, refresh, pause, bulk-delete, clear-completed, or separate-log buttons.

Output: one single desktop UI screen only. Do not include mobile frames, annotations, browser chrome, device mockups, or multiple viewport mockups.
