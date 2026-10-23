# R1936 结果：测试治理阶段2——环境变量与 Tk 样板收拢

轮次类型：修复轮（测试资产整改）。分支 claude/affectionate-goldstine-5e7003。

## 改动
- 新增 `tests/env_test_support.py`（`patched_env(test, **kv)`，基于 `mock.patch.dict(os.environ)`，用例结束自动还原）；替换 `test_asset_thumbs`、`test_ui_edges`、`test_leak_teardown`、`test_token_saver` 四处手写还原（共约 30 行样板）。其余约 8 处 `os.environ.pop` 属 `try/finally` 或模块级辅助，逻辑各异，未动。
- 新增 `tests/tk_test_support.py`（`make_root()` 无显示抛 SkipTest 并引用登记常量，`pump(window, seconds, idle_first)`）；迁移 `test_account_entry`、`test_account_page`、`test_desktop_compact_layout`。`test_desktop_startup_perf` 用例内逐个 `skipTest` 的写法保持不动。类级共享窗口结构未改。
- **断言未动**，无新增 skip。

## 未做
- `sys.path.insert` 清理：这些测试文件头部注明可 `python test_x.py` 直接运行，删掉会破坏直跑，且收益只是去样板，本轮不做。

## 验证
- `run_selftests.py -k asset_thumbs leak_teardown token_saver ui_edges`：ALL TESTS PASSED。
- `run_selftests.py -k account_entry account_page compact_layout`：ALL TESTS PASSED，实际跳过 0 条。
- 未运行：`smoke_test.py`、`--architecture`、`--all --safe`。
