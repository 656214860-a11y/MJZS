# R1799：修复轮——收口 R1792 新增模块带来的架构门禁红（skip 原因常量、覆盖率基线）

1. 本轮类型：§3.2 修复轮，随 R1792（微交互与动效优化）合入。起因：合入前跑完整 `tests/architecture`，R1792 新增的 `tests/test_ui_motion_perf.py` 与 `ui_scroll.py`、`ui_hover_fade.py` 带来 4 条红，同 R1794 收口过的 R1786 那一类。

2. 测试跑了吗、三个基线过了吗：
   - 修后 `test_coverage_baseline`、`test_skip_hygiene`、`test_ui_motion_perf` 共 34 条，0 红。
   - 完整 `tests/architecture`（376）修前 6 条红：4 条是本轮收口的；`test_agents_md::test_performance_history_is_declared_as_historical_only`（缺 `维护记录/基准历史.json`）与 `test_skill_reference_injection`（缺 `skills/00全流程SKILL/.../screenplay-gate-engine.md`）两条是本工作树缺少未入库文件，非本轮引入，未处理。
   - 完整安全全量本轮未跑；历史凭据不写成本轮通过。

3. 欠账：本轮改源码 0（测试、台账、基线、runbook 数字）。

## 根因与修复（断言未动）

| 红 | 根因 | 修复 |
|---|---|---|
| `test_skip_hygiene` 2 条 | `tests/test_ui_motion_perf.py` 的 `TkCase.setUp` 用 `skipTest(str(exc))`，不是 `skip_reasons` 登记的常量 | 改用 `PLATFORM_TK_DISPLAY`，`维护记录/skip台账.json` 追加一条 |
| `test_coverage_baseline` 2 条 | R1792 新增 `ui_scroll.py`、`ui_hover_fade.py` 两个生产模块，基线仍是 294 个 | 用原 8 组定向用例重跑 `scripts/coverage_report.py --json` 刷新基线：296 个模块、50 个有行覆盖，`tests_ok` 为真；`runbook.md` §11 数字同步为 296／246 |

## 另记

合并时 `master` 在本分支开发期间多次前进（R1788～R1796）；合并提交会把 `project_status.md` 带进非 master 分支，被钩子拒绝，所以改用 `git rebase master`（本分支提交均未发布、无冲突），R1792／R1795 的提交信息与内容不变。
