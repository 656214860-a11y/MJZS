# R3117 功能轮结果（B1 合并提速与看门狗）
<!-- round-evidence: {"commit_base": "d1854eb8", "credential_hits": 0, "evidence_sha256": "4f62229661de28f9", "exit": 0, "failed": 0, "passed": 22, "round": 3117, "tests": "run_selftests.py -k merge_round commit_round full_safe_merge_gate"} -->

- 轮次类型：功能轮（任务书 B1；改合并关键路径，不改合并语义与门禁强度）
- 三问：①类型＝功能轮；②测试跑了：`run_selftests.py -k merge_round commit_round full_safe_merge_gate` 22/22 绿（含新增 2 条）；③欠账未变
- 交付（`scripts/merge_round.py`）：
  1. **B1-a 锁等待后移**：删除合并前 `wait_for_lock`；新流程 merge --no-commit → exit-CI → 等锁 → 领号 → 提交。merge+CI（约 5 分钟）与后台全量并行，串行段只剩等锁→提交；exit-CI 为静态/架构/冒烟，无计时型用例，并发不影响判定
  2. **领号移到 CI 后（烧号修复）**：CI 失败、等锁超时均发生在 `claim_next` 之前 → 不再白白烧轮次号，修 N==M+1 断档的来源之一
  3. **MERGE_HEAD 僵死看门狗**：新增 `merge_head_age_seconds()`（`git rev-parse --git-path` 兼容工作树私有 gitdir）＋`MERGE_HEAD_STALE_SECONDS=45min`（覆盖等锁上限 30min＋CI 余量）；超龄在 merge 拒绝时打印报警与人工处置指引，**不自动 abort**（R2564 纪律）
  4. **提交失败现场还原**：`commit_round.main` 非 0 且 MERGE_HEAD 确属本分支 → `abort_merge` 还原，消除 R2958 类僵死合并隐患
  5. runbook §13 合并流程描述同步；模块 docstring 同步
- 未做（任务书记载）：合并请求队列接口留待 B3 lanes.json 一并实现（B0 spike 结论＝自建）；B1-b docs-only 豁免、B1-c 提交豁免验收锁维持 ❓ 不做（风险未解除）
- 风险：exit-CI 与在跑全量并发可能给 `test_perf_baseline` 带来 CPU 噪声——该用例近两轮已判环境性抖动，C2 全量复核；若复发红再评估 B1-c
- 提交：分支 `codex/gov-v2`，`dev.py commit` 后回填；合入 master 走正常合并轮（届时新流程首次实战）
