# R4229 结果：FIX-AUD-US03-AUTOTMP 修复生成资产自动导入失败残留 *_autoimport.png
<!-- round-evidence: {"commit_base": "e4f0c15c", "credential_hits": 0, "evidence_sha256": "ee544121d31128a3", "exit": 0, "failed": 0, "passed": 12, "round": 4229, "tests": "run_selftests.py -k asset_batch_retention asset_image_import"} -->

## 开头三问

- 本轮属于 §3.2 修复轮：只修 `register_image` 抛错后 `*_autoimport.png` 未清理导致 `pending_generated_files` 重复扫描的缺陷。
- 测试跑了吗、三个基线：卡面定向命令改前 12 条中 1 条红（新复现用例），改后 12/12 全绿；`smoke_test.py --architecture` 700/700 全绿、退出码 0。默认冒烟与全量 `--all --safe` 未运行（卡面未要求；全量凭据不由本车道更新）。
- 欠账少了吗：无新增欠账；历史欠账未在本卡范围核验。

## L0→L5 盘点结论

- L0 临时文件命名/生命周期与 pending 识别契约：`import_pending_generated` 把转换后 PNG 先写到与源图同目录的 `<aid>_autoimport.png`（`程序/domain/asset_generated_import_service.py:90`）；`pending_generated_files` 只扫 `generated_dir(base)` 与 `project/workflows/Comfy资产批次`（含 `seedream`）下的 `*.png`，用 `(CHAR|LOC|PROP)_\d{3,}` 反解 aid，且要求 aid 在计划内、`image_ready` 为假（同文件 `:51-72`；`generated_dir` 见 `程序/domain/asset_context.py:21-25`）。因此残留的 `CHAR_001_autoimport.png` 会再次命中同一 aid。
- L1 落盘、`register_image` 异常与清理边界：成功路径在 `register_image` 返回后 `remove_temporary_file(tmp)`（`asset_generated_import_service.py:92-97`）；改前 `except` 只 `report` 不清理（改前 `:98-100`），缺陷成立。`register_image` 本体先 `publish_bytes(dest)` 再 `publish_json(registry)`（`程序/domain/asset_batch_service.py:86-93`），本卡不改其事务语义。
- L2 导入失败是否留下可被发现资产：生成导入临时文件不进入资产登记表；`register_image` 失败时 `assets.json` 不会新增 `image` 指针，`image_ready` 仍为假，原图会继续作为 pending 被扫到。该语义保持不变。
- L3 生成资产轮询与重试编排：L3 `import_pending_generated_assets` 注入 `asset_batch_gateway()` 与 `project_context`（`程序/orchestrator/stage_asset_gateways.py:119-124`）；L4 在项目加载与资产页打开时调用（`程序/ui/desktop_asset_pages.py:134-149,282-287`）。本卡不在轮询/UI 层绕过清理。
- L4 UI/状态提示：单项失败经 `report` 回调上报「自动导入未完成 …」，不中断整轮；外层 UI 只兜启动/页面级异常（`desktop_asset_pages.py:140-149,286-287`）。失败原因未被吞掉，残留文件才是缺陷。
- L5 测试、结果文件与端到端验收：新增用例放在允许文件 `程序/tests/test_asset_batch_retention.py:117-141`；验收命令与结果见下。

## 缺陷复现方式

新增 `test_failed_register_image_removes_autoimport_temp`：临时目录内建 `assets/资产清单/assets.json` 计划与 `生成资产/CHAR_001_seedream_fail.png` 真 PNG；用 `patch.object(asset_batch_service, 'register_image', side_effect=OSError('登记失败'))` 让登记在临时文件已发布后抛错；调用 `import_pending_generated(..., gateway={'publish_bytes': save_bytes})`。断言：返回 `[]`、`CHAR_001_autoimport.png` 不存在、报告含「自动导入未完成」、`pending_generated_files` 只剩原图。

改前定向命令输出尾部原文：

```text
  test_asset_batch_retention     6 条     0.4 秒  ✗ 1
  test_asset_image_import_service     5 条     1.1 秒

共 12 条用例，2.0 秒；1 个文件有红
===== test_failed_register_image_removes_autoimport_temp (test_asset_batch_retention.AssetBatchRetentionTests.test_failed_register_image_removes_autoimport_temp) =====
Traceback (most recent call last):
  File "程序\tests\test_asset_batch_retention.py", line 137, in test_failed_register_image_removes_autoimport_temp
    self.assertFalse((source.parent / 'CHAR_001_autoimport.png').exists())
AssertionError: True is not false
```

红的原因与卡面一致：`register_image` 抛错后 except 分支未删除 `CHAR_001_autoimport.png`。

## 改了什么

- `程序/domain/asset_generated_import_service.py:90`：把 `tmp = folder / (aid + '_autoimport.png')` 移到 `try` 前，保证 except 分支总能拿到同一临时路径；`:99` 在 except 分支先 `remove_temporary_file(tmp)` 再 `report`。成功路径、返回值、报告文案与异常吞并范围均不变。
- `程序/tests/test_asset_batch_retention.py:117-141`：新增上述复现/回归用例。
- `程序/tasks_round/tasks_round_4229_result.md`：本文件。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k asset_batch_retention asset_image_import`（改前） | 1 | 12 条用例，1 个文件有红；红因如上 |
| 同上（改后） | 0 | 12 条用例，0 个文件有红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 700 tests，OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次 4229 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4229: FIX-AUD-US03-AUTOTMP 修复" … --tests asset_batch_retention asset_image_import` | 见完成报告 | 提交哈希与证据见 `tasks_round/evidence/R4229.json` 及完成报告 |

改后定向命令输出尾部原文：

```text
  architecture.test_asset_image_import_boundary     1 条     0.2 秒
  test_asset_batch_retention     6 条     0.3 秒
  test_asset_image_import_service     5 条     1.8 秒

共 12 条用例，2.9 秒；0 个文件有红
最慢 3 路工作单元：
  test_asset_image_import_service    1.8 秒 / 5 条
  test_asset_batch_retention    0.3 秒 / 6 条
  architecture.test_asset_image_import_boundary    0.2 秒 / 1 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：（共同 Git 目录 selftest-incremental.json）
最近 5 轮自检中位基线：2.9 秒

ALL TESTS PASSED
```

架构门禁输出尾部原文：

```text
----------------------------------------------------------------------
Ran 700 tests in 254.075s

OK
✅ 架构治理测试：tests/architecture
```

## 没验证的地方

- 未跑默认 `smoke_test.py` 与全量 `run_selftests.py --all --safe`：卡面只要求定向命令与 `--architecture`。
- 未做真实 Comfy/Seedream 出图与真实 `register_image` 落库的端到端验证；复现用例用真 PNG 与打桩登记失败覆盖缺陷路径。
- `git diff --numstat` 未运行（卡面注明由验收角色复跑）；提交前 `git status --porcelain` 结果见完成报告。

## 卡外发现（只记录，不顺手修）

- `register_image` 在 `publish_bytes(dest)` 与 `publish_json(registry)` 之间没有跨文件事务；若 `publish_json` 失败，可能留下未被 `assets.json` 引用的唯一名 PNG（`程序/domain/asset_batch_service.py:86-93`）。本卡只清理 `*_autoimport.png` 临时文件，未扩大范围。

## 被拒绝的命令

无。
