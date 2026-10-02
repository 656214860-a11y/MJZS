# R565｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`tasks_round/tasks_round_547_result.md` J 节 P2-4——为非剧本阶段建立阶段级上下文摘要策略及可观测预算，避免不同模型调用重复携带全量项目文本。
- 应用代码只改动三个模块：`workflow_context.py`、`workflow_context_budget.py`、`desktop.py`。未改分层、对外契约、模型配置、阶段状态机或用户项目数据，未增加用户可见功能。

## 完成结果

- `workflow_context.request_instruction()` 现显式区分策略：剧本准备（`writing`／`script`／`剧本准备`）保留完整项目索引；其余阶段使用项目续接摘要，包含阶段名、成果计数、持久化 `data/项目接续.json` 路径与按需读取约束，不内联项目正文。
- 非剧本摘要路径仍先刷新原有项目进度文件，确保模型可获得同一份最新成果索引；任务、SKILL、阶段输出契约和用户输入仍按既有流程拼接，未裁剪本次具体任务内容。
- `workflow_context_budget.prepare_request_context()` 在既有重复大段去重与 96,000 字符硬上限之上，返回安全预算元数据：`stage`、`strategy`、`characters`、`limit`、`remaining`。不保存提示词、项目正文、模型回复或密钥。
- `Desktop.open_flow_agent()` 对最终初始/续接提示统一预检，并把两份预算元数据写入已有 Agent 发送收据。不同模型或会话续接可据此审计上下文规模，续接仍保持短摘要策略。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `workflow_context.py` | 增加非剧本阶段摘要／剧本完整索引策略选择。 |
| `workflow_context_budget.py` | 增加无正文预算观测原语，保留 `ensure_request_context()` 原接口。 |
| `desktop.py` | 在既有 Agent 派发前应用策略与预算预检，并写入既有收据。 |
| `tests/test_context.py` | 覆盖非剧本摘要、进度文件刷新与剧本完整索引保留。 |
| `tests/test_workflow.py` | 覆盖预算元数据不含提示词正文。 |
| `project_status.md`、`architecture.md` | 同步轮次、债务与架构边界。 |

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_context tests.test_workflow.WorkflowContextBudgetTests`：24/24 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected workflow_context workflow_context_budget desktop`：9 项通过、0 项失败；定向自检 7 条通过。增量台账因环境对 `维护记录` 临时文件的既有权限限制未写入，不影响结论。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py`：默认冒烟 8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture`：98/98 通过，无新增红点。

## 债务状态与自审

- P2-4 完成；R182 已拆分债务由 5 项减至 4 项。P0-3 的二进制成果发布/分层阻塞不受本轮影响。
- 预算元数据仅使用标量，不复制请求正文；现有 96,000 字符拒绝阈值、重复段去重、持久化进度文件、首次任务与会话续接的既有接口均保留。
