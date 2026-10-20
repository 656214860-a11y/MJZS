# R1768：修复轮——「套用总控建议」窗口不超屏、确认按钮常驻、制作锁灰态提示（C7）

工作目录：`D:\漫剧制作助手\.wt\lane_c7\程序`（车道开工时工作树干净，无前序执行方改动）
解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`

## 三问

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。先复现并确认根因，再最小修复；未改分层、契约、权威源与用户数据。
2. **测试跑了吗、三个基线过了吗？**
   - 跑了任务书列出的全部窄命令，均通过：
     `tests.test_skills -k workflow` 7/7、`tests.test_skill_panel_production_locks` 3/3、
     `tests.test_skill_panel_dropdown_layout` 13/13、`tests.test_skill_panel_layout_fit` 3/3、
     `tests.test_skill_panel_imported` 2/2、`tests.architecture.test_requirement_traceability` 5/5、
     `tests.architecture.test_layers` 5/5；`smoke_test.py` 通过 8 项／失败 0 项。
   - 默认冒烟：**8/8**。架构门禁：只按任务书跑了 `test_requirement_traceability` 与 `test_layers`（5+5 全绿），
     **未跑**全量架构门禁 `--architecture`。全量回归：**未运行**（任务书明确禁止 `run_selftests.py`、全量、`--affected`），
     因此不冒用历史全绿凭据。
3. **`project_status.md` 的欠账少了吗？**
   执行方不改状态页，本轮未增删状态页欠账；本轮自身无新增欠账。

## 根因（逐条确认／推翻任务书推断）

1. **确认**：`Panel.workflow_apply_dialog` 原先把说明、整张 13 阶段表格、按钮依次 `pack` 进 `body`，
   只调用 `geometry('+x+y')` 设位置、不设尺寸，也没有滚动区。任务书数据量（13 阶段×6 条 SKILL）下，
   真 Tk 修前实测对话框高 **1901px**（可用高 720／620），「确认套用」按钮底边在 **1850px**、落到 800px 屏幕外。
   另实测：只给位置不给尺寸时窗口初始为 1×1（withdraw 根窗口 + `transient` 对话框不映射时更明显）。
2. **确认**：`refresh_workflow()` 用 `enabled=bool(name)` 置灰全部制作锁；`choose_workflow()` 选总控只弹窗，
   只有 `apply_selected()` 里的 `put_workflow` 才写入总控名；`save_writing_production_locks` 在总控名为空时
   抛 `ValueError('请先在阶段配置选择总控')`。修前 E2E 复现：未确认前锁为 disabled，确认后解锁并写回画幅。
3. **确认**：总控为空时 `lock_notice` 仍显示「旧项目兼容：赛道、素材来源未选，仅提示不阻断。」，
   没有任何“先选总控并确认”的说明。
4. **补充确认（同属 G3 的“显示≠真值”）**：
   - 取消按钮会 `refresh_workflow`，但标题栏 ✕（`WM_DELETE_WINDOW`）与 Esc 直接 `destroy()`，下拉框停在用户刚选的名字；
   - 「浏览本地…」路径也只把下拉框改成 `NO_MASTER`，不写项目、不还原已保存值。
   上述两处均在允许文件内一并修复，未改对话框业务语义。

## 改动（文件:函数／条目）

- `skill_panel.py`
  - 新增模块常量 `DIALOG_SCREEN_MARGIN_X/TOP/BOTTOM`、`NO_MASTER_LOCK_HINT`，与 `dialog_working_area(widget)`
    （屏幕尺寸扣标题栏 32、任务栏 48，测试可用 `winfo_screenheight` 包装固定尺寸）。
  - `Panel.refresh_workflow`：总控为空时把 `lock_notice` 置为提示文案；有总控时恢复原有“旧项目兼容”提示；
    同步失败信息另起一行，不覆盖提示。
  - `Panel.workflow_apply_dialog`：动作区先 `pack(side='bottom')` 固定底部；阶段表放进 `tk.Canvas`＋
    `ttk.Scrollbar`（滚轮绑到表内全部控件）；按表体自然尺寸量窗口后夹到屏幕可用区并夹在屏内定位；
    `BaseDialog(on_close=self.refresh_workflow)`，取消／`WM_DELETE_WINDOW`／Esc 走同一关闭路径。
  - `Panel.choose_workflow`：「浏览本地…」不再伪造下拉显示，立即 `refresh_workflow()` 还原已保存总控。
  - 未改默认勾选规则、`apply_selected()` 写入逻辑、`stage_config` 接口、`save_writing_production_locks`。
- `docs/stages/S01_剧本准备.md`：新增 `REQ-S01-57`（下一个未用编号，已 grep 确认 57 未被占用）、
  `DES-S01-57`，并在测试锚定表补一行。
- `tests/test_skills.py`：新增 `_thirteen_stage_preset()` 与 2 个用例（追加，未改既有用例）。
- `tests/test_skill_panel_production_locks.py`：新增 `WorkflowLockEnablementTests` 2 个用例（追加）。

未改 `production_lock_fields.py`（本轮不需要）。未改 `project_status.md`、`AGENTS.md`；未执行任何 git 写命令。

## V1–V7 实测命令与计数

| 验收 | 命令 | 结果 |
| --- | --- | --- |
| V1 | `python -B -m unittest tests.test_skills.PanelTests.test_workflow_apply_dialog_fits_screen_and_keeps_actions_visible` | 1 test / 3 subtests（800 普通、800 `switching=True`、700 小屏）**OK**。断言：高度 ≤ 720/720/620；两按钮 `winfo_viewable`、底边 ≤ 对话框且不落屏外；纵向滚动条 `winfo_viewable`；表宽未被裁切；滚轮事件改变 `canvas.yview()`；窗口 x/y/底边在屏内 |
| V2 | `python -B -m unittest tests.test_skill_panel_production_locks.WorkflowLockEnablementTests.test_lock_notice_tells_user_to_confirm_master` | **OK**。空总控时提示含「确认套用」；下拉框显示已挑总控但未确认时锁仍灰、提示仍在；生效后提示不含「确认套用」，恢复为空或「旧项目兼容」 |
| V3 | `python -B -m unittest tests.test_skills.PanelTests.test_workflow_dialog_close_paths_restore_saved_master` | **OK**。有／无已保存总控 × 取消／`WM_DELETE_WINDOW`／Esc 共 6 条路径，关闭后 `workflow_choice` 均等于已保存值（无总控为 `NO_MASTER`） |
| V4 | `python -B -m unittest tests.test_skill_panel_production_locks.WorkflowLockEnablementTests.test_confirm_master_enables_locks_and_saves_change` | **OK**。选总控→确认套用：确认按钮可见且不落屏外；未确认前锁 disabled；确认后解锁；画幅改 `9:16` 后 `stage_config.workflow_lock()` 读回 `9:16` |
| V5 | 见下「先红证据」「变异验证」 | 先红 4 tests / 9 failures；变异后 V1 3 subtests 变红，还原 sha256 一致 |
| V6 | `python -B -m unittest tests.test_skills -k workflow` | **7/7 OK**（5 个既有对话框用例 + 2 个新用例）；按钮文本仍为「确认套用」「取消」，勾选框行为未变 |
| V7 | `python -B -m unittest tests.architecture.test_requirement_traceability`；`python -B tests/architecture/test_requirement_traceability.py --find REQ-S01-57` | 5/5 **OK**；`--find` 返回 4 个锚点：`test_workflow_apply_dialog_fits_screen_and_keeps_actions_visible`、`test_workflow_dialog_close_paths_restore_saved_master`、`test_lock_notice_tells_user_to_confirm_master`、`test_confirm_master_enables_locks_and_saves_change` |

其余窄命令：`test_skill_panel_production_locks` 3/3、`test_skill_panel_dropdown_layout` 13/13、
`test_skill_panel_layout_fit` 3/3、`test_skill_panel_imported` 2/2、`test_layers` 5/5、`smoke_test.py` 8/8，全部 OK。
（Tk 启动时 stderr 的 `pkgIndex.tcl ... unknown encoding "cp1252"` 是本机 Tcl 环境噪声，各进程退出码 0。）

## 先红证据（改前）

`skill_panel.py` 临时换回 `HEAD` 版本（sha256 `0f5a3692…`），用最终测试文件跑 4 个新用例，再按字节还原：

```
FAIL test_workflow_apply_dialog_fits_screen_and_keeps_actions_visible (800,False)
AssertionError: 1901 not less than or equal to 720 : 对话框高度超过屏幕可用高度
FAIL ... (800,True)  1901 not less than or equal to 720
FAIL ... (700,False) 1901 not less than or equal to 620
FAIL test_workflow_dialog_close_paths_restore_saved_master (wm, saved)   '不使用总控' != 'AIGC全流程'
FAIL test_workflow_dialog_close_paths_restore_saved_master (escape, saved) '不使用总控' != 'AIGC全流程'
FAIL ... (wm, none)      'AIGC全流程' != '不使用总控'
FAIL ... (escape, none)  'AIGC全流程' != '不使用总控'
FAIL test_confirm_master_enables_locks_and_saves_change
AssertionError: 1850 not less than or equal to 800 : 确认套用按钮落到屏幕外，用户点不到
FAIL test_lock_notice_tells_user_to_confirm_master
AssertionError: '确认套用' not found in '旧项目兼容：赛道、素材来源未选，仅提示不阻断。'
Ran 4 tests, FAILED (failures=9)
```

还原校验：`restored_sha_match True`，最终 `skill_panel.py` sha256
`6b093b8f90b2e68459019a87020e2ae686dd0fe26dd75d2f2f767b0622be89da`。

说明：取消按钮路径改前即会 `refresh_workflow`，所以 V3 的 cancel 子路径改前是绿的；✕／Esc 两条红。
V4 的“未确认灰／确认后不灰”改前本身成立，红的是“确认按钮不可见／落屏外、用户点不到”这一步（端到端可达性）。

## 变异验证（V5）

临时把高度上限 `min(chrome_h + table.winfo_reqheight(), available_h)` 改成不设上限，
跑 V1：

```
FAIL ... (800,False) AssertionError: 1901 not less than or equal to 720
FAIL ... (800,True)  AssertionError: 1901 not less than or equal to 720
FAIL ... (700,False) AssertionError: 1901 not less than or equal to 620
Ran 1 test, FAILED (failures=3)
```

还原后 `restored_sha_match True`，与上列 sha256 一致。

## 断言未动声明

**断言未动**：既有测试文件中的既有用例、断言、fixture 均未修改、未弱化、未删除、未跳过；
两个测试文件只在末尾追加新用例（`test_skills.py` 另加一个仅本轮使用的 `_thirteen_stage_preset` 静态方法）。
本轮功能未改变既有契约，只有新增 REQ-S01-57 的测试锚定。

## 需裁决事项

1. **测试夹具的根窗口映射方式**：任务书建议“withdraw 的根窗口”，但 Windows 下 `transient` 子窗在 withdraw
   根窗口上不会被映射，`winfo_viewable` 恒为 0、`geometry` 也停在 1×1，无法验证 G1 的“按钮可见”。
   新用例改为在测量前 `deiconify()` 根窗口（与现有 `test_skill_panel_dropdown_layout._open_stage_config_window`
   同法），屏幕尺寸仍用 `winfo_screenheight/screenwidth` 包装固定，不依赖本机分辨率。若审查要求严格 withdraw，
   “按钮 `winfo_viewable`”这条断言需要改成别的口径，请裁决。
2. **屏幕余量口径**：本轮按任务书示例固定为“上 32、下 48”，未读取 Windows 真实工作区
   （`ui_theme.work_area()` 可拿任务栏高度，但不可注入固定分辨率）。若要求贴合真实任务栏高度，可后续替换
   `dialog_working_area()` 实现；G1 与测试的 720／620 口径也随之调整。
3. **「浏览本地…」显示还原**：属于 G3“显示即真值”的同类问题，已在本轮允许文件内一并修复
   （`choose_workflow` 调用 `refresh_workflow()`）。未改其提示文案与“只认总控.json”语义。

## 自检结论

任务书允许范围内改动（`skill_panel.py`、`docs/stages/S01_剧本准备.md`、两个测试文件），
窄命令与冒烟全绿，先红与变异证据齐全，新建 REQ/DES 编号与锚点通过门禁。
`project_status.md`、`AGENTS.md`、用户数据、`private/` 未动，未领号、未提交。

## 独立验收（advisor，lane_c7 真实环境直接运行）

- 范围：skill_panel.py、docs/stages/S01_剧本准备.md、tests/test_skills.py、tests/test_skill_panel_production_locks.py（4 文件 +310/-9）。
- diff 审查：常量取 `SPACING`／`COLORS` token，无魔法数字与内联 hex；对话框改为动作区 `pack(side='bottom')` 先占底部＋Canvas 滚动表体＋`dialog_working_area()` 屏幕内夹取；`on_close` 统一还原，`choose_workflow` 浏览本地立即还原。
- 测试（lane_c7 前台窄命令）：smoke_test.py 8/8；test_skills -k workflow 7/7；test_skill_panel_production_locks＋dropdown_layout＋layout_fit＋imported 21/21；test_requirement_traceability＋test_layers 10/10。全 OK。
- 全量架构与完整安全全量：未跑（C7 任务书禁止；架构门禁已跑 requirement_traceability＋layers）。
- 断言未动：执行方只追加 4 条用例，未改既有断言。
