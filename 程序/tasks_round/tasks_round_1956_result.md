# R1956 修复轮：快速点击侧栏导航时的文字重影

## 现象与判断
- 用户反馈：快速点左侧阶段目录，09 白模预演以下各行出现文字重影，停几秒自己消失。
- 截图放大：10～13 行下方约 13 px 处残留本行旧文字，只露上半截。说明这些行曾在更低的位置画过，上移后按钮之间的空隙（侧栏框背景）没被失效重画。
- 隐藏桌面探针与真实桌面截帧都没复现（侧栏几何全程不变），位移来源未定位。

## 改动
- `desktop_layout_resize`：user32 载入收拢为 `_user32()`（`PaintFreeze` 改用它，行为不变）；新增 `repaint_area(widget)`，`RedrawWindow(INVALIDATE|ERASE|ALLCHILDREN|UPDATENOW)` 整块擦底重画；控件不可见或非 Windows 时不做。
- `desktop_layout`：`freeze_page_paint` 在一串连续换页的第一次记下侧栏几何（yview、scrollregion、末行 y、项目列表行数、表头间距）；`thaw_page_paint` 落定时对侧栏画布 `repaint_area` 一次，几何前后不同则写 `换页时侧栏几何变化 前=… 后=…`（INFO，进 app.log），用于下次定位位移来源。

## 验证
- `run_selftests.py -k page_paint_freeze ui_motion desktop_compact page_cache`（经 `gui_hidden.py`）67 条全绿；新增 `test_page_paint_freeze` 3 条：连续换页落定后侧栏只重画一次、侧栏几何变化写日志／不变不写、不可见控件不重画。
- `smoke_test.py --affected desktop_layout_resize desktop_layout` 全绿。
- `smoke_test.py --architecture` 406 条：3 红为既有（`test_agents_md` 缺 `维护记录/基准历史.json`、`test_skill_reference_injection`、`test_round_number_continuous`），已在干净 master 上复核同样红；`维护记录/skip台账.json` 补登新测试的 5 处平台 skip。断言未动。
- 未跑 smoke 默认集与 `--all --safe`；重影是否消失需用户在真实窗口复测。
