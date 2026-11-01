# R1425 结果：CLI 失败提示与桌面图形程序误配拦截（路线图 A）

- 轮次类型：§3.2 修复轮。范围：`维护记录/TODO注释快照_20261003.json`、`维护记录/架构统一基数.json`、`workflow_settings.py`、`workflow_engines.py`、`pet_models_ui.py`、`desktop.py`、对应 2 个测试文件、`维护记录/路线图_20261014.md`。领号方式同 R1423。

## 根因

模型条目 `claude code` 的程序路径指向 Claude Desktop 图形程序（`...\WindowsApps\Claude_*\app\Claude.exe`）。该条目走命令行路径，用 `-p --output-format json` 启动图形程序，得不到 JSON，只报「Claude CLI 未返回有效 JSON」；剧本页失败原因只写状态栏，用户看不到。

## 修改

- `workflow_settings.gui_claude_program(path)` 识别 WindowsApps／AnthropicClaude／Programs\Claude 下的 `claude.exe`（命令行版在 `.local\bin`、npm 包内，不受影响）；`GUI_CLAUDE_CLI_HINT` 给出改用 `claude-desktop-app` 条目或换命令行 exe 的说明。
- `workflow_engines`：`ClaudeWritingAdapter.chat` 调用前识别，直接返回该说明且不启动进程；`background_command`、交互任务启动同样拦截。
- `pet_models_ui.save_one`：Claude 命令行条目（模型 ID `claude`／`claude code`／`claude-desktop`）保存图形程序路径时提示并拒绝；`claude-desktop-app` 不受影响。
- `desktop.py`：剧本页模型调用失败原先仅预算超限弹窗，现在其余失败也弹「模型调用失败」，文案沿用原有分类（网络／服务端统一提示重试，鉴权／预算／请求沿用原文）。

## 测试

- 新增 3 项：路径识别（图形与命令行样例）、写作适配器不启动进程并返回说明、模型管理拒绝保存。
- 实测环境：远端 Linux 源码副本（Python 3.12.13，非随附解释器）。新增 3 项全部通过；`test_claude_program_detection` 唯一失败与 R1424 记录相同（依赖 Windows）；`ModelPoolTests` 唯一失败与 R1423 记录相同；相关 243 项中唯一错误 `test_separate_confirmations_do_not_share_dispatch_signature` 在未改代码副本上同样出现（`date` 被 mock）。
- 架构目录全量 341 项：初次 2 项失败（`desktop.py`、`workflow_engines.py` 行号后移使 TODO 注释快照与裸 JSON 棘轮基线过期），已把 `维护记录/TODO注释快照_20261003.json`（2809→2811）与 `架构统一基数.json`（174→178、215→219）按实际行号更新，不放宽规则；这两项复跑 5/5 通过。
- 未运行：`test_pet_ui` 全文件、`test_idea_chat` 全文件（超时）、随附解释器冒烟、全量；1425−1420=5，命中 §5 五轮欠账，**需在 Windows 随附解释器上补跑 `--all --safe`**，本轮不冒充。

## 自审

仅改授权文件；未改用户配置；未启动任何真实程序；弹窗是行为变更，已在报告中列明。同类问题：Codex 桌面条目未做同类拦截，未发现已知故障，暂不改。
