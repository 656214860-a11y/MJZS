# R4211 · DOC-S02 补「接口」「交互」两节
<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "bf8defe6bdde0d35", "exit": 0, "failed": 0, "passed": 0, "round": 4211, "tests": "docs-only"} -->

本轮类型：功能轮（纯文档；需求设计裁决 N45：直接补节并提交，豁免先红后绿）。

## 做到哪一步

1. 核对工作树干净、HEAD=`6e687b94`、分支=`codex/doc-stages-a`。
2. 读 `docs/process/阶段文档写法.md`、`tests/architecture/test_stage_doc_sections.py`、S02 既有需求／设计，并核对 `script_contract`、`desktop_script_pages`、`desktop_script_edit_session`、`stage_flow`、`stage_parallel`、`stage_completion_service`、`skill_orchestrator` 入口。
3. 在 `docs/stages/S02_剧本结构.md` 文末（`## 设计` 之后）补 `## 接口`、`## 交互` 及固定八个三级小节。
4. 跑定向验收；先领到 R4208，提交时回执报「轮次已归属其他工作树、分支或命令参数：R4208.json」，改领 R4211 后重写本结果文件再提交。

## 补了哪几节及依据

- **接口／读入**：自然稿采用源、上下框文档清单、结构稿识别、三份 manifest、只读锁、依赖与并行配置、血缘可用性；依据 REQ-S02-01/02/03/21/23 与上列代码入口。
- **接口／写出**：`write_structured_script`、manifest、同源回收、编辑落盘、采用、删除进回收站、可选世界观／台词润色。
- **接口／完成判定与交接**：DEPENDS、CONFIG、完成核验、完成事件、交给 S03。
- **接口／对外调用**：默认本地规则；可选模型路径标 🟡；无硬外部依赖。
- **交互**：双框现状控件与状态；REQ-S02-37–44 目标项标 ⬜／🟡 并写来源。

## 待裁决／差异清单（只记录）

| 编号 | 说明 |
|---|---|
| IF-S02-08 | 五个 SKILL 的默认勾选与项目覆盖未逐项核对代码，标 ❓ |
| IF-S02-27 | `world_bible.md` 是否经统一发布器未核对，标 ❓ |
| IF-S02-61 | 可选模型路径计费与失败文案未逐 SKILL 核实，标 🟡 |
| UX-S02-13 | 与 REQ-S02-41 一致：文字尚未当制作要求带入；「/」技能命令本页仍无入口 |

未发现「文档已写死的现状」与「代码明显相反」且需改既有需求行的冲突；页面重做目标仍按未实现记账。

## 验收命令

```
..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage
```

- 退出码：`0`
- 结果行：`共 34 条用例…0 个文件有红`；`ALL TESTS PASSED`
- 未跑：默认冒烟、全量（卡面规定纯文档不跑冒烟）

## 提交

- 轮次：`4211`
- 提交说明：`R4211: DOC-S02 补接口交互两节`
- 文件：`程序/docs/stages/S02_剧本结构.md`、`程序/tasks_round/tasks_round_4211_result.md`
