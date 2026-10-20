# R1759：修复轮——三处陈旧内部标识／路径文案对齐现行阶段命名（STALEID）

## 三问

1. **本轮类型**：修复轮。三条均判定为“代码偏离需求”：`panel_text()` 继续展示旧内部编号；新台账继续写 `stage='03_continuity'`；SG-02 两个阻塞分支返回不存在的旧路径。
2. **测试与三基线**：已跑。默认冒烟 8/8；架构门禁 `test_requirement_traceability` + `test_layers` 10/10；消费方 18 个文件中 17 个整文件通过。`test_asset_detail` 整文件仍有 4 个既有 Tk 焦点顺序失败，单独运行失败方法均为绿；以 HEAD 的 `asset_contract.py` 复跑同样为 37 测试、4 失败，确认不是本轮行为引入。全量回归按任务书明确禁止，未运行，不能记为绿色基线。
3. **欠账是否减少**：未减少。本任务未领号、未改 `project_status.md`，也没有把既有 GUI 测试欠账记为本轮已解决。

## 根因与改动

### REQ-S05-42

- 根因：`asset_contract.panel_text()` 把用户可见阶段名写死为 `02_assets`，与 `pet_bus.STAGES` / `stage_label()` 的现行名称分离，阶段编号变化后文案漂移。
- 改动：`asset_contract.py:panel_text()` 从 `pet_bus.stage_label('assets')` 与 `stage_label('continuity')` 现算标题；注释同步说明现算原因。`pet_bus` 与 `asset_contract` 同属 L0，未引入反向依赖。
- 文档：`docs/stages/S05_资产管理.md:44` 的 REQ-S05-42 改 ✅，描述现算行为。
- 测试：`tests/test_req_s05_anchors.py` 新增 `test_req_s05_42_panel_text_uses_current_stage_labels`，docstring 锚定 REQ-S05-42。

### REQ-S06-27

- 根因：`continuity_ledger.build()` 新写台账仍使用历史内部键 `03_continuity`；发布与问题登记路径也残留旧目录文案/别名。
- 改动：`continuity_ledger.py:build()` 新台账写 `stage='continuity'`；新增 `ledger_path(project)`，统一经 `stage_path_service.read_file(project, 'continuity', 'output', LEDGER_NAME)` 解析当前或旧目录实际文件；`read()` 复用该函数；`publish_bundle()` 与 `issues_path()` 写现行 `06连贯性清单`。保留 `stage_layout` 旧键别名和旧 `05连贯性清单` 只读兼容，未改旧台账读取语义。
- 文档：`docs/stages/S06_连贯性清单.md:33` 的 REQ-S06-27 改 ✅，写明新写现行键、旧目录只读兼容。
- 测试：`tests/test_req_s06_anchors.py` 新增 `test_req_s06_27_new_ledger_uses_current_stage_and_old_ledger_stays_readable`，覆盖新台账 `stage`、schema 校验、旧 `stage='03_continuity'` 在旧 `05连贯性清单` 目录下的读取/校验/陈旧判断。

### REQ-S07-45

- 根因：`stage_parallel.ledger_ready()` 的陈旧和待办分支用字符串拼接返回 `<项目>/03_continuity/output/continuity_ledger.json`，与实际读取路径分离；当前和旧项目布局下该展示路径都可能不存在。
- 改动：`stage_parallel.py:ledger_ready()` 改为复用 `continuity_ledger.ledger_path(project)`，两个阻塞分支都返回实际读到的文件；台账不存在分支仍不返回 artifacts。
- 文档：`docs/stages/S07_分镜定稿.md:46` 的 REQ-S07-45 改 ✅；设计尾部待定清单移除已完成条目并注明已落地。
- 测试：`tests/test_req_s07_anchors.py` 新增 `test_req_s07_45_ledger_artifacts_are_real_paths_in_both_blocking_branches`，覆盖 `06连贯性清单`、旧 `05连贯性清单`、陈旧/待办两个分支、`Path.is_file()` 和台账不存在分支。

## V1-V6 实测

| 验收项 | 实测 |
| --- | --- |
| V1 | 新 `build()` 台账 `stage == 'continuity'`；手写 `stage='03_continuity'` 的旧台账可 `read`、通过 `artifact_schema.validate`，`stale_reason` 返回空。对应 S06 锚点绿。 |
| V2 | `ledger_ready()` 陈旧与待办分支在 `06连贯性清单`、旧 `05连贯性清单` 两种布局下都返回真实文件，`is_file()` 为真；不存在台账时 artifacts 为空。对应 S07 锚点绿。 |
| V3 | `panel_text()` 以 `pet_bus.stage_label('assets')` / `stage_label('continuity')` 开头和包含断言通过，文本不含 `02_assets`、`03_continuity`。对应 S05 锚点绿。 |
| V4 | 三条需求均改 ✅，带现行行为描述；三条测试 docstring 均锚定对应 REQ。未发现可同步的同编号 DES 条目。 |
| V5 | 三条锚点均先红后绿；三类生产改动分别临时回退，对应锚点均变红，恢复后均转绿。详见下表。 |
| V6 | 未新增生产模块、未新增 `skipTest`、未改 `desktop.py`、未新增分层登记；架构门禁 10/10。 |

## 先红、转绿与变异证据

- S05 先红：旧文案下 `text.startswith('资产管理页（05资产管理）...')` 为 `False`。
- S06 先红：初始夹具写错场景后修正，断言为 `'03_continuity' != 'continuity'`。
- S07 先红：两个布局 subtest 均得到 `<临时项目>/03_continuity/output/continuity_ledger.json`，而实际文件在 `06连贯性清单` 或 `05连贯性清单`。
- 变异 S05：把 `panel_text()` 标题临时改回 `02_assets`，`test_req_s05_42...` 在 `startswith` 断言处失败；恢复后 OK。
- 变异 S06：把 `build()` 的 `stage` 临时改回 `03_continuity`，`test_req_s06_27...` 在 `assertEqual` 处失败；恢复后 OK。
- 变异 S07：把 `artifact` 临时改回手工拼接旧路径，两个布局 subtest 均在真实路径断言处失败；恢复后 OK。

## 消费方、架构门禁与冒烟

- 逐文件运行 18 个消费方测试文件：17 个整文件通过。
- `tests/test_asset_detail.py`：37 个测试中 4 个 Tk 焦点顺序失败；`test_image_actions_are_keyboard_buttons` 的两个失败方法单独运行均 OK。以 HEAD 的 `asset_contract.py` 通过临时模块加载复跑同一整文件，仍为 37 测试、4 失败，确认不是本轮改动引入。
- `tests.test_asset_detail.BoardTests`：6 个测试中 3 个焦点断言失败，显示同进程前序缩放/焦点用例污染。
- 架构门禁：`PYTHONPATH=tests python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_layers`，10/10 OK。
- 默认冒烟：`python -B smoke_test.py`，通过 8 项、失败 0 项。
- 全量：未运行，遵守任务书“不要跑 `run_selftests.py` / `--architecture` / 全量 / `--affected`”的限制；无全量绿色凭据。
- 实际 Python 测试/门禁/冒烟调用计数：可核对 43 次；其中 4 次为先红阶段，后续 39 次含环境导入重跑、变异和 HEAD 基线辨别（有 3 次 `skip_reasons` 路径导入错误、1 次基线引导导入错误，均按真实结果记录）。

## 既有测试与断言

- 既有测试预期值变更为：**无**。
- 仅新增 3 条锚点测试；`tests/test_req_s07_anchors.py` 把原测试方法内的 `import stage_parallel` 移到模块顶部，原 REQ-S07-03 的断言未改。
- 既有断言未弱化、未删除、未跳过；未新增 `skipTest`，未用改动测试制造通过。

## 需裁决事项

1. 当前工作树为 detached HEAD `41f4fc1b`，任务书指定该车道；AGENTS §2.5 通常禁止 detached HEAD 开工。全程未执行 git 写命令、未领号、未提交、未改 `project_status.md`，需提交方决定是否接受本结果。
2. `test_asset_detail` 整文件存在既有 Tk 焦点顺序失败：`test_image_actions_are_keyboard_buttons` 3 个子测试、`test_reload_restores_focus_to_detail_navigation` 1 个；失败方法单独运行均绿，且 HEAD 基线同样红。若整文件必须绿才能验收，应另开 GUI 测试稳定性修复轮，不宜在本任务范围内改 `asset_detail.py` 或弱化断言。
3. 其它旧内部标识仍存在于范围外模块，未擅自修改：`confirm_gates.py` 的 `03_continuity` 确认记录路径/文案，`desktop_media_pages.py` 的旧路径与文案，`skill_tools.py:446` 与 `stage_execution_service.py:1378` 的旧路径文案；`pet_ui_support.py` 与 `stage_layout.py` 中的旧键映射属于兼容层，是否继续保留需按旧项目只读要求裁决。
4. 全量回归与欠账闭环未执行，源于任务书明确限制；提交前由调度方决定是否另行跑全量。

## 独立验收（Claude，车道 lane_b1 内直接运行，真实环境）

- 范围：3 个生产文件（asset_contract／continuity_ledger／stage_parallel）、3 份 docs/stages、3 个既有锚点测试文件；测试 diff 只追加（s07 文件另有一处 `import stage_parallel` 由函数内提升到模块级，无断言改动）。
- 锚点：S05/S06/S07 三个锚点文件 28/28 全绿；消费方 18 个测试文件逐个跑全绿（含 test_asset_detail 37/37、test_pet_ui 599/599、test_stage_wiring 16/16；这三个须带 `PYTHONPATH=tests`，执行方自报的 test_asset_detail 4 个 Tk 失败本次未复现）。
- 门禁：`smoke_test.py` 全绿；`smoke_test.py --architecture` 375/375。
- 变异：临时回退三份生产改动，S05-42、S06-27、S07-45（两种布局）共 4 项失败；还原后三个文件 sha256 与改动态一致。
- 未跑：`run_selftests` 全量与 `--all --safe`（本轮不属触发条件）。
