# R2326 结果：U12 失败占比上限 20%、默认解释器切到 Python 3.15.0、修 R2324 留下的三道门禁红（修复轮）

## 改动
- U12：用户裁定失败占比上限 20%。`scripts/release_watch.py` 新增 `FAILURE_SHARE_LIMIT = 0.20`：样本够 5 次且占比超过上限即建议回滚（退出码 1，只报告不自动回滚）；原「超过基线一倍」规则保留。新增 `tests/test_release_watch.py`（4 条）；`说明/发布检查单.md`、`优化待办队列.md` 同步。
- 解释器：`运行环境\Python` 换成 3.15.0 稳定版（并列目录 Python315 改名为 Python），原 3.15.0a2 改名 `Python_alpha_a2_backup` 留作回滚；`runbook.md` §9、`.agent-handoff/risks.md` 同步。`运行环境` 被 gitignore，不入库。
- 门禁红：R2324 新增 `writing_unconfirm.py` 与一条 Tk 跳过用例后，覆盖率基线（358 模块，未覆盖 305）、runbook §11 数字、`skip台账.json` 没同步，补上。

## 验证
- 切换前：干净检出 `.wt/ci` 用 3.15.0 `run_selftests --all --safe --force` 7082 条 0 红；切换后默认冒烟通过。
- `run_selftests -k release_watch release_bindings stdlib_closure startup_budget` 全过；`smoke_test.py --architecture` 全绿。
- GUI 面（Tk 启动、快捷方式）未实机过；未再跑全量。断言未动。
