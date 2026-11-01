# R2251 结果：合入 codex/wip-R2250（R2250：stage_config 无项目读取不再留 None 缓存键）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。用户「先查全量红」的修复合入。
- 测试和三个基线：合并无冲突，只动 `stage_config.py` 两处写缓存判空与一份新测试；R2250 已在分支上跑定向（stage_config／stage_model_value／stage_prompt_governance／writing_status_line 全过）和 `--architecture`（主检出外只多 worktree 缺子模块的两项）。合并后未再手动跑全量，提交后看后台全量。
- `project_status.md` 欠账：未增减；当前轮次 2252。

## 内容
- 见 `tasks_round_2250_result.md`：后台全量的随机红由 `None` 缓存键污染引起，已修；`test_clipboard_lock` 依赖真实跨进程剪贴板锁，被别的进程占用时必红，属环境类，未改。
