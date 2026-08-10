Create a polished landscape narrow-window stress-test UI mockup for the xPano batch-processing task queue.

Audience: xPano desktop users working in a short, wide window while long-running projects execute.
Primary workflow: horizontally scan queue order, stage status, progress, elapsed time, and errors while retaining immediate queue controls.
Design system direction: extend the current xPano 2.0.1 light blue-white liquid-glass UI with compact Chinese typography, navy brand actions, cyan data progress, subtle borders, and soft depth. Keep the desktop-tool character.
Design DNA blend: Operational Dashboard with supporting compact mobile landscape ergonomics and AI Tool process transparency.

Visual rules:
- Original, production-realistic React/CSS interface.
- Use Simplified Chinese labels.
- Preserve the same tokens, iconography, radii, and panel material as current xPano.
- Avoid squeezing the full desktop table, a sidebar, KPI cards, charts, search, filters, decorative gradients, neon glow, and permanent logs.

Viewport: one landscape narrow-window composition, approximately 900x430.

Layout requirements:
- Slim title bar with xPano, `批量任务`, environment icon, theme and window controls.
- One main queue panel. Its compact header shows `任务列表 · 6 项` and the primary `新增任务` button.
- Use a landscape-native two-column row structure: left identity and three-stage chain, right current status, thin progress, elapsed time, and detail chevron.
- Show three visible rows at once: active, queued, and failed. The failed row must clearly say `已跳过，队列继续`.
- Keep the list vertically scrollable; do not add horizontal scrolling.
- Slim sticky bottom dock with `第 2 / 6 项`, current task, global progress, `停止队列`, primary `继续批量`, and far-right `不使用任务模式`.
- Keep action targets reachable and text readable despite limited height.

Output: one single landscape UI screen only. Do not include desktop views, portrait views, annotations, browser chrome, device hardware, or multiple viewport mockups.
