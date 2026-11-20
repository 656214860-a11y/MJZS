# tasks_round_4012_result — L4-U7d 10 视频生成页输入框位置与其他页一致
<!-- round-evidence: {"commit_base": "8ca777e9", "credential_hits": 0, "evidence_sha256": "1f0eeac636f2beac", "exit": 0, "failed": 0, "passed": 2, "round": 4012, "tests": "run_selftests.py -k desktop_page_nav"} -->

## 三问

- **本轮类型**：修复轮（§3.2；任务卡 L4-U7d，界面契约变更，根因已定位在 `ui/desktop_page_nav.py` 的状态栏显隐特判）。
- **测试跑了吗、三个基线**：跑了。默认冒烟 9/9 通过（`PY -B smoke_test.py`）；架构门禁 685 条全过、失败集合为空（`PY -B smoke_test.py --architecture`，中途因新增测试文件先红了 2 条，补齐登记后复跑全绿）；全量回归本轮未跑——分支轮次不累计源码轮次，最新真实绿凭据 `full-safe-receipts.json` 记 R3961（2026-11-21T00:22，tree 6fe8bf1f），本轮无新增欠账。
- **欠账少了吗**：少了。视频页输入框与共享输入框 43px 错位修复；无新增欠账。

## 任务卡执行方式

- 卡：L4-U7d「10 视频生成页——输入框位置与其他页一致」（§4.9）。
- 做法选**乙**：视频页也显示统一状态栏，视频工作台底栏的状态文字并进状态栏分段。理由：R3016 已把 `bind_status_segment('video', …)`／`video_model` 段接好（`ui/desktop_media_pages.py:644/653`），收起状态栏只是让这段绑定不可见；恢复显示后云端额度行自然回到左区分段，工作台底栏（按钮行／进度行／动态日志）与状态栏内容不重复。甲要把整块底栏挪进状态栏区并压成 43px，会截掉按钮与日志，做不到「信息一条不少」。
- 视频工作台底栏所在模块：`程序/app.py`（`App.footer`，`_build_video_actions` 与 `_build_progress_and_log`）。本轮未改它——底栏信息全留在原位，无内容需要迁移。

## 改了哪些文件

1. `ui/desktop_page_nav.py`（约 271–275 行处）：`_show_reset_page` 不再对视频页 `status_bar.pack_forget()`，统一状态栏在全部页保持 `pack(side='top',fill='x',pady=DESKTOP_LAYOUT['status_gap'])`。打包序不变（`status_bar` 仍是 `body` 里 `area` 之后最后打包者），仍钉在窗口底部。
2. `tests/test_desktop_page_nav.py`（新增）：T1 用真窗口量共享输入框工具行（`shared_input.icon_row`）在 1280×800／1024×680／880×600 三档下视频页与剧本准备页的 `winfo_rooty` 相等；T2 断言统一状态栏与工作台底栏同显，底栏每条信息（13 颗按钮文字、「验收备注：」标签与 `note` 输入框、`progress_text`／`shared_progress` 进度行、「动态日志」标签与 `log` 内容框）仍在窗口里。
3. `维护记录/skip台账.json`：登记新测试文件的 2 处 `skipTest(PLATFORM_TKINTER)`（`VideoPageStatusBarTests._desktop`、`VideoPageStatusBarTests.test_status_bar_and_workbench_footer_stay_visible`）。属新增测试时的必做台账同步（AGENTS.md §5「skip 只引用常量并登记台账」；skip 卫生门禁双向核对），不改它则架构门禁必红。

## 改前的失败输出（先红）

`PY -B scripts\gui_hidden.py logs\l4u7d_red.log . -- PY -B -m unittest tests.test_desktop_page_nav_statusbar -v`（改名前文件名），`FAILED (failures=4)`：

```
AssertionError: 1390 != 1347 : 1280x800 下视频页输入框工具行比剧本准备页低 43px
AssertionError: 1390 != 1347 : 1024x680 下视频页输入框工具行比剧本准备页低 43px
AssertionError: 1390 != 1347 : 880x600 下视频页输入框工具行比剧本准备页低 43px
AssertionError: 0 is not true : 视频页也要显示统一状态栏
```

另：架构门禁改前第一轮 `FAILED (failures=2)`——`test_skip_hygiene`（台账 321 != 源码 323，新测试的 2 处 skip 未登记）与 `test_structure` STR006（新跨模块测试未登记归属）。处置：skip 台账补 2 条；测试文件改名 `test_desktop_page_nav.py`，文件名 stem 与被测模块 `ui/desktop_page_nav.py` 同名，STR006 同名推导自动通过，不动 `governance/structure.json`。

## 测试期望变更

无。排查确认现存用例没有任何一条断言「视频页统一状态栏不显示」（`tests/` 下 `status_bar` 相关用例只覆盖 script/storyboard/assets 页的分段与几何），故没有需要同步的既有断言，更没有删改任何断言。

## 每条验收命令的结果

- `PY -B scripts\gui_hidden.py logs\l4u7d.log . -- PY -B -m unittest tests.test_desktop_page_nav -v` → 退出码 0，`Ran 2 tests … OK`（T1 三档窗口 y 实测相等：1347==1347；T2 两栏同显、底栏信息全在）。
- `PY -B smoke_test.py` → 通过 9 项 / 失败 0 项，`冒烟测试通过`。
- `PY -B smoke_test.py --affected desktop_page_nav` → 选中 2 个测试文件（`test_desktop_page_nav`、`test_shared_input_stages`），共 25 条用例，0 个文件有红，`ALL TESTS PASSED`。
- `PY -B smoke_test.py --architecture` → `Ran 685 tests … OK`，`✅ 架构治理测试`，退出码 0（日志 `logs\l4u7d_arch.log`）。

## 提交前自查（code-review 两轴）

- **规范轴**：改动只在任务卡允许的范围——`desktop_page_nav.py` 的状态栏显隐段；新增测试走 `UiEdgeCase`/`make_adopted_project`/`widget_test_support` 既有夹具，断言量真实几何不比对源码字符串；skip 引用 `PLATFORM_TKINTER` 常量并已登记台账；无新依赖、无魔法数字（43px 只出现在断言消息与注释里说明旧缺陷）。
- **规格轴**：R1 三档窗口实测差 0（改前 43）；R2 两栏内容不重复（状态栏=页标题/路径/用量/video 段；底栏=按钮/进度/日志）、底栏信息一条未少；未改按钮文字、命令与可用条件；未动 `desktop_media_pages.py`、`app.py` 等允许清单外文件（skip 台账属 §5 规定的同步登记）。
- 结论：两轴均通过，无需修改。

## 备注

- 页面切换时 `_show_reset_page` 仍每次 `pack` 状态栏：与初始化时（`desktop.py:346`）同参同序，重 pack 只把它钉回 `body` 打包序末尾（底部），无布局抖动；T1 三档实测相等即证据。
- 本地模式下 `App.status`（「本地生成 · 不消耗云端额度」）本无控件显示（云端侧才绑 `video` 段），本轮前后可见性一致，不属本卡要补的信息；如要补是 `desktop_media_pages.py` 的改动，超出允许清单，留作记录。
- 未提交前 `git status` 将包含本文件与上述三个改动文件。
