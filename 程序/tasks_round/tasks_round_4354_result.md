# R4354 · FIX-REL11-QUALNAME-GUARD：外发清单守卫升级（文件, 符号限定名, 计数）强匹配
<!-- round-evidence: {"commit_base": "535419c0f", "credential_hits": 0, "evidence_sha256": "caa605c70bd80e68", "exit": 0, "failed": 0, "passed": 35, "round": 4354, "tests": "run_selftests.py -k app_logging diagnostic_capture http_boundary"} -->

## 开头三问

- （一）本轮类型：修复轮（AGENTS.md §3.2）。车道 `codex/rel-11`，基准 `535419c0`。队列卡 FIX-REL11-QUALNAME-GUARD（W2）。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k app_logging diagnostic_capture http_boundary` 35/35 绿（退出码 0）；`smoke_test.py --architecture` 706/706 绿（退出码 0）。默认冒烟与全量回归未跑（卡面未要求；全量以 `full-safe-receipts.json` 凭据为准）。
- （三）欠账少了吗：未新增欠账；消除了清单行号漂移反复补登的复发源（R4345 同类欠账的根因）。

## 缺陷与复现方式

`OutboundRegistryTests` 以 `(rel_path, 绝对行号)` 为断言键核对 `docs/process/外发内容清单.md`，跨分支无关增删行即造成误报：REL-11 已在 R4341/R4349 两次中招（`desktop_media_pages.py` 817→801、`desktop_account_page.py` 184→242）。当前树上清单仍登记 `ui/desktop_account_page.py:184`，而实际 `webbrowser.open` 出站点在 `AccountPageMixin._account_update_card` 内第 242 行（REL-10 合入后位置）。

复现：未改任何文件时跑 `run_selftests.py -k app_logging diagnostic_capture http_boundary` 即红 2 条，红因与卡面一致——清单登记的 `:184` 已不存在、实际的 `:242` 未登记。

## 改前红（原样输出）

改前定向命令退出码 1，`architecture.test_http_boundary` 6 条用例中 2 条红：

```
===== test_outbound_registry_covers_every_outbound_point (architecture.test_http_boundary.OutboundRegistryTests.test_outbound_registry_covers_every_outbound_point) =====
AssertionError: {'ui/desktop_account_page.py': [242]} != {}
- {'ui/desktop_account_page.py': [242]}
+ {} : 未登记的外发点（写入 docs/process/外发内容清单.md）：{'ui/desktop_account_page.py': [242]}

===== test_outbound_registry_has_no_stale_entries (architecture.test_http_boundary.OutboundRegistryTests.test_outbound_registry_has_no_stale_entries) =====
AssertionError: Lists differ: [('ui/desktop_account_page.py', 184)] != []
First list contains 1 additional elements.
- [('ui/desktop_account_page.py', 184)]
+ [] : 外发内容清单登记了已不存在的出站点：[('ui/desktop_account_page.py', 184)]
```

守卫改造就位、清单未同步时的中间态同样按预期红（covers 1 条：全部 77 个检出点未登记；stale 绿；新增单元用例绿），证明新守卫确实拦截未登记点而非恒真。

## 改动（文件:行号）

- `程序/tests/architecture/test_http_boundary.py:79`：新增锚点正则 `_SITE`（`相对路径.py::符号限定名`）。
- `程序/tests/architecture/test_http_boundary.py:108-128`：`_outbound_points`（行号集合）改为 `_outbound_sites(tree)`——检出条件逐字不变，按所属符号限定名归并，值升为升序行号列表（模块顶层记 `<module>`）。
- `程序/tests/architecture/test_http_boundary.py:131-138`：新增 `_detected_sites()`，全量生产文件的 `{(rel_path, qualname): 行号列表}`。
- `程序/tests/architecture/test_http_boundary.py:178-184`：新增 `_registry_sites()`，清单锚点按出现次数计条数。
- `程序/tests/architecture/test_http_boundary.py:191-206`：新增 `test_outbound_sites_resolve_enclosing_qualnames`，合成源码钉住 `<module>`/函数/类方法/同符号多点的解析与计数。
- `程序/tests/architecture/test_http_boundary.py:208-225`：`test_outbound_registry_covers_every_outbound_point`、`test_outbound_registry_has_no_stale_entries` 改按 (rel_path, qualname) 多重集计数核对——覆盖看检出缺额、陈旧看登记超出，双向合起来仍是逐点一一对应，守卫强度不弱化。`test_outbound_registry_lists_required_flows` 与 HttpBoundaryTests 全部用例逐字未动。
- `程序/docs/process/外发内容清单.md`：全部 77 个出站点条目改写为 `file.py::符号限定名` 锚点（括号内保留当前参考行号，不作断言键）；「更新检查」节 `domain/account_client.py` 与「账号服务」同一注入点改为文字引用、不再重复计锚点；`ui/desktop_account_page.py` 条目同步为 `AccountPageMixin._account_update_card`（L242）；首段说明同步锚点格式与多重集口径。出站点口径名单与各条「外发的字段」描述逐字不变。

## 改后命令输出尾部

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k app_logging diagnostic_capture http_boundary`（退出码 0）：

```
共 35 条用例，9.5 秒；0 个文件有红
最慢 3 路工作单元：
  architecture.test_http_boundary    8.7 秒 / 7 条
  test_diagnostic_capture       0.2 秒 / 9 条
  test_app_logging              0.1 秒 / 19 条
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
Ran 706 tests in 293.841s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证

- 默认冒烟 `smoke_test.py` 与全量回归 `run_selftests.py --all --safe` 未跑（卡面验收未列；全量以 `full-safe-receipts.json` 凭据为准）。
- 改前红输出尾部有 `[SUSPECT_CONCURRENCY]` 提示（红项发生时有其他 PID 持有 GUI 令牌），为环境提示而非断言红因；两条红均为清单行号断言，改后复跑全绿。
- 清单括号内行号为写稿时点的参考值，未来行漂移后可能失真但不影响断言（这正是本卡要消除的脆性）。

## 卡外发现（只记录，不修）

- 无。

## 回滚

`git revert` 本轮提交。
