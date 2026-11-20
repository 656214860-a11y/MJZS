# R3963 结果：登记主干正式全量转绿，记录会话接续上下文

## 1. 三问

- 轮次类型：状态接续轮。只改状态页（抬头一行、两处失效链接）和本文件。
- 测试跑了吗、三个基线过了吗：本轮未跑冒烟、架构门禁和全量（docs-only）。登记的全量结论来自后台自动全量：主干 `91d2d803`（R3961）2026-11-21 00:22:18 结束，9517 条用例、0 个文件红；`scripts/auto_full_safe.py --status` 输出「上次全量 R3961；最新 R3961；其间改过源码的轮次 0（门禁线 8）；红后冷却 无」。
- 欠账少了吗：主干全量欠账归零（上一份绿全量是 2026-11-19 22:30:51 的 `98dafefa`）。新记 1 条待修的偶发红，见 §2 第 2 条。

## 2. 登记的事实

1. 主干最近三次后台正式全量（`<git common-dir>/full-safe-history.jsonl` 末三行）：

   | 结束时间 | HEAD | 结果 | 耗时 | 红的测试文件 |
   | --- | --- | --- | --- | --- |
   | 11-20 22:57:11 | `01d25ba3`（R3946） | 红 | 1027 秒 | test_copy_rules、test_l1_transport_requests、test_idea_chat、test_idea_inline_brief |
   | 11-20 23:43:02 | `c6ae9f72`（R3955） | 红 | 1172 秒 | test_publication_fsync_budget |
   | 11-21 00:22:18 | `91d2d803`（R3961） | 绿 | 935 秒 | 无 |

   第三行对应日志 `程序/logs/auto_full_safe.log`：「共 9517 条用例，921.3 秒；0 个文件有红」。第二行的用例数（9487）是上一会话当时从日志读到的，日志已被第三次全量覆盖，本轮没有复核。

2. `test_publication_fsync_budget` 是偶发红：全量历史 297 行里它红过 2 次（11-19 06:37 `f82f40f3`、11-20 23:43 `c6ae9f72`），两次都是当次唯一红的文件；`91d2d803` 上该文件通过。上一会话读代码得到的原因（本轮未复现，由修复轮给出前后对比）：用例在 `publication._LOCK` 之外手工摆事务目录，而 `agent.core` 的读写都会进 `publication.access()`，把还没写 `journal.json` 的事务目录当作未登记清掉；同进程有别的线程恰好读写时就红。同样写法的测试有两处：`tests/test_publication_fsync_budget.py`、`tests/test_publication_recovery.py`。修复在车道 `codex/publication-test-fixture-lock`（R3962）：只改这两处测试夹具，产品代码和断言不动。全量里是哪条测试留下了后台线程没有查明，记为欠账。

3. 状态页两处失效链接改到迁移后的位置（依据 `docs/records/文档迁移台账.md`）：`说明/账户会员云端立项前清单.md` → `docs/records/账户会员立项历史.md`；`说明/账户会员云端设计.md` → `docs/specs/07_业务域规格.md` §7.9。

4. 合并队列现状（`scripts/dev.py merge-queue list`）：mq-31（`codex/nightly-review-2026-11-19`，R3859）failed，待重新合入；mq-32（`codex/taskbook-reconcile`，W3）pending，待返工；mq-34（`codex/mature-component-eval`，W2）、mq-35（`codex/gate-unblock-close`，W7）、mq-36（`codex/merge-tool-synced-lane-2`，W6）、mq-37（`codex/stale-lane-verdicts`，W12）、mq-38（`codex/scan-exclude-logs`，W13）pending。

5. 本轮开工时另一条车道在跑安全全量（`.agents/worktrees/l2-maturity-takeover`，00:25:47 起，持 `full-safe-runner.lock`）。本轮不跑测试，不受影响。

## 3. 会话接续上下文（AGENTS §9）

上一会话（对话 ID 前缀 c2cb0ad3，2026-11-20 20:35 开始，记录导出于 11-21 00:13）结束，本会话（前缀 6c3dd20b）接手。用户要求把每个结束的会话上下文保存进工程文档，本节即上一会话的上下文：只记目标、决定和仓库事实，不抄聊天原文。完整消息记录在本机 `.agent-chat/`（不入库）。

- **目标**：12 小时窗口（11-20 20:35 至 11-21 08:35）内推进改造：锁任务书 G0–G2、主干转绿与状态轮、合入已完成分支（W2、R3859、R3947）、复核 Devin 交付（W3 返工、W6–W13）。总计划见《分层收口与并行冲刺任务书》，锁机制见《Git并发锁机制优化任务书》，均在 `程序/tasks_round/`。
- **用户定的事**：限时的远程模型只做解阻塞、裁决、合并验收和写任务书，量大且规则明确的实现与盘点交给本机 Devin；DeepSeek、GPT 两边中断的会话任务交给 Devin 接着做。
- **沿用的约束**：不 push；不 `git add -A`；不 `--no-verify`；不动别的会话的工作树；不跑 `merge_queue serve`（会弹出 mq-32）；全量跑着时不跑重测试。
- **已完成（主干提交）**：R3933 状态接续 `f675ebf6`；R3937 两本任务书合入 `f82c1b8d`；R3940 残留包列表不再列出阶段模板目录 `fbcde1c4`；R3945 治理车道 `codex/governance-land` 合入 `5697ac34`；R3946 中断会话任务的接手任务单（W6–W13、W3 返工）合入 `01d25ba3`；R3951 W1 历史残留盘点合入 `cdf93433`；R3955 修主干全量 5 条红合入 `c6ae9f72`；R3961 G2 提交门禁按真实冲突判断合入 `91d2d803`（车道提交 `4081eb82`、`6baadecb`，R3956）。
- **进行中**：车道 `codex/publication-test-fixture-lock` 已领 R3962，两处测试夹具已改、结果文件已起草，均未提交。
- **待办（按顺序）**：① 偶发红夹具修复提交并合入；② 合入 `codex/mature-component-eval`（W2，合后把 mq-34 标 done）、`codex/nightly-review-2026-11-19`（R3859）、`codex/auto-full-clean-nested`（R3947）；③ 文档小分支：删《成熟组件评估任务书》末尾 3 行、勾锁任务书 G2、勾冲刺任务书 §9；④ 锁任务书 G0（`codex/git-lock-g0-baseline`，R3949：补记合并工具的 GBK 解码线程异常与钩子输出乱码、旧门禁 11 秒、偶发红、漏登记只能靠出口检查发现，写 `concurrency_report.py`），然后 G1；⑤ 复核 Devin 交付（W3 返工、W6–W13）；⑥ 请用户确认：ADR-0015 第 3 条与契约 C18 的措辞、工作树清理清单。
- **本会话新增的用户要求（2026-11-21 00:20）**：每个结束的会话上下文保存进工程文档；围绕「完善和补全需求文档设计规格」先澄清、再出方案和任务卡，用户回答前不写代码。澄清问题已发出，本轮提交时尚未答复；存放位置与常设规则由用户答复后另轮落地。

## 4. 提交

已提交：是。本轮提交只含 `程序/project_status.md` 与本文件，hash 以 `git log --grep "^R3963:"` 为准（同一提交无法回填自身 hash）。
