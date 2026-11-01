# R2247 结果：合入 codex/wip-R2244（R2244：配音与字幕音频脚本选 API 模型时直连调用，不经 Qwen）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。
- 测试：合并后 `run_selftests.py -k coverage_baseline audio_direct storyboard_direct` 18 条全过；`smoke_test.py --architecture` 在本合并所用的临时工作树里 411 项 3 项不过：`test_round_number_continuous`（状态页轮次，本轮已改为 2248）、`test_script_stages_name_only_their_approved_00_references` 与一项读 `基准历史.json` 的用例（该工作树缺少被忽略的文件，R2242 同样记过「worktree 缺文件」），需在主检出复跑确认。未跑全量。
- `project_status.md` 欠账：全量欠账不减；当前轮次更新为 2248。

## 合并内容
- `git merge --no-ff codex/wip-R2244`，在临时分支 `merge-r2244`（从 master（994993db）切出）上合并，再快进 master。
- 冲突两处，均为生成物，已手工消解：
  - `程序/runbook.md` 覆盖率口径一句：两边各自改了模块数，合并后取 336 个模块、52 个有行覆盖（284 个未碰到）。
  - `程序/维护记录/覆盖率基线.json`：`desktop_idea_chat.py` 取分支值（行数 970），`model_pool.py` 取 master 值（R2239 拆出 config_snapshot 后 754 行），`modules_total` 改为清单实数 336、`modules_covered` 52。`test_coverage_baseline` 5 条通过。
- 内容见 `tasks_round_2244_result.md`。真实 API 未调用。
