# R3846 结果：修复轮——distribution_manifest 补登 docs/specs 八册（合并后自动全量红项清偿）＋R3842 结果补记
<!-- round-evidence: {"commit_base": "99554eb1", "credential_hits": 0, "evidence_sha256": "b721b7d5334a41c3", "exit": 0, "failed": 0, "passed": 0, "round": 3846, "tests": "docs-only"} -->

## 1. 三问

- 轮次类型：修复轮（§3.2）＋结果补记。
- 是否跑测试：是。`run_selftests.py -k distribution_selfcheck` 3/3 绿（改动前该用例在合并树 auto-full-safe 中实测红）；`smoke_test.py` 9/9 绿。架构门禁本轮不适用（纯清单/文档改动，未动源码与层级）。全量凭据：见 §4。
- 欠账少了吗：是——清掉合并后 auto-full-safe 的唯一红项；`docs/specs` 欠账为 master 侧 R3809 遗留，非验收分支引入。

## 2. 根因与修复

- 根因：master 侧提交 `76d432de`（R3809）新增 `程序/docs/specs/` 七册规格＋README 共 8 个文件，但未在 `程序/distribution_manifest.md` 声明保留或排除；`distribution_build.plan()` 将其列入 `undecided`，`test_distribution_selfcheck.test_manifest_covers_every_file` 断言失败。该红项与本验收分支无关，在合并树 auto-full-safe（21:05–21:40，2141 秒）中首次暴露。
- 修复：`distribution_manifest.md`「必须排除 → 开发文档」一行补登 `程序/docs/specs/**`（与 `docs/stages`、`docs/review`、`docs/adr` 同属开发文档，不进分发副本）。
- 附带：`tasks_round_3842_result.md` §6 补记合并校验原始输出与 commit `99554eb1`（合并提交后追加的如实记录，随本轮一并入库），并新增 §6.1 记录 auto-full-safe 实测红/Deferred 结果。

## 3. 改动文件

- `程序/distribution_manifest.md`（1 行：`程序/docs/specs/**` 入排除表开发文档行）
- `程序/tasks_round/tasks_round_3842_result.md`（补记 §6/§6.1，无新断言）
- `程序/tasks_round/tasks_round_3846_result.md`（本文件）

## 4. 全量欠账与 GUI_DEFERRED 处置

- 合并后 auto-full-safe（HEAD `99554eb1`）退出码 1：红 1 条（本轮已修）＋170 个 GUI 测试 `GUI_DEFERRED`（他车道 PID 8600 持 GUI 令牌，`SUSPECT_CONCURRENCY`）。
- 修复合入 master 后，将按 runbook 对该 HEAD 串行重跑 `run_selftests.py --all --safe`；最终凭据以 `.git/full-safe-receipts.json` 真实绿凭据为准。未拿到绿凭据前不宣称全量通过。
