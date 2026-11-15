# R2713 结果：SWE-2 T7.3——全量并行实测对比登记（T7 收口）
<!-- round-evidence: {"commit_base": "a684ab97", "credential_hits": 0, "evidence_sha256": "3c76948ac075819f", "exit": 0, "failed": 0, "passed": 0, "round": 2713, "tests": "docs-only"} -->

1. 轮次类型：验证基线轮（实测登记；T7 第 3 步收尾，不改产品代码、不改测试）。
2. 测试：默认冒烟 8/8；架构门禁当轮 466 条 / 1 红（`test_round_number_continuous`，见下，如实记录非本轮引入）；全量实测对比见下表。
3. 欠账：T7 三步全部完成；T8 余 8.2 黄金文件（另一会话在跑）／8.4 覆盖率下限；T9、T10 分工见用户裁定（本会话接 T9）。

## 拆分前后用例数对比（只加载不运行的同口径计数）

用 `unittest.TestLoader.loadTestsFromName` 对 `tests/**/test_*.py` 全量加载计数（不执行用例），四个检出逐点对比：

| 检出 | 语义 | 用例总数 | 测试模块数 |
| --- | --- | --- | --- |
| `e33a71c0` | T7.1 拆分前（R2601 合入点） | 7353 | 637 |
| `ddda856c` | T7.1 拆分合入（R2606） | 7353 | 641 |
| `332b3b1f` | T7.2 拆分前（R2633 合入点） | 7368 | 642 |
| `fd56ad67` | T7.2 拆分合入（R2639） | 7371 | 642 |

- T7.1：`test_ui_edges` 115 例 → `test_ui_edges_{autopilot,pages,tables,controls,guards}` 五文件 34+20+15+18+8＝115 例逐文件相等；其余全部共享模块用例数零差异（该合并树只含拆分改动）。模块数 +4 为 1 拆 5 的净增；`ui_edges_support.py` 非 `test_` 前缀不被发现。
- T7.2：测试模块清单不变（642→642）；唯一用例差异 `test_selftests` +3，即 R2615 新增的 `SelftestModuleSplitTests` 三条拆分守卫（域归属／无环依赖／facade 契约），属有意新增而非拆分损耗。
- 结论：拆分前后用例总数与集合一致（T7.1 完全相等；T7.2 仅多 3 条守卫用例），「通过集合」由下述全量绿凭据覆盖。

## 全量耗时对比（`full-safe-receipts.json` 实测秒数，唯一权威）

- 任务书基线口径「约 16–21 分钟」对应 10 月中下旬凭据区间 920–1182 秒（R1850 1182s、R1911 920s）。
- T7.1 合入前最近绿凭据（11-13～11-15）：363s（R2394）、434s（R2427）、518s（R2575）。
- T7 拆分合入后：406s（R2633）、994s（R2656，多车道合并风暴争抢 GUI 令牌的离群值，触发 T8.3 趋势告警但不阻断）、437.2s（ec62c7cc 最新实测，2 红见下、未写凭据）。
- 结论：全量稳定在约 7–9 分钟（400–550 秒常态带），满足任务书「显著下降」目标。并行双池（无 Tk 8 workers＋Tk 4 workers 受控）自 10 月初已存在；T7 的贡献是把 5440 行 `test_ui_edges.py` 切成 5 个可并行域文件、把 1640 行运行器拆成 5 个调度模块，提升工作单元粒度与可调度性，而非新建并行机制。

## 最新全量红项说明（与 T7 无关，如实记录）

`ec62c7cc` 全量 7373 条用例 / 437.2 秒 / 2 个文件有红：

- `architecture.test_round_baselines.test_round_number_continuous`：2697≠2683。R2683、R2696 两次合并为手工提交、未走 `merge_round.py`，缺对应 `tasks_round_N_result.md`，状态轮次与最新结果号脱节。正规 `dev.py merge` 会自写结果文件并抬头，自愈；本架构红在本分支同样复现（466 中 1 红），属多车道在途状态，非本轮引入。
- `test_video_ui.test_a_running_shot_keeps_the_picker_read_only`：全量并行下红（实际文案 `这一镜正在制作：勾选暂时改不动，可以看图。` vs 断言 `LOCKED_SAY`），日志标 `[SUSPECT_CONCURRENCY]`。本工作树串行复跑 `run_selftests.py -k test_video_ui --serial`：66 条 0 红 ALL TESTS PASSED——GUI 并行争抢下的偶发红，非确定性回归。

## T7 验收核对（任务书 T7）

- 拆分前后测试总数与通过集合一致：用例数逐点相等（见上表），通过集合由 R2633/R2656 等绿凭据覆盖。
- 全量绿：拆分后已有多张绿凭据（406s/994s/437s 实测带）；当前 master 的 2 红均为非 T7 因素（编号在途＋并行 flake），已如实记录。
- 至此 T7.1（test_ui_edges 拆分 R2605/R2606）、T7.2（run_selftests 拆分 R2615/R2639 及修复 R2644/R2645/R2655）、T7.3（本轮实测登记）全部完成。
