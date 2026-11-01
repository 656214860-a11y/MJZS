# R1827 结果：native_assets.attach_controls 改写成类（整理轮）

- 改动：`attach_controls` 用 c2c 改写成 `_AssetControls`（闭包状态挂实例，`__init__(**context)` 避开参数上限），函数长度从 167 行降到 2 行薄壳；`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_native_asset_controls_equivalence.py`，旧实现取 HEAD 原文内嵌；空选/有选两种，对照初态控件树与逐个点按钮后的控件树、宿主回调。新增公共件 `tests/window_diff_support.py`（抹掉 PY_VAR 序号）。
- 变异检验：按钮文字“预估费用”改一字，差分测试 2 项变红，已还原。
- 验证（本轮运行）：差分测试、`tests.test_asset_gating`、`test_skip_hygiene`、函数长度与复杂度门禁均通过；新 Tk 测试已登记 skip 台账。
- 断言未动。
