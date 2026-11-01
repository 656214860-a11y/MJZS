# R1794：修复轮——收口 R1786 遗留的 4 条架构门禁红（覆盖率基线未刷新、skip 缺原因常量）

1. 本轮类型：§3.2 修复轮。起因：R1788 合并 R1786 后跑架构门禁，4 条红来自 R1786 新增的 `ui_motion.py`、`ui_rounded.py`、`tests/test_ui_motion.py`，在 master 上本来就红；它们会让下一次后台全量一开始就红，所以先收口。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k coverage_baseline skip_hygiene ui_motion`：23 条，0 红（含 `test_coverage_baseline` 的核心路径下限与 runbook 数字自洽两条）。
   - 架构门禁与完整安全全量：见合入 master 后的回填；全量本轮未手动跑，历史凭据仍 R1734。

3. project_status.md 欠账少了吗：本轮改源码 0（只改测试、台账、基线、runbook 数字），不计源码轮。

## 根因与修复（断言未动）

| 红 | 根因 | 修复 |
|---|---|---|
| `test_skip_hygiene` 2 条 | `tests/test_ui_motion.py` 的 `MotionBase.setUp` 用 `self.skipTest(str(exc))`，原因不是 `skip_reasons` 里登记的常量 | 改用 `PLATFORM_TK_DISPLAY`（与同类 Tk 测试一致），在 `维护记录/skip台账.json` 登记一条（只追加 9 行） |
| `test_coverage_baseline` 2 条 | R1786 新增 `ui_motion.py`、`ui_rounded.py` 两个生产模块，基线仍是 292 个 | 用同样的 8 组定向用例重跑 `scripts/coverage_report.py --json` 刷新基线：294 个模块、50 个有行覆盖；`tests_ok` 为真，核心路径下限全部满足；`runbook.md` §11 数字同步为 294／244 |

## 说明

- 基线是对固定 8 组用例的真实测量，所以用原工具重跑，没有手改 JSON；R1788 删掉 `Splash` 等死代码后相关模块的总行数也随之更新。
- 不改任何门禁断言或下限。

## 提交

- 已提交，commit hash 见 git log `R1794:`。
