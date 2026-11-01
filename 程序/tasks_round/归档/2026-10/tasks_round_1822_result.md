# R1822 结果：压平 _tick_async_result 的嵌套（整理轮）

- 改动：`desktop_async_tasks.py` 把失败收尾抽成 `_async_failed`，`_tick_async_result` 嵌套降到上限内；`test_complexity_ratchet.py` 删除该函数的 NESTING_CAPS 条目。
- 新增差分测试 `tests/test_tick_async_result_equivalence.py`：旧实现原文内嵌，15 种结果逐次对照调用记录与状态。
- `tests/test_desktop_automation_service.py`：宿主替身补上 `_async_failed`，照样跑真方法（契约变更同步 mock）。断言未动。
- 本轮验证：`run_selftests.py -k tick_async_result desktop_automation_service complexity_ratchet` 全过；`-k architecture` 仅预期常驻红 test_round_number_continuous。
