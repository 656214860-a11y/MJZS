# R2862 功能轮结果：任务书轮 1/5——删总控机制、制作锁扁平化、阶段配置面板精简
<!-- round-evidence: {"commit_base": "f4afbe32", "credential_hits": 0, "evidence_sha256": "a317e3f5d8fbd76c", "exit": 0, "failed": 0, "passed": 1150, "round": 2862, "tests": "run_selftests.py -k skill stage_config stage_model_value stage_execution_service workflow idea production_lock stage_command stage_prompt scope manual_plan button_consistency release_bindings req_s script_agent stage_notes"} -->

- 轮次类型：功能轮（§3.1，用户任务书《共享输入框与skill体系重构任务书》轮 1）。
- 任务书：`程序/tasks_round/共享输入框与skill体系重构任务书.md`（已随本提交入库）。
- 轮次归属：`round_claim.py record 2862` 补登本工作树（分支 `codex/wip-R2862`）；领号时误在主工作树跑 `next` 产生的 2875 幽灵归属已移除，计数器不动。

## 改动

- 删除总控机制：`skills/00全流程SKILL/总控.json`、`master_skill.py`、`master_import_service.py`、`master_skill_update.py`、`desktop_master_update.py`、`skill_panel_presets.py`、`scripts/migrate_workflow_presets.py` 及三个总控测试文件、`test_workflow_migration.py`。
- `workflow_settings.py`：移除 `MASTER_MANIFEST`/`WORKFLOW_PRESETS`/`master_gate`/总控同步体检与 workflow-skill 提示注入；`resolve_for_send` 冻结入口保留。
- 制作锁扁平化：项目 `skill_config.json` 顶层 `production_locks` 为唯一新写入口（`stage_config.put_production_locks`）；`stage_model_value.production_locks()`（L1）为唯一读取口，缺扁平锁时回退旧 `workflow.lock.<总控名>` 并归一中文标签；`stage_config.workflow_lock()` 委托 L1 读取；`stage_execution_service.save_writing_production_locks()` 经 L3 发布器把扁平锁与简报锁投影同包落盘。
- `idea_chat.receive_brief()` 改从 L1 `stage_model_value.production_locks()` 取锁（消除 L2→L3 反向依赖，架构门禁通过）。
- `skill_panel.py`/`skill_panel_workflow.py`：面板只留 skill 勾选＋技能说明；制作锁入口改为弹窗预选（`skill_panel_workflow` 重写为锁弹窗助手，含附件派生锁同步与写失败报错）；模型选择移出面板，由 `stage_model_picker.StageModelPicker` 承接。
- `desktop.py`/`desktop_automation_tick.py`/`selftest_env.py`/`desktop_idea_chat.py`/`desktop_idea_send_gate.py`/`idea_chat.py`/`stage_handler_registry.py`/`workflow_engines.py`：摘除总控更新、预设应用与 master 模式链路；13 阶段顺序、`stage_parallel`、`confirm_gates`、`stage_completion_service` 行为不动。
- 文档同步：`AGENTS.md`、`architecture.md`、`PROJECT_MAP.md`、`runbook.md`、`docs/stages/S01_剧本准备.md` 改为「内置层＋用户导入层 skill 注册表＋项目级扁平制作锁」口径，删除总控权威源条款。
- 架构登记：`tests/architecture/_layers.py` 等分层/棘轮登记同步；`test_complexity_ratchet.py` 下调 `desktop_idea_chat.py::IdeaChatMixin` 过期上限；统一基数/类型检查/覆盖率/skip 台账按实际改动刷新（skip 台账保留 indent=2 原格式，diff 最小化）。
- 测试改写（契约变更，同步断言未弱化）：预设/总控断言改写为扁平锁契约；`test_idea_chat.py` 移除已失效的 `Panel.set_model` 断言（模型选择契约归 `StageModelPicker`）；SKILL 冻结夹具显式配置剧本 skill 勾选，修复 30 万字符上下文超限；`put_production_locks` 为整体替换语义，测试改写全量期望值。

## 三问

- 本轮属于 §3.1 功能轮（任务书 5 轮中的第 1 轮）。
- 测试跑了：`smoke_test.py` 8/8；`smoke_test.py --architecture` 470/470（结果文件落盘后 `test_round_baselines.test_round_number_continuous` 转为分支固有欠账——`project_status.md` 仅 master 可提交，抬头由合并轮推进闭环，同 R2831 先例）；受影响模块定向回归 `run_selftests.py` 17 个测试文件／28 个工作单元／253 条用例，0 红，`ALL TESTS PASSED`（含 skill_panel 全族、stage_config、stage_execution_service、stage_model_value、idea_chat/inline_brief/local_brief、workflow_engines/settings、stage_command_contract、stage_prompt_governance、production_lock 系列、scope 系列与架构套件）。
- 欠账：本轮删除总控子系统整体收口，无新增欠账；全量欠账 `full_safe_required=False`（last_full_safe_all_round=2811），后台 `auto_full_safe` 正在补跑（`auto_full_running=True`），不手动全量；分支固有轮次基线红 1 项待合并轮闭环。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
