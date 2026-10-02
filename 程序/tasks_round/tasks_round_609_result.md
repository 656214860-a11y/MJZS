# R609｜结构治理轮（子场景：只读诊断）｜架构门禁登记与基线脱节核验

## A. 目标

核验 `tests/architecture/test_legacy_facade_manifest.py` 是否实际纳入架构门禁，以及 `AGENTS.md` 的门禁清单和基线是否与仓库事实一致。

## B. 范围

只读检查 `AGENTS.md`、`project_status.md`、`smoke_test.py`、目标测试和既有 R567 结果；未修改 `.py`、测试、台账或用户项目数据。

## C. 实际收集路径

- `smoke_test.py:632-644` 的 `--architecture` 对 `tests/architecture/` 执行 `unittest.defaultTestLoader.discover(..., pattern='test_*.py')`。
- 因此目标文件名满足发现模式，会被实际架构门禁自动收集；它不需要另行在 `smoke_test.py` 建映射。

## D. 目标测试事实

- 文件存在：`tests/architecture/test_legacy_facade_manifest.py`。
- 定义 `LegacyFacadeManifestTests`，含 3 个检查：公共兼容入口与清单一一对应、声明调用方等于生产 AST 引用、淘汰日尚未到期。
- 它守护的是 P3-1 建立的 `legacy_compat.FACADE_MANIFEST`，而非普通功能测试。

## E. 清单脱节事实

| 项目 | AGENTS.md 当前声明 | 磁盘/代码事实 | 结论 |
| --- | --- | --- | --- |
| 目标测试登记 | 未出现 `test_legacy_facade_manifest.py` | 文件存在，且符合自动发现模式 | 漏登记。 |
| 架构测试文件数 | 55 个（`AGENTS.md:352`） | 56 个 `tests/architecture/test_*.py` 文件 | 数量少 1，正好对应漏登记文件。 |
| 架构检查基线 | 98/98（`AGENTS.md:350,352`） | R567 记录该测试新增后实测 101/101 | 当前入口基线为陈旧记录，不能据此断言今天仍为 101/101。 |

## F. 历史证据

- `tasks_round/tasks_round_567_result.md` 明确记录：该测试为 P3-1 新增架构门禁，含三项检查，且当轮 `smoke_test.py --architecture` 为 101/101。
- `project_status.md:91` 也记录 R567 的三项 facade 清单门禁及 101/101。
- 这证明缺口发生在后续 AGENTS 架构门禁清单/基线维护，没有证据表明测试未被纳入实际发现。

## G. 根因

架构测试采用“目录自动发现”，而 `AGENTS.md` 采用人工枚举的静态清单。R567 新增测试后，历史结果和状态摘要记录了它，但 AGENTS 第 5 节没有同步补入该文件名及对应基线，形成文档与执行收集脱节。

## H. 影响

- 执行层：低。该测试仍会被 `--architecture` 收集，静态清单遗漏不会使其失效。
- 治理层：中。Reviewer 依据 AGENTS 清单无法看见 facade 兼容入口门禁，且 98/98 与 R567 的 101/101 造成基线口径混乱。
- 风险边界：本轮未运行测试，故不把历史 101/101 伪报为当前实测结果。

## I. 不应做的事

- 不应给 `smoke_test.py` 增加该测试的专用映射：当前目录发现已覆盖它，重复入口会制造两套收集规则。
- 不应修改 `test_legacy_facade_manifest.py`：诊断未发现测试逻辑或发现机制缺陷。

## J. 整改路线

建议下一次**结构治理轮（子场景：执行）**做一个纯文档台账收口：

1. 在 `AGENTS.md` 第 5 节“依赖与平台边界”旁新增“历史兼容门面”条目，登记 `test_legacy_facade_manifest.py`。
2. 将“55 个测试文件”更新为 56 个；将“98 个检查 / 98/98”改为以一次当轮 `python smoke_test.py --architecture` 的实测总数为准。
3. 在 `project_status.md` 的当前状态补一条简短事实：R567 已新增该门禁，后续基线以复测值统一；不得把未复测的历史数字写成当前结果。
4. 结果文件记录清单、文件数和实测数三者一致。

## K. 测试迁移计划

无需测试迁移：文件已位于唯一规定目录 `tests/architecture/`，且发现规则已正确收集。执行轮只需运行 `python smoke_test.py --architecture` 复核；不移动、不重命名、不改断言。

## L. 轮次连续性观察

`project_status.md:3` 仍写“当前轮次：608 待执行（已完成至 R607）”，但 R608 结果文件已存在。这是状态台账滞后；本轮只读诊断不覆盖状态文件，留待上述执行/状态接续轮按轮次规则统一校正。

## M. 自审

通过。满足只读诊断边界：未改任何 `.py`、未改测试逻辑、未执行会改变状态的操作；报告给出发现路径、具体漏项、基线证据、影响和可独立执行的整改项。
