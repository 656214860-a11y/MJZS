# R1939 结果：测试治理阶段4——增量台账漏检修复

轮次类型：修复轮（测试资产／自检工具）。分支 claude/affectionate-goldstine-5e7003。

## 发现（对抗测试先红）
新增 `tests/test_selftest_incremental_gaps.py`，在临时程序树里走真实 `incremental()`，改被依赖文件后看目标测试是否被排进“要跑”。结果：
- 函数内 import：不漏（`ast.walk` 已覆盖）。
- `from agent.core import x` 点号导入：**漏检**（agent 子包文件未按点号名登记）。
- `from agent import media`：**漏检**。
- `tests/` 下共用辅助模块（widget_test_support、env_test_support、startup_fixtures 等）：**漏检**，辅助模块变了依赖它的测试不会重跑。

## 修复（`run_selftests.py`）
- `project_modules()` 增加 `agent`／`agent.<名>` 与 `tests/*.py` 辅助模块；`imports_of()` 额外产出点号全名。
- 新增 `INCREMENTAL_RULES = 2`：旧台账不含该版本即整体作废，首次增量会把所有测试照跑一遍（保守，不许漏检）。
- 这是自检工具的契约扩充，**只增加依赖、不减少**；既有断言未动。

## 验证
- `run_selftests.py -k selftest_incremental test_selftests`：ALL TESTS PASSED（5 条新增，含旧台账作废用例）。
- 未运行：`smoke_test.py`、`--architecture`、`--all --safe`。仍未覆盖：`importlib.import_module("字面量")`、subprocess 启动的脚本、skills 以外的数据文件、scripts／workflows 子目录。
