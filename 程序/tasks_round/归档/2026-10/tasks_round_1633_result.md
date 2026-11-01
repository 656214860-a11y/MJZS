# R1633 批量规划与持久队列的本地口径（联调/测试 T6）

- 本轮类型：§3.10 验证/基线轮（来源：阶段4 只读评估清单 T6 的“先补本地可测两条”）。
- 测试跑了吗？跑了。定向 `tests/test_perf_batch_queue.py` 3/3（5.5 秒）；默认冒烟 8/8；架构门禁 356/356。三个基线全过。
- 欠账少了吗？没有新增：只改 `tests/`、`说明/`、状态页与交接文件，按 §5 不计源码轮；未跑全量，最近真实全量仍是 R1624（13dea0a），不冒称同树全量。

## 交付

1. `tests/performance_contract.py` 新增 `BATCH_PLAN_PER_SHOT_MS = 5.0`、`QUEUE_ITEM_MS = 400.0`，附实测口径注释（含成本构成）。
2. 新增 `tests/test_perf_batch_queue.py`（3 用例）：文件名以 `test_perf` 开头，按 `run_selftests.split_performance_units` 的既有规则自动进串行性能池，不需要改 runner。
   - `test_planning_cost_per_shot_stays_within_the_recorded_budget`：`keyframe_batch.batch_plan` 在 50 镜／200 镜上各热身后取中位：**0.52／0.48 ms 每镜**（上限 5 ms），并断言目标集＝一半镜头（保证耗时不是空转）。
   - `test_enqueue_and_claim_cost_stay_within_the_recorded_budget`：生产上限 `QUEUE_LIMIT`＝10 的持久队列，逐项入队与领取计时（**入队中位约 132 ms、领取约 123 ms**，上限 400 ms），并验第 11 项被拒、每项恰好领取一次、领完为空。
   - `test_claim_order_is_priority_then_arrival`：领取顺序＝优先级降序、同级先到先领（用固定 `clock` 去掉时间扰动）。
3. `说明/联调测试出口基线.md`：§1 新增“批量与队列（本地）”行并改写 P95 行（保留并发／弱网缺口）、§6 T6 转完成、§7 检查单补“改批量／队列／事务后必须重测”。

## 本轮探到的范围外瓶颈（只登记，未改）

- 持久队列每项约 130 ms 里，约 100 ms 是 `agent.publication.transaction()` 的目录扫描：同一个临时项目下单独实测 `read`≈0.8 ms、`save`≈4 ms、`access`≈0.4 ms、`transaction`≈**80–205 ms**（`access` 会 `ROOT.iterdir()` 并对每个 32 位名目录跑 `_recover`）。
- 影响面：生产队列上限 10，最坏一次连续入队约 1.3 秒；`enqueue_descriptor` 是否在 UI 线程调用决定用户是否看到卡顿——本轮没有实机 Tk 证据，不下结论。
- 为什么不在本轮修：改 `transaction` 的扫描范围会动跨进程发布事务的语义（回滚／恢复），与本轮“只加口径”的范围不同，且需要专门的并发／崩溃复验。已写进 `performance_contract.py` 注释与 §1 行，供后续单独立轮。

## 未覆盖（如实登记）

- 并发提交吞吐、编码队列积压、弱网／高延迟分布：未测；供应商延迟属外因，按评估口径只登记不进门槛。
- “队列压力下 UI 响应”：需要实机 Tk，本文件是纯服务层口径，不冒称覆盖。
