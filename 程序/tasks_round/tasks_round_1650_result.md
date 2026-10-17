# R1650 验证/基线轮：清单 P2-4／P2-5／P2-6／P2-8 收口（度量口径登记与复核）

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证/基线轮。范围＝`tasks_round/tasks_round_1645_result.md` J 节清单 P2-4／P2-5／P2-6／P2-8；四项同属「文档／口径登记＋门禁」类，按 §2.5 规则 27 批量成轮。不改产品运行期代码、不改契约、不搬目录、不重命名。P2-7（迁移哈希缓存）留到下一轮。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；定向 `tests.architecture.test_agents_md`＋`tests.architecture.test_coverage_baseline` **20/20**；行尾＋轮次 **21/21**；架构门禁 **364/364（299.7 秒，本轮实测，改前 362）并绿**。**未跑全量**（欠账未增，见第 3 问）。
3. **project_status.md 的欠账少了吗？** **没有变**。本轮只改 `.md` 与 `tests/architecture/` 下的测试（`run_selftests.is_source_change()` 口径：非 skills 的 `.md`、`tests/` 内文件均不算改源码）⇒ 欠账不增加，仍为 5/8；也没有减少（清零要看后台全量转绿，而它因 D 节的红仍未转绿）。

## A 改动

1. **P2-4 性能基准口径**（`程序/runbook.md` 新增 §10「性能基准口径」）
   - 明示 `维护记录\基准历史.json` 是**历史参考、不作当前判据**：最新记录停在 R1373，指标名（`first_frame_ms`／`ready_total_ms`／`cold_ms`／`warm_ms`／`row_count`）与现行契约不同名不同口径、不可直接比较。
   - 指认当前两处权威源：`tests\performance_contract.py`（11 条阈值常量）与 `tests\test_perf_baseline.py`（把阈值写成用例）；并写明「要对齐必须先把探针指标名与契约对齐再真机重跑」。
2. **P2-5 覆盖率口径**（`程序/runbook.md` 新增 §11「覆盖率口径」）
   - 明示 `维护记录\覆盖率基线.json` 是**定向测量、不是整仓覆盖率**，并给出当前数字与字段口径：`modules_total` 281、`modules_covered` 49、未覆盖 232、`targets` 8 组定向用例、`tests_ok` 含义。
   - 写明「232 个模块覆盖率 0 ≠ 整仓覆盖率 7%、不能据此列未覆盖清单」，工具是 `scripts\coverage_report.py`（`sys.settrace`），不重跑测量，诚实边界与刷新条件。
3. **P2-4 门禁**（`程序/tests/architecture/test_agents_md.py`）
   - 新增 `test_performance_history_is_declared_as_historical_only`：断言 runbook §10 存在且含 `基准历史.json`／`历史参考`／两处权威源路径；并把「`基准历史.json` 的指标名与 `performance_contract` 阈值常量名（小写）**交集为空**」变成可执行断言——一旦有人把基准与契约对齐又忘了改口径，这条会红。顺带在该文件补 `import json`。
4. **P2-5 门禁**（`程序/tests/architecture/test_coverage_baseline.py`）
   - 新增 `test_runbook_states_the_directed_measurement_caliber`：断言 runbook §11 存在、含「不是整仓覆盖率」，且 §11 里出现的数字与 `覆盖率基线.json` 的 `modules_total`／`modules_covered`／`len(targets)`／未覆盖数**逐项一致**（口径即字段）。
5. **P2-6 正式产物版本「待核查」6 类**：沿用清单原文「见阶段5 清单 U11（本项与其同一工作项，不重复立项）」，本轮把它写成**书面归属**并核对 U11 已在 `维护记录/优化待办队列.md:69` 登记；未改 `说明/持久化产物版本清单.md`，不重复立项。
6. **P2-8 越层计数与台账口径**：书面归属＝**差集为空**。依据 R1647 的实测：改用与门禁同一的 `_scan.import_rows()`／`production_files()` 复算后，扫描集合与 `架构统一基数.json.层级.items` **完全相等**（本 R1647 时点为 37→35 后的 35=35；R1649 未动层级台账，仍相等，本轮的架构门禁 `test_layer_exemptions_are_a_locatable_nonincreasing_baseline` 绿即是最新证据）。原先「42 vs 37」的差额来自上一轮**独立扫描的实现口径**（导入写法／文件集合不同），不是漏判层级。

## B 验证（本轮实测命令与结果）

- `python -B -m unittest tests.architecture.test_agents_md tests.architecture.test_coverage_baseline` → `Ran 20 tests` **OK**（5.625 秒；`test_agents_md` 15 条、`test_coverage_baseline` 5 条）。
- `python -B -m unittest tests.test_line_endings tests.architecture.test_round_baselines` → `Ran 21 tests` **OK**。
- `python -B smoke_test.py` → **通过 8 项 / 失败 0 项**。
- `python -B smoke_test.py --architecture` → `Ran 364 tests in 299.670s` **OK**（改前 362；本轮新增 2 条用例）。
- P2-4 的事实基线：`基准历史.json` 记录指标名集合 ∩ `performance_contract` 阈值常量名（小写）＝ **空**（由新增门禁断言）。
- P2-5 的事实基线：runbook §11 的 281／49／8／232 与 `覆盖率基线.json` 字段逐项相等（由新增门禁断言）。

## C 完成判据对照

| 清单项 | 判据（原文） | 结果 |
| --- | --- | --- |
| P2-4 | 文档写明口径差异且被测试引用 | ✅ runbook §10 ＋ `test_agents_md` 新用例引用并断言交集为空 |
| P2-5 | 文档口径与 `覆盖率基线.json` 字段一致，且 `test_coverage_baseline` 仍绿 | ✅ runbook §11 ＋ `test_coverage_baseline` 新用例逐项比对字段 |
| P2-6 | 与 U11 同一工作项（清单原文：见阶段5 U11） | ✅ 书面归属，U11 已在 `维护记录/优化待办队列.md:69` 登记；未重复立项 |
| P2-8 | 差集为空，或差集每条都有书面归属 | ✅ 差集为空（R1647 实测 35=35；本轮架构门禁的台账相等断言绿为最新证据） |

## D 未做与局限

- **后台全量红（本轮外，复述）**：R1648 触发的自动全量在 `.wt/ci` 退出码 1，唯一红＝`tests/test_distribution_selfcheck.py::test_manifest_covers_every_file`：`['程序/data_model.md','程序/runbook.md','程序/task_states.md']` 未在 `distribution_manifest.md` 声明保留或排除。三文件由 **R1625** 新增；`test_distribution_selfcheck` 只在全量跑，故自 R1624 后首次全量才暴露。**非本轮引入、非本轮范围**，按 §8.6 只登记不修（§5 亦写明「后台全量红…人工接续」）。**注意**：本轮又改了 `runbook.md` 的内容，但该红由「文件未声明」引起，与本轮改动无关，不会因本轮而恶化。
- 未重跑性能基准（本机无 Tk display、无真机条件），故 P2-4 走「文档＋门禁」路线；真机对齐指标重跑仍待授权。
- 未做全量 `sys.settrace` 覆盖率测量（成本高、须用户同意），故 P2-5 只登记口径，不产出「未覆盖模块」清单。
- P2-7 未动（下一轮：迁移校验哈希改走 `file_cache.file_digest`）。
- 未更新接力文件（结果文件已记录完成／未完成／验证／下一步）。
- 提交：按 §2.6 一次性 `git add`＋`git commit`，提交信息以 `R1650: ` 开头；hash 见 `git log`（本文写入时尚未提交）。
