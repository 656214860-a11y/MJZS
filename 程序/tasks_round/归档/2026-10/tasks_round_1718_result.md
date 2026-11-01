# R1718：验证基线轮——S13 质检与交付补 20 条需求测试锚点（REQ-S13）

- 轮次类型：验证/基线轮（§3.10，补需求锚点、只动测试资产与基线登记）。
- 未领号、未提交、未改 `project_status.md`、未触碰任何生产代码与 UI 批次／client_profiles／workflow_settings。
- 改动文件（仅此两个）：
  - `程序/tests/test_req_s13_anchors.py`（新建，docstring 含「REQ-S13 测试锚定」）
  - `程序/维护记录/需求锚定基线.json`（仅从 `untested_done` 删除本轮锚定的 20 个 S13 编号）
- `程序/docs/REQUIREMENTS.md`：未改（20 条全部真的满足，无需降 🟡）。
- 无新增 skip，`维护记录/skip台账.json` 未触碰。测试不依赖 Tk，也不打开真实用户项目（全部 `tempfile.mkdtemp()`）。

## 逐条对照（锚点测试 → 断言 ↔ 需求原文）

| 编号 | 锚点测试 | 对应断言 → 需求原文 | 结论 |
| --- | --- | --- | --- |
| REQ-S13-02 | `test_req_s13_02_scope_binds_adopted_storyboard_with_shots` | `media_scope` 未选定／无镜头分别 `assertRaisesRegex('选择当前已采用的分镜')`、`assertRaisesRegex('没有可核验的镜头')`；改 shots 后 `completion_evidence` 为假 →「未选定或没有可核验镜头时报错，不产生成果确认。切集或改分镜使旧确认失效」 | 锚定 |
| REQ-S13-03 | `test_req_s13_03_missing_ffprobe_errors_not_suffix_passthrough` | `config.json` 无 `ffprobe` 且补丁 `tool_path→None` 时 `assertRaisesRegex('FFprobe')`，且无清单 →「缺失时直接报错，不退化为按扩展名放行」 | 锚定 |
| REQ-S13-10 | `test_req_s13_10_delivery_page_buttons_match_the_manual_flow` | `desktop_media_pages.py` 含「导入剪映最终成片／校验并确认本阶段成果／生成商用待填资料／核验商用交付资料」→「导入最终成片→校验并确认本阶段成果→生成商用待填资料→人工填写后核验商用交付资料，页面按钮与此一致」 | 锚定 |
| REQ-S13-12 | `test_req_s13_12_probe_freezes_pending_review_and_never_autocompletes` | `prepared['status']=='pending_review'` 且 `completion_evidence` 为假；纯音频流／时长 0 抛错；探测期间改文件 `assertRaisesRegex('校验期间')` →「必须有真实视频流、有限且大于零的时长；校验期间文件变化则失败；结果冻结为 pending_review 清单，导入或探测成功不会自动完成阶段」 | 锚定 |
| REQ-S13-13 | `test_req_s13_13_output_must_be_nonempty_media_in_delivery_dir` | `.srt`／`.zip`／空 `.mp4`／项目外文件均抛错 →「必须位于本项目交付目录内、非空；字幕或压缩包不能替代媒体」 | 锚定 |
| REQ-S13-14 | `test_req_s13_14_only_explicit_confirmation_writes_complete_and_pending` | 确认后 `status=='complete'`、`reviewed is True`、`commercial_status=='pending'`；确认前改文件再确认抛错 →「只有显式人工确认才写入…并带 commercial_status='pending'。确认前重新核对冻结版本」 | 锚定 |
| REQ-S13-20 | `test_req_s13_20_completion_is_the_frozen_confirmation_manifest` | `target==media_manifest_path`、父目录 `成果确认`、`schema/stage/scope` 与当前一致、`completion_evidence` 为真；篡改 size 后为假 →「阶段完成＝存在成果确认清单…schema、阶段、范围一致，已 complete 且 reviewed，成片大小与 SHA256 与清单一致」（模型文字／界面提示不作证据＝只认清单） | 锚定 |
| REQ-S13-21 | `test_req_s13_21_media_or_storyboard_change_invalidates_completion` | 同尺寸改内容→假；改分镜 shots→假；切集→假 →「成果文件被替换或修改、分镜版本变化后，完成判定失效，须重新校验确认」 | 锚定 |
| REQ-S13-22 | `test_req_s13_22_emit_verified_completion_gates_stage_completed` | 未确认时 emit 未被调用；确认后仅发出 `stage.completed`（stage=delivery）→「完成判定走 emit_verified_completion：核验通过才发 stage.completed」 | 锚定 |
| REQ-S13-23 | `test_req_s13_23_completion_does_not_depend_on_commercial_evidence` | `commercial_delivery_status` 为假、`validate_commercial_evidence({})` 抛错时 `completion_evidence` 仍为真 →「完成判定不依赖商用资料：商用核验通过与否不影响阶段是否完成」 | 锚定 |
| REQ-S13-30 | `test_req_s13_30_commercial_template_requires_confirmation_and_refuses_overwrite` | 未确认时 `create_commercial_template` 抛错且无 `.pending` 文件；确认后生成 `.commercial.pending.json`；再次调用 `assertRaisesRegex('已存在')` →「生成商用待填资料需先有已确认成果；已存在的待填文件拒绝覆盖，保护已填内容」 | 锚定 |
| REQ-S13-31 | `test_req_s13_31_template_prefills_sources_without_granting_rights` | `edit_bundle.json` 的 manifest/fonts 与成片、剧本被预填（script=1、video=2、font=1）；每项 `commercial_allowed/derivative_allowed/obligations_fulfilled` 为假、`rights_holder/license` 空、`authorization=={'path':'','sha256':''}`；warnings 含「来源版本已改变」「缺少路径」 → 需求原文 | 锚定 |
| REQ-S13-33 | `test_req_s13_33_every_item_needs_rights_and_a_frozen_authorization_file` | 合法资料通过；`source/rights_holder/license` 置空、`commercial_allowed/derivative_allowed/obligations_fulfilled` 置假 → `assertRaisesRegex('授权范围或履约记录不完整')`；授权文件空路径／越出项目抛错；授权摘要篡改 → `assertRaisesRegex('摘要不一致')` →「每个素材条目须有来源、权利人、许可、可商用、可衍生、义务已履行，并附本项目内授权文件（路径＋SHA256 一致）」 | 锚定 |
| REQ-S13-34 | `test_req_s13_34_inventory_covers_actual_script_and_delivery` ＋ `test_req_s13_34_inventory_covers_shot_reference_font_versions` | 剧本未覆盖→`'剧本授权清单'`；视频类为空→`'缺少素材'`；成片被替换件顶替→`'未覆盖实际交付成片'`；edit_bundle 镜头来源未覆盖→`'镜头来源'`；参考→`'参考授权'`；字体→`'字体授权'` →「清单须覆盖当前分镜的实际剧本来源、全部交付成片，以及 edit_bundle.json 中登记的镜头来源、参考来源、字体版本；覆盖不全即报错」 | 锚定 |
| REQ-S13-35 | `test_req_s13_35_content_review_and_reviewer_confirmation` | 侵权／NSFW／敏感 三项 status≠cleared 或 reviewer／evidence 空 → `assertRaisesRegex('内容风险未完成审核')`；`inventory_complete=False` 或 `inventory_reviewer` 空 → `assertRaisesRegex('需由审核人确认清单覆盖')` → 需求原文 | 锚定 |
| REQ-S13-36 | `test_req_s13_36_commercial_evidence_binds_master_and_storyboard` | scope 不符→`'不属于当前采用分镜版本'`；outputs 不符→`'对应成片已改变'`；改分镜后 validate 抛错；合法资料确认后 `commercial_delivery_status` 文案含「依据人工」 →「商用资料绑定成片摘要和分镜版本，成片变化后须重新审查。程序只核验声明、摘要和人工记录…界面文案据此说'依据人工记录'」 | 锚定 |
| REQ-S13-40 | `test_req_s13_40_usage_is_unknown_not_zero_and_blocked_not_counted` | `total.calls==2`（`not_submitted` 不计远端调用）、`unknown_usage==1`、`total_tokens==7`（无用量不记 0）、`not_submitted==1` → 需求原文 | 锚定 |
| REQ-S13-41 | `test_req_s13_41_denominator_uses_confirmed_delivery_only` ＋ `test_req_s13_41_one_export_per_adopted_storyboard` | `delivery_duration==2.5`（取已确认成片）；空／重复／目录外文件抛错；无 `delivery_outputs` 时文案含「尚未绑定交付证据」；同集两份导出 → `assertRaisesRegex('多个导出')` → 需求原文 | 锚定 |
| REQ-S13-42 | `test_req_s13_42_missing_cost_items_stay_separate_and_never_zero_filled` | 缺项时 `total_per_minute is None`、`missing_overheads=={gpu,storage,bandwidth}`、`basis=='recorded_usage_estimate_not_supplier_invoice'`；未关联台账的 Comfy 任务单列于 `untracked_comfy` →「成本缺项…单列，总成本只在录入项齐全时给出，绝不补零；结果标注为按录入用量估算，非供应商账单」 | 锚定 |
| REQ-S13-43 | `test_req_s13_43_human_cost_and_time_are_separate_and_unknown_when_absent` | 无人工项时 `human_amount/human_per_minute/human_minutes/including_human_per_minute` 皆为 `None`；给出人工金额与耗时后 `human_per_minute==2`、`human_minutes==15`、`including_human_per_minute==4` →「人工费用与人工耗时单列，缺失显示未知；含人工全成本仅在其余项齐全且人工金额已填时给出」 | 锚定 |

结论：20 条全部「锚定」，无一条降 🟡（无「代码不满足需求」的情况，故删除的测试为空）。

## 命令实际计数

1. `python -B -m unittest tests.test_req_s13_anchors tests.architecture.test_requirement_traceability`（PYTHONPATH 含 `tests`）
   → `Ran 26 tests … OK`，**0 红**（新文件 22 条 + 门禁 4 条）。
2. `python -B run_selftests.py -k test_req_s13`
   → `22 条用例，3.4 秒；0 个文件有红`，`ALL TESTS PASSED`。

## 需裁决事项

- `tests/architecture/test_round_baselines.py::test_full_safe_all_is_required_after_eight_source_rounds` 当前红：本工作树 `content_tree()` 为空（未提交脏树、`last_full_safe_all_round=1693`、当前 R1715 欠一次完整安全全量），无匹配绿凭据。**与本轮文件集无关**，属项目既有全量欠账，由 master 的 post-commit 后台补跑；本轮按任务书不跑全量、不做任何 git 写操作，故未处理。
- 工作树中另有他人改动（`client_profiles`／`workflow_settings`／UI 批次文件／`skip台账.json` 等），非本轮产生，未触碰。

摘要：20/20 条 S13 需求已用真实断言锚定并全部通过（无降级），基线已删除对应 20 个编号；`unittest` 26 条 0 红、`run_selftests -k test_req_s13` 22 条 0 红。

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 定向 `-k test_req_s13_anchors requirement_traceability`：26 条 0 红。
- `smoke_test.py --architecture`：368/368 OK（含需求追溯门禁，基线只减不增）。
- 审查备注：REQ-S13-10 的锚点是检查源码字符串（页面按钮文案），属弱锚点；按新规应改为真 Tk 量控件，留待 UI 视觉契约批次处理。
- 不改生产代码，未新增 skip。
