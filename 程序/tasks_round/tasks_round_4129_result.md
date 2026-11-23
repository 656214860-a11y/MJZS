# R4129 结果：FIX-P1 四处直写项目设置改走统一入口
<!-- round-evidence: {"commit_base": "d8d10a5b", "credential_hits": 0, "evidence_sha256": "19b19ba2fbca7785", "exit": 0, "failed": 0, "passed": 39, "round": 4129, "tests": "run_selftests.py -k keyframe_comfy storyboard_recycle_service native_assets storyboard_source_selector project_settings"} -->

## 开头三问

（一）本轮类型：缺陷修复轮。任务卡 W6B-FIX-P1，车道 codex/fix-p1-save-prefs，基准 d8d10a5b0070af6fb5f4720d77748768c3cb5460；来源是用户报的「老项目打不开」（需求任务书 R21、R22）——项目库目录被改名后，四处绕过统一入口的 `ui_settings.json` 直写会把旧路径重新建成空壳。

（二）测试跑了吗、三个基线：改后定向 `-k keyframe_comfy storyboard_recycle_service native_assets storyboard_source_selector project_settings` 共 39 条用例全绿、退出码 0；验收定向 `-k keyframe_comfy recycle native_run native_assets asset_gating aspect_ratio_priority seedream_direct project_settings ui_edges_controls storyboard_source` 共 178 条用例全绿、退出码 0（基准 168 条＋本轮新增 10 条）；静态检查 `-k copy_rules static_names` 共 26 条用例全绿、退出码 0；架构门禁 `smoke_test.py --architecture` 共 700 条用例全绿、失败集合为空、退出码 0（343.5 秒）。默认冒烟没单独跑；全量自测没跑。新增 10 条用例（四组功能各 2 条＋扫描器自检＋全量源码扫描），未修改或删除任何现有用例。

（三）欠账少了吗：四处绕开统一入口 `save` 直写 `ui_settings.json` 的写法全部改走 `infra.project_settings.save_prefs`，项目目录不在时不再重建空壳、统一抛带中文说明的 `ConfigError`；源码扫描用例改前恰好列出这四处，改后为空。无新增欠账。

## 改了哪些文件

- `orchestrator/storyboard_recycle_service.py`（+3/-2）：`recycle_files` 函数内加 `from infra.project_settings import save_prefs`；`save(prefs_file, prefs)` → `save_prefs(project, prefs)`；`save` 在该函数不再使用，`from agent.core import read, save` 改为 `from agent.core import read`（`detach_video_refs` 自己的导入未动）。
- `ui/keyframe_comfy.py`（+2/-1）：文件头在 `import infra.app_logging as app_logging` 下加 `import infra.project_settings as project_settings`；方法内 `save(self.prefs_file, data)` → `project_settings.save_prefs(self.project, data)`（方法同名，按卡面带模块名调用）。
- `ui/storyboard_source_selector.py`（+2/-2）：`from agent.core import save` 在本文件不再使用，换成 `from infra.project_settings import save_prefs`；`save(Path(app.root)/'ui_settings.json',data)` → `save_prefs(app.root,data)`。
- `ui/native_assets.py`（+2/-1）：文件头在 `from infra.file_cache import remove_temporary_file` 下加 `from infra.project_settings import save_prefs`；行尾 `save(self.prefsfile,prefs)` → `save_prefs(self.project,prefs)`，前半句不动。
- `tests/test_keyframe_comfy.py`（+31/-0）：文件头加一行 `import types`；文件末尾、`if __name__` 之前追加 `SavePrefsEntryTests`（2 条），现有行未删未改。
- `tests/test_native_assets.py`（新建）：`SelectedSavePrefsTests`，`SimpleNamespace` 替身 controls 直调 `_AssetControls.selected`（2 条）。
- `tests/test_project_settings.py`（新建）：`direct_writes` AST 扫描器自检＋全量产品代码扫描，`RETAINED` 保留清单带非空断言（2 条）。
- `tests/test_storyboard_recycle_service.py`（新建）：`RecycleSavePrefsTests`，打桩 `linked_path` 模拟「读完设置后项目被改名」（2 条）。
- `tests/test_storyboard_source_selector.py`（新建）：`FakeCombo`／替身 app 走 `source_selector` 真实 choose→safe→apply 链路（2 条）。
- `tasks_round/tasks_round_4129_result.md`（新建）：本文件。

`git -c core.quotepath=false diff --numstat` 原文（新建文件未入库前不计入）：

```
3	2	程序/orchestrator/storyboard_recycle_service.py
31	0	程序/tests/test_keyframe_comfy.py
2	1	程序/ui/keyframe_comfy.py
2	1	程序/ui/native_assets.py
2	2	程序/ui/storyboard_source_selector.py
```

四个产品文件增删各不超过 4；`tests/test_keyframe_comfy.py` 删除数为 0，符合卡面要求。

## 四处各自的处理

1. `orchestrator/storyboard_recycle_service.py` `recycle_files`
   - 改前 `save(prefs_file, prefs)`，改后 `save_prefs(project, prefs)`。
   - 用例：`RecycleSavePrefsTests`——目录在时 `final_storyboard_json` 清空、`other` 保留；目录不在时抛 `ValueError`（消息含「项目目录不存在或已被移动」）、原路径未重建、被挪走目录里的 MARK 仍在。
   - 错误接住：`storyboard_page_controller.py:115` `recycle()` 直调；界面入口（`ui/storyboard_files.py:673/702/757` 的删除动作经 `self.desktop.safe` 包装）→ `desktop.py:557` `safe` 接住 `Exception` → `diagnostic_capture.record_degradation` 记录、`notifier.error(error_codes.user_text(e))` 弹错误提示。用户看到带「项目目录不存在或已被移动」说明的错误提示，文件已移入回收站但偏好未写回。
2. `ui/keyframe_comfy.py` `_KeyframeComfyWindow.save_prefs`
   - 改前 `save(self.prefs_file, data)`，改后 `project_settings.save_prefs(self.project, data)`。
   - 用例：`SavePrefsEntryTests`（替身 window 直调，不建窗口）——目录在时 `frame_production.aspect_ratio` 写入且 `other` 保留；目录不在时三条统一断言。
   - 错误接住：两个调用点。`keyframe_comfy.py:468` `shape.bind('<<ComboboxSelected>>')` 的回调未经 `safe` → 异常进 Tk `report_callback_exception` → `app_logging.install` 的 `tk_hook` 转 `desktop_launcher.py:43` 的处理：`diagnostic_capture.record_crash` 记崩溃、`after_idle` 弹「发生未处理错误，详情已写入 启动错误.log。」通知。`keyframe_comfy.py:803` `start()` 里的调用经 `app.safe`（`:477`）→ 同上 `desktop.py:557` 记降级 + 错误弹窗。用户分别看到「发生未处理错误」通知或带消息文案的错误提示；比例偏好不保存，不重建目录。
3. `ui/storyboard_source_selector.py` `apply`
   - 改前 `save(Path(app.root)/'ui_settings.json',data)`，改后 `save_prefs(app.root,data)`。
   - 用例：`SourceSelectorSavePrefsTests`——目录在时 `asset_scope='current'`、`other` 保留、`focus` 被调一次、`shown==[4]`；目录不在时 `errors` 恰好一条 `ValueError`、`focus` 未调、`shown` 为空、目录未重建。
   - 错误接住：`choose()` 在 `storyboard_source_selector.py:79` 用 `app.safe(apply)` 调用 → `desktop.py:557` 记录降级并 `notifier.error` 弹提示；`after_idle(resync)` 随后把下拉框显示拉回真实文件。用户看到错误提示，下拉框不切换、页面不重建。
4. `ui/native_assets.py` `_AssetControls.selected`
   - 改前行尾 `save(self.prefsfile,prefs)`，改后 `save_prefs(self.project,prefs)`。
   - 用例：`SelectedSavePrefsTests`——目录在时 `asset_workflow` 写入 `{model, aspect_ratio, quality:'medium', seed:42}` 且 `other` 保留；目录不在时三条统一断言。
   - 错误接住：唯一调用点是 `native_assets.py:383` `selector`/`shape` 两个 `<<ComboboxSelected>>` 直绑回调，未经 `safe` → `report_callback_exception` → `tk_hook`/`desktop_launcher.py:43`：记崩溃 + 弹「发生未处理错误」通知。用户看到「发生未处理错误」通知，偏好不保存。

源码扫描用例改前列出的位置（恰好四处）：`orchestrator/storyboard_recycle_service.py:103`、`ui/keyframe_comfy.py:572`、`ui/native_assets.py:415`、`ui/storyboard_source_selector.py:63`。`RETAINED` 保留清单只有一条：`scripts/acceptance_stage_op_walkthrough.py`（第 87 行）——验收走查脚本向它自建的临时项目写设置夹具，不随应用运行，未改动；清单带「每条仍能扫出至少一处」的反向断言，不留过期条目。改后扫描结果为全空。

## 命令与结果

所有命令均在工作树 `程序` 子目录（git 命令在工作树根）直接运行成功，无权限拒绝、无 GUI_DEFERRED。

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain` | 0 | 无输出（改动前空；改动后为 4 产品文件 M＋test_keyframe_comfy M＋4 个新测试文件 ??） |
| `git log -1 --format=%h` | 0 | `d8d10a5b` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/fix-p1-save-prefs` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k keyframe_comfy storyboard_recycle_service native_assets storyboard_source_selector project_settings`（改前） | 1 | 共 39 条用例，5 个文件有红 |
| `git -c core.quotepath=false diff --numstat` | 0 | 见上节原文 |
| 同上 `-k` 定向命令（改后第 1 遍） | 1 | 共 39 条用例，1 个文件有红（本轮新增 recycle 用例自身把「挪走目录」断言写在了临时目录 `with` 块外，清理先于断言；产品行为已正确抛错。按卡面只允许改本轮加的测试，把断言收进 `with` 块内） |
| 同上 `-k` 定向命令（改后第 2 遍） | 0 | 共 39 条用例，0 个文件有红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k keyframe_comfy recycle native_run native_assets asset_gating aspect_ratio_priority seedream_direct project_settings ui_edges_controls storyboard_source` | 0 | 共 178 条用例，0 个文件有红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k copy_rules static_names` | 0 | 共 26 条用例（2 个文件），0 个文件有红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 700 tests in 343.5s，失败集合为空，✅ 架构治理测试 OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 输出 `4129` |

改前那一遍恰好 5 条红：

- `test_keyframe_comfy.SavePrefsEntryTests.test_missing_project_raises_and_does_not_recreate`
- `test_native_assets.SelectedSavePrefsTests.test_missing_project_raises_and_does_not_recreate`
- `test_storyboard_recycle_service.RecycleSavePrefsTests.test_missing_project_raises_and_does_not_recreate`
- `test_storyboard_source_selector.SourceSelectorSavePrefsTests.test_missing_project_records_error_and_does_not_recreate`（errors 为空）
- `test_project_settings.SingleWriteEntryTests.test_only_project_settings_writes_prefs_file`（扫描列出上节那四处）

其中一条失败原文（目录为用户目录的部分已写成 %USERPROFILE%）：

```
===== test_missing_project_raises_and_does_not_recreate (test_storyboard_recycle_service.RecycleSavePrefsTests.test_missing_project_raises_and_does_not_recreate) =====
Traceback (most recent call last):
  File "<工作树>\程序\tests\test_storyboard_recycle_service.py", line 65, in test_missing_project_raises_and_does_not_recreate
    recycle_files(proj, "script", [source])
AssertionError: ValueError not raised
```

## 如实说明

- 与卡面不一致处：卡面预演提到「回收那一组挪走后的目录里 final_storyboard_json 仍是 MARK」，本轮用例按卡面把断言放在 `TemporaryDirectory` 块内验证，行为与预演一致；第 4 组替身按卡面写法已够用，未补额外属性。除此之外无不一致。
- 没有在真实界面上试过：四处「用户会看到什么」的结论全部来自读代码（`desktop.py:557`、`desktop_launcher.py:43-52`、`app_logging.py:380-390` 调用链），未起应用验证。
- 改后定向第一遍有 1 条红，原因是本轮新增 recycle 用例自身作用域写法（断言读到已被 `TemporaryDirectory` 清理的目录），按卡面「只允许改本轮加的测试」修正后第二遍全绿；产品文件未为此改动。

## 未覆盖项

- 真实界面没试：四处错误的用户可见表现只按代码推断。
- 全量自测没跑；默认冒烟没单独跑。
- 静态检查只跑了 `copy_rules` 和 `static_names` 两组；其余静态模块与结构检查（governance 下脚本）由派卡窗口另跑。
- 扫描用例只认 `save`、`write_text`、`write_bytes` 三种直写形态；经别的函数间接写设置文件的位置不在本卡范围、没有查（如 `domain/asset_batch_settings_service.py` 的 `_publish_settings`、`orchestrator/stage_gate_gateways.py` 的 `publish_cloud_video_workspace_preference` 与 `publish_cloud_video_session_config`、`domain/storyboard_storage.py` 经 `publish_json` 写的那一组）。
- `recycle_files` 里项目目录不在时文件已移入回收站但 `ui_settings.json` 偏好未写回（`final_storyboard_json` 等残留原值）——属既有写序，本卡不改逻辑，仅记录。
