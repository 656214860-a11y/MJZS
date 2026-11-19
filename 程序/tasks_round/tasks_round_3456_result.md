# R3456 — A9-4c checkpoint_tree 身份裁定与 A13 移交
<!-- round-evidence: {"commit_base": "4eb3b4fc", "credential_hits": 0, "evidence_sha256": "6eaa6e27a9623b8a", "exit": 0, "failed": 0, "passed": 58, "round": 3456, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮；执行《六层架构收口与企业级演进任务书》A9-4c、R3447 交接。按授权的未接线原型分支收口，只新增结果/evidence，生产及守卫模块改动0，登记0项；不用纯元数据12项例外。
2. 测试：旧严格入口及服务范围负例已实测；定向、冒烟、完整架构前后对照见验证节。历史失败不扩大范围修复，不宣称整本任务书完成。
3. 欠账：严格拒绝21→21，身份/服务范围表不变；把一个待裁定项明确移交A13，不以减少拒绝数代替证据。

## 基线与范围
- 基线 `4eb3b4fc54ae696c78517cd91623830381d10f7b`，初始干净detached HEAD，在现有工作树创建 `codex/architecture-a9-checkpoint-identity`。从程序目录用标准 round_claim.py next 领取3456；第一次在仓库根调用相对脚本路径不存在，未领号，纠正目录后一次成功。
- 使用同仓库安装随附 `D:/漫剧制作助手/运行环境/Python/python.exe`（当前树无随附解释器），PYTHONUTF8=1。完整读取根及程序AGENTS，读取任务A9/A13、R3447、runbook相关规则。
- dev.py scope 使用仓库相对结果路径：102分支，重叠为空，errors为空。未修改master、未推送，不处理UI、门面、动态注册、TOOLS或五模块环。

## 裁定：保留未登记，移交 A13
- `domain/checkpoint_tree.py:2–11` 自述L2；实际只有time依赖，CheckpointStore在内存追加/分叉/切换/剪枝，snapshot/restore转换JSON结构，无磁盘或网络调用。职责形态可作为L2候选，但不能由目录或注释推断已投产。
- 437个真实生产扫描实体：resolved_module_import_rows(qualified=True) 的精确静态消费者为空；AST字面量模块/类名引用为空；排除自身后的checkpoint_tree/CheckpointStore名称引用为空。登记入口ui_plugin_registry与orchestrator/stage_handler_registry亦未找到名称引用。这覆盖仓库可见静态/字面量动态证据，不声称排除了外部任意运行时拼接加载。
- 唯一直接实例化消费者是 `tests/test_checkpoint_tree.py:12–17`。`ui/ui_branch_tree.py:30` 只接收nodes与注入回调，没有构造/消费CheckpointStore；UI组件存在不等于L3接线。
- 原始交付 `tasks_round_3132_result.md` 的“范围外/已知缺口”明确：落盘与继续生成恢复留待阶段/对话整合轮。现有skill_orchestrator的checkpoint字段/恢复方法不引用该类，不能把同名概念计作消费者。
- 结论：当前证据支持未接线原型；不新增LAYERS键，不进入L2服务范围scope_audit_pending，不新增adopter、豁免、allowlist、阈值，不改变默认严格开关。其余20项逐项保留原拒绝状态；本项继续unregistered。

## 先负例后正例（真实守卫）
1. 基线真实LayerDirectionTests严格入口抛AssertionError，消息与全部21项分类字典精确相等，domain.checkpoint_tree=unregistered。
2. 仅用patch.dict临时登记domain.checkpoint_tree=2，调用原ServiceReturnContractBoundaryTests.test_every_registered_l2_module_has_a_scope_record：预期AssertionError，second set多出domain.checkpoint_tree。这是实际守卫调用，不用伪造守卫；上下文退出即恢复。
3. 恢复原LAYERS后，同一服务范围守卫通过。未写入推测登记；旧A9守卫回归继续覆盖精确拒绝、撤销差集和默认语义。

## A13 明确退出条件
- 暂时保留源码与既有测试，所有权交A13；本批不删除、不重命名、不接线。
- 删除路径：A13先复核静态/动态注册、配置、发布入口和生产消费者仍为空，核对现有编排checkpoint是否为后续唯一实现；需求owner确认不用此原型后，成对处置domain/checkpoint_tree.py及其专属测试，核对UI节点树是否独立使用，并同步PROJECT_MAP及原交付说明。不能只删测试来消除身份拒绝。
- 保留投产路径：先给出实际L3消费入口及恢复用例，明确快照读写网关、schema_version兼容、发布器注入与ServiceResult适用范围；补真实创建→落盘→重载→分叉/恢复回归，随后以精确身份+服务范围台账+真实守卫负正例原子登记。若形成向上边，显式报告且不启用默认严格模式。
- 未满足任一路径前保持严格拒绝；源码关于随附sqlite3缺失的注释是历史陈述，不作为当前环境事实或本次层级依据。

## 验证
- 标准round_evidence.py 3456 -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui：58/58，exit0，失败0，真实机器凭据evidence/R3456.json。Tk部分经原runner隐藏桌面并等待跨树GUI令牌，未绕过令牌或跳过用例。
- 默认smoke_test.py：8/8基线＋隐藏桌面probe，总9/9。首次误传--probe仅返回用法，没有把它计作通过；改用默认入口，其内部实际调用scripts/gui_hidden.py --probe并通过。
- 前置完整架构563项、560通过、2 failures＋1 error、301.430秒；在相同源码/守卫上进行报告封口前后对照。本报告是在前置架构运行期间新增，轮次断言已看到3456，因此预期3409 != 3457。
- 历史失败ID：test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only（缺维护记录/基准历史.json）；test_round_baselines.RoundBaselineTests.test_round_number_continuous（3409 != 3457）；test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references（缺screenplay-gate-engine.md）。与R3447同组根因，未改状态页、未补忽略资产、未弱化断言。
- 后置完整架构563项、560通过、2 failures＋1 error、350.990秒、exit1。按FAIL/ERROR完整测试ID自动比较，两次集合相等（3项），无新增失败；严格拒绝字典亦逐项相等21→21。前后零源码变更；本次第二遍仅因明确要求前后实测对照，未再跑无变更的第三遍。
- 原源码、LAYERS、服务范围台账相对基线无diff；未新增测试模块或规则，不需要更新规则生成索引。拒绝集前后按精确名称与状态核对，不是只看总数。
- 安全全量未运行：本轮0源码改动，分支不触发master累计；dev.py debt实测上次绿R3293、最新R3447、源码轮次23/线8、主干False、后台触发False；最新后台全量HEAD0e3fc76退出1，历史失败test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline，未改receipts。完整架构对照不是安全全量凭据。

## 下一 UI 分类批精确输入
13项：ui.edit_habits_dialog、ui.project_settings_dialog、ui.ui_asset_card、ui.ui_branch_tree、ui.ui_citation、ui.ui_code_block、ui.ui_diff、ui.ui_hitl、ui.ui_media、ui.ui_media_player、ui.ui_multimodal、ui.ui_param_panel、ui.ui_task_progress。
逐项核验职责、生产消费者与动态入口，再按≤3模块拆批；本清单不授权一次登记13项。domain.checkpoint_tree移交A13，agent初始化和6个歧义实体仍独立待办：contract.file_index_contract、contract.file_naming、domain.global_library_service、infra.file_index、infra.storage_maintenance、orchestrator.legacy_migration。

## 收尾
- 本树状态页N3409，新结果M3456，N=M+1不满足；仅master可写状态页，本批不改。交主干合入轮按届时最新M同步，本结果对应3457。
- 本批仅完成身份裁定及A13退出条件，不宣称A9/整书完成，不生成虚假整书任务完成文件。完整架构历史红保留，不标[TASK_COMPLETE]。
- 标准dev.py commit保存R3456-FAIL检查点；提交哈希用 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3456_result.md` 定位，最终交接给出以免自引用。提交后核验干净树，不推送，不启动下一轮。
