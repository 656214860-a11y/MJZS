# R2866 修复轮结果

1. 轮次类型：修复轮（§3.2）。R2861 合并 codex/wip-R2851（T10 批次1–6 一次性入主干）后，主干 10 个测试文件红、约 25 条用例失败；经 a7ecd950 基线对照确认均为合并回归，另带出 2 个历史欠账一并修复。
2. 测试：跑了。`run_selftests.py -k` 覆盖全部受影响文件：video_task_state_cache、stage_parallel、req_s07_anchors、stage_wiring、desktop_send_steps、script_agent_delivery_paths、flow_agent_launch、asset_detail、script_structure_dedup、mutation_sample、script_workspace_results、desktop_startup_perf——修复后 12 文件全绿（mutation_sample 2/2、desktop_startup_perf 14/14、script_workspace_results 6/6 等，详见 evidence/R2866.json）。三个基线：默认冒烟未单独重跑（exit CI 随合并轮执行）；架构门禁未跑（本轮只动 tests/ 与 scripts/mutation_sample.py 位点表，不触分层）；全量安全未跑（合并轮 exit CI 通过后由后台补跑）。
3. 欠账：project_status.md 欠账减少——修复了合并引入的回归与 2 个历史确定性红（test_script_workspace_results 的 _WritingPage 抽取环境缺 WritingSnapshotsMixin 基类；test_desktop_startup_perf 夹具缺必填字段被「还缺必填」门禁拦截）。

## 根因与修法

T10 把 30 个模块实体迁入 `contract/`，顶层留兼容门面。测试侧三类失配：

- `mock.patch('X.y')` / `patch.object(门面模块, ...)` 打不到生产侧 `from contract.X import y` 的调用期查找 → 改打 `contract.X.y`（stage_layout.ensure/adopt_legacy、storyboard_paths.media_root、script_contract.script_baseline_path/resolve_script_source、workflow_context_budget.prepare_request_context、asset_contract、shot_batches、script_contract.datetime 等）。
- 测试直接摸私有缓存：`storyboard_paths._LISTINGS/_RESOLVED` → 改 `import contract.storyboard_paths`。
- 源码字符串断言与变异位点表仍写旧扁平模块名 → `from contract.shot_batches import assign`、`scripts/mutation_sample.py` SITES 改 `contract.*` 且 `_apply`/测试读路径做点号转路径。

断言语义全部保留；仅同步导入/补丁定位路径（AGENTS §2.4 允许）。

## 提交

- commit：`1f03312a`（本文件随 amend 并入同一提交）。
