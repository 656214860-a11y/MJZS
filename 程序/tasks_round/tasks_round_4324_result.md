# R4324 结果：MERGE-GUARD（merge_round 对「分支已含于 master」短路，杜绝幻影合并轮）
<!-- round-evidence: {"commit_base": "0815d266f", "credential_hits": 0, "evidence_sha256": "742399fac7d6e9a8", "exit": 0, "failed": 0, "passed": 49, "round": 4324, "tests": "run_selftests.py -k merge_round lane_merge full_safe_merge"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。卡面 MERGE-GUARD（`.agent-tmp/supervision-card-MERGE-GUARD.md` 固化）：对已含于 master 的分支跑 `dev.py merge` 会白跑出口 CI，`merge --no-commit` 返回 0 但不产生 MERGE_HEAD，流程仍领号、改状态页、写结果与 evidence，最后 commit_round 被规则 34a 拒绝，留下暂存垃圾还烧掉轮次号。只改 `scripts/merge_round.py` 与 `tests/test_merge_round.py`。
- （二）测试跑了吗、三个基线：跑了。先红后绿——改前定向 2 条新增用例失败（原文见下）；改后 `run_selftests.py -k merge_round lane_merge full_safe_merge` 49 条 0 红、退出码 0；`smoke_test.py --architecture` 702 条 OK、退出码 0。默认冒烟与全量 `--all --safe` 本轮未跑（卡面禁止运行卡面未列的命令，且未列入验收）。
- （三）欠账少了吗：少了。幻影合并轮缺陷闭合：已含于 master 的分支在出口 CI 之前短路返回，不占主干、不领号、不写三件套。

## 缺陷复现方式

1. `scripts/merge_round.py` 的 `main()`（改前 383–387 行）在 `rebase_onto_master` 返回 0 后直接调 `run_branch_exit_ci`，全程没有「分支已是 master 祖先」的检查；`rebase_onto_master` 内 `merge-base --is-ancestor upstream branch`（改前 207–208 行）判的是反方向（master 是否已含于分支，用于跳过空变基），不能替代。
2. `_merge_locked()`（改前 410–424 行）里 `merge --no-commit --no-ff` 返回 0 后未校验 `merge_in_progress()`：Already up to date 时 returncode 也是 0、无 MERGE_HEAD，随后照常 `wait_for_lock` → `round_claim.claim_next` → 写状态页/结果文件 → `commit_merge_result` → 34a 拒绝。

新增 `MergeGuardTests` 三条用例（`程序/tests/test_merge_round.py`）在未改产品代码前运行 `run_selftests.py -k merge_round lane_merge full_safe_merge`，2 条红，红的原因与卡面缺陷一致（出口 CI 被调用；merge 成功但无 MERGE_HEAD 时仍走到等锁路径返回 3）。

## 改前红的条数与原因（原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k merge_round lane_merge full_safe_merge`（改前）：共 49 条用例，1 个文件有红，2 条失败用例（均在 test_merge_round.MergeGuardTests）：

- `test_branch_already_in_master_returns_before_exit_ci`：`AssertionError: Expected 'run_branch_exit_ci' to not have been called. Called 1 times. Calls: [call('feature')].`（闸一缺失，出口 CI 被白跑）
- `test_merge_without_merge_head_returns_before_lock_and_claim`：`AssertionError: 3 != 0`（闸二缺失，merge 返回 0 但无 MERGE_HEAD 时仍走到 `wait_for_lock` 分支返回 3）

## 改了哪几处

- `程序/scripts/merge_round.py`：
  - 闸一（386–388 行）：`main()` 中 `rebase_onto_master` 返回 0 之后、`run_branch_exit_ci` 之前，加 `_git("merge-base", "--is-ancestor", args.branch, "master").returncode == 0` 检查；命中则打印「分支 <branch> 已含于 master，无需合入。」并 `return 0`，不跑 CI、不领号、不动主树。
  - 闸二（422–424 行）：`_merge_locked()` 中 `merge --no-commit --no-ff` 返回 0 之后、`wait_for_lock` 之前，`if not merge_in_progress():` 打印「分支 <branch> 已含于 master，本次 merge 未产生合并内容，未领号。」并 `return 0`，不领号、不写状态页/结果/evidence。正常合并路径（MERGE_HEAD 存在）行为逐字不变。
- `程序/tests/test_merge_round.py`：
  - 新增 `MergeGuardTests`（403–481 行）三条：已含于 master 时 `main` 直接返回 0 且 `run_branch_exit_ci`/`acquire_merge_lane`/`claim_next` 未被调用；merge 成功但无 MERGE_HEAD 时 `_merge_locked` 返回 0 且 `wait_for_lock`/`claim_next` 未被调用；正常有差异分支仍走 `ci → lock → _merge_locked` 全链（回归）。
  - 既有替身按新契约同步两处（见下节）。
- `程序/tasks_round/tasks_round_4324_result.md`：本文件。

## 测试替身契约同步说明（§2.4；断言保持原样）

卡面「现有行不删不改」与「改完后定向命令全绿」在本文件内存冲突：两处既有 git 替身编码了旧行为假设，新闸落地后若不同步则既有断言必然变红。按「测试契约有意变更时可同步 mock、断言保持原样并注明」处理，只在替身内插入条件应答，不删不改任何断言与用例名：

- `MergeOrderTests._git`（309–310 行）：替身原对未匹配命令一律返回 0，会使闸一始终命中、两个既有用例（`test_dirty_trunk_after_exit_ci_does_not_take_the_lane`、`test_exit_ci_precedes_the_merge_lane`）必然变红。插入 `merge-base → 返回 1` 应答，模型化「分支未含于 master」（这两个用例本就模拟有差异分支）；未修产品时该应答不被调用，对旧行为无影响。
- `test_locked_merge_uses_no_commit_only_on_a_clean_trunk` 内 `clean` 替身（389–391 行）：原替身对 `rev-parse -q --verify MERGE_HEAD` 恒返回 1，但真实 git 在 `merge --no-commit` 成功且有内容时必写 MERGE_HEAD；该用例场景是「merge 产生了真实合并再等锁超时返回 3」。同步为「merge 调用出现后返回 0、之前仍 1」；未修产品时行为不变（依旧走到等锁超时返回 3），断言 `code == 3` 与 merge 调用记录原样保留。

未删除、未弱化、未 skip 任何既有断言；其余测试文件零改动。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `0815d266f` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/merge-guard` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k merge_round lane_merge full_safe_merge`（改前） | 1 | 49 条中 2 条失败（见上） |
| 同命令（改后） | 0 | 49 条 0 红，`ALL TESTS PASSED`（49 = 改前 46 + 新增 3） |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 702 tests in 301.480s`，`OK` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次号 `4324` |
| `git diff --numstat` | 0 | `6	0	程序/scripts/merge_round.py`、`85	1	程序/tests/test_merge_round.py`（结果文件为新增未跟踪，不计入 diff） |

改后定向输出尾部原文：

```
共 49 条用例，8.9 秒；0 个文件有红
最慢 5 路工作单元：
  test_merge_round#2            8.1 秒 / 14 条
  test_merge_round#3            6.5 秒 / 7 条
  test_lane_merge_queue         0.5 秒 / 13 条
  test_merge_round#1            0.1 秒 / 7 条
  test_full_safe_merge_gate     0.1 秒 / 8 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：…\.git\selftest-incremental.json
最近 5 轮自检中位基线：21.5 秒

ALL TESTS PASSED
```

架构门禁输出尾部原文：

```
----------------------------------------------------------------------
Ran 702 tests in 301.480s

OK
✅ 架构治理测试：tests/architecture
```

## 没有验证的地方

- 未实跑一次真实 `dev.py merge`（该命令只在主检出 master 上运行，车道工作树内不可实跑）；短路行为由 mock 层用例覆盖，真实 git 语义（`merge-base --is-ancestor` 返回码、`merge --no-commit` Already-up-to-date 无 MERGE_HEAD）沿用既有 `MergeInProgressTests` 真仓库用例与 git 文档口径，未另做端到端复演。
- 出口 CI 期间「分支被他窗合入」的竞态只由闸二兜底覆盖；闸一按变基后分支头判定，竞态窗口内的极端时序未做并发测试。
- 默认冒烟、全量 `--all --safe` 未跑（卡面未列入验收且禁止运行未列命令）。
