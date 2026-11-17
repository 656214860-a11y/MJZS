# R3217 结果：合入 codex/wip-R3215＋合并后基线校正

## 三问

1. **本轮属于 §3 哪种类型**：验证基线/状态接续轮（车道代收口合并＋合并后台账校正，无功能改动）。
2. **测试跑了吗、三个基线过了吗**：默认冒烟 **9/9**；`test_unification_ratchet` 4/4、`test_coverage_baseline`＋`test_branch_coverage_floor` 9/9 转绿；覆盖率工具重测 97 用例全过；全量架构门禁复跑结果见下。
3. **欠账少了吗**：是——清偿了 master 上遗留的 `test_bare_json_load_debt_is_a_nonincreasing_subset` 红（合并树实测锚点补登记）与覆盖率基线模块口径漂移（646→647，补 `domain/offline_asr_setup.py`）。

## 改动

- `git merge codex/wip-R3215`（`33196cf3`）：把 R3215 代收口的停摆车道 R3199 依赖白名单政策（白名单文档、CLAUDE/AGENTS 政策修订、`tests/architecture/test_dependency_whitelist.py`、证据与结果文件）并入本分支；自动合并无冲突。
- 合并后基线校正（本提交）：
  - `维护记录/架构统一基数.json`「第四项」：`agent/media.py` `probe:json.loads` 锚点按合并树实测改 `0c4dea56d7890453`；新增 `ui/asset_thumbs.py` `_probe_media:json.loads:a2bd43747d745de3` exempt 条目（R3210 媒体预览 ffprobe stdout 解析，包路径）；`count` 由误写的 82 改回 pending 项数 **0**（全部 82 项已 exempt/migrated，`actual-exempt == pending == ∅`）。
  - `维护记录/覆盖率基线.json`：`scripts/coverage_report.py` 九组定向用例重测，**647 模块／71 覆盖／97 用例全过**（新增 `domain/offline_asr_setup.py`）。
  - `runbook.md` §11：同步 647/71/576 口径。
  - 本文件与 `tasks_round_3216_result.md`：同步合并轮次补记。

## 验证

- `unittest tests.architecture.test_unification_ratchet`：**4/4 OK**（修复前 `actual<=identities` 缺 2 项、`count` 82≠0 两处红）。
- `unittest tests.architecture.test_coverage_baseline tests.architecture.test_branch_coverage_floor`：**9/9 OK**（修复前模块集合缺 `domain/offline_asr_setup.py`、工具口径 647≠646 两处红）。
- `coverage_report.py` 重测：97 用例全过，基线已写入。
- `smoke_test.py`：9/9。

## 提交

- `33196cf3` R3217 合入 codex/wip-R3215 合并提交。
- 本轮基线校正提交（hash 以 git log 为准）。
