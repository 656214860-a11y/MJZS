# R2946 功能轮结果
<!-- round-evidence: {"commit_base": "e7807e16", "credential_hits": 0, "evidence_sha256": "a1b19a122a93ad15", "exit": 0, "failed": 0, "passed": 785, "round": 2946, "tests": "run_selftests.py -k desktop pet_ui ui_popup ui_tokens ui_widgets asset_detail"} -->

- 轮次类型：功能轮（§3.1）。用户 9 项侧栏改版需求（R2933 预览后的第二轮反馈）。
- 测试跑了吗：跑了。三个基线：冒烟检查 8/8；架构门禁当轮实测 470 条、468 绿 2 红（两条均非本轮代码，见「验证记录」）；定向门禁分批全绿。`project_status.md` 欠账：未新增，历史欠账未扩大。
- 说明：开工时暂定 R2940，提交前 `round_claim.py next` 核实 master 已推进、最新可用轮次为 R2946，分支更名 `codex/wip-R2946`（未提交改动由工具原样带入），全库「R2940」注释同步改为「R2946」。

## 需求落法（9 项）

1. **删「我的项目」标签**：侧栏项目区上方的分组标签整块移除。
2. **阶段名移到左侧**：页标题「0X  名称」以 `EllipsisLabel` 放在侧栏滚动区顶端（`scroll.form`，避开 `side` 的 sm 内边距）；轨宽 92→96、字号 heading_3(12pt)→body_bold(10pt)，实测最长页名「0X  连贯性清单」89px ≤ 可用 92px，不再截断，Tooltip 留全文。
3. **Token 排版优化**：页头只剩标题行（Token 用量靠左、状态／模型靠右）；`align_header` 改为给 `usage_indicator` 套内容区内缩对齐，标题行候选高度去掉已搬走的 `self.title`。
4. **齿轮上移对齐图标轨**：`settings_rail_button` 作为导航末位 `RailIcon.TButton`（Fluent `settings.png`，点开既有设置 hub，`pet.act(pet.open_settings)`）；`pet_ui_settings.build_gear` 在真桌面有 `settings_rail_button` 时不再建底栏齿轮，无该控件的宿主仍走 `settings_gear_layer`/`pet_dock` 承载。
5. **资产清单二级图标**：常驻入口删除；点「05 资产管理」图标弹 `Flyout` 单选层（仅「资产清单」一项），激活时该图标临时换 `asset_list.png`（`_nav_icon_name` 跟踪），清单页激活中再点图标回资产管理主页（`asset_roster` 复位）。
6. **项目下拉框删除**：常驻 `SelectBox` 移除；「在制作／已完成」图标点击弹 `_post_project_picker` 的 `Flyout` 项目层（● 标当前项、右键项目菜单、「项目管理…」入口），`_picker_items` 保留为数据模型；窗口标题仍是项目名唯一展示位。
7. **三虎簇正方形**：`pet_ui_view._cluster_layout` 动态计算簇区边长 `side=max(内容宽, 内容高+边距)`，左列头像(48→44)＋小字、右列猫爪(16→14) 对整组垂直居中，命中区右沿钳在 dock 内；`DOCK_ROOM` 初值即边长，运行时 `patch_room` 跟实测簇高。
8. **左右间距收窄**：`body_padding` 左距 xl(24)→sm(8)，侧栏 +4px 后内容区净增宽 12px。
9. **图标放大**：`build_nav_icons.py` RENDER_PX 36→48、TARGET_PX 18→24，`assets/nav/*.png` 全量重生成。

## 主要改动

- `ui_popup.py` 新增 `Flyout`（无边框 Toplevel＋1px 描边壳，复用 `make_passive_popup`/`monitor_bounds`）。
- `desktop_page_nav.py`：`_open_sidebar_popup`/`_close_sidebar_popup`/`_sidebar_popup_outside`/`_sidebar_popup_destroyed` 侧栏弹层基座；**点外部／Esc 监听改主窗 `bind`/`unbind(seq, funcid)`**——修掉 `bind_all` 无法按 funcid 摘除、`unbind_all` 连坐其它 all 绑定的缺陷；`_assets_nav_toggle`/`_open_asset_flyout`/`_post_project_picker`/`_popup_row`/`_popup_pick_project`/`_popup_manage_projects`。
- `desktop.py`：`self.title` 改挂 `scroll.form` 顶端（`EllipsisLabel`，`FONTS['body_bold']`）；`settings_rail_button` 入导航末位；`sidebar_dock` 只剩 `pet_dock`。
- `desktop_project_pages.py`：删 `SelectBox` 常驻选择器与 `project_picker_menu`，`_sync_project_picker` 退化为 `_picker_items` 数据同步；`set_project_group(state, popup=True)` 转发弹层。
- `desktop_layout.py`：`align_header` 候选高度去 `self.title`，左内缩对齐转给 `usage_indicator`；`pet_dock` 高跟 `patch_room`。
- `pet_ui_view.py`/`pet_ui_support.py`/`pet_ui_settings.py`/`pet_ui.py`：`_cluster_layout` 正方形簇、`DOCK_CLUSTER_W`/`DOCK_PAW_GAP` 等常量重写、`GearButton` 真桌面让位轨钮。
- `ui_tokens.py`：`sidebar_width` 92→96（含实测注释）、`body_padding` 左距收紧、`PET_LAYOUT` 头像/爪缩小。
- `scripts/build_nav_icons.py`＋`assets/nav/*.png`：图标放大一档全量重生成。
- `ui_components.md` 侧栏两段同步 R2946 结构。

## 测试契约变更（§2.4）

- 弹层取代下拉框：`test_asset_detail`/`test_project_switch_guard`/`test_project_rename_reconcile`/`test_desktop_compact_layout` 断言迁到 `_sidebar_popup_win`、`_picker_items`、`_nav_icon_name` 临时字形。
- 三虎簇正方形：`test_pet_ui`/`test_pet_settings` 断言迁到 `_cluster_layout()` 实测几何与 `patch_room`。
- `test_ui_batch3_shell`：页标题字号断言 heading_1→body_bold（标题收进图标轨顶行）。
- `test_pet_settings` 齿轮 seam：`winfo_ismapped` 在 withdrawn 窗恒假，改 `winfo_manager=='pack'`＋显式 `geometry` 后验 `rooty` 次序。
- `test_desktop_compact_layout`：`d.title.winfo_parent()` 断言由 `d.sidebar` 改 `d.sidebar_scroll.form`。

## 验证记录

- `smoke_test.py`：8/8。
- 定向 `run_selftests.py -k account_entry pet_settings batch3_shell asset_detail compact_layout startup_perf`：135 条全绿（首轮广跑 6 文件红已全部修复复绿）。
- 定向 `run_selftests.py -k pet_ui ui_motion project_switch_guard project_rename_reconcile page_lock`：675 条全绿。
- 此前定向：popup/asset 相关 21 条、pet 三项 3 条全绿。
- `smoke_test.py --architecture`：470 条，468 绿 2 红——
  - `test_round_number_continuous`：功能分支 `project_status.md` 按规则只在 master 更新（分支上 2916 落后最新结果 2933），合并轮同步状态页即复绿，非代码问题；
  - `test_bare_json_load_debt_is_a_nonincreasing_subset`：在干净 master（R2944）同测同红约 70 条登记外 `json.loads` 命中，属既有基线欠账，与本轮改动无关（本轮未新增任何 `json.loads`）。
- 噪声：GUI 测试 teardown `invalid command name ...after` 回调为基线同现；`desktop_writing_page.py:346` Destroy 绑定参数错误为基线既有缺陷，未动。

## 提交

- 待 `dev.py commit` 回填 commit hash 与证据。
