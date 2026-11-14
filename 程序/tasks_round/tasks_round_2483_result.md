# R2483 可靠性轮：CLI 引擎后台调用流式日志与续跑参数

## 三问

1. **本轮属于 §3 哪种类型？** 可靠性轮（§3.8）。只提升引擎调用可靠性（流式能力 + 续跑参数），不改任何阶段业务语义、不改输入输出契约、不改分层/契约/权威源。
2. **测试跑了吗、三个基线过了吗？**
   - 定向：`test_cli_streaming` 6 条全绿；受影响测试 `workflow_engines_run`/`workflow_process_registry`/`force_quit`/`opencode_engine`/`engine_probe` 共 68 条全绿（含 15 条架构定向：分层 + 静默异常）。
   - 默认冒烟 8/8 通过（与基线一致）。
   - 架构门禁：本轮的静默异常与越层依赖两处已修复；剩余 4 项失败（`基准历史.json` 缺失、`desktop_idea_chat::IdeaChatMixin 765 行`、`skill 引用`、`api_endpoints json.loads` 债务）均为**既有历史欠账**，与本轮改动无关，如实登记、不擅自扩大范围修复。
3. **project_status.md 的欠账少了吗？** 未减少；本轮未触碰历史欠账条目（按规则 30a 只登记不擅自修复）。

## 目标

用户诉求「调用 codex/claude desktop 更丝滑，替代手动粘贴上传」。经 grill 收敛：本轮先优化 **CLI 引擎后台调用路径**（`run_background`），给流式日志能力 + 续跑参数，对齐 R2470「API 稳定层」的可靠性思路。桌面 GUI 引擎（`claude-desktop-app`/`desktop-app`）因无法被程序驱动，本轮不动。

## 改动

- `程序/platform_tools.py`：`communicate_or_kill` 增加可选 `on_output` 参数——提供时用 PIPE 逐行读 stdout/stderr 并回调（回调在独立线程执行，异常不打断主流程）；未提供时行为不变。新增 `_stream_communicate_or_kill`。
- `程序/workflow_process_registry.py`：`run_registered` 增加可选 `on_output` 透传——提供时把 stdout/stderr 改为 PIPE 逐行读，每行既写回调用方给的文件对象（flush）又回调；未提供时行为不变。
- `程序/workflow_engines.py`：`_run` 增加 `on_output` 透传；`background_command` 对 claude/codex 增加 `--resume <session>`（当 config 带 `resume_session` 时）。
- `程序/tests/test_cli_streaming.py`：新增 6 条测试，锚定流式逐行回调、回调异常不打断、无回调时向后兼容、claude/codex 的 `--resume` 参数。

## 设计说明（为何不触发 §2.7 文档先行）

CLI 调用优化不改变任何阶段的业务语义（输入 prompt、输出 report 契约不变），只是「怎么调引擎」更稳/更流式，属 §3.8 可靠性轮，不要求先改 `docs/stages/` 需求/设计。

## 未实证 / 待确认

- **codex 的 `--resume` 接受什么 session id**：本机未安装 codex CLI，无法实证。基于 GitHub 调研事实（`codex exec --resume <thread-id>`）加代码，session id 来源待接入调用方时实证（`codex_tasks` 持久化的 thread id 与 `codex exec` 的 session id 是否同源需验证）。
- **claude 的 `--resume` 复用 `Claude对话.json` session id**：本机装有 claude CLI，`claude -p --resume <uuid>` 机制与现有 `claude_session_stale` 读取的 session 同源，可实证但本轮未真机跑（无联网额度验证）。

## 端到端接入（留待后续轮）

本轮交付「能力地基」：`on_output` 与 `resume_session` 接口就位、三层透传贯通、测试覆盖。`run_background` 的调用方 `previs_automation.py` 尚未传 `on_output` 回调（无人值守，无实时 UI），`resume_session` 字段尚未由任何调用方写入。端到端接入（previs 接流式回调、UI 显示、session id 持久化）涉及跨 L3/L4 改动，留待后续轮。

## 验证命令

```
python -B run_selftests.py -k cli_streaming workflow_engines_run workflow_process_registry force_quit opencode_engine engine_probe
python -B smoke_test.py                          # 默认冒烟 8/8
python -B smoke_test.py --architecture           # 架构门禁（4 项历史欠账除外，本轮的静默异常+越层已修复）
```

## 提交

- 提交信息：`R2483: CLI 引擎后台调用流式日志与 --resume 续跑参数`
- 分支：`codex/wip-R2483`
