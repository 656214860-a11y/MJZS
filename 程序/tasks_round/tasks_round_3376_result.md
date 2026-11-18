# R3376 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 7B 补项（降级开关按族命名 — §3c-3）
<!-- round-evidence: {"commit_base": "67d8f28d", "credential_hits": 0, "evidence_sha256": "0a2169fce039e177", "exit": 0, "failed": 0, "passed": 51, "round": 3376, "tests": "run_selftests.py -k startup_selfcheck diagnostic_capture startup_budget"} -->

## 三问

1. **本轮类型**：§3.9 可靠性轮补项（任务书轮 7B 遗留项 §3c-3「降级开关按族命名」，`L0契约层防崩溃与协议补齐任务书.md:633/653/824`）——给启动自检乙类检查加按族命名的 skip／disable 旗标开关（A1111 `--skip-*`／`--disable-*` 的 GUI 等价物）。范围：`infra/diagnostic_capture.py` 族开关实现、`tests/test_startup_selfcheck.py` 新增 `FamilySwitchTests` 9 条、`tests/architecture/test_startup_budget.py` 启动链名单补 3 个助手函数、`维护记录/分支覆盖率基线.json` 真实重测刷新。
2. **测试跑了吗、三个基线过了吗**：跑了。先红后绿：`FamilySwitchTests` 改动前（回退 `diagnostic_capture.py` 至 HEAD）9 条中 6 条红（skip 跳过/留诊断、disable 抑制/静默/安全入口共 6 个行为断言失败），4 条行为不变断言保持绿；改动后 9/9 绿、全文件 45 条 0 红。定向 `run_selftests.py -k startup_selfcheck` 45 条、`-k diagnostic_capture` 5 条、`-k startup_budget` 1 条全绿；`smoke_test.py --affected diagnostic_capture` 10/10（门禁 6 个测试文件 71 条 0 红）；默认冒烟 **9/9**；`smoke_test.py --architecture` 532 条、唯一红 `test_round_number_continuous`（3234 != 3371，状态页滞后既有欠账，与 R3364 同一失败集合、与本改动无关）。全量 `--all --safe` 未跑（§4.2 轮 7B 档只要求 `--affected`；合入 master 前启动路径改动的当次全量由合并轮出口 CI 与后台验收承担，`full-safe-receipts.json` 未新增本轮凭据，如实记录）。
3. **欠账少了吗**：少了——任务书 §8「轮 7B」勾选里的「降级开关按族命名」遗留项本轮闭环，任务书 14 条验收勾选至此全部有对应轮次证据；收尾《任务完成文件》按规则 35 在下一收尾轮输出（本文件为代码轮结果）。新增欠账：无（边界观察见 §备注）。

## 任务与决策来源

- 任务书 §8 轮 7B 勾选（`L0契约层防崩溃与协议补齐任务书.md:824`）：「降级开关按族命名（`skip` / `disable` 的 GUI 等价物，§3c-3）」；§3c-3（:633）：「开关**按族命名**（`--skip-*` 跳检查 / `--disable-*` 关功能），本项目 GUI 版落成 `诊断 → 以安全模式启动` 时要有同名族的两组选项」。
- R3364 结果文件 §备注明确「不在本轮 D10 任务表内，未做，留待任务书细化轮」——本轮即该补项。
- 领号：`round_claim.py next` → **R3376**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`；`round-claims.json` 归属记录 2026-11-18T17:16:42+08:00）。

## 实现

| 文件 | 改动 |
| --- | --- |
| `infra/diagnostic_capture.py` | 新增 §3c-3 族开关段（:562-620）：`_STARTUP_CHECK_FAMILIES` 10 族登记（与 `startup_checks` 检查元组一一对应，注释要求新增检查同轮登记族名）；`_family_flag_enabled`（`data/selfcheck_{skip,disable}_<族>.flag` 存在即开，OSError 按未开）；`_skip_diagnostic`（DEGRADED、scope=`selfcheck`、码 `selfcheck-skip-<族-连字符>`，状态栏按码去重不串族）；`_family_check` 包裹器（skip→返回跳过诊断且探针不执行；disable→检查照跑、产出与自身异常一并抑制返回 None 完全静默；无旗标→原样返回）；`startup_checks` 末尾 `zip` 逐族包裹。甲类 FATAL 仍只有全局 `selfcheck_failopen.flag`（G12 不变），族开关管不到甲类。 |
| `tests/test_startup_selfcheck.py` | 新增 `FamilySwitchTests` 9 条：skip 只跳自家族并留 `selfcheck-skip-disk-space` DEGRADED 诊断、disable 只关自家族告警、disable 照跑检查但丢弃产出（spy 断言已调用）、skip 不执行探针（spy 断言未调用）、disable 吞检查异常且不产生 `check-error`、无旗标行为不变、族旗标不影响甲类 FATAL 与全局 failopen、安全启动入口同样生效、未知族旗标惰性。 |
| `tests/architecture/test_startup_budget.py` | `STARTUP_CHAIN` 登记 `_family_flag_enabled`/`_skip_diagnostic`/`_family_check` 三个新助手——它们与其余检查同在启动链上（`startup_checks` 逐项包裹调用），纳入启动预算零递归扫描断言。 |
| `维护记录/分支覆盖率基线.json` | 真实重测刷新：`diagnostic_capture.py` 决策点 85→89、覆盖 43→46（51.7%）；同目标集（90 个测试模块不变、`tests_ok=true`）下 `asset_contract.py` 覆盖 57→59（89.4%，点数不变）为主干演进带来的真实增量；合计 2737→2741 点、1517→1522 覆盖。棘轮下限表未动（diagnostic_capture 下限 12.0、asset_contract 下限 83.0，实测均高于下限）。 |

## 设计口径（自主决策）

- **GUI 等价物＝旗标文件**：任务书原文要求「`诊断 → 以安全模式启动` 落成时要有同名族的两组选项」——该 GUI 尚不存在；本轮先把族命名机制与旗标契约落到自检组装点，与既有 `selfcheck_failopen.flag`（G12）同为 `data/` 下零依赖旗标文件，未来安全模式入口只需按 `_STARTUP_CHECK_FAMILIES` 同名族写两组旗标即可接入，不改自检侧。
- **skip 与 disable 语义分层**：skip 跳过探针本体（用于探针自身卡死/误报拖慢启动的逃生），disable 只关告警（检查照跑用于排查、产出抑制完全静默）；两者都只认自己那族，未知族名旗标惰性不生效（有测试钉死）。
- **族开关不碰甲类**：`selfcheck_failopen.flag` 仍是甲类 FATAL 唯一降级通道（G12 语义不变，有测试钉死族旗标对 FATAL 无效、failopen 对族检查无效）。
- **旗标读取失败按未开**：`is_file()` OSError 一律按旗标不存在处理，不挡自检（与 `_failopen_enabled` 同口径）。

## 先红后绿证据

改动前（`git checkout HEAD -- infra/diagnostic_capture.py`，测试文件保留新用例）：

```
FAIL: test_disable_flag_silences_only_its_family
FAIL: test_disable_still_runs_check_but_discards_output
FAIL: test_disable_swallows_check_error_silently
FAIL: test_flags_honored_on_safe_start_entry
FAIL: test_skip_does_not_execute_the_check
FAIL: test_skip_flag_skips_only_its_family_and_records_diagnostic
Ran 45 tests — FAILED (failures=6)
```

（`test_no_flags_preserves_current_behavior`／`test_unknown_family_flag_is_inert`／`test_family_flags_do_not_affect_fatal_or_global_failopen` 三条断言的是未变行为，改前即绿，属预期。）改动后 `FamilySwitchTests` 9/9 绿，全文件 45 条 0 红。

## 测试与验证证据

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k startup_selfcheck` | 45 条用例 0 红（4 分片 12.0 秒） |
| `run_selftests.py -k diagnostic_capture` | 5 条 0 红 |
| `run_selftests.py -k startup_budget` | `architecture.test_startup_budget` 1 条 0 红 |
| `smoke_test.py --affected diagnostic_capture` | 10/10 通过；门禁定向 6 个测试文件（test_app_logging/test_diagnostic_capture/test_l1_l0_integration_r3331/test_secret_status_diagnostics/test_selftest_diagnostics_isolation/test_video_result_polling）71 条 0 红（GUI 令牌排队等待约 200 秒后通过） |
| `smoke_test.py`（默认） | **9/9** 通过 |
| `smoke_test.py --architecture` | 532 条，唯一红 `test_round_number_continuous`（`3234 != 3371`）：`project_status.md` 按钩子规则只许 master 更新、分支保留旧版抬头的已知治理现场（R3330/R3364 同口径），master 侧合并轮出口 CI 期间 `MERGE_HEAD` 豁免该断言；分支覆盖率棘轮红已由本轮基线真实重测闭环（改前 85!=89 → 改后 5/5 绿） |
| `run_selftests.py --all --safe` | 未运行（§4.2 轮 7B 档不要求；启动路径改动的当次全量由合并轮 `local_ci.py exit`＋后台验收承担） |

## 问题与处置

1. **分支覆盖率基线红**：`test_branch_coverage_floor` 改动前实测 `diagnostic_capture.py 基线决策点与当前实体不一致（85 != 89）`。处置：上一会话已按同一 90 目标集真实重测产出 `_tmp_branchcov_result.json`（`tests_ok=true`，点数/覆盖与本改动逐模块吻合），本轮核对模块集合、targets、metric、scope 与基线完全一致后并入 `分支覆盖率基线.json`，复跑 `test_branch_coverage_floor` 5/5 绿；下限表按「只许人工上调」未动。
2. **`test_round_number_continuous`**：改前改后同一失败（状态页轮次滞后），与本改动无关；合并轮 `merge_round.py` 领号抬头后由 `continuity_gap()` 复核，`MERGE_HEAD` 在场时该测试自带豁免。
3. **临时文件清理**：`维护记录/_tmp_targets.txt`、`_tmp_targets_lf.txt`（重测目标清单）与 `_tmp_branchcov_result.json`（重测产物，内容已并入基线）为本轮临时产物，已受控删除；`tasks_round/地基加固_跨车道交接单.md` 为无关未跟踪文件，保持原样（R3364 同口径）。

## 自主决策记录

- **族名集与检查一一对应**：`_STARTUP_CHECK_FAMILIES` 顺序与 `startup_checks` 元组顺序绑定并由 `zip` 配对；注释明示「新增检查须同轮登记族名」，`test_startup_budget` 的启动链名单同步登记三个新助手，防止新检查漏挂族开关。
- **skip 诊断留痕而非静默**：skip 旗标产出一条 DEGRADED（`selfcheck-skip-<族>`），让「某族被跳过」在状态栏可见；disable 才是完全静默。这与 A1111 `--skip-*`（跳过但有提示）／`--disable-*`（关功能）语义同构。
- **族名只用 `[a-z0-9_]`**：直接进入旗标文件名 `selfcheck_{skip,disable}_<族>.flag`，无需转义；诊断码把 `_` 换成 `-` 与既有 kebab 码表风格一致。

## 剩余欠账与边界观察

- 「诊断 → 以安全模式启动」GUI 入口本身不在本轮范围（任务书原文亦注明「落成时要有同名族的两组选项」——族名现已就位，入口轮到时按 `_STARTUP_CHECK_FAMILIES` 写旗标即可）。
- `test_round_number_continuous` 需 master 侧状态页回合后自愈；本分支每轮都会报同一红（R3330/R3364 同口径）。
- 任务书 §9「明确不做」各项（recoverable 零读取、schema() 零消费者、queue.put 锁外、播报前缀校验、重试次数配置）维持既有记欠账口径，由收尾《任务完成文件》逐条登记。

## 提交

- 已提交：`R3376:` 前缀提交一条（`dev.py commit -m "R3376: …" --tests startup_selfcheck diagnostic_capture startup_budget`；commit hash 见 `git log`——结果文件随提交入库，hash 无法自指）；提交门禁生成证据 `tasks_round/evidence/R3376.json` 并入本提交。
- 提交内容仅授权范围：`程序/infra/diagnostic_capture.py`、`程序/tests/test_startup_selfcheck.py`、`程序/tests/architecture/test_startup_budget.py`、`程序/维护记录/分支覆盖率基线.json`、本结果文件。
- 不添加：`程序/project_status.md`（仅 master 可提交）、`程序/tasks_round/地基加固_跨车道交接单.md`（无关未跟踪文件，保持未跟踪）。
- 《L0契约层防崩溃与协议补齐·任务完成.md》按规则 35 由收尾轮输出并经 `taskbook_closure.validate` 核对，本文件不代替。

## 备注（接续上下文）

本轮由截断的前一会话接续完成：降级开关实现与测试已在工作树就位，本轮补齐分支覆盖率基线重测并入、先红后绿复验证据、定向＋冒烟＋架构复跑、临时文件清理与结果文件；任务书 14 条验收勾选的轮次映射已核对（轮 0=R3239、轮 1=R3246、轮 2=R3259、轮 3A=R3267、轮 3B=R3280、轮 4A=R3286、轮 4B=R3298、轮 5A=R3300、轮 5B=R3304、轮 6A=R3311、轮 6B=R3313、轮 6C=R3330、轮 6D=R3338、轮 7A=R3343、轮 7B=R3364、本补项=R3376；调研并入=R3255、只读诊断=R3230）。

