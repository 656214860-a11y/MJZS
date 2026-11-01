# R2224 结果：合入 codex/wip-R2218（R2218：模型管理列表与表单布局）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。用户在 R2218 完成后要求「提交并合入」。
- 测试和三个基线：在 master（合并前 2e6ead51，R2220）合并后的主检出树上，经 `工作流任务/gui_hidden.py`。
  - 定向自检 `run_selftests.py -k pet_settings model_manager_actions model_delete_stays ui_batch7 button_consistency pet_ui`：699 条，0 个文件有红。
  - 默认冒烟：8 项通过。
  - `smoke_test.py --architecture`：411 项全过（R2218 在 worktree 上红的 3 条环境性失败，在主检出上都绿）。
  - 另跑了 R2218 提交前那次后台全量（HEAD 4cfd064）红过的 5 个文件 `test_stage_model_value test_stage_prompt_governance test_writing_restart test_writing_status_line test_leak_teardown`：42 条，0 个文件有红。那次红不是本轮引入的，本轮树上不复现，原因没有追查。
  - 全量 `--all --safe` 本轮未手动运行。`auto_full_safe.py --status` 在合并前报：上次全量 R2183，其间改过源码的轮次 7（门禁线 8），后台触发 False，红后冷却中；上次后台全量未通过（HEAD 4cfd064，退出码 1）。本次合并后是第 8 个源码轮次，之后是否启动后台全量，以提交后的 `--status` 为准，结果另补，这里不写成已通过。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少也没有新增；当前轮次更新为 2225。

## 合并内容
- `git merge --no-ff codex/wip-R2218`，无冲突，只动 `pet_models_ui.py`、`tests/test_pet_settings.py`、`tests/test_ui_batch7_settings_models.py` 和 R2218 结果文件。内容见 `tasks_round/tasks_round_2218_result.md`。
- 断言未动：R2218 里按新列顺序与左右分栏调整的 3 处测试取值位置属契约有意变更，没有弱化断言。

## 合并证据（§2.6 第 41 条）
在暂存区上运行（提交前）。分支没有改 `project_status.md`，只有表头一行由本轮改写。
- `git diff --cached 2e6ead51 -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'`：输出 0 行（应为 0）。
- 暂存区状态页的轮次号去重共 100 个，与 2e6ead51 一侧和分支一侧的并集逐字节相同（`cmp` 无差异）。

## 用户需做
重启应用后生效。
