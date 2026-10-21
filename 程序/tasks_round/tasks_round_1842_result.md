# R1842 结果（修复轮）：剧本结构页——同源去重、厂商命名、编辑按钮改造

## 一、三问

1. **本轮类型**：修复轮（`AGENTS.md` §3.2）。现象是「02 剧本结构」页同源结构剧本并列多份、文件名内容段写死 `正稿`、编辑按钮仍是旧的「修改内容／恢复删除／保存修改」；判定为代码偏离了需求（REQ-S02 阶段应「同源只显示一份」「内容段＝厂商／本地」「编辑自动保存」），按 §2.7 第 3 条改代码，并同步阶段文档 REQ/DES。
2. **测试跑了吗、三基线过了吗**：
   - 跑了（本轮需要的定向命令，见下）。
   - 默认冒烟：**8/8 通过**（`python -B smoke_test.py`）。
   - 架构门禁：`tests.architecture.test_layers`、`test_requirement_traceability`、`test_function_size_ratchet` 共 **12 项通过**（改前 `test_function_size_ratchet` 因函数变小而红，已按「登记上限只许下降」下调 `script_structure` 上限 244→205、删除已降到 ≤150 的 `content_box` 登记）。
   - 全量回归：**未运行**（任务书明令不跑 `run_selftests.py`／`--all`／`--affected`；本轮无全量凭据）。
3. **欠账**：`project_status.md` 欠账**未减少**（本轮不涉及、未改状态页）。另确认一条**既存、与本轮无关**的红：`tests.test_script_contract.AuditTests.test_the_audit_covers_every_script_skill`（`manifest_rows` 直读 `skills/` 注册表，期望的 `script-forging`、`编剧技能集` 两个 SKILL 文件在本工作树不存在）；本轮的 `script_contract.py` 改动只落在 `structured_script_*`／`write_structured_script` 一带，`manifest_rows`/`audit_rows`（`:1225` 起）未动。

## 二、改动（文件:函数）

生产：
- `script_contract.py`
  - `structured_script_file_name`：内容段默认 `'正稿'` → `'本地'`。
  - `canonical_structured_script_path(project, content='本地')`：不再写死 `正稿`，透传内容段。
  - 新增 `_structured_script_candidates(project, available_only)`：抽出结构稿发现逻辑（复用展示与回收两处）。
  - 新增 `_structured_source_identity(project, path)`：有血缘按来源路径分组，无来源记录退化为内容 sha256。
  - 新增 `_is_newer(path, other)`：同源内按 `(mtime, 路径)` 比较。
  - `structured_script_paths`：由「全局 sha256 去重」改为「同源只保留最新一份；无来源记录按内容 sha256 去重」。
  - 新增 `superseded_structured_scripts(project, source, *, exclude)`：返回与新稿同来源的旧稿（不含 exclude），供回收。
  - `write_structured_script(..., vendor=None, supersede=None)`：`vendor` 经 `_file_name_part` 净化后作内容段（缺省 `本地`）；写入成功后经注入的 `supersede(paths)` 回调回收同源旧份（契约层不直接依赖回收服务，规避 L0→L1 越层）。
- `stage_exec.py` `_run_script_structure.execute('write_structured_script')`：注入 `supersede` 回调（`storage_maintenance.recycle_paths`）。
- `skill_tools.py` `_write_structured_script`：注入 `supersede` 回调。
- `script_structure_edit_controller.py`（新增，L2，无 Tk）：`ScriptStructureEditController`——内容快照撤销栈 + 防抖自动保存；`save`／`schedule`／`cancel` 全注入，不依赖 Tk、不写项目数据。
- `ui_tokens.py`：新增常量 `SCRIPT_EDIT_SAVE_DEBOUNCE_MS = 600`。
- `desktop_script_pages.py`
  - 新增模块级 `_install_script_edit_controls(...)`：建「编辑／后退／恢复」按钮，把 `<<Modified>>` 接到控制器 `record_edit`、按钮接到 `begin_edit`／`undo`／`edit_undo`，按 `can_undo` 维护「后退」禁用态。
  - `content_box`：改为调用 `_install_script_edit_controls`；`SCRIPT_EDIT_BUTTON_WIDTH` 注释改为「编辑/后退/恢复三按钮」。

测试/架构登记：
- `tests/architecture/_layers.py`：登记 `script_structure_edit_controller` 为 L2。
- `tests/architecture/test_function_size_ratchet.py`：`script_structure` 上限 244→205（实际 190），删除 `content_box` 登记（实际 127，已 ≤150）。**断言未动，仅下调/删除登记上限。**
- 新增 `tests/test_script_structure_dedup.py`（REQ-S02-33/34）、`tests/test_script_structure_edit.py`（REQ-S02-35）。

文档：
- `docs/stages/S02_剧本结构.md`：新增 `REQ-S02-33`（同源去重+回收）、`REQ-S02-34`（厂商/本地命名+旧 `_正稿_` 兼容）、`REQ-S02-35`（编辑/后退/恢复+防抖）；对应 `DES-S02-33/34/35`；模块分工表补 L2 `script_structure_edit_controller`；测试锚定表补两行。

## 三、结构剧本生成调用点清单

- `script_contract.canonical_structured_script_path` / `structured_script_file_name`：命名定义处（内容段由写死 `正稿` 改为参数化，默认 `本地`）。
- `stage_exec.py::_run_script_structure` → `write_structured_script`（本地规则，`content` 为 `structure_script` 输出）→ 文件名内容段 `本地`。
- `skill_tools.py::_write_structured_script` → `write_structured_script`（`content=None`，本地规则）→ 文件名内容段 `本地`。
- 经模型生成（未来/测试注入）→ `write_structured_script(..., vendor='Anthropic')` → 文件名内容段 `Anthropic`。

## 四、V1–V5 实测命令与计数

工作目录 `D:\漫剧制作助手\.wt\lane_c8\程序`，解释器 `D:\漫剧制作助手\运行环境\Python\python.exe -B`，`$env:PYTHONPATH='tests'`。

| 验收 | 命令 | 结果 |
| --- | --- | --- |
| V1/V2 | `-m unittest tests.test_script_structure_dedup` | **8 项 OK** |
| V3 | `-m unittest tests.test_script_structure_edit` | **6 项 OK** |
| 新用例合计 | `-m unittest tests.test_script_structure_dedup tests.test_script_structure_edit` | **14 项 OK** |
| V2 注入契约 | `-m unittest tests.test_model_output_contract` | OK（文件名注入用例未改、通过） |
| 既有剧本结构回归 | `-m unittest tests.test_script_structure tests.test_model_output_contract tests.test_script_page_services tests.test_script_structure_scope tests.test_req_anchor_s02` | **84 项 OK**（未含 test_script_contract 的既存红） |
| 其余 grep 命中 | `-m unittest tests.test_core tests.test_critical_chains tests.test_file_cache tests.test_req_s07_anchors tests.test_sanhu_mode tests.test_script_view_style tests.test_stage_gate_modes` | **224 项 OK（skipped=1）** |
| grep 命中（大文件） | `-m unittest tests.test_pet_ui` | **退出码 0（通过）** |
| V5 架构 | `-m unittest tests.architecture.test_layers tests.architecture.test_requirement_traceability tests.architecture.test_function_size_ratchet` | **12 项 OK** |
| 冒烟 | `python -B smoke_test.py` | **8/8 通过** |
| 已改的 UI 旧用例 | `-m unittest tests.test_ui_reading_density` | **8 项 OK** |
| 已改的 UI 旧用例 | `-m unittest tests.test_ui_edges.UiEdgeTests.test_script_structure_page_shows_source_and_output_in_separate_boxes` | **OK** |

未运行：`run_selftests.py`、`--architecture`、全量、`--affected`（任务书禁止）。`tests.test_ui_edges` 全文件未跑（任务书标注「主干就红，不要修」），只跑了本轮改动的单个测试。

## 五、先红证据（V4 变异）

`script_contract.py` 变异前 sha256：`5F86F8B1065BB40A7834F1E0726B7684DC8A3406CF996013585306C4B418A08B`。

对 `_structured_source_identity` 做变异（`if sources:` → `if sources and False:`，即去掉同源去重、退回内容 sha256），跑 V1：

```text
Ran 1 test in 0.097s
FAILED (failures=1)
AssertionError: Tuples differ: (…_本地_20261021.md, …_本地_20261020.md) != (…_本地_20261021.md,)
First tuple contains 1 additional elements.
```

还原后 sha256：`5F86F8B1065BB40A7834F1E0726B7684DC8A3406CF996013585306C4B418A08B`（**与改前一致**），复跑 V1/V2/V3 全绿（14 项 OK）。

## 六、断言未动声明

未改、未弱化、未跳过的既有断言：
- `tests/test_model_output_contract.py` 全文件未动，文件名注入用例照常通过。
- `tests/test_req_anchor_s02.py`、`tests/test_script_structure_scope.py`、`tests/test_script_contract.py`（除既存红外）、`tests/test_script_page_services.py` 等全未动。
- `tests/architecture/test_layers.py`、`test_requirement_traceability.py` 未动。

契约有意变更需同步的旧用例（逐条列出，均为「文件名内容段」或「按钮」契约变更，非弱化断言）：
1. `tests/test_script_structure.py::test_write_only_creates_script_md_and_keeps_raw_unchanged`：断言正则 `_结构剧本_正稿_` → `_结构剧本_本地_`（REQ-S02-34 内容段契约）。
2. `tests/test_ui_reading_density.py::test_unchanged_edit_save_preserves_source_bytes`：删「保存修改」按钮调用与「保存后 state=disabled」断言（该断言对应被 G3 删除的保存按钮行为）；核心断言「未改动的编辑态不重写源文件字节」保留不变。
3. `tests/test_ui_edges.py::test_script_structure_page_shows_source_and_output_in_separate_boxes`：`_save_button.invoke()` → `_controller.save_now()`，删「保存后 state=disabled」断言；核心断言「恢复删除后原文恢复」「文件含新增修订」保留不变。

「恢复」按钮语义说明：G3 要求保留原「恢复删除」语义——本实现沿用原 `restore_deleted` 的 `preview.edit_undo()`（Tk 文本框原生撤销，恢复刚删除的文字），与「后退」（控制器内容快照撤销栈，整份内容回退上一版）是两回事，未改语义。

## 七、需裁决事项

无必须裁决事项。两点记录，不阻断：
1. 既存红 `test_the_audit_covers_every_script_skill`（SKILL 审计缺 `script-forging`/`编剧技能集`，非本轮引入、不在授权范围，未处理）。
2. G3 删除「保存修改」后，编辑态不再显式回到只读态（自动保存持续同步）；切换剧本的下拉守卫仍按 `state=='normal'` 阻止切换。这是任务书 G3 按钮契约的直接结果，未扩大范围改动；如需「退出编辑」按钮或切换时先 flush，属新需求。

## 独立验收（Claude，rebase 到 a1e42b1b 后，隐藏桌面）
- 新测试＋剧本结构定向＋test_script_contract＋test_ui_reading_density＋架构三门禁：156 项，唯一红 test_the_audit_covers_every_script_skill（既存，不在本轮）。test_ui_reading_density 4 条在隐藏桌面因托盘注册失败报错，设 DRAMA_SUPPRESS_TRAY=1 后 8/8 过（主干同样现象，属环境限制）。
- 冒烟：0 失败。test_ui_edges 红集合与主干一致（已知主干红）；多出的 test_the_video_table_shows_the_first_frame_thumbnail 单跑 OK，判为顺序相关抖动。
- 真实项目探针（摄影侠_20260930 只读副本）：两份同源 `_正稿_` 结构剧本只显示最新一份；以 vendor='Anthropic' 写入后新文件名为 `*_结构剧本_Anthropic_<日期>.md`，两份旧稿交回收回调，只显示新稿。按钮文案为 编辑／后退／恢复；自动保存由 test_script_structure_edit 6 项覆盖，未在真实 GUI 手点。
