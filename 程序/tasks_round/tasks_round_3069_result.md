# R3069 结果 — 死代码清理轮（结构治理·按报告执行）第 5 批
<!-- round-evidence: {"commit_base": "9d7ab15e", "credential_hits": 0, "evidence_sha256": "737289234f00ddb3", "exit": 0, "failed": 0, "passed": 31, "round": 3069, "tests": "run_selftests.py -k coverage_baseline branch_coverage_floor layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 3 个模块（≤3 上限）。轮次号 3069（3068 被并行车道领走）。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_branch_coverage_floor`＋`test_layers` 复跑 15/15 通过；三份基线 JSON 程序化自洽校验通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A3·T10 死门面：contract/infra/domain 混合批）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `shot_selection.py`（→contract）、`store_program_locator.py`（→infra）、`idea_script_heuristic.py`（→domain） | 任务书 A3：三门面生产/测试/patch/动态引用全零；实体均 LIVE（`app.py`/`local_previs.py` 用 `contract.shot_selection`，`workflow_settings.py` 用 `infra.store_program_locator`，`idea_chat.py`/`writing_api.py` 用 `domain.idea_script_heuristic`） |
| 同步 | `维护记录/覆盖率基线.json` | 移除 3 门面行，modules_total 540→537（covered=0） |
| 同步 | `维护记录/分支覆盖率基线.json`＋`分支覆盖率下限.json` | shot_selection（L0）＋store_program_locator（L1）出分支口径：modules_total 77→75，points_total 2153→2138、points_covered 1047→1044；idea_script_heuristic 属 L2 不在分支口径 |
| 同步 | `runbook.md` §11 | 行覆盖 540→537/469→466；分支覆盖 77→75 |

## 备注

- `_layers.py` 未改：三个登记名经 R3067 修正后的 `entity_file` 解析到包实体，分层分类保持有效。
- `architecture.md` 未改：层表按模块概念名登记，实体存活故名字仍有效。
- 余 9 个 orchestrator T10 死门面，分三批收尾。
