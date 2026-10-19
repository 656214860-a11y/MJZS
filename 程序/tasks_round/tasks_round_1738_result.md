# R1738：验证/基线轮——S12 后期剪辑补 12 条需求测试锚点（REQ12）

- 本轮类型：**§3.10 验证/基线轮**（只补需求测试锚点与基线登记，不改任何生产代码；非功能轮，无需先改文档）。
- 测试跑了吗／三个基线：跑了两条任务书命令，均 0 红（见下）。默认冒烟与全量安全回归**未运行**——本轮不改生产代码，任务书也未要求；架构门禁仅运行 `tests/architecture/test_requirement_traceability.py`（5 条，绿），未跑全量架构门禁。
- `project_status.md` 欠账：本任务不领号、不改状态页；`维护记录/需求锚定基线.json` 的欠账由 47 → 35（本轮 −12，均为 S12）。

## 结果表

| 编号 | 锚点测试 | 对应断言 → 需求原文 | 自证红的输出 | 结论 |
| --- | --- | --- | --- | --- |
| REQ-S12-05 | `tests/test_output_spec.py::EngineOutputSpecTests`（docstring 新增）、`OutputSpecContractTests.test_output_filter_pads_and_never_crops`（docstring 新增） | `test_studio_spec_reads_the_project_lock`：patch `stage_config.workflow_lock={'aspect_ratio':'9:16'}` 后 `studio.output_spec()` 得 (1080,1920)、`output_spec_text()` 得 `1080x1920 · 30fps · 9:16`；`test_output_filter_pads_and_never_crops`：滤镜含 `scale=…:force_original_aspect_ratio=decrease` 与 `pad=…`、且无 `crop` → 需求「输出规格…来自项目制作锁（workflow_lock → resolve_output_spec）…界面在导出前显示实际规格」「等比缩放＋居中留边，不裁切」 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-10 | `tests/test_req_s12_anchors.py::ReqS12AnchorTests.test_req_s12_10_reencode_each_shot_then_concat_copy_and_note_missing_audio`（新增） | 带音轨镜头 S01 编码命令含 `scale=1080:1920:force_original_aspect_ratio=decrease`、`pad=1080:1920:(ow-iw)/2:(oh-ih)/2`、`-ar 48000 -ac 2`、`-c:v libx264`、`-c:a aac`、`loudnorm=I=-16:TP=-1.5:LRA=11`；无音轨 S02 含 `anullsrc=channel_layout=stereo:sample_rate=48000`、无 `loudnorm`、且写出 `S02_音轨说明.json`（S01 不写）；合成命令含 `-c copy` → 需求全文 | 改反 `script_contract.loudness_filter`→`crop=iw:ih`：`AssertionError: 'loudnorm=I=-16:TP=-1.5:LRA=11' not found in 'ffmpeg -y -v error -i …'`（RED） | 锚定 |
| REQ-S12-11 | `tests/test_integration.py::PartialAssembleTests`（docstring 新增）、`tests/test_editing_page_controller.py`（两条用例 docstring 新增） | `test_partial_assemble_skips_unready_shots`：`skip_unready=True` 跳过 SH003 且 `report['included'/'expected'/'duration'/'skipped']` 正确；`test_partial_assemble_needs_at_least_one_shot`：报「没有可剪辑的镜头」；`test_strict_assemble_still_rejects_partial`：`skip_unready=False` 报 SH003 +「缺少已下载」；controller：`assembled_message` 输出「已包含 1/2 镜；总时长 8秒；已跳过…」 → 需求「以 skip_unready=True 跳过未就绪镜头，把跳过原因和『已包含 N/M 镜、总时长』写进状态栏；不跳过时…即报错；一镜都没有时报错」 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-12 | `tests/test_edit_service.py::AutomaticAssembleDecisionTests`、`AutomaticAssembleMarkerPublicationTests`（docstring 新增）、`tests/test_integration.py::AutoEditReadyTests`（docstring 新增） | `automatic_assemble_decision` 的 skip／wait／complete／dispatch；标记写入 `12后期剪辑/自动粗剪.json`；`AutoEditReadyTests`：整集就绪才给指纹且稳定、未验收→「尚未验收」等待、文件缺失→等待、重做并重新验收后指纹改变 → 需求「所有未删除镜头都有采用版本时才给出成片指纹；同一指纹只拼一次（标记 …/自动粗剪.json）；镜头重做并重新验收后才再拼一版；分镜未对齐、正在定稿时等待」 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-13 | `tests/test_edit_adoption.py::EditBundleTests.test_bundle_records_the_actual_overlay_font_digest`（docstring 新增） | 带 `post_overlay` 的镜头 → `bundle['fonts'] == [{'path':'font.ttc','sha256':…}]` → 需求「唯一的画面叠加是镜头自带的 post_overlay 文字（用系统微软雅黑，字体副本与摘要进 bundle）」；转场／背景音乐属 REQ-S12-33（既有 `test_editing_scope` 覆盖） | 已有测试，未单独改反 | 锚定 |
| REQ-S12-14 | `tests/test_handoff_bundle.py::ManifestBuildTests`、`OfflineVerifyTests`（docstring 新增）、`tests/test_handoff_service.py::AutomaticDecisionTests`、`AutomaticMarkerPublicationTests`（docstring 新增） | manifest 含 `001_SH001.mp4`、`镜头顺序.json`、`导入剪映说明.txt`、文件 size/sha256；`shots` 如实标注 `included/expected/missing`（缺镜不补齐）；离线 `verify` 对缺失／改内容／改大小／越界／坏清单均如实报错；自动标记写 `12后期剪辑/自动交接.json` 且同一指纹只整理一次 → 需求全文 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-16 | `tests/test_edit_service.py::EditingChecklistPublicationTests`（docstring 新增） | 保存 → `12后期剪辑/剪辑优化清单.md` 内容一致；传空串 → 文件被清空 → 需求「由用户维护，可保存、可清空，位于 12后期剪辑/」；「写入经 L3 发布器、L2 无权自行放宽空正文」由既有 `tests/architecture/test_edit_publication_boundary.py::test_desktop_delegates_checklist_publication_to_l3`（`save_editing_checklist` 用 publish、无 save_text；L3 `allow_empty=True`）守护 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-21 | `tests/test_edit_adoption.py::EditBundleTests`（docstring 新增） | `bundle['master']/['master_sha256']/['manifest']`（镜头、版本、sha256、相对路径）/`['coverage']`、`edits.json.inputs` 与 `edit_manifest.json` 两索引；索引写失败仍能从 bundle 恢复；只有两索引时 `legacy` 读取 → 需求全文 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-22 | `tests/test_edit_export.py::PublishEditListsTests`（docstring 新增） | `publish_edit_lists` 返回 `ok=False` → `_encode` 抛 `ValueError('成片已保留…剪辑交付包不完整…')` 且 `MASTER.mp4` 保留；`save_text` 抛 OSError → 不删 master；三份清单写出 → 需求「EDL／FCPXML／分轨清单写失败时不删成片，如实报『剪辑交付包不完整』」；「先写临时文件 → `-xerror` 解码通过才替换」由既有 `test_encode_does_not_report_success_when_delivery_lists_fail` 与 `architecture/test_edit_publication_boundary.py::test_encode_uses_temporary_master_and_delegates_bundle_publication`（`temporary_path`/`replace`/`publish_edit_bundle`）共同守护 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-27 | `tests/test_req_s12_anchors.py::ReqS12AnchorTests.test_req_s12_27_recovery_hint_points_to_manual_editing_and_reviewed_stills`（新增） | `stage_flow.RECOVERY_HINTS['edit']` 含「剪辑软件」「人工剪辑」「静帧」「审核」「不当作」「AI视频」 → 需求「无可用成片时的手动出路：…改用剪辑软件人工剪辑；静帧替代镜头须明确审核，不当作 AI 视频成功」 | 改反 hint 为「改用剪辑软件人工剪辑。」：`AssertionError: '静帧' not found in '改用剪辑软件人工剪辑。'`（RED） | 锚定 |
| REQ-S12-35 | `tests/test_edit_export.py::EditExportTests`（docstring 新增） | EDL 首行 `TITLE:`、含 `FCM: NON-DROP FRAME` 且事件行时间码正确；`layout` 按帧累计 `[60,96,1]`、end=157（无漂移）；FCPXML well-formed、`frameDuration=1/24s`、`offset=60/24s`、`duration=157/24s`；`tracks`/`export_texts` 产出三文件 → 需求「EDL（CMX3600）、FCPXML、分轨素材清单，时间码非丢帧、按帧数累计防漂移」 | 已有测试，未单独改反 | 锚定 |
| REQ-S12-40 | `tests/test_req_s12_anchors.py::ReqS12AnchorTests.test_req_s12_40_edit_stage_never_synthesizes_dialogue_subtitles_or_drafts`（新增） | 未验收镜头严格拼装报 `ValueError(SH001…)`（不静默采用）；`handoff_service.publish_bundle(subtitle=None)` 产出的包无 `对白.srt`、清单 `subtitle=False`、无含「草稿」的文件、`导入剪映说明.txt` 含「不是剪映草稿」 → 需求「不生成或合成对白、配音、字幕；…不静默使用未验收版本；不生成剪映草稿」 | 改反 `engine.adopted_edit_version` 使其返回假版本：`ERROR: KeyError: 'file'`（RED） | 锚定 |

## 改动文件

- 新增：`tests/test_req_s12_anchors.py`（3 条新测试，文件 docstring 含「REQ-S12 测试锚定」）。
- 仅加 docstring（不动断言）：`tests/test_output_spec.py`、`tests/test_integration.py`、`tests/test_editing_page_controller.py`、`tests/test_edit_service.py`、`tests/test_edit_adoption.py`、`tests/test_edit_export.py`、`tests/test_handoff_bundle.py`、`tests/test_handoff_service.py`。
- `维护记录/需求锚定基线.json`：`untested_done` 删除 12 条 S12 编号（保持 `indent=2`、`ensure_ascii=False`、文件末尾换行）。
- 未改：`docs/stages/S12_后期剪辑.md`（无降级项，无需 ✅→🟡）；`维护记录/skip台账.json`（未新增 skip）；任何生产 `.py`（车道内实现保持原样）。
- 自证用的改反只在**临时副本脚本**（`%TEMP%\opencode\req12_red_proof.py`，仓外）里用 `unittest.mock.patch` 完成，未触碰车道代码。

## 验证命令与实际计数

1. `python -B -m unittest tests.test_req_s12_anchors tests.architecture.test_requirement_traceability`（PYTHONPATH=`.;tests`）→ **Ran 8 tests … OK**（新文件 3 条 + 门禁 5 条，0 红）。
2. `python -B run_selftests.py -k "test_output_spec test_integration test_editing_page_controller test_edit_service test_edit_adoption test_edit_export test_handoff_bundle test_handoff_service test_req_s12"` → **9 个测试文件 / 87 条用例 / 17.3 秒；0 个文件有红；ALL TESTS PASSED（exit=0）**；无本机登记跳过（实际跳过 0 条）。
3. 锚点查询 `tests/architecture/test_requirement_traceability.py --find REQ-S12-nn`：12 条编号均能定位到上表测试。
4. 基线文件校验：`trailing_newline=True`、`ensure_ascii=False`、`json.dumps(..., indent=2, ensure_ascii=False)` 往返一致、S12 残留 `[]`。

## 需裁决事项

1. `docs/stages/S12_后期剪辑.md` 的 `## 测试锚定` 表仍写着旧状态（如「REQ-S12-05 暂无断言」「REQ-S12-10/11 → test_integration」，以及 05/10/12/14/16/21/22/27/35/40 的归属）。本任务只授权在该文件做第 2 条的 ✅→🟡，无降级项，故未改表；表与现状已不一致，是否下一轮同步。
2. 若严格按任务书「先红后绿只针对新测试」，表中 9 条走「已有测试加 docstring」的锚点未单独改反自证；其对应生产逻辑若被删／改反，相应既有断言即红（对应关系见上表）。如需逐条改反自证，请下指令。
3. REQ-S12-35「不臆造剪映草稿格式」与 REQ-S12-40 的若干否定句（不查询云端任务、不改上游验收记录等）属负向声明，测试以「不产出该物／不静默采用」的可观察行为锚定，未对不存在的行为单独造断言。

## 独立验收（Claude，主工作区）

- 逐条核对已有测试的 docstring 锚点：均挂在直接断言该需求行为的测试上，只改 docstring。
- 主树 `test_req_s12_anchors`＋门禁 OK；8 个相关测试文件定向 0 红。
- 裁决：`S12_后期剪辑.md` 的「测试锚定」表与现状不一致——记为后续文档同步项，本轮不动。
