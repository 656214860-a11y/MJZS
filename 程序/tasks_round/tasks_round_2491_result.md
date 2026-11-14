# R2491 可靠性轮：codex 后台调用 session 持久化与 resume 续跑（含 resume 命令修正）

## 三问

1. **本轮属于 §3 哪种类型？** 可靠性轮（§3.8）。承接 R2488 的流式端到端，把 codex 后台调用的 session id 持久化 + `exec resume` 续跑闭环打通；并修正 R2483 里 codex resume 命令语法的 bug。不改阶段业务语义、不改输入输出契约、不改分层/权威源。
2. **测试跑了吗、三个基线过了吗？**
   - 定向：`test_cli_streaming` 16 条全绿（含 6 条新增 session 持久化/消息提取）；`test_engine_probe` 28 条全绿（契约同步）；受影响 `workflow_engines_run`/`workflow_process_registry`/`qwen_adapter`/`opencode_engine`/`previs_monitor`/`previs_automation`/`force_quit` 共 128 条全绿。
   - 默认冒烟 8/8 通过。
   - 架构门禁：分层、静默异常无新增；`desktop_idea_chat::IdeaChatMixin 769 行` 为既有历史欠账（非本轮触碰）。
3. **project_status.md 的欠账少了吗？** 未减少；本轮未触碰历史欠账条目（规则 30a）。

## 目标

codex CLI 已装（v0.169.0，本机实证）。打通 codex 后台调用的 session 持久化闭环：跑完记录 session id → 失败重试时 `codex exec resume <id>` 续上下文，替代"每次从头重跑"。

## 实证（本机 codex v0.169.0，已登录）

- `codex exec resume [SESSION_ID] [PROMPT]` 是**子命令**（不是 `--resume` flag）；`SESSION_ID` 是 UUID，`PROMPT` 用 `-` 走 stdin。
- `codex exec --json` 输出 JSONL，首事件 `{"type":"thread.started","thread_id":"<uuid>"}` 即 session id；`item.completed` + `item.type=="agent_message"` 带 `item.text` 为回复正文。
- 附带发现：用户 `.codex/agents/executor.toml`、`reviewer.toml` 有 TOML 解析错误（codex 输出里报了 `Ignoring malformed agent role definition`），与本轮无关，仅供记录。

## 改动

- `程序/workflow_engines.py`：
  - 修正 `background_command`：codex 的 resume 从错误的 `--resume <id>` flag 改为 `exec resume <id>` 子命令；claude 保持 `-p --resume <id>` flag 不变。
  - codex 加 `--json`（stdout 输出 JSONL，含 thread_id 与 agent_message）。
  - 新增 `extract_codex_thread_id(line)` / `extract_codex_message_text(line)`：解析 JSONL 提取 session id 与回复正文。
  - 新增 `save_background_session` / `load_background_session`：session id 按 engine+stage 存进 `工作流任务/后台引擎会话.json`。
  - `run_background`：开头回读 session 绑定（无显式 resume_session 时）；codex 分支边流式显示 agent_message 正文边提取 thread_id，跑完持久化；监视页不再显示 JSONL 噪声，只显示人读回复。
- `程序/tests/test_cli_streaming.py`：新增 6 条（thread_id 提取、message_text 提取、codex 加 `--json`、resume 子命令、session 读写 roundtrip）。
- `程序/tests/test_engine_probe.py`：`CODEX_HELP` mock 加 `--json`（契约同步——真实 codex v0.169.0 的 `exec --help` 确实有 `--json`）。

## 契约变更说明（规则 2.4）

- `background_command` 的 codex 加 `--json`：`engine_probe` 契约测试的 mock `CODEX_HELP` 同步补 `--json`（基于真实 codex 实证，非弱化断言）。
- codex 后台调用的 stdout 从"过程日志文本"变为"JSONL"，`run_background` 已过滤 JSONL 噪声、只把 agent_message 正文交给流式回调；logfile 仍写原始 JSONL 供排查。

## 未实证 / 待确认

- **claude 的 session 持久化**：本轮聚焦 codex；claude 的 `-p --resume` flag 语法已正确（R2483），但 `run_background` 里 claude 跑完后的 session id 持久化尚未接（`save_background_session` 只接在 codex 分支）。留待后续轮。
- **codex 真机端到端**：`extract_codex_thread_id` 基于本机 `codex exec --json` 真跑实证；但 `run_background` 里 codex 完整链路（跑完→存 session→重试 resume）未真机端到端验证（previs 批量无人值守路径需要真实项目触发）。

## 验证命令

```
python -B run_selftests.py -k cli_streaming engine_probe workflow_engines_run workflow_process_registry qwen_adapter opencode_engine previs_monitor previs_automation force_quit test_layers test_silent_exception_ratchet
python -B smoke_test.py                          # 默认冒烟 8/8
```

## 提交

- 提交信息：`R2491: codex 后台调用 session 持久化与 exec resume 续跑`
- 提交 hash：`84848625`
- 分支：`codex/wip-R2491`
