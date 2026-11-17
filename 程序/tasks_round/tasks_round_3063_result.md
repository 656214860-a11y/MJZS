# R3063 结果 — 死代码清理轮（结构治理·按报告执行）第 1 批
<!-- round-evidence: {"commit_base": "b0a9b3a9", "credential_hits": 0, "evidence_sha256": "c3685f75f4d78daf", "exit": 0, "failed": 0, "passed": 53, "round": 3063, "tests": "run_selftests.py -k coverage_baseline branch_coverage layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」——执行 `维护记录/死代码与无效功能任务书_20261116.md` A 节候选。本批删 2 个模块（≤3 上限）。
2. **测试**：`smoke_test.py` 8/8 通过；`smoke_test.py --architecture` 471 项中 7 失败＋1 错误，均为本分支既有欠账（棘轮基线漂移、round 连续性、skills 文件缺失、runbook 声明），逐一核对均不引用本批删除文件；覆盖率基线三件套（test_coverage_baseline／test_branch_coverage_floor／test_layers）定向复跑 15/15 通过。
3. **欠账**：`project_status.md` 欠账口径未变（状态页仅 master 提交）；本批消除 2 个死模块登记。

## 本批变更

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `edit_habits_dialog.py`（147 行） | 任务书 A1：全仓零 import/patch/动态引用，仅 DES-S01-60 文档与 `_layers` 登记 |
| 删除 | `project_settings_dialog.py`（12 行，`confirm_unattended`） | 任务书 A1：生产零调用；「无人值守」勾选框已改由三虎 `pet.auto_variable` 承载 |
| 同步 | `tests/ui_edges_support.py` | 移除 `UiEdgeCase.setUp` 中对已删模块的补丁桩（§2.4 契约变化：被测对象删除，断言未动） |
| 同步 | `tests/architecture/_layers.py` | 移除 `edit_habits_dialog`、`project_settings_dialog` 两个登记名（实体文件已不存在） |
| 同步 | `architecture.md` L4 表 | 移除 `project_settings_dialog` 名 |
| 同步 | `维护记录/覆盖率基线.json` | 用 `scripts/coverage_report.py` 按原 9 个定向目标重测刷新（97 用例全绿；次序修复了 cell_zoom_suppress.py 漏登记的既有口径漂移） |
| 同步 | `runbook.md` §11 | 基线数字 548→547、477→476，与基线字段自洽 |

## 备注

- `previs_progress.py` 经复核改判 KEEP：`test_stdlib_closure.py` 注释与 `HOST_SCRIPTS` 证明它随白模批量任务复制进批次目录交 Blender 侧执行，不是死代码；任务书 A1 已更正口径。
- 剩余候选 19 个文件按 ≤3 模块/轮继续：R3064 契约报表簇、R3065 分镜目录兼容簇、R3066–R3070 T10 死门面五批。
- L0/L1 门面删除轮需同步 `分支覆盖率基线.json`＋`分支覆盖率下限.json`（script_brief/model_protocol/pet_settings_contract/shot_selection/store_program_locator 在册）。
