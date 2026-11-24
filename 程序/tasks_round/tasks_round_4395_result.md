# R4395 FIX-S11-E6：导入音频选用途，BGM 不再被当成对白（修复轮）
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "59b359562cc48fbe", "exit": 0, "failed": 0, "passed": 67, "round": 4395, "tests": "run_selftests.py -k audio_import audio_role_binding stage_completion"} -->

## 来源
任务卡 FIX-S11-E6（波次 W2），出处 AUD-US05 报告第 3 段 E-6、第 5 段 FIX-E6；2026-11-24 按 N855 修订：不新建模块、不扩 `desktop_media_pages.py` 行数，胶水放进既有已被其导入的 `ui/tts_settings.py`。工作树 `codex/fix-s11-e6`，基准 67fd96c9。

## 轮次类型／三套基线／债务
修复轮（§3.2）：缺陷在 L3/L4 接缝——`import_stage_audio` 不接受用途 `kind`，页面把导入音频一律按对白处理；L2 `audio_import_service.import_audio(kind=)` 与 `tts_api.AUDIO_KIND_*` 前缀、成果确认拒非对白早已在（R1356）。测试已跑：定向 67/67 绿（改前 61 + 新增 6），架构门禁 708/708，默认冒烟本轮未运行（卡面验收只列两条命令，未运行项如实标注）。无新增债务。

## 缺陷复现与改前红（先写测试后改产品）
命令：`run_selftests.py -k audio_import audio_role_binding stage_completion`，改前共 67 条、7 条红，原因与缺陷一致：

- `test_audio_role_binding.test_l3_bgm_import_is_still_not_dialogue`：`TypeError: import_stage_audio() got an unexpected keyword argument 'kind'`（L3 不透传用途）
- `test_audio_import_service.test_bgm_kind_reaches_domain_and_marks_the_name`：同上 `TypeError`
- `test_audio_import_service.test_desktop_import_failure_success_and_cancel`、`test_selected_kind_is_passed_to_l3`、`test_cancelled_choice_imports_nothing`、`test_failed_import_surfaces_reason_like_before`：`AttributeError: <module 'ui.tts_settings' ...> does not have the attribute 'ask_audio_kind'`（L4 胶水缺失）
- `architecture.test_audio_import_boundary.test_desktop_delegates_audio_copy_to_service`：`AssertionError: 0 != 1`（页面未调用胶水）

## 改动
- `stage_execution_service.py:174-185`：`import_stage_audio`/`_import_audio_file` 加 `kind='dialogue'`，原样传给 `import_audio`（既有调用不变）。
- `ui/tts_settings.py:10` 加 `BaseDialog` 导入；`:97-140` 新增 `_AUDIO_KIND_CHOICES`、`AudioKindDialog`（BaseDialog＋ttk.Radiobutton 五选一，默认对白，取消/Esc/关闭为 None）、`ask_audio_kind`（`wait_window` 同步语义，照 `ask_string` 口径）、`import_audio_with_kind`（问清用途→`import_stage_audio(project, source, kind=kind)`→`app.async_`＋`音频已导入：` 状态回写，取消不导入）。
- `ui/desktop_media_pages.py:802-815`：`import_audio` 保持 14 行不变，改为工作区＋文件对话框后调 `import_audio_with_kind(self,p)`；文件仍 982 行，`:914` `launch_windows_app(executable, '剪映专业版')` 钉点未漂移（净行差 0）。

## 测试契约有意变更（按卡面第 5 条同步并注明）
- `tests/architecture/test_audio_import_boundary.py:15-27`：委托点由 `import_stage_audio` 改为 `import_audio_with_kind`（页面→胶水→L3 新契约），并新增「页面内直调 `import_stage_audio` 计数为 0」与胶水源码 `import_stage_audio(project, source, kind=kind)` 两处锚点；L3 断言随 `kind=kind` 透传同步。L2 直写禁令、`publish_imported_media` 注入断言未动。
- `tests/test_audio_import_service.py:87-113`：行为断言（失败抛原因、成功写同一状态文案、取消不导入）保持原样；只改 mock 挂接点——旧 `FileDialog` 命名空间桩对现行 `media_page_services.file_dialog` 实现是死桩，改为 `app.media_page_services.file_dialog.return_value.open_file.return_value`，取消分支由「async_ 不执行 work 空过」变为真实覆盖 `if not p:return`。新增 `StageAudioImportKindTests`（L3 BGM 落盘带 `BGM_` 前缀、不传 kind 落盘名逐字一致）与 `ImportAudioWithKindTests`（选 BGM→L3 收到 `kind='bgm'`、取消不导入、失败原因照旧抛出）。
- `tests/test_audio_role_binding.py:190-203`：新增 `test_l3_bgm_import_is_still_not_dialogue`——经 L3 按 BGM 导入落进成果目录后，`prepare_media_completion` 仍拒「所选音频都不是对白音轨」。

## 改后验证
- `run_selftests.py -k audio_import audio_role_binding stage_completion`：67/67 绿，退出码 0（中途两次因其它车道全量占 GUI 令牌、`test_stage_completion_service` 60 秒超时未执行而退出码 1，非测试失败；令牌空出后原样重跑全绿）。
- `smoke_test.py --architecture`：首次红 1 条 `test_numeric_padding_does_not_increase`（新代码 `pady=(0, ...)` 数字 padding 违规），改 `SPACING['none']` 后复跑 708/708 绿，退出码 0。

## 未验证项
- `AudioKindDialog` 真实 Tk 弹窗未人工点击（新测试按卡面要求不建真窗口，交互语义照 `BaseDialog`/`ask_string` 同源实现）。
- 真实 ffprobe 导入链路本轮用注入 `publish` 替身验证 L3 透传；真实媒体校验链路由既有 `test_media_import_validation` 覆盖（本轮未改）。

## 待文档同步
`docs/stages/S11_配音与字幕.md` 本卡不改，以下句子待同步：IF-S11-20「页面按钮一律按对白音轨导入…页面未暴露用途选择」应改为「页面按钮经用途询问后按所选用途导入」；UX-S11-05 交互列应补「选文件后弹用途询问，默认对白」。

## 回滚
`git revert` 本轮提交。
