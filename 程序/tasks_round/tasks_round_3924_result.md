# R3924 结果：登记已合入的架构树与队列修正

## 1. 三问

- 轮次类型：状态接续轮（`runbook.md` §15 的 3.11）。只改状态页，不改生产代码。
- 测试跑了吗、三个基线过了吗：本轮未跑。R3923 合并轮的出口档已通过（冒烟、静态门禁、架构门禁），日志在车道工作树 `logs/ci_最近.log`。未跑全量。
- 欠账少了吗：没有。最新绿凭据仍是 R3849。

## 2. 改动

R3923 合入之后，状态页车道条还写着这些修正未提交，主树提交号也还停在 `f870678a`。本轮改成当前事实：主树 `271e7637`。已合入的是删去 `skills/cinematic-director/`、模板清单补上 `animatic`、优化队列 25 条归档链接和 A7、U14。两处扫描范围与 `message_parts` 括注没有合入。

## 3. 仍未合入

`codex/architecture-doc-facts` 工作树里还有未提交改动：两处 `skills/01`—`12` 改为 `01`—`13`，以及 `domain/message_parts` 改为已在 `_layers.py` 登记为 L2。`git merge-file` 显示前者给 5 条检出分支新增冲突，后者给 `codex/foundation-c8-updater` 和 `codex/foundation-integration-final` 各新增 1 处。`dev.py commit` 对整份 `architecture.md` 仍会拒绝。不绕过钩子把这两处提交进去。

车道尖端复核仍与 R3922 相同：`35196826`、`385dd7b6` 是主干祖先；`2e3399af`、`0f359379`、`d5fb72fd` 不是。

## 4. 提交

master 非合并提交不能带 `tasks_round/evidence/`。本轮直接 `git commit`，只暂存状态页和本结果文件。不推送。
