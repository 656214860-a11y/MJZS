# R4436：S04-PAGE-REDESIGN 返工——独立审查 6 项 P1 行为缺陷修复
<!-- round-evidence: {"commit_base": "82ca5d1ea", "credential_hits": 0, "evidence_sha256": "dbe0c0a7e045ced1", "exit": 0, "failed": 0, "passed": 188, "round": 4436, "tests": "run_selftests.py -k animatic_page animatic_references animatic_audio animatic_sketch_backends animatic_timeline animatic_service animatic_scope req_s04_anchors copy_rules"} -->

- 轮次类型：§3.2 修复轮（卡面 S04-PAGE-REDESIGN W2；REQ-S04-71/74/76/78/84/96/98/99 相关点位）。
- 测试跑了吗：跑了。先红 28 条（原文见下）→ 修后定向 188 条全绿、media_import_validation 12 条全绿、架构门禁 708 条全绿（当轮实际数，改前 707+1 红→改后 0 红）。默认冒烟未跑（卡面未要求）。
- 欠账少了吗：未新增欠账；`audio_import_service` 未增 L2 import，`animatic_gateways` 未增外部地址登记项（函数行数压回基线，已登记的 `http://127.0.0.1:8188` 行号 75/157 保持不动）。
- 轮次说明：成果原拟以 R4435 提交；首轮 commit 参数笔误留下不可续接凭据（详见 `tasks_round_4435_result.md`），改领 R4436。

## 先红原文摘要（改前 `run_selftests.py -k animatic_page`：共 55 条用例，36.9 秒；4 个文件有红——单文件 4 路分片共 28 条红，exit 1）

【P1-1｜REQ-S04-71/96 参考图自动导入丢失 characters/locations】2 条：

- `ReferenceImportRoutingTests.test_import_lands_character_location_and_style_dirs`：`AssertionError: False is not true : 角色名图应进 角色/，导入必须带分镜 characters`（真实临时项目导入后 `角色/林夏.png` 不存在，全归 风格/）。
- `FilesPanelHookTests.test_import_handler_classifies_by_suffix`：`AssertionError: {'characters': [], 'locations': ['LOC_01']} != {}`（调用 `import_animatic_reference_library` 未传 characters/locations kwargs）。

【P1-2｜REQ-S04-99/96 「本地生成参考草图」死锁不可达】4 条：

- `PlayAreaTests.test_video_menu_has_external_open`：`AssertionError: '本地生成参考草图' not found in ['用外部播放器打开', '重新合成新版本'] : 播放区右键应常驻草图入口`。
- `SketchEntryTests.test_video_menu_without_video_offers_sketch_and_generate`：同上断言（无视频时菜单无草图项、无「生成分镜预演」）。
- `SketchEntryTests.test_empty_player_binds_context_menu`：`AssertionError: '' is not true : 无视频态播放容器应绑右键菜单`。
- `SketchEntryTests.test_panel_hook_offers_sketch_for_non_reference_file`：`AssertionError: '本地生成参考草图' not found in []`（面板非参考图右键空菜单）。

【P1-3｜REQ-S04-84/98 重合成状态陈旧＋异步回调切页崩溃与状态段泄漏】8 条：

- `RefreshLifecycleTests.test_refresh_after_recompose_resets_version_and_checks`：`AssertionError: 'animatic_v002' != 'animatic_v001'`（v002 发布后 state 仍是 v001）。
- `RefreshLifecycleTests.test_stale_page_refresh_stays_quiet`：`AssertionError: 'animatic_note' unexpectedly found in {...}`（切页后迟到回调仍写状态段）。
- `StaleCallbackTests.test_dead_frame_callbacks_do_not_raise_or_write`：`_tkinter.TclError: bad window path name ".!frame.!frame.!frame2"`（`_refresh` 对已销毁 frame 重画）。
- `StaleCallbackTests.test_stale_page_never_rebuilds_other_index`：`AssertionError: Lists differ: [] != [5]`（页码不匹配仍回调 `page.show(5)`）。
- `StaleCallbackTests.test_locked_reports_only_when_project_matches`：`[] != [('animatic', '节奏、时长与对白同步均已确认')]`（项目已切换仍上报 pet_report）。
- `StaleCallbackTests.test_destroy_releases_without_shared_input`：`'' != '分镜 1 镜 / 参考图 0 张 / 声音：静音 / 未生成'`（无 shared_input 时漏绑 `<Destroy>`，状态段泄漏）。
- `StaleCallbackTests.test_destroy_after_page_switch_releases_own_handlers`：`3 unexpectedly found in {3: (...)} : 切页后销毁应释放建页时登记的页码`（按新页码误释放别页登记）。
- `StaleCallbackTests.test_on_send_delegates_after_stage_switch`：`AssertionError: True is not false : 共享框已切到别阶段时，本页 wrapped 应放行给原发送链`。

【P1-4｜REQ-S04-78 设置透传丢失、source 丢失、worker 防重入缺失】7 条：

- `SettingsPassthroughTests.test_generate_passes_settings_and_current_source`：`KeyError: 'source'`（run_command 未传 source/settings）。
- `SettingsPassthroughTests.test_redo_passes_settings`：`KeyError: 'settings'`。
- `SettingsPassthroughTests.test_worker_busy_rejects_run` / `test_worker_busy_rejects_redo`：`AssertionError: True is not false`（worker 占用时仍放行）。
- `ShotMenuTests.test_menu_items_and_redo`、`SendCommandTests.test_typed_redo_only_regenerates_that_shot`：`expected call not found. Expected: regenerate_animatic_shot(..., 'SH001', settings={}) / Actual: regenerate_animatic_shot(..., 'SH001')`（旧断言漏 settings 同步修正）。
- `SendCommandTests.test_empty_send_generates_timeline`：`KeyError: 'source'`（旧断言同步修正）。

【P1-5｜切分镜后 source/board 陈旧】1 条：

- `BoardSwitchTests.test_select_board_swaps_source_board_and_import_routing`：`AssertionError: '03初步分镜/分镜拆分/ep_b.json' != '03初步分镜/分镜拆分/ep1.json'`（切板后 source 仍是旧板）。

【P1-6｜REQ-S04-74/76/96 声音优先级反置＋面板导入落地断层】6 条：

- `AudioImportRouteTests.test_track_audio_lands_in_track_dir_and_sets_mode`：`AssertionError: 1 != 0 : 面板导入整轨音频必须落 声音/整轨/ 才会被合成读取`（落在 04分镜预演/ 根目录）。
- `AudioImportRouteTests.test_music_audio_lands_in_music_dir`：`AssertionError: 1 != 0 : bgm/音乐 文件名应落 声音/音乐/`。
- `AudioImportRouteTests.test_explicit_track_param_routes`：`TypeError: import_animatic_audio() got an unexpected keyword argument 'track'`。
- `AudioImportRouteTests.test_track_dir_beats_dialogue_audio`：`AssertionError: '整轨' != '逐镜 TTS'`（优先级反置）。
- `AudioImportRouteTests.test_music_dir_is_not_reported_as_track`：`AssertionError: '静音' != '整轨'`（音乐目录误报整轨）。
- `TimelineTrackTests.test_dialogue_within_tolerance_not_marked`：`AssertionError: '对白超长' unexpectedly found in [...]`（缺 OVERLONG_TOLERANCE_SECONDS 容差）。

（修后首轮 `test_panel_hook_offers_sketch_for_non_reference_file` 曾单红，定位为测试辅助 `_menu_labels` 把 `index('end')==0` 当空菜单的 off-by-one，修正测试自身后转绿；产品代码该点位本就正确。）

## 改了哪几处

- `ui/animatic_page.py`（+122/-60）：
  - P1-1：`_import_files` 参考图分支新增 `_board_names(board)` 从 `state['board'].values()` 提取去重 characters/locations，调用 `import_animatic_reference_library(..., characters=chars, locations=locs)`。
  - P1-2：`video_context_menu` 常驻「本地生成参考草图」（`_open_inline_edit` 草图描述条），有视频含「用外部播放器打开」「重新合成新版本」，无视频含「生成分镜预演」；`_build_player` 无视频态在播放容器与占位控件上绑 `<Button-3>`；`_reference_menu_hook` 去掉无参考图早退，「修改参考图分类」仅限共享参考图目录内图片。
  - P1-3：`_new_state` 记 `page_index`；新增 `_is_alive`（frame 存在+winfo_exists+页码一致）；`_refresh` 先判 `_is_alive`，每次重载 timeline/video/manifest/version_tag/confirmed 并复位 `checks`，video 变更且页码匹配才 `page.show` 重建否则重画；`_after_sketch`/`_locked` 操作前校验 `_is_alive`（`_locked` 仅 `page.root == state['project']` 才上报）；`_build_confirm_bar` 用 `bool(state.get('confirmed'))` 初始化三项 BooleanVar；`show()` 无论有无 shared_input 均绑 `<Destroy>`（按 `state['page_index']` 释放＋清 `animatic_note`）；wrapped 检查 `shared.stage == 'animatic'`。
  - P1-4：新增 `_animatic_settings`（浅拷贝 settings，`comfy_url`→`url`）；`_run_async` 开头拦 `page.worker` 重入（置状态文案返回 False）；`_redo_shot` 传 `settings=`，`run_command` 传 `source=`＋`settings=` 并返回 `_run_async` 结果。
  - P1-5：`_select_board` 同步更新 `source`/`board`/`video`/`manifest`/`version_tag`/`confirmed` 再重画。
  - P1-6：`_audio_mode` 改整轨优先（`声音/整轨/`→'整轨'→dialogue_audio→'逐镜 TTS'→manifest.audio→'整轨'→'静音'）；`_dialogue_cell` 超长比较加 `OVERLONG_TOLERANCE_SECONDS` 容差。
- `ui/desktop_status_bridge.py`（+1/-1）：`clear_page_segments` 元组补 `'animatic_note'`。
- `domain/audio_import_service.py`（+8/-2）：`import_audio` 增可选 `subdir=None`（仅 `stage=='animatic'` 且 `target.resolve().is_relative_to(folder.resolve())` 校验后落 `folder/subdir`）；无新增 import。
- `orchestrator/stage_animatic_gateways.py`（+12/-2）：`import_animatic_audio` 加 `*, track=None`；新增 `_animatic_audio_route`（显式 track 优先，否则文件名含 bgm/music/音乐/配乐→'music' 其余→'track'，传 `animatic_audio.SUBDIRS[kind]` 为 subdir）。函数压回基线行数、辅助函数置于 157 行之后，已登记外部地址行号不漂（`docs/process/外部依赖清单.md` 不在本卡允许清单）。
- `tests/test_animatic_page.py`（+378/-8）：新增 6 个测试类共 28 条真实行为用例（真临时项目、不 mock 被测网关/分类器）；两处 stale mock 断言补 `source=`/`settings=` kwargs（行为断言不弱化）；修 `_menu_labels` off-by-one。

## 验收命令输出尾部原文

命令 1：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_page animatic_references animatic_audio animatic_sketch_backends animatic_timeline animatic_service animatic_scope req_s04_anchors copy_rules`（目录 程序，exit 0）

```
共 188 条用例，25.5 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：…\.git\selftest-incremental.json
最近 5 轮自检中位基线：44.8 秒
ALL TESTS PASSED
```

命令 2：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，exit 0）

```
Ran 708 tests in 252.412s
OK
✅ 架构治理测试：tests/architecture
```

附加：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k media_import_validation`（exit 0）：`共 12 条用例，3.1 秒；0 个文件有红 / ALL TESTS PASSED`。

git diff --numstat（改后工作树 vs 82ca5d1ea，产品代码＋测试）：

```
8	2	程序/domain/audio_import_service.py
12	2	程序/orchestrator/stage_animatic_gateways.py
378	8	程序/tests/test_animatic_page.py
122	60	程序/ui/animatic_page.py
1	1	程序/ui/desktop_status_bridge.py
```

## 未验证项

- 真实 ComfyUI 出图、真实视频播放、真实 FFmpeg 合成未在本机端验证（页面动作经注入回调与网关桩/真实临时项目目录覆盖）。
- 全量 `--all --safe` 与默认冒烟未跑（卡面不要求；定向、media_import_validation 与架构门禁均绿）。

## 卡外发现（只记录）

- `test_http_boundary` 的行号登记口径意味着在已登记外部地址行之前净增行数即红；本轮用「函数压回基线行数＋辅助函数后置」规避，`docs/process/外部依赖清单.md` 未动。
- 显式提交凭据 `explicit-commit-receipts/R<N>.json` 在 `git add` 失败前已写入 identity：路径参数一旦写错，该轮次号即不可复用（见 `tasks_round_4435_result.md`）。
- 本机 `运行环境` 不在本工作树内，Python 走主工作区解释器；`logs/` 未读（卡面禁止）。
