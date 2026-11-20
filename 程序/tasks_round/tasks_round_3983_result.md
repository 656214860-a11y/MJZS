# R3983 结果
<!-- round-evidence: {"commit_base": "beab5c97", "credential_hits": 0, "evidence_sha256": "2b0ede4eb4456681", "exit": 0, "failed": 0, "passed": 118, "round": 3983, "tests": "run_selftests.py -k files_panel"} -->

任务卡：L4-U2（文件面板筛选区去掉重复的下拉框），工作树 `l4-files-panel`，分支 `codex/l4-files-panel`。

## 三问

1. **本轮类型**：§3.1 功能轮（UI 界面层优化，任务书 L4-U2）。
2. **测试跑了吗**：跑了。unittest 模块全量 110/110 绿；默认冒烟 9/9 通过；`--affected files_panel` 定向自检全绿（10 项，ALL TESTS PASSED）；`--architecture` 架构门禁 684 项全过。全量 `--all --safe` 未跑（分支车道不累计，按任务卡不跑）。
3. **欠账少了吗**：少了。阶段选择只剩右缘图标列一个入口，筛选区重复的「阶段」下拉框删除；四个剩余下拉框按取值自适应像素宽，不再写死字符宽截断取值。

## 改动文件

- `ui/desktop_files_panel_filters.py`：删 `stage_box` 与 `FILTER_STAGE_WIDTH`/`FILTER_BOX_WIDTH` 常量；`_build_filter_bar` 改为第一行「关键字＋刷新」、第二行 FlowBar 放「类型框＋状态框＋尾框」，尾框内依次是「分组」名称＋下拉框、「排序」名称＋下拉框（`fill='y'` 顶对齐，名称随框整体换行不拆散）；四个 SelectBox 按取值实测像素宽自适应（fit）；`_apply_filters` 不再读 `stage_box`；`show_stage()` 是 `stage_filter` 唯一写入方，并同步 `script_title` 为「项目文件 · <阶段名>」（None＝「项目文件 · 全部阶段」，素材库视图＝「项目文件 · 全局素材库」）；库视图禁用／恢复逻辑改作用在剩余下拉框上。
- `tests/test_files_panel_stages.py`：新增 `FilterDedupTests`（T1–T4）；`test_filter_bar_has_four_boxes_and_a_keyword_entry` 断言 `stage_box` 不存在；T5 把 stage_box 驱动的既有用例改为 `show_stage()` 驱动，断言不变。
- `tasks_round/tasks_round_3983_result.md`：本文件。

## 改前失败输出（`logs/l4u2_pre_red2.log`，16 条用例 1 error＋3 failures）

```
ERROR: test_group_sort_pair_wraps_aligned_with_kind_box
T3：880×600 下「分组」名称文字换行后左边缘与类型框左边缘一致。
StopIteration            # 筛选区里找不到「分组」名称文字

FAIL: test_clicking_stage_icon_updates_panel_title
T4：点阶段图标后面板标题随之变化。
AssertionError: '项目文件' == '项目文件'   # 点图标前后标题不变

FAIL: test_each_dropdown_fully_shows_current_value
T2：两档窗口下四个下拉框实际宽 ≥ 当前取值文字宽＋箭头区宽。
AssertionError: 63 not greater than or equal to 83 :
1280x800 kind_box：实际宽 63 < 取值「全部类型」宽 52＋箭头区 31

FAIL: test_filter_controls_sit_on_two_rows_at_wide_window
T1：1280×800 下筛选区控件只占两行（按控件顶边坐标分组计数）。
AssertionError: 4 != 2 : [578, 615, 652, 689]
```

（另：`test_filter_bar_has_four_boxes_and_a_keyword_entry` 改前因 `stage_box` 存在而红，`logs/l4u2_pre_red.log` 留有证据。）

## 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py logs\l4u2.log . -- PY -B -m unittest tests.test_files_panel_stages -v` | ✅ `Ran 110 tests` / `OK` |
| `PY -B smoke_test.py` | ✅ 通过 9 项，失败 0 |
| `PY -B smoke_test.py --affected files_panel` | ✅ 通过 10 项（自检 `ALL TESTS PASSED`，选中 test_files_panel＋test_files_panel_stages 两文件） |
| `PY -B smoke_test.py --architecture` | ✅ `Ran 684 tests` / `OK` |

实测几何（`$TEMP/l4_probe.py`，隐藏桌面）：1280×800 下面板 480px，四个下拉框＋两个名称同处第二行；880×600 下「分组」「排序」整组换到第三行且「分组」左边缘与类型框一致；各框实际宽 ≥ 取值文字宽＋箭头区宽，无截断。

## T5 驱动方式转换清单（断言不变）

- `FilterBarTests.test_kind_and_stage_combine`：`stage_box.set('资产管理')` → `show_stage('assets')`
- `FilterBarTests.test_keyword_filters_by_name`：`stage_box.set('全部阶段')` → `show_stage(None)`
- `FilterBarTests.test_status_filter_matches_published`：`stage_box.set('全部阶段')` → `show_stage(None)`
- `FilterBarTests.test_clearing_conditions_restores_full_index`：`stage_box.set('资产管理'/'全部阶段')` → `show_stage('assets')/show_stage(None)`
- `GlobalLibraryViewTests.test_library_view_disables_stage_controls`（原名近义）：`stage_box` 不存在后，禁用／恢复断言改验同排 `status_box` 的 `disabled`/`readonly`
- `FilterBarTests.test_filter_bar_has_three_boxes_and_a_keyword_entry` → 改名 `test_filter_bar_has_four_boxes_and_a_keyword_entry`，断言 `not hasattr(panel, 'stage_box')`

说明：`show_stage()` 本身会触发一次索引重载（原 `stage_box.set()` 不触发），转换用例中的 `self.pump(.2)` 统一换成现成 `self.wait_index()`，等渲染完成再断言——`--affected` 首跑曾因此在分片环境红了 `test_status_filter_matches_published`（0 != 2，竞态），改用行为级等待后复跑全绿。断言本身未动。

## 备注

- `pet_skills_manage.py` 的同名 `stage_box` 属另一窗口，按任务卡范围未动。
- 面板初始标题保持 `'项目文件'`（`show_stage`/`show_library` 才改写），`test_files_panel.py:196`、`test_idea_chat.py:1126` 的原断言不受影响，`--affected` 已含 test_files_panel 验证通过。
- 欠账记录：夹具项目文件名都很短时面板收至最窄宽，「分组／排序」尾框会被 FlowBar 钳到可用宽、排序框右缘可能裁掉几像素；真实项目文件名普遍较长（探针实测 880×600 下尾框完整放下），若后续 U3 做省略号截断可一并覆盖。
