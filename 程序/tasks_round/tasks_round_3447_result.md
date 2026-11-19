# R3447 — A9-4b L2 精确身份与服务范围台账闭环
<!-- round-evidence: {"commit_base": "2da07ffc", "credential_hits": 0, "evidence_sha256": "f0be0af720f5eeb8", "exit": 0, "failed": 0, "passed": 51, "round": 3447, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮；来源《六层架构收口与企业级演进任务书》A9、R3437 的 A9-4b 交接。只处理 domain、domain.hitl 两项，三模块；不用扩至12模块的纯元数据例外，不宣称 A9 或整本任务书完成。
2. 测试：两个真实守卫负例先红，修正后定向51/51、非架构消费者在内82/82、0 skip；默认冒烟8/8（加隐藏桌面探针和定向门禁10/10）。完整架构559项/3历史失败→563项/相同3历史失败，无新增失败；历史失败不在授权修复范围。
3. 欠账：精确身份拒绝23→21；L2身份/范围漏登两项消除，ServiceResult范围审计仍明确待办，真实向上边与安全全量欠账不冒称减少。

## A. 基线、领号、范围
- 基线 `2da07ffc2abba535bb396796da37e418a7ced137`，开工树干净且为detached HEAD；在现有工作树创建 `codex/architecture-a9-l2-scope`，标准 `round_claim.py next` 领取R3447，队列show为空。未接触master、未同步/合并/推送。
- 本树无随附解释器，使用同仓库主安装随附 `D:/漫剧制作助手/运行环境/Python/python.exe`。领号子线程第一次按系统GBK解码Git输出报UnicodeDecodeError，但领号已返回3447，未重领；后续统一PYTHONUTF8/PYTHONIOENCODING。
- `dev.py scope` 以仓库相对的三个完整路径复核：扫描100分支，25分支重叠，errors为空；逐分支读取_layers确认均未登记domain.hitl，不另建重复实现。首次误用程序相对路径得到空匹配，已纠正，不以空匹配作证。
- 变更仅 `_layers.py`、`维护记录/架构统一基数.json`、`test_service_return_contract.py`；另新增本结果和标准evidence。生产源码、接口、返回值、初始化副作用均无变化；不处理UI、歧义门面、动态注册、TOOLS或五模块环。

## B. 两项裁定与权威台账
| 精确身份 | 层级、职责与依据 | 台账处置 |
|---|---|---|
| `domain` | L2；`domain/__init__.py:1` 仅包职责docstring，architecture §1:24明确L2业务包，§3:90已认定其L2证据。初始化登记不向后代传播。 | 第一项.scope_audit_pending新增精确键domain |
| `domain.hitl` | L2；`domain/hitl.py:2` 明示L2，risk_of/auto_decision/apply_decision负责业务风险和决策；只依赖time/enum，无Tk/网络/磁盘。`ui/ui_hitl.py:12` 是生产源码消费者，但不由此推断UI入口已完整接线。architecture §3:90已明确支持该L2裁定。 | 同组新增domain.hitl；不加adopters/exempt_items，不伪称ServiceResult已迁移 |

- LAYERS 416→418，原416键和值逐项不变；台账只加两项，scope_audit_pending 5→7。两项是范围可追溯登记，不是新豁免；原adopters、52项服务结果豁免、静态18/动态2分层豁免及全部其他台账内容逐项不变。
- `domain.checkpoint_tree` 虽有L2源码说明，未纳入本批；本轮有明确的两项根因，不为凑数扩大。下一分类批独立核验生产消费者、持久化职责和服务范围。
- 不修改第四模块architecture.md：§3:80/90是带R3437轮次的历史记录，并已明确domain/HITL的L2职责与台账原子补登记要求；§3:94–98已定义精确身份优先、初始化不传播、未知身份拒绝和严格影子模式；§3 L2表末段（131行）已指定其余待迁移范围由架构统一基数登记。此次未改变任何层级规则或新增规则编号，只落实既有裁定，当前数量由本结果及机器登记给出。
- 规则11生成索引仍用原守卫；`test_rule_guard_map`已验证同步。没有新增测试模块或更改门禁清单。

## C. 先负例后正例
1. 在未改源码的基线上，仅用patch.dict给真实LAYERS加domain/domain.hitl=2，调用原 `ServiceReturnContractBoundaryTests.test_every_registered_l2_module_has_a_scope_record`：1项失败、exit1；原105行提示second set缺domain/domain.hitl。复现R3437新增失败，不以模拟守卫代替。
2. 同一基线再仅补真实台账数据的scope_audit_pending两项，调用同一守卫：1项失败、exit1；原113行missing多出domain.hitl。根因是原代码拼出domain.hitl.py，而实际源码是domain/hitl.py；不能把它登记成历史缺失名逃避检查。
3. 守卫仅把精确点号身份映射为同一根目录下的源码路径或包初始化；不调用stem回退，不改变历史名集合相等、跨组去重、采用方棘轮等原断言。
4. 新增4个永久行为测试：真实分层消费者精确裁定/撤销差集/剩余拒绝及选中实体向下正例；移除每项范围登记必须失败；精确源码缺失即失败且hitl.py同stem文件不能掩盖domain/hitl.py缺失；默认静态/动态图语义不变。
5. 实测新增登记差集精确为这两项，其余21项状态逐项不变。选中二实体经原LayerDirectionTests严格入口通过；全仓严格入口仍准确拒绝21项，未静默改默认、未宣称全图分层绿色。A9-1/2/3/4a原测试全部保留并通过。

## D. 暴露边界与未修复项
- 精确解析器仍暴露 `global_library_service.py:3`（L1）→ `domain` 初始化（L2）。这是R3437已提示的真实向上边，不新增豁免。完整严格入口先被21项未裁定身份阻断；有界加入该门面也会先拒绝其未裁定目标domain.global_library_service，不能把未到达越层判定说成越层通过。
- 修复该门面涉及生产门面/其歧义实体裁定，既超出本批明确范围，也会使本批超过三模块；保留失败证据，交后续门面owner独立处理。默认静态/动态依赖图与基线逐项不变。

## E. 验证与历史失败对照
- 改前完整架构：559项、556通过、2 failures＋1 error、311.124秒、exit1。
- 改前失败集合：`test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（缺维护记录/基准历史.json）；`test_round_baselines.RoundBaselineTests.test_round_number_continuous`（3409 != 3438）；`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references`（缺screenplay-gate-engine.md）。未复制忽略资产或改断言消红。
- 定向 `run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map`：51/51、21.0秒、0 skip、exit0。
- `smoke_test.py --affected test_service_return_contract test_branch_coverage_entity test_selftests`：实际4文件82/82、29.3秒、0 skip；默认冒烟8/8，加隐藏桌面探针及定向门禁10/10、exit0。Tk相关测试由原runner自动移到隐藏桌面；登记表其余架构消费者由完整架构覆盖。
- 改后完整架构：563项、560通过、2 failures＋1 error、289.945秒、exit1。自动提取并比较前后FAIL/ERROR完整测试ID，集合相等（3项），新增4项全部通过；轮次连续性为3409 != 3448，其余两项仍是同一缺失资产。不越权改状态页或补忽略资产，不重复无变更的完整架构/安全全量。
- 标准 `round_evidence.py 3447 -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map`：51/51、exit0、凭据零命中。仅为产生仓库规定的机器凭据再运行精确定向，未扩大为安全全量。FAIL标题无法触发dev.py的自动evidence解析，沿R3437先显式调用原生成器和stamp_result，不改提交脚本或绕过检查。
- 安全全量未运行：本轮三模块，不用>3模块元数据例外，功能分支不触发主干累计；层级登记改动合入master前须按AGENTS §5跑当次全量，定向不能充当全量凭据。dev.py debt：上次绿R3293、基线最新R3437、源码轮次23/线8、主干False、后台触发False；最新后台全量HEAD0e3fc76退出1，历史失败文件test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。未改receipts。

## F. 下一分类批精确清单及提交
剩余严格拒绝21项，未自动启动下一轮：
- 未登记初始化：`agent`。
- 未登记包实体14项：`domain.checkpoint_tree`、`ui.edit_habits_dialog`、`ui.project_settings_dialog`、`ui.ui_asset_card`、`ui.ui_branch_tree`、`ui.ui_citation`、`ui.ui_code_block`、`ui.ui_diff`、`ui.ui_hitl`、`ui.ui_media`、`ui.ui_media_player`、`ui.ui_multimodal`、`ui.ui_param_panel`、`ui.ui_task_progress`。
- 歧义包实体6项：`contract.file_index_contract`、`contract.file_naming`、`domain.global_library_service`、`infra.file_index`、`infra.storage_maintenance`、`orchestrator.legacy_migration`。
- 下一批先独立裁定domain.checkpoint_tree；UI组件、agent初始化、歧义门面分别按职责/消费者证据分批，不把上述21项当成一次授权批。动态注册/TOOLS/五模块环及向上边仍移交原owner。
- 状态页N3409，本树新增结果M3447，N=M+1不满足；分支无权修改project_status.md，交主干合入轮按实际最新结果同步（本结果对应3448）。任务书尚在A9，不产出虚假整书完成文件，不标[TASK_COMPLETE]。
- `git diff --check`通过，提交白名单仅三个治理模块、本结果、evidence/R3447.json五文件，均非忽略运行资产。本轮通过标准dev.py commit保存R3447-FAIL检查点，完整架构仍有历史红，不标完成。提交状态/哈希由 `git log -1 --format=%H -- 程序/tasks_round/evidence/R3447.json` 唯一定位，在最终交接给出，避免提交自引用。提交后核验干净树；不推送、不启动下一轮。
