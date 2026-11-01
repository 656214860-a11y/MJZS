# R2263 结果：资产／首帧出图直连（引擎为 qwen 时不经 Qwen Code）

1. **轮次类型**：功能轮（§3.1），REQ-S05-50／DES-S05-50、REQ-S08-52／DES-S08-52。
2. **测试**：定向与架构门禁见下；默认冒烟、`--all --safe` 未运行（分支不累计欠账）。`project_status.md` 未改（worktree 会话）。
3. **提交**：已提交到 `codex/wip-R2263`（hash 见 git log）。

## 改动
- 文档先行：`docs/stages/S05_资产管理.md`、`S08_首帧管理.md` 新增 REQ／DES 与测试锚定行。
- 分流唯一一处：`desktop_idea_chat._FlowAgentLaunch.build()`（stage=assets、带 `direct={'image': 批次.json}`、引擎 qwen）→ `desktop_image_direct.run_image_direct`（L4 薄壳：状态文案、轮询收尾）。
- `image_direct.py`（L3）：复用 `storyboard_direct_api.Job`，线程内调 `image_agent_runner.execute(project, manifest, stop)`；失败经 `asset_batch_lifecycle.fail` + 注入 gateway 写 `执行状态.json`；项目内唯一作业登记在 `workflow_process_registry`，「强制停止制作」经 `cancel_project_requests` 置位 stop。
- `image_agent_runner.execute/_execute` 增可选 `stop`（默认 None→新 Event，行为不变）；停止时状态文案为「已强制停止制作…」。
- `asset_skill_batch.launch`、`keyframe_import.launch`：qwen 引擎走 `open_direct_flow_agent`，其余引擎仍 `open_flow_agent`（含 attach 回执）；首帧 `launch_comfy(silent=True)` 保留。`watch()` 状态文案「Qwen → ComfyUI」改为「图片制作 → ComfyUI」。
- 层级登记：`tests/architecture/_layers.py`、`architecture.md`（L3 `image_direct`、L4 `desktop_image_direct`）；覆盖率基线 +2 模块（340），runbook §11 数字同步。

## 测试
- 红：`tests/test_image_direct.py` 先于实现运行，`_run_image_direct` 不存在而失败。
- 绿：`run_selftests.py -k image_direct`（8 条）；`-k coverage_baseline requirement_traceability print_ratchet layers keyframe asset_skill asset_batch flow_agent image_direct` 184 条 0 红（经 gui_hidden）。断言未动。
- `smoke_test.py --architecture`：411 条，红 4（含 error）：2 条因覆盖率基线未含新模块（已修并复跑绿）；另 `test_skill_reference_injection`（缺 `screenplay-gate-engine.md`）与 `test_agents_md` 性能历史（缺 `维护记录/基准历史.json`）为本 worktree 缺少未入库文件所致，非本轮引入，未复跑通过。

## 未验证
- 未真实起 ComfyUI／生图；界面薄壳 `desktop_image_direct` 的 Tk 回调仅经路由与作业层测试覆盖。
- engine=qwen 且 cloud_assets 云端后端时也走直连（`execute` 内部仍按批次 comfy_config 处理云端），codex／claude 引擎的云端路径不变。
