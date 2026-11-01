# R1635 实际跳过清单机制与实测收口（联调/测试 T8 剩余）

- 编号说明：本轮中央领取号为 **1635**（原写成 1634）。结果文件先于领号创建，使 `round_claim.latest_result_round()` 多算一号；按提交门禁“提交号必须等于中央已领取号”，连同状态页一起改为 1635（与 R1629 同因）。1634 未被任何轮次使用。
- 本轮类型：§3.10 验证/基线轮（含自检器改动：`run_selftests.py` 是自检工具，不是产品模块，但按 §5 路径口径计 1 个源码轮）。
- 测试跑了吗？跑了。定向 `tests.test_selftests` 52/52；默认冒烟 8/8；架构门禁 356/356。三个基线全过。
- 欠账少了吗？没有减少也没有新增全量欠账条目之外的负担：本轮计 1 个源码轮（欠账 1／8），未命中风险路径（启动入口／删除语义／层级表），不触发强制全量。

## 交付

1. `run_selftests.py`：`_run_unit` 的结果从 7 位扩到 8 位，第 8 位是该单元**实际跳过**的 `(用例, 原因)` 清单（来自 `result.skipped`，异常路径给空表）；新增 `skip_summary(results)` 与汇总打印 `实际跳过 N 条用例…`（明细上限 `SKIP_REPORT_LIMIT`＝40 条），没有跳过时打印 `实际跳过 0 条用例`。
2. `tests/test_selftests.py` 加 3 条：`test_actual_skips_are_reported_from_run_results`（从结果取、不从登记位取）、`test_unit_result_always_carries_the_skip_list`（真跑一个单元，第 8 位存在且为空表）、`test_skip_report_is_printed_in_the_summary`（汇总必须打印）。52/52 通过。
3. `说明/联调测试出口基线.md`：§3 从“登记位口径”改成“实测口径”（清单＋取证范围＋一处更正）、§6 T8 转完成、§7 检查单补一行。
4. `说明/联调测试出口基线.md` §6 顺手补记：T2／T3（R1630）、T4／T10（R1629）、T5／T11（R1631）此前只在状态页与各自结果文件里记了完成，表里仍写“未开工”；本轮按那些轮次的记录把状态补齐，不改它们的验收内容。

## 实测结论（本机当前环境）

- **实际跳过 1 条**：`tests/test_core.py::ValidateProfileTests.test_stage_profile_wrong_preset_rejected`，原因＝需实机复验（发行包未含受测 bundled skill）。
- 4 个平台可用性条件逐条实测满足：`import tkinter` 可导入、`Tk()` 可建窗、目录符号链接可创建、`K32GetProcessMemoryInfo` 可读工作集（26.6 MB）→ 219 个平台登记位（tkinter 203／Tk display 16／目录链接 4／工作集 1）在本机都不触发。
- 条件类站点实跑 219 条用例（`test_core.ValidateProfileTests`＋`ProjectsDeleteTests` 那一条＋`test_stage_layout`＋`test_workspace_maintenance`＋`test_skills`）：唯一跳过即上面那 1 条。
- 口径更正：旧文“实际跳过约 3 个（node 1＋bundled skill 2）”是**推断**；实测为 1 个——node 本机可用（`node --version` 成功），另一个 bundled skill 站点 `test_preset_label_round_trips_through_preset_folder` 实跑通过。`MISSING_NODE` 那处挂在辅助方法 `GeneratorTests.run_generator` 上，不会被 unittest 收集。

## 环境限制（如实登记，不冒称全量）

- 本轮**没有**跑 `run_selftests.py --all --safe`：在当前沙箱里派生工作进程被拒（`[Errno 5] 拒绝访问`，此前定向跑自检时也出现过“安全隔离进程未启动，改为同进程执行”），全量会退化成单进程串行（实测 4 个文件跑 5 分钟仍未结束），故停掉。全部 229 个登记位的机器核对留给下一次沙箱外的全量：新打印的“实际跳过”一行即是那份清单。
- `tests.test_perf_baseline.PerfBaseline.test_memory_stays_bounded_after_every_page`（工作集那条）本轮未单独重跑（单跑超过 4.5 分钟）；其触发条件已按 §1 口径 K32 接口实测可用，故登记位不触发。该用例仍由全量覆盖。
