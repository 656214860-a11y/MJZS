# R3012 修复轮结果
<!-- round-evidence: {"commit_base": "93ad84e2", "credential_hits": 0, "evidence_sha256": "1bc904bca07066e3", "exit": 0, "failed": 0, "passed": 653, "round": 3012, "tests": "run_selftests.py -k cell_zoom_suppress cell_menu pet_ui"} -->

## 三问（§7.2）

1. **轮次类型**：修复轮（§3.2）。按 R2993 只读诊断 J 整改路线 **R2** 执行：闭环剩余互斥与零散项。
2. **测试**：跑且全绿（本轮范围）。默认冒烟 **8/8**；新增测试 5 条全绿（`test_cell_zoom_suppress` 1 条＋`test_pet_ui.ClickCancelTests` 4 条）；定向回归 `run_selftests.py --serial -k cell_zoom_suppress cell_menu pet_ui writing_cancellation cancellation_status` 共 675 条：**本轮相关模块（cell_zoom_suppress／cell_menu／pet_ui）全绿**；6 条红全部落在无关模块（`test_writing_cancellation`／`test_cancellation_status`，关键词 can**cell**ation 误匹配），根因＝工作树缺 `程序\skills\00全流程SKILL\AIGC创作全流程\sd-decision-engine\SKILL.md`（与 R1988 同源的工作树环境限制，FileNotFoundError），与本轮改动无关。`smoke_test.py --affected cell_hover pet_ui pet_ui_view` 消费方门禁 18 文件共 1230 条：**除 `test_skills` 2 红外全绿**，该 2 红＝注册表计数 71≠73（工作树缺 2 个捆绑 SKILL 文件，单跑复现同一断言，环境限制非本轮改动）。期间先红后修 1 处：既有 `test_pet_ui` 点击用例以 `_Event(widget=…)` 替身调用 `pet_click`，无 `x_root` 属性——`pet_click` 取坐标改为防御式（替身无坐标则不记录起点，不取消）。三个基线：冒烟 8/8 通过；架构门禁未跑（本轮不改分层、非跨层/结构治理）；全量未跑、欠账口径不变。
3. **欠账**：未新增。R2993 漏洞清单本轮闭环 #4/#11/#15；#5/#12/#16/#20 由 R1 组件级修复自动闭环（消费点无需改动，见下）；#18/#19 经复查既有机制已覆盖（不改代码，理由见下）；#13/#14/#21 保留记录（见边界）。

## 改动清单

- `cell_hover.py`：`CellImages` 新增 `_zoom_suppress`——点击缩略图（选择行／双击打开）立即收起放大图并抑制重弹，直到指针离开该格再进入（`zoom_leave` 解除）。绑定登记在 forward/view 之前，不拦原行为（#4/#11）。
- `pet_ui.py`／`pet_ui_view.py`：宠物单击待决（CLICK_MS=220）随指针移动取消——`pet_click` 记录点击起点，窗口 `<Motion>` 超出 `CLICK_MOVE_CANCEL_PX=8`（双击容差）或 `<Leave>` 离开宠物窗即 `cancel_pending`（#15，「点击后鼠标一动云朵照样弹出」不再发生）。
- `tests\test_cell_zoom_suppress.py`（新增 1 条）、`tests\test_pet_ui.py`（新增 `ClickCancelTests` 4 条）。

## 由 R1 组件级修复自动闭环（本轮复核，消费点零改动）

- **#5 模型选择器触发钮并存**：R1 的 `_press` 抑制（点击后 FocusIn 不再排程）对 `stage_model_picker.py` 的 Tooltip 自动生效。
- **#12 TreeRowTooltip 双通道**：R1 状态机「排程先取消旧计时器＋点击抑制」消除 Motion/FocusIn 打架。
- **#16 show 不校验指针**：根因「Leave 被吞」来自 grab 接管，R1 豁免后不复现。
- **#20 附件 chip 三实例**：R1 的单例可见（`_VISIBLE_TIP`）保证同帧只显示一张；三实例是「chip/图标/标题三块命中区」的有意分布，保留。
- **#18 孤儿 Label**：`refresh→zoom_hide`（`cell_hover.py:945-946`）与 destroy 收尾（994-1016）已在位，复查确认无新增路径。
- **#19 Flyout 悬挂窗口期**：`_sidebar_popup_destroyed` 兜底解绑＋`_sidebar_popup_outside` 的 `winfo_exists` 复核已在位（`desktop_page_nav.py:395-422`），复查确认无改动必要。

## 范围与边界

- #13（Flyout 贴底翻上压指针）、#14（悬停底色覆盖选中态）为交互打磨项，未纳入本轮；#21 部分（tip 模式高频建窗）受既有测试契约（destroy 语义）约束保留。
- 状态页轮次头同步留待合入 master 时随合并提交完成（与 R2993/R2997 同口径）。
