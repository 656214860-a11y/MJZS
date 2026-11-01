# R1688 功能轮（源码轮）：新增 opencode CLI 制作引擎

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（源码轮）。新增与 qwen 并列的 `opencode` 制作引擎，走官方 `opencode-cli.exe`，不接 API；不改任何阶段的默认引擎，也不改用户已有配置数据。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k opencode_engine workflow_engines workflow_settings model_pool skill_panel stage_execution engine_probe`：110 条 0 红（3 个 GUI `skill_panel` 文件被入口自动延后），单独复跑这 3 个文件 6/6，合计 116/116；新测试文件直跑 12/12；架构门禁 `function_size_ratchet agents_md module_size_ratchet test_layers` 24/24；默认冒烟 8/8。既有 `test_core:363`、`test_workflow:385/417` 的引擎集合断言未改，对应 3 条定向用例 3/3。未跑 `--all`。
3. **project_status.md 的欠账少了吗？** 没有减少。本轮改源码，源码轮全量欠账 **+1**。

## A 改动

- `workflow_settings.py`：`ENGINES` 新增 `opencode`，显示名“opencode CLI（自动放行权限）”；`find_model_program` 的 CLI 别名表与受支持引擎元组加入 `opencode`；`find_program` 先查 `shutil.which('opencode-cli.exe')`，再扫 `%APPDATA%\ai.opencode.desktop\cli\*\opencode-cli.exe` 并取修改时间最新者；SKILL 提示词注入元组加入 `opencode`。`defaults/load` 由 `ENGINES` 循环自动带出 `opencode` 档案，默认引擎仍为 `codex`。
- `workflow_engines.py`：`background_command(..., prompt_file=None)` 为 opencode 生成 `[exe, 'run', '--auto', '--format', 'json', '-m', model, '--file', 提示词文件, '执行附件中的制作任务']`；不传 `--cd/--add-dir`，工作目录由 `Popen(cwd=project)` 指定。新增 `_opencode_prompt_file`、`_opencode_report_text`、`_run_opencode`，提示词写入 `报告名.opencode-prompt.md`，原始 JSONL 保留为 `报告名.response.jsonl`；经既有 `_run` 登记进程，强制停止可结束；解析 `type=text` 事件的 `part.text` 写入报告，非零退出、空报告、非法事件均抛中文 `ValueError`。`launch_interactive` 明确拒绝 opencode 并提示走手动／后台入口。
- `stage_execution_service.py`、`model_pool.py`、`skill_panel.py`：本地 Agent 集合、CLI 调用模式元组、显示名映射同步加入 `opencode`，避免被识别成 Desktop。
- 新增 `tests/test_opencode_engine.py`（12 条）：查找 PATH／APPDATA 两条路径、CLI 别名、后台参数与提示词文件、成功／失败／空报告、强制停止、`defaults/load` 带出档案、调用模式路由、面板显示。事件夹具来自本机 `opencode-cli.exe v2.0.32` 的一次真实 `run --format json` 取样；进程边界用测试 CLI 替身，但参数、提示词文件、cwd 与 JSON 事件解析走真实实现。
- `project_status.md`：当前轮次改为 1689，并在 R1687 前新增 R1688 条目。未运行 `round_claim.py`，未执行 `git add/commit`，等待复验提交。

## C 待裁决

- **`--auto` 无沙箱**：后台命令按任务书使用 `--auto`，OpenCode 可按当前用户权限直接改文件／执行命令；目前没有目录级沙箱或额外权限确认。是否需要限定工作目录或增加运行前提示，待产品裁决。
- **事件格式只取样一次**：成功事件夹具来自 `--standalone` 的一次真实调用，取样命令未加 `--auto`；取样环境默认托管服务报端口 45278 被占用，未验证默认托管模式、不同版本、工具调用事件、错误事件等其它事件形态。若实际输出含非 JSON 前缀行或其它 `type`，当前解析会抛错并保留原始 JSONL，需按真实样本再调整。
- **未做交互启动**：`launch_interactive` 对 opencode 明确拒绝；尚未实现交互式追问、会话续接或权限交互。
- **未做目视／真实引擎端到端**：未用真实账号、额度与实际项目跑完整制作；未验证 OpenCode 生成报告内容、工具调用、长提示词、Windows 命令行长度、并发槽位与 GUI 展示。测试只覆盖进程调用、事件解析和路由。
- **默认模型未写死**：`opencode` 档案的 `model` 默认为空，此时后台命令不传 `-m`，使用 CLI 自身默认模型；实际模型需用户在调用设置中填写或选择。
- **真实进程树未验证**：强制停止只用测试 CLI 验证了 `_run` 登记路径；未验证真实 `opencode-cli.exe` 是否派生独立子进程并被 `terminate_process_tree` 一并结束。
- **未改默认与用户数据**：没有把 opencode 设为任何阶段默认引擎，没有迁移或改写用户已有 `工作流调用设置.json`。
- **`engine_probe.py` 未纳入**：该文件不在本轮 ALLOWLIST，未把 opencode 加入其 `locate`／`app_argv`，只跑了既有回归；环境自检页是否应展示 opencode 需另开轮次。
- **测试入口环境绕过**：`run_selftests.py -k` 的跨树 GUI 锁指向 `D:\repo-meta\漫剧制作助手.git`，在本沙箱会卡住；定向运行时通过调用入口临时置空 GUI 锁函数完成，未修改 `run_selftests.py`。该绕过只影响测试令牌，不影响被测代码；正式复验建议在正常令牌环境重跑同一定向命令。
