# R3085 结果：T10 包化——ui/（L4 界面层）第三批 24 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "aea2955a", "credential_hits": 0, "evidence_sha256": "91785f4df98fd690", "exit": 0, "failed": 0, "passed": 238, "round": 3085, "tests": "run_selftests.py -k asset_reference_search asset_skill_batch cloud_assets_dialog desktop_account_page desktop_async_tasks desktop_automation_tick desktop_layout_resize desktop_lifecycle desktop_page_support desktop_script_edit_session desktop_send_choice desktop_tk_gc desktop_voice_input desktop_writing_snapshots pet_agent_rules skill_note_render skill_panel_workflow speech_settings_ui stage_model_picker ui_scroll video_navigation video_prompt_results white_model_ref workflow_agents keyframe_comfy white_model desktop_idea_chat account_security task_center button_consistency dialog_boundary ui_icons_boundary video_prompt_publication confirm_gates_json read_json_definitions button_boundary card_boundary complexity_ratchet"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k` 定向 27 文件 238 条（首轮 2 文件红＝门面形态回归，修复后复跑 28 条全绿）；`smoke_test.py --architecture` 架构门禁结果见验证记录；覆盖率基线重测 674 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **ui/ L4 第三批**：`ui/` 实体由 57 → 81 个（含 `__init__.py` 共 82 文件）。L4 顶层剩余约 57 个实体继续分批；L3 仅剩 `writing_api`（拆分批）、`stage_execution_service`（扇出 50 单独一轮）、`image_agent_runner`（子进程入口永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 24 个低扇出（入度 0–2）顶层 L4 模块 `git mv` 入 `ui/`：asset_reference_search、asset_skill_batch、cloud_assets_dialog、desktop_account_page、desktop_async_tasks、desktop_automation_tick、desktop_layout_resize、desktop_lifecycle、desktop_page_support、desktop_script_edit_session、desktop_send_choice、desktop_tk_gc、desktop_voice_input、desktop_writing_snapshots、pet_agent_rules、skill_note_render、skill_panel_workflow、speech_settings_ui、stage_model_picker、ui_scroll、video_navigation、video_prompt_results、white_model_ref、workflow_agents。 |
| 别名门面 ×24 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面（domain.projects 体例，含 mock.patch 补丁面说明 docstring）；`import <扁平名> is ui.<名>` 实体同一校验通过。 |
| 消费方 import | 24 个生产文件改包路径导入（含批内边 `desktop_automation_tick→desktop_account_page/desktop_tk_gc`、`ui/asset_batch→asset_skill_batch`、`ui/native_assets→cloud_assets_dialog` 等）；AST 复扫残留 1 处单行懒加载 `from desktop_send_choice import choose`（desktop_idea_chat.py:947）手工补改，复扫 **0 处**。`ui_plugin_registry` 扁平键表（asset_skill_batch/desktop_voice_input）按既有口径不动，`module()` 经门面解析。 |
| 动态串 ×3 | `keyframe_comfy.py` `import_module('workflow_agents')` ×2 → `'ui.workflow_agents'`；`white_model.py` `import_module('white_model_ref')` → `'ui.white_model_ref'`。`ui_plugin_registry.module('…')` 扁平键 ×3 处为注册表键，保持扁平。 |
| 日志名冻结 ×3 | `desktop_lifecycle`/`desktop_script_edit_session`/`desktop_send_choice` 的 `logging.getLogger(__name__)` → 字面量扁平名（`__name__` 入包后变 `ui.*`，按 domain 先例冻结）。 |
| `__file__`/`__main__` | 本批 24 模块锚点扫描 **0 命中**（`shot_numbering`/`keyframe_import`/`desktop_tray`/`environment_check`/`desktop_shared_send`/`skill_panel_import` 有锚点或 `__main__`，均未入本批，留后续批次单独处理）。 |
| 测试取径 ×8 | 直读门面源码改 `entity_file()`：`test_dialog_boundary`（cloud_assets_dialog）、`test_ui_icons_boundary`（video_navigation，补 _scan 导入）、`test_video_navigation_json_boundary`、`test_video_prompt_publication_boundary`、`test_confirm_gates_json_boundary`（desktop.py＋desktop_automation_tick 双源拼接）、`test_account_security`（desktop_automation_tick，补 _scan 导入）、`test_task_center`（desktop_async_tasks）；`test_read_json_definitions` REGISTERED `'video_navigation.py'` → `'ui/video_navigation.py'`（relpath 口径）。`test_complexity_ratchet`/`test_button_boundary`/`test_card_boundary`/`test_button_consistency`/`test_static_names`/`_scan.DESKTOP_PARTS` 均已包感知或按 basename 键，零改动。 |
| 冒烟源路径 ×1 | `smoke_test.py` `程序\white_model_ref.py` 文件/关键词检查 ×3 → `程序\ui\white_model_ref.py`（同 R3058 `orchestrator\workflow_settings.py` 先例）；`import` 检查项经门面不变。 |
| 棘轮台账 | `架构统一基数.json` 本批 24 模块精确名零命中；`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **674 模块／74 覆盖**（650+24，97 条目标用例全过）；`runbook.md` §11 同步（674/74/600）；`architecture.md` ui 目录树「三批共 57 个」→「四批共 81 个」；`distribution_manifest.md` `程序/ui/**` glob 已覆盖；`PROJECT_MAP.md` ×6 处路径改 `ui/` 前缀（ui_scroll/desktop_page_support/desktop_script_edit_session/skill_panel_workflow/desktop_voice_input/speech_settings_ui）。 |

## 验证记录

- `smoke_test.py`（随附解释器）：首轮 7/8（white_model_ref 源路径检查命中门面）→ 修路径后 **8/8 通过**。
- `run_selftests.py -k <本批 24 模块＋keyframe_comfy/white_model/desktop_idea_chat 消费方＋account_security/task_center/button_consistency/dialog_boundary/ui_icons_boundary/video_prompt_publication/confirm_gates_json/read_json_definitions/button_boundary/card_boundary/complexity_ratchet 测试面>`：27 文件 **238 条用例／81.1s／2 文件红**——`test_asset_skill_batch` 与 `test_white_model_ref` 各 1 条，均为 **`mock.patch.object(扁平门面,'read'/'SUPPORT')` 补丁面失效**：本批门面初生成时为 `package_migrate.py` 默认显式再导出形态（`from ui.X import (名…)`），补丁落在门面命名空间、实体全局不受影响；按 domain.projects 先例把 24 个门面整体改写为 `sys.modules` 别名后复跑 **28 条全绿**。其余 25 文件首轮全绿（含全部取径修复的架构测试）。
- `smoke_test.py --architecture`：首轮 **3 红**——`test_round_number_continuous`（状态页轮次头 3083 陈旧，临时同步 3086 后复测绿，未提交）、`test_todo_comment_snapshot`（`ui/desktop_async_tasks.py` 扫描序后移致快照条目乱序，快照 JSON 按扫描序重排，断言与 reviewed 内容不变）、`test_unification_ratchet` 第四项（`video_prompt_results.py` → `ui/` relpath，台账 3 条 exempt 前缀更新）；修复后三轮 **471/471 全绿（155.7s）**。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过，674/74）。
- 未跑：`--all --safe` 全量；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3085**（3083/3084 被并行车道占用）；新建 `codex/wip-R3085` 分支叠加在 `codex/wip-R3082`（aea2955a）之上承接本批。
- **门面形态回归（本轮唯一实质返工）**：`scripts/package_migrate.py` 现产出显式再导出门面（`from ui.X import (…)`，为满足 `test_no_star_imports` 禁 `import *` 的早期折中），但 R3021 起 domain/orchestrator/ui 各批实际统一采用 `sys.modules` 别名门面——`import <扁平名>` 直接返回实体本体，`mock.patch`/`patch.object` 补丁面、私有名与模块级状态与包内路径完全一致。本批首跑即被 `test_asset_skill_batch`/`test_white_model_ref` 两处补丁面测试抓出；已把 24 个门面改写为别名体例。**教训：package_migrate 产物必须与既有门面体例（sys.modules 别名）对齐后再提交；后续批次应先统一修工具或批量转正。**
- **台账/快照 relpath 与扫描序**：`架构统一基数.json` 第四项 exempt 条目 `video_prompt_results.py` → `ui/video_prompt_results.py`（×3，同 R3024/R3043 先例）；`TODO注释快照_20261003.json` 条目按 `module_scan_files()` 新序重排（`ui/` 实体排在顶层文件之后），快照内容与处置结论零改动。
- **`dep_scan_tmp.json`/`head_py_tmp.txt` 等诊断临时文件**：已删，不入提交。
- **覆盖率基线模块数**：R3082 基线 650 → 本批实测 674（+24，与迁移数一致；基线工具权威口径）。

## 下一步（T10 后续批次）

- L4 剩余约 57 个顶层实体继续分批；本批排除的锚点/`__main__` 模块（desktop_tray、environment_check、keyframe_import、shot_numbering、desktop_shared_send、skill_panel_import）需逐个评估锚点修复或留待专轮。
- L3 收官：`stage_execution_service`（扇出 50）单独一轮；`writing_api` 随拆分；`image_agent_runner` 永久除外。
- `app.py`/`desktop.py`/`pet_cloud.py`/`pet_ui_*`/`ui_widgets`/`ui_theme`/`desktop_shared_input`/`storyboard_files`/`keyframe_comfy`/`desktop_idea_chat` 等大模块随批推进或拆分。
- 门面清除轮需单独授权。
