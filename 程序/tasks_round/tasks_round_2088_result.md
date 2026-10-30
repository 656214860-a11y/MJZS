# R2088 复核 R2080 后台全量红项（修复轮）

轮次类型：修复轮（§3）。日期：2026-10-30。分支 `codex/wip-R2088`（基于 master `389007ed`）。

- 跑了哪些测试与基线：基于 `33b684b8` 时隐藏桌面串行复跑 `run_selftests -k test_copy_rules test_core test_idea_chat edit_habit test_leak_teardown`（298 条，0 个文件红）、`test_idea_chat` 再跑一次（145 条，0 红）、默认冒烟 8/8、`--architecture` 410 条；改基于 `389007ed` 后复跑见下节。
- 断言未动：`test_idea_chat` 只把上传列表用例里首绘后的 `win.update()` 换成文件内已有的 `settle_script_page(win)`。
- 轮次号：开工领 R2083，提交时中央计数器已到 R2086；R2086 合入的 R2081 已修掉本轮同样发现的 `test_core` mock 和 8 条气泡用例，本轮改基于 `389007ed`，去掉重叠改动，领号时 R2087 已被其他会话领走，用 R2088 提交。R2083 空号。
- 未改 `project_status.md`（worktree 不写）。

## 依据

后台全量 `auto_full_safe.py --run`，HEAD `33b684b8`，2026-10-30 11:38 结束，665 秒，退出码 1，6792 条用例里 5 个文件红。

## 逐项结论

| 红项 | 结论 | 处理 |
|---|---|---|
| `test_copy_rules::test_interface_copy_speaks_to_you_with_the_polite_pronoun` | 已修。R2074 新增的两处文案用了「你」 | `edit_habits_dialog.py:48` 的界面说明改成「您」；`edit_habits.py:219` 是给模型的提示词，开头改成「任务：分析用户对 AI 生成剧本的修改」，不靠扩大 `PROMPT_FILES` 白名单放行 |
| `test_core::test_script_stage_project_loads_without_storyboard_json` | 已由 R2081（R2086 合入）修复：假 `ProjectList` 补 `exists` | 本轮不改 |
| `test_idea_chat::BubbleLayoutTests` 两条（单击编辑绑定、编辑不跨气泡） | 已修（测试等待不足）。单跑也稳定红。调试确认：`show(0)` 加一次 `win.update()` 后，日志框还停在「正在读取聊天记录…」，气泡要等后台模型键解析完才分片画出，所以 `bubble_0` 还没有 `<Button-1>` 绑定，`start_bubble_edit` 在 `ranges<2` 处提前返回，`_bubble_edit` 也就没有设置 | 已由 R2081（R2086 合入）修复：8 条气泡用例改用 `settle_script_page(win)` |
| `test_idea_chat::test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy` | 已修（同上，时序不稳）。上传列表也在首绘后回填，单跑时有时绿 | 同样改用 `settle_script_page(win)` |
| `test_leak_teardown::test_three_rounds_of_all_pages_stop_growing` | 环境（并发）。全量日志标了 `[SUSPECT_CONCURRENCY]`，after 数 7→7→6 是往下降而不是增长；串行单跑 3 条全绿 | 不改 |
| `architecture.test_round_baselines::test_round_number_continuous` | 流程。状态页轮次头由 master 合并轮同步 | 不改 |

## 改基于 389007ed 后复跑

- 隐藏桌面 `run_selftests -k test_copy_rules test_core test_idea_chat edit_habit`：295 条，0 个文件红。
- 默认冒烟 8/8 通过。

## 仍红（均非本轮引入）

- worktree 里 `--architecture` 有 2 红：`test_agents_md::test_performance_history_is_declared_as_historical_only`（worktree 缺被 gitignore 的 `维护记录/基准历史.json`，主目录有）；`test_round_number_continuous`（流程）。

## 未运行

- `--affected`、`--all --safe`（合入 master 后由后台补跑）、真实界面目测。未 push。
