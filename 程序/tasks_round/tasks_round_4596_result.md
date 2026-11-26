# R4596 轮次结果（S04-W1：默认文字分镜卡、静音容错、音频回收与单镜审核闭环）
<!-- round-evidence: {"commit_base": "ce76e22d3", "credential_hits": 0, "evidence_sha256": "dbba527eba9be84a", "exit": 0, "failed": 0, "passed": 132, "round": 4596, "tests": "run_selftests.py -k animatic_sketch_backends animatic_audio animatic_timeline animatic_references animatic_service copy_rules"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（执行《分镜预演工作台与管理预览审核改造任务书》卡 `S04-W1`，落地 `REQ-S04-114`／`REQ-S04-115` 与 `DES-S04-37`／`DES-S04-38`）。
- **测试跑了吗、三个基线过了吗**：已运行——定向＋核心架构门禁 11 组（`test_animatic_sketch_backends`、`test_animatic_audio`、`test_animatic_timeline`、`test_animatic_references`、`test_animatic_service`、`test_copy_rules`、`test_layer_relations`、`test_module_size_ratchet`、`test_requirement_traceability`、`test_static_names`、`test_static_hygiene`）158/158 通过（49.23s）；默认冒烟 `smoke_test.py` 9/9 通过（含隐藏桌面探针）；`smoke_test.py --affected animatic_timeline` 10/10 通过（27/27 用例，10s）；全量安全回归留待任务书收尾或合并轮按口径执行。
- **欠账少了吗**：`REQ-S04-114`／`REQ-S04-115` 与 `DES-S04-37`／`DES-S04-38` 翻绿为 ✅ 并完成测试锚定；4 个 L2 模块保持零新增同层导入边（LR-03）；`stage_execution_service.py` 保持 980/1000（净增 0 行）、`orchestrator/stage_animatic_gateways.py` 880/1000，全部严守 1000 行棘轮红线，零新增欠账。

## 改动清单

- `程序/domain/animatic_sketch_backends.py`：将 `DEFAULT_BACKEND` 由 `'comfy_local'` 改为 `'text_card'`；显式注册 `'comfy_local'` 保持原有 `comfy_local`/`gflow_cli` 行为不变。
- `程序/domain/animatic_audio.py`：`plan(shots, *, full_track=None, music=None, use_tts=True)` 新增 `use_tts` 开关；无整轨且 `use_tts is False` 时直接返回 `{'mode': 'silent', 'full_track': None, 'music': bgm, 'tts_shots': []}`。
- `程序/domain/animatic_timeline.py`：新增 `REVIEW_STATES = ('pending', 'approved', 'needs_revision')` 并纳入 `_CARRIED` 与 `_new_row`；新增 `review_status_of(row)`、`set_review_status(timeline, shot_id, status)`、`needs_revision_ids(timeline)`、`filter_shots(timeline, board, *, scene='', status='')`。
- `程序/domain/animatic_references.py`：抽取共享内部优先级与去重收集器 `_pick_shot_refs`，新增 `shot_ref_badges(shot, lib, *, formal_assets=None)`，与 `refs_for_shot` 严格同优先级同去重顺序，返回五类来源徽章（`S05 资产`／`角色`／`场景`／`风格`／`未分类`），零新增 L2 同层边。
- `程序/orchestrator/stage_animatic_gateways.py`：
  - 修正 `_timeline_render` 与 `_ensure_comfy_ready` 改为显式比对 `'comfy_local'`（避免默认 `text_card` 误探测 ComfyUI）。
  - `_timeline_audio` 读取 `settings.get('animatic_use_tts', True)` 传给 `animatic_audio.plan`，并在逐镜 TTS 失败时抛出可读中文错误提示可在「声音」关闭逐镜 TTS 先静音出片或配置语音。
  - 新增 `remove_animatic_audio(project, track)`（仅允许 `'track'`｜`'music'`，经 `storage_maintenance.recycle_paths` 移入回收站）。
  - 扩展 `update_animatic_shot(..., review_status=None)`；新增 `regenerate_revision_shots(project, *, settings=None)` 与 `shot_ref_details(project, shot)`。
  - `lock_animatic` 在回写 S03 前校验 `needs_revision_ids(timeline)`，非空时抛出拦截提示（含数量与前 6 镜号，≤45 字，遵守 `copy_rules`）。
- `程序/stage_execution_service.py`：在既有第 33 行 import 行合并转发 `regenerate_revision_shots`、`remove_animatic_audio`、`shot_ref_details`（净增 0 行，保持 980/1000）。
- `程序/docs/stages/S04_分镜预演.md`：`REQ-S04-114`／`115`、`DES-S04-37`／`38` 翻绿为 ✅，并回填测试锚定。
- `程序/tests/test_animatic_sketch_backends.py`、`test_animatic_audio.py`、`test_animatic_timeline.py`、`test_animatic_references.py`、`test_animatic_service.py`：补充 T1–T4 行为单测。

## 既有测试契约变更说明（AGENTS.md §2.4）

因用户 Q3 拍板（`REQ-S04-114`）将未保存偏好时的默认草图引擎由 `comfy_local` 修订为 `text_card`，同步以下依赖旧默认值的断言，未削弱原有 `comfy_local` 行为覆盖：
1. `程序/tests/test_animatic_sketch_backends.py`（`test_missing_settings_dispatch_to_comfy_local`）：改为断言 `DEFAULT_BACKEND == 'text_card'` 且缺省／空设置落到 `text_card`，同时在同一用例内保留显式 `'animatic_sketch_backend': 'comfy_local'` 分流断言。
2. `程序/tests/test_animatic_timeline.py`（`test_run_animatic_timeline_probes_and_opens_comfy_when_missing_images`、`test_run_animatic_timeline_skips_comfy_probe_when_client_injected`、`test_req_s04_83_regenerate_animatic_shot_reuses_ensure_comfy_ready`）：在测 ComfyUI 探测／注入客户端路径时显式传 `'animatic_sketch_backend': 'comfy_local'`，并新增 `test_req_s04_114_default_text_card_silent_and_tts_failure_hint` 验证默认不探测 ComfyUI。

## 先红后绿证据

改动生产代码前先更新上述 5 个测试文件并运行 `tests.test_animatic_sketch_backends tests.test_animatic_audio tests.test_animatic_timeline tests.test_animatic_references tests.test_animatic_service`，实测 **Ran 114 tests in 11.225s, FAILED (failures=1, errors=8)**：
- `test_missing_settings_dispatch_to_comfy_local`：`AssertionError: 'comfy_local' != 'text_card'`
- `test_req_s04_114_use_tts_false_returns_silent_without_tts_shots`：`TypeError: plan() got an unexpected keyword argument 'use_tts'`
- `test_req_s04_115_review_status_lifecycle_legacy_compat_and_rebuild`：`AttributeError: module 'domain.animatic_timeline' has no attribute 'REVIEW_STATES'`
- `test_req_s04_115_filter_shots_by_scene_and_status`：`AttributeError: module 'domain.animatic_timeline' has no attribute 'set_review_status'`
- `test_req_s04_114_default_text_card_silent_and_tts_failure_hint`、`test_req_s04_114_remove_animatic_audio_recycles_and_validates_track`、`test_req_s04_115_regenerate_revision_shots_resets_status_and_rejects_empty`：`ImportError`／行为不满足
- `test_req_s04_115_113_shot_ref_badges_and_gateway_details`：`ImportError: cannot import name 'shot_ref_badges'`
- `test_req_s04_115_lock_blocks_needs_revision_shots_without_touching_s03`：`TypeError: update_animatic_shot() got an unexpected keyword argument 'review_status'`

改动后 11 组定向＋架构 158/158 全绿、冒烟 9/9 全绿、`--affected animatic_timeline` 10/10 全绿。

## 提交状态

- 工作树：`D:\漫剧制作助手\.agents\worktrees\s04-workbench-spec`
- 分支：`codex/s04-workbench-spec`（未 `git push`）
- 提交方式：经 `scripts/dev.py commit` 提交。
