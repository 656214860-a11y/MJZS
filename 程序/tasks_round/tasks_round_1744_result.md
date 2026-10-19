# R1744：结构治理轮——收口 9 处 UI 统一入口绕过（UIFIX）

执行：opencode（独立车道 `D:\漫剧制作助手\.wt\lane_uifix\程序`，detached HEAD `aa2875e6`）。
日期：2026-10-19。
类型：§3.1 功能轮（任务书派发）。未执行任何 git 写命令，未领号、未提交，未改 `project_status.md`、`AGENTS.md`。

## 0. 三个问题

1. **本轮属于 §3 哪种类型？** §3.1 功能轮：按 `AUDIT_result.md` B.1/B.3/B.5 收口 11 处 UI 绕过。
2. **测试跑了吗、三个基线过了吗？**
   - 架构门禁：`smoke_test.py --architecture` → **374 条，146.634 秒，OK，0 红，EXIT=0**。
   - 定向自检：`run_selftests.py -k asset_detail media_pages pet_models asset_batch ui_widgets` → **93 条，42.2 秒，0 个文件有红，EXIT=0**。
   - 默认冒烟 `smoke_test.py`：未运行（任务书未要求；本轮只改 UI 调用点）。
   - 全量安全回归 `run_selftests.py --all --safe`：未运行（任务书未要求）。
   - `smoke_test.py --affected ...`：两次均被其内置 900 秒上限终止（EXIT=1），详见 §3。
3. **`project_status.md` 的欠账少了吗？** 未改该文件（执行方不改状态页）；本轮不新增也不闭环状态页欠账。

## 1. 逐处改动

### 1.1 第 5 项：文字层级改走 `ui_widgets`（10 处）

| # | 文件:行 | 改前 | 改后 |
|---:|---|---|---|
| 1 | `asset_detail.py:355` | `ttk.Label(holder, text='（缩略图暂不可用）', foreground=COLORS['text_muted'])` | `HintLabel(holder, text='（缩略图暂不可用）')` |
| 2 | `asset_detail.py:358` | `ttk.Label(holder, text='（缺图）', foreground=COLORS['text_muted'])` | `HintLabel(holder, text='（缺图）')` |
| 3 | `asset_detail.py:442` | `ttk.Label(body, text='还没有：…', foreground=COLORS['text_muted'])` | `DescriptionBlock(body, text='还没有：…')` |
| 4 | `asset_detail.py:625` | `ttk.Label(holder, text='（缺图）', foreground=COLORS['text_muted'])` | `HintLabel(holder, text='（缺图）')` |
| 5 | `asset_detail.py:635` | `ttk.Label(panel, text='还没有状态变体：…', foreground=COLORS['text_muted'])` | `DescriptionBlock(panel, text='还没有状态变体：…')` |
| 6 | `asset_detail.py:649` | `ttk.Label(foot, text='正典板 … 格已绑定 · 状态变体 … 个', foreground=COLORS['text_secondary'])` | `DescriptionBlock(foot, text='正典板 … 格已绑定 · 状态变体 … 个')` |
| 7 | `desktop.py:191` | `ttk.Label(self.header_info, style='Muted.TLabel', font=FONTS['pet_hint'], anchor='e')` | `HintLabel(self.header_info)`，随后 `configure(anchor='e')` |
| 8 | `desktop.py:192` | `ttk.Label(self.header_info, style='Muted.TLabel', font=FONTS['pet_hint'], anchor='e', justify='right')` | `HintLabel(self.header_info)`，随后 `configure(anchor='e', justify='right')` |
| 9 | `desktop_media_pages.py:234` | `ttk.Label(head, text='已落盘：…' / '还没生成…', foreground=COLORS['text_secondary'])` | `DescriptionBlock(head, text=…)` |
| 10 | `desktop_media_pages.py:323` | `ttk.Label(box, text='理由：'+…, foreground=COLORS['text_secondary'], wraplength=TEXT_DESC['wraplength'], justify='left')` | `DescriptionBlock(box, text='理由：'+…)` |

- 短提示（≤20 字，如「（缺图）」「（缩略图暂不可用）」）用 `HintLabel`；较长空态/状态文字用 `DescriptionBlock`。
- 未使用 `ProgressLabel`：其 token 前景色为 `primary`，会改变原 `text_secondary`／`text_muted` 的颜色层级。
- `text_muted` 迁移后采用组件规范色 `text_secondary`；`desktop.py` header 的 `pet_hint` 字号改由 `TEXT_HINT['font']`（`FONTS['caption']`）提供。这是组件 token 的规范值，不是新增的视觉分支。
- 所有 `pack` / `grid` 的 side、fill、expand、padx、pady、sticky、row、column 参数保持原样；只移除了由组件自身提供的 `foreground` / `wraplength` / `justify` 参数。
- `desktop.py` 两个 header label 后续仍有 `configure(text=...)` 更新；`HintLabel` 是 `ttk.Label` 子类，`configure(text=...)` 与 `textvariable` 均兼容。`test_frame_sources.py:116` 读 `header_status.cget("text")` 已通过。

### 1.2 第 7 项：忙碌态改走 `BusyState.set_busy`（2 处）

| # | 文件:行 | 改前 | 改后 |
|---:|---|---|---|
| 11 | `desktop.py:1506` / `1510` | `previous=self.win.cget('cursor')`；`self.win.configure(cursor='watch')`；`finally: self.win.configure(cursor=previous)` | `self.busy_state.set_busy(True)`；`finally: self.busy_state.set_busy(False)`（沿用 `Desktop` 已有的 `self.busy_state`，不新建宿主） |
| 12 | `pet_models_ui.py:525` / `532` / `559` / `577` | 搜寻按钮手工 `configure(text='正在搜寻…', state='disabled')`，结束再 `configure(text='自动搜寻', state='normal')` | 局部 `search_busy = BusyState(hint)`；开始时 `set_busy(True, controls=(search_button,), progress=False)`，`stop_search` / 结果轮询结束 `set_busy(False)`；按钮文字仍由原逻辑设置 |

- `desktop.py` 忙碌态不再改写状态栏文字（不传 `message`），避免留下永久「正在导入…」提示；用户可见文字保持原样。
- `pet_models_ui.py` 的 `BusyState(hint)` 以现有提示变量为 status，`progress=False`，只负责按钮禁用/恢复；未牵动窗口结构。

### 1.3 `asset_batch.py`

| # | 文件:行 | 改前 | 改后 |
|---:|---|---|---|
| 13 | `asset_batch.py:5` | `from tkinter import ttk,filedialog,messagebox` | `from tkinter import ttk,messagebox` |

- 已 grep 确认 `filedialog` 在该文件无任何使用；`messagebox` 按任务书保留（本轮未扩大删除范围）。

## 2. 新增/同步测试

### 2.1 新增真 Tk 回归测试

| 测试 | 覆盖 |
|---|---|
| `tests/test_asset_detail.py:179` `TextHierarchyTests.test_asset_hints_and_empty_states_use_shared_text_components` | 第 5 项：真实 `tk.Tk()` 下构建正典板、状态变体、角色格，断言短提示是 `HintLabel`、空态/统计是 `DescriptionBlock`，并核对文本、前景色与 `linespace` token。 |
| `tests/test_ui_batch3_shell.py:152` `ShellScrollAndStatusTests.test_header_hints_use_the_shared_text_component` | 第 5 项：真实桌面 Tk fixture 下断言 `header_model` / `header_status` 为 `HintLabel`，前景色、`linespace`、`max_chars` 取自 `TEXT_HINT`，且 `anchor='e'`、状态行 `justify='right'` 保留。 |
| `tests/test_ui_batch3_shell.py:162` `ShellScrollAndStatusTests.test_json_import_uses_the_shared_busy_state` | 第 7 项：真实桌面 Tk fixture 下调用 `import_json()`，断言 `set_busy` 调用序列为 `[True, False]`、不传 `message`（不改写状态栏文字）、结束后 `busy=False`。 |

第 5、7 项各至少有 1 条真实 Tk 回归测试。

### 2.2 测试查找/期望同步

- `tests/test_frame_sources.py:116`：仍用 `header_status.cget("text")` 查找；`HintLabel` 是 `ttk.Label` 子类，查找方式与断言均未改，**断言未动**。
- `tests/test_asset_detail.py` 的 `texts()`：仍遍历 `ttk.Label`；子类自动包含，查找方式与断言均未改，**断言未动**。
- `tests/test_pet_ui.py` / `tests/test_pet_settings.py` 的 header 替身：未改，仍构造 `ttk.Label`，**断言未动**。
- `tests/test_ui_batch3_shell.py:142` `test_shell_fonts_come_from_tokens`：查找方式未改（仍读 `d.header_model` / `d.header_status` 的实际字体）；期望字体来源由 `FONTS['pet_hint'][1]` 改为组件规范 `TEXT_HINT['font'][1]`，并新增 `assertIsInstance(widget, HintLabel)`。原「字号等于 token」断言未删除、未弱化；这是组件规范值的契约同步，**不是**「断言未动」条目。

## 3. 实际命令与计数

| 命令 | 实际结果 |
|---|---|
| `python -B smoke_test.py --architecture` | **374 条，146.634 秒，OK，0 红，EXIT=0**（最终工作树） |
| `python -B run_selftests.py -k asset_detail media_pages pet_models asset_batch ui_widgets` | **93 条，42.2 秒，0 个文件有红，ALL TESTS PASSED，EXIT=0** |
| `python -B run_selftests.py -k test_asset_detail test_ui_batch3_shell test_ui_batch7_settings_models` | **71 条，53.9 秒，0 个文件有红，ALL TESTS PASSED，EXIT=0** |
| `python -B run_selftests.py -k test_ui_batch3_shell`（最终重放后） | **10 条，9.4 秒，ALL TESTS PASSED，EXIT=0** |
| `python -B run_selftests.py -k test_frame_sources` | **4 条，3.7 秒，ALL TESTS PASSED，EXIT=0** |
| `python -B smoke_test.py --affected asset_detail desktop desktop_media_pages pet_models_ui asset_batch` | **EXIT=1，未取得正常计数**。两次均未在 900 秒级上限内完成：第一次被外层工具 900 秒超时终止；第二次由 `smoke_test.py` 内置 `GATE_TIMEOUT = 900` 终止，日志显示已跑到 `test_workflow`，属于运行时限而非断言失败。未改 `smoke_test.py` 抬高上限。 |
| 按 `_affected_test_plan` 给出的 57 个筛选名执行 `run_selftests.py --serial -k <57 个筛选名>`（`--affected` 会走的同类串行门禁，去掉 wrapper 的 900 秒上限） | **2102 条，986.5 秒，0 个文件有红，ALL TESTS PASSED，EXIT=0**；登记跳过 1 条（`test_core.ValidateProfileTests.test_stage_profile_wrong_preset_rejected`，需实机复验打包产物）。`test_ui_batch3_shell` 不在该 57 个筛选名内，已单独跑 10/10。 |

说明：上述 2102 条长跑期间，外部进程把 `desktop.py` 写回了原版（见 §4）；该长跑覆盖的是其它消费者与 `desktop.py` 的原版路径。`desktop.py` 两处改动由 `test_ui_batch3_shell` 10/10 与 `test_frame_sources` 4/4 在最终重放后单独验证，架构门禁 374/374 也在最终重放后通过。

## 4. 需裁决事项与风险

1. **`desktop.py` 被外部进程周期性写回原版（需提交前复核）**：本轮观察到该文件在 19:19、20:28:44、20:40:14 被写回 HEAD 内容（长度 122890），同一时段其它已改文件不受影响；执行方未运行任何 git 写命令。疑似外部编辑器/同步进程自动保存旧缓冲。最终已重新应用 `desktop.py` 两处改动，并在架构门禁后核对 `HintLabel`（191/192）与 `busy_state.set_busy`（1506/1510）仍在。**提交方在暂存前请再核对 `git diff -- 程序/desktop.py`**；若再次被写回，需先关闭该外部进程。
2. **组件规范值**：`text_muted` → `text_secondary`、header `pet_hint` → `TEXT_HINT['font']` 均由 `ui_widgets` 组件 token 决定；若要求 header 维持 8pt，需要另有组件或 token 决策，本轮未在页面覆写组件视觉规格。
3. **`pet_models_ui` 搜寻忙碌态未新增专用异步测试**：任务书要求第 7 项至少 1 条真 Tk 测试，已由 `test_json_import_uses_the_shared_busy_state` 满足；`pet_models_ui` 的 `search_busy` 路径由现有 `test_ui_batch7_settings_models`（13 条，窗口构建/设置页）与本次 93 条定向自检间接覆盖，未新增伪造异步时序的测试。
4. **`asset_batch.messagebox` 仍未使用**：任务书只点名删除 `filedialog`，本轮按最小范围保留 `messagebox`，未顺手扩大改动。

## 5. 自检结论

- 改动范围：仅 `asset_detail.py`、`desktop.py`、`desktop_media_pages.py`、`pet_models_ui.py`、`asset_batch.py`、`tests/test_asset_detail.py`、`tests/test_ui_batch3_shell.py` 与本结果文件；未改 `project_status.md`、`AGENTS.md`。
- 用户可见文字内容未改；颜色/字号层级按 `ui_widgets` 组件规范统一；`pack` / `grid` 布局参数保持。
- 现有测试未删除、未跳过、未弱化；新增测试均为真 Tk。
- `pet_models_ui.open_manager` 因本轮新增代码一度达到 501 行（上限 497）；已将搜寻结果回填抽为模块级 `_apply_program_search`，函数现为 **493 行**，未抬高门禁上限。
- 未运行项：默认 `smoke_test.py`、`smoke_test.py --gate`、`run_selftests.py --all --safe`（任务书未要求）。
- `--affected` wrapper 未取得正常计数（900 秒上限），已在 §3 如实写明；同一底层串行清单 2102 条全绿。

## 独立验收（Claude，主工作区）

- 来源：AUDIT 审计 B.1/B.3/B.5 的绕过清单；UIFIX 首版改了 desktop.py 两处合理绕过，经 UIFIX2、UIFIX3 两轮返修还原（desktop.py 与 test_ui_batch3_shell 对 HEAD 无差异）。
- 主树 `run_selftests -k asset_detail media_pages pet_models asset_batch ui_widgets ui_batch3 frame_sources ui_batch6 ui_batch7` 全绿；`smoke_test --architecture` OK。
- 红证：把 `asset_detail.py:442` 的 `DescriptionBlock` 改回 `ttk.Label`、或 `:625` 的 `HintLabel` 改回 `ttk.Label` → `TextHierarchyTests` 各自 FAIL，已还原。
- 裁决：`text_muted` 迁移后用组件规范色 `text_secondary`，接受；`pet_models_ui` 搜寻忙碌态无专用异步测试，由现有窗口构建测试间接覆盖，接受。
- 现有测试断言未动（只新增 1 个真 Tk 回归测试）。
