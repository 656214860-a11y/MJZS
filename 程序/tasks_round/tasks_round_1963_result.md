# R1963：修复轮——侧栏滚轮只滚目录列表，顶部标题与齿轮固定

## 三个问题

- 轮次类型：修复轮（用户报告：鼠标上下滚动时标题「漫剧助手」和齿轮一起滚上去被遮挡）。
- 测试：默认冒烟 8/8 通过；定向 27/27 通过；受影响模块门禁 1888 条中 7 个红文件全部为已知既有红（idea_chat 14、pet_ui 云位置 1＋登录闸门 5、BriefTint 1、writing_api 2），本轮新增的两个既有红（page_paint_metric、window_resize_coalescing）在改为浮层实现后转绿。架构门禁与全量安全回归未触发、未运行。
- 欠账：未新增欠账。

## 根因与修复

- 根因：侧栏标题「漫剧助手」原来是可滚动内容框（ScrollForm）里的第一个子控件，滚轮滚动整个画布时标题跟着滚走；齿轮锚定在标题上，也跟着被带走。
- 修复：把标题改成 `place` 在侧栏视口顶部的**固定浮层**——不参与 pack，不改变滚动画布视口高度，只覆盖在画布最上层；滚动内容顶部让出与浮层等高的空当，「我的项目」从浮层下沿开始。滚轮仍然只滚画布，标题和齿轮不再移动。
- 附带：`fit_sidebar` 的垂直留白改为读 `side` 的实际 padding（顶部现在是浮层高度，不再写死 `sidebar_padding×2`）。

## 改动文件

- `程序/desktop.py`：`_build_sidebar` 标题改为固定浮层；滚动内容顶部 padding 与浮层等高。
- `程序/desktop_layout.py`：`fit_sidebar` 的固定高度预算改为按 side 实际 padding 计算。
- `程序/tests/test_ui_batch3_shell.py`：滚动测试补两条断言——滚轮滚动和滚到底后，`app_title` 与齿轮的 `winfo_rooty` 保持不变。

## 验证

- 定向（经 `工作流任务/gui_hidden.py` 隐藏桌面）：`test_page_paint_metric` + `test_window_resize_coalescing` + `test_ui_batch3_shell` + `test_desktop_compact_layout` → **27/27 OK**。
- 默认冒烟：**8/8 通过**。
- 受影响模块门禁 `smoke_test.py --affected desktop desktop_layout`：1888 条，7 个红文件——`test_idea_chat`（14 条，R1960 起即存在的既有红）、`test_pet_ui`（云位置 1＋登录闸门 5，R1962 已核）、`test_ui_edges` BriefTint（1，R1961 已核）、`test_writing_api`（2，本轮在基线 worktree `3c61f2f6` 上核过）。本轮最初把标题放进 pack 布局时曾让 `test_page_paint_metric`／`test_window_resize_coalescing` 变红，改为浮层实现后两处转绿。
- 架构门禁：未触发，未运行。
- 全量安全回归：未触发，未运行。

## 提交

- 已提交：分支 `codex/wip-R1963`；提交包含上述 4 个文件，最终 commit 以 `git log -1` 为准。

## 备注

- 工作树开轮前已有未提交改动：`程序/project_status.md`、`.claude/settings.local.json`（用户既有改动），本轮未触碰。
- 认领：`round_claim.py next` → R1963，分支 `codex/wip-R1963`。
