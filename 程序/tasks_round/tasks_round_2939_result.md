# R2939 结果：T10 包化——orchestrator/（L3 编排层）第三批 14 个低扇出服务模块迁移
<!-- round-evidence: {"commit_base": "0581308b", "credential_hits": 0, "evidence_sha256": "9196e612a80efe09", "exit": 0, "failed": 0, "passed": 1061, "round": 2939, "tests": "run_selftests.py -k direct_api image_direct dispatch send_ledger send_steps auto_batch batch_execution asset_batch previs startup exit_maintenance coordinator broadcast image_agent pet_ui local_previs auto_flows idea_chat writing_page"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁复测 **470/470 全绿**（首轮 3 红全部定位修复后二轮一遍过）；定向两轮共 42 个测试文件 **1062 条用例 0 红**；覆盖率基线重测 **516 模块／70 覆盖**。
3. **欠账少了吗**：是。T10 包化推进 orchestrator 第三批：`orchestrator/` 实体由 27 → 41 个，顶层 L3 实体剩约 34 个。剩余 L3 重枢纽（stage_execution_service、writing_api、skill_orchestrator、stage_config、stage_parallel、workflow_settings、skill_registry、project_context_factory、stage_models、stage_flow、engine 等）、L4 大模块（desktop/pet_ui/ui_widgets/app）与 `app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 14 个 L3 模块 `git mv` 入 `orchestrator/`：audio_direct_api、video_prompt_direct_api、image_direct、storyboard_direct_api（直接派发四件套互为骨架复用）、agent_dispatch、desktop_send_ledger、asset_auto_batch_service、asset_batch_execution、previs_batch_service、previs_monitor、desktop_startup_service、exit_maintenance、pet_chat_coordinator、pet_broadcast_state。入选口径：`_layers.py` 登记 L3、实体仍在顶层（排除已是门面的）、静态+动态扇出最低；扇出见下表。 |
| 别名门面 ×14 | 顶层同名 `.py` 为 `sys.modules[__name__] = orchestrator.<名>` 别名门面。**注意**：`package_migrate.py` 生成的是名单再导出门面（`from pkg.mod import (...)`），与 R2921/R2935/R2937 的别名门面不同；本轮已按既有口径统一改写为别名形态（私有名、模块级状态、`mock.patch` 扁平补丁面一致），14/14 `ALL ALIAS OK`。 |
| 消费方 import | 19 个生产文件改包路径导入：desktop 及 desktop_* 页面族（audio_direct/image_direct/storyboard_direct/video_prompt_direct/auto_flows/lifecycle/send_choice/idea_chat）、asset_batch、local_previs、previs_automation、pet_ui、image_agent_runner（留顶层、仅改 import）；包内交叉引用同步改 `orchestrator.*`（`import orchestrator.storyboard_direct_api as _base` 保绑定名）。 |
| `__file__` 根锚 | `orchestrator/storyboard_direct_api.py` 7 处 `program=Path(__file__).resolve().parent` → `.parents[1]`（model_pool 程序根）；`orchestrator/desktop_send_ledger.py` `PROGRAM` 常量同法。沿用 `domain/idea_transcript.py` 既有口径。 |
| 显式排除 | `image_agent_runner.py` **不迁**：含 `if __name__=='__main__'` 子进程入口（`task_instruction` 拼 `python <本文件>` 跑批），实体入包后子进程 `sys.path[0]` 变 `orchestrator/`、扁平 `agent.core` 导入与门面不跑 `__main__` 块都会破功能；留待 agent/ 家族专项轮处理。 |
| 动态字符串引用 | 5 处人工核对均安全：`contract/artifact_schema.py:35` 与 `desktop_send_ledger.py:41/193` 的 `'desktop_send_ledger'` 是**产物契约 kind 键**（非模块导入）；`ui_plugin_registry.py:10` 的 `'agent_dispatch'` 走 `import_module` 由扁平门面解析。 |
| 边界测试包感知 | 4 个读源码的架构测试改 `entity_file()`：test_asset_batch_ledger_boundary（asset_batch_execution）、test_previs_batch_json_boundary、test_previs_monitor_json_boundary、test_project_entry_boundary（desktop_startup_service）；语义断言原样。basename 键登记表（complexity/print/token ratchet）按 `registry_key`/`path.name` 口径天然兼容，未改。 |
| 棘轮台账 | `架构统一基数.json` 两条 point 条目路径改 `orchestrator/`（storyboard_direct_api `_extract_json`、asset_auto_batch_service `retired:`）；**一条例外**：asset_batch_execution 的**层级豁免**条目 `file` 沿用 basename 口径 `asset_batch_execution.py` 不改——`_upward_pairs()` 与该节 ledger 均以 `registry_key` 归一，改包路径反而制造「台账项不可定位」红。 |
| 基线与文档 | `覆盖率基线.json` 重测 **516 模块／70 覆盖**（502+14 实体）；`runbook.md` §11 同步（516/70/446）；`architecture.md` orchestrator 目录树 27→41（三批）；`PROJECT_MAP.md` 1 处实体路径同步；`distribution_manifest.md` `程序/orchestrator/**` glob 已覆盖无需改。 |

## 扇出明细（选批依据）

静态+动态扇出（生产文件计数，含包内）：desktop_startup_service 1、exit_maintenance 1、image_direct 1、pet_chat_coordinator 1、pet_broadcast_state 1、storyboard_plan_service 1（留待下批）、agent_dispatch 2、desktop_send_ledger 2、asset_auto_batch_service 2、audio_direct_api 2、codex_skill_sync 2、previs_batch_service 2、previs_monitor 2、qwen_adapter 2、skill_notes 2、skill_templates 2、storyboard_recycle_service 2、video_prompt_direct_api 2、asset_batch_execution 3、desktop_auto_state 3、stage_download_inbox_service 3、storyboard_direct_api 5、previs_automation 5（留待下批，含 ui_plugin_registry 动态登记）。本批取扇出≤5 的连贯低扇出集；`image_agent_runner`（3）因 `__main__` 子进程问题显式排除。

## 验证记录

- `smoke_test.py`（主工作区解释器）：8/8 通过。
- `smoke_test.py --architecture`：首轮 3 红（runbook 基线数字未同步、层级豁免台账 file 口径误改、同源）→ 修复后 **470/470 全绿**（当轮实测二轮）。
- 定向一：`run_selftests.py -k direct_api image_direct dispatch send_ledger send_steps auto_batch batch_execution asset_batch previs startup exit_maintenance coordinator broadcast image_agent` → 32 文件 **275 条 0 红**。
- 定向二（消费方族补充）：`-k pet_ui local_previs auto_flows idea_chat writing_page` → 10 文件 **787 条 0 红**。
- 导入冒烟：14 个 `orchestrator.*` 实体 + 14 个扁平门面全部可导入，别名一致（`ALL ALIAS OK`），无循环导入。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行）。

## 过程损耗（如实）

- 功能工作树环境补齐：`维护记录/基准历史.json`（gitignored，从主工作区复制）、4 个人工检出的技能子模块（无 `.gitmodules` 映射，按钉住 commit 从主工作区整体复制：reference/HoLLMwood、AIGC创作全流程、剧本锻造、编剧技能集）；`skill_package_pins.py --check` 3 包 0 问题。
- `package_migrate.py` 门面形态与既有别名口径不一致（名单再导出 vs sys.modules 别名），本轮手工统一为别名；**教训**：搬家后须核对门面形态，名单门面会丢私有名补丁面。
- `架构统一基数.json` 分节口径不同：point 条目 `file` 用 relpath（包路径），层级豁免条目 `file` 用 `registry_key`（basename）；首轮把豁免条目也改成包路径导致 `_upward_pairs` 对不上，已回退 basename。
- 首轮架构 3 红＝1 个文档数字滞后（runbook 502 vs 基线 516）＋2 个同一台账口径误改；均最小修复。

## 下一步（T10 后续批次）

- 剩余 L3 实体 34 个。下一批低扇出候选（扇出≤6，约 16 个）：storyboard_plan_service(1)、codex_skill_sync(2)、qwen_adapter(2)、skill_notes(2)、skill_templates(2)、storyboard_recycle_service(2)、stage_download_inbox_service(3)、desktop_auto_state(3)、idea_semantic_brief_service(4)、stage_handler_registry(4)、writing_unconfirm(4)、previs_automation(5)、edit_habits(5)、legacy_compat(5)、skill_budget(5)、skill_orchestrator(5)、workflow_tasks(6)、desktop_automation_service(6)。
- 中扇出（9–14）：stage_completion_service、workflow_engines、writing_api、stage_models、stage_flow。
- 重枢纽（15+）：skill_registry(16)、stage_parallel(18)、project_context_factory(18)、stage_config(18)、storyboard_selection(27)、workflow_settings(28)、engine(31)、stage_execution_service(50)——建议「一枢纽＋私有簇」分批，先做依赖分析再动。
- `image_agent_runner`（扇出 3）因 `__main__` 子进程入口＋`agent.core` 导入面，随 agent/ 包族专项处理，不走普通搬家批次。
- L4 大模块 desktop/pet_ui/ui_widgets/app 与顶层前缀族（pet_*、asset_*、stage_*、script_*、storyboard_* 等）逐批同法迁移。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
