# R3506 — A9-7 阶段注册器条件与回调静态闭包
<!-- round-evidence: {"commit_base": "3e39050f", "credential_hits": 0, "evidence_sha256": "8b0bb9cc1c7140d0", "exit": 0, "failed": 0, "passed": 263, "round": 3506, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring test_file_index test_file_naming test_global_library_service test_migrate_legacy_layout test_dynamic_import_registry test_stage_command_contract"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行；来源《六层架构收口与企业级演进任务书》A9、A4/R3411 G、A8/R3416 F05/J 与 R3494 下一输入。三模块：_scan.py、test_dynamic_import_registry.py、architecture.md；另有本结果及 evidence。不启动下一轮。
2. 测试：先负例后正例；旧扫描 3 tests / 7 failures。新守卫、定向、完整架构最终凭据见下。冒烟默认 8/8＋隐藏探针共 9/9；严格生产阶段闭包保持拒绝，不能冒充全绿。
3. 欠账：补上此前漏报的阶段条件/回调和 L3 UI 动态边；生产缺陷未修复、全量欠账未减少。未新增豁免、未改变默认静态/动态导入图及剩余 15 项严格身份拒绝。

## 领号、范围与设计
- 基线 01cc78a9a35f43354d898fcf724d97d96c1ab274；干净 detached HEAD 上建立 codex/architecture-a9-stage-registry，使用随附 D:/漫剧制作助手/运行环境/Python/python.exe，round_claim next 领取 3506。初次根目录调用路径不存在，未领号；正确程序目录调用领号成功但出现旧子进程 GBK 解码警告，后续设置 PYTHONUTF8=1，无重复领号。无匹配队列任务，不冒领其他租约。
- 两级 AGENTS 完整读取；runbook §12–15、A4/A8/A9、R3411/R3416/R3494 定位读取。scope 扫描 100 分支，errors={}，39 条范围重叠分支含前序 A9；逐分支读取扫描器，未发现等价 stage_registry_audit 交付。只在当前工作树修改，不接触 master、不推送。
- 实际注册器是条件分派而非字典。13 阶段键来自 pet_bus.STAGES；pet_performance/pet_test 是现存辅助命令，不冒充第14/15阶段。未知 stage 可能进入 fallback 或返回空串；运行行为保持原样，严格入口拒绝此未验证域。
- 不增加规则编号或测试文件；规则18仍指向同一守卫，生成索引通过原 test_rule_guard_map 校验。L4 注入回调按注入方层级判定，不把运行回调方向错当成 L3→L4 import 许可。

## 交付及负例/正例
- 新增 AST-only literal_string_keys / stage_registry_audit / require_stage_registry_closure。声明及注册器均不 import/exec；条件两支、死分支、import/from/as、关键字、常量目标、本地函数与同类方法回调体均进入审计；保存分支条件和调用行号。未知键、变量、转存/遮蔽、星号、无法证明的方法/目标、未登记与向上目标均拒绝。已声明的非 start API 单独核对声明存在及目标层。
- 改扫描前：未知/变量/条件变量键 3 断言、未登记/向上/变量分派目标 3 断言、变量回调 1 断言，旧 module_dynamic_import_rows 全部漏报，3 tests / 7 failures。原始负例日志仅在系统临时目录，证据保存摘要/哈希，不入库完整日志。
- 正例含三种导入形式、常量/关键字/条件键、L4 向 L3 注入 L4 callable、本地回调递归、同类方法、显式拒绝未知域。负例还含别名逃逸/重绑定/同名参数与定义、回调条件坏分支/装饰器、死分支未知键、下层调用注册器及 L3 UI 动态越层。顶层 raise 的声明与注册器仍可解析，证明未执行被扫描源码。
- 实际消费：限定实体全扫描，4 个 start 调用位置（desktop_pet_bridge:58/85，pet_ui_stages:603/637）；全部15个键进入注册器条件审计。审计 JSON 包含所有调用、22个注册器条件分支及两侧调用、目标、拒绝和生产源码哈希；严格入口实测exit=1。
- 严格生产入口直接执行后拒绝 3 文件、29 条诊断：stage_handler_registry 19、desktop_pet_bridge 9、stage_models 1。pet_ui_stages 的两个辅助命令调用与既有非启动 API 均可解析。29 条是保守拒绝诊断，**不是29个确定生产缺陷**：容器方法、外部函数、继承方法和动态属性尚未做类型/跨函数证明时也拒绝。无失败允许清单；默认测试验证严格拒绝行为，不等于生产闭包已绿。

## 越层证据与精确移交
- LAYERS 与 architecture §3 均登记 stage_models=L3、skill_panel=L4。真实链：stage_models.manual_command 内 run 的 configure 分支 :347–348 → open_config :248–252 → ui_plugin_registry.module('skill_panel').show(desktop, stage)。原 scanner 未接入此源层，本轮 _target_errors 按实际源层产生 upward-target。
- 现有上移/注入接缝：ui/ui_stage_popups.install_stage_presenters:155–158 → stage_exec.install_ui_presenters:24–29 → stage_models 的已有呈现器 setter。沿此链增加配置面板呈现器至少触及三个生产模块，加扫描器和消费测试超过本轮三模块限制，因此按授权只补门禁与移交，不改 UI/业务行为。
- A10/A11 下一修复批：复用上述安装链，将 skill_panel.show 的构造放 L4，L3 只调用注入的配置呈现器；保持懒加载、configure 后返回 False、失败状态提示/None。补安装/未安装/异常/点击配置行为测试；真实动态边消失后让严格 UI 检查通过，不加豁免。
- 阶段启动后续：在任何副作用前明确未知键处理，兼顾现存两个辅助命令与 auto/manual/fallback 行为；为 desktop_pet_bridge.pet_start 的 stage 来源提供可静态证明的有限域，不能把变量直接列白名单。_start_unattended_stage 的继承目标分别位于 desktop_script_pages.pet_script_structure_batch:393、desktop_media_pages.pet_continuity_ledger:192、pet_frame_batch:133；desktop 属性/动态 getattr 的目标需通过显式端口或声明证明，继续保留拒绝直到真实闭包成立。
- TOOLS 下一输入仍为 codex_tasks/codex_paste/console_submit/batch_frames_tool 的生产消费者、独立 ASR 子进程协议与分发闭包；现有5项登记/4个扫描工具口径不变。不处理五模块环、HTTP/事务、A13 原型，不启动下一轮。

## 验证、欠账与提交
- 改前完整架构：577 项，574 通过，2 failures＋1 error，294.651 秒。原三项：test_agents_md.performance_history 缺维护记录/基准历史.json；test_round_baselines.round_number_continuous 的状态页 N=3409；test_skill_reference_injection 缺 short-drama-director/references/screenplay-gate-engine.md。
- 中间完整架构590项出现原三红外的文档新红：R3506 紧邻“阶段”被阶段数解析器识别为3506。仅把轮次与正文加冒号分隔，不改守卫；复合条件/遮蔽/装饰器拒绝补齐后先定向复测，再做最终完整架构。最终完整架构590项/587通过、2 failures＋1 error、441.409秒，失败ID与改前完全相同；文档新红已消除。标准定向由原 round_evidence.py 3506 -k 运行，精确用例数与退出码由文件头机器证据及 R3506.json 记录；最终收口须 judge 绿色。阶段/UI 专项最近 26/26（包含原 A9-6 的13项）。默认 smoke_test.py 自动执行隐藏桌面 --probe，共9/9；显式 smoke_test.py --probe 不支持（exit 2），按源码确认后运行默认入口通过，没有绕过隐藏桌面。
- 安全全量未运行：本分支不触发 master 累计；dev.py debt 实读上次绿 R3293、最新 R3494、源码轮23/线8、主干False、后台触发False；最近后台 HEAD93e3ef6 exit1（request_ledger/shared_adapter_infrastructure/ui_edges_guards/pet_ui）。不改 receipts，不将定向/架构作为全量绿凭据。
- 保留三项历史红及严格闭包红，按 runbook §13 使用 R3506-FAIL 检查点，经原 dev.py commit --tests 创建检查点后，发现 commit_round.py:40 的 ^R(\d+): 不匹配 -FAIL，因而跳过 attach_evidence，首次提交3e39050f没有测试evidence。立即补原 round_evidence.py 的真实定向测试和 stamp_result，再以同轮元数据 amend 补齐；不改提交工具、不跳过 hook。机器evidence的 commit_base 指向首次检查点，受测源码与最终提交相同。提交哈希由 git log -1 --format=%H -- 程序/tasks_round/tasks_round_3506_result.md 唯一定位，避免自引用；提交后检查工作树干净。不宣称 A9 或整书完成，不标 [TASK_COMPLETE]，不生成整书完成文件。
- 本树 N=3409、新增结果 M=3506，N=M+1 不满足；仅 master 能改 project_status，留给合入轮按届时最新 M 同步。不修改 master 专属状态页或复制被忽略资产来制造全绿。

- 最终专项（文档修复＋阶段/UI守卫）27/27；原扫描器28个函数AST逐一对比完全未变。提交前白名单5文件＋标准生成evidence共6文件，git diff --check通过，原credential_scan及含审计evidence的scan_lines均无命中。

- 原工具实际定向结果：263项通过、failed=0、exit=0；完整架构590项的原三红与严格入口29条拒绝不因定向通过而转绿。
