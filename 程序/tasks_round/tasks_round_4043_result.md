# R4043 结果：补上《阶段文档写法》并落地 DOC-G1 结构守卫
<!-- round-evidence: {"commit_base": "45f2662b", "credential_hits": 0, "evidence_sha256": "7d6756712394f6c7", "exit": 0, "failed": 0, "passed": 10, "round": 4043, "tests": "run_selftests.py -k test_stage_doc_sections"} -->

## 开头三问

- 本轮属于哪种类型：测试轮／结构治理补登记（任务书 §4.3 DOC-G1）。这是原先未提交的 DOC-G1：测试与两处登记已在工作树里，但结构测试因缺少登记目标 `程序/docs/process/阶段文档写法.md` 报 STR006，本卡补回该文档并完成收尾。
- 测试跑了吗、三个基线：跑了。结构定向 `test_stage_doc_sections`＋`test_structure` 37/37 通过（OK）；架构门禁 `smoke_test.py --architecture` 695/695 全绿，失败集合为空；默认冒烟 `smoke_test.py` 通过 9 项、失败 0 项。
- 欠账少了吗：少了。补回缺失的阶段文档后 STR006 解除，结构检查 `delta.added=[]`、`delta.removed=[]`，violations 集合与重写前一致（仅 `STR003` 一条存量）。

## 与 R3986 及未提交 DOC-G1 的关系

- 缺失的 `程序/docs/process/阶段文档写法.md`、`程序/tasks_round/tasks_round_3986_result.md`、`程序/tasks_round/evidence/R3986.json` 均来自 R3986 的提交对象 `13ed7f81577860a1ae04cd17c303db81fe06c019`，按对象检出，内容未改写。R3986 的父提交 `81577d36` 已是当前 HEAD 的祖先，但 R3986 自身不是，因此只按对象取上述三个文件。
- 只补登记表一行与 README 一句，**没有整文件检出 README 或登记表**，避免删掉 R3989 的「用户沟通与要求标准」与 R4014 的「会话接续记录」等后加行。
- 相关 `git stash` 条目**未删除、未 pop**，仍保留 DOC-G1 原始实现作为证据。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `docs/process/阶段文档写法.md` | 按对象 `13ed7f81` 检出，内容未改写 |
| `tasks_round/tasks_round_3986_result.md` | 按对象 `13ed7f81` 检出（R3986 结果原件） |
| `tasks_round/evidence/R3986.json` | 按对象 `13ed7f81` 检出（R3986 证据原件） |
| `docs/README.md` | 「阶段条款」段末追加一句：「接口」「交互」两节的写法见[《阶段文档写法》](process/阶段文档写法.md)。 |
| `docs/records/工程文档登记表.md` | 在 `docs/process/联调测试出口基线.md` 行后插入一行：`| docs/process/阶段文档写法.md | 全局 | 全局 | 权威 | R3986 | 执行 agent |` |
| `tests/architecture/test_stage_doc_sections.py` | 沿用未提交 DOC-G1 的测试文件，未改断言 |
| `architecture.md` | 「## 当前架构门禁清单」保留 `test_stage_doc_sections.py` 一行 |
| `governance/structure.json` | `test_ownership` 保留 `程序/tests/architecture/test_stage_doc_sections.py` 一条，targets 指向阶段文档 |
| `governance/structure-baseline.json` | `check_structure.py --write-baseline` 官方入口重写，仅 `source_commit`／`inventory_sha256`／`policy_sha256` 变化 |
| `tasks_round/tasks_round_4043_result.md` | 本文件（由未提交的 4004 结果改名） |

## 结构基线重写证据

- 命令：`python -B 程序/governance/check_structure.py --write-baseline --summary`
- 输出：`{"ok": true, "delta": {"added": [], "removed": []}, "finding_count": 1, "findings": []}`
- 重写前后 violations 的 `(rule_id, path)` 集合一致：`[("STR003", "程序/batch_frames_tool/启动批量首帧.pyw")]`；仅溯源字段更新为新 HEAD `45f2662b`。

## T1 改前失败输出（先红，沿用 R3990 实证）

`problems()` 空桩 `return []` 时 `PY -B -m unittest tests.architecture.test_stage_doc_sections -v`（原文见 `tasks_round_3990_result.md`「T1 改前失败输出」一节）：

```
FAIL: test_t1_r1_violation ... AssertionError: [] is not true
FAIL: test_t1_r2_violation ... AssertionError: [] is not true
FAIL: test_t1_r3_violation ... AssertionError: [] is not true
FAIL: test_t1_r4_violation ... AssertionError: [] is not true
FAIL: test_t1_r5_violation ... AssertionError: [] is not true
FAIL: test_t1_r6_violation ... AssertionError: [] is not true
FAIL: test_t4_require_all_flags_missing_sections ... AssertionError: [] is not true
Ran 10 tests in 0.006s
FAILED (failures=7)
```

## 验收命令逐条结果

| 命令 | 结果 |
|---|---|
| `python -B 程序/governance/check_structure.py --write-baseline --summary` | ok，`delta.added=[]`、`delta.removed=[]` |
| `python -B -m unittest tests.architecture.test_stage_doc_sections tests.architecture.test_structure -v` | 37/37 通过（OK），结构检查 delta 为空 |
| `python -B smoke_test.py --architecture` | 695/695 通过，失败集合为空 |
| `python -B smoke_test.py` | 9 项通过 0 失败 |
| `python -B scripts/dev.py claim` | 领到轮次 R4043 |

## 提交前自查（code-review 两条轴，会话内完成）

- 规范轴：阶段文档按对象检出未改写；README 只追加一句、登记表只插入一行，未整文件检出；baseline 由官方入口重写未手改；测试断言未修改，未改 structure.json targets 绕开 STR006。未发现问题。
- 契约轴：`problems(text, stage) -> list[str]`、两节全缺返回空列表、R1–R6、`REQUIRE_ALL = False`、stage_files() 复用、T1–T4 逐条对得上；targets 指向 `程序/docs/process/阶段文档写法.md`。未发现问题。

## 工作树状态

提交前 `git status --short`：`M architecture.md`、`M docs/README.md`、`M docs/records/工程文档登记表.md`、`M governance/structure-baseline.json`、`M governance/structure.json`，新增阶段文档、R3986 结果与证据、本结果文件、测试文件；stash 未动。
