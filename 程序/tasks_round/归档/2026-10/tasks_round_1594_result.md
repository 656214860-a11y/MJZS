# R1594：剧本 CLI 读取当前采用剧本并对隔夜会话自动换新

- 类型：§3.2 修复轮；用户直接报告，无对应队列 ID。
- 测试：定向（workflow_tasks / script_contract / episode / agent_delivery / claude_writing / workflow_engines / idea_chat）0 红；`smoke_test.py` 与 `--affected idea_chat workflow` 通过；新增 2 份测试，既有断言未动。未跑架构全量与全量。

## 根因与证据

摄影侠项目 2026-10-16 15:27 任务书（113 KB）中“咔咔”0 次：用户手改剧本位于 `01剧本准备/Anthropic/Claude Desktop/…`，而交付契约只列本模型（Claude Code CLI）目录，限定输入又禁止读取其他模型产物；CLI 回复自承“全新写的”。同一 Claude 会话自 10-09 起一直 `--resume`，旧稿残留上下文。

## 修复

- `script_contract.script_baseline_path`：从 `script_episode_baseline` 抽出路径选取（采用版 → 最新自然剧本 → 工作稿），原函数改为复用。
- `workflow_tasks._current_script_notice`：本地 Agent 剧本初始任务与续发注入【当前自然剧本】绝对路径，声明不受“其他模型产物”限制、须以其为基础修改并待确认；API 路径不注入。
- `workflow_engines.claude_session_stale`：绑定会话 jsonl 超 12 小时未写入即视为过期，`open_flow_agent` 走既有关闭空闲窗口并新建会话流程；旧会话记录不删除。

## 交付与接续

需重启应用生效；真实 CLI 按当前剧本改写的效果待用户发送后验收。
