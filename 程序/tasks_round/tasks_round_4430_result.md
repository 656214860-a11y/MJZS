# R4430：S04-PAGE-REDESIGN 少按钮三段式预演页
<!-- round-evidence: {"commit_base": "34c13e0e0", "credential_hits": 0, "evidence_sha256": "f7b429ae388759b1", "exit": 0, "failed": 0, "passed": 164, "round": 4430, "tests": "run_selftests.py -k animatic_page animatic_references animatic_audio animatic_sketch_backends animatic_timeline animatic_service animatic_scope req_s04_anchors copy_rules"} -->

- 轮次类型：§3.1 功能轮（REQ-S04-95…99、DES-S04-25；同步翻 ✅：REQ-S04-62、REQ-S04-70…99、DES-S04-20…25）。
- 测试跑了吗：跑了定向与架构门禁，全绿。三个基线：定向 164 条全绿（9 个文件、0 红）；架构门禁 708 条全绿（当轮实际数）；覆盖率基线按原 15 个核心目标真实重测刷新（687 模块/133 触达/554 未触达/195 条目标用例全绿）。
- 欠账少了吗：未新增欠账；`json.loads` 裸债务未新增（新模块读取全走 `file_cache.read_json` 与 L3 网关）。

## 先红摘要（本车道上一会话先写测试，原文未留在工作树）

按卡面「先红后绿」顺序执行：先建 `tests/test_animatic_page.py`（31 条：指令解析、状态摘要、空项目引导、确认条显隐、右键菜单动作、常驻按钮上限、7 项功能入口保真），并在 `tests/test_ui_edges_pages.py` 加 `test_animatic_page_low_button_layout`、`tests/test_media_page_buttons.py` 改 04 页断言，再实现。改前变红的原因即卡面缺陷（由当前 diff 可机械复核）：

- `ui/animatic_page` 在基准 34c13e0e 树内不存在，新测试与薄壳 `from ui.animatic_page import show` 的引入点先红（`ImportError`）。
- 旧 04 页是 7 颗常驻按钮＋3 个 `LineInput`＋3 个 `Checkbutton`＋1 颗「确认预演（SG-B）」（`git diff` 中被删的 85 行堆叠代码），与「常驻按钮 ≤1」「未生成无确认勾选」断言直接矛盾。
- 文件面板无 `set_import_handler`／`set_menu_handler`，新用例调用先红（`AttributeError`）。

本轮收口前的三处遗留红（总控升级报告给出的缺陷，本轮逐项核实后修复）：

- `test_platform_process_boundary`：`SPAWN_SITE_EXEMPT['detached']` 登记的 `ui/desktop_media_pages.py:914` 已漂移——`launch_windows_app('剪映专业版')` 实测在 `:832`（`ui/desktop_media_pages.py:832`，删旧 85 行所致），旧登记既漏新点又留死点。
- `test_coverage_baseline.test_core_paths_meet_recorded_floor`：上次刷新 `覆盖率基线.json` 漏传第 10 个目标 `tests.test_publication_recovery`（只跑了 14 目标 183 条），`agent/publication.py` 实测 64.6% 低于登记下限。
- skip 台账覆盖：`test_ui_edges_pages.py::UiEdgePagesTests.test_animatic_page_low_button_layout`（`tests/test_ui_edges_pages.py:100-103` 的 `skipTest(PLATFORM_TKINTER)`）未登记。

## 改了哪几处

- `ui/animatic_page.py`（新建 L4，748 行）：`parse_animatic_command`（空/「生成」→generate，「只重做 SH003」「重做 sh003」→redo_shot）；`format_status_summary`（`分镜 N 镜 / 参考图 M 张 / 声音：… / vNNN 未确认|已锁定|未生成`）；`show(page)` 三段式——上方播放区（无视频显当前镜缩略图、有视频显封面＋点击外部播放＋右键「用外部播放器打开」，经 `page.media_page_services.open_path`，未注入时回退可选回调）、中间时间线（按时长比排格＋对白轨「对白超长」高亮＋音乐轨，镜头格右键六项：重做这一镜、用导入的图替换、改时长、切换图版本、查看提示词与所用参考图、写批注；改时长/写批注走时间线下内联编辑条，不弹窗）、生成后可播放版本才出现的确认锁定条（3 个 Checkbutton＋1 颗「锁定」SecondaryButton，未全勾只写状态栏）；自动载入 S03 已采用分镜（多份时经 `files_panel.set_select_handler` 点选）、`shared_input.set_stage_action('animatic', ...)`＋`<Destroy>` 释放登记与状态段；只注入回调、业务全走 `stage_execution_service`／`stage_animatic_gateways`，无弹窗、无手写 `tk.PhotoImage`（缩略图走 `asset_thumbs`）、无 `http://` 字面量（ComfyUI 地址只读 `page.settings.get('comfy_url')`）。
- `ui/desktop_media_pages.py`：`animatic_page` 删旧 85 行堆叠代码，改两行薄壳 `from ui.animatic_page import show; return show(self)`（文件 982→900 行，类实测 788 行）。
- `ui/desktop_files_panel.py`：新增 `set_import_handler`／`set_menu_handler`（登记页码失效制，仅 animatic 注册），`import_files` 命中自定义 handler 时委派，索引行单选右键放行登记挂钩；其余阶段行为不变。
- `tests/test_animatic_page.py`（新建，31 条）：覆盖卡面全部边界例子。
- `tests/test_ui_edges_pages.py`：+34 行新用例（真实 Desktop 验证常驻按钮 ≤1、未生成无勾选、发送动作已登记）。
- `tests/test_media_page_buttons.py`：04 页用例改为新布局断言（未生成确认条隐藏、常驻 ≤1；写出版本后三勾选＋「锁定」可见），11/12/13 页用例逐字未动（用户批准的 S04 布局契约变更 REQ-S04-95/96/98/99）。
- `tests/architecture/_layers.py`：`_register(4, "animatic_page")`；SAME_LAYER_EDGES 补 `('animatic_page','asset_thumbs')`、`('animatic_page','desktop_files_panel_filters')`、`('animatic_page','ui_widgets')`、`('desktop_media_pages','animatic_page')`（无互依赖）。
- `tests/architecture/test_complexity_ratchet.py:75`：`MediaPagesMixin` 登记 885→803（实测 788＋15 余量，同 S03 口径）。
- `tests/architecture/test_platform_process_boundary.py:80`：豁免点 `:914`→`:832`（收口 1）。
- `docs/process/外部依赖清单.md`：删 `:507`（旧 animatic_page 的 `http://127.0.0.1:8188`），`:801`→`:719`。
- `docs/process/外发内容清单.md`：删 `animatic_page.preview`（L567，`open_target`）一行；`audio` 行号 `:801`→`:719`。
- `维护记录/skip台账.json`：追加 `test_ui_edges_pages.py::UiEdgePagesTests.test_animatic_page_low_button_layout` 的 PLATFORM_TKINTER 登记（收口 2，无计数字段）。
- `维护记录/覆盖率基线.json`：全齐 15 个目标真实重测刷新（收口 3；`tests.test_publication_recovery` 已回 targets，`agent/publication.py` 回到 89.0%，`modules_total` 687、`modules_covered` 133、`tests_ok` true）。
- `runbook.md` §11：686→687、553→554，口径句同步。
- `docs/stages/S04_分镜预演.md`：REQ-S04-62 与 REQ-S04-70…99 全部 ⬜/🟡→✅，DES-S04-20…25 标已实现，L4 模块表行与测试锚定表同步新模块与新锚点。

## 验收命令输出尾部原文

命令 1：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_page animatic_references animatic_audio animatic_sketch_backends animatic_timeline animatic_service animatic_scope req_s04_anchors copy_rules`（目录 程序，exit 0）

```
共 164 条用例，28.4 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：…\.git\selftest-incremental.json
最近 5 轮自检中位基线：12.6 秒
ALL TESTS PASSED
```

（首次执行因跨树 GUI 令牌被占，`test_animatic_page`/`test_animatic_scope` 两个 GUI 文件 GUI_DEFERRED 未计通过、exit 1；稍候重跑即全量执行。）

命令 2：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，exit 0）

```
Ran 708 tests in 258.935s
OK
✅ 架构治理测试：tests/architecture
```

附加：`scripts\coverage_report.py <15 核心目标> --json 维护记录\覆盖率基线.json`：`Ran 195 tests in 48.778s / OK`，`模块被覆盖：133/687；目标用例：全通过`。

## 未验证项

- 真实 ComfyUI 出图、真实视频播放与真实文件导入未在本机端验证（页面动作经注入回调与网关桩覆盖）。
- 全量 `--all --safe` 未跑（卡面不要求；定向与架构门禁均绿）。
- 先红阶段的失败输出原文未保留在工作树（上一会话未落盘），本文件按可复核的代码事实记录红因。

## 卡外发现（只记录）

- 本机 `运行环境` 不在本工作树内，Python 走主工作区解释器（卡面口径）。
- 会话接续记录文件不在本卡允许修改清单内，本轮未写该文件。
