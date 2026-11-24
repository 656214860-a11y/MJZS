# R4345 · FIX-REL11-REBASE：外发内容清单行号同步（desktop_media_pages.py:817→801）
<!-- round-evidence: {"commit_base": "e3eb4aab2", "credential_hits": 0, "evidence_sha256": "850fb782b9e57794", "exit": 0, "failed": 0, "passed": 34, "round": 4345, "tests": "run_selftests.py -k app_logging diagnostic_capture http_boundary"} -->

## 开头三问

- （一）本轮类型：修复轮（AGENTS.md §3.2）。车道 `codex/rel-11`，基准 `e3eb4aab`。队列卡 FIX-REL11-REBASE（W2）。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k app_logging diagnostic_capture http_boundary` 34/34 绿（退出码 0）；`smoke_test.py --architecture` 705/705 绿（退出码 0）。默认冒烟与全量回归未跑（卡面未要求；全量以 `full-safe-receipts.json` 凭据为准）。
- （三）欠账少了吗：未新增欠账。

## 缺陷与复现方式

`codex/rel-11` 变基至最新 master（82e396a27）后，R4327/R4329 的改动使 `ui/desktop_media_pages.py` 中 ElevenLabs 站点的 `open_target` 出站点从 817 行移到 801 行，而 `docs/process/外发内容清单.md` 仍登记 `:817`。`tests/architecture/test_http_boundary.py` 的 `OutboundRegistryTests` 要求清单行号与代码实际出站点一一对应，REL-11（R4331）合入出口 CI 因此实测失败。

复现：`run_selftests.py -k app_logging diagnostic_capture http_boundary` 在未改清单时即红 2 条，红因与卡面一致——清单登记了不存在的 `:817`、实际的 `:801` 未登记。实测核对该出站点现位于 `ui/desktop_media_pages.py:801`。

## 改前红（原样输出）

改前定向命令退出码 1，`architecture.test_http_boundary` 6 条用例中 2 条红：

```
===== test_outbound_registry_covers_every_outbound_point (architecture.test_http_boundary.OutboundRegistryTests.test_outbound_registry_covers_every_outbound_point) =====
AssertionError: {'ui/desktop_media_pages.py': [801]} != {}
- {'ui/desktop_media_pages.py': [801]}
+ {} : 未登记的外发点（写入 docs/process/外发内容清单.md）：{'ui/desktop_media_pages.py': [801]}

===== test_outbound_registry_has_no_stale_entries (architecture.test_http_boundary.OutboundRegistryTests.test_outbound_registry_has_no_stale_entries) =====
AssertionError: Lists differ: [('ui/desktop_media_pages.py', 817)] != []
First list contains 1 additional elements.
- [('ui/desktop_media_pages.py', 817)]
+ [] : 外发内容清单登记了已不存在的出站点：[('ui/desktop_media_pages.py', 817)]
```

## 改动（文件:行号）

- `程序/docs/process/外发内容清单.md:140`：表格行 `ui/desktop_media_pages.py:817` 改为 `ui/desktop_media_pages.py:801`，描述列（`open_target`：ElevenLabs 站点）逐字不变。未动测试、未动产品代码、未动其它清单条目。

## 改后命令输出尾部

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k app_logging diagnostic_capture http_boundary`（退出码 0）：

```
共 34 条用例，9.1 秒；0 个文件有红
最慢 3 路工作单元：
  architecture.test_http_boundary    8.3 秒 / 6 条
  test_app_logging              0.2 秒 / 19 条
  test_diagnostic_capture       0.2 秒 / 9 条
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
Ran 705 tests in 284.738s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证

- 默认冒烟 `smoke_test.py` 与全量回归 `run_selftests.py --all --safe` 未跑（卡面验收未列；全量以 `full-safe-receipts.json` 凭据为准）。
- 改前红输出尾部有 `[SUSPECT_CONCURRENCY]` 提示（红项发生时有其他 PID 持有 GUI 令牌），为环境提示而非断言红因；两条红均为清单行号断言，改后复跑全绿。

## 卡外发现（只记录，不修）

- 无。

## 回滚

`git revert` 本轮提交。
