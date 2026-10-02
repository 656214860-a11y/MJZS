# R557｜功能轮｜三虎右键进度与待确认项提示框

## 结果

- 三虎右键的「进度面板」和原「查看待确认详情」均不再调用 `Desktop.pet_show_text()`，因此不会创建只读弹窗。
- 两项改为直接复用三虎旁的圆形提示框，分别展示完整分节进度和待确认项内容；原菜单名已改为「待确认项」。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `pet_ui.py` | `show_panel()`、`show_details()` 直接写入 `progress_bubble()`；新增 `DETAIL_MENU_LABEL = '待确认项'`；右键菜单对这两项关闭二次单行播报，保留多行内容。 |
| `tests/test_pet_ui.py` | 更新旧弹窗契约为提示框契约，覆盖宿主弹窗入口不会被调用、菜单新名称与进度提示框展示；保留主动查看后自动播报让路的语义。 |

## 验证

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.test_pet_ui.DetailsTests tests.test_pet_ui.MenuFeedbackTests tests.test_pet_ui.PetClickTests tests.test_pet_ui.PanelQuietTests` | 22/22 通过。 |
| `python smoke_test.py` | 8/8 通过。 |

## 自检

- 右键触发的两项均不再经过 `pet_show_text()` / `prompt_window`，而是在已有的窗口内三虎提示框显示对应文本。
- `act(..., speak=False)` 仅用于这两个已自行展示多行提示框的入口，避免后续统一播报把换行压成一行；其他菜单行为不变。
- 未改用户数据、阶段状态或其他页面。
