# R854 结果｜UI 线程 sleep 调用链审计

## 结论

- `native_assets.run()` 与 ComfyUI 检测回退均通过 `Desktop.async_()` 执行；循环 sleep 不接触 Tk。
- `asset_thumbs.settle()` 只供测试收敛；worker 的轮询 sleep 在独立后台进程。
- `storage_maintenance.main()` 的三秒等待仅位于 `--cleanup` 命令行入口。

未发现静态可证实的 Tk 回调直达 sleep；仍需实机卡顿证据才可关闭台账中的 A 级实测挂账。

`[TASK_COMPLETE]`：完成静态调用链裁决，不把未做实机验证误报为已修复。
