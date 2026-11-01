# R1823 结果：压平 App.tick 的嵌套（整理轮）

- 改动：`app.py` 把结果收尾块抽成 `App._tick_result(ok, value)`，`tick` 嵌套降到 5；两处 phase 赋值并到同一行，`App` 类行数保持 1388。`test_complexity_ratchet.py` 删除 `('app.py','tick')` 登记。
- 新增差分测试 `tests/test_app_tick_equivalence.py`：旧实现原文内嵌，26 种场景（消息、成功／失败、静默轮询、渲染异常、定时到期、Tk 退出等）逐次对照调用记录与状态；变异检验（失败提示改走 notifier）能使其变红。
- 断言未动。
- 本轮验证：`run_selftests.py -k app_tick complexity_ratchet function_size app video` 全过。
