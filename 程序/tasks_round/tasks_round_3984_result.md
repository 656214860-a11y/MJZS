# tasks_round_3984_result — 错误代码统一任务书 EC-1：登记两个启动类代码，新增统一出口 user_text()
<!-- round-evidence: {"commit_base": "81577d36", "credential_hits": 0, "evidence_sha256": "bacfe33c1dc5d311", "exit": 0, "failed": 0, "passed": 28, "round": 3984, "tests": "run_selftests.py -k error_codes"} -->

## 三问

1. **本轮属于哪种类型**：契约轮（AGENTS.md §3.4）：只改 `contract/` 内一个模块与配套测试/文档，不动 L1 及以上。
2. **测试跑了吗、三个基线各是什么结果**：跑了。默认冒烟 9/9 通过；架构门禁 685 条用例全过、失败集合为空；全量未运行（任务书 §4.0-7 禁止执行者跑全量，由主控合入后补跑，以 `full-safe-receipts.json` 为准）。
3. **欠账少了吗**：少了。EC-B4（启动失败没有错误代码）本轮登记 `E-START-FAILED`/`E-START-SELFCHECK` 收口；EC-B1/EC-B2 的统一出口 `user_text()` 已立，待 EC-2/EC-3 接线。无新增欠账。

## 改动文件

- `contract/error_codes.py`：`_ITEMS` 末尾按卡面原文新增 `E-START-FAILED`（FATAL，不重试）、`E-START-SELFCHECK`（FATAL，不重试），登记总数 24→26；新增 `user_text(error, *, fallback='E-UNKNOWN')`（R1 已登记 `code` → `describe(code)`、中文说明非空接 `：说明`；R2 系统 `OSError` errno 非 None → `FileNotFoundError` 归 `E-FILE-NOT-FOUND`、其余归 `fallback`；R3 中文说明原样并一行；R4 其余归 `describe(fallback)`；纯函数、任何输入不抛异常、不调 `classify()`、不引入 contract/ 以外模块）。既有 24 码与 `lookup/describe/classify/from_http_result/code_data/code_of/analyze/TEXT_RULES` 一字未动。
- `tests/test_error_codes.py`：金表加两行（T1）；新增 `UserTextTests` 9 条用例（T2–T9 全覆盖，另补一条「errno 非 None 的非 FileNotFoundError 系统错误」用例——`error_codes.py` 棘轮下限 100%，没有它 R2 else 分支覆盖不到，基线重测只能 16/17）。
- `docs/specs/02_接口与详细设计.md`：§5 错误码条目下补两个新代码含义、`user_text()` 四规则、「界面显示失败只经 `user_text()`」；未新增需求编号（卡面 S1：若门禁要求编号才停下报告——`test_agent_doc_budget`/`test_doc_registry_migration` 实测全过，无需编号）。
- `architecture.md`：R3984 条目（照 R3407 写法）。**插位说明**：按惯例条目本应追加在 R3721 之后，但范围门禁试合并显示该位置与 `archive/foundation-c8-updater`、`archive/foundation-integration-final` 重写分层表区域的未合入改动真实冲突；按门禁提示「错开改动位置」，条目改插在 R3701 与 R3721 之间（时序仅局部倒置），对两条车道试合并零冲突标记。
- `tasks_round/tasks_round_3984_result.md`：本文件。

**已刷新但未提交**：`维护记录/分支覆盖率基线.json`。`user_text` 使 `error_codes.py` 决策点 11→17，`test_branch_coverage_floor` 要求基线值与当前 AST 相等（「须真实重测」）。用 `scripts/branch_coverage_report.py` 按基线登记的同一批 102 个定向目标在隐藏桌面重测（全绿，`error_codes` 17/17=100%）后工具写入，本地验收 `--architecture` 685 条全过以此为准。但该生成台账与 6 条活跃车道（archive/foundation-c8-updater、archive/foundation-integration-final、codex/l2-maturity-takeover、codex/req-app-02-takeover、codex/retire-builtin-prerequisite、codex/wip-r3764）的未合入重测结果试合并真实冲突，范围门禁拒绝其入库且无法错开位置；台账又不在卡面「允许修改文件」清单内，故已还原不提交。**遗留影响如实标注**：本分支头 `--architecture` 将因 `error_codes.py` 基线 11≠实测 17 红 1 条，待合并轮按既有惯例在合并树实测重写基线（先例：R3966「分支覆盖率基线取主干后合并树实测重写」、R3412 同轮重测）。

## 改前失败输出（先红）

`PY -B -m unittest tests.test_error_codes -v`：`FAILED (failures=1, errors=11)`，关键输出：

```
FAIL: test_golden_table_code_severity_retryable
AssertionError: Items in the second set but not the first:
'E-START-SELFCHECK'
'E-START-FAILED'

ERROR: test_infra_error_with_code_uses_describe（等 8 条 UserTextTests，逐条）
AttributeError: module 'contract.error_codes' has no attribute 'user_text'
```

## 验收命令逐条结果

| 命令 | 结果 |
| --- | --- |
| `PY -B -m unittest tests.test_error_codes -v` | 28 条全过（改前 1 fail + 11 errors） |
| `PY -B -m unittest tests.architecture.test_contract_purity tests.architecture.test_infra_errors_boundary tests.architecture.test_layers -v` | 全过（连同下条共 58 条 OK） |
| `PY -B smoke_test.py` | 通过：9 项 / 失败：0 项 |
| `PY -B smoke_test.py --affected error_codes` | 选中 `test_error_codes` 28 条、0 个文件有红；通过：10 项 / 失败：0 项 |
| `PY -B smoke_test.py --architecture` | 685 条全过（`OK` / `✅ 架构治理测试`），失败集合为空——以重测后的分支覆盖率基线为准（该台账未提交，见「改动文件」节说明） |
| `PY -B -m unittest tests.architecture.test_agent_doc_budget tests.architecture.test_doc_registry_migration -v` | 18 条全过 |

## 中途遇到的环境问题与处置

- 首轮 `--architecture` 红 1 条：`test_branch_coverage_floor` 报 `error_codes.py 基线决策点 11 != 17` → 按门禁口径重跑工具刷新基线（见上「改动文件」说明）。
- 首次基线重测 `tests_ok=false` 未写入：`test_script_contract.AuditTests.test_the_audit_covers_every_script_skill` 环境性失败——`skills/01 剧本准备SKILL/` 下 5 个嵌套 gitlink（剧本锻造/影视剧本写作技能/短剧工业化流水线/短剧编剧搭子/编剧技能集）在工作树是空目录占位。按 R3385 结果文件的既有处置从主工作区拷入内容（gitlink 边界内不入库、`git status` 不体现），该用例转绿后重测 102 目标全绿、基线写入。此失败与本轮改动无关，主工作区同样缺内容时同样红，属环境欠账（历史结果文件 R2231/R2497/R2832 均记过同一条）。
- 拷贝时因命令引号问题生成过一个 stray 目录 `程序/skills/01 剧本准备SKILL$d`（误入 gitlink 同级），已删除，`git status --short` 干净。

## 提交前自查（code-review 两轴，merge-base `81577d36` 起全部改动，会话内完成未起子代理）

**Spec（对 EC-1 卡面）**：两个新代码字段逐字一致并置于 `_ITEMS` 末尾；`user_text` 签名、`R1–R4` 顺序命中、R2 不给系统原文、R3 并一行、R4 fallback 未登记归 `E-UNKNOWN`、纯函数不抛异常、不调 `classify()`、不引入 `infra_errors`（只看 `code` 属性）全部符合；T1–T9 用例齐且先红后绿；文档先行完成；禁止项未触碰（未改 contract/ 以外 .py、未动 24 码字段与「10–30」断言、未跑全量）。一处实现裁量：R1 追加的「说明」与 R3 同口径做了并一行处理（卡面只写「`describe(code) + '：' + 说明`」，未限定是否规整空白；状态栏单行显示需要，T3 口径不受影响）。一个范围说明：`维护记录/分支覆盖率基线.json` 不在卡面清单内，但 `--architecture` 验收以它为准且工具禁止手写；本地已按 R3412 先例真实重测取证，因范围门禁对 6 条活跃车道试合并真实冲突而未入库（见「改动文件」节），合并轮实测重写。
**Standards（对本仓规范）**：分层未动（L0 内改动、`contract/error_codes.py` 无新增 import）；命名/文档字符串风格与 `_mark_hit`/`_status_text` 一致；测试断言行为而非源码字符串、含 Tk 无关项；未删/改任何既有断言；临时文件均在 `$TEMP`，未污染 `程序/`。无新增第三方依赖。找现成记录：`describe()`/`lookup()`/金表/`branch_coverage_report.py`/`gui_hidden.py` 全部复用，未自写平行实现。

## 其他

- 未运行全量（`--all`/`--safe`）：按任务书留给主控合入时补跑。
- 未推送、未合并、未登记合并请求；`tasks_round/evidence/R3984.json` 由 `dev.py commit` 自动生成。
