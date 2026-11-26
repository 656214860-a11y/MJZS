# tasks_round_4540_result — REL-09 出口静态门禁修复：付费护栏四处人话文案去「转人工」
<!-- round-evidence: {"commit_base": "90821c865", "credential_hits": 0, "evidence_sha256": "1da440d2557ee9d7", "exit": 0, "failed": 0, "passed": 275, "round": 4540, "tests": "run_selftests.py -k copy_rules pet_agent budget skill_budget stage_doc_sections agent_doc_budget requirement_traceability design_coverage"} -->

- 本轮属于 §3.2 修复轮（REL-09 卡面 W2 同步轮：功能已在车道提交 90821c865，本轮只修 `test_copy_rules.PetVoiceTests.test_nothing_talks_about_the_user_in_third_person` 判红的四处用户可见文案，不重做付费护栏、不 reset）。
- 测试跑了吗、三个基线过了吗：跑了。卡面 3 条验收命令退出码均 0——`run_selftests.py -k pet_agent budget skill_budget`（234 条 0 红）；`run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（34 条 0 红）；`smoke_test.py --architecture`（711 条 OK）。另按卡面第 3 步加跑 `run_selftests.py -k copy_rules pet_agent budget skill_budget`（252 条 0 红，含 test_copy_rules 18 条全绿，即本次判红用例转绿）。
- 欠账少了吗：copy_rules 第三人称门禁由红转绿；无新增欠账。

## 改动表

| 文件 | 改动 | 内容 |
| --- | --- | --- |
| `orchestrator/skill_budget.py` | +4/−4 | `paid_stage_guard` 四处返回给用户的人话把句尾「这一步转人工」改为「请您接手这一步」：L295 配额不够、L298 Token 见底、L315 未授权、L319 配额刚用完。四件事实（配额不够／Token 见底／未授权／配额刚用完）与 `agent.spend`／`agent.pause`＋`stage.failed` 行为逐字未动；函数 docstring 内的「转人工」是开发者注释，`literals()` 只收非 docstring 字符串常量（`tests/test_copy_rules.py:309-325`），按卡面不动。 |
| `tests/test_pet_agent.py` | +1/−1 | `AutoPaidAuthorizationTests.test_refusal_pauses_the_chain_and_never_dispatches` 的 `assertIn('转人工', reply)` 改为 `assertIn('请您接手这一步', reply)`，与新文案对齐；同文件 docstring 与 assertEqual 消息里的「转人工」是测试内部文字，扫描器跳过 `test_*` 文件，按卡面不动。 |

四处文案原文 → 新文案（`%` 占位与前缀事实原样）：

- L295：`「%s」的%s配额不够（%d/%d）：这一步转人工` → `「%s」的%s配额不够（%d/%d）：请您接手这一步`
- L298：`「%s」预计消耗 Token %d，今天的 Token 见底（剩 %d/%d）：这一步转人工` → `「%s」预计消耗 Token %d，今天的 Token 见底（剩 %d/%d）：请您接手这一步`
- L315：`「%s」是付费步骤，您没有授权：这一步转人工` → `「%s」是付费步骤，您没有授权：请您接手这一步`
- L319：`「%s」的%s配额刚用完：这一步转人工` → `「%s」的%s配额刚用完：请您接手这一步`

## git diff --numstat 原文

```
4	4	程序/orchestrator/skill_budget.py
1	1	程序/tests/test_pet_agent.py
```

（结果文件 `tasks_round/tasks_round_4540_result.md` 与证据 `tasks_round/evidence/R4540.json` 由本轮新增，提交时一并暂存。）

## 实际命令与退出码

前置（全部 exit 0）：`git status --porcelain` 无输出；`git log -1 --format=%h` = `90821c865`；`git rev-parse --abbrev-ref HEAD` = `codex/rel-09-sync`。

```
..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k copy_rules pet_agent budget skill_budget
共 252 条用例，9.1 秒；0 个文件有红        （exit 0；test_copy_rules 18 条全绿）

..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_agent budget skill_budget
共 234 条用例，3.9 秒；0 个文件有红        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage
共 34 条用例，1.3 秒；0 个文件有红        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture
Ran 711 tests in 440.765s
OK
✅ 架构治理测试：tests/architecture        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim
4540                                    （exit 0）
```

## 三个基线数

- 默认冒烟基线：未单跑 `smoke_test.py`（无参）；卡面只要求 `--architecture`，实测 711 条 OK。如实记「未运行」。
- 架构门禁当轮实际：711 条，失败集合 0 项（本树实测全绿）。
- 全量回归 `--all --safe`：未跑（分支车道不累计）。

## 提交状态

- `dev.py claim` → 轮次号 **4540**。
- 提交命令：`dev.py commit -m "R4540: REL-09 出口静态门禁修复：付费护栏四处人话文案去转人工" orchestrator/skill_budget.py tests/test_pet_agent.py tasks_round/tasks_round_4540_result.md --tests copy_rules pet_agent budget skill_budget stage_doc_sections agent_doc_budget requirement_traceability design_coverage`
- commit hash 以 `git log` 为准；提交后 `git status --porcelain` 须无输出。

## 没有验证的地方

- 真实桌面人工看屏未做；文案改动只影响 `paid_stage_guard` 四条返回串，行为路径（pause／stage.failed／spend）由 `test_pet_agent` AutoPaidAuthorizationTests 覆盖。
- `tests/test_copy_rules.py`、`NO_SECOND_PERSON` 禁词表均未改动；门禁仍按原样扫描全部非测试源码字符串常量。
- skill_budget.py docstring（L276-284）与 pet_agent.py:366、desktop_pet_bridge.py:77 等处的「转人工」为注释/docstring，`literals()` 不收集，属设计内保留，未逐一人工复核其余历史文档中的同词（扫描器实测全绿）。
