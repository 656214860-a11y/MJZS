# R2876 功能轮结果：三虎状态小字下移到头像正下方，猫爪列底边与之对齐
<!-- round-evidence: {"commit_base": "17beaef5", "credential_hits": 0, "evidence_sha256": "0cd7b746c70a9b83", "exit": 0, "failed": 0, "passed": 958, "round": 2876, "tests": "run_selftests.py -k pet_ui desktop_compact usage_indicator sanhu pet_settings pet_popup pet_offer pet_cloud ui_token window_resize batch9_pet skills idea_inline"} -->

- 轮次类型：功能轮（§3.1，UI 布局调整，无阶段行为变化，不先改 REQ/DES）。
- 用户要求：页面右上角文字「已暂停／半自动／全自动」移动到三虎图像正下方，底部和右侧三个猫爪切换按钮底部对齐；三个猫爪按钮间距保持一致。
- 轮次号说明：开工时按 `round_claim.py next` 领号；主干合并轮已先后占用 R2870–R2875，本轮实际使用 **R2876**（`codex/wip-R2876`；前两次领号 R2873/R2876 间隙被主干合并轮占用）。

## 改动

- `程序/ui_tokens.py`：`PET_LAYOUT["paw_arc"]` 2→0（三只爪取消弧形下坠、等距直排）；新增 `caption_gap`（小字与头像底边间距，取 `SPACING["sm"]`）。
- `程序/pet_ui_support.py`：重排簇几何——`PATCH_X` 右移让出猫爪列右缘位、`PAW_COL_X` 收到窗口右缘、`HEAD_PAD` 按小字左沿让开整簇、`CAPTION_Y` 落到头像底边之下、`PAW_COL_Y` 改为按 token 行高的占位估值、新增 `PAW_COL_BOTTOM_LOCAL`（列内末爪视觉底边相对列顶的偏移）。
- `程序/pet_ui_view.py`：小字 `place` 改 `x=PATCH_X, y=CAPTION_Y`（右沿与头像右沿对齐）；新增 `_paw_col_top()`（按小字 `winfo_reqheight` 实测高反推列顶）、`_align_paws()`（小字一行↔两行换行时整列平移，命中区同步）、`_sync_patch_room()`（标题行保留高度随小字实高收缩并触发 `desktop.align_header()`）；`<Configure>` 绑定驱动重排。
- `程序/pet_ui.py`：`__init__` 新增 `_paw_col_y`／`patch_room` 实例状态；过时注释同步。
- `程序/desktop_layout.py`：`align_header()` 标题行最小高度优先取 `pet.patch_room`（运行时实高），回退静态 `pet_ui.PATCH_ROOM`。
- `程序/pet_ui_voice.py`：caption 文档注释同步「图像下方」口径。
- `程序/tests/test_pet_ui.py`：几何／小字／猫爪断言按新契约更新（契约有意变更，行为断言保留：命中区 36×36、点击映射、悬停／焦点、键盘行为均未动）。

## 实测几何（隐藏桌面探针）

- 单行小字（高 21px）：小字底边 77px ＝ 猫爪列视觉底边 77px；`patch_room` 动态收缩至 87。
- 两行小字「待确认 N」（高 38px）：猫爪列下移，小字底边 94px ＝ 列底边 94px。
- 三只爪等距：`PAW_ARC=0`，相邻爪心距恒为 `PAW_STEP=16`；命中区仍 36×36 且随列平移。

## 三问

- 本轮属于 §3.1 功能轮。
- 测试跑了：`smoke_test.py` 默认冒烟 8/8 绿；`test_pet_ui.py` 607/607、`test_desktop_compact_layout.py` 5/5、用量指示器／窗口缩放／宠物设置等受影响批次 66/66 与 7/7 全绿；`smoke_test.py --affected`（6 个改动模块）定向 60 个测试文件进行中（结果见下「验证」）；`skill_package_pins.py --check` 3 包 0 问题。
- 欠账少了：无新增；`project_status.md` 抬头滞后为分支固有欠账（仅 master 可提交），由合并轮闭环，本轮不动。

## 环境插曲（与本次改动无关，已闭环）

本工作树创建时未带 gitlink 子模块内容（树内 4 个 mode-160000 条目、无 `.gitmodules` 映射，属嵌入式仓库）。先后暴露两处环境性红，均与 UI 改动无关：

1. `test_skills`：注册表期望 73 实得 71——`01 剧本准备SKILL/剧本锻造`、`编剧技能集` 两个 gitlink 空目录。已按父树钉住提交（6c3d7399／357d1348）从主工作区补入内容（父仓库不跟踪其内容，`git status` 不受影响），注册表恢复 73。
2. `test_idea_inline_brief`：10 条断言红——`00全流程SKILL/AIGC创作全流程`（1a43ae5a）整目录未检出，`freeze_skills` 内联引用 `sd-decision-engine/SKILL.md` 缺失。补齐后 30/30 全绿。
3. 顺带补齐第 4 个 gitlink `reference/HoLLMwood`（3ef9f995）。

`skill_package_pins.py --check` 复核 3 个已检出外部技能包与登记哈希一致、0 问题。

## 验证

- `python smoke_test.py`：8/8 通过。
- `run_selftests.py` 定向 `test_pet_ui`：607/607 通过（改后复跑 462s，含 `_sync_patch_room` 改走 `errors.append` 后的最终代码）。
- 定向 `test_desktop_compact_layout`：5/5；用量指示器等批次：66/66、7/7。
- `smoke_test.py --affected`（6 个改动模块自动展开 60 个测试文件，721s）：除 `test_idea_inline_brief` 外全绿；该文件 10 条断言红均因 `00全流程SKILL/AIGC创作全流程` gitlink 未检出（`freeze_skills` 引用缺失），补齐后复跑 30/30 全绿——环境性失败，与本次 UI 改动无关。
- `run_selftests.py -k test_skills`：12 分片全绿（注册表 73，gitlink 补齐后）。
- `scripts/skill_package_pins.py --check`：3 个外部技能包 0 问题。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
