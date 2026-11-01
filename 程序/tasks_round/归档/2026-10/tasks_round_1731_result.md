# R1731：功能轮——阶段配置页「更多制作锁」上移、SKILL 下拉按内容收窄、勾选框并入 SKILL 行（SPMORE）

执行者：DeepSeek Harness（lane_spmore）。执行方改完代码后会话结束，未写结果文件；本文件由 Claude 按车道 diff 与独立复验补写。

## 改动

- `production_lock_fields.py`：`FlowFields` 新增 `insert_after`（插到指定 key 项后参与流式换行）、`remove`；重排时跳过已销毁控件；`fill_last` 行没有 `grow` 项时不再把余宽强塞给最后一项。
- `skill_panel.py`：
  - 「更多制作锁」按钮和 `lock_notice` 改为制作锁流式布局里紧跟 `material_source` 的两项，取消单独的 `lock_status` 行；提示文字变化后调 `schedule()` 重排。
  - SKILL 操作行改为 `fill_last=False`，下拉框不再 `grow`；勾选框（≤10 项）直接流式排进操作行，去掉 `width=28`，外部包提示排在勾选框之后。
  - >10 项仍走原滚动容器三列网格（未改）。总行数 1500（门禁上限）。
- 测试（契约有意变更，断言未弱化为空检查）：
  - `tests/test_skill_panel_dropdown_layout.py`：新增 4 条真 Tk 几何用例（按钮同行右侧、下拉按内容定宽、首个勾选框同行右侧、最小窗不越界）；锁布局用例把按钮/提示纳入越界检查；`test_skill_action_row_has_no_right_blank` → `test_skill_action_row_flows_checkboxes_without_overflow`（删去「行右侧不留空白」，因下拉框不再撑满，属用户要求改掉的旧契约，越界检查保留）。
  - `tests/test_skills.py`：`:1077` 打包顺序参照 `skill_list_outer` → `skill_content`（≤10 项时已无 `skill_list_outer`）；`:1622` 三列网格行列断言 → 勾选框在操作行内且不用 grid；`:1638/:1656` 去掉列号断言，保留不越界断言。其余断言未动。
  - 任务书范围外两处（同一契约变更的直接后果）：`tests/test_production_lock_ui.py:41` 子项数 `+1` → `+3`（按钮与提示进入 `lock_fields`）；`tests/test_skill_panel_imported.py:41` `winfo_manager()=='grid'` → `box.master is panel.flow_skill_row`。

## 先红后绿（Claude 复验）

产品代码退回 HEAD、只留新测试：

```
FAIL test_more_locks_button_sits_next_to_material_source: 66 not less than or equal to 2 : 更多制作锁按钮应与素材来源下拉框同一行
FAIL test_skill_action_dropdown_width_fits_content_not_row: 380 not less than or equal to 151 : 下拉框应按内容定宽，不再撑满整行
FAIL test_first_checkbox_sits_next_to_skill_dropdown: 35 not less than or equal to 2 : 第一个勾选框应与 SKILL 下拉框同一行
Ran 4 tests — FAILED (failures=3)
```

第 4 条（最小窗不越界）改前改后都绿，是防回退护栏。恢复改动后全绿。

## 实际计数

- `run_selftests.py -k test_skill_panel test_skills test_production_lock test_idea_inline_brief test_ui_batch5`：214 条，0 个文件有红。
- `smoke_test.py`：8/8 通过。
- `smoke_test.py --architecture`：368 条，仅 `test_full_safe_all_is_required_after_eight_source_rounds` 1 红（全量欠账，后台补跑，不阻断）。
- 目视：1280×800 收起/展开、920×615 三张截图，按钮在素材来源右侧、下拉框按内容收窄、勾选框跟在下拉框右侧依次排、窄窗外部包提示换到下一行（截图在 `工作流任务/commit_tools/pSPMORE/`）。

## 需裁决

1. SKILL 超过 10 项仍在下方滚动区三列排（任务书第 4 条，保持现状）。
2. 截图中「预设」「厂商」标签被裁半个字，改前同样存在，不是本轮引入，另行处理。

## 独立验收（Claude，主工作区）

- 车道 diff 干净应用到 R1730；`skill_panel.py` 1500 行（未超门禁上限）。
- 先红后绿、定向、冒烟、架构计数见上文，均为 Claude 本人在本轮实际运行。
- 执行方越出任务书改了 `test_production_lock_ui.py`、`test_skill_panel_imported.py` 各一条断言，均为同一布局契约变更的直接后果，Claude 审过接受。
