# R3139 结果（任务书 P1 重放：阶段图标列＋筛选条，基于 master 新面板结构）

- 轮次类型：功能轮（任务书《统一项目文件生命周期管理》P1；分支 `codex/wip-R3139`）。
- 背景：R3136 合并轮已把 P0／P2／P3／P4 合入 master；P1 因 master 的 `ui/desktop_files_panel.py` 已改为 `panel_area` 停靠列结构，整份替换会抹掉 R3060 改动，故本轮改为**在新结构上逐点重放**。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（既有面板加阶段图标列与筛选条，7 处小编辑，不改启动路径）。
2. **测试跑了吗、三个基线过了吗？** 跑了。默认冒烟 **9/9**；架构门禁 **483/483 全绿**（`test_round_number_continuous` 在本轮也绿，因为 master 抬头与最新结果同步）；面板定向 **29 条 0 红**。
3. **欠账少了吗？** 减少：P1 的「阶段快捷图标列」与「四条件筛选条」从悬置分支落回主线，且**没有回退 master 的 R3060 停靠列改造**。

## 本轮改动（相对 master）

| 文件 | 改动 |
| --- | --- |
| `ui/desktop_files_panel_filters.py`（新，L4） | `FilesPanelFilterMixin`：两行筛选条（阶段／类型／状态 `SelectBox`＋关键字 `LineInput`）、阶段图标列（「全部」＋13 阶段＋♻／🗑）、`show_stage`／`_apply_filters`／`_fill_index_list`／`_reset_filters`／`_ensure_filter_state` |
| `ui/desktop_files_panel.py` | 7 处：import 混入、类基类、建 `stage_rail` 并 `_build_stage_rail()`、`_build_filter_bar()`、`_reload_current_view()`（`open_panel` 与 `project_changed` 改调用并复位筛选）、`open_script_file` 支持相对行 id、`script_menu` 对索引行只给「查看」 |
| `tests/test_files_panel_stages.py`（新） | 12 条：图标列位置与顺序、Tooltip、索引填表、高亮、「全部」回四类视图、换项目复位、♻／🗑 入口、筛选条四条件 |
| `tests/architecture/_layers.py` | 新模块登记 L4 |
| `维护记录/覆盖率基线.json`、`runbook.md` §11 | 新增 1 个生产模块后刷新（691 模块），数字同步 |

## 验证

- `smoke_test.py`：**9/9**
- `smoke_test.py --architecture`：**483/483 全绿**
- `run_selftests.py -k test_files_panel_stages test_files_panel`：**29 条 0 红**

## 剩余

P1 改动表内的「按阶段分组（可折叠）」与「图片缩略图列」尚未实现；《任务完成文件》待这两项完成后输出。
