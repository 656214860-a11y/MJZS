# R3922 结果：校正架构文档合并试算

## 1. 三问

- 轮次类型：状态接续轮（`runbook.md` §15 的 3.11）。只改状态页，不改生产代码。
- 测试跑了吗、三个基线过了吗：未跑。本轮不改 `.py`。写入时 `full-safe-runner.lock` 与 `gui-selftest.lock` 都不在，PID 7796 已退出。
- 欠账少了吗：没有。`.git/full-safe-receipts.json` 最新绿凭据仍是 R3849，`.git/full-safe-history.jsonl` 末行仍是 `98dafefa`、成功、外层 1037 秒。锁已释放，没有新凭据，不把这次查锁写成全量成功或失败。

## 2. 改动

R3921 把 `architecture.md` 的未提交修正写成「对 49 条检出分支做合并试算，47 条会冲突」。那个 47 用的是当前主干当合并基线，数字作废。本轮按 `git merge-base master <分支>` 重算，并改了状态页上的主树提交号（现为 `f870678a`）和车道条里的这句。

`codex/architecture-doc-facts` 工作树里的未提交草稿仍在，本轮没有提交它。草稿相对主干有 4 处：删去不存在的 `skills/cinematic-director/`、两处扫描范围 `skills/01`—`12` 改为 `01`—`13`、阶段模板清单补上 `animatic`、`domain/message_parts` 改为已在 `_layers.py` 登记为 L2。优化队列草稿把 25 条结果链接改到 `tasks_round/归档/2026-10/`，并改正 A7 的已缺失路径、给 U14 加注主树已无 `skills/00全流程SKILL/`。

## 3. 重算结果

`dev.py commit` 在该工作树对这两份文件返回退出码 5。`architecture.md` 与 48 条检出分支的未合入改动重叠，`维护记录/优化待办队列.md` 与 `codex/directory-governance-execution`、`codex/governance-land` 重叠。门禁按整份文件拒绝。

同一时刻用 `git merge-file`（基线是 merge-base，不是当前主干）分开看改动：

- 只删 `cinematic-director/`、只补 `animatic`，或两处一起：对上述 48 条都不新增冲突。
- 只改两处扫描范围：给 5 条分支新增冲突。`codex/account-design-consolidation`、`codex/directory-governance-execution`、`codex/retire-builtin-prerequisite`、`codex/wip-r3764` 各增加 1 处；`codex/governance-land` 增加 2 处。
- 只改 `message_parts` 登记说明：给 `codex/foundation-c8-updater`、`codex/foundation-integration-final` 各增加 1 处冲突。
- 优化队列草稿：对那两条车道的冲突数都是 0，相对主干本身的合并试算也是 0。文件级门禁仍然拒绝。

因此这 4 处架构口径和队列修正都还不能经 `dev.py commit` 进主干。不绕过钩子，也不把「合并试算不新增冲突」写成已经提交。

## 4. 车道核对

本轮提交前：`codex/l0-constitution` `35196826`、`codex/l1-enterprise` 与 `codex/architecture-root-layout` 的 `385dd7b6` 都是主干祖先。`codex/gate-unblock` `2e3399af`、`codex/foundation-ffmpeg-runtime` `0f359379`、`codex/foundation-integration-final` `d5fb72fd` 都不是。任务书仍是 29 份、`任务完成/` 除 README 外 19 份；10 份没有完成文件的名单不在本轮重对，仍以 [R3918](tasks_round/tasks_round_3918_result.md) 为准。

## 5. 提交

master 非合并提交不能带 `tasks_round/evidence/`。本轮与 R3918、R3921 一样直接 `git commit`，只暂存状态页和本结果文件。不推送。
