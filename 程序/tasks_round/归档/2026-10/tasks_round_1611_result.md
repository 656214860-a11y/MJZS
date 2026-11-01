# R1611 静态卫生门禁与无效转义修复（Q1+Q3）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round_1610_result.md) J 第一批 Q1 与 Q3）。
- 测试：定向 `tests.architecture.test_static_hygiene`＋`test_agents_md`＋`test_dev_entry` 通过；架构门禁 348/348 通过（174.437 秒，较上轮 345 增 3；首跑因状态页轮次头未同步失败 1 项，同步后全量复验通过）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮改源码，`project_status.md` 全量欠账计数 +1，未清。

## 改动

1. **Q1 新增静态卫生门禁** `tests/architecture/test_static_hygiene.py`（纯标准库、零运行时依赖）：① 无效转义序列／语法错误；② `from ... import *`；③ 生产运行时内建 `eval`/`exec`。三类均为 AST／编译期可确定、误报极低、未来 Python 会升级为硬错误的类别。刻意不做“未用导入”等易误报项。
2. **Q3 修复本仓无效转义序列 1 处**：`tests/test_dev_entry.py:23` 的 `'scripts\dev.py'` → `r'scripts\dev.py'`。修复后本仓自有源码 `compile()` 的 SyntaxWarning 归零。
3. **Q1 门禁登记同步**：`AGENTS.md` §5「当前架构门禁清单」加入 `test_static_hygiene.py`（`test_agents_md` 要求清单与实际文件集合相等）。

## 边界：外包子模块不作为本仓修复目标

- 全仓扫描另命中 1 处转义问题：`程序/skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239`。
- 该目录是**外部技能包**（嵌套 Git 仓库、remote `manju-laoli-skill.git`，父仓以 gitlink 160000 记录），不属本仓源码，无法在本仓提交修复，也不应改写第三方历史。
- 处置：已把本地改动还原（子模块工作树恢复干净），并在门禁中排除 `skills/` 与嵌套仓库（与 `test_busy_state_boundary`／`test_token_boundary` 等既有门禁口径一致）。**该外部缺陷建议上游修复，不在本轮范围。**

## 证据与边界

- 日志：`outputs/r1611-architecture.log`、`outputs/r1611-smoke.log`。
- 门禁只覆盖确定性类别，不等于完整 lint（无未用变量、类型、复杂度检查；类型检查缺口保留待后续轮）。

## 下一项

Q2（函数行数棘轮并拆解最长函数）。