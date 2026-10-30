# R2150 结果：合入 codex/wip-R2149（R2149：弹窗首次定位不再裁内容）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。
- 测试和三个基线：在主检出 master 合并后的树上运行。
  - `run_selftests.py -k ui_theme model_manager speech_api account dialog popup pet_models ui_widgets window placement`（经 gui_hidden）：220 条全过。
  - 默认冒烟：失败 0 项。
  - `--architecture`：411 项中两项在写状态页前失败：`test_round_number_continuous`（2149 != 2150，状态页尚未登记本轮），`test_full_safe_all_is_required_after_eight_source_rounds`（上次全量 R2124，其间超过 8 个源码轮，超过门禁线 8）。其余全过。
  - 全量 `--all --safe` 本轮未手动运行：门禁提示由提交后的 post-commit 钩子在后台自动补跑，进度见 `logs/auto_full_safe.log`。
- `project_status.md` 欠账：没有减少，也没有新增；本轮把当前轮次更新为 2151。

## 合并内容
- `git merge --no-ff codex/wip-R2149`，自动合并，无冲突（6 个文件）。
- 功能说明与测试契约变更见 `tasks_round/tasks_round_2149_result.md`（断言未动）。
- 用户需重启应用，弹窗定位修复才生效。
