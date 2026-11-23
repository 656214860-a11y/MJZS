# R4196 NAMING-INVENTORY 产物命名盘点（只读诊断／文档轮）
<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "72c1e7f3c81a5b8c", "exit": 0, "failed": 0, "passed": 0, "round": 4196, "tests": "docs-only"} -->

## 开头三问（§7）

- （一）本轮属于哪种类型：只读诊断＋设计文档轮（§3.5 语义；卡面为纯文档卡，不改任何 `.py`、不改 runbook 与 AGENTS.md）。卡号 NAMING-INVENTORY，波次 W2，车道 `codex/naming-inventory`，基准 `6e687b94`。目标：盘点应用写出的每一类文件现在叫什么名字，统一成「类型＋provider＋年月日」要改哪些地方、哪些得用户先定。
- （二）测试跑了吗、三个基线：跑了卡面指定的文档门禁。`run_selftests.py -k agent_doc_budget requirement_traceability design_coverage` 退出码 0，「共 24 条用例；0 个文件有红」「ALL TESTS PASSED」。冒烟与全量按卡面「纯文档轮，不跑产品测试」未跑；三个基线数本轮不适用（无源码改动）。
- （三）欠账少了吗：无欠账增减；本轮不产生代码欠账，产出为盘点＋设计文档一份，待用户裁决题单移交需求设计。

## 领号

- 命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`（工作目录 `程序`）。
- 结果：轮次号 **4196**（上一会话已领，本线程未重复领号，避免烧号；若提交时被判归属冲突再重新领号）。

## 已完成

- 通读 `程序/AGENTS.md`、`runbook.md` 相关节、既有结果文件格式（参照 R4188/R4194）。
- 只读盘点命名权威与全部产物类别，产出 **`程序/docs/process/产物命名盘点.md`**（新建）：
  - 命名权威总览（`contract/file_naming.py` 为唯一命名中心；`generate_name()`/`TEMPLATES` 新方案零生产调用，现行全走 `generate_existing()`/`EXISTING_TEMPLATES`）。
  - 盘点表覆盖 **5 大类 30+ 种文件**：剧本/文档、分镜（工作稿/提示稿/历史/定稿目录/包内清单/别名表）、媒体（首帧导入与生成位、资产图三条入库路＋参考图、Comfy/Seedream 批次、音频导入与固定清单、Animatic、字幕导出、分镜视频与成片）、清单/索引/台账（file_index、成果确认、批次状态、续跑台账、来源关系、回收站批次）、程序目录内文件（`private/.env`、`素材库.json`，标注不建议纳入）。
  - 「从文件名反解信息」逐个列出代码位置：`tts_api.audio_kind()` 前缀反解、`idea_attachments._ARCHIVE_NAME` 四段反解、`asset_generated_import_service` 的 `(CHAR|LOC|PROP)` 正则、`storyboard_catalog_service.file_order/default_source`、`file_naming.parse/legacy_scheme`、`storyboard_paths.is_final_dir`、file_index 忽略名单等。
  - 设计稿：`{类型}_{provider}_{YYYYMMDD}_{序号}_{可读名}.{后缀}`；同日冲突 `_2`/`_3`（`dated_path` 先例）；中文骨架＋ASCII 元数据段；旧名只读新名新写、读取方双认清单；三期分批建议（字幕/交接/Animatic/音频导入先行，分镜与首帧次之，剧本名/附件名/帧路径/固定名暂缓）。
  - 待用户裁决 7 题（Q1–Q7），每题带推荐与改选条件，含卡面点名的 provider 进名与否、旧项目改名政策、provider 语义、冲突策略、中文保留度、清单固定名、分隔符/类型词表。
- 每条现状均带 `文件:行号` 出处；未逐行核实处在文末「未核实项」如实标注；示例项目名用虚构名「星河」，未扫描用户真实项目目录。

## 差异文件（本轮新增，均在允许清单内）

- `程序/docs/process/产物命名盘点.md`（盘点＋设计稿正文）
- `程序/tasks_round/tasks_round_4196_result.md`（本文件）
- `程序/tasks_round/evidence/R4196.json`（由 `dev.py commit` 生成）

## 卡面要求的各项

- 盘点到的文件类型数：**5 大类、30+ 种**（盘点文档 §3 表格逐行）。
- 读取方数：文档 §4 汇总 **6 类硬约束**＋逐行「受影响读取方」列；可计数的命名反解点 **10+ 处**（文档 §4.3）。
- 待用户题单：**7 题**（文档 §6，Q1 provider 是否进文件名、Q2 旧项目是否一次性改名、Q3 provider 取值语义、Q4 同日冲突策略、Q5 中文保留度、Q6 清单/台账固定名是否跟随、Q7 分隔符与类型词表）。
- 未验证项：文档 §7 列 6 条（参考图 attach 实现细节、首帧服务扫描面、历史目录时间戳解析、cloud_video 工作集名生成函数、09 册其余 Q 项、成果确认内其余文件名）。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k agent_doc_budget requirement_traceability design_coverage`（工作目录 `程序`） | 退出码 0；「共 24 条用例，1.4 秒；0 个文件有红」「ALL TESTS PASSED」 |

输出尾部原文：

```
  architecture.test_design_coverage     8 条     0.1 秒
  architecture.test_agent_doc_budget    11 条     0.2 秒
  architecture.test_requirement_traceability     5 条     0.5 秒
共 24 条用例，1.4 秒；0 个文件有红
ALL TESTS PASSED
```

## 提交

- 本文件与盘点文档由 `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4196: NAMING-INVENTORY 产物命名盘点文档"` 一并提交；commit hash 与凭据见 `tasks_round/evidence/R4196.json` 及提交输出。

## 如实说明

- 本卡为续做：上一会话已完成盘点文档与本结果文件初稿、已领 4196，但文档门禁命令两次被工具层拒绝（当时误加引号与 `cd &&`，不符合字面前缀规则），未跑门禁、未提交。本线程按卡面原样命令（无引号、无 `cd &&`、workdir 设为 `程序`）重跑门禁通过后更新本文件并提交。
- 上一会话被拒命令原文（存档）：`cd "D:\漫剧制作助手\.agents\worktrees\naming-inventory\程序" && "..\..\..\..\运行环境\Python\python.exe" -B run_selftests.py -k agent_doc_budget requirement_traceability design_coverage`；及带引号的裸命令 `"..\..\..\..\运行环境\Python\python.exe" -B run_selftests.py -k agent_doc_budget requirement_traceability design_coverage`。两次均 `Tool execution was rejected`。
- 本线程被拒命令：无。未使用 git 任何命令；未跑卡面以外的 Python 命令；未打开 `private`、`.env`、`outputs`、`logs` 与用户项目目录。

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（卡面明确纯文档轮不跑产品测试）。
- 盘点文档 §7 列出的 6 条未核实项原样保留，移交需求设计裁决时一并考虑。
