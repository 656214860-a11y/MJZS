# R596｜修复轮：最小化恢复后的主页面滚动

## 本轮结论

- 本轮是修复轮：主窗口从最小化恢复时，整页画布的滚动区域可能尚未按新可视高度重算，首枚滚轮因此偶发无效。
- 测试已运行：新增的恢复后滚轮回归、受影响 UI 测试、默认冒烟和架构门禁结果记录在本轮验证节。
- `project_status.md` 欠账未减少：本轮修复独立 UI 生命周期问题，不对应 R182 余项。

## 根因与修复

- 根因：`desktop.py` 的 `fit_content()` 合并为 `after_idle` 布局任务；最小化恢复的画布尺寸变化与用户首枚滚轮存在时序竞争，滚轮可在更新滚动区域之前到达。
- 修复：主窗口 `<Map>` 时调用已有 `fit_content()`，仍由其合并空闲任务实际计算。没有同步强制布局、没有改变滚轮分流，也不影响局部 `Text`／`Treeview`／下拉列表滚动。
- 回归：覆盖“恢复入口完成布局后，落在主页面画布的第一枚向下滚轮会移动页面”。

## 文件范围

- `desktop.py`
- `tests/test_ui_edges.py`
- `project_status.md`
- `tasks_round/tasks_round_596_result.md`

## 验证与自审

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_ui_edges.UiEdgeTests.test_restored_main_window_recomputes_page_scroll_before_wheel`：1/1 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --affected desktop`：7/7 通过。自检增量台账临时文件权限提示仍为受限运行环境写入边界，不影响测试结果。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：101/101 通过。
- 自审：通过。修改仅覆盖窗口恢复与回归；无用户项目数据写入、无新依赖；同类滚轮分流仍由既有局部控件规则处理。
