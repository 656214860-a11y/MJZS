# tasks_round_4335_result — EC-3 其余显示异常原文的调用点改用统一出口，并立守卫
<!-- round-evidence: {"commit_base": "930a05fc4", "credential_hits": 0, "evidence_sha256": "3646c9ddc037c558", "exit": 0, "failed": 0, "passed": 28, "round": 4335, "tests": "run_selftests.py -k notification_boundary ui_error_text desktop_async_tasks"} -->

- 轮次类型：§3.2 修复轮（按任务书 §4.3 + §4.0 落范围）。
- 测试跑了吗：守卫改前先红后绿；`-k notification_boundary`、`-k ui_error_text desktop_async_tasks`、`smoke_test.py --architecture` 三条验收命令均退出码 0。冒烟基线本轮未跑（验收命令不含默认冒烟）；架构门禁 704/704 全绿；全量回归欠账以凭据为准、本轮未新增。
- 欠账少了吗：守卫上线后 `ui/`、`desktop.py`、`app.py`、`agent/prompt_optimizer.py` 的通知调用不得再直接渲染 `except` 绑定的异常变量；本卡清单 32 处 + `desktop_async_tasks.py` 入队转换点全部收口。

## 缺陷与复现方式

界面多处失败提示直接把 `str(e)`/`'%s' % e` 送进 `notify`/`notifier.error`，系统异常原文（含本机路径）原样显示给用户；`desktop_async_tasks.py` 在入队前就把异常转成 `str(e)`，显示处拿不到异常对象，带中文路径的系统报错仍会漏出。

复现：新守卫 `test_notification_calls_never_render_the_bound_exception`（AST 扫描，见 `tests/architecture/test_notification_boundary.py`）。

## 改前红

`run_selftests.py -k notification_boundary`：8 条用例 1 红，失败原因即本卡缺陷——`test_notification_calls_never_render_the_bound_exception` 断言违规清单为空，实际抓出 **32 处**，逐条列出（`First list contains 32 additional elements`）：

```
agent/prompt_optimizer.py:206、224；app.py:622、682、1370；
ui/asset_reference_import.py:87、113；ui/background_characters.py:167；
ui/cloud_assets_dialog.py:29；ui/cloud_video.py:184、239；
ui/local_previs.py:73、226、276、297、337、345；
ui/qwen_setup_dialog.py:51、62；ui/reference_wall.py:202、209；
ui/seedream_settings.py:75；ui/skill_panel.py:727、859；
ui/skill_panel_workflow.py:97、122；ui/storyboard_files.py:416；
ui/tts_settings.py:80；ui/ui_usage_detail.py:136；
ui/white_model.py:48、171；ui/workflow_settings_dialog.py:107
```

（行号为改前基准；其中 skill_panel:859、skill_panel_workflow:122 为 `'%s' % exc` 形，其余为 `str(异常变量)` 形。任务书 §4.3 列 27/28 处 + 新增 4 处，守卫实抓 32 处全在允许文件内。）

## 改动清单（文件:行号为改后）

### 守卫与测试

- `tests/architecture/test_notification_boundary.py`：新增 `test_notification_calls_never_render_the_bound_exception`（扫描 `ui/` 全部模块、`desktop.py`、`app.py`、`agent/prompt_optimizer.py`；`notify(...)` 与 `*.notifier.error/warning(...)` 的文字参数中出现 `except` 绑定的异常变量即违规，允许名单为空）+ 金丝雀 `test_exception_text_guard_canary`（对源码字符串求值：违规写法 9 例抓 5 例、`user_text` 包装与非 except 变量不误报）；新增模块级辅助 `_notification_scan_files`、`_is_notification_call`、`_is_user_text_call`、`_renders_exception`、`_exception_text_leaks`。
- `tests/test_ui_error_text.py`：新增 `BackgroundPathFailureTests.test_failure_with_local_path_never_shows_the_path`——`AsyncTasksMixin.async_` 跑挂 `FileNotFoundError('D:\\项目库\\私有\\secret.txt')`，入队文字与 `_async_failed` 显示文字都不含路径、以 `[E-` 开头；诊断记录仍收到原始异常对象。
- `tests/test_desktop_async_tasks.py:40`：入队文字断言由 `'task failed'` 同步为 `error_codes.describe('E-UNKNOWN')`（转换点收口后的新契约），并加 `from contract import error_codes`。

### 产品调用点（str(e)/'%s' % e → error_codes.user_text(e)，前后拼接文字不动）

| 文件 | 调用点 |
| --- | --- |
| `agent/prompt_optimizer.py` | 206、224（`import contract.error_codes as error_codes` 行内引入，见下） |
| `app.py` | 623、683、1371；顶部 `import contract.error_codes as error_codes`（与第 9 行 `import contract.pet_bus as pet_bus` 同形） |
| `ui/asset_reference_import.py` | 88、114；顶部 `from contract import error_codes` |
| `ui/background_characters.py` | 168；同上 |
| `ui/cloud_assets_dialog.py` | 29（函数内引入风格 → except 行内 import） |
| `ui/cloud_video.py` | 184、239（except 行内 import） |
| `ui/desktop_async_tasks.py` | 23（`str(e)`→`error_codes.user_text(e)`）；顶部 `import contract.error_codes as error_codes` |
| `ui/local_previs.py` | 74、227、277、298、338、346；顶部 `from contract import error_codes` |
| `ui/qwen_setup_dialog.py` | 51、62（except 行内 import） |
| `ui/reference_wall.py` | 203、210；顶部 `from contract import error_codes` |
| `ui/seedream_settings.py` | 75（except 行内 import） |
| `ui/skill_panel.py` | 728、860（`'%s' % error_codes.user_text(exc)`）；顶部 `from contract import error_codes` |
| `ui/skill_panel_workflow.py` | 98、123（`'%s' % error_codes.user_text(exc)`）；顶部 `from contract import error_codes` |
| `ui/storyboard_files.py` | 417；顶部 `from contract import error_codes` |
| `ui/tts_settings.py` | 81（except 内加 `import contract.error_codes as error_codes` 行） |
| `ui/ui_usage_detail.py` | 137；顶部 `from contract import error_codes` |
| `ui/white_model.py` | 49（except 内 import 行）、172（except 行内 import） |
| `ui/workflow_settings_dialog.py` | 108；顶部 `from contract import error_codes` |

### 引入写法说明（外部地址登记行号约束）

`tests/architecture/test_http_boundary.py::test_hardcoded_addresses_are_registered` 按 `(文件, 行号)` 登记外部地址。首轮用顶层 import 使 7 个含登记 URL 的文件行号整体 +1，9 个登记失配变红。改法：这 7 个文件（`prompt_optimizer`、`cloud_assets_dialog`、`cloud_video`、`qwen_setup_dialog`、`seedream_settings`、`tts_settings`、`white_model`）撤掉顶层 import、改用 EC-2 同款 `import contract.error_codes as error_codes` 行内引入（`except X as e:import …;notify(…)` 或多行 except 内首行），不产生行号位移。`tts_settings.py` 多行 except 内加 1 行 import，同文件 `row=ttk.Frame(body);row.grid(…)` 两行并为分号一行抵消，登记行号全部恢复（http_boundary 3/3 绿）。其余文件无登记地址，按卡面示例用顶层 `from contract import error_codes`（`app.py`/`desktop_async_tasks.py` 用 `import contract.error_codes as error_codes`，与各自文件既有 `import contract.X` 风格一致）。

### 消费方核验

`desktop_async_tasks.py` 转换点下游：`finish(error=…)` → 历史/运行状况显示、`_async_failed` → `notifier.error`，均无对原文分支判断的调用方；唯一依赖原文的是测试断言，已同步。

## 改后命令输出尾部

```
$ ..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k notification_boundary
共 8 条用例，5.1 秒；0 个文件有红 … ALL TESTS PASSED   （退出码 0）

$ ..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_error_text desktop_async_tasks
共 20 条用例，1.5 秒；0 个文件有红 … ALL TESTS PASSED   （退出码 0）

$ ..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture
Ran 704 tests in 339.274s  →  OK  ✅ 架构治理测试：tests/architecture   （退出码 0）
```

另加跑 `-k notification_boundary ui_error_text desktop_async_tasks http_boundary`：31 条全绿（含 http_boundary 回归确认）。

## 没验证的地方

- 未跑默认冒烟（验收命令不含）；未跑全量自测（卡面禁止）。
- 改后调用点的提示级别、标题、去处未动（L4-U10a 范围）。
- `desktop_async_tasks` 失败路径下 `diagnostic_capture.record_degradation` 仍收原始异常对象（测试已断言 `recorded == [error]`）。

## 卡外发现（只记录，不顺手修）

- `ui/workflow_settings_dialog.py:101` `feedback.set(str(exc))`、`ui/qwen_setup_dialog.py:65` `status.set(str(exc))`、`ui/local_previs.py:312` `self.state['summary']='强制停止未完成：'+str(exc)`、`ui/storyboard_files.py` 目录扫描 `(False,str(exc))` 入队值——同属「界面可见文字含异常原文」，但走的是 status/状态变量而非 notify 通道，不在本卡守卫口径与范围清单内。
- `app.py:1465` `self.notifier.error(str(value))`：`value` 是 `done(value)` 交回的结果文字（非 except 绑定变量），守卫不误报、行为不变。

## 被拒绝的命令

- `Set-Location`（切到程序目录）一次——改用 `workdir` 参数执行，卡面命令均按原样在 `程序` 目录跑通。
- `git log -1 --format=%h`、`git rev-parse --abbrev-ref HEAD`（bash 一次性会话）一次——经 PowerShell 会话执行成功，HEAD=930a05fc、分支 codex/ec-call-sites 已核实。
- 首次 `-k notification_boundary`（bash 一次性会话，中文路径乱码 exit 127）——PowerShell 会话跑通；守卫 8 条用例 1 红即改前缺陷。
