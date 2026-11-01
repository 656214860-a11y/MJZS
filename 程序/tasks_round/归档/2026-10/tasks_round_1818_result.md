# R1818 结果（整理轮）

- 新增差分测试 tests/test_preparation_step_equivalence.py：旧 _preparation_step 原样内嵌，同一段 8 轮对话（含修订、推进、无标题回答、进入自然剧本）分别驱动旧／新实现，逐轮对照发给模型的请求、返回值与 preparation_state.json。改动前这段请求正文没有任何测试覆盖（改一个字现有测试全绿）；现在改一个字就红。
- writing_api._preparation_step：10 个参数 → 参数对象 `_PreparationRequest`（namedtuple）+ 4 个关键字参数；拼请求正文的 32 行抽成 `_preparation_task`；函数从 181 行降到 150 行。删除 PARAM_CAPS 与 OVERSIZE_CAPS 中该项。唯一调用点 writing_api.reply 同步。
- 验证：-k writing_api script_agent preparation writing_restart architecture，仅剩常驻红 test_round_number_continuous。断言未动。
