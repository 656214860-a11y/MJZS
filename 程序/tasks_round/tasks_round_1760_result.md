# R1760：修复轮——交接包选版口径对齐成片，并补强完成清单链路锚点（BATCH2）

- **轮次类型**：§3.2 修复轮。S12-15 是代码偏离需求（修生产代码），S11-04 是测试锚点不足（只补测试，不改生产）。
- **测了吗 / 三基线**：
  - 默认冒烟 `python -B smoke_test.py`：8/8 通过。
  - 架构门禁：`test_requirement_traceability`＋`test_layers` 10/10 通过；另加 `test_handoff_publication_boundary` 共 14/14 通过。
  - 全量回归与欠账：本轮未跑 `run_selftests.py`／`--all --safe`／`--architecture`（任务书明确不跑），留待调度方验收；未用历史凭据冒充本轮结果。
- **欠账少了吗**：REQ-S12-15、REQ-S11-04 两条已按任务书闭环并补锚点；`project_status.md` 按派发约定未改，状态页欠账由提交方回收。

## 一、REQ-S12-15：交接包选版对齐成片

**根因**：`desktop_media_pages.py::MediaPagesMixin.handoff` 另写了一套选版规则
`(approved_versions(vs) or vs)[-1]`：不看 `pinned`、不核文件存在与 sha256，无已验收版时退回未验收版；
而自动粗剪／成片走 `engine.adopted_edit_version(versions, root)`，于是锁定旧版、文件被替换、无验收版三种情况下两边选出的镜头不同。

**改动**（仅 `desktop_media_pages.py`）：
- 顶部 import 改为 `from engine import adopted_edit_version, adoption_summary, review_label`（`approved_versions` 在本文件已无其它消费者）。
- `MediaPagesMixin.handoff` 逐镜改为 `v,_reason=adopted_edit_version(st['shots'].get(s['id']),self.root)`；`v is None` 的镜头不进 `rows`。打包、发布、校验、手动／自动入口、字幕仅在全部镜头进包时附带的逻辑均未改。
- 文档：`docs/stages/S12_后期剪辑.md` 的 `REQ-S12-15` 改 ✅ 并改写为现状（去掉行号与“待改”口吻）；`DES-S12-14` 并入同一选版口径（未新造重复 DES）；测试锚定表原 `REQ-S12-15/24/34` 行只去掉 15，其余未动。
- 锚点追加在 `tests/test_req_s12_anchors.py`，四条测试 docstring 均写 `REQ-S12-15`。

**V1–V6 实测**：
- V1 pinned 优先：`test_req_s12_15_handoff_uses_pinned_approved_version` 通过；断言交接包选中 v1，且与 `adopted_edit_version([v1,v2],root)[0]` 同一对象。
- V2 无 pinned 取最后已验收版：`test_req_s12_15_handoff_without_pin_uses_last_approved_version` 通过，同时与 `adopted_edit_version` 同一对象。
- V3 只有未验收版：`test_req_s12_15_handoff_skips_shot_without_approved_version` 通过；只有 SH002 进包、`subtitle is None`，并断言 SH001 的采用原因确为 `ADOPT_UNAPPROVED`。
- V4 文件被替换／缺失：`test_req_s12_15_handoff_skips_missing_or_replaced_adopted_file` 通过；SH001（sha 不符）、SH002（文件删除）均不进包，仅 SH003 进包，并分别断言 `ADOPT_REPLACED`／`ADOPT_MISSING`。
- V5 先红＋变异：见下节。
- V6 文档：见上节，已改。

**V5 先红证据**（改生产代码前运行 `tests.test_req_s12_anchors`）：
`Ran 7 tests ... FAILED (failures=3)`，恰为 V1/V3/V4：
- pinned 用例：`[2] != [1]`（旧逻辑取了更新版）；
- 未验收用例：`['SH001','SH002'] != ['SH002']`（旧逻辑把未验收版塞进包）；
- 替换／缺失用例：`['SH001','SH002','SH003'] != ['SH003']`（旧逻辑不核文件）。
V2 在改前即通过，符合“回归保护”预期。

**变异验证**：临时把 `handoff` 回退为旧选版表达式（即时内联 `approved or vs`，不改 import），复跑该文件得 `Ran 7 tests ... FAILED (failures=3)`，仍是上述三条；还原后文件 SHA256 与改前一致（`CB387D5B…F7710`），复跑 7/7 通过。工作树无临时残留。

## 二、REQ-S11-04：补齐完成清单链路锚点（不改生产）

**根因**：不是代码缺陷，是测试锚点不足。既有覆盖散在：
- `test_stage_completion_service.py`：字幕单独不算完成、pending_review 需人工确认、分镜改动／切集失效、文件替换失效、无有效流拒绝等；
- `test_critical_chains.py`／`test_audio_role_binding.py`：只有非对白音频不能完成、BGM 不能代替对白；
- `test_audio_subtitle_scope.py`：可接受扩展名。
缺口是“清单存在但 `status`／`reviewed` 不合格”没有显式失败断言，且 S11 锚点文件未逐条锚定上述可判定行为。

**改动**（仅测试与文档）：
- `tests/test_req_s11_anchors.py` 新增 `ReqS11MediaCompletionAnchorTests` 五条，docstring 均写 `REQ-S11-04`：
  1. 只有字幕、无确认清单 → `completion_evidence` 为假（并给出“校验＋确认后才为真”的对照）；
  2. 清单 `status=pending_review` 或 `reviewed=False` → 均为假，恢复原清单后才真；
  3. 采用版分镜内容改动（sha256 变化）→ 旧清单失效，且旧 prepared 不能再确认；
  4. 成果音频被替换 → 旧清单失效；恢复原字节后重新有效（证明看摘要而非时间戳）；
  5. 只有 BGM（非对白）→ `prepare_media_completion` 当场拒绝且不生成待审清单；对白文件才进入 `pending_review`。
- 用 `patch('agent.media.probe')` 桩与临时项目，沿用既有测试做法，无新增外部依赖、不建 Tk 窗口、不碰真实项目。
- 文档：`docs/stages/S11_配音与字幕.md` 的 `REQ-S11-04` 去掉 🟡 改 ✅，改写“仅锚定扩展名／本批未逐条核对”为现状并列出锚点测试名；测试锚定表第 93 行同步。

**变异验证**：临时把 `_validate_media_completion` 的条件改成只查 `status`（跳过 `reviewed is not True`），复跑 S11 锚点得 `Ran 6 tests ... FAILED (failures=1)`，失败断言为 `AssertionError: True is not false : reviewed=False 必须判为未完成`；还原后 `stage_completion_service.py` SHA256 与改前一致（`7AB9C87D…6ED0`），复跑 6/6 通过；`git status` 中该生产文件无改动。

## 三、既有测试预期同步（逐条）

只改了一处既有测试，属于有意行为变化的预期同步，非弱化：

- `tests/test_ui_edges.py::UiEdgeTests.test_handoff_prefers_approved_take`
  - 删除旧断言 `assertEqual((out2/'001_SH001.mp4').read_bytes(), b'unapproved-take')`：旧行为“无已验收版时退回最新未验收版”已被 REQ-S12-15 明确废止。
  - 新增 `assertRaisesRegex(ValueError, '没有已下载视频')`：单镜且全无采用版时如实报错。
  - 在第二次 `d.handoff()` 前恢复 `take_v1`，保留原 `assertNotEqual(out, out2)`（手动整理仍一事一目录）。
  - 其余断言未动；未新增 skip、未删除测试、未弱化任何通过条件。

**断言未动声明**：除上述 `test_handoff_prefers_approved_take` 的旧行为预期外，本轮未修改、弱化、跳过任何既有断言；新增测试均为行为断言，不检验源码字符串。

## 四、验证命令与结果（实际执行）

解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`；消费方测试统一设 `PYTHONPATH=tests`。

- 锚点：`tests.test_req_s12_anchors` 7/7；`tests.test_req_s11_anchors` 6/6。
- 任务指定消费方（`grep -ln "handoff|adopted_edit_version|approved_versions" tests/*.py` 命中 17 个文件，逐个单文件）：
  `test_app_metadata` 5/5、`test_editing_scope` 15/15、`test_edit_adoption` 9/9、`test_handoff_bundle` 9/9、`test_handoff_service` 7/7、`test_integration` 27/27、`test_pet_ui` 599/599、`test_req_anchor_s10` 15/15、`test_root_layout` 1/1、`test_storage` 17/17、`test_ui_edges` 115/115、`test_version_pin` 3/3、`test_video_generation_scope` 19/19、`test_workflow` 98/98、`test_req_s12_anchors` 7/7、`test_req_s11_anchors` 6/6、`test_idea_chat` 见下“非本轮失败”。
- S11 相关：`test_stage_completion_service` 32/32、`test_critical_chains` 17/17、`test_audio_role_binding` 18/18、`test_delivery_scope` 18/18、`test_audio_subtitle_scope` 16/16。
- 架构：`tests.architecture.test_requirement_traceability`＋`test_layers` 10/10；加 `test_handoff_publication_boundary` 共 14/14；`--find REQ-S12-15` 与 `--find REQ-S11-04` 均能列出新锚点。
- 冒烟：`python -B smoke_test.py` 8/8。

**命令计数**：unittest 模块运行 37 次（含先红、变异、复跑、HEAD 基线），smoke 1 次，架构门禁 3 批，`--find` 2 条，HEAD 临时导出基线 1 次。

## 五、需裁决事项

1. **非本轮引入的既有失败**（未修，超出允许文件）：
   - `tests/test_idea_chat.py`：本树 4 failures＋4 errors（集中在气泡编辑 `_bubble_edit` 未建立、附件树行为），与 handoff 选版无关。用 `git archive HEAD 程序` 临时导出 HEAD 复跑，同名失败仍出现（且因导出树缺运行数据，失败更多：7F/19E），可确认非本轮改动引入。
   - `tests/test_desktop_automation_service.py`：16 errors，均为测试替身缺 `cancel_resize`；HEAD 临时导出复跑同样 16 errors，确认既有失败。
   - 这两个文件被任务书的 grep 命中（字符串含 `handoff`／`auto_handoff`），但不是本轮改动的消费者；是否另开修复轮由调度方裁决。
2. **全部镜头都无采用版时的手动整理**：现在 `handoff()` 会因 `rows` 为空报“当前项目没有已下载视频”，不再产出含未验收版的半成品包。这是 V3 要求的直接结果；若产品希望此时仍产出“空壳包”，需要另立需求。
3. **全量／`--architecture`／`--affected` 未跑**：按任务书禁止项执行，未用历史绿凭据替代；请调度方在验收树复跑。
4. **`test_idea_chat` 的 grep 命中**来自 `handoff` 字面（如 `.agent-handoff` 相关断言），不是交接包功能；记录以免后续误判为消费者。

## 独立验收（Claude，车道 lane_b2 内直接运行，真实环境）

- 范围：1 个生产文件（desktop_media_pages.handoff 选版）、2 份 docs/stages（S11／S12）、3 个测试文件（两个锚点文件追加，test_ui_edges 一处预期同步）。
- 锚点与消费方：S12 锚点 7/7、S11 锚点 6/6；handoff_service、handoff_bundle、edit_adoption、version_pin、editing_scope、stage_completion_service、critical_chains、audio_role_binding、delivery_scope、req_anchor_s10、storage、integration、workflow、app_metadata、root_layout、video_generation_scope、audio_subtitle_scope 逐个全绿（带 PYTHONPATH=tests）；test_ui_edges 115/115。
- 门禁：`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 变异：回退 handoff 生产改动，S12 锚点 3 项变红（V1／V3／V4），还原后 sha256 一致；把 stage_completion_service 的 reviewed／status 判定短路，S11 的 reviewed 用例变红，还原后 sha256 一致。
- 既有失败（非本轮引入，执行方在 HEAD 导出树复跑已确认）：test_idea_chat、test_desktop_automation_service，未处理，留待另开修复轮。
- 未跑：`run_selftests` 全量与 `--all --safe`（本轮不属触发条件）。
