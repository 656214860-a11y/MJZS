# R4192：L5-E4 退出时结束所有项目登记进程并记录后台任务状态
<!-- round-evidence: {"commit_base": "b5b41193", "credential_hits": 0, "evidence_sha256": "1ac91d37e0fbb67b", "exit": 0, "failed": 0, "passed": 41, "round": 4192, "tests": "run_selftests.py -k force_quit process_supervisor infra/workflow_process_registry.py orchestrator/workflow_engines.py ui/desktop_lifecycle.py tests/test_force_quit.py tests/test_process_supervisor.py 维护记录/分支覆盖率基线.json tasks_round/tasks_round_4192_result.md"} -->

## 缺陷复现

`ui/desktop_lifecycle.py` 的 `stop_automation_processes()` 只对当前 `self.root` 调 `terminate`；`self.root is None` 时直接返回空列表。用户切换过项目后，旧项目仍在跑的登记进程不会被显式结束。退出路径也不记录 `infra.executors.pool_status()`。

改产品前定向命令红 7 条（与缺陷一致）：

- `exit_candidates` / `terminate_all` 不存在 → `AttributeError`（4 条，`test_process_supervisor`）
- `stop_automation_processes` 未调 `terminate_all` → stub 失败／行为缺失（2 条，`test_force_quit`）
- `finish_close` 未记「退出时后台任务」日志 → `assertLogs` 无 INFO（1 条，`test_force_quit`）

## 改动

| 文件 | 行号／说明 |
| --- | --- |
| `infra/workflow_process_registry.py` | `exit_candidates()`（约 337 行）：仍在跑且非 `detached` 的 `(项目键, 进程)` 只读快照 |
| `orchestrator/workflow_engines.py` | `terminate_all(timeout=3.0)`（约 591 行，文件末尾，避免上移 `launch_windows_app` 豁免行号）：取消涉及项目请求 → 先树杀 → 总超时内等待 → kill → forget |
| `ui/desktop_lifecycle.py` | `stop_automation_processes`（89–103）：当前项目 `terminate` 后接 `terminate_all`；`root is None` 仍调 `terminate_all` |
| 同上 | `finish_close`（110–114）：`LOGGER.info('退出时后台任务 %s', pool_status())`，失败走 `swallowed` |
| `tests/test_process_supervisor.py` | T1 `exit_candidates`、T2 `terminate_all`（含超时 kill／空列表／放过 detached） |
| `tests/test_force_quit.py` | T3 其它项目＋只做一次／无 root；T4 后台池日志 |
| `维护记录/分支覆盖率基线.json` | `workflow_process_registry.py` 决策点 83→89（AST 对齐）；covered 保持 53，percent 59.6；`points_total` 3082→3088 |

未改 `terminate(project)` 签名与行为；未调 `executors.shutdown`。

## 验收

1. `run_selftests.py -k force_quit process_supervisor branch_coverage_floor` → 退出码 0，46 条全绿  
2. `smoke_test.py --architecture` → 退出码 0，700 条 OK（约 345 s）

## 未验证

- 未跑全量自检／默认冒烟  
- 未真起 Desktop／真子进程做退出残留实测（卡面禁止）  
- 分支覆盖率基线未整表重测工具；仅按 AST 决策点数对齐本模块，covered 未因本卡定向用例重测上调  

## 卡外发现（未修）

无。
