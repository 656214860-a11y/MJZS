# R4206 结果：DOC-PREVIEW-GUIDE 合入前预览说明（纯文档轮）
<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "bbc54074c303a01f", "exit": 0, "failed": 0, "passed": 0, "round": 4206, "tests": "docs-only"} -->

## 开头三问

- （一）本轮属于哪种类型：纯文档轮（§3.1 功能轮口径下的文档交付；不涉及 REQ/DES）。只新建用户指南一篇与本结果文件；不改任何 `.py`、不改 runbook、AGENTS.md、工程文档登记表。车道 `codex/doc-preview-guide`，基点 `6e687b94`。
- （二）测试跑了吗、三个基线：跑了卡面指定的文档门禁 `run_selftests.py -k agent_doc_budget requirement_traceability design_coverage`（退出码与输出见下）；另按卡面用 `dev.py preview --print-only` 核对命令原文（exit 0）。未跑 smoke／`--architecture`／全量（纯文档轮）。
- （三）欠账少了吗：无新增流程欠账；但新文档未能同轮登记进工程文档登记表（超出允许文件，见「如实说明」一），由 `test_doc_registry_migration` 口径看是新增登记欠账，需总控裁定。

## 改了哪些文件

- `程序/docs/guides/合入前预览说明.md`（新建）：一页用户向说明，覆盖卡面六项内容要求。
- `程序/tasks_round/tasks_round_4206_result.md`：本文件。
- `程序/tasks_round/evidence/R4206.json`：由 `dev.py commit` 自动生成。

## 依据与核对

- 唯一依据：`程序/runbook.md` §12「合入前看效果（R4099）」（L204–213）。文档中「在哪里运行／命令／能看到什么／--reset 场景／不能拿真实项目预览」均出自该节。
- 参数语义另核对实现：`scripts/dev.py:41`（preview 子命令）与 `:62`（参数原样转发）；`scripts/preview_app.py` 全文——argparse `--data/--reset/--print-only`（L347–350）、缺省数据目录 `manju-preview\<分支名>`（L89–91）、示例项目（L205–217）、车道校验与拒绝文案（L111–114、362–364）、`--print-only` 不开窗口（L367–368）、数据出界拒绝并提示 `--reset`（L165–184）、`--reset` 只删带标记目录（L354–361）、真实项目不可预览的原因（L25–26）、用户级目录／注册表／关窗清理三层隔离（L224–311）。
- 「常见被拒绝」表中「数据目录不能放在代码仓库里」「不是预览工具建的目录」两条出自 preview_app.py 报错原文（L120–130），runbook 未逐条写，已如实标注来源在此。
- 现状核对：`使用说明.txt:4` 的「预览」指压缩包预览，与本工具无关，未动；仓库根 `使用说明.md`、`开发者工具\AI开发流程\README.md`、`docs/guides` 原无本工具说明（卡面已核对，本轮 grep 复核 guides 目录仅 `编剧功能说明.md` 一篇）。

## 命令与结果

工作目录均为车道 `程序\`，命令以 `..\..\..\..\运行环境\Python\python.exe -B` 开头（车道工作树无自带 `运行环境`，用主工作区同一解释器）。

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 领到轮次 4206，exit 0 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py preview --print-only` | exit 0；输出：`[预览] 数据目录 C:\Users\LAIBIAO\AppData\Local\Temp\manju-preview\codex-doc-preview-guide；项目 C:\Users\LAIBIAO\AppData\Local\Temp\manju-preview\codex-doc-preview-guide\downloads\项目\预览示例项目_20261123` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k agent_doc_budget requirement_traceability design_coverage` | 见下方「文档门禁」 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4206: DOC-PREVIEW-GUIDE 合入前预览说明文档" <文件>` | 见下方「提交」 |

## 如实说明

- （一）**登记表缺口（待总控裁定）**：`doc_registry.py:31` 的 SCOPES 含 `docs/**/*.md`，`collect_errors`（L120–121）对「存在但未登记」报错；`tests/architecture/test_doc_registry_migration.py:24-27` 据此断言全登记。本卡允许文件不含 `docs/records/工程文档登记表.md`，故新指南未登记——合入车道跑架构门禁时该测试预计报 `存在但未登记：docs/guides/合入前预览说明.md`（未实跑，结论来自读源码）。`文档导航.md:54` 的指南链接同样未加。参照 `工程文档登记表.md:75` 编剧功能说明行格式补一行即可消除；是否由总控扩权补登或另开卡，请裁定。
- （二）未打开预览窗口：runbook §12 末句规定只有用户提出要看时才由验收窗口或用户本人运行；本轮只用 `--print-only` 核对命令原文（该分支不做车道校验，preview_app.py:362）。
- （三）`--print-only` 在本车道实际建出了 `manju-preview\codex-doc-preview-guide` 数据目录与示例项目（系统临时目录，非仓库文件）。

## 未验证

- 未真开预览窗口：标题前缀、隔离效果、窗口交互均按 preview_app.py 代码核对，未实测。
- `test_doc_registry_migration` 未跑（卡面未授权该 `-k`）；登记缺口结论来自源码阅读。
- `git diff --check` 未跑（卡面说明由验收复跑）。

## 未覆盖项

- 工程文档登记表、文档导航未更新（超出允许文件清单）。
- 未跑 smoke、`--architecture`、全量自测；未 push、未 merge、未动 project_status.md／AGENTS.md／产品代码／测试。
