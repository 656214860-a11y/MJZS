# R2184 工作流调用设置窗口迁到 workflow_settings_dialog（结构治理轮·执行）

来源：`tasks_round/tasks_round_2178_result.md` J 节 **J1**。日期：2026-11-01。
基线：013d3ba2（R2178）；分支 `codex/wip-R2184` 由领号从 `claude/relaxed-chatelet-951d14` 切出。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：默认冒烟 8/8；架构门禁 412 项（含本轮新增 1 项），只剩 2 条与本轮无关的既有红（见「测试」）；`--affected workflow` 8 个文件 125 条全过；覆盖率基线同步（331→332 个模块）。债务：`--all --safe` 欠账 +1，本分支未跑全量；本轮改了层级登记表，合入 master 前须跑全量。`workflow_settings.py` 行数上限 1176→1056。

## 改动

1. 新模块 `workflow_settings_dialog.py`（L4，120 行）：`show_settings` 函数体原样迁入，连同它用到的 Tk 与 UI 名称（`tkinter`／`ttk`、`FileDialog`、`BaseDialog`、`Card`、`PrimaryButton`、`SecondaryButton`、`notify`、`LineInput`、`TextArea`、`TEXT_ROWS`、`WRAPLENGTH`、`SPACING`）。函数体里只改了「保存」一处：原来窗口内的六行（校验所选引擎这一档 → 写 `engine` → 读旧设置 → 写回本流程 → Qwen 同步共享模型）改调 `workflow_settings.save_flow()`，执行顺序和对 `draft` 的就地修改都不变。
2. `workflow_settings.py` 1176→1056 行：删去 `show_settings` 与 6 行 UI 导入，新增无 Tk 的 `save_flow(project, stage, draft, engine)`。导入本模块不再加载 tkinter。
3. `desktop.flow_settings` 改从 `workflow_settings_dialog` 懒导入 `show_settings`。调用方 `keyframe_comfy.py`、读 `_flow_settings_dialogs` 的 `workflow_agents.py` 都不用改。

## 登记

- `tests/architecture/_layers.py` 把 `workflow_settings_dialog` 登记为 L4。`workflow_settings` 本轮仍登记在 L4，按真实依赖重新登记留给 J3。
- 边界测试的登记文件名跟随迁移，断言未动：`test_button_boundary`、`test_card_boundary`、`test_file_dialog_boundary`（1 处 `FileDialog`）、`test_notification_boundary`（0 处）。`test_workflow_settings_json_boundary`、`test_workflow_dir_ratchet`、`test_agents_md` 登记的字符串仍在 `workflow_settings.py` 里，不用动。
- `test_module_size_ratchet`：`workflow_settings.py` 上限 1176→1056，按实际行数。
- 覆盖率基线：重跑 `scripts/coverage_report.py`（原 8 组定向用例，全通过）刷新为 332 个模块、50 个有行覆盖，`runbook.md` §11 同步。本轮相关的两项是 `workflow_settings.py` 888→789 可执行行、新增 `workflow_settings_dialog.py` 106 行，合计多 7 行，即 `save_flow` 与新模块的导入头。另有 14 个模块的可执行行数随 R2147 以后其他轮次的改动一并刷新，`file_cache`、`platform_tools` 各多 1 行被覆盖，模块覆盖数不变。
- `architecture.md`：分层表 L4 行加 `workflow_settings_dialog` 及职责说明；R714 段注明设置窗保存改经 `save_flow()`。

## 新增测试

- `tests/architecture/test_migrated_ui_boundaries.py::test_split_settings_modules_load_without_tk`：子进程 `import workflow_settings` 后检查 `sys.modules` 里没有 tkinter。改前输出 True（红），改后输出 False（绿）。J2 会把 `qwen_setup` 加进同一登记 `TK_FREE_ON_IMPORT`。
- `tests/test_workflow_settings_cache.py` 两条：`save_flow` 写回本流程并同步共享 Qwen 模型；所选引擎这一档校验失败时不写文件。

## 测试

- 默认冒烟 `smoke_test.py`：8/8 通过。
- `smoke_test.py --affected workflow`：8 个测试文件、125 条用例全过。
- `smoke_test.py --architecture`（经 `工作流任务\gui_hidden.py`）：412 项，剩 2 条红，都与本轮无关。一条是 `test_round_baselines.test_round_number_continuous`：状态页只在 master 更新，分支上必红。另一条是 `test_agents_md.test_performance_history_is_declared_as_historical_only`：`维护记录/基准历史.json` 被 `.gitignore` 排除，工作树里没有这个文件，主检出里有。首跑时另有 `test_coverage_baseline` 两条红，原因是新增模块后基线没刷新；重跑工具刷新后已转绿。
- 临时核对（脚本不入库）：在隐藏 Tk 根上打开迁出后的窗口，依次验证同一流程复用已开窗口；模型 ID 校验失败时窗口保留且不写文件；改对后保存写回 `engine=codex`、`model=gpt-adhoc`；`on_saved` 只回调一次；关窗后从 `_flow_settings_dialogs` 移除。输出 `OK engine=codex model=gpt-adhoc dialogs={}`。
- 未运行：`--all --safe` 全量；真实界面目测。

## 回滚

`git revert <本轮提交>`。不涉及用户数据与配置格式。

## 下一步

J2：`qwen_setup.show()` 迁到新 L4 模块 `qwen_setup_dialog.py`，并把 `qwen_setup` 加进 `TK_FREE_ON_IMPORT`。
