# R3111 运维轮结果（A2 死分支盘点＋台账提速＋脏树协议）
<!-- round-evidence: {"commit_base": "070cb446", "credential_hits": 0, "evidence_sha256": "7729e3d05fae8dd0", "exit": 0, "failed": 0, "passed": 7, "round": 3111, "tests": "run_selftests.py -k worktree_ledger"} -->

- 轮次类型：运维轮（任务书 A2；只读盘点＋基准脚本增强＋规则文本，不删任何分支/工作树）
- 三问：①类型＝运维轮；②测试跑了：`run_selftests.py -k worktree_ledger` 7/7 绿、`smoke_test.py` 9/9 绿；架构门禁未单独跑（基准脚本非产品层，smoke 已含架构快检）；全量欠账未变；③欠账未变
- 交付：
  1. `worktree_ledger.py` 提速 **~90s→4.1s**（实测）：per-worktree 探测改 ThreadPoolExecutor(8) 并行；`branch_snapshot()` 用一次 `for-each-ref %(ahead-behind)` 取全部分支 ahead/behind/提交时间/工作树归属，替代每树 2 次 rev-list＋1 次 show；detached 仍走原 rev-list 回退
  2. 新增分支维度盘点 `collect_branches()`＋`--branches` 表＋plan 追加 `git branch -d` 候选（仅 MERGED 且无工作树）；分类：MERGED 369／PARKED 103／ACTIVE-WT 21／STALE 0（全部 <7 天）
  3. `git cherry master` 补丁等价核验 103 个 PARKED：**18 个全 '-'＝内容已在主干**（真「已合入」候选），85 个有独有补丁
  4. `runbook.md` §12 新增「脏树处置协议」：三类裁定（草稿/已跟踪改动/百级活树）、rescue 补丁存 `<common-dir>/rescue/`、分支只走 `git branch -d`、cherry 等价核验口径
  5. `git config rerere.enabled true` 已写入 common-dir（重复台账冲突自动复用解法，零成本启用）
- 删除清单（待用户逐条确认，本轮未执行任何删除）：
  - 工作树 RECYCLE 12 棵（ahead=0 空转树，plan 已列命令）
  - 分支 MERGED 无工作树 ~339 个（`git branch -d` 自带未合并保护）
  - PARKED 中 patch-merged 18 个（cherry 全 '-'，内容已在主干）
  - BLOCK 5 棵游离 HEAD 树需先落分支或人工裁定（Temp 审计树、.wt/ci 等）
  - 25 棵脏树 KEEP：wip-R3060(461 文件)/wip-R3088(105)/wip-R3099(16)/wip-R3054(25) 等百级活树不动；草稿级 ?? 残留按协议先 rescue 再确认
- 风险记录：并行探测只读、不写仓库状态；for-each-ref 批处理在 git 2.52 可用（%(ahead-behind) 需 ≥2.41，已实测）；Windows 下 8 线程 subprocess 无冲突
- 提交：分支 `codex/gov-v2`，`dev.py commit` 后回填；合入 master 走正常合并轮
- 遗留：删除执行须用户逐条确认（任务书 D2 硬门槛）；PARKED 85 个有独有补丁的分支属「在途/归档」候选，不在本次删除范围
</file_path> D:\漫剧制作助手\.agents\worktrees\gov-v2\程序\tasks_round\tasks_round_3111_result.md