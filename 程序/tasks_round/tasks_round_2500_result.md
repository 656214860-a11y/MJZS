# R2500 可靠性轮：claude 后台调用 session 持久化（对齐 codex）+ 架构欠账收口

## 三问

1. **本轮属于 §3 哪种类型？** 可靠性轮（§3.8）。把 R2491 已落地的 codex 后台 session 持久化对齐到 claude；顺带修复 R2491 引入的 `run_background` 嵌套越限与 codex json.loads 未登记债务。不改阶段业务语义、不改输入输出契约、不改分层/权威源。
2. **测试跑了吗、三个基线过了吗？**
   - 定向：`test_cli_streaming` 17 条全绿（含 2 条新增 claude session 持久化）；`test_engine_probe` 28 条全绿；`workflow_engines_run`/`workflow_process_registry` 共 57 条全绿。
   - 默认冒烟 8/8 通过。
   - 架构门禁：本轮引入的 `run_background` 嵌套越限已压平、codex json.loads 债务已登记；剩余 2 项为**基线/环境欠账**（`desktop_idea_chat::IdeaChatMixin 769 行` 为 R2482 遗留类体量超线、`screenplay-gate-engine.md` 缺失为 worktree 未实体化 gitlink），非本轮引入，如实登记不越界修复。
3. **project_status.md 的欠账少了吗？** 未减少；本轮未触碰历史欠账条目（规则 30a）。

## 目标

claude 后台调用（`run_background` 的 `-p --output-format json` 路径）跑完后持久化 session id，失败重试时 `claude -p --resume <id>` 续上下文，对齐 R2491 已为 codex 打通的机制。

## 改动

- `程序/workflow_engines.py`：
  - `background_command` 的 claude 分支：无 `resume_session` 时主动生成 uuid 加 `--session-id <uuid>`（与 `launch_interactive` 的 claude 分支同一机制），uuid 回写 `config['session_id']` 供持久化。
  - `run_background` 的 claude 分支：跑完 returncode==0 且有 session_id 时 `save_background_session(project, stage, 'claude', session_id)`。
  - 把 codex 的流式回调闭包提为模块级函数 `_codex_stream_output`，用 `functools.partial` 绑定，压平 `run_background` 嵌套深度（修复 R2491 引入的复杂度棘轮越限）。
- `程序/tests/test_cli_streaming.py`：新增 `test_claude_without_session_gets_session_id_and_no_resume`（uuid 格式 + config 回写）与 `test_claude_with_resume_uses_resume_not_session_id`（resume 时不生成 session-id）。
- `程序/维护记录/架构统一基数.json`：
  - 第四项登记 2 条 codex json.loads 债务为 exempt（`extract_codex_thread_id`/`extract_codex_message_text`，解析 codex exec --json 进程 stdout 内存文本，不读文件）。
  - 修正 R2470 代码迁移遗留：`_http_transport`/`http_stream` 两条 json.loads 台账的 file 从 `model_pool.py` 迁到 `api_endpoints.py`（代码已随 R2470 下沉，台账未同步）。

## 契约变更说明（规则 2.4）

claude 后台调用从"claude 自生成 session id"改为"程序主动指定 `--session-id <uuid>`"，与 `launch_interactive` 的 claude 分支一致；`SESSION_SWITCHES` 已含 `--session-id`，`engine_probe` 契约未破。同步更新 `test_cli_streaming.py` 断言（未弱化，反而更精确地区分 resume 与新建两种路径）。

## 真机实证（2026-11-15 补记）

claude 侧此前标注的「未实证」已补齐，真机跑通 `--session-id` → `--resume` 闭环（claude 2.1.309，经 `cc switch` 路由到 DeepSeek 代理 `ANTHROPIC_BASE_URL=http://127.0.0.1:15721`、`ANTHROPIC_AUTH_TOKEN=PROXY_MANAGED`）：

| 步骤 | 命令要点 | 实测结果 |
| --- | --- | --- |
| 新会话 | `claude -p --output-format json --permission-mode auto --session-id <uuid> "记住数字 42"` | exit 0，响应 `session_id` 回显与传入一致 |
| 续跑 | `claude -p --output-format json --permission-mode auto --resume <uuid> "刚才的数字？"` | exit 0，`"result":"42"`，`cache_read_input_tokens:22912`（命中缓存续上下文，非重发 23k token） |

结论：`workflow_engines.py::background_command` 的 claude 分支参数形态（新跑 `--session-id <uuid>` + 持久化、重试 `--resume <id>`）与真机二进制行为一致，续跑会话成立。此前首轮真机调用曾返回 `Not logged in`，经确认系代理握手未就绪的一次性瞬态，随后调用即正常并消耗真实额度。

## 验证命令

```
python -B run_selftests.py -k cli_streaming engine_probe workflow_engines_run workflow_process_registry
python -B smoke_test.py                          # 默认冒烟 8/8
```

## 提交

- 提交信息：`R2500: claude 后台调用 session 持久化对齐 codex + 架构欠账收口`
- 提交 hash：`d5a70220`
- 分支：`codex/wip-R2500`
