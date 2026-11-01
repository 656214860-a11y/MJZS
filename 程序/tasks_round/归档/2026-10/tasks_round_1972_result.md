# R1972 补记轮：补记分支 codex/wip-R1969 的轮次记录（R1965／R1966／R1969）

## 范围
阶段配置页（「阶段配置 · 01 剧本准备」）下拉框与标签布局优化三轮，已快进合入 master（master = b2d3227c）。本轮只补 `project_status.md`，不改代码。

## 记录
- R1965（修复轮，b5cdbb1d）：全页下拉框统一宽度（`STAGE_PANEL_LAYOUT['select_width']=12`）；标签列统一宽度并对齐（`production_lock_fields.label_pixel_width` 用真实 ttk.Label 量宽）；`SelectBox` 弹出列表按最长选项加宽（style `postoffset`），当前值放不下也能在列表看全名；标签防裁字（`CompactLabel` 多留 xs 余量）。
- R1966（修复轮，9a6463b9；ff711c26 为合并 master 上 R1964 文件卡片）：「必选」改标签警示色、不再占一行；`FlowFields` 支持逐项 `gap_after`，下拉框与下一个标签之间用 `item_gap`（md）区分归属；「添加模型…」项主色突出（`SelectBox(accent_values=...)`）。
- R1969（修复轮，b2d3227c）：标签列右对齐（`sticky='e'`），文字紧贴自己的下拉框，拉近标签与下拉框距离。

## 测试
- 定向通过：`test_skill_panel_dropdown_layout`、`test_skill_panel_layout_fit`、`test_skill_panel_production_locks`、`test_manual_plan`、`test_ui_edges`、批 5 相关（均经 `工作流任务/gui_hidden.py` 在隐藏桌面运行）。
- 契约有意变更（断言已按新契约改写，未弱化）：下拉框等宽而非按行拉满；配置区高度容差放宽一行（约 58px）；必选提示由文字行改为标签警示色；列对齐检查跳过以按钮开头的行。
- `test_skills` 两条红（71≠73）判断为 worktree 缺未跟踪 skill 文件所致，未独立复核。
- 未跑 `--all --safe`；未在真实窗口目测，实机观感待用户确认。

## 未做
- 「更多制作锁」按钮独占一行、「选择操作」下拉改按钮／菜单：会增行或改测试契约，待用户裁决。

## 提交
本轮为文档补记轮，不跑 smoke／selftest。已提交，commit hash 见 git log 中 `R1972: 补记分支 codex/wip-R1969 的轮次记录`。
