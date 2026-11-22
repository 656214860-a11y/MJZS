# R4084 结果：文档入口层说法与分层登记对齐，写清两份启动错误日志
<!-- round-evidence: {"commit_base": "7ea1ddeb", "credential_hits": 0, "evidence_sha256": "0144f981422de9e3", "exit": 0, "failed": 0, "passed": 18, "round": 4084, "tests": "run_selftests.py -k agent_doc_budget doc_registry_migration"} -->

## 开头三问

- 本轮属于哪种类型：结构治理轮（只改文档），任务卡 B-L5-E1（《L5 入口层优化任务书》§4.2 的 L5-E1，缺陷 L5-B1、L5-B4），车道 `codex/l5-docs-align`，基线 `7ea1ddeb`。
- 测试跑了吗、三个基线：`run_selftests.py -k test_layers agent_doc_budget doc_registry_migration` 3 个文件 45 条全绿、`ALL TESTS PASSED`；`smoke_test.py --architecture` 696 条全绿、失败集合为空；默认冒烟按卡面未跑。
- 欠账少了吗：少了一处。任务书列的四处说法改了三处（`architecture.md` §3 的 L5 行、`docs/specs/01_架构与技术选型.md` 两行、`runbook.md` 的日志说法）；第四处 `docs/stages/S07_分镜定稿.md` 第 70 行的「L5/L4」不在本卡范围，由车道 `codex/doc-stages-b` 的 DOC-S07 那一轮一并改，本轮提交时它还留着。未新增欠账。

## 改了哪七行

| 文件:行 | 改成了什么 |
|---|---|
| `architecture.md:130` | L5 行成员改为 `app_shortcut`、`desktop_launcher`（与 `tests/architecture/_layers.py` 层值 5 逐名一致），写明用户双击的启动文件是根目录 `启动漫剧制作助手.pyw`（不在 `程序/` 分层登记、由 `test_dynamic_import_registry.py` 按第 5 层审计），`desktop_launcher` 是调试入口；职责格写明 `app` 在 L4、`app_icon` 在 L1 不属于本层 |
| `docs/specs/01_架构与技术选型.md:31` | L5 行成员改为「启动文件与启动适配器，只做启动、装配、退出收尾（成员见 `architecture.md` §3 的 L5 行）」，不再写 `app.py` |
| `docs/specs/01_架构与技术选型.md:40` | 代码块首行加注「（启动文件，按 L5 审计）」 |
| `docs/specs/01_架构与技术选型.md:41` | 删掉「`app.py`（L5）→ 」，只留 `└─ desktop.Desktop（L4，Tk 主线程）` |
| `runbook.md:25` | 句末补两份同名日志的归属：根目录那份由启动文件最外层异常处理写（主窗口出来前失败看它），`程序\logs\启动错误.log` 由 `infra/diagnostic_capture.py` 的 `record_crash` 写（运行期未处理错误看它） |
| `runbook.md:89` | 「启动即退」一行的 `启动错误.log` 前加「根目录 」 |
| `runbook.md:90` | 「点按钮没反应」第二格补「未处理的错误还会记到 `程序\logs\启动错误.log`」 |

`git diff --numstat`：`architecture.md` 1 增 1 删；`docs/specs/01_架构与技术选型.md` 3 增 3 删；`runbook.md` 3 增 3 删。行数不变。

## 改前命中与改后复核

- 改前 `git grep`（`L5.*app\.py`／`app\.py.*L5`／`入口层.*app\.py`，限 `*.md` 且排除 `tasks_round`、`维护记录`）正好三行：`architecture.md:130`、`docs/specs/01_架构与技术选型.md:31`、`docs/specs/01_架构与技术选型.md:41`。
- 改后同一命令无任何输出（退出码 1，无命中属正常）。

## 命令与退出码

| 命令（执行目录：`程序`） | 退出码 | 结果 |
|---|---|---|
| `git -c core.quotepath=false status --porcelain` / `git log -1 --format=%h`（改前） | 0 | 无输出；`7ea1ddeb` |
| `PY -B run_selftests.py -k test_layers agent_doc_budget doc_registry_migration` | 0 | `ALL TESTS PASSED`，3 个文件 45 条用例、0 个文件有红 |
| `PY -B smoke_test.py --architecture` | 0 | `Ran 696 tests`，`OK`，失败集合为空 |
| `PY -B scripts\dev.py claim` | 0 | 领到轮次 4084 |
| `PY -B scripts\dev.py commit -m "R4084: 文档入口层说法与分层登记对齐，写清两份启动错误日志" --tests agent_doc_budget doc_registry_migration --agent OpenCode architecture.md docs/specs/01_架构与技术选型.md runbook.md tasks_round/tasks_round_4084_result.md` | — | 本文件写完后由提交工具执行（含点名测试与架构门禁），证据文件 `tasks_round/evidence/R4084.json` 由工具生成 |

## 未覆盖项

- 没改任何 `.py`／`.pyw`，没改 `tests/architecture/_layers.py`，没改测试、文档预算与文档登记表。
- 没改 `docs/stages/S07_分镜定稿.md`；`architecture.md` 分层表的 L4、L1 两行没改，`app`、`app_icon` 的登记层只写在 L5 行里。
- 没跑全量自测，没跑不带参数的 `smoke_test.py`。
- 未 push、未 merge。
