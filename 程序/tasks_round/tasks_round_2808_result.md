# R2808 结果：修复 master 静态门禁阻断——ui_usage_detail 吞异常改走 app_logging.swallowed()
<!-- round-evidence: {"commit_base": "2ded4464", "credential_hits": 0, "evidence_sha256": "ab1c73aa76a9c431", "exit": 0, "failed": 0, "passed": 32, "round": 2808, "tests": "run_selftests.py -k silent_exception usage_indicator usage_snapshot usage_overview"} -->

1. 轮次类型：修复轮（合并阻断修复，根因单点）。
2. 测试：棘轮门禁 test_silent_exception_ratchet 4/4 绿；usage 定向 28 条全绿；默认冒烟 8/8。未跑全量。
3. 欠账：无新增；本修复解除 master 静态门禁阻断（R2779 合入的 ui_usage_detail.py:142 `except Exception: pass` 未登记，导致一切 merge_round 的 local_ci exit 静态门禁失败）。

## 根因与修复

- R2774（费用统计模块收口，R2779 合入）新增 `ui_usage_detail.py`，CSV 导出后刷新
  `desktop.status` 的兜底分支用了 `except Exception: pass`，未按棘轮要求改走
  `app_logging.swallowed()`（同模块姊妹文件 ui_usage_detail 配套的
  `ui_usage_indicator.py` 已是 swallowed() 口径）。
- 修复：`import app_logging`＋`except Exception: app_logging.swallowed()`，
  与 ui_usage_indicator.py / ui_theme.py 既有惯例一致；断言未动。
- 验证：test_silent_exception_ratchet 全绿（含 allowlist 无陈旧项、无裸 except）；
  test_usage_indicator_ui／test_usage_snapshot／test_usage_overview 28 条全绿；
  smoke_test.py 8/8。
