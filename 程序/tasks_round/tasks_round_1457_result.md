# R1457 可靠性轮：统一日志与崩溃钩子（优化清单第 2、3 项）

1. **本轮类型？** 可靠性轮。新增 `app_logging.py`（L1），启动入口接线；不改业务逻辑。
2. **测试与基线？** 新增 `tests/test_app_logging.py` 5 项通过；默认冒烟 8/8；`smoke_test.py --architecture` 340 项全绿；日志相关定向（diagnostic_capture、log_maintenance）通过。本轮改了启动入口（`启动漫剧制作助手.pyw`），按 §5 属风险路径，由 post-commit 后台全量补跑，凭据以 common-dir 实际写入为准。
3. **是否欠账？** 无新增；启动入口全量欠一次，交后台补跑。

## 事实

- 各模块早已使用 `logging.getLogger(__name__)`，但全仓没有任何处理器；pythonw 又没有 stderr，记录实际丢失。
- 真实入口 `启动漫剧制作助手.pyw` 未设置 Tk 的 `report_callback_exception`（只有 `app.py → desktop_launcher` 路径设置），生产中 Tk 回调异常没有落盘。
- 后台线程异常、`sys.excepthook`、`faulthandler` 均无处理。

## 改动

- `app_logging.py`：根 logger 挂 `logs/app.log` 滚动文件（5MB×3，轮转名与 `log_maintenance` 受管名一致），写入前经 `diagnostic_capture.redact` 脱敏；接管 `sys.excepthook`、`threading.excepthook`、Tk 回调（链式调用原钩子）、`faulthandler`（`logs/faulthandler.log`）；崩溃同时写 `diagnostic_capture.record_crash`。幂等，任何失败静默降级。
- `启动漫剧制作助手.pyw`：`app_logging.install()` 与创建 Tk 根后 `install(window)`。
- `tests/architecture/_layers.py`：登记 `app_logging` 为 L1。

## 提交

已提交，见 git log 标题 `R1457:`。
