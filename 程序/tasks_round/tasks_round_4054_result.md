# R4054 — 文档轮：分发清单声明 `开发者工具/AI开发流程/**` 为开发工具不分发（docs-only）
<!-- round-evidence: {"commit_base": "9013996d", "credential_hits": 0, "evidence_sha256": "d52ac8f926e8ad3b", "exit": 0, "failed": 0, "passed": 3, "round": 4054, "tests": "run_selftests.py -k distribution_selfcheck"} -->

## 三问

1. **轮次类型**：文档轮（docs-only）。只改 `程序/distribution_manifest.md` 一行，不动代码、测试和其他文档。
2. **测试跑了吗、三个基线各是什么结果**：跑了 `tests.test_distribution_selfcheck`（3/3）、`tests.test_distribution_build`（18/18）、`smoke_test.py --architecture`（695/695，失败集合为空）。默认冒烟与全量未跑（文档轮不要求）。
3. **欠账少了吗**：少了一条主干上一直存在的红。R4025-FAIL（6e3300c8）接入 `开发者工具/AI开发流程/` 下 21 个文件时没补清单，`test_manifest_covers_every_file` 在主干上一直失败。

## 改了什么

| 文件 | 改动 |
|---|---|
| `程序/distribution_manifest.md` | 「必须排除」表在 `开发者工具/本地CI.cmd` 那行之后新增一行：`开发者工具/AI开发流程/**`，类别「开发工具」，理由为 Spec Kit 模板、Superpowers 子代理开发技能与流程说明，仅供开发时按需读取，不随分发。已有行未改。 |

## 为什么

R4025-FAIL 接入了 `开发者工具/AI开发流程/` 下 21 个文件（README.md、spec-kit、superpowers），这些文件只供开发时按需读取（见 `tasks_round_4025_result.md`），不属于用户运行所需，但当时没有在清单里声明保留或排除，导致主干的清单覆盖检查一直红。

## 验证

工作目录 `程序`：

- 改前 `python -B -m unittest tests.test_distribution_selfcheck -v`：`Ran 3 tests`，`FAILED (failures=1)`；`test_manifest_covers_every_file` 报 21 个未声明文件，逐个核对全部以 `开发者工具/AI开发流程/` 开头，无其他目录。
- 改后 `python -B -m unittest tests.test_distribution_selfcheck -v`：`Ran 3 tests`，`OK`。
- 改后 `python -B -m unittest tests.test_distribution_build -v`：`Ran 18 tests`，`OK`。
- 改后 `python -B smoke_test.py --architecture`：`Ran 695 tests`，`OK`，失败集合为空。
- `git diff --stat`：仅 `程序/distribution_manifest.md`，1 insertion，0 deletion。

## 没做的

- 没跑全量自测（`run_selftests.py --all --safe`）。
- `开发者工具/AI开发流程/` 下这 21 个文件要不要继续留在仓库，由负责人另定；本轮只声明「不分发」。
