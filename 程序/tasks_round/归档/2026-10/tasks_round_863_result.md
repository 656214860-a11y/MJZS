# R863 结果｜退出维护 sleep 不阻塞界面

关闭后的项目维护在独立 `storage_maintenance.py --cleanup` 进程中先延后三秒再扫描；退出 UI 仅调用 `launch_background()`，不会在 Tk 或启动路径等待。

验证：项目运行器定向 `run_selftests.py --safe test_storage` 9 条／0 红。新增回归替换后台启动器，断言命令精确为当前解释器加 `storage_maintenance.py --cleanup`，并且 stdin/stdout/stderr 均脱离标准流。完整安全全量 `run_selftests.py --all --safe`：3,706 条／641.2 秒／0 红；已将全量基线轮次更新为 R863。

`[TASK_COMPLETE]`：退出维护的 sleep 已确认不在 UI／启动线程，专项与完整安全全量均通过。
