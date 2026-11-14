# R2501 结果：自然剧本节拍表闸门拆分到独立 L0 模块，修复模块行数棘轮回归

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。R2497 把「本集节拍表」豁免逻辑直接写进 `script_contract.py`，使该文件 1209→1238 行，触发 `tests/architecture/test_module_size_ratchet.py` 的上限棘轮（`script_contract.py` 登记上限 1209，只许下降）。本轮按棘轮自身指引「新增功能应放进新模块」，把节拍表字段表格闸门拆到新 L0 模块 `script_natural_gate.py`，`script_contract.py` 回到 1209 行，并同步层级登记、覆盖率基线与 runbook 口径。

2. **测试跑了吗、三个基线过了吗？**
   - 定向：`test_script_contract.py` 54/54 OK（含 R2497 两条节拍表用例）；`tests.architecture.test_module_size_ratchet`＋`test_layers`＋`test_coverage_baseline` 13/13 OK。
   - 架构门禁：`smoke_test.py --architecture` 420 条，剩 3 FAIL＋1 ERROR，全部为**既有**、与本轮无关（`test_performance_history_is_declared_as_historical_only` 缺基线文件；`test_class_size_does_not_grow` 的 `desktop_idea_chat.py::IdeaChatMixin 769>748`；`test_round_number_continuous` 2483≠2498 并发车道；`test_bare_json_load_debt_is_a_nonincreasing_subset` JSON 债务）。本轮不引入新红。
   - 默认冒烟：8/8（submodule 就绪前已通过）。
   - 全量 `--all --safe`：未跑（约 16–21 分钟，且受既有红项影响）；本轮改动仅移动一个纯函数，定向＋架构门禁已覆盖。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；本轮消除 R2497 自己引入的模块行数棘轮回归（`script_contract.py` 回到上限内）。既有欠账（性能基线缺失文件、`desktop_idea_chat` 类尺寸、JSON 债务、并发轮次号）不属本轮范围。

## 改动清单

- `程序/script_natural_gate.py`（新，L0，37 行）：`has_foreign_field_table(value)` 与 `_BEAT_TABLE_HEADER`，按 REQ-S01-16 六列表头豁免节拍表，其余管道表格仍判「字段表格」。
- `程序/script_contract.py`：删除内联的节拍表检测（29 行），改 `from script_natural_gate import has_foreign_field_table` 并在 `natural_script_violations` 调用；行数 1238→1209。
- `程序/tests/architecture/_layers.py`：L0 登记 `script_natural_gate`。
- `程序/architecture.md`：L0 合同行补 `script_natural_gate`。
- `程序/维护记录/覆盖率基线.json`：新增 `script_natural_gate.py`（total 19，covered 0），`modules_total` 363→364。
- `程序/runbook.md`：§11 口径 363→364 个模块、未覆盖 304→305。

## 验证

- 真实文件复现：`摄影侠_自然剧本_Google_20261114.md` 修复后 `natural_script_violations() == ()`、已含于 `natural_script_paths`；分镜表/镜头表管道表格仍被「字段表格」拦截。
- `script_contract.py` 行数 1209（== 登记上限，通过 `n > cap` 判定）；新模块 37 行（< 1000）。
