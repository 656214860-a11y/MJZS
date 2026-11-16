# R2945 结果：T10 包化——orchestrator/（L3 编排层）第四批 18 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "4cf25601", "credential_hits": 0, "evidence_sha256": "884fa89b8d5c5edc", "exit": 0, "failed": 0, "passed": 92, "round": 2945, "tests": "run_selftests.py -k storyboard_plan_service codex_skill_sync qwen_adapter skill_notes skill_templates storyboard_recycle_service stage_download_inbox_service desktop_auto_state idea_semantic_brief_service stage_handler_registry writing_unconfirm previs_automation edit_habits legacy_compat skill_budget skill_orchestrator workflow_tasks desktop_automation_service"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁当轮复测 **470/470 全绿**；定向 `--affected`（18 模块全消费方）93 个测试文件 **1978 条用例**，唯一红项 `test_skills`（2 条）系工作树技能子模块复制缺层，修复目录结构后复跑 **127/127 绿**；覆盖率基线重测 **534 模块／71 覆盖**。
3. **欠账少了吗**：是。T10 包化推进 orchestrator 第四批：`orchestrator/` 实体由 41 → 59 个，顶层 L3 实体剩约 16 个（中扇出 5＋重枢纽 8＋`image_agent_runner` 等显式排除项）。剩余重枢纽（skill_registry、stage_parallel、project_context_factory、stage_config、storyboard_selection、workflow_settings、engine、stage_execution_service）与 L4 大模块、`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 18 个 L3 模块 `git mv` 入 `orchestrator/`：storyboard_plan_service、codex_skill_sync、qwen_adapter、skill_notes、skill_templates、storyboard_recycle_service、stage_download_inbox_service、desktop_auto_state、idea_semantic_brief_service、stage_handler_registry、writing_unconfirm、previs_automation、edit_habits、legacy_compat、skill_budget、skill_orchestrator、workflow_tasks、desktop_automation_service。入选口径：`_layers.py` 登记 L3、实体仍在顶层（排除已是门面的）、静态+动态扇出 ≤6 且无 `__main__` 入口（18/18 核验 `__main__=0`）；即 R2939 结果文件「下一步」列出的低扇出候选全集。 |
| 别名门面 ×18 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = orchestrator.<名>` 别名门面（沿用 R2937/R2939 口径：私有名、模块级状态、`mock.patch` 扁平补丁面一致）；18/18 `ALL ALIAS OK`，`ui_plugin_registry.module('previs_automation')` 动态路径实测返回实体本体。 |
| 消费方 import | 34 个生产文件改包路径导入：desktop 及 desktop_* 页面族（auto_flows/automation_tick/direct_dispatch/idea_chat/lifecycle/media_pages/pet_bridge/script_edit_session/script_pages/send_choice/writing_page/writing_snapshots）、engine、local_previs、pet_models_ui/pet_settings_ui/pet_ui/pet_ui_stages/pet_ui_support、skill_panel/skill_panel_support、stage_execution_service、storyboard_files、workflow_engines、workflow_settings、writing_api、edit_habits_dialog、domain/confirm_gates、domain/idea_document_paths（后两者为既有 L2→L3 引用，仅改路径）；包内交叉引用同步改 `orchestrator.*` 并保绑定名（`import orchestrator.skill_orchestrator as skill_orchestrator` 等）。全库扫描：18 个扁平名在生产代码中残留静态导入 **0 处**。 |
| `__file__` 根锚 | 5 处 `Path(__file__).resolve().parent` → `.parents[1]`：orchestrator/skill_notes.py、skill_templates.py、edit_habits.py、skill_budget.py 的 `PROGRAM`／模板根；orchestrator/previs_automation.py 的 `previs_progress.py` 辅助脚本查找改程序根。同 R2939 口径。 |
| 包内交叉 import | orchestrator/stage_handler_registry.py `from storyboard_plan_service import storyboard_work_plan` → `orchestrator.storyboard_plan_service`；orchestrator/stage_exec.py、storyboard_direct_api.py、storyboard_page_controller.py、skill_orchestrator.py 同法。 |
| 动态字符串引用 | R2939 干跑报告的 15 处命中逐个人工分类：`ui_plugin_registry.py:13` 的 `'previs_automation'` 与 `local_previs.py:266/285` 的 `module('previs_automation')` 是**真实运行时插件引用**——由扁平别名门面解析，实测 `ui_plugin_registry.module('previs_automation') is sys.modules['previs_automation']`，无需改；`artifact_schema.py` 的 `'edit_habits'`/`'desktop_automation_service'` 是产物 owner/kind 键、`legacy_compat.py` 清单串是兼容元数据、`skill_notes.py` 串是数据/owner 标识，均非导入路径，保持原样。 |
| 边界测试包感知 | 6 个架构测试改 `entity_file()` 或等价解析，不再读顶层薄门面：test_previs_automation_json_boundary、test_skill_orchestrator_json_boundary（读实体源码断言 JSON 边界）、test_writing_api_stage_config_boundary、test_project_context_boundary、test_model_provider_boundary（`entity_file(name)` 取径）；test_legacy_facade_manifest 增 `_is_legacy_compat()` 归一 `legacy_compat`/`orchestrator.legacy_compat` 两种写法并把 `__module__` 断言改 `legacy_compat.__name__`，清单语义不变。test_qwen_adapter 改 `entity_file('qwen_adapter')` 并把续写脚本断言同步为 `from orchestrator.qwen_adapter import submit_existing`（生成代码的真实新形态）。test_copy_rules 的 PROMPT_FILES 登记 `orchestrator/workflow_tasks.py`。语义断言原样。 |
| 棘轮台账 | `架构统一基数.json` 第四项 point 条目 ×5 的 `file` 改 `orchestrator/` 包路径（desktop_automation_service、previs_automation、qwen_adapter、skill_notes、edit_habits）；层级豁免条目沿用 basename/`registry_key` 口径未动（沿用 R2939 教训）。`_layers.py` 扁平登记名与 `registry_key` 归一天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **534 模块／71 覆盖**（516+18 门面实体口径，门面本身计入生产模块集，与既有批次一致）；`runbook.md` §11 同步（534/71/463）；`architecture.md` orchestrator 目录树 41→59（四批）；`PROJECT_MAP.md` 4 处实体路径同步；`smoke_test.py` 检查项路径 `程序\workflow_tasks.py` → `程序\orchestrator\workflow_tasks.py`；`distribution_manifest.md` `程序/orchestrator/**` glob 已覆盖无需改。 |

## 扇出明细（选批依据）

即 R2939 结果文件「下一步」预告的低扇出候选全集（扇出 ≤6）：storyboard_plan_service(1)、codex_skill_sync(2)、qwen_adapter(2)、skill_notes(2)、skill_templates(2)、storyboard_recycle_service(2)、stage_download_inbox_service(3)、desktop_auto_state(3)、idea_semantic_brief_service(4)、stage_handler_registry(4)、writing_unconfirm(4)、previs_automation(5)、edit_habits(5)、legacy_compat(5)、skill_budget(5)、skill_orchestrator(5)、workflow_tasks(6)、desktop_automation_service(6)。18/18 均为 `_layers.py` 登记 L3、顶层实体、无 `__main__` 守卫；`image_agent_runner`(3) 仍因 `__main__` 子进程入口显式排除，留待 agent/ 家族专项。

## 验证记录

- `smoke_test.py`（主工作区解释器）：8/8 通过。
- `smoke_test.py --architecture`：首轮 4 红（覆盖率基线未刷新 ×3、技能参考文件缺失 ×1）→ 全部定位修复后复测 **470/470 全绿**（当轮实测二轮）。
- 定向：`smoke_test.py --affected <18 模块名>` → run_selftests `--serial -k <别名+直接消费方>`，**93 个测试文件 1978 条用例**，唯一红 `test_skills`（2 条，技能注册表计数 71≠73，系工作树技能子模块目录多套一层所致，见过程损耗）→ 修复后 `run_selftests.py -k test_skills` 复跑 **127/127 绿**；其余 92 文件首轮即全绿。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入，目标用例全通过；`test_coverage_baseline` 5/5 绿。
- 导入冒烟：18 个 `orchestrator.*` 实体 + 18 个扁平门面全部可导入且对象同一（`ALL ALIAS OK`），`ui_plugin_registry.module('previs_automation')` 返回实体本体；生产侧 18 扁平名静态导入残留 0。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行；本轮为结构搬迁，未触发启动路径/Tk 生命周期/删除语义新增风险）。

## 过程损耗（如实）

- **工作树技能子模块复制缺层**：上一会话为补工作树环境从主工作区复制的 4 个人工检出目录（`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`、`reference/HoLLMwood`）全部多套了一层同名目录（内容在 `<名>/<名>/` 下），导致 `test_skill_reference_injection` 缺 `screenplay-gate-engine.md`、`test_skills` 注册表计数 71≠73。已逐一把内层内容上移一层修正；修复后 `skills/`、`reference/` 与主工作区逐文件比对 0 缺失。**教训**：跨树复制含 `.git` 的检出目录时须核对目标层级，`rglob` 计数类测试能兜住此类错误。
- **领号误操作**：本轮在主工作区误跑 `round_claim.py next`，将 R2948 误记到 master 名下；核对 `round-claims.json` 后手工移除该条归属（计数器由 claims 推导，无独立 last_claimed 受损），R2948 号位已释放可再领。功能轮 R2945 归属本工作树 `codex/wip-t10svc2` 不受影响。
- **覆盖率口径**：`production_runtime_files()` 递归口径含顶层门面文件，18 个新门面使模块集 516→534（门面 4 行壳亦计模块），`modules_covered` 70→71（`desktop_automation_service.py` 门面 4/4 全覆盖）；基线按工具实测重写，`runbook.md` §11 数字同步。
- **测试契约微调**：`test_legacy_facade_manifest` 需识别 `orchestrator.legacy_compat` 包路径写法（`_is_legacy_compat` 归一）；`test_qwen_adapter` 断言生成的续写脚本 import 语句同步为包路径——均为定位/导入路径适配，断言语义未动，已在本文件注明。

## 下一步（T10 后续批次）

- 剩余 L3 实体约 16 个。中扇出（9–14）候选：stage_completion_service、workflow_engines、writing_api、stage_models、stage_flow。
- 重枢纽（15+）：skill_registry(16)、stage_parallel(18)、project_context_factory(18)、stage_config(18)、storyboard_selection(27)、workflow_settings(28)、engine(31)、stage_execution_service(50)——建议「一枢纽＋私有簇」分批，先做依赖分析再动。
- `image_agent_runner`（扇出 3）因 `__main__` 子进程入口＋`agent.core` 导入面，随 agent/ 包族专项处理，不走普通搬家批次。
- L4 大模块 desktop/pet_ui/ui_widgets/app 与顶层前缀族（pet_*、asset_*、stage_*、script_*、storyboard_* 等）逐批同法迁移。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
