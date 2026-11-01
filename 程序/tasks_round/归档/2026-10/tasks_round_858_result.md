# R858 结果｜安全模式取消隔离子进程派生

Windows 宿主会拒绝复制隔离子进程句柄；R857 的“启动时回退”仍不能覆盖子进程启动后才暴露的句柄复制失败。安全模式现直接在当前进程依次执行真实测试单元，不再创建隔离进程；非安全串行模式仍保留原有进程隔离与超时回收。

验证：`tests.test_selftests` 21 条／0 红；`run_selftests.py --safe -k selftests` 21 条／0 红；`run_selftests.py --layer architecture --all --safe` 226 条／69.9 秒／0 红、`ALL TESTS PASSED`。同步更新 JSON 读取棘轮中因 R856 新增异常类型而漂移的两个既存 `comfy_service.py` 定位，不新增读取入口。

`[TASK_COMPLETE]`：安全模式不再依赖 Windows 上可能失败的隔离子进程派生，架构门禁全绿。
