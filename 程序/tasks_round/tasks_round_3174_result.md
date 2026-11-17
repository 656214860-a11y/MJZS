# R3174 结果——车道 role 指定持久化（lane_registry.register 缺省不覆盖）
<!-- round-evidence: {"commit_base": "2cab1882", "credential_hits": 0, "evidence_sha256": "43ce6535ce8b0e22", "exit": 0, "failed": 0, "passed": 10, "round": 3174, "tests": "run_selftests.py -k lane_merge_queue"} -->

## 三问

1. **轮次类型**：§3.2 修复轮（治理脚本自身缺陷，属并行吞吐治理任务书 B3 交付件范围）。
2. **测试**：定向 `run_selftests.py -k lane_merge_queue` 10/10 绿（新增 1 条 `test_unspecified_role_preserves_existing_and_defaults_dev`）；`smoke_test.py` 9/9 绿；架构门禁由合并轮 exit-CI 执行。
3. **欠账**：少了——车道 role 指定此前会被每次领号重置为 dev，专职道（merge/gui）登记名存实亡；本轮修掉。

## 根因

`lane_registry.register()` 签名 `role: str = "dev"`：`round_claim.next()` 领号时无参调用 → `"dev" in ROLES` 为真 → 每次领号把已指定的 `gui`/`merge` role 重置回 `dev`。用户拍板的"专职合并道（漫剧制作助手→merge）/GUI 专道（devin-dead-symbols→gui）"登记无法持久。

## 改动

- `维护记录/基准脚本/lane_registry.py`：`register()` 的 `role` 默认改为 `None`；未指定时归一为空串走既有回退分支，保留 `entry` 里已登记的 role（新车道仍缺省 `dev`）；显式传合法值才改写。`heartbeat()`/领号路径不传 role，语义自动变为"只刷心跳，不动指定"。
- `tests/test_lane_merge_queue.py`：新增用例覆盖「指定 merge 后无参 register 不回退」「新车道无参登记默认 dev」。

## 关联 ops（不入本提交）

- `lanes.json`（`.git` 数据，不跟踪）：合并后由合并道执行 `register(root=漫剧制作助手, role="merge")` 一次性指定；`devin-dead-symbols` 已登记 `role: gui`，本轮修复后其领号心跳不再回退。
- A2 清理执行：PARKED 106 支已全部归档 `refs/archive/parked/<分支名>` 并 `git branch -D` 删除；另有 21 个 MERGED 分支（含 codex/fullsafe-int8）`-d` 删除；fullsafe-int8/master-check/audit-base/manju-master-inspect 4 棵游离或空转工作树已移除。

## 提交

分支 `codex/lane-role`，随提交补记 hash。
