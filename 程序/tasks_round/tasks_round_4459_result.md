# R4459 结果：GIT-LOCK-G0 Git 并发锁机制优化 G0 对账与基线
<!-- round-evidence: {"commit_base": "1abd6d878", "credential_hits": 0, "evidence_sha256": "72718f365d17c055", "exit": 0, "failed": 0, "passed": 26, "round": 4459, "tests": "run_selftests.py -k static_hygiene silent_exception_ratchet unification_ratchet json_io_boundary round_baselines lane_flow_gates"} -->

## 1. 三问（AGENTS §7）

1. **本轮属于 §3 哪种类型？** 验证基线轮（§3.10／只读对账轮），对应任务卡 `GIT-LOCK-G0`（《Git并发锁机制优化任务书》§3 G0）。不修改任何产品源码、既有测试或 Git hooks。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟（`smoke_test.py`）：通过 **9/9**（8 项轮次检查＋隐藏桌面探针，失败 0，退出码 0）。
   - 架构门禁（`smoke_test.py --architecture`）：通过 **708/708**（用时 328.636s，失败 0，退出码 0；较改前无新增失败）。
   - 定向脚本确定性验收：连续两次执行 `scripts/concurrency_report.py`，均退出码 0，stdout 与 `logs/concurrency_report.md` 逐行 diff 均为空（差异 0 行）。
   - 全量回归（`run_selftests.py --all --safe`）：**未运行**（本轮为只读基线轮，按卡面与 AGENTS §5 不跑全量；全量欠账以 common-dir `full-safe-receipts.json` 为唯一权威，当前最近绿凭据为 R4264）。
3. **欠账少了吗？** 未减少历史全量或结构欠账，也未新增任何架构/静态/JSON 边界债务；本轮将 §1 基线指标、H1–H6 实证结论与《全量锁卡死治理任务书》P0–P2 真实进度固定留痕，为后续 G1–G8 提供无误判的决策依据。

## 2. 改前红的证据与改动清单

- **改前复现（红）**：创建脚本前在车道工作树 `程序/` 下执行 `..\..\..\..\运行环境\Python\python.exe -B scripts/concurrency_report.py`，退出码 `1`，stderr 关键错误：`[Errno 2] No such file or directory`（`scripts/concurrency_report.py` 缺失）。
- **改动文件**（均在允许修改清单内）：
  - `程序/scripts/concurrency_report.py`（新建，1–958 行）：纯标准库只读并发与锁机制基线脚本；全程使用 `git --no-optional-locks`，不使用裸 `json.loads`，全部子进程文本捕获显式 `encoding="utf-8"`，路径脱敏不输出本机绝对路径或锁 token，时间窗锚定到 `master` HEAD 提交时间确保连跑两次逐字一致，输出同时写 `程序/logs/concurrency_report.md`。
  - `程序/tasks_round/Git并发锁机制优化任务书.md`（281–285 行）：仅勾选 §6 G0 三项验收并附 R4459 证据，未改正文及 G1–G8。
  - `程序/tasks_round/全量锁卡死治理任务书.md`（233–258 行）：仅对 §6 P0–P2 逐项核码打勾与标注现状，未落地/部分落地项保持空白，未改方案与范围。
  - `程序/tasks_round/tasks_round_4459_result.md`（新建）：本结果文件。
  - `程序/tasks_round/evidence/R4459.json`（提交门禁自动生成）。

## 3. §1 验收线当前基线（`concurrency_report.py` 实测摘录）

基准主干快照：`master` `36ffa9684`（提交时间 `2026-11-25T06:13:15Z`；本车道开工基点 `1abd6d878`）。连续两次执行 `scripts/concurrency_report.py` 输出逐字一致（`RC1=0 RC2=0 STDOUT_DIFF_COUNT=0 FILE_DIFF_COUNT=0`）：

| 验收线 | 2026-11-25 实测基线 | 2026-11-20 基线 | 目标 |
| --- | --- | --- | --- |
| 主干上的非轮次提交 | 24h 内 0 个；近 600 第一父链共 5 个（`5d010101d`、`f583e096a`、`65ba4a86f`、`d52811c3f`、`d27188667`） | 24h 内 2 个（近 600 共 2 个） | 机制上写不进去 |
| 主干根目录未登记条目（F2） | 0 个未登记（`.agents/` 受跟踪 1 个） | 78 个 `.agents/`（主干必红） | 0 |
| 7 天全量红灯段与停留 | 7 段，中位 11.6 小时／最长 34.9 小时（末尾仍在红；56 条有效记录） | 18 段，中位 2.4 小时（最长 24.5 小时） | 合入不引红；环境红 ≤ 20 分钟 |
| 全量历史绿/红统计 | 近 40 次绿 6／红 34（15.0%）；全历史绿 23／红 122（15.9%，剔除 182 条无效行） | 最近 40 次绿 6／红 34（15.0%） | 主干最新绿凭据比例 ≥ 90% |
| 主干最新提交内容树全量绿凭据 | 未覆盖（最近绿凭据 R4264，库内 30 条；`auto-full-safe-result.json` 仍为 `returncode=-1` 受阻） | — | ≥ 90% |
| 合并队列统计与失败率 | 共 39：完成 22、失败 10（25.6%）、待 7、执 0（10 条失败项分支均已删） | 31 条里失败 10 条（32.3%） | 失败率 < 10% |
| 重叠门禁状态 | 三方试合并已上线（活跃窗 24h，试合并缓存 323 条） | 整文件拒绝（R3919/R3922 误拒） | 0 误拒（有回归用例） |
| 工作树数量与状态 | 总 172 棵：脏 14、游离 7、`ahead=0` 164、维护租约 0；`lanes.json` 登记 228（24h 活跃 58） | 76 棵，脏 50，游离 7，`ahead=0` 49，租约 0 | 活跃车道 ≤ 20，无无主脏树 |
| 本地分支数量（F7） | 总 243 个，未合入 `master` 48 个 | 406 / 362 | 停用分支归档 |
| 合并中／变基中残留 | 合并中 0 棵，变基中 0 棵 | 5 棵合并中 | 0，或 `doctor` 有归属 |
| 无主领号（无提交且无结果） | 共 372 个（工作树已删 283、仍在 89；`round-claims.json` 共 1585 条，`last_claimed=R4455`） | 至少 1 个（R3917） | 0，或 `doctor` 有归属 |
| 提交等锁上限／GUI 等锁上限 | 提交 `30.0` 分钟（合并 `30 * 60` 秒）；GUI `1800` 秒（遇全量 `60` 秒）；锁租约心跳 `30.0`s／静默 `180.0`s | 30 分钟／1800 秒 | 提交 5 分钟（P0-2） |
| 共享锁现状（common-dir） | `full-safe-runner.lock` 静默(可回收，PID 99424，R4444，启动 `2026-11-25T02:18:46Z`)；`explicit-commit.lock` 占位/非 JSON；其余 6 把锁不存在；`gui-selftest.queue` 0 票 | — | — |

### 3.1 与任务书 §0.1／§0.1a 实测事实（F1–F24）的现状差异（仅记录，不私改任务书正文）

- **F2（已变化）**：R3945（`5697ac349`）治理分支合入后，主干 `.agents/` 已清理至仅 1 个受跟踪文件且 `.agents` 已登记入 `tests/test_root_layout.py:14` `ALLOWED`，当前主干根目录未登记条目 = 0。
- **F8（已落地，对应 G2）**：R3956（`4081eb82f`，R3961 合入 `91d2d8038`）已将 `维护记录/基准脚本/branch_scope.py` 改为活跃车道（24h）三方试合并（`git merge-tree --write-tree --no-messages -z`）＋common-dir 缓存，并新增 `tests/test_branch_scope_precise.py`（30 条用例）。
- **F17（已缓解）**：`tests/architecture/test_round_baselines.py:35-92` 已增加 `_mainline_snapshot()`，功能分支按 `merge-base(HEAD, master)` 校验主干基点状态页连续性，不再因车道自带最新结果号而误红。
- **F6/F7（数值变化）**：工作树由 76 增至 172（其中 `ahead=0` 164 棵，脏树由 50 降至 14，合并中残留由 5 降至 0）；本地分支由 406/362 降至 243/48。
- **仍成立的既有事实**：F9（`scripts/merge_queue.py:41-55` 仍无 `shared_lock`）、F10/F19（`scripts/merge_round.py:194-223` 在车道已检出时仍调 `_rebase_in`）、F11（`auto-full-safe-result.json` 仍受阻 rc=-1）、F12（`hooks/pre-commit:29,51` 仍未放行 `evidence/R<N>.json`）、F15（`commit_round.py:238` 仍 30 分钟、`selftest_env.py:105` 仍 1800 秒）、F16（Git 2.52.0.windows.1、`rerere.enabled=true`、`extensions.worktreeconfig=true`）、F18（`merge_round.py:444` 仍写死协作者名）、F20（`hooks/commit-msg:81` 仍 `--all --not HEAD`）、F22（队列失败项中 10 条分支已删除仍标 `failed`）、F23（`tests/architecture/_scan.py:25,252` 仍未排除 `logs`；注 `mq-38` `codex/scan-exclude-logs` 在队列待合入）、F24（`commit_round.py:235-239` `--tests` 仍 `nargs="*"`）。

## 4. H1–H6 逐条验证结论与证据（孤立临时仓库实测，未改动真实 `.git`）

环境：`git version 2.52.0.windows.1`，全部 H1–H5 实验均在 `tempfile.TemporaryDirectory()` 中执行并自动清理；H6 结合源码与现网只读 `lanes.json` 统计。

| 编号 | 假设原文（§0.4） | 结论 | 实测证据与对后续轮次的影响 |
| --- | --- | --- | --- |
| **H1** | `reference-transaction` 钩子在 `prepared` 阶段返回非零，可以拦住 `git commit --no-verify` 和 `git update-ref` 对 `refs/heads/master` 的更新；钩子内可执行只读 Git 命令 | **成立** | 临时仓库实测：钩子内在 `prepared` 阶段调用 `git log -1 --format=%s "$new"` 与 `git ls-tree --name-only "$new"` 均正常。① `master` 上 `git commit --no-verify -m "checkpoint before checkout"` 被拒（rc=128，`fatal: ref updates aborted by hook`，`master` SHA 未变）；② 车道分支 `WIP:` 提交放行（rc=0）；③ `git update-ref refs/heads/master <feat_sha>` 被拒（rc=128，`master` 未变）；④ `git update-ref -d refs/heads/master` 被拒；⑤ 合规 `R2: valid commit` 通过（rc=0）。G1 主体拦截可行。 |
| **H2** | 钩子给每次引用更新增加的耗时小于 150 毫秒；20 个提交的 rebase 多耗时不超过 10 秒 | **不成立** | 临时仓库同机对比（无钩子 → 装 `sh` `reference-transaction` 钩子）：① 车道 `update-ref` 均值 `58.2 ms → 135.1 ms`（`+76.9 ms < 150 ms`）；② **`master` `update-ref` 均值 `56.0 ms → 314.2 ms`（`+258.2 ms > 150 ms`）**；③ **20 提交 `git rebase master` 均值 `0.655 s → 11.207 s`（`+10.552 s > 10 s`，约 17 倍）**。主因是 Windows 下每次事务的 `prepared`/`committed`/`aborted` 均派生 MSYS2 `sh.exe`。已同步实测「若不成立」替代路径：利用已启用的 `extensions.worktreeconfig=true`，给车道工作树配独立空 `core.hooksPath` 后 20 提交 rebase 恢复至 **`0.569 s`**。**影响**：G1 须采用按工作树 `core.hooksPath` 仅主工作区安装（并知悉仅主树安装无法拦截在车道树直接执行 `update-ref refs/heads/master`），或改用无 `sh` 派生的原生轻量可执行钩子。 |
| **H3** | Git 2.52 的 `reference-transaction` 能看到主工作区 `HEAD` 的符号引用更新，可以拒绝主工作区切走 master | **不成立** | 临时仓库实测：Git 2.52 确实向 `prepared` 传入 `0000000000000000000000000000000000000000 ref:refs/heads/<target> HEAD`（注意 `old` 为全零而非 `ref:refs/heads/master`），返回非零可拦截 `git switch`／`switch -c`／`checkout`／`checkout --detach`（rc=128，`HEAD` 留在 `master`），且不干扰 `master` 上 `git commit`。**但存在致命误杀**：在主工作区执行 `git worktree add -b <lane> <wt> master` 新建车道时，Git 2.52 以**逐字相同**的 stdin 行（`0000... ref:refs/heads/<lane> HEAD`）和**完全一致**的 `GIT_*` 环境变量（`GIT_DIR` 为空、`PWD` 为主树）调用 `reference-transaction`，钩子无法从协议字段区分「主树切走 `HEAD`」与「主树建新车道初始化其 `HEAD`」，导致 `git worktree add` 被误杀失败（rc=128）。**影响**：按任务书「若不成立」降级，G1 不在 `reference-transaction` 拦截 `HEAD`，改用 `post-checkout` 记录违规＋`doctor` 报红＋合并轮拒绝（`scripts/merge_round.py:367` 已拒绝非 `master`）。 |
| **H4** | `git merge-tree --write-tree --name-only --merge-base=<基> <暂存树> <车道尖>` 能列出真实冲突路径；20 条活跃车道以内、带缓存时不超过 2 秒 | **成立** | 临时仓库复演 R3919/R3922（20 条改 `architecture.md` 不同段落车道＋1 条改同段落冲突车道）：`git merge-tree --write-tree --name-only --merge-base=<base> <staged> <tip>` 对无冲突段落返回 rc=0，对同段落冲突返回 rc=1 并列出 `architecture.md`。调用已落地的 `branch_scope.commit_gate_report`（R3956 `4081eb82f`／R3961 `91d2d8038`）：21 条活跃车道冷跑 `1.581 s`、带缓存热跑 `0.978 s`（检出 1 条真冲突）；去掉冲突车道后 20 条不同段落车道热跑 **`0.835 s`（≤ 2 s）** 且误拒数 = `0`。 |
| **H5** | 在集成树的列车尖上跑出口档，与逐条车道跑出口档等价；按内容树记录的全量凭据在主干快进到同一棵树后可以直接复用 | **成立** | 读码（`selftest_receipts.py:82-91,231-241,291-306,343-350,401-414`、`scripts/local_ci.py:51-55`、`tests/architecture/test_round_baselines.py:43-92`）＋临时仓库端到端演练：分离集成工作树 `.wt/train` 依次 `--no-ff` 合入两条车道后，`rev-parse HEAD:程序` 与 `master` 执行 `git merge --ff-only <train_tip>` 后的 `HEAD:程序` 内容树 OID 完全一致；`record_verified_tree` 写入 common-dir 后主干 `verified_tree_record()` 直接命中复用（round=5）。**G3 实施注意点**：`receipt_checkout_allowed()`（`selftest_receipts.py:231-241`）在非 `master` 的分离树上要求环境变量 `AUTO_FULL_SAFE_HEAD=<train_head>`（或由 `merge_train.py` 显式写凭据），且分离树上 `test_full_safe_all_is_required_after_eight_source_rounds` 因 `is_master_checkout()=False` 会跳过，须由 G3 步 4 显式检查风险路径与全量欠账。 |
| **H6** | 车道每次调用 `dev.py` 顺带续约，足以判断车道是否活着，不需要常驻进程 | **不成立** | 读码＋现网 `lanes.json` 实测：① `scripts/dev.py` 当前**完全未调用** `lane_registry.heartbeat()`（该函数全仓 0 调用点，仅 `round_claim.py:300,604` 在领号/补登时调 `register()`）；② 现网 24h 内有提交的 79 个工作树分支中，仅 57 个在 `lanes.json` 有 24h 内 `last_seen`，**22 个缺失或过期（漏报率 27.8%）**；③ 172 棵现存工作树有 30 棵未登记入 `lanes.json`（含本车道 `git-lock-g0` 领号前），同时 `lanes.json` 存留 85 条工作树已删除的幽灵条目；④ 大量会话/工作卡直接跑 `smoke_test.py`、`run_selftests.py`、`git` 而不经 `dev.py`。**影响**：按任务书「若不成立」建议，G4 除在 `dev.py` 入口顺带续约外，应增 `dev.py lane renew` 并把分支尖提交时间／工作树活动时间与 `lanes.json` 联合判定活跃度（复用 `branch_scope.py:117-132` 口径）。 |

## 5. 《全量锁卡死治理任务书》P0–P2 逐项对账表

已同步在 `程序/tasks_round/全量锁卡死治理任务书.md` §6 对已落地项打勾、未落地/部分项保持空白并附证据。

### 5.1 P 书 §0.2 前置假设核验

- **P-H1（`acquire_gui_lock` 超时后退出释放锁，不挂起）**：**成立**。`selftest_scheduling.py:230-232` 超时输出 `[GUI_DEFERRED]` 并返回 `None`（`finally` line 238 退出排队）；`run_selftests.py:259-265` 记录 `deferred` 并跳出循环；`run_selftests.py:482-483` 返回退出码 `2`；`finally`（`:495-500`）反注册 `atexit` 并调用 `release_full_safe_lock(lock)`。
- **P-H2（`pre-commit` hook 独立检查验收锁且不按分支豁免）**：**不成立（已按分支豁免）**。`维护记录/基准脚本/hooks/pre-commit:8-14` 自 R2298（`c6ffbdaa0`）即仅对 `""|master|main` 检查 `full-safe-selftest.lock`，工作分支已豁免；且 ADR-0015（`5d010101d`／R3934 `81140ca11`）起全量改持 `full-safe-runner.lock` 不再创建 `full-safe-selftest.lock`。

### 5.2 P 书 §6 验收勾选清单（21 项）

| 阶段 | 清单项 | 状态 | 打勾 | 代码／提交证据与现状一句话 |
| --- | --- | --- | --- | --- |
| P0 | H1 已验证并记录结论 | ✅ 已完成 | `[x]` | 本轮 R4459 已核验成立：`selftest_scheduling.py:230-232`、`run_selftests.py:259-265,482-483,495-500`。 |
| P0 | H2 已验证并记录结论 | ✅ 已完成 | `[x]` | 本轮 R4459 已核验不成立（已豁免工作分支）：`hooks/pre-commit:8-14`（R2298 `c6ffbdaa0`）。 |
| P0 | `heartbeat` 字段写入锁 | ✅ 已完成 | `[x]` | 统一租约 `维护记录/基准脚本/lock_lease.py:24-35` 写 `heartbeat_at`＋`token`，`selftest_scheduling.py:31` 调用（提交 `5d010101d`／R3934 `81140ca11`）。 |
| P0 | 心跳刷新线程接入 `run_selftests.py` | ✅ 已完成 | `[x]` | `selftest_scheduling.py:46,55,83` → `selftest_env.py:289-294` → `lock_lease.py:152-192`（30s daemon 线程），`run_selftests.py:366,370,500` 持锁/释放（`5d010101d`）。 |
| P0 | `_holder_stalled` 实现于 `selftest_env.py` | ✅ 已完成 | `[x]` | 等效统一实现：`selftest_env.py:275-286`（`holder_is_live`/`inspect_lock`/`reclaim_stale_lock`）→ `lock_lease.py:18,38-128`（静默阈值 180s，`5d010101d`）。 |
| P0 | `commit_round.py:134` 接入卡死判定 | ✅ 已完成 | `[x]` | `scripts/commit_round.py:208-229`（现 `:219-222`）调 `reclaim_stale_lock`，回归用例 `tests/test_commit_round.py:125-134`（`5d010101d`）。 |
| P0 | `selftest_scheduling.py:49` 接入卡死判定 | ✅ 已完成 | `[x]` | `selftest_scheduling.py:40-54` 调 `inspect_lock`＋`reclaim_stale_lock`，回归用例 `tests/test_pid_reuse_tokens.py:71-80`（`5d010101d`）。 |
| P0 | 旧锁无心跳字段的兼容路径 | ✅ 已完成 | `[x]` | `lock_lease.py:49-60` 缺 `heartbeat_at` 时退回 `legacy_pid_alive`＋`started_at`/`created_at`（`5d010101d`）。 |
| P0 | 未来心跳不误判 | ✅ 已完成 | `[x]` | `lock_lease.py:46` `(now - float(beat)) < LOCK_STALE_SECONDS` 未来心跳恒活，`selftest_env.py:235-236` 亦护旧锁未来时间（尚缺专项单测）。 |
| P0 | `--wait-minutes` 默认 5.0 | ❌ 未做 | `[ ]` | `scripts/commit_round.py:238` 仍 `default=30.0`，`scripts/merge_round.py:427` 仍 `30 * 60`。 |
| P0 | `tests/test_selftest_lock_liveness.py` 5 条用例全绿 | 🟡 部分 | `[ ]` | 该文件不存在；活/静默心跳回收分散于 `test_commit_round.py:114-142`、`test_pid_reuse_tokens.py:61-81`、`test_round_claim.py:468-496`，缺未来心跳与 `--wait-minutes == 5.0` 用例。 |
| P0 | smoke 8/8 | ❌ 未做 | `[ ]` | P0 尚余 `--wait-minutes` 与专项测试未落地，待补齐后验收。 |
| P0 | 结果文件已写 | ❌ 未做 | `[ ]` | 尚未合入 P0 独立收尾轮结果文件（历史 `codex/wip-r3839` 中断未合入，见 R3944）。 |
| P1 | H1 结论驱动 `GUI_WAIT_SECONDS` 改值或改 raise | 🟡 部分 | `[ ]` | `selftest_env.py:105` `GUI_WAIT_SECONDS` 仍 `1800`；但 ADR-0015 已加 `GUI_FULL_SUITE_WAIT_SECONDS = 60`（`:106`、`selftest_scheduling.py:206-209`）与全量波次归还（`run_selftests.py:240-282,439`）。 |
| P1 | 超时信息含心跳距今时长 | ❌ 未做 | `[ ]` | `scripts/commit_round.py:226,321` 与 `selftest_scheduling.py:157-173,186-190` 均未打印心跳距今时长。 |
| P1 | `-k selftests_gui_token` 全绿 | ❌ 未做 | `[ ]` | P1 未实施；现有 `tests/test_selftests_gui_token.py:422-470` 已覆盖 60s 封顶与波次归还。 |
| P2 | 提交路径无 `wait_for_lock` 引用 | 🟡 部分 | `[ ]` | ADR-0015 已让全量改持 `full-safe-runner.lock`（`selftest_scheduling.py:66`）不再建提交锁，但 `commit_round.py:208,320` 与 `merge_round.py:427` 仍留 `wait_for_lock`；另 P2-2 分层全量已被 ADR-0015 `:15,:37` 否决（⏭️ 不适用）。 |
| P2 | 未跑全量时可提交 | ✅ 已完成 | `[x]` | ADR-0015（`5d010101d`／R3934 `81140ca11`）全量仅持 `full-safe-runner.lock`，不挡提交，异步由 `auto_full_safe.py` 补跑，`tests/architecture/test_lane_flow_gates.py` 守卫。 |
| P2 | 凭据过期仍被 hook 拦 | 🟡 部分 | `[ ]` | 欠账/过期拦截在 `tests/architecture/test_round_baselines.py:121-145`（架构/出口门禁），`hooks/post-commit:7-8` 异步告警补跑；`hooks/pre-commit` 未内置凭据过期检查。 |
| P2 | 全量 `--all --safe` 绿 | ❌ 未做 | `[ ]` | 当前主干树未取得绿凭据（最近 R4264），近 40 次全量历史绿 6／红 34。 |
| P2 | 观察一周无回归 | ❌ 未做 | `[ ]` | P0/P1/P2 未收尾，未进入观察期。 |

## 6. 验收命令与输出尾部

1. 连续两次运行 `scripts/concurrency_report.py` 并比对 stdout 与 `logs/concurrency_report.md`：
   - 退出码：`RC1=0`，`RC2=0`
   - 差异：`STDOUT_DIFF_COUNT=0 FILE_DIFF_COUNT=0`
2. 默认冒烟 `smoke_test.py`：
   - 退出码：`0`
   - 尾部原文：
     ```
     ==================================================
     通过：9 项
     失败：0 项
     ==================================================
     ✅ 冒烟测试通过，可以进入下一轮
     ```
3. 架构门禁 `smoke_test.py --architecture`：
   - 退出码：`0`
   - 尾部原文：
     ```
     ----------------------------------------------------------------------
     Ran 708 tests in 328.636s

     OK
     ✅ 架构治理测试：tests/architecture
     ```

## 7. 未验证项与卡外发现（只记录不顺手修）

- **未验证项**：本轮未运行 `run_selftests.py --all --safe`（按卡面只读基线轮口径不跑全量）；未在真实仓库安装任何新钩子（严守 §0.4 纪律）。
- **卡外发现**：
  1. **G2 实际已落地但任务书 §6 G2 未勾选**：R3956（`4081eb82f`／R3961 合入 `91d2d8038`）已在 `branch_scope.py` 与 `tests/test_branch_scope_precise.py` 实现 G2 三方试合并门禁，后续规划 G 书排期时可直接对账核销，避免重复派工。
  2. **H2／H3 对 G1 的直接设计约束**：G1 不可把 `sh` 版 `reference-transaction` 全工作树安装（20 提交 rebase 慢 17 倍），也不可在 `reference-transaction` 里拦截 `HEAD`（会误杀主工作区的 `git worktree add`）。
  3. **现网遗留状态膨胀**：工作树已达 172 棵（其中 `ahead=0` 164 棵，远超规则上限 20）、无主未提交领号 372 个、`lanes.json` 含 85 条已删工作树幽灵项、`full-safe-runner.lock` 留有 PID 99424（R4444）的静默锁、合并队列 10 条历史失败项分支已全部删除且 `mq-35..mq-39` 尚在 `pending`；留待 G4／G5 处理。
  4. **`commit_round.py` 路径口径与 `commit_retry.py` 失败回执锁死**：`scripts/commit_round.py:162` 在 `cwd=PROGRAM` 下执行 `git add`，传相对仓库根的 `程序/...` 路径会报 `could not open directory '程序/程序/'`；而 `commit_retry.Receipt.start()` 在 `stage_inputs()` 之前就落盘了 `explicit-commit-receipts/R<N>.json`，导致路径写错一次即烧掉该轮次号（本轮首次领号 R4456 因此中止并重领 R4459）。建议 G4 改 `dev.py`/`commit_round.py` 时在 `receipt.start()` 前先校验路径或支持仓库根路径。
  5. **提交状态**：通过 `scripts/dev.py commit` 提交至 `codex/git-lock-g0`（本文件由提交门禁补盖 `round-evidence` 机器头）。
