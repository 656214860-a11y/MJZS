# R1997 media 页无 Tk 状态与决策下沉 media_page_controller（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J3**。日期：2026-10-24。
基线：`codex/wip-R1995` @ 332ca75d（R1995）。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红；默认冒烟 8/8；覆盖率基线同步（313→314 模块）。债务：`--all --safe` 欠账 +1；`desktop_media_pages.py` 的 `MediaPagesMixin` 类行数上限 994→890。

## 改动（3 个模块）

- 新增 `media_page_controller.py`（L3，无 Tk）：就绪签名、首帧批次可否派发判据（`busy`／`missing_settings`／`blockers` 回调保持短路与惰性求值）、连贯性台账与三张表的行、剪映候选路径、字幕状态文案、交接包选版、配音对白可用性、交付逐镜行、视频工作区解析与写回、首帧勾选表钥匙。L4 的 `local_video.skip_summary`、`video_progress.LABELS/status_next` 由调用方注入（避免 L3→L4 越层，未新增层级豁免）。
- `desktop_media_pages.py`：1041→942 行；对应方法体改为薄转发，公共方法名不变（他处调用与补丁点不变）；`find_editor` 内部局部导入 `editor_candidates`，因为 `test_desktop_settings_callers` 把该方法源码抽到裸命名空间执行。
- 测试与登记：新增 `tests/test_media_page_controller.py`（22 条）；`_layers.py` 登记 L3；`test_migrated_ui_boundaries.SERVICES` 加入；`test_complexity_ratchet` 类上限 994→890；`覆盖率基线.json` 与 `runbook.md` §11（313→314、263→264）同步；`architecture.md` 登记。

## 验证（本轮实测，经 gui_hidden）

- 定向 `-k media_page_controller media_page_services req_s06_anchors continuity_scope delivery_scope editing_scope account_security editing_page ui_edges desktop_settings_callers test_frame_checks keyframe coverage_baseline`：362 条，仅 `test_desktop_settings_callers` 3 条红（`launch_comfy` 的两条与「取消选择」一条）。**这 3 条在干净 HEAD（R1995）上同样红**（已用基线工作树对照，已清理）：R1995 把 `launch_comfy` 改走 `self.media_page_services`，测试仍给模块级 `comfy_executable`／`FileDialog` 打桩所致，与本轮无关，留作后续测试同步（仅 mock 同步，断言不动）。
- `test_pet_ui` 的既有红（首轮定向时出现）与历史集合一致，本轮未改 pet 相关代码。
- `smoke_test.py --architecture`：410 条，仅 3 条已知红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）。
- 默认 `smoke_test.py`：8 项全通过。
- 未跑 `--all --safe`，全量欠账 +1。未在真实窗口目测制作后段各页。
- **断言未动**：本轮没有修改任何既有断言；新增测试均为新文件。

## 回滚

撤回 `desktop_media_pages.py` 与 `architecture.md`／`runbook.md`／覆盖率基线／三个架构测试的改动，删除 `media_page_controller.py` 与其测试。

## 提交

见提交哈希（由 `scripts/dev.py commit` 生成，见会话报告）。

## 下一步

J4 导航与计时器；另需一轮把 `test_desktop_settings_callers` 的 `launch_comfy` 桩同步到 `media_page_services`。
