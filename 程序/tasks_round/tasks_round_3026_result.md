# R3026 合并轮结果
<!-- round-evidence: {"commit_base": "87dec75f", "credential_hits": 0, "evidence_sha256": "20414e37b89b1d23", "exit": 0, "failed": 0, "passed": 0, "round": 3026, "tests": "docs-only"} -->

- 轮次类型：合并轮。
- 合入：`dsh-52a9b6ff-8ed3` 到 master。
- 说明：R2993 悬停卡片全量盘点（只读诊断）＋R2997 Tooltip 悬停状态机升级与技能卡片 grab 豁免＋R3012 缩略图点击抑制与宠物单击待决取消。
- 集成口径：R2997 原按 R2971 之前的旧结构迁移了技能卡片；合入时 master 已有 R2971「技能菜单面板化」（`desktop_shared_menus`，✦/＋ 下拉与说明卡不再弹 BaseDialog 菜单，说明卡本身仍是 BaseDialog Toplevel 并带 200ms 收起窗口）。据此收敛：**保留 master 的 R2971 卡片形态**，只应用 R2997 的 grab 豁免修复——说明卡改走 `make_passive_popup`（原只标 `_positioned_once`，防得住居中、防不住隐藏初始化挂的 `<Map>`→grab；grab 一抢技能行 Leave/Enter 循环、卡片反复弹出，即用户报告的 bug）。Tooltip 状态机升级（排程先取消旧计时器、pin、closeDelay、reshow、点击抑制、单例可见）作为两版共同的组件底座合入。
- 冲突：`desktop_shared_input.py` 一处（导入与卡片构造），按上述口径以 master 为基础解决；rebase 后悬停相关 24 条测试全绿（test_hover_card_states／test_cell_zoom_suppress／test_ui_compact_widgets／test_script_file_hover_card／test_pet_ui.ClickCancelTests）。
- 断言未动。未跑全量（欠账与后台补跑按 §5 口径，post-commit 钩子会安排）。
