# R2950 功能轮结果
<!-- round-evidence: {"commit_base": "180b20f6", "credential_hits": 0, "evidence_sha256": "2eed959fd6de23ea", "exit": 0, "failed": 0, "passed": 786, "round": 2950, "tests": "run_selftests.py -k desktop pet_ui ui_popup ui_tokens ui_widgets asset_detail"} -->

- 轮次类型：功能轮（§3.1）。用户对 R2946 预览的三条修正反馈。
- 测试跑了吗：跑了。三个基线：冒烟检查 8/8；架构门禁当轮实测 470 条、469 绿 1 红（`round_number_continuous`，功能分支状态页按规则只在 master 更新，合并轮复绿，非代码问题）；定向门禁全绿。`project_status.md` 欠账：未新增，历史欠账未扩大。

## 需求落法（3 项）

1. **「token: 0」与「01 XXX」同一行、下方同步上移**：
   - `header_info` 由状态/模型两行堆叠改为单行（状态居左可伸展、模型名贴右），`title_row` 高度随之从 ~40px 收到控件请求高；
   - `ui_tokens.body_padding` 顶距 lg(16)→xs(4)，侧栏 `side` 内边距顶沿 sm→xs、页标题 `pady` 底 sm→xs——「token」与侧栏「01 XXX」落在同一水平带，阶段列表与聊天区整体上移；
   - `align_header` 摘除 `project_block`/`list_top`/`_header_list_gap` 旧下拉框时代几何（该耦合是阶段列表被顶低的根因），标题行高只取 `usage_indicator`/`header_info`/`header_stage_button` 请求高最大值。
2. **「在制作/已完成」图标点不出项目列表**：根因是 `_open_sidebar_popup` 用 `winfo_screenwidth()/winfo_screenheight()` 钳制弹层——主窗在副屏时弹层被钳回主屏坐标系外，实测弹层其实已创建并映射（94x82、152x52 均 viewable）但落在屏幕外。改用 `monitor_bounds(self.win, x, y)` 按主窗所在显示器钳制，副屏/主屏均正确。
3. **资产管理图标点不出「资产清单」**：同上根因，同一修复覆盖 `_assets_nav_toggle`/`_post_project_picker` 两条弹层路径。

## 主要改动

- `desktop_page_nav.py`：`_open_sidebar_popup` 钳制坐标改 `monitor_bounds`（导入自 `ui_popup`）；弹层其余逻辑（Flyout、● 当前项、右键菜单、点外部/Esc 主窗 bind/unbind）不变。
- `desktop.py`：`header_info` 单行化（`header_status` side=left expand、`header_model` side=right）；侧栏 `side` 顶内边距与 `self.title` `pady` 收紧。
- `desktop_layout.py`：`align_header` 删除 project_block/list_top 测量链，`_sidebar_geometry` 去 `_header_list_gap`；docstring 注明旧几何属下拉框时代。
- `ui_tokens.py`：`body_padding` 顶距 lg→xs。
- `ui_components.md`：页头单行与弹层定位描述同步。
- 测试：`test_desktop_compact_layout` 断言迁到新几何（标题行单行、idea_log 与侧栏标题同带）；`test_ui_batch3_shell` 滚轮回弹断言容忍缓动残余（语义仍要求回顶，键盘 Home/End 精确断言保留）。

## 验证记录

- `smoke_test.py`：8/8。
- 定向 `run_selftests.py -k desktop pet_ui ui_popup ui_tokens ui_widgets asset_detail`（789 条）：首轮仅 `test_ui_batch3_shell` 1 红（缓动滚动残余 0.0015≠0），断言修正后复跑 8 条全绿。
- `test_desktop_compact_layout`：5 条全绿。
- `smoke_test.py --architecture`：470 条，469 绿 1 红——`test_round_number_continuous`（功能分支状态页按规则只在 master 更新，合并轮同步即复绿；R2946 同项基线欠账，本轮 `bare_json_load` 已转绿）。
- 噪声：GUI 测试 teardown `invalid command name ...after` 回调为基线同现；`desktop_writing_page.py` `stop_input_hint` Destroy 绑定参数错误为基线既有缺陷，未动。

## 提交

- 待 `dev.py commit` 回填 commit hash 与证据。
