# R1720：验证基线轮——S08 首帧管理补 17 条需求测试锚点（REQ-S08）

- 轮次类型：§3.10 验证/基线轮（只补测试锚点与基线，不改生产代码）。
- 允许范围内实际改动：`程序/tests/test_req_s08_anchors.py`（新建，19 条用例）；`程序/维护记录/需求锚定基线.json`（只删 S08 的 17 个编号，106 → 89）。
- 未改：任何生产代码（`程序/*.py` 非 tests）、`docs/REQUIREMENTS.md`、已有测试文件、`维护记录/skip台账.json`、`project_status.md`。工作树里其它文件的改动属并行 S04／S06／UI 执行者，非本任务。
- 结论：17 条全部**锚定**，无一条降 🟡（新测试全绿，代码满足需求）。

## 逐条对照

| 编号 | 锚点测试 | 断言 → 需求原文 | 结论 |
| --- | --- | --- | --- |
| REQ-S08-11 | `test_req_s08_11_frame_size_must_match_aspect_lock_and_expected_size` | 16:9 图对 9:16 画幅锁：`frames_ready` 不通过且 problems 含「画幅」；换 9:16 且 `expected_size` 一致→通过；`expected_size=(16,9)` 对 9:16 图 `make_evidence` 抛「尺寸」 →「尺寸必须符合项目画幅锁和记录的期望尺寸」 | 锚定 |
| REQ-S08-12 | `test_req_s08_12_three_modes_target_only_shots_without_a_frame` | `BATCH_MODES` 三值；只补缺失 targets＝['SH002']（SH001 已有、SH003 已删）；另一集 SH900 不进；三模式下已成功镜头 targets 空；仅 replace 点名 SH001 才进且 note 含「覆盖」 →「三种模式…只处理没有首帧的镜头；已成功永不重复；本集之外不进计划」 | 锚定 |
| REQ-S08-13 | `test_req_s08_13_deleted_never_revived_and_unbuildable_shots_reported` | 三模式下已删除镜头 targets 空、skipped 原因含「已删除」＋首帧管理页标签；未配置／空文件／越界分别给出「未配置／空文件／越界」 →「已删除…任何模式都不复活；空文件、未配置路径、越界列为不可生成并给原因」 | 锚定 |
| REQ-S08-14 | `test_req_s08_14_uncertain_and_unusable_done_are_reported_not_resubmitted` | uncertain 不进「只补缺失」targets、原因含「重试失败／结果待核实」；retry note 含「结果待核实」；attempt=completed 但文件不可用 → note 含「记录称已完成，但首帧文件不可用」 →「结果不确定标结果待核实不自动重提；记录称完成但文件不可用同样报告」 | 锚定 |
| REQ-S08-15 | `test_req_s08_15_frame_prompt_prefers_frame_then_keyframe_never_video` | `frame_prompt` 优先、缺则 `keyframe_prompt`、仅 `video_prompt` → ''；`first_frame_prompt` 可用 →「取 frame_prompt，缺失退到关键帧提示词；不得用视频提示词代替」 | 锚定 |
| REQ-S08-16 | `test_req_s08_16_manual_import_rejects_bad_input_and_keeps_old_on_failure` | 分镜已改／编号非法／非 PNG → `register` 抛 `ValueError`；保存失败时源 JSON 字节不变、已发布 PNG 仍在（无半成品） →「分镜已被修改、镜头号非法、非 PNG 都拒绝；关联失败保留旧来源与已发布首帧」 | 锚定 |
| REQ-S08-17 | `test_req_s08_17_late_result_is_not_adopted_when_the_source_changed` | 镜头签名变 → 抛错、不写 `frame_evidence`、生成图保留；来源内容（整集／提示词／资产）变 → 抛「分镜或参考资产」 →「结果迟到时来源分镜已变化则不采用」 | 锚定 |
| REQ-S08-18 | `test_req_s08_18_stage_config_is_the_only_model_source` | `production_choices` 含两个原生模型；`stage_config.put('keyframe', model=…)` 分别设 Seedream／本地 → `current_model` 随之 →「模型以阶段配置 `keyframe.model` 为唯一来源；可选模型始终含两个原生模型」 | 锚定 |
| REQ-S08-19 | `test_req_s08_19_paid_generation_needs_confirmation_and_same_shot_serial` | `skill_templates.load_template('keyframe')` 第 3 步 `action=='generate_keyframes'` 且 `needs_confirmation`；`skill_registry` 的 keyframe paid 含三个生成 SKILL；`Governor` 对同一镜头 SH001 第二次 acquire 不 ok →「有付费生成动作、须用户确认（第 3 步）；受并行配置约束，同一镜头不并发」 | 锚定 |
| REQ-S08-20 | `test_req_s08_20_evidence_records_image_facts_and_source_versions` | `evidence.image.sha256`＝文件哈希、记 (w,h)；`source.shot_id/storyboard_sha256/prompt_sha256` 齐全；引用资产 `sha256`＝reference.png 哈希、`metadata` 非空；改提示词后 `prompt_sha256` 变 →「记录图片事实＋来源分镜／提示词／参考资产版本哈希」 | 锚定 |
| REQ-S08-21 | `test_req_s08_21_review_reasons_are_distinct_and_never_silently_pass` | 缺证据「缺少来源」、外部替换（mtime 不变）「外部替换」、来源变化「来源」、资产缺版本「缺少可核对版本」，四条均含「重新」 →「原因分明…都要重新导入复核，不静默通过」 | 锚定 |
| REQ-S08-22 | `test_req_s08_22_one_shots_asset_change_only_invalidates_its_own_frame` | 改 CHAR_001 图片后：引用它的 SH001 出现「来源」，未引用的 SH002 仍为 '' →「一个镜头的参考资产变化只影响引用它的镜头」 | 锚定 |
| REQ-S08-23 | `test_req_s08_23_delete_restore_replace_go_through_recycle`／`…_failed_delete_rolls_back_frame_and_state`／`…_failed_replace_rolls_back_previous_frame` | 删除→文件进`工作流任务/回收站`且 `frame_deleted`；恢复清标记；替换旧图进回收站且新图＝`png()`；发布失败时删除回滚（原图在、无 `frame_deleted`）、替换回滚（仍为原字节） →「删除走回收站可恢复；删除/恢复/替换事务化回滚；替换把旧版本放回收站」 | 锚定 |
| REQ-S08-24 | `test_req_s08_24_frames_dir_is_numbered_and_legacy_is_read_only` | `write_dir=='08首帧管理'`；`read_dirs` 含 `07首帧管理`；旧目录有成果时 `existing_dir` 只读回退，但 `write_dir` 仍不含 07 →「写入 08首帧管理/；旧目录 07首帧管理 只读兼容，不回写」 | 锚定 |
| REQ-S08-30 | `test_req_s08_30_completion_needs_frames_ready_and_a_started_stage` | 未开始（无帧、`has_run` False）：`frames_ready` ok 但 `started` False→`completion_evidence` False；已开始且证据齐全→ completion True；文件损坏→ not ok／False →「完成＝frames_ready 通过且本阶段已开始；界面提示不算证据」 | 锚定 |
| REQ-S08-31 | `test_req_s08_31_sg04_blocks_previs_when_keyframe_frames_are_bad` | `evaluate(root,'previs').id=='SG-04'`、ok False、problems 含「未配置首帧路径」、`blocked_stages==('keyframe',)`、`blocked_text` 含「首帧管理」；空项目放行 →「SG-04：本阶段已开始但缺帧／校验不过则阻塞白模预演并说明原因」 | 锚定 |
| REQ-S08-32 | `test_req_s08_32_video_skips_shots_without_a_frame_and_points_to_keyframe` | `local_video.auto_plan`：缺帧的 SH002 不进 `submit`（不进空图顶替），进 `skipped` 且原因含「尚无首帧」＋`pet_bus.stage_step('keyframe')`（第08步，指向首帧管理页） →「视频侧遇到缺首帧的镜头拒绝／跳过并给出原因、指向首帧管理页」 | 锚定（见裁决 1） |

## 命令实际计数

1. `PYTHONPATH=tests;. python -B -m unittest tests.test_req_s08_anchors tests.architecture.test_requirement_traceability`
   → `Ran 23 tests`（19 条新锚点 ＋ 4 条门禁），`OK`，0 红，退出码 0。
2. `PYTHONPATH=tests;. python -B run_selftests.py -k test_req_s08`
   → `1 个测试文件 / 19 条用例 / 0 红 / ALL TESTS PASSED`，退出码 0。
3. `python -B tests/architecture/test_requirement_traceability.py --find REQ-S08-xx`
   → 例如 REQ-S08-11／19／32 均只命中小节 `KeyframeRequirementAnchorTests.test_req_s08_xx_*`。
4. 基线核对：`untested_done` 106 → 89，仅 S08 的 17 个编号被删，`REQ-S08-*` 已无剩余；JSON 仍 `indent=2`、中文不转义。

## 需裁决 / 说明

1. **REQ-S08-32 的「视频生成」云端分支**：云端拒绝入口 `app.py: ensure_frame` 是 Tk 页面方法，本任务按「能不用 Tk 就不用」不做 Tk 用例；本锚点覆盖本地渲染跳过与「指向首帧管理页」文案。云端分支另有既有 Tk 用例（`tests/test_ui_edges.py` 中「尚无首帧」断言）覆盖。若要求该条也显式锚定云端分支，请裁决是否允许加 Tk 用例并登记 `skip台账.json`。
2. **基线末尾换行**：git 原 blob 以 `}` 结尾、无末尾换行；本次按任务书“保持原有 JSON 格式”保留原样（未按“末尾换行”字面添加），以免出现超出“只删 S08 编号”的差异。如需补末尾换行请裁决。
3. 未新增任何 skip；全部锚点无需 Tk，`维护记录/skip台账.json` 未改动。
4. 无 `✅ → 🟡`：17 条新测试全绿，未触碰 `docs/REQUIREMENTS.md` S08 节。

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 定向 `-k test_req_s08 requirement_traceability`：23 条 0 红。
- `smoke_test.py --architecture`：368/368 OK。
- 基线 diff 只删 S08 的 17 个编号；抽查新测试无源码字符串锚点（两处 read_text 读的是 JSON 数据）。
- 不改生产代码，未新增 skip。
