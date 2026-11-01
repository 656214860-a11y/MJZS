# R1338：O14 会话、请求身份、上下文与项目共享成果分开说明

类型：功能轮（§3.1），承接 R1267 清单 O14（O01—O13 已完成）。中央轮次 1338。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 131/131（`idea_chat`）、关联 全绿（`ui_edges idea_inline_brief writing`）、架构相关全绿（`todo_comment_snapshot unification_ratchet layers writing_api_json_boundary writing_publication_boundary no_circular_import import_error_boundaries dynamic_import_registry`）、`desktop_startup_perf` 14/14、默认冒烟 8/8，全 0 红。
- 欠账：O14 关闭，清单剩 O15—O48；本轮号 1338 − 上次绿全量 1336 = 2 < 5，且不命中 §5 升级条件，本轮不跑全量。

## 问题
- 剧本页只说「已打开 X 的独立对话」和一条 token 用量，但没解释四件事其实是不同维度：当前会话模型与调用方式、本次实际请求身份、上下文来源（本模型对话记录 vs 项目共享成果）、以及正式采用关系。
- 用户在 A→B→A 切模型、或同一模型换调用方式后，容易把「对话历史看不见了」误当成「项目成果没了」，或者反过来以为切换模型会复制出第二套权威稿。

## 实现
- `writing_api.chat_session_overview(project, model=None)`（只读）：返回会话模型、调用方式（`API 直连`／`桌面 Agent（claude）`）、请求身份（Provider／模型目录）、上下文说明（本模型对话记录，按模型隔离）、项目共享的已确认阶段文件数与自然剧本采用状态，以及三条说明。`chat_session_summary(...)` 合成一行。
- 桌面剧本页在用量标签下新增只读说明标签 `idea_session_label`；`show_conversation` 重绘时按当前显示模型刷新，模型切换（`refresh_script_chat_for_selected_model`）后随之更新。
- 说明明确：切换模型只换对话记录（含 token 用量估算按模型分开），不串入其他模型历史、不改变项目成果；已确认阶段文件与自然剧本采用是项目共享成果，不隐藏也不复制；「删除全部信息」把本模型对话移入回收站、项目成果保留（即「从当前成果开新会话」）。
- 未新增模块、未改分层登记表；`writing_api` 仅追加 L2 只读函数，不落盘、不改采用状态。

## 验证
- 新增 `tests/test_idea_chat.py::SessionOverviewTests::test_overview_separates_session_context_and_adoption`：`gpt-4o` 判为 `API 直连`、`claude-code` 判为 `桌面 Agent（claude）`；已确认阶段文件计 1；未采用自然剧本；摘要含模型名、「已确认阶段文件 1 份」与「不隐藏也不复制项目成果」。
- 新增 Tk 用例 `ComposerLayoutTests::test_session_label_explains_dimensions_and_follows_model_switch`：首帧后说明标签含「当前会话：」「按模型隔离」「不隐藏也不复制项目成果」；切到「另一模型」刷新后标签随之更新。
- 定向 `-k idea_chat` 131/131、0 红；关联 `-k ui_edges idea_inline_brief writing` 全绿；架构相关全绿；`-k desktop_startup_perf` 14/14（13.3 秒，无抖动）；默认冒烟 8/8。
- 台账：`desktop.py` 新增 Tk 标签与重绘赋值，TODO 注释快照 desktop.py 行号 2749→2753；`writing_api.py` 未触碰 `json.loads`（第四项 point 486 不变）。

## 风险与边界
- 说明标签是只读文案，不是采用或隔离凭据；真正的隔离仍由「按模型分区的对话记录」实现，采用仍由阶段台账决定。
- 新增标签放在用量标签下方，只在剧本页重绘时更新；未重启应用、未真实点击界面，单元与静态验证不等于真实交互验收；`desktop_startup_perf` 未出现退化。
- 「从当前成果开新会话」复用既有「删除全部信息」入口，未新增第二套清空逻辑。

[TASK_COMPLETE] 会话、请求身份、上下文来源与项目共享成果在界面分开说明（会话模型／调用方式、Provider／模型身份、按模型隔离的对话记录、已确认阶段文件与自然剧本采用状态）；切模型只换对话记录，不隐藏也不复制项目成果；只读说明不落盘、不改采用状态；定向 131/131、关联全绿、架构全绿、desktop_startup_perf 14/14、默认冒烟 8/8，0 红。
