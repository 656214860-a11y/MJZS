# R2037 结果：合入 codex/wip-R2032 到 master（合并轮）

## 内容
- 本轮把 R2032 合入 master（`569e35ec`，已含 R2029 的 desktop.py 拆分和 R2035／R2036 的 R2028 账号补全）。R2032 修复的是后台回调异常「'AutoState' 无 gate_auto_due」。
- 合入前，先把 R2032 rebase 到最新 master。rebase 时棘轮有冲突，按实测值处理：
  - complexity Desktop 838→836；
  - shared_state Desktop 49→48。
  - 断言未动。
- 顺带修正 `tasks_round_2032_result.md` 里的棘轮数值说明。
- R2034 号已领，但没有用：worktree 内的合并提交被门禁拒绝，原因是工作树不得写 project_status.md。

## 验证（rebase 后在 worktree 实跑，代码与本次合入一致）
- `run_selftests.py -k test_core auto_state auto_flow automation lifecycle page_nav account login_gate`：ALL TESTS PASSED。
- `smoke_test.py --architecture`：一共 410 项，有 3 项已知遗留红，与本轮无关：
  - agents_md
  - round_baselines
  - skill_reference_injection
