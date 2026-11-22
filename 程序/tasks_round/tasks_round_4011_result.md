# R4011 结果：设计规格新增第 08 册「对话式交互与输出排版」（DOC-T1B）
<!-- round-evidence: {"commit_base": "e6f8dc49", "credential_hits": 0, "evidence_sha256": "ed68ab9d01670917", "exit": 0, "failed": 0, "passed": 0, "round": 4011, "tests": "docs-only"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-T1B，《工程文档细化任务书》§4.6）。未修改任何 `.py`／`.pyw` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收的两条架构门禁命令已跑，改动前后均绿——`python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure`：改动前 Ran 58 tests OK、改动后 Ran 58 tests OK，EXIT=0（test_structure 输出 `ok:true`、0 findings）；`python -B -m unittest tests.architecture.test_layers`：改动前 Ran 27 tests OK、改动后 Ran 27 tests OK，EXIT=0。
3. **欠账**：本轮无新欠账；既有欠账未触碰，不增减。

## 改动文件

- 新增 `docs/specs/08_对话式交互与输出排版.md`（12 章：范围与结论、消息种类、正文排版、流式输出、回话组织方式、可点选项、干活过程呈现、过程与回话区、长消息与对话记录、组件现状与去向、待实现清单、未决事项）
- `docs/specs/README.md`：§2 分册索引表加 08 行（仅一行，插在 07 与 09 之间）
- `docs/records/工程文档登记表.md`：加一行 `docs/specs/08_对话式交互与输出排版.md | L4 | 全局 | 权威 | R4011 | 执行 agent`
- `docs/records/对话需求追溯.md`：加一行记录 DOC-D8 六条决定与落点（来源格 `11-21 · 6c3dd20b，专题一`）
- 新增 `tasks_round/tasks_round_4011_result.md`（本文件）

## DOC-D8 → 章节对照表（验收要求）

| 决定 | 册内落点 |
|---|---|
| DOC-D8-1 第 2–13 页每页加「过程与回话区」，只记录不发模型，原有表格预览不变 | §1、§8（目标表＋13 行现状表）、§11、§12 Q1/Q2 |
| DOC-D8-2 改掉旧任务书「第 2 到 13 页不放对话气泡」；「共享事实、不共享对话」不变 | §1（正文说明＋表内 DOC-D8-2 行） |
| DOC-D8-3 回话统一「先结论、再分点、最后给下一步」，产物不受影响 | §1、§5、§11 |
| DOC-D8-4 聊天页四样复用到项目界面 | §1、§3（排版）、§5（组织方式）、§6（可点选项）、§7（过程呈现）、§11 |
| DOC-D8-5 复用现有排版模块、流式分段排版、表格两种候选、不引第三方库 | §1、§3、§4、§11、§12 Q3 |
| DOC-D8-6 不进产品的排版演示小窗口 | §1、§3、§11、§12 Q3 |

## 验收命令结果

| 命令 | 结果 |
|---|---|
| `PY -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_design_coverage tests.architecture.test_doc_registry_migration tests.architecture.test_agent_doc_budget tests.architecture.test_structure -v` | 改动前：58 项 OK；改动后：58 项 OK，EXIT=0 |
| `PY -B -m unittest tests.architecture.test_layers -v` | 改动前：27 项 OK；改动后：27 项 OK，EXIT=0 |
| `git diff --stat`（工作区相对 HEAD `e6f8dc49`） | 3 个已登记文件各 +1 行；另新增 08 册与本结果文件，均为任务卡允许文件。同车道更早的 DOC-T2B 提交（R4008）不计入本轮改动 |

## 待裁决清单（册内 ❓，收进 08 册 §12）

| 编号 | 事项 | 主控建议（建议，待确认） |
|---|---|---|
| Q1 | 「过程与回话区」位置、默认展开与否、收起时显示什么 | 底部输入框上方，可收起，默认收起，收起时只显示最新一条 |
| Q2 | 回话区记录保留、按页分开、加载条数 | 跟项目一直保存，按页分开，界面一次只加载最近 200 条 |
| Q3 | 表格显示方式（列对齐文字表格 vs 每行小卡片） | 等排版演示小窗口（DOC-T1D）做出来后再定 |
| Q4 | 复制原文还是所见 | 鼠标选中复制得到看到的文字；「复制」按钮得到原文 |
| Q5 | 长消息折叠阈值 | 超过 40 行自动折叠，点一下展开 |
| Q6 | 可点选项的数量上限、反馈形式、能否改选；`FormDialog` 去留 | 随 `build_choice_card` 接线时一并定 |
| Q7 | 已建未接线的「继续生成／排队」机制是否启用 | 由实现轮决定 |

## 未核实事项

- 本轮抽样实读核对：`ui/skill_note_render.py` 的 `parse`（:92）与 `apply`（:239）、`orchestrator/idea_chat_controller.py` 的折叠阈值常量（:11-12）、`desktop_shared_send.py` 的「暂无对话入口」提示原文（:138）、`domain/idea_transcript.py` 的 `创意对话/对话.json`（:30-31）、`ui/skill_panel_support.py` 的 `markdown_document`（:220），均与盘点报告对应事实一致。
- 册内其余标 ✅／🟡 的现状条目直接引用盘点报告 F 编号，未逐条重读代码；盘点报告每条事实自带 `文件:行号` 证据。

## 复用情况（任务书复用要求）

- 分册结构沿用 01–07 册既有「`# NN 名称`＋`## N. 名称`」格式；状态记号沿用阶段文件与 §4.1 的 ✅/🟡/⬜/❓。
- 界面规范、对话记录目录位置不重复，直接链到 05 册与 04 册 §2。
- 未新增第三方依赖与文档工具。

## 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R4011: 设计规格新增第 08 册对话式交互与输出排版" --agent Devin docs/specs/08_对话式交互与输出排版.md docs/specs/README.md docs/records/工程文档登记表.md docs/records/对话需求追溯.md tasks_round/tasks_round_4011_result.md`
- commit hash：（提交后补记）
