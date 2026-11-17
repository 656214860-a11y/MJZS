# R3033 修复轮结果
<!-- round-evidence: {"commit_base": "4c033784", "credential_hits": 0, "evidence_sha256": "83dcd7441f6254a1", "exit": 0, "failed": 0, "passed": 652, "round": 3033, "tests": "run_selftests.py -k cell_hover cell_menu pet_ui_view pet_ui ui_tooltip"} -->

## 三问（§7.2）

1. **轮次类型**：修复轮（§3.2）。目标＝master 出口门禁红：`cell_hover.py` 模块棘轮（1028 行 > 登记上限 1016，R3012 悬停缩略图逻辑累积所致）。本轮在 `codex/wip-R3033` 上完成拆分（领轮时工作树有未提交改动，round_claim 自动带到新分支；原任务点名的 `codex/wip-R2980` 内容已由 R3013 合入 master，本轮是其后的独立阻断修复）。合入前复跑发现 master 另有 3 条同源历史欠账红（R2997/R3012 未跑架构门禁遗留），一并按实测修复，未抬任何登记值。
2. **测试**：跑且本轮范围全绿。默认冒烟 **8/8**；`smoke_test.py --affected cell_hover cell_menu pet_ui_view pet_ui ui_tooltip` 定向 18 文件共 **1230 条**：除 `test_skills` 2 红（注册表计数 71≠73，工作树缺 2 个 gitlink 捆绑 SKILL——`剧本锻造`／`编剧技能集` 为空目录，R3012 已记录同源环境限制）外全绿；`smoke_test.py --architecture` 471 条：**改前 4 条内容红全部清零**，余 2 条环境项（`test_performance_history` 缺未跟踪的 `维护记录/基准历史.json`、`test_skill_reference_injection` 缺 gitlink 内 `screenplay-gate-engine.md`，均只在主工作区存在，合并出口 CI 在主工作区复跑）。三个基线：冒烟 8/8 通过；架构门禁当轮 471 条、失败集合＝上述 2 条环境项（改前 6 条失败/错误 → 改后 2 条，且均为环境）；全量未跑、欠账口径不变。
3. **欠账**：未新增；反而闭环 4 条历史欠账——`CellImages` 610>600、`PetViewMixin` 746>732、`Pet` 多写者属性 55>54、`ui_tooltip.__init__` 9 参数>7，全部用真实拆分/收拢修复，棘轮登记表零改动（`CLASS_CAPS`/`PARAM_CAPS`/`SHARED_STATE_CAPS` 均未动）。

## 改动清单

- `cell_menu.py`（新增，L4）：`cell_hover.py` 右键菜单四件套搬出——`ROW_MENU_VIEW/DELETE`、`wants_column`、`call_delete`、`popup_row_menu`、`bind_row_menu`；`cell_hover.py` 按原名重导出，7 个消费方与全部既有测试零改动。
- `cell_hover.py`：1028 → 962 行（<1000，摘除 `test_module_size_ratchet` 登记上限）；`CellImages` 的悬停放大块（`zoom_hide`…`zoom_leave` 约 246 行）拆为同文件 `CellImagesZoomMixin`，`CellImages` 610 → 362 行、Mixin 250 行，均 <600。
- `pet_ui_view.py`：R3012 单击待决取消块拆为同文件 `PetClickCancelMixin`（`_note_click_xy`/`_pet_move`/`_pet_away`/`_cancel_pending_click`＋`_click_xy` 类属性默认值），`PetViewMixin` 746 → 727 行；`pet_click` 改为 `self._note_click_xy(event)` 委托，行为不变。
- `pet_ui.py`：删 `Pet.__init__` 的 `self._click_xy = None`（默认值由 Mixin 类属性承担）→ `_click_xy` 写入只剩单一类，`Pet` 多写者属性 55 → 54。
- `ui/ui_tooltip.py`：`Tooltip.__init__` 9 个具名参数 → `(widget, text, **opts)`（参数棘轮 9 → 3）；`_TOOLTIP_OPTION_KEYS` 白名单＋未知关键字照旧 `TypeError`，全部既有调用（位置 2 参＋测试关键字）零改动。
- 门禁登记同步：`tests/architecture/_layers.py` L4 表加 `cell_menu`；`architecture.md` §3 L4 表加 `cell_menu`；`test_module_size_ratchet.py` 摘除 `cell_hover.py` 上限；`维护记录/覆盖率基线.json` 重测（549 模块、71 覆盖，新增 `cell_menu.py` 条目）；`runbook.md` §11 口径同步 549/71/478。

## 范围与边界

- 行为保持：右键菜单「查看/删除」契约、缩略图单击/双击/点击抑制/放大右键回指、宠物单击待决取消、Tooltip 状态机参数语义均未变；相关定向测试（`test_cell_menu` 40 条、`test_cell_zoom_suppress`、`test_pet_ui` 全部、`test_hover_card_states`、`test_popup_no_interrupt`）全绿。
- 环境限制（非本轮改动，与 R3012/R1988 同源）：本工作树 `程序/skills/` 下 `剧本锻造`、`编剧技能集` 两个 gitlink 为空目录，`维护记录/基准历史.json` 为未跟踪文件仅存于主工作区——对应 4 条测试红在主工作区合并出口 CI 复跑，不受本分支影响。
- 状态页轮次头同步留待合入 master 时随合并提交完成（与 R3012 同口径）。
