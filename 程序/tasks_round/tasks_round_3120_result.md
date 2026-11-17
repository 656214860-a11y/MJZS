# R3120 并行吞吐治理-B3 lanes.json 车道注册+租约心跳+ahead 源码口径+合并队列
<!-- round-evidence: {"commit_base": "df68b9f2", "credential_hits": 0, "evidence_sha256": "dc56e7229cfb5be0", "exit": 0, "failed": 0, "passed": 27, "round": 3120, "tests": "run_selftests.py -k lane_merge_queue round_claim merge_queue"} -->

## 三问

- **类型**：功能轮（任务书 B3，治理基建）。
- **测试**：`run_selftests.py -k lane_merge_queue round_claim` 27 条全绿（含新文件 9 条）；`smoke_test.py` 9/9。
- **欠账**：无新增。

## 交付物

| 任务书 B3 项 | 实现 |
|---|---|
| `lanes.json` 车道注册 | `维护记录/基准脚本/lane_registry.py`：`<git common-dir>/lanes.json`，字段 lane/branch/worktree/owner/role/last_seen/registered_at；`role ∈ {dev, gui, merge, ci}`；原子写、损坏降级空表；`claim_next` 领号成功后自动登记心跳（尽力而为绝不阻断领号） |
| 车道查看 | `round_claim.py lanes` / `dev.py lanes`：列出各车道 role/owner/idle_hours，失联（>7 天无心跳）标 `[STALE]`——**只警告不阻断、不自动删** |
| 租约心跳 | `round_claim.py renew <task> --owner X [--lease-minutes N]` / `dev.py` 同名入口：owner 续约 `lease_until`，他人或未认领态拒绝；`_note` 留痕 |
| ahead 源码口径 | `require_worktree_fresh` 改 `git rev-list --count master..branch -- ":(top,glob)**/*.py" ":(top,glob)**/*.pyw"`：只数源码提交，纯文档/结果文件/台账提交不再触发 rebase；`:(top,)` 锚定仓库根（修掉 cwd 在子目录时 pathspec 失效的回归）；rev-list 出错回退无过滤口径（保守） |
| 合并请求队列 | `scripts/merge_queue.py` + `dev.py merge-queue`：`enqueue <branch> -s 说明` 亚秒登记（同分支 pending/serving 去重）；`serve` FIFO 调 `merge_round.py` 执行；serving 超龄 45min 自动回队；failed 留痕不自动重试；轮次仍由 merge_round 原生领号 |

## 设计说明

- **并存策略**：`dev.py merge` 直接合并仍可用，队列是可选加速层；enqueue 去重 + merge_round 前置检查兜底，不会双合并。
- **B0 结论落地**：mergetrain spike 证明「请求-执行分离+FIFO+租约」方向正确，但其 SQLite/批准流与本仓轮次号/证据/状态页协议不兼容——本队列吸收核心三件套，协议由 merge_round 原生产出（见任务完成文件 B0 条）。
- **失联语义**：lanes.json stale 与 merge_queue serving 超龄都只回队/警告，不 abort 不删除——与 A2/R3117 的「不自动破坏他人现场」一致。

## 提交

- `程序/维护记录/基准脚本/lane_registry.py`（新）
- `程序/维护记录/基准脚本/round_claim.py`（源码口径+心跳+lanes/renew CLI）
- `程序/scripts/merge_queue.py`（新）
- `程序/scripts/dev.py`（lanes/merge-queue 子命令）
- `程序/tests/test_lane_merge_queue.py`（新，9 条）
- `程序/tests/test_round_claim.py`（ahead 测试提交物 .txt→.py，契约随口径变更同步）
- 本结果文件、`tasks_round/evidence/R3120.json`

## 三个基线

- 冒烟：9/9 通过
- 架构门禁：未触及架构层
- 全量：分支不累计欠账

## 风险与回滚

- 源码口径变宽（文档提交不计 ahead）：最坏情况是文档型分支可攒更多提交，但 rebase 成本本就近零；源码深分仍被 >10 拦截。回滚：pathspec 改回无过滤 rev-list。
- lanes.json/merge-queue.json 都在 git common-dir，不进版本库，不污染工作树。回滚：删两个新文件+还原 round_claim/dev.py。

[TASK_COMPLETE]
