# R1828 结果：reference_wall.show 改写成类（整理轮）

- 改动：`reference_wall.show` 用 c2c 改写成 `_ReferenceWall`（`__init__(**context)`），函数从 193 行降到薄壳；`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_reference_wall_equivalence.py`，旧实现取 HEAD 原文内嵌；3 组候选（单条、可商用+非商用、弱候选被阈值滤掉），对照初态控件树、逐个点按钮后的控件树与宿主回调。
- 变异检验：按钮文字“重新打分”改一字，差分测试变红，已还原。
- 验证（本轮运行）：差分测试、`tests.test_reference_wall`、函数长度与复杂度门禁均通过；新 Tk 测试已登记 skip 台账。
- 断言未动。
