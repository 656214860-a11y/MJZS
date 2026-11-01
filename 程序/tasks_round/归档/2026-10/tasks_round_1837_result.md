# R1837 结果（文档轮）：撤销派发规则，改为 Claude Code 自己完成全部任务

## 改动
- AGENTS.md §4：删除"调度兼审查方／执行方（Codex／opencode／DeepSeek）"分工，改为 Claude Code 自己改代码、跑测试、领号、提交；新增"含 Tk 的测试一律经 `工作流任务/gui_hidden.py` 在隐藏桌面运行"。另删改入口、规则 7／27／§2.6／§7 中"派发执行方"的 7 处表述。
- CLAUDE.md：工作约定"Claude 的角色"同步改写。
- .claude/settings.local.json：顺带提交此前会话积累的只读命令白名单。
- 仓库外（不入库）：新增 PreToolUse 钩子 `~/.claude/hooks/gui_test_guard.py`，拦截未经隐藏桌面的测试命令；`工作流任务/dispatch*.sh` 移入 `dispatch_archive_20261022/`。

## 验证
- 钩子：直接 `python -B smoke_test.py` 被拒绝，经 `gui_hidden.py` 放行（手工输入 JSON 实测）。
- 纯文档改动，未跑测试。
