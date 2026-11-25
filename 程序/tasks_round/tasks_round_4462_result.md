# tasks_round_4462_result — DOC-S04 S04 阶段文档补接口与交互两节
<!-- round-evidence: {"commit_base": "1f66bd04d", "credential_hits": 0, "evidence_sha256": "2b9bb3c0833766c7", "exit": 0, "failed": 0, "passed": 0, "round": 4462, "tests": "docs-only"} -->

## 三问

1. 本轮类型：§3 之外的任务卡轮——纯文档轮（DOC-S04，W2，工作树 `doc-s04-sections`，分支 `codex/doc-s04-sections`），只改 `docs/stages/S04_分镜预演.md`（末尾追加）与本结果文件，未改任何 `.py`。
2. 测试：按卡面跑文档门禁 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（34 用例 0 红，退出码 0）；`smoke_test.py --architecture`（708 用例 OK，退出码 0）；`smoke_test.py`（通过 9 项、失败 0，退出码 0）。
3. 欠账：无新增欠账；文档与代码不一致处记入下方差异清单，未改任何既有 REQ/DES 条目。

## 改动

`docs/stages/S04_分镜预演.md` 末尾（`## 设计` 整节之后）追加 `## 接口`（读入 16 行 IF-S04-01~16、写出 14 行 IF-S04-20~33、完成判定与交接 9 行 IF-S04-40~48、对外调用 5 行 IF-S04-60~64）与 `## 交互`（页面区域 7 块＋共用部分说明、控件与操作 23 行 UX-S04-01~23、页面状态 10 行 UX-S04-60~69、键盘右键拖放 7 行 UX-S04-80~86）。`git diff --numstat`：`135 0`，仅新增行，既有「需求」「设计」两节一字未改。

## 读过的文件清单（证据为 file:line）

- `docs/process/阶段文档写法.md`：三级标题与编号段规则（`:26-29`）、读入/写出表头（`:56/:62`）、状态记号（`✅` 须带反引号位置、`⬜` 须写来源）。
- `tests/architecture/test_stage_doc_sections.py:60-141`：R1–R6 守卫实际判定逻辑。
- `docs/stages/S01_剧本准备.md:355-485`：已过检两节样例（表头与行式）。
- `docs/stages/S04_分镜预演.md:1-192`：全文（追加前基线；REQ-S04-95…99 在 `:97-101`，DES-S04-20…25 在 `:151-170`）。
- `ui/animatic_page.py:1-810`：`parse_animatic_command:38`、`format_status_summary:46`、`_guide:202`、`_build_confirm_bar:212`、`_build_player:228`、`_build_tracks:266`、`_render_timeline:286`、`_shot_cell:310`、`_dialogue_cell:323`、`_open_inline_edit:344`、`_refresh:376`、`_update_summary:398`、`_redo_shot:409`、`_replace_shot_image:417`、`_apply_seconds:449`、`_apply_sketch:458`、`_show_shot_info:486`、`_lock:497`、`_locked:509`、`_open_video:520`、run_command:529、`shot_context_menu:549-567`、`video_context_menu:570-580`、`_reclassify:583`、`_reference_menu_hook:590-607`、`_import_files:612`、`_select_board:648`、`_register_panel:706`、`_register_send_key:722-759`、`_new_state:760`、`show:782`、`build_animatic_page:808`。
- `tests/test_animatic_page.py:1-522`：菜单六项文案（`:463-465`）、确认条三勾＋锁定（`:378-405`）、发送键行为（`:411-450`）、面板三挂钩（`:344-349`）、状态段 `animatic_note`（`:350-368`）。
- `domain/animatic_references.py`：`CATEGORIES=('角色','场景','风格')`、`UNCATEGORIZED`、`classify`、`library`、`refs_for_shot`、`import_plan`（摘要去重＋同名编号）。
- `domain/animatic_audio.py`：`SUBDIRS`（对白/整轨/音乐）、`plan`（`full_track`/`per_shot_tts`/`silent`）、`shot_tts`（`…_temp_<sig>.mp3` 复用、`request_id='tts-previs:<shot>:<sig>'`）、`detect_overlong`（`OVERLONG_MESSAGE`）、`build_audio_mix_command`。
- `domain/animatic_sketch_backends.py`：`BACKENDS`/`register`/`create`、`DEFAULT_BACKEND='comfy_local'`、`comfy_local_render`、`validate_imported_sketch`。
- `domain/animatic_timeline.py`：`TIMELINE_FILE`、`MIN_DURATION=2`/`MAX_DURATION=15`、`build`（`_CARRIED`）、`set_duration`/`set_version`/`set_note`、`next_version`、`next_video_name`（`版本/animatic_v%03d.mp4`）、`writeback_plan`。
- `domain/animatic_service.py`：`MANIFEST='animatic_manifest.json'`、`CONFIRMATIONS`、`_future_blocked`、`validate_bundle`、`shots_of`、`build_bundle`、`evidence`。
- `orchestrator/stage_animatic_gateways.py:1-667`：`publish_animatic_bundle`、`import_animatic_reference_library`/`import_animatic_references`、`reclassify_animatic_reference`、`import_animatic_audio`、`generate_animatic_reference`、`run_animatic`、`load_or_sync_animatic_timeline`、`update_animatic_shot`、`regenerate_animatic_shot`、`replace_animatic_shot_image`、`_timeline_audio`、`run_animatic_timeline`、`confirm_animatic`、`lock_animatic:607-667`（历史版本存档→`writeback_plan`→`validate_episode`→`adopt`→清单，事务回滚）。
- `orchestrator/stage_completion_service.py:760-761`：`stage=='animatic'`→`domain.animatic_service.evidence`。
- `orchestrator/storyboard_selection.py:96` `adopted`、`:100` `current_source`、`:256-262` `sync_draft_outputs`（`03初步分镜/output/` 落 `storyboard_draft.json`＋`scene_breakdown.json`）、`:270-294` `draft_problems`、`:297` `adopt`。
- `orchestrator/stage_publication.py:70/112/141`、`orchestrator/stage_gate_gateways.py:24`、`orchestrator/stage_flow.py:28/39/61-62/85`（`DEPENDS['animatic']=('storyboard',)`）、`orchestrator/stage_parallel.py`（`evaluate` 门禁入口）、`stage_execution_service.py:33`（重导出 animatic 网关）。
- `contract/stage_path_service.py:28-66`（`shared_reference_dir`/`shared_reference_read_dirs`/`write_dir`/`read_dirs`）；`contract/script_contract.py:979-1054`（`STAGE_LOCK_REQUIREMENTS` 无 `animatic`）；`contract/script_output_spec.py:87-99`（`preview_spec`/`output_filter`）；`contract/platform_tools.py:162/302/336/361`；`contract/episode_contract.py:120`；`contract/storyboard_paths.py:21`；`contract/pet_bus.py:26-39`。
- `domain/edit_service.py:66-102`（`assemble_image_timeline`）、`:117-130`（`render_mixed_audio`）；`domain/audio_import_service.py:13-57`；`domain/tts_api.py:288-293`（`script_signature`）、`:741-787`（`synthesize`）。
- `infra/comfy_runtime.py:18/35`、`infra/comfy_service.py`（`Comfy`/`ComfyGenerationFailed`/`ComfySubmissionUncertain`）；`infra/file_cache.py:234/276/297/336`；`infra/file_index.py:36-38`；`infra/pet_state.py`（`PAGE_OF`，见 `ui/animatic_page.py:24/208`）；`infra/storage_maintenance.py`（`recycle_paths`，见网关 `:227`）。
- `ui/desktop_files_panel.py:250/263/287`、`ui/desktop_files_panel_filters.py:24/679/832-853/939`（`import_suffixes['animatic']`＝图｜音｜视频）；`desktop_shared_input.py:55-109`（`_upstream_error`/`_send_empty_storyboard`）、`:526-548`、`:950-987`。
- `desktop.py:120-141`（`MediaPageServices`）、`:157-181`（`_present_stage`：`SHOW_ANIMATIC`→`desktop.show(STAGES.index('animatic'))`）；`ui/desktop_media_pages.py:37-38/499-500`；`ui/desktop_page_nav.py:229`；`ui/skill_tools.py:532-534/614-658`（`PAGES['animatic.generate'/'animatic.validate']`→预演页）。
- `ui_widgets.py:492/749/819/826/1109/1115`；`ui/asset_thumbs.py:176/212/297/496`；`skills/04 分镜预演SKILL/pipeline-animatic.skill.md:1-49`；`tasks_round/工程文档细化任务书.md §4.0/§4.9`；`tasks_round/tasks_round_4443_result.md`（格式参照）。

## 控件数对照

构建代码创建的可操作控件（`ui/animatic_page.py` 亲读）：

- 静态控件 7 个：引导钮「去初步分镜」1；确认条勾选框 3＋「锁定」钮 1（仅在有可播放版本时构建，`_build_confirm_bar`）；播放区可点面 1（`<Button-1>`/`<Button-3>`，`_build_player`）；内联输入条 1（`_open_inline_edit` 复用）。
- 动态控件：镜头格每镜 1 格（`_shot_cell` 绑 `<Button-3>`，数量随分镜镜数）。
- 右键菜单项 11 个：镜头菜单 6（`shot_context_menu:553-566`）、播放区菜单 ≤3（`video_context_menu:573-579`）、参考图挂钩 2（`_reference_menu_hook:600-606`，其中「修改参考图分类」为 3 项子菜单）。
- 本页登记在共用控件上的行为 5 个：发送动作 1＋`on_send` 包装 1（`_register_send_key`）、面板挂钩 3（`_register_panel`：点选/导入/右键）。

「控件与操作」表 23 行（UX-S04-01~23），与上数不等，逐个说明：

- 勾选框 3 个拆 3 行（UX-S04-03~05）；引导钮、封面、锁定各 1 行（01/02/06）。
- 内联输入条 1 个不单列：三个触发入口「改时长」「写批注」「本地生成参考草图」各一行（12/15/19），其 Enter/Esc 行为入键盘节（UX-S04-83）。
- 动态镜头格不按格数拆行；其 6 个菜单项拆 6 行（10~15）；播放区菜单 3 项＋参考图挂钩「本地生成参考草图」与播放区同名项合并计 4 行（16~19）。
- 面板 3 个挂钩拆 2 行（20 导入分流、21 点选分镜）＋参考图右键改分类 1 行（22）。
- 发送登记拆 3 行（07 空发＝生成、08 文本重做、09 「/」放行原链）。
- UX-S04-23 为固定目标行「过程与回话区」，无对应控件（⬜ 来源：用户决定 2026-11-21；细节见专题册 08）。

## 差异清单（文档已有条目 vs 代码，未改既有行）

1. REQ-S04-96（`docs/stages/S04_分镜预演.md:100`）写「参考图、整轨配音、音乐都走文件面板的导入入口**或拖入**」；代码里文件面板与本页均无拖放绑定（`ui/` 全目录无 windnd/DnD/drop 相关绑定），导入唯一入口是面板「导入文件」→`desktop_files_panel_filters.import_into_stage:939`/本页 `_import_files:612`。交互节按现状写（UX-S04-86）；需求行未改。
2. 「没有打开项目」「空项目未采用」「S03 未完成」三种情形在代码里走同一 `_guide` 引导页（`ui/animatic_page.py:202`、`show:782` 对 `page.root` 为空与拿不到时间线同一处理，文案均指向初步分镜）；本文件按规范在「页面状态」分列为 UX-S04-60/61/62 并注明同一依据，无对应需求行改动。

## 待裁决清单

无标 ❓ 的行；无待裁决项。固定目标行「过程与回话区」按卡面标 ⬜（来源：用户决定 2026-11-21；细节见专题册 08），归主控按专题册 08 推进，不在本轮裁决。

## 验收

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（cwd=`程序/`）：4 个测试文件 34 用例，`ALL TESTS PASSED`，退出码 0。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：`Ran 708 tests in 293.095s`，`OK`，退出码 0。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py`：`通过：9 项 失败：0 项`，退出码 0。
- `git diff --numstat -- 程序/docs/stages/S04_分镜预演.md`：`135 0`（仅新增行，0 删除）。

## 未验证项

- `_select_board` 对所选 `.json` 的校验文案按调用链与既有提示文本引用，未逐字截屏核对其全部报错分支。
- `desktop_page_nav.py:229` 只核到构建器列表登记 `self.animatic_page`，翻页调度内部未逐行读。
- `run_selftests --all --safe` 全量未跑（卡面只要求文档门禁＋两条 smoke；纯文档轮无 `.py` 改动）。
