# R1443 结果：全量欠账收尾三项（风险触发代码强制、钩子自愈、后台失败提示）

三个收尾问题：
- 本轮类型：可靠性轮（R1440 验证治理的后续，用户要求完成此前未做的事）。
- 测试与基线：`test_selftests`／`test_auto_full_safe`／`test_git_hooks` 共 62 条通过；`test_round_baselines` 随新规则更新（断言结构未弱化）。未跑全量。
- 欠账：并行的 R1441 改了 `tests/architecture/_layers.py`，按本轮新规则立即欠一次全量，由其后提交的 post-commit 钩子触发后台补跑，结果写入 `auto-full-safe-result.json`。

## 改动

1. **风险触发改为代码强制**：`run_selftests.has_risk_change()`／`risk_changed_since()` 按路径判定启动入口（`启动漫剧制作助手.pyw`／`启动助手.cmd`）、`storage_maintenance.py`、`tests/architecture/_layers.py`；任一轮改过即立即欠一次全量（`full_safe_required(risk=)` 与 `full_safe_auto_due` 同时触发，不等阈值）。Tk 控件生命周期无法静态判定，仍人工。
2. **钩子自愈**：`round_claim.py next` 领号时 `ensure_hooks()` 自检三种钩子，缺失或与版本受控源不一致就自动安装；失败只提示，不影响领号。
3. **失败提示**：`auto_full_safe.py` 结束写 `auto-full-safe-result.json`（HEAD、退出码、红的测试文件、日志路径）；post-commit 钩子每次先跑 `--notice`，上次未通过就在提交输出里打印；`--status` 同样显示。
4. `AGENTS.md` §5 同步（风险触发自动判定、钩子自愈、失败提示）。

## 测试

风险路径与立即欠账、红模块解析与提示、`--notice` 不失败、钩子自愈各有用例。

## 流程说明

主树当时有并行任务的未提交改动，领号要求干净树，所以本轮在独立工作树 `.wt/R1443`（分支 `codex/wip-R1443`）领号提交，再合回 master。
