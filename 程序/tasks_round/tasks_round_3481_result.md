# R3481 — A9-4f 六组同 stem 门面／包实体精确身份
<!-- round-evidence: {"commit_base": "756df6b6", "credential_hits": 0, "evidence_sha256": "bb040e2a0973cf18", "exit": 0, "failed": 0, "passed": 227, "round": 3481, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring test_file_index test_file_naming test_global_library_service test_migrate_legacy_layout"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮；来源《六层架构收口与企业级演进任务书》A9 及 R3429/R3437/R3471。仅三个模块，不使用十二模块例外，不启动下一轮，不宣称 A9／整书完成。
2. 测试：先负例后正例，新增四项行为测试由旧登记下7个失败断言转为4/4通过；完整架构563→567项、相同三项历史失败，无新增；冒烟8/8加隐藏桌面探针9/9。标准定向25文件227/227，实际跳过0项，exit0。
3. 欠账：六组全部精确登记，严格拒绝21→15；其他拒绝不变。真实越层未修复，全量欠账未减少。

## 基线、领号与范围
- 指定基线 `756df6b6fa1ac99d0298f052f95fa1179aead260`，开工干净、detached HEAD；当前工作树新建 `codex/architecture-a9-facade-identities`，round_claim.py next领取3481，无对应队列ID。
- 完整读取根／程序 AGENTS，按任务点名恢复R3429、R3437、R3471与任务书A9、A10/A13、删除判据及runbook规则。工作树缺随附环境，使用同仓库安装的随附解释器 `D:/漫剧制作助手/运行环境/Python/python.exe`，统一UTF-8；没有使用全局Python。
- dev.py scope扫描106条其他分支，36条历史改动交集、errors=0；逐一查看涉及_layers的重叠分支，未发现本批六个限定名登记。只改 `tests/architecture/_layers.py`、`tests/architecture/test_layers.py`、`architecture.md`，另有结果及evidence。保留其他车道交付，不改生产门面／实体，不触碰master、不推送。

## 六组独立裁定
| 顶层门面 / 包实体 | 裁定、职责依据与实际消费者 | 兼容责任 |
|---|---|---|
| file_index / infra.file_index | L1；实体:2–12索引缓存／显式扫描／agent.core原子写，本节既有L1权威；domain/audio_import_service.py:44及文件面板等，严格扫描内16个导入位置 | 保留28项__all__再导出；不扩大历史导出集 |
| file_index_contract / contract.file_index_contract | L0；实体:2–14字段事实与dataclass，无扫描写盘；infra/file_index.py:25及文件面板，4个位置 | 保留11项再导出及FileRow对象身份 |
| file_naming / contract.file_naming | L0；实体:2–17名称模板／清洗／解析与校验，既有L0命名权威；contract/script_contract.py:400/410等，15个位置 | 保留13项再导出；不把包内新增函数自动暴露到旧入口 |
| global_library_service / domain.global_library_service | L1；实体:2自述历史目录保留、:107/143复制事务／索引／来源登记，与architecture原L1一致；ui/desktop_files_panel_filters.py:177/210等，3个位置 | 保留4项再导出；不能按domain目录／初始化L2继承层级 |
| legacy_migration / orchestrator.legacy_migration | L3；plan/apply/rollback编排迁移和引用重写，:283调用阶段服务；严格范围内门面1处，另有实际CLI scripts/migrate_legacy_layout.py:17及测试:15 | 保留11项迁移／回滚API再导出；CLI有dry-run/map/rollback，不因scripts不在默认扫描内判死代码 |
| storage_maintenance / infra.storage_maintenance | L1；实体:4–7依赖L0/L1，回收／恢复／受控清理，既有删除权威；desktop.py:26等，53个位置 | sys.modules别名保留私有名／模块状态／扁平mock.patch；--cleanup转发main，不实际运行清理 |

以上消费者计数是437个限定扫描实体内的导入位置（含门面），不是全仓独立消费者数。额外扫描scripts/tests找到32个相关文件；精确边、导出集和12个生产源文件SHA256保存在审计evidence。顶层均保留独立登记／文件身份；没有按stem合并、删除或通过目录赋层。六项均证据充分，拒绝裁定0项；前批A13残留不重新裁定。

## 负例、正例与兼容证据
- 改登记前直接调用真实严格LayerDirectionTests入口，拒绝字典与分类器逐项一致：六组均ambiguous，总21项。先新增FacadeIdentityTests四项，旧登记运行4 tests、7 failures、exit1；六个子例报告 ambiguous != registered，另一个拒绝差集断言失败；兼容行为与旧图测试已通过。
- 仅添加六个精确登记，418→424；重跑四项4/4通过、exit0。after审计复核旧418键和值、TOOLS五项、静态18／动态2豁免、默认静态／动态图、导出集、消费者与生产源码哈希完全一致。
- 严格拒绝21→15，减少集合恰为六个限定名；其余状态不变：agent初始化、domain.checkpoint_tree和13个UI包实体继续拒绝，沿用前批A13移交。
- 永久四项行为测试覆盖双身份精确分类、撤销条目恰恢复六歧义且真实入口保持拒绝、默认图语义不变、五组__all__对象同一性以及storage sys.modules别名／扁平补丁／CLI无参数不调用和--cleanup恰调用一次。main被mock，无用户数据操作。
- 暴露并保留 `global_library_service.py:3 → domain`，L1→L2包初始化依赖；本批所选源的有界已分类边只有这一项向上。实体L1并不消除门面的初始化依赖；agent仍未分类，严格入口仍先拒绝剩余身份，不声称全图无越层。交A10/A13按≤3模块迁移／兼容处理，不提高层级、不加豁免、不切默认严格模式。

## 验证与交付
- 前置完整架构：`smoke_test.py --architecture`，563项、560通过、2 failures＋1 error、280.599秒、exit1。后置同一命令567项、564通过、2 failures＋1 error、341.657秒、exit1；完整失败集合相同，无新增失败。按完整FAIL/ERROR测试ID集合比较，不只比较失败数量。
- 三项历史失败分别是 `test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（缺维护记录/基准历史.json）、`test_round_baselines.RoundBaselineTests.test_round_number_continuous`（状态页N=3409；前置预期3472，新增本轮报告后预期3482）、`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references`（缺00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md）。已逐项核对报错与实文件存在性；不复制忽略资产、不弱化断言、不修改master专属状态页。
- 默认 `smoke_test.py`：8/8加隐藏桌面探针，总9/9、失败0、exit0；Tk相关回归沿标准隐藏桌面／跨树令牌执行，不绕过等待、不终止其他工作树进程。
- 标准 `round_evidence.py 3481 -k ...` 保留R3471的20个关键词（A9-1至4e回归），追加 file_index/file_naming/global_library_service/migrate_legacy_layout 四类消费者测试；实际25文件227/227、失败0、跳过0、exit0；跨树GUI排队后正常完成，未终止其他进程。真实命令、通过数及退出码保存于 `evidence/R3481.json`。原有扫描器、门禁及canary的AST定义逐项与HEAD相同，只新增FacadeIdentityTests四方法。规则11守卫映射和生成器入口未变，由test_rule_guard_map核验。
- `evidence/R3481-facade-identities-audit.json` 保存六组前后精确身份、两次完整拒绝字典、生产源码SHA256、导出集、消费者及CLI补充扫描、有界向上边、元数据／默认图不变摘要、前后完整架构失败ID／用时／日志SHA256、四项红绿证据、冒烟与标准定向凭据摘要。原始日志只留本机临时目录，不入库。
- 安全全量未运行：普通三模块结构治理，不使用十二模块例外，分支不触发master累计；层级登记变更在合入master前仍必须跑当次安全全量。`dev.py debt`读取真实凭据：上次绿R3293、基线最新R3471、源码轮次23/线8、主干False、后台触发False；最近后台HEAD2a63a23退出1，历史红为test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。未改receipts，不把定向／架构对照当成安全全量。
- 本树N=3409，本结果M=3481，N=M+1不满足；仅master可提交project_status，本轮不越权修改，交合入轮按届时最新M同步（本结果对应3482）。
- 完整架构仍有历史三红，标准 `dev.py commit` 使用 `R3481-FAIL:` 保存本轮检查点；不标[TASK_COMPLETE]，不宣称A9或整书完成。沿R3429/R3471的现有FAIL标题证据流程：先用原round_evidence生成真实定向证据，再由原stamp_result补机器头，最终调用原credential_scan／scan_lines核验白名单新增行；不改提交工具或绕过门禁，不重复无变化测试。
- 提交白名单仅三个模块、本结果及两个evidence文件（共六文件）；`git diff --check`通过，标准credential_scan与包含evidence的逐新增行scan_lines均hits=[]，六文件暂存范围准确且无忽略路径；按标准入口提交。提交哈希以 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3481_result.md` 唯一定位，避免提交自引用。提交后核验工作树干净，不推送，不启动下一轮。


## 下一输入（本轮不启动）
- H03/H09：ui_plugin_registry／stage_handler_registry调用者、常量目标、未知键及变量目标闭包；静态身份登记不能代替动态注册验收。
- TOOLS：codex_tasks／codex_paste／console_submit／batch_frames_tool生产消费者，独立ASR进程闭包与分发边界。保留现有5项登记和4个扫描工具口径。
- agent初始化仍须独立裁定；五模块环与前批14项A13残留沿既有移交，不在本轮处理。
