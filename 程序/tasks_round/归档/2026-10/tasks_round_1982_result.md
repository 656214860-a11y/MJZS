# R1982 结果（修复轮）

## 用户反馈
1. 制作锁短标签（预设／总控／帧率／赛道／厂商／编剧风格）左侧留白：要的是下拉框往左移，不是文字往右移。
2. 悬停预览卡片（R1964）在真实窗口里仍然看不到。

## 根因
1. 全页统一的标签列宽取的是所有制作锁标签里最长的一个（「视频模型版本」），因此每一列的短标签前都留出了大段空白。
2. `ui_theme.install_window_placement` 会给每个新建的 Toplevel 设置 `-alpha 0`，并在 `<Map>` 时 `grab_set`。卡片浮层一弹出就抢走了 grab，Windows 随即给文件表补发坐标失真的 Leave／Enter，卡片刚显示就被收掉，而且一直是透明的。
   - R1976（`6727ea5c`，分支 `codex/wip-R1976`）已找到这个根因并修复，但该提交一直没有合入 master，也没进用户运行的目录，这是第二次“失败”的原因。
   - R1964 的测试只在隐藏桌面里检查卡片窗口有没有创建，没有在真实程序的窗口规则下检查卡片会不会被收掉、是否可见。

## 改动
- `production_lock_fields`：
  - 折行仍按最宽标签计算，每行放几项不变。
  - 摆放时每一列只取本列最宽的标签（`_fit_columns`），短标签所在列的下拉框随之左移。
  - 第一列宽度变化时，经新增的 `align_label_column` 同步预设／厂商／编剧风格／SKILL 各行。
  - 删除了没有调用方使用的 `horizontal`、`label_width` 两个参数，并从 `test_complexity_ratchet` 登记表中删掉该项（参数数已不超线）。
- `skill_panel`：第一列标签列宽只按预设／厂商／总控／SKILL／编剧风格计算。
- 合入 R1976（cherry-pick，未改其内容）：`ui_popup.make_passive_popup`、`pet_cloud_move_guard`（拖窗时不弹三虎云朵）。
  - `_layers.py`、覆盖率基线（重算为 312 个模块）和 runbook 中的数字已同步。
- 测试：
  - `test_script_file_hover_card` 新增一条：装上 `install_window_placement` 后悬停，卡片 0.3 秒后仍在、不持有 grab、alpha 为 1。去掉 `make_passive_popup` 时这条测试失败，加上后通过。
  - `test_skill_panel_dropdown_layout`：契约有意变更，“所有字段等宽”改为“同列 x 对齐、同列等宽、短标签列紧贴标签”；另新增第一列对齐测试。
  - `test_production_lock_ui`：补改 R1965 留下的旧宽度断言，改为 `select_width`。
  - 其余断言未动。

## 验证
- gui_hidden 定向测试：script_file／skill_panel／production_lock／ui_widgets／tooltip／popup／pet_cloud／desktop_compact／writing_page／coverage／architecture，共 523 条。只剩 4 个历史红，都不是本轮引入：
  - `desktop.py::Desktop` 1303 行 > 1302，master 上已存在，本轮没动 desktop.py。
  - test_agents_md、test_round_baselines、test_skill_reference_injection：worktree 已知红。
- smoke_test 通过；未跑 `--all --safe`。
- 未验证：真实指针下卡片的显示与消失、下拉框左移后的实际观感，需要用户在真实窗口确认。
