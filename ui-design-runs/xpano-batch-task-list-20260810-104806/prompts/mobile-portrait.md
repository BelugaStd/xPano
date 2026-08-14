Create a polished narrow-window stress-test UI mockup for the xPano batch-processing task queue.

Audience: xPano desktop users viewing the application at an unusually narrow portrait-sized window.
Primary workflow: scan queued projects, understand stage status and errors, start or stop the queue, and switch to manual mode.
Design system direction: extend the current xPano 2.0.1 light liquid-glass desktop UI with navy brand actions, cyan data progress, compact Simplified Chinese typography, low-contrast borders, and soft translucent panels. This is a responsive hierarchy test, not a consumer mobile redesign.
Design DNA blend: Operational Dashboard with supporting Mobile-First progressive disclosure and AI Tool status clarity.

Visual rules:
- Original, production-realistic interface implementable in React/CSS.
- Use Simplified Chinese labels.
- Preserve the same tokens, icon style, panel material, and status colors as the desktop xPano references.
- Avoid a bottom navigation tab bar, hamburger navigation, KPI cards, search, filters, decorative gradients, neon effects, and developer explanations.

Viewport: one portrait narrow-window composition, approximately 430x900.

Layout requirements:
- Compact title bar with xPano, `批量任务`, environment status icon, and essential window controls.
- Header row inside the workspace with `任务列表`, compact count `6 项`, and primary `新增任务`.
- Task rows become two-level stacked items: first line project name, queue state, and detail chevron; second line the three-stage chain; third line thin progress and time.
- Show an active task, queued tasks, a completed task, and one failed task whose summary remains visible without expansion.
- Use progressive disclosure for paths and logs; do not hide stage labels or failure meaning.
- Sticky bottom action area with queue progress and two rows of controls: primary `开始批量` / `继续批量`, conditional `停止队列`, and a clear secondary `不使用任务模式` at the lower right.
- Touch targets should be at least 44px, but visual density should still feel like xPano desktop software.

Output: one single portrait UI screen only. Do not include desktop views, landscape views, annotations, browser chrome, phone hardware, or multiple viewport mockups.
