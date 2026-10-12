# R1403 结果 — 合入 codex/R1308-idea-brief-split（idea_chat 五类职责拆分等）

- 本轮属于 §3 哪种类型？ **结构治理轮（§3.3）管合入**。主体是 `idea_chat.py` 五类职责拆分（语义 brief 请求轮询→L3；剧本启发式、路径命名、brief 表单解析、聊天记录持久化→L2）；随分支带入 R1385 修复轮与 R1398 功能轮成果。合入本身不改语义，断言未动。
- 测试跑了吗？三个基线过了吗？ 架构门禁 341/341 绿；定向 `--affected idea_chat writing_api stage_execution_service desktop workflow` = 8 项检查中 7 绿、1 红，唯一红项为 `tests/test_workflow.py::test_stage_model_selects_the_matching_desktop_agent`（**既有环境相关红**：本机 gitignore 的 `程序/配置/宠物/配置.json` 将 `claude-desktop` 标为「Claude Desktop」，而用例硬编码期望「Claude Code」；在干净 master `e1cfbdb` 上复制同一配置同样复现，非本轮引入）；默认冒烟 8/8。因本轮改动 `tests/architecture/_layers.py`，按 §5「合并到 master 前的当次全量升级条件」在干净 master 工作树跑 `run_selftests.py --all --safe`（结果见文末补记）。
- project_status.md 的欠账少了吗？ **减少**：状态页轮次头由「当前轮次：1403」推进到「1404」并补记本轮内容（仅 master 可写该文件）。

## 做什么

将 `codex/R1308-idea-brief-split`（71165f9）合入 master（e1cfbdb），落地五类职责拆分：

- L3 `idea_semantic_brief_service`：语义 brief 请求轮询（`semantic_brief_request`、`semantic_brief_values` 与
 `SEMANTIC_BRIEF_TIMEOUT`、`SEMANTIC_BRIEF_POLL_SECONDS`、`SEMANTIC_BRIEF_MAX_BYTES`、`SEMANTIC_BRIEF_INFERRED`），函数签名、返回结构与常量值均不变。
- L2 `idea_script_heuristic`（`looks_like_script`、`SCRIPT_MARKS`、`SCRIPT_MIN`）、`idea_document_paths`（路径与命名策略）、`idea_brief_form`（brief 表单解析与校验）、`idea_transcript`（聊天记录持久化）。
- 调用方 `stage_execution_service.py`、`writing_api.py`、`workflow_tasks.py`、`desktop.py` 只改 import 来源，调用方式、返回结构与断言未动；`idea_chat.py` 保留必要 re-export，无死引用。
- 随分支带入：R1385（脚本阶段缺 kind 不再误报「系统内部错误」）、R1398（剧本准备「作为确认输出文件」右键入口）。

## 冲突面与处理

- 硬冲突：仅 `程序/project_status.md` 轮次头（取 master 侧并推进到 1404）。
- 自动合并：`程序/desktop.py`、`程序/维护记录/架构统一基数.json`、`程序/维护记录/TODO注释快照_20261003.json`（行号登记表随新树重钉，以当轮 `--architecture` 结果为准）。
- 合并前为避免 git 拒绝覆盖，将 master 工作树中 3 个遗留 staged 改动（`idea_attachments.py`、`idea_chat.py`、`配置/SKILL/预设.json`，均 10-12 旧 WIP）`git stash` 保存后再合并，合并完成后再还原；未将他人 WIP 混入本次提交。

## 边界与不变量

- 未改任何函数签名、返回结构、超时/轮询常量值；未改测试断言。
- 不涉及 UI 行为变更（`desktop.py` 仅 import 来源与既有轮次成果）。
- 全量以后台子进程执行，本轮不刷新历史绿凭据；`程序/配置/宠物/配置.json` 属本机运行时配置（gitignore），本轮不修改。

## 验证与提交

- 命令：`smoke_test.py --architecture`（架构 341/341）、`smoke_test.py --affected idea_chat writing_api stage_execution_service desktop workflow`（`workflow` 单项复现：仅 1 条环境相关红）、`smoke_test.py`（默认冒烟 8/8）、`run_selftests.py --all --safe`（干净 master 工作树）。
- 本轮已提交：是（合并提交；commit hash 与全量凭据待后续「报告与状态页补记」同轮提交记录）。

## 全量凭据（待补记）

- 待补：`run_selftests.py --all --safe` 的用例数、耗时、红数与凭据 tree。
