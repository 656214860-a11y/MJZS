# R864 结果｜Qwen 就绪等待不阻塞 Tk

`qwen_adapter.launch_interactive()` 在启动交互会话后，将窗口命名所需的 `wait_ready()` 交给守护线程；已有会话的续发则由 `desktop.open_flow_agent()` 的 `Desktop.async_()` 执行。Qwen 的 250ms 就绪轮询不会占住按钮回调。

验证：`tests/test_qwen_adapter` 3 条／0 红；新增调用边界回归，冻结命名线程和续发 `Desktop.async_()` 提交。默认 `smoke_test.py` 8/8。

`[TASK_COMPLETE]`：Qwen 适配器的 sleep 调用已有后台边界，并已加入防回退测试。
