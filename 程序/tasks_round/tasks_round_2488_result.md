# R2488 可靠性轮：CLI 引擎后台调用流式日志端到端接入

## 三问

1. **本轮属于 §3 哪种类型？** 可靠性轮（§3.8）。承接 R2483 的「能力地基」，把 `on_output` 流式回调端到端接入白模预演监视页；不改阶段业务语义、不改输入输出契约、不改分层/权威源。
2. **测试跑了吗、三个基线过了吗？**
   - 定向：`test_cli_streaming` 9 条全绿（含 3 条新增端到端）；受影响 `workflow_engines_run`/`workflow_process_registry`/`qwen_adapter`/`opencode_engine`/`engine_probe`/`previs_monitor`/`previs_automation`/`force_quit` 共 112 条全绿。
   - 默认冒烟 8/8 通过。
   - 架构门禁：本轮的「参数数量超限」已通过 `options` 字典收拢修复；静默异常、越层依赖无新增；剩余红项 `desktop_idea_chat::IdeaChatMixin 769 行` 为**既有历史欠账**（master R2482 带入，本轮未触碰该文件），如实登记、不擅自扩大范围修复。
3. **project_status.md 的欠账少了吗？** 未减少；本轮未触碰历史欠账条目（规则 30a）。

## 目标

R2483 交付了「能力地基」：`on_output`/`resume_session` 接口就位、三层透传、测试覆盖，但无生产调用方使用。本轮把流式日志**端到端接上**：白模预演批量无人值守跑 CLI 引擎时，引擎实时输出边跑边显示在浏览器监视页。

## 改动

- `程序/platform_tools.py`：`on_output` 回调签名从 `on_output(line)` 精化为 `on_output(line, stream)`（stream ∈ 'stdout'/'stderr'），让调用方能区分日志与结构化响应（Claude 的 stdout 是 JSON 响应、stderr 才是运行日志）。
- `程序/workflow_process_registry.py`：`run_registered` 的可选关键字 `env`/`on_output` 收拢为 `options` 字典（修复参数数量 8→7 越限），`forward` 按 `stream` 写回对应文件对象。
- `程序/workflow_engines.py`：`_run`、`_run_claude_json`、`run_background` 均透传 `on_output`。
- `程序/qwen_adapter.py`：`run_registered` 调用改 `options={'env': env}`（适配收拢）。
- `程序/previs_automation.py`：`worker` 里给 `run_background` 传 `on_output` 回调，把引擎输出尾随最后 200 行写进 `state['engine_log']`（stderr 加 `[err] ` 前缀）。
- `程序/previs_monitor.py`：`render` 在镜头表后新增 `<pre class="engine-log">` 区块，显示 `state['engine_log']` 尾随 200 行，深色等宽滚动区。
- 测试：`test_cli_streaming.py` 适配新签名 + 新增 3 条端到端（`run_background` 透传、监视页显示/省略日志块）；`test_workflow_engines_run.py` 的 `fake_run` 补 `on_output=None` 形参（契约同步）。

## 契约变更说明（规则 2.4）

`on_output` 回调签名由单参数改为双参数 `(line, stream)`，属有意契约变更：R2483 的 `on_output` 尚无生产调用方，端到端接入 claude 时发现 stdout（JSON 响应）与 stderr（运行日志）必须区分，否则 JSON 会混入日志显示。同步更新了 `test_cli_streaming.py` 断言（未弱化，反而更精确地区分流来源）。

## 未实证 / 待确认

- **codex 的 `--resume` 接受什么 session id**：本机未装 codex，`codex exec --resume` 的 session id 来源待真机验证（沿用 R2483 标注）。
- **session id 持久化**：`resume_session` 字段仍无调用方写入；`run_background` 跑完后从引擎输出解析并持久化 session id（复用 `Claude对话.json`/`codex_tasks`）留待后续轮，因涉及引擎输出格式解析 + codex 未实证，本轮不做。

## 验证命令

```
python -B run_selftests.py -k cli_streaming workflow_engines_run workflow_process_registry qwen_adapter opencode_engine engine_probe previs_monitor previs_automation force_quit
python -B smoke_test.py                          # 默认冒烟 8/8
```

## 提交

- 提交信息：`R2488: CLI 后台调用流式日志端到端接入白模监视页`
- 提交 hash：`0e67666d`
- 分支：`codex/wip-R2488`
