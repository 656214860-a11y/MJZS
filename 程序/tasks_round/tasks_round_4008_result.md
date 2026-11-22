# R4008 结果：设计规格新增第 09 册「资产数据生命周期」（DOC-T2B）
<!-- round-evidence: {"commit_base": "95c9f7b7", "credential_hits": 0, "evidence_sha256": "62fd6903c5d56814", "exit": 0, "failed": 0, "passed": 0, "round": 4008, "tests": "docs-only"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-T2B，《工程文档细化任务书》§4.8）。未修改任何 `.py`／`.pyw` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收的两条架构门禁命令已跑，改动前后均绿——`python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure`：Ran 58 tests，OK，EXIT=0（test_structure 输出 `ok:true`、0 findings）；`python -B -m unittest tests.architecture.test_layers`：Ran 27 tests，OK，EXIT=0。
3. **欠账**：本轮无新欠账；既有欠账未触碰，不增减。

## 改动文件

- 新增 `docs/specs/09_资产数据生命周期.md`（13 章：范围与结论、资产身份、四种形态、字段表、命名目录、版本记录、状态流转、过期判定、展示、场景与道具、来源关系与产物索引、待实现清单、未决事项）
- `docs/specs/README.md`：§2 分册索引表加 09 行（仅一行）
- `docs/records/工程文档登记表.md`：加一行 `docs/specs/09_资产数据生命周期.md | L0,L1,L2,L4 | 全局 | 权威 | R4008 | 执行 agent`
- `docs/records/对话需求追溯.md`：加一行记录 DOC-D9 四条决定与落点（来源格 `11-21 · 6c3dd20b，专题二`）
- 新增 `tasks_round/tasks_round_4008_result.md`（本文件）

## DOC-D9 → 章节对照表（验收要求）

| 决定 | 册内落点 |
|---|---|
| DOC-D9-1 镜头视频可从角色查到＋角色自己的视频资产 | §1、§3（目标行）、§9（「使用情况」「动态参考」行）、§12、§13 Q4 |
| DOC-D9-2 「演变记录」「使用情况」两块，每环标「最新」「过期」「缺失」 | §1、§9（目标表）、§12 |
| DOC-D9-3 角色改动后首帧与视频只标过期、列镜头、用户决定重做 | §1、§8、§12 |
| DOC-D9-4 文字与图片记版本、可对比、可回退、采用留存/未采用回收 | §1、§6、§12、§13 Q3 |

## 验收命令结果

| 命令 | 结果 |
|---|---|
| `PY -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure -v` | 改动前：58 项 OK；改动后：58 项 OK，EXIT=0 |
| `PY -B -m unittest tests.architecture.test_layers -v` | 改动前：27 项 OK；改动后：27 项 OK，EXIT=0 |
| `git diff --stat`（相对分叉点 `95c9f7b7`） | 3 个文件各 +1 行；另新增 09 册与本结果文件，均为任务卡允许文件 |

## 待裁决清单（册内 ❓，收进 09 册 §13）

| 编号 | 事项 | 主控建议（建议，待确认） |
|---|---|---|
| Q1 | 生成的图、导入的图、历史版本的命名统一规则与入库冲突策略 | 统一成「新图成为当前图，旧图进历史版本」 |
| Q2 | 场景、道具是否和角色用同一套版本与过期规则 | 用同一套 |
| Q3 | 历史版本清理入口与数量上限 | 不设上限，在现有存储清理入口列出占用，可清掉没被采用过的版本 |
| Q4 | 角色自己的视频资产的展示块、生成与消费阶段 | 详情页正典板下新增「动态参考」；S05 生成或导入；S10 可选作输入 |
| Q5 | 哪些改动算「过期」 | 只有影响画面的改动算（外观要求、提示词、参考图、状态变体、图片本身）；改名和别名不算 |
| Q6 | 「设计上不需要资产合并」是否成立 | 未核实，无建议 |
| Q7 | 资产图片要不要进产物索引／来源账本 | 未裁决，无建议 |

## 未核实事项

- 资产合并：程序内无合并函数，但「设计上不需要」未核实（盘点报告 F11，册内 Q6）。
- 除 `keyframe_evidence.source_evidence` 的元数据 digest 覆盖范围（`domain/keyframe_evidence.py:109-112`，已实读）外，册内其余现状条目直接引用盘点报告 F 编号，未逐条重读代码。

## 复用情况（任务书复用要求）

- 分册结构沿用 01–07 册既有「`# NN 名称`＋`## N. 名称`」格式；状态记号沿用阶段文件与 §4.1 的 ✅/🟡/⬜/❓。
- 目录结构、原子发布、保留策略不重复，直接链到 04 册与 `docs/process/存储盘点与保留.md`。
- 未新增第三方依赖与文档工具。

## 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R4008: 设计规格新增第 09 册资产数据生命周期" --agent Devin docs/specs/09_资产数据生命周期.md docs/specs/README.md docs/records/工程文档登记表.md docs/records/对话需求追溯.md tasks_round/tasks_round_4008_result.md`
- commit hash：（提交后补记）
