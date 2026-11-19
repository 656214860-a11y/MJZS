# R3437 — A9-4a 首个精确身份元数据登记子批
<!-- round-evidence: {"commit_base": "64c89f11", "credential_hits": 0, "evidence_sha256": "d50c5b57eeb67915", "exit": 0, "failed": 0, "passed": 47, "round": 3437, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮；来源《六层架构收口与企业级演进任务书》A9、R3429 C/F。仅三模块、5项登记，不使用扩至12模块的批量例外；不宣称 A9 或整本任务书完成。
2. 测试：先红后绿；最终定向47/47、初选版扩大消费者107/107、最终默认冒烟8/8（加隐藏桌面探针9/9）。完整架构556项/3历史失败→559项/相同3历史失败，无新增失败。历史失败不在授权修复范围，不修改状态页、忽略资产或 skill 引用。
3. 欠账：严格未知/歧义拒绝28→23；5项身份欠账消除，真实向上边未修复，全量回归欠账未减少。

## A. 基线、领号与范围
- 基线 `64c89f1118c83fa08e4771174ae8130024fe5ae8`，开工干净、detached HEAD；在现有功能工作树新建 `codex/architecture-a9-metadata`，领取 R3437。未接触 master、未同步或推送。
- 本树无随附解释器目录，使用同仓库主安装随附解释器 `D:/漫剧制作助手/运行环境/Python/python.exe`，未用全局 Python；子进程统一 UTF-8。首次本树路径查找失败、未执行领号，修正解释器后仅领号一次。队列 show 为空，无匹配租约可领。
- `dev.py scope` 共28条重叠分支、errors为空；涉及登记/守卫的24分支均未新增本批精确身份；A9-1/2/3已在基线，保留其他车道变更。
- 仅修改 `_layers.py`、`test_layers.py`、`architecture.md`，另加本结果与标准 evidence。生产模块零修改；不处理动态注册、TOOLS、五模块环和门面迁移。

## B. 5项逐实体权威裁定
| 精确身份 | 层级 | 源码职责、消费者/权威依据 | 运行时变化 |
|---|---|---|---|
| `contract` | L0 | `contract/__init__.py:1` 纯事实/协议说明，architecture §1 契约包及 §3 L0 职责 | 无行为变化 |
| `infra` | L1 | `infra/__init__.py:1` T10包化说明显式指向architecture §3；§1基础设施包职责 | 无行为变化 |
| `orchestrator` | L3 | `orchestrator/__init__.py:1` T10包化说明指向§3，§1编排包职责 | 无行为变化 |
| `ui` | L4 | `ui/__init__.py:1` 明确L4界面组件包，与architecture §1/§3一致 | 无行为变化 |
| `ui.ui_part_renderers` | L4 | Tk消息part分派、host回调注入；`ui/desktop_idea_bubbles.py:352` 为实际生产引用，消费domain.message_parts和ui_tokens | 无行为变化 |

所选四个初始化AST均只有1个字符串表达式，无导入/副作用。初始化登记只约束该可导入实体，不能向整个包传播。`agent` 横跨L1–L4，不凭空初始化/目录猜层。`ui.ui_hitl` 虽消费HITL信封，自身审批入口接线仍无证据；本批不把下游引用误当其已接线证明。

`domain` 的包说明与 `domain.hitl` 的请求/风险/决策规则（`ui/ui_hitl.py:12` 消费）支持L2职责，但L2服务范围台账尚未同步。完整架构首次复验暴露原子登记还需第四模块，因此两项移交A9-4b，继续严格拒绝；不是缺少生产引用就降为工具。初选时 `global_library_service:3 → domain` 的额外向上边也随domain初始化裁定移交，最终新增登记目标有8条向上边。

## C. 负例→实现→正例与兼容
- 改登记前真实严格消费者拒绝28项，含初选7项及最终5项。新增 `AuthoritativeIdentityTests` 先跑3方法：1通过、8失败（7个身份subTest及拒绝差集断言），exit1；关键错误 `('unregistered', None, None) != ('registered', '<精确名>', <层>)`。负例日志为本机临时证据，不入库。
- `_layers` 最终只新增5个精确键，411→416；不新增stem登记/allowlist/阈值。原411个键和值、TOOLS五项、静态18/动态2豁免与默认图逐项对照不变。
- 三个永久测试覆盖真实仓库精确分类、撤销所选登记只恢复这5个拒绝且未选拒绝完全相同、旧静态/动态依赖语义不变；保留A9-1扫描、A9-2原子登记、A9-3严格消费者canary原断言。
- 原实体存在性守卫仅支持扁平路径；新增精确限定路径实文件检查，不修改通用 `_scan.entity_file` 或引入宽泛stem回退。
- 规则11生成索引不受本批影响：`scripts/rule_guard_map.py:47` 的 build 只读AGENTS规则及规则守卫基线，render不读取LAYERS；实测 `render(build())` 与已提交索引逐字相等，原 `test_rule_guard_map` 通过。

## D. 暴露的真实向上边（不加豁免）
以下为严格扫描器解析的、目标属于本批新增登记的向上边。全仓严格入口仍先拒绝23个未裁定身份，因此此表是有界诊断，不能宣称已完成全图越层检查。旧豁免不能自动迁成限定身份豁免。

| 源实体:行 | 目标初始化 | 处置 |
|---|---|---|
| `infra.engine_probe:93` | `orchestrator` | L1 owner后续≤3模块修复 |
| `infra.native_apps:91` | `ui` | L1/UI owner后续≤3模块修复 |
| `domain.confirm_gates:27` | `orchestrator` | L2/L3 owner后续≤3模块修复 |
| `domain.idea_document_paths:41` | `orchestrator` | L2/L3 owner后续≤3模块修复 |
| `orchestrator.skill_orchestrator:28` | `ui` | L3/UI owner后续≤3模块修复 |
| `agent.shot_assets:118` | `ui` | agent视频适配器/UI owner后续≤3模块修复 |
| `agent.volcengine:23` | `ui` | 同上 |
| `agent.wan:19` | `ui` | 同上 |

## E. 验证与历史失败对照
- 精确定向 `run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map`：38/38、23.6秒、0 skip、exit0。
- 冒烟初次误传顶层 `--probe`，exit2（未运行测试）；核实 `smoke_test.py:627/745` 默认调用 `scripts/gui_hidden.py --probe`，按现有 `--affected` 入口重试，不改runner。
- `smoke_test.py --affected test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map test_branch_coverage_entity test_selftests`：实际7文件107/107、48.0秒、0 skip、exit0；默认8/8，加隐藏桌面探针及定向门禁10/10。非架构消费者test_branch_coverage_entity/test_selftests已覆盖，其他登记表测试消费者由完整架构覆盖；Tk runner自动迁入隐藏桌面。
- 初次标准evidence为38/38；收缩为最终5项后以 `round_evidence.py 3437 -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map` 重新生成：47/47、exit0、凭据零命中。重复仅因变更后更新机器证据，无重复安全全量。
- 最终精确定向含新增失败守卫：47/47、20.4秒、0 skip、exit0；最终默认冒烟8/8，加隐藏桌面探针9/9、exit0。原411键、TOOLS、旧静态/动态图、生成索引再核验完全一致；严格28→23，拒绝差集精确等于最终5项，剩余状态逐项不变。
- 改前完整架构：556项、553通过、2 failures＋1 error、356.689秒、exit1。失败集合仍为 `test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（缺维护记录/基准历史.json）、`test_round_baselines.RoundBaselineTests.test_round_number_continuous`（3409 != 3430）、`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references`（缺screenplay-gate-engine.md）。未以复制忽略资产或修改断言消红。
- 首次改后完整架构（初选7项）：559项、555通过、3 failures＋1 error、296.004秒、exit1。新增 `test_service_return_contract.ServiceReturnContractBoundaryTests.test_every_registered_l2_module_has_a_scope_record`：`domain`／`domain.hitl` 尚未进入L2服务范围台账。自动诊断确认该守卫要求LAYERS所有L2键与服务台账逐项相等（test_service_return_contract.py:97–105）。不弱化断言、不改层规避：撤回这两项登记，将其与L2台账原子补登记移交A9-4b，最终5项仍在原三模块内。
- 最终完整架构：559项、556通过、2 failures＋1 error、285.487秒、exit1；自动比较改前/最终FAIL与ERROR完整测试ID集合相等（3项），新增3个身份测试均通过，L2服务范围守卫恢复通过。状态连续性改后为3409 != 3438，其余缺失资产与改前相同。本次完整复跑由首次新增失败触发，未重复无变化的全量。
- 安全全量未运行：本轮3模块，不使用>3模块纯元数据批量例外，功能分支不触发主干累计；本批修改层级登记，合入master前必须按AGENTS §5跑当次全量，不复用本轮定向作为全量凭据。`dev.py debt`：上次绿R3293、当前基线最新R3429、源码轮次23/线8、主干False、后台触发False；最新主干后台全量HEAD0e3fc76退出1，历史失败文件test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。未改receipts。

## F. A9-4b剩余精确清单与提交
严格拒绝仍为23项，精确清单如下（与A9-3差集恰为最终所选5项）：
- 未登记初始化：`agent`、`domain`。
- 未登记包实体15项：`domain.hitl`、`domain.checkpoint_tree`、`ui.edit_habits_dialog`、`ui.project_settings_dialog`、`ui.ui_asset_card`、`ui.ui_branch_tree`、`ui.ui_citation`、`ui.ui_code_block`、`ui.ui_diff`、`ui.ui_hitl`、`ui.ui_media`、`ui.ui_media_player`、`ui.ui_multimodal`、`ui.ui_param_panel`、`ui.ui_task_progress`。
- 歧义包实体6项：`contract.file_index_contract`、`contract.file_naming`、`domain.global_library_service`、`infra.file_index`、`infra.storage_maintenance`、`orchestrator.legacy_migration`。
- 默认严格开关未启用；TOOLS/H03/H09动态注册、生产门面alias及兼容导出、旧豁免精确迁移、五模块环继续移交原owner/后续子批。本轮不启动下一轮。
- 标准evidence47/47、凭据零命中；`git diff --check`通过，提交白名单仅三模块、本结果、evidence/R3437.json五文件，均非忽略运行资产。完整架构尚有历史红，使用标准 `dev.py commit` 保存 `R3437-FAIL` 检查点，不标[TASK_COMPLETE]。沿R3429流程，FAIL标题无法触发自动evidence解析，先显式调用原round_evidence生成并用原stamp_result写机器头，不改提交脚本或绕过检查。
- 状态页N3409、最新本树结果M3437，N=M+1不满足；分支无权提交状态页，交主干合入轮按实际最新结果同步（本结果对应3438）。未修改project_status或receipts。
- 提交哈希以 `git log -1 --format=%H -- 程序/tasks_round/evidence/R3437.json` 唯一定位并在最终交接给出，避免提交自引用；提交后核验干净树，不推送、不启动下一轮。
