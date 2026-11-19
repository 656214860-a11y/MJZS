# R3494 — A9-6 UI 动态注册目标闭包
<!-- round-evidence: {"commit_base": "b548a184", "credential_hits": 0, "evidence_sha256": "e4c6750d7997893f", "exit": 0, "failed": 0, "passed": 240, "round": 3494, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring test_file_index test_file_naming test_global_library_service test_migrate_legacy_layout test_dynamic_import_registry"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行；来源任务书 A9、A4/R3411 G、A8/R3416 F05、R3481 交接。仅 _scan.py、test_dynamic_import_registry.py、architecture.md 三模块，另有本结果及 evidence；不启动下一轮。
2. 测试：先红后绿，旧扫描3项坏样本4个断言失败，新UI守卫13/13；默认冒烟8/8＋隐藏探针共9/9。完整架构及标准定向最终结果见下。
3. 欠账：关闭已登记L4 UI调用者的动态目标漏报；未改变生产注册器、15项严格身份拒绝、18静态/2动态豁免、TOOLS及默认模式。历史欠账不冒充减少。

## 领号、查重与设计
- 基线 b548a184a4f22ad3cb63cc802197a48738448adb；开工干净detached HEAD，当前树创建 codex/architecture-a9-ui-registry，round_claim next领取3494。无匹配队列ID；不接触master、不推送。
- 完整读取两级AGENTS，定位runbook §12–15、任务书A4/A8/A9、R3411/R3416设计与R3429/R3437/R3481移交。使用同仓库随附 D:/漫剧制作助手/运行环境/Python/python.exe；本树无随附环境，不用全局Python。
- scope JSON errors={}，38条重叠分支逐一检查_scan，无UI_PLUGINS/ui_plugin_registry解析器，存在前序A9与历史车道交集；该注册器守卫的全分支历史仅T10包迁移及初始化，无等价闭包交付。已有守卫只验证运行时未知键、固定五键子集与少数根目录L4直导；_scan只识别直接import_module常量。复用既有守卫文件，不新增规则编号或架构测试文件；test_rule_guard_map验证生成索引一致。
- 阶段注册器不是键→模块字典：start按stage条件分派并接受fallback，未知stage会走fallback或空串；生产调用含desktop_pet_bridge:58变量stage/回调、:85常量storyboard、pet_ui_stages性能/测试入口。不得擅改其运行时语义，因此缩批UI，A9-7接阶段闭包。

## 实现与红绿证据
- 改扫描实现前，三个坏样本经旧module_dynamic_import_rows实际消费，3 tests / 4 failures：未知键、登记键指向未登记或L5目标、变量目标均漏报。随后更换为AST专用解析器，最终13/13通过。
- UI_PLUGINS仅接受单个字面量frozenset声明；扫描不import/exec生产源。覆盖import/from/as、flat/infra入口、name关键字、条件表达式两支；变量、加载器/注册器转存、getattr和星号导入报unresolved，不静默放行，无变量例外清单。
- 真实消费者：23个登记键、42个L4调用位置、未解析0；详见R3494-registry-audit.json。目标登记沿既有扁平口径，不能据此宣称严格身份已全部收口。
- desktop_launcher为L5，唯一UI调用在app.py顶层__main__直接启动表达式；A4明确保留调试入口，本守卫按入口装配L5核验，普通UI函数仍L4（正负例覆盖）。不修改层号或豁免台账。
- 新负例覆盖未知键、未登记/向上目标、变量、条件分支未知值、函数内向上边、加载器与注册器转存；正例覆盖别名、字面量、条件两支、关键字与调试入口。恶意顶层raise的声明样本可读取，证明解析不执行；运行时unknown在mock import_module前ValueError，已知键保持原strip和返回对象行为。
- _scan旧接口、默认静态/动态图完全未改；生产两注册器哈希保存在审计JSON。规则18仍指向原守卫文件，architecture说明消费边界；不改HTTP/事务/计量、A13或五模块环。

## 验证与提交
- 完整架构前置567项/564通过/2 failures+1 error/378.722秒；后置577项/574通过/同样2 failures+1 error/309.718秒。按完整FAIL/ERROR测试ID逐项相同，无新增失败。
- 原三项：test_agents_md的performance_history缺维护记录/基准历史.json；test_round_baselines的round_number_continuous状态页N=3409（本轮结果写入后应3495）；test_skill_reference_injection缺short-drama-director/references/screenplay-gate-engine.md。沿R3481核实并保留，不复制忽略资产，不弱化测试，不修改master专属状态页。
- 冒烟9/9（默认8＋隐藏探针）；标准定向26文件240/240，failed=0、exit=0；保留R3481全部24关键词并追加test_dynamic_import_registry，A9-1至5回归通过。日志只留临时目录，审计evidence保存哈希、测试ID和摘要，不存完整日志。
- 安全全量未运行：分支不触发master累计；开工时dev.py debt实读上次绿R3293、最新R3481、源码轮次23/线8、主干False、后台触发False；最近后台HEAD93e3ef6退出1（request_ledger/shared_adapter_infrastructure/ui_edges_guards/pet_ui）。不修改receipts，不将架构或定向视作全量绿色。
- 沿R3481检查点流程，以R3494-FAIL标题经原dev.py commit提交，原round_evidence生成真实定向证据并stamp_result；全新增行另跑原credential_scan/scan_lines，不改提交工具、不跳过hook。提交哈希由git log -1 --format=%H -- 程序/tasks_round/tasks_round_3494_result.md唯一定位，避免自引用。完整架构历史三红仍在，不标[TASK_COMPLETE]。


## 下一输入（不启动）
- A9-7：stage_handler_registry条件/回调/未知stage边界；另有orchestrator/stage_models.py:252 → skill_panel的L3→L4动态边。本批明确不把L3视为已验收，不加历史越层豁免；后续按A10/A11迁移/注入并加门禁。
- TOOLS：codex_tasks/codex_paste/console_submit/batch_frames_tool生产消费者，以及独立ASR进程闭包/分发；沿用现有5项登记和4个扫描工具口径。
- 动态变量本批全部拒绝；跨函数推导未实现，后续若需支持须可静态证明有限键集或有精确退出条件的清单，不得宽泛放行。
- 不宣称A9或整书完成，不生成整书完成文件。仅master可同步project_status；本树N=3409，新增结果M=3494，N=M+1不满足，合入轮须按最新M同步。

- 白名单六文件，git diff --check通过，原credential_scan与含evidence全部新增行scan_lines均hits=[]。GUI回归按跨树令牌排队后成功，未绕过/终止其他测试进程。提交后核验工作树干净，不推送。
