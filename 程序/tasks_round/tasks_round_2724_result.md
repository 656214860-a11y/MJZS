# R2724 结果：剧本结构页编辑改自动保存＋右键菜单／撤销快捷键（反转 R1862 手动保存契约）
<!-- round-evidence: {"commit_base": "2ded4464", "credential_hits": 0, "evidence_sha256": "627ee028e8b1ebd0", "exit": 0, "failed": 0, "passed": 135, "round": 2724, "tests": "run_selftests.py -k script_structure script_autosave script_context_menu script_undo_shortcuts ui_edges_pages usage_indicator_ui usage_snapshot"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）。任务源：`tasks_round/剧本编辑自动保存重构任务书.md`（用户指定
   「实现任务书目标功能, 测试通过停止」）。文档先行：先改 S02 REQ-S02-32/35、
   DES-S02-35 与 S01 DES-S01-58，再改实现与测试（§2.7）。
   轮次号说明：会话开工时领 R2686；期间中央计数器被并行车道连续推进且本工作树
   被另一会话（费用统计 CSV 收口）复用并改领 R2722→R2774，本车道重新领取后
   定号 **R2724**（`round_claim.py next` 发放，提交信息与结果文件同号）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过（第 10 轮）。
   - 定向 `run_selftests.py -k test_script test_ui_edges_pages
     test_ui_batch5_stage_panel_and_script_page test_ui_reading_density
     test_stage_wiring`：**29 个文件 / 287 条用例全绿**（分模块拆分后另复跑
     4 个剧本编辑文件 29/29、8 个文件 43 条中 autosave 修补后 11/11 复绿）。
   - `smoke_test.py --architecture`：**466/466 全绿**。首跑曾 2 红，均非本轮
     引入并已消除：`test_round_number_continuous`（project_status.md 2697 vs
     结果 2774 的跨树合入欠账，由并行车道 R2801 状态页同步为 2775 消除）；
     `test_silent_exception_ratchet`（`ui_usage_detail.py:142` 未登记
     `except Exception: pass`，系并行 R2774 车道刚提交引入）经用户授权顺手
     修复为 `app_logging.swallowed()` 留痕（含 `import app_logging`，
     `ui_usage_detail.py` 一并纳入本轮提交并在此披露）；复跑棘轮 4/4、
     `test_round_baselines` 5/5、全量 466/466 绿；
     `test_usage_indicator_ui`/`test_usage_snapshot` 17/17 绿。
   - 覆盖率基线已按 `scripts/coverage_report.py` 同目标重测刷新：
     生产运行时模块 372→**373**（新增 `desktop_script_edit_session.py`）、
     61 个有行覆盖、9 组定向用例全绿；runbook §11 数字已同步。
   - 模块行数棘轮：`desktop_script_pages.py` 拆分后 708 行（原 1009 超限），
     新模块 324 行，均在 1000 上限内，未抬任何登记上限。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账；合入 master 前的全量由主树安排）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；消除一笔契约冲突：R1862 手动保存与「防丢稿」目标相悖，本轮按任务书
   恢复防抖自动保存，编辑／后退／复原／保存统一收进右键菜单，落盘失败留在编辑态
   不再静默丢稿。`script_structure_edit_controller` 瘦身为只持初始原文／落盘基线／
   变化判定（无 Tk、无快照栈）。

## 变更

- **`desktop_script_edit_session.py`（L4，新）**：从 `desktop_script_pages` 拆出
  `_ScriptEditSession`＋`_install_script_edit_controls`＋`_reset_preview_text`＋
  `_record_natural_edit`（行数棘轮要求）。会话持有编辑态、防抖 `after` 定时器
  （`SCRIPT_EDIT_SAVE_DEBOUNCE_MS`＝600ms，预览 `<Destroy>` 时 `after_cancel` 撤销、
  `autosave` 对销毁窗口按 `tk.TclError` 丢弃）、右键 `ContextMenu`（经
  `page.script_page_services.context_menu`，不直建 `tk.Menu`）与快捷键
  （经 `page.shortcuts.bind`→`ShortcutRegistry`，scope＝`剧本结构页·自然/结构剧本`）。
  可见按钮只留「编辑」（编辑中「退出」；结构框另有「删除」，编辑中禁用）。
- **`desktop_script_pages.py`（L4）**：`_ContentBox.select_document` 编辑态先
  `exit_edit`（内含 flush 落盘；失败则 `selection_set` 回退并提示、不切换）再加载
  新文档；`exit_edit` 不再询问「放弃修改」（已自动保存）；`set_preview`／`build`
  改从新模块导入 `_reset_preview_text`／`_install_script_edit_controls`。
- **`script_structure_edit_controller.py`（L2）**：瘦身——`begin_edit(initial)`／
  `save(text)`（与上次落盘相同不写盘返回 False）／`initial`／`saved`／`dirty`；
  撤销栈交还 Tk 原生 `edit_undo`/`edit_redo`，不再自持内容快照。
- **`ui_tokens.py`（L1）**：新增 `SCRIPT_EDIT_SAVE_DEBOUNCE_MS = 600`。
- **落盘路由不变**：natural 走 `script_contract.save_natural_script`＋落盘后
  `edit_habits.record_edit`（REQ-S01-58，自动保存同样记修改习惯）；structured 走
  `agent.core.save_text`；均直接读 `preview.get('1.0','end-1c')` 当前内容，
  空内容报错且文件不动。
- **测试**：`test_script_structure_edit.py` 按新契约重写（编辑/退出、空框禁用、
  只读拒绝、结构删除门禁）；新增 `test_script_autosave.py`（11 条：防抖落盘、
  未变化不写盘、退出/切换 flush、natural 记习惯、structured 保空白、空内容拒绝、
  只读不保存、真 Desktop 切文档）、`test_script_context_menu.py`（6 条：四项顺序、
  编辑态可用/非编辑态禁用、复原确认、撤销步进、立即保存幂等）、
  `test_script_undo_shortcuts.py`（3 条：registry 登记＋控件绑定、处理入口步进、
  非编辑态空操作）。`test_ui_edges_pages.py`、`test_script_structure_expand_edit.py`、
  `test_script_structure_natural_edit.py` 同步改断言新会话入口（`*_edit_session`
  的 `undo_step`/`save_now`），未变行为断言保持原样。
- **分层登记**：`tests/architecture/_layers.py` L4 登记新模块；`_scan.py`
  `DESKTOP_PARTS` 纳入（Desktop 行为扫描覆盖会话方法）；
  `test_migrated_ui_boundaries.py` `GUARDED_FILES` 增列（`preview.after` 已按
  TclError 守卫）。`PROJECT_MAP.md`、`runbook.md` §11、S01/S02 阶段文档同步。
- **`维护记录/覆盖率基线.json`**：按工具同 9 组目标重测刷新（模块数 372→373）。

## 已知边界与如实记录

- 隐藏桌面上 `event_generate` 合成字母键不投递（实测），快捷键测试改为断言
  registry 记录＋控件绑定串＋直接调用 `_shortcut_undo`/`_shortcut_redo` 处理入口；
  `<Button-3>` 需控件已有内容并完成首次 `update` 才稳定投递，测试夹具已按真实
  `set_preview` 口径预填原文并置只读。
- 架构门禁首跑的 2 红均非本轮引入：轮次连续性系跨树合入欠账（已由并行车道
  R2801 状态页同步消除）；`ui_usage_detail.py` 静默 except 系 R2774 车道引入，
  经用户授权本轮顺手修复（见上）。
- 本工作树曾被多会话并发使用：并行会话领 R2774（费用统计 CSV 收口）并先行
  提交 `cfd1e610`，R2801 再同步状态页；其余功能文件不在本轮提交内，仅
  `ui_usage_detail.py` 因静默异常棘轮红经用户授权纳入（改动仅
  `import app_logging`＋`pass`→`app_logging.swallowed()`，行为不变）。
  本轮暂存清单已逐一核对。
- 提交状态：见本文件末尾 commit hash（dev.py commit 回填）。
