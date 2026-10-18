# R1693 修复轮（开发基础设施）：后台自动全量通道的两个真实失败模式

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（改的是自检器与扫描口径，按 R1635 先例计源码轮）。对象是 `scripts/auto_full_safe.py`（后台补跑全量的唯一入口）与两处「生产模块」扫描口径。不碰产品行为。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k auto_full_safe coverage_baseline coverage_audit_ratchet layers agents_md` **69/69**；`tests/test_auto_full_safe.py` 由 9 条扩到 **22 条**；真机四步验证工作树（新建／复用／重建／加锁）；`auto_full_safe.py --status` 提示已改口。**安全全量改由修好的通道自己跑（见 D）**，不手跑第二遍。
3. **project_status.md 的欠账少了吗？** 本轮改源码 → 欠账 +1；修复后的后台全量会把它清零（D 节回填）。

## A 根因一：沙箱会话里提交 → 全量必崩在进程池，却被记成「测试未通过」

- 证据：`logs/auto_full_safe.log` 里是 `concurrent.futures.process.BrokenProcessPool: A child process terminated abruptly`，78 秒结束；提交输出长期挂着一句「上次后台全量未通过」。而同一台机器上手动跑 `--all --safe` 是 5806 条 0 红。
- 根因：钩子是 `git commit` 的子进程，**继承了提交所在会话的限制**。在受限会话里提交时，后台全量无法派生工作进程，必然 78 秒崩；它不是测试失败。
- 修复：`_run_locked()` 建工作树之前先 `spawn_problem()` 预检（`ProcessPoolExecutor` 提交一个 `int('1')`）。不可用就**不建树、不跑、不写凭据**，结果文件写 `blocked` 与 `BLOCKED_CODE=-1`；`failure_notice()` 先说「环境不允许派生工作进程，不是测试失败」，并给出可执行的下一步。历史结果没有 `blocked` 字段时，用 `blocked_reason()` 按日志特征（`BrokenProcessPool` 等）就地改口，不翻旧账。

## B 根因二：`.wt/ci` 半成品或被回收 → 找不到 `run_selftests.py`

- 证据：同一日志里另有 `FileNotFoundError: ...\.wt\ci\程序\run_selftests.py`。
- 根因：`.wt/ci` 是链接工作树，`workspace_maintenance.worktree_verdict()` 会把「已并入 HEAD＋干净」的 `.wt` 工作树当可再生残留回收。全量跑在树上时被一次应用退出清掉，就是「找不到脚本」；下次 `_sync_clean_worktree()` 见到残留目录只做 `checkout`，于是带着没有脚本的树去跑，再假红一次。
- 修复：①同步后**强制校验** `程序/run_selftests.py` 存在，缺了就 `unlock → remove --force → prune → 重新 add` 一次，仍缺就抛错（不再拿坏树跑）；②工作树建好即 `git worktree lock --reason "auto full safe"`，`worktree_verdict()` 对 locked 一律保留——从源头断掉「边跑边被清」。

## C 连带风险（本轮自己踩到的）：常驻 `.wt/ci` 会把生产模块数第二遍

- 现象：`.wt/ci` 一常驻，`_scan.production_runtime_files()` 就同时数到 `程序/model_pool.py` 和 `.wt/ci/程序/model_pool.py`，`test_coverage_baseline` 立刻红（实测 `287 != 284`）。
- 修复：两处扫描口径同时加入 `.wt`（检出副本不是第二批模块）与 `.selftmp`（自检临时区，探针脚本不是产品模块，一次残留就能把门禁弄红）。`tests/architecture/_scan.py` 与 `scripts/coverage_report.py` 保持一致，基线模块集合不变（284）。新增 2 条用例钉住这两条排除项与「工作树副本不进生产口径」。

## D 验证

| 项 | 结果 |
| --- | --- |
| `tests/test_auto_full_safe.py` | **22/22**（原 9 条 + 环境阻塞 6 条 + 工作树 3 条 + 扫描隔离 2 条 + 原有的 2 条改口） |
| 定向四门禁 | **69/69**（`auto_full_safe`／`coverage_baseline`／`coverage_audit_ratchet`／`layers`／`agents_md`），且 `.wt/ci` 真实存在的情况下跑过 |
| 真机工作树四步 | 新建→`程序/run_selftests.py` 存在；复用具同一目录；`worktree remove --force` 后**自动重建**；`git worktree list --porcelain` 显示 `locked auto full safe` |
| `--status` | 由「上次后台全量未通过…」改为「上次未能测量：环境不允许派生工作进程…不是测试失败…原因：BrokenProcessPool」 |
| 安全全量 | 改由修好的通道（`auto_full_safe.py --run`）自己跑，见回填 |

## E 边界与未做

- **不改变「谁该跑全量」的规则**：欠账阈值仍唯一由 `run_selftests` 决定，本脚本不新增数字。
- **沙箱会话里仍然跑不了全量**——这是环境限制，不是本脚本能绕过的。修的是「别再假装它跑过、别再报假红」，不是「让沙箱能派生进程」。所以：受限会话里提交后，提示会明说请在非沙箱会话手跑。
- `.wt/ci` 锁住后，人工删除需先 `git worktree unlock .wt/ci`；已在脚本 docstring 语义内，未写进用户文档（属开发内部）。
- 未处理：同一会话里连续提交触发的防抖（`QUIET_SECONDS`）行为未改。

## 提交

（见收尾提交与回填。）
