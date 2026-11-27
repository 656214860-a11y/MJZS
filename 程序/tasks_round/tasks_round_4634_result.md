# R4634 结果：C20 移除 `test_ui_theme.py` 未登记 `skipTest` 以通过静态门禁
<!-- round-evidence: {"commit_base": "5dfa74fd8", "credential_hits": 0, "evidence_sha256": "38038653325b61ff", "exit": 0, "failed": 0, "passed": 52, "round": 4634, "tests": "run_selftests.py -k test_ui_theme test_skip_hygiene"} -->

1. **轮次类型**：静态门禁返修轮（卡 C20，分支 `codex/opt-c20-theme-live`，工作树 `.wt/opt_c20`）。
   - 移除 `tests/test_ui_theme.py` 中新增用例 `test_toplevel_transparentcolor_follows_live_theme_switch` 里的未登记 `self.skipTest(...)`（Windows Tk 始终支持 `-transparentcolor`，直接调用 `top.attributes('-transparentcolor', COLORS['background_primary'])`，未改 `skip台账.json`）。
   - 未动任何既有测试断言。
2. **测试与三基线**：
   - `python -B -m unittest tests.architecture.test_skip_hygiene tests.architecture.test_static_hygiene`：全部通过（exit 0）。
   - `run_selftests.py -k theme style_engine`：3 个测试文件 / 65 条用例全过，0 跳过（exit 0）。
   - `smoke_test.py`：9/9 通过（exit 0）。
   - 覆盖率／模块规模／结构三基线未放宽、未弱化。
3. **欠账变化**：
   - 消除 R4630 新增的 1 处未登记 `skipTest`（`test_skip_hygiene` 归零通过），无新增欠账。
