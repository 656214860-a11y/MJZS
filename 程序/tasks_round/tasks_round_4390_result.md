# tasks_round_4390_result — FIX-AST-V2-EC3-GUARD：asset_detail.py:793 通知改经 error_codes.user_text
<!-- round-evidence: {"commit_base": "a30b9f3b7", "credential_hits": 0, "evidence_sha256": "32535b632206cfbd", "exit": 0, "failed": 0, "passed": 97, "round": 4390, "tests": "run_selftests.py -k notification_boundary asset_detail asset_versions"} -->

- 轮次类型：§3.2 修复轮（先定位根因，只改根因所在模块）。
- 测试跑了吗、三个基线过了吗：跑了，先红后绿。改前 `run_selftests.py -k notification_boundary asset_detail asset_versions` 97 条用例 2 个文件红、退出码 1；改后同命令 97 条全绿、退出码 0；`smoke_test.py --architecture` 708 条全绿、退出码 0。默认冒烟基线本轮未跑（验收命令不含）；全量回归分支不累计、未跑 `--all --safe`（卡面禁止）。
- 欠账少了吗：EC-3 守卫 `test_notification_calls_never_render_the_bound_exception` 在 codex/ast-version-2 车道上的唯一命中点收口，AST-VERSION-2 合入出口 CI 的 1/708 失败消除；无新增欠账。

## 缺陷复现方式

卡面缺陷：`程序/ui/asset_detail.py` `restore_to_version` 的 `except (ValueError, TypeError) as exc:` 分支把 `str(exc)` 直接送进 `notify(...)`（改前第 793 行），命中 EC-3（R4360）新增的通知守卫：提示调用的文字参数不得直接渲染所在 except 绑定的异常变量，必须经 `contract.error_codes.user_text(exc)`。

复现（两处同源红）：

1. 新增 `tests/test_asset_detail.py::OperationCompletionTests.test_restore_failure_notice_goes_through_user_text`：`SimpleNamespace` 假 desktop（不建真 Desktop/Tk）、`records` 参数传入绕过 `list_versions`、`ask_confirmation` 打桩放行、`domain.asset_versions.restore_version` 打桩抛 `ValueError('plain english failure without any chinese')`，捕获 `notify` 文本，断言等于 `error_codes.user_text(failure)` 且不等于 `str(failure)`。
2. 既有守卫 `architecture.test_notification_boundary.NotificationBoundaryTests.test_notification_calls_never_render_the_bound_exception` 用 AST 扫描直接命中 `ui/asset_detail.py:793`。

## 改前红的条数和原因（原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k notification_boundary asset_detail asset_versions`：共 97 条用例，44.9 秒；**2 个文件有红**，退出码 1。

```
### architecture.test_notification_boundary（1 条红）

===== test_notification_calls_never_render_the_bound_exception =====
AssertionError: Lists differ: ['ui/asset_detail.py:793 通知调用直接渲染异常变量 exc'] != []
First list contains 1 additional elements.
'ui/asset_detail.py:793 通知调用直接渲染异常变量 exc'

### test_asset_detail（1 条红）

===== test_restore_failure_notice_goes_through_user_text =====
  File "…\tests\test_asset_detail.py", line 437, in test_restore_failure_notice_goes_through_user_text
    self.assertNotEqual(text, str(failure))
AssertionError: 'plain english failure without any chinese' == 'plain english failure without any chinese'
```

两条红同源：notify 文本是异常原文 `str(exc)`，未经 `error_codes.user_text()` 统一出口。

## 改了哪几处（文件:行号为改后）

- `程序/ui/asset_detail.py:28` 新增 `from contract import error_codes`（与 `ui/asset_reference_import.py:7` 同惯例，置于 `from agent.core import read` 与 `from contract.platform_tools import open_path` 之间）。
- `程序/ui/asset_detail.py:794`（改前行号 793）`notify(desktop.win, str(exc), level='error', title='无法退回', status=desktop.status, modal=False)` → `notify(desktop.win, error_codes.user_text(exc), level='error', title='无法退回', status=desktop.status, modal=False)`；级别、标题、去处逐字不动，接住的异常类型不变。
- `程序/tests/test_asset_detail.py:417-438` `OperationCompletionTests` 新增 `test_restore_failure_notice_goes_through_user_text`（无真 Desktop/Tk，只用 `SimpleNamespace` 与桩）。
- 产品文件总行数 994 ≤ 1000 上限；`tests/architecture/test_notification_boundary.py` 未动，无测试弱化、删除或跳过。

## 改后命令输出尾部（原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k notification_boundary asset_detail asset_versions`：退出码 0

```
共 97 条用例，44.3 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0

```
Ran 708 tests in 251.968s

OK
✅ 架构治理测试：tests/architecture
```

## 三个基线数

- 默认冒烟基线：本轮未跑（验收命令不含默认冒烟）。
- 架构门禁：当轮 708 条、失败集合 ∅；改前同命令同树实测 1 红（`ui/asset_detail.py:793`，即本卡修复点）。
- 全量回归：分支不累计，未跑 `--all --safe`（卡面禁止）。

## 没有验证的地方

- 真实 `restore_version` 失败多为中文 `ValueError`（锁定、缺版、旧图缺失、网关缺失），`user_text` 按 R3 规则原样返回中文消息，与改前 `str(exc)` 显示一致；仅对非中文原文（英文 TypeError、含本机路径的系统错误）才改显 `[E-UNKNOWN] …` 兜底文案——这正是 EC-3 契约意图，非行为退化。该分支由桩用例与守卫静态扫描覆盖，未用真实失败逐类复验。
- 真机界面「退回此版」确认窗→失败提示路径未人工复验（新用例在桩层覆盖到 notify 文本参数）。
- 默认冒烟、全量自测未跑（卡面验收未列/明确禁止）。

## 卡外发现的问题（只记录）

- 无新增：`test_notification_boundary` 在本车道的唯一命中即本卡修复点；守卫允许名单 `UI_MESSAGEBOX_IMPORT_ALLOWED` 含 `asset_detail.py` 属既有登记，本轮未触碰 messagebox 使用面。

## 被拒绝的命令原文

```
Test-Path 'D:\漫剧制作助手\运行环境\Python\python.exe'            （探测主工作区解释器存在性，被拒；卡面命令本身原样可跑，未再探测）
Get-ChildItem '…\tasks_round\tasks_round_43*_result.md' …       （列结果文件探测格式，被拒；改用 find_file_by_name 工具）
```

## 提交

- 提交方式：`scripts\dev.py commit -m "R4390: FIX-AST-V2-EC3-GUARD 修复" ui/asset_detail.py tests/test_asset_detail.py tasks_round/tasks_round_4390_result.md --tests notification_boundary asset_detail asset_versions`
- 提交哈希：见完成报告（提交后回填）。
