# R618 修复轮结果：新增 SKILL 说明刷新与窄窗口换行

- 本轮是功能轮还是整理轮？修复轮。
- 测试跑了吗？三个基线过了吗？新增专项 3/3、默认 `smoke_test.py` 8/8 通过；架构基线和全量基线本轮未运行。受影响 SKILL 门禁命中后仍有 2 条既有独立失败，故三个基线未全部通过。
- `project_status.md` 的欠账少了吗？没有；已按连续轮次规则将台账从“616 待执行”校正为“619 待执行”（完成至 R618），但本轮未减少既有 P3 债务。

## 根因与修复

1. 新增 SKILL 不刷新说明：`build_notes()` 只在面板创建时，以 `flow_skill_choices()` 的固定候选构建 `note_items`；`save_flow_skill()` 新增了勾选框与配置，却没有更新该列表或 Listbox。
   - 新增 `note_entries()`，在固定工作流顺序后补入 `flow_vars` 中用户新增的路径。
   - 新增 `refresh_notes()`，重建说明目录并优先选中刚新增的路径；`save_flow_skill()` 与删除路径均调用它。

2. 窄窗口遮挡：所有流程 SKILL 控件原先都 `pack(side='left')` 到同一 Frame，Tk 的 pack 不会自动换行。
   - 改为把管理框、勾选框、阶段附加项和删除按钮登记到 `skill_controls`。
   - Frame 宽度变化后以空闲回调按请求宽度分配 grid 行；放不下即转入下一行。
   - 首次实现暴露“窗口销毁后 idle 回调仍执行”的 Tk 生命周期问题；`Panel.destroy()` 及 `<Destroy>` 事件现在都取消该回调，受影响门禁复跑后未再出现 `invalid command name ...layout_skill_controls`。

修改文件：

- `skill_panel.py`：说明目录刷新、勾选项自动换行、换行回调生命周期管理。
- `tests/test_skills.py`：新增后的说明同步断言与窄宽度多行布局断言；测试因新增 UI 契约而扩展，既有断言未弱化。
- `project_status.md`：校正已完成轮次与当前待执行编号，并登记 R616–R618 的完成事实。

## 验证

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B -m unittest tests.test_skills.PanelTests.test_a_skill_picked_by_hand_is_remembered_as_a_path tests.test_skills.PanelTests.test_skill_controls_wrap_into_multiple_grid_rows_when_narrow tests.test_skills.PanelTests.test_the_panel_shows_the_skill_markdown
```

结果：`Ran 3 tests in 0.448s`，`OK`。

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py
```

结果：8 项通过，0 项失败。

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py --affected skill_panel
```

结果：本轮新增的 Tk 回调残留已修复；定向门禁最终只剩两条既有独立失败：

1. `PanelTests.test_the_skill_boxes_follow_the_flow_order`（`tests/test_skills.py:1241`）：实际音频项多出 `pipeline-audio-subtitle`，旧断言只期待四项。
2. `ToolTests.test_every_tool_in_the_registry_is_known`（`tests/test_skills.py:539`）：`skill_tools.missing(names)` 返回 18 个未注册工具名。

两项均不涉及说明刷新、控件布局或 Tk 回调；本轮未修改其根因模块。

## 自审

- 新增 SKILL 后，说明目录与正文同步更新；阶段配置缩窄时控件会自动分行。
- 未修改 SKILL 注册规则、配置格式、用户项目数据、删除范围或 `/` 补全。
- 未引入越界依赖；所有变更仍在 L4 面板与既有测试/状态台账范围内。
- 同类检查：删除后也刷新说明目录；顶层窗口关闭与面板自身销毁均会取消布局回调。
- 自审结论：本轮功能与默认冒烟通过；受影响完整门禁仍因两条既有失败未通过。
