# R1831 结果：desktop_idea_chat.send_message 拆出回复回调（整理轮）

- 改动：`send_message` 里直连 API 的嵌套回调 `received` 提升为方法 `IdeaChatMixin._idea_api_received(token, model, request_model, result)`，原处改为一行 lambda；函数从 171 行降到 110 行；`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_send_message_equivalence.py`，旧实现取 HEAD 原文内嵌；宿主替身与 writing_api／idea_chat／stage_config 等全部记账，新旧实现走同一条直连发送路径，再把截获的回调喂 10 种模型结果 × 3 种宿主状态，对照完整调用记录。先用旧实现自比为绿；改写后首次运行即抓到新方法漏了 `import idea_chat`，已补。
- 变异检验：失败提示“请稍后重试”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、test_idea_chat（124 项，1 项红：`test_initial_brief_discovery_failure_is_visible_without_blocking_input`，换回 HEAD 原文同样红，非本轮引入）、`run_selftests.py --architecture` 通过。
- 断言未动。
