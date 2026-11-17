# R3049 结果（测试契约轮：test_tooltip 补齐 R2997/R3033 后的契约漂移）
<!-- round-evidence: {"commit_base": "c5e2233f", "credential_hits": 0, "evidence_sha256": "d2cf302c10de258a", "exit": 0, "failed": 0, "passed": 6, "round": 3049, "tests": "run_selftests.py -k tooltip"} -->

## 三问
1. 轮次类型：测试契约同步（§2.4）——行为契约已由 R2997（Button-1/pin）与 R3033（hide 调 winfo_exists）确立，本文件断言未跟上。
2. 测试：`python -m unittest tests.test_tooltip` 4/4 绿（改前 master 上 1 失败＋1 错误）。
3. 债务：后台全量 auto_full_safe 在 master（222326c）报 test_tooltip 红，本轮消除其一。

## 改动
- `tests/test_tooltip.py`：`_Tip` 假件补 `winfo_exists()`（hide() 现会调用）；绑定断言补 `<Button-1>`（pin_on_click 的按下绑定，R2997 起即存在）。断言只增不减，语义与 ui/ui_tooltip.py 现行契约一致。

## 证据
- master（c5e2233f）复跑：改前 `FAILED (failures=1, errors=1)`；改后 `OK (4 tests)`。
- auto_full_safe.log 同批另有 test_soak_light（耗时超限，机器负载型）、test_multi_monitor_popups／test_ui_edges_tables（yview 断言）红，均不在本轮范围，留 nightly 审查车道跟进。
