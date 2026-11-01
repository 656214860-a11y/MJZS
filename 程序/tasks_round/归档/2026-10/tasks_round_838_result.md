# R838 结果：覆盖率审计 25 事件契约同源

- 覆盖率审计 25 改以 `pet_bus.CONTRACT` 为唯一事件名权威源，不再维护手写事件白名单。
- 扫描器现正确读取 `pet_bus.emit_safe(bus, errors, kind, ...)` 的第三参数，并覆盖所有 `*._emit(kind)` 静态字面量调用；金丝雀同步改为真实参数形状。
- 运行期共有 38 个静态字面量事件发送点，均在 `pet_bus.CONTRACT` 中登记；冻结谓词、判据文档和台账 pending 三源均为 0。

## 验证

- `run_selftests.py -k coverage_audit_ratchet --safe`：4 条／0 红。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：219/219 通过（52.577 秒）。
- R838−R837=1，未触发每三轮一次的完整安全全量；`last_full_safe_all_round` 保持 R837。
