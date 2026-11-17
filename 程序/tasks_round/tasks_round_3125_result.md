# R3125 B3 修复：merge_queue 走 agent.core.read_json（架构门禁第四项）
<!-- round-evidence: {"commit_base": "118ff08f", "credential_hits": 0, "evidence_sha256": "bcdb5559d628141e", "exit": 0, "failed": 0, "passed": 13, "round": 3125, "tests": "run_selftests.py -k lane_merge_queue unification_ratchet"} -->

## 三问

- **类型**：修复轮（R3120 合并轮 exit-CI 架构门禁红 → 根因修复）。
- **测试**：`run_selftests.py -k unification_ratchet lane_merge_queue` 13/13 绿；enqueue/list 实测通过。
- **欠账**：无新增；本轮即闭环 R3120 合并被拦的欠账。

## 根因与修复

`merge_queue.py` 在 `scripts/` 审计面内裸用 `json.loads`，命中 `test_unification_ratchet` 第四项「bare json load 债务非增」——合并轮 exit-CI 在架构门禁失败，B1 新流程正确中止且未烧号（R3121 合并轮验证了该语义）。

修复：`_read` 改经 `agent.core.read_json(path)`（程序既有宽松读唯一实现，缺失/损坏返回 default）；`sys.path` 注入 `程序/` 使 `agent` 包可导入。`json.dumps` 不在审计面，`_write` 不动。

## 提交

- `程序/scripts/merge_queue.py`
- 本结果文件、`tasks_round/evidence/R3125.json`

## 三个基线

- 冒烟：前轮 9/9，本轮改动为读取路径替换，定向 13/13 绿
- 架构门禁：unification_ratchet 4/4 绿（原红项转绿）
- 全量：分支不累计欠账

## B1 流程实战验证（附记）

本次合并失败恰好实测了 R3117 设计：merge --no-commit → exit-CI 红 → 自动清理本分支合并态 → 未领号不占轮次 → master 无残留。`git status` 合并后干净。

[TASK_COMPLETE]
