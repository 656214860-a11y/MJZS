# R3463 — A9-4d 首个 UI 未登记身份分类批
<!-- round-evidence: {"commit_base": "d1c80bed", "credential_hits": 0, "evidence_sha256": "4ddbafb1924a89a4", "exit": 0, "failed": 0, "passed": 76, "round": 3463, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮，执行《六层架构收口与企业级演进任务书》A9 及 R3456 的 UI 分类输入。只改 architecture.md 与本结果/evidence；生产源码及守卫改动 0，普通三模块范围内，不使用纯元数据扩展模块数的例外。本批只裁定 12 个身份。
2. 测试：先验证旧严格入口对本批身份的真实拒绝，再记录不登记裁定；A9-1 至 4c、11 个组件原测试、默认冒烟和完整架构前后对照见验证节。历史失败不扩大范围修复，不宣称整本任务书完成。
3. 欠账：登记 0、移交 A13 共 12、待定 0；严格拒绝 21→21。分类证据变明确，不把移交等同于欠账消除。

## 基线、范围与方法
- HEAD 基线 `d1c80bed7f9d6e6c69079a1da3dc03450728dbb1`，初始干净 detached HEAD；在当前工作树建 `codex/architecture-a9-ui-identities`，标准 round_claim.py next 领号 3463。当前明确任务无对应队列 ID，不冒领别项。
- 完整读取根及程序 AGENTS，读取任务书 A9/A13、R3456、runbook §12–15、架构 §3。当前树无随附解释器，使用同仓库安装随附 `D:/漫剧制作助手/运行环境/Python/python.exe`、PYTHONUTF8=1。
- 开工 dev.py scope 检查最初三模块计划：扫描 103 分支，32 条分支报告已有路径重叠、errors={}；包含本基线的前序 A9 车道及其他历史改动。没有同名新增文件；本批最终只在现有 architecture.md 加独立裁定段，结果/evidence 使用新领唯一号，不覆盖他树工作，不动 master、不推送。
- 对 437 个限定身份扫描实体调用 resolved_module_import_rows(qualified=True)，逐项核对精确静态消费者；module_dynamic_import_rows 核对字面量动态导入，同时核对 infra/ui_plugin_registry.py 与 orchestrator/stage_handler_registry.py 的名称引用。12 项静态/动态/注册入口均为 0。
- 扩查 production_files_recursive() 的 705 个 Python 文件，排除各自定义后的 12 项模块名引用为 0。独立入口函数名与类名逐词检索也无接线证据；ui_multimodal.classify 的 54 处同名引用归属 artifact_schema、error_codes、previs_routing、model_pool、pet_agent 等，不是本模块消费者。reference_part/attach_references 没有生产引用。
- 以上是仓库可见静态与字面量动态证据，不声称排除外部任意拼接加载。历史“新增 L4 组件”或测试通过不能替代现有生产入口。

## 12 项逐项裁定

下表 S/D 分别是上述精确静态/字面量动态生产消费者数。每项均保持 unregistered；表中 L4 形态只是源码职责描述，不是新增权威登记。

| 精确身份 | 源码职责 | S/D 与测试消费者 | 入口或历史交付依据 | 裁定 |
| --- | --- | --- | --- | --- |
| ui.project_settings_dialog | ui/project_settings_dialog.py:4，confirm_unattended 封装 ask_confirmation，无设置持久化 | 0/0；当前测试也无引用 | R2202 明记生产无调用；R3063:15–18 删除顶层文件、旧测试补丁与层级登记；R3059 曾搬入 ui，包内文件当前仍在。不能把历史删除叙述当作当前实体不存在 | A13：历史残留 |
| ui.ui_asset_card | ui/ui_asset_card.py:21/57，资产名高亮与缩略图悬浮卡，动作回调注入 | 0/0；tests/test_asset_hovercard.py:36/42 | R3135 交付组件及测试，明确悬停防抖留待接线；无正文渲染生产调用 | A13：仅测试组件 |
| ui.ui_branch_tree | ui/ui_branch_tree.py:15/29，节点树展平、DataTable 展示、切换/提问回调 | 0/0；tests/test_branch_tree_ui.py:39 | R3132 的节点树组件，未接会话入口；不消费 CheckpointStore，沿用 R3456 区分 UI 节点数据与 checkpoint 实现的证据 | A13：仅测试组件 |
| ui.ui_citation | ui/ui_citation.py:16/40，引用标记着色、点击回调、引用列表转换 | 0/0；tests/test_citation.py:34/44 | R3135 交付溯源组件与测试；没有消息渲染调用 | A13：仅测试组件 |
| ui.ui_code_block | ui/ui_code_block.py:17/39，代码高亮、折叠、复制/应用回调 | 0/0；tests/test_code_highlight.py:33/41 | R3128 交付独立组件；没有消息 part 分派入口 | A13：仅测试组件 |
| ui.ui_diff | ui/ui_diff.py:19/37，行差异、红绿 Text 及接受/拒绝回调 | 0/0；tests/test_diff_view.py:33/40 | R3128 交付独立组件；没有审批或编辑页面接线 | A13：仅测试组件 |
| ui.ui_hitl | ui/ui_hitl.py:24/48，审批按钮与选择卡，消费 domain.hitl 决策信封 | 0/0；tests/test_hitl_ui.py:45/55 | R3123 明确审批面板/阶段 UI、超时计时器留待接线；domain.hitl 已登记不等于其 UI 已接线 | A13：仅测试组件 |
| ui.ui_media | ui/ui_media.py:22/36，Lightbox、候选缩略图、收藏/打开回调 | 0/0；tests/test_media_render.py | R3128 明确真实收藏入库与资产页联动留后续；无产物卡调用 | A13：仅测试组件 |
| ui.ui_media_player | ui/ui_media_player.py:33/64，音视频卡、封面/波形及播放/采用/导出回调 | 0/0；tests/test_video_audio_card.py:39/56 | R3138 交付音视频卡及测试；无生产页面调用 | A13：仅测试组件 |
| ui.ui_multimodal | ui/ui_multimodal.py:17/27/38，按扩展名分类并构造 FILE part，无 Tk/网络/读写 | 0/0；tests/test_multimodal_upload.py:17/25 | R3138 明确拖拽/粘贴真实事件绑定留后续；目录不能证明其应为 L4，后续还须裁定纯转换职责归属 | A13：未接线转换原型 |
| ui.ui_param_panel | ui/ui_param_panel.py:40，温度/步数/比例控件，返回 values 与 on_change | 0/0；tests/test_param_panel.py:33 | R3138 明确引擎支持集和页面整合留后续；无参数提交入口 | A13：仅测试组件 |
| ui.ui_task_progress | ui/ui_task_progress.py:29，Canvas 进度卡、转后台/完成回调 | 0/0；tests/test_background_task.py:34 | R3138 明确后台队列与 notifier 留待页面接线；无任务中心消费者 | A13：仅测试组件 |

## 先负例后正例与严格拒绝集
1. 在写入裁定前，调用真实 LayerDirectionTests.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)：预期 AssertionError，完整异常文本与 21 项精确状态字典相等；本批 12 项逐项为 unregistered。没有伪造守卫或使用正常模式代替严格负例。
2. 在同一源码/登记下调用默认 LayerDirectionTests 入口：通过，保留 A9 当前默认模式；不声称这是全限定图通过。由于没有任何生产接线证据，不作临时补登记来换取绿色结果。
3. 文档裁定后再次调用真实严格入口，逐项比较前后拒绝字典相等，并确认本批 12 项与剩余 9 项全部保留。源码、LAYERS、服务范围台账、TOOLS、阈值及静态/动态豁免零改动。
4. 未选 9 项：ui.edit_habits_dialog、domain.checkpoint_tree、agent、contract.file_index_contract、contract.file_naming、domain.global_library_service、infra.file_index、infra.storage_maintenance、orchestrator.legacy_migration。前 3 项 unregistered，后 6 项 ambiguous。未切默认严格模式，没有通过新登记暴露或掩盖向上边。

## A13 移交退出条件
- 本批保留所有源码与测试，不删除、不改名、不迁移、不新增生产消费者。A13 接收上述精确 12 项，并保留其与 R3456 checkpoint_tree 移交的独立边界。
- 删除路径：逐项复核静态导入、动态注册、配置及发布清单仍无消费者，明确功能是否被现有页面替代；在 A13 已授权范围内处置包内残留与专属测试、同步 PROJECT_MAP/原交付说明及覆盖登记。尤其 project_settings_dialog 须核对“历史顶层已删、包内残留仍在”的路径区别，不能删除另一条无人值守实现。
- 保留投产路径：先明确页面/消息/事件的实际入口、回调与 L3 服务归属，补打开→交互→取消/关闭的真实集成回归，再以源码职责和实际消费者逐项精确登记。ui_multimodal 另须判定纯转换逻辑层级；ui_task_progress 须遵守 BackgroundTaskLifecycle；ui_hitl 须验证实际审批入口而非只验证信封单测。
- 任一路径未满足前继续严格拒绝；后续接线若暴露向上边，记录并按模块范围移交，不新增豁免、allowlist、阈值或宽泛目录映射。

## 验证
- 旧严格负例及文档裁定后正向核对均通过：真实严格入口精确拒绝字典 21→21，12 项选中身份与 9 项未选身份逐项相等；默认 LayerDirectionTests 入口通过。LAYERS、test_layers.py 和架构统一基数相对指定基线无 diff，没有用新测试清单绕过既有守卫。
- 默认 smoke_test.py：8/8 基线加隐藏桌面 `scripts/gui_hidden.py --probe`，总 9/9，exit0。
- 前置完整架构：563 项、560 通过、2 failures＋1 error、391.800 秒、exit1。轮次断言在新增本结果前执行，实际为 `3409 != 3457`。
- 历史失败精确 ID：test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only（缺维护记录/基准历史.json）；test_round_baselines.RoundBaselineTests.test_round_number_continuous（状态页未同步）；test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references（缺 screenplay-gate-engine.md）。沿用 R3456 的三项根因，不补缺失资产、不弱化断言。
- 后置完整架构：563 项、560 通过、2 failures＋1 error、354.422 秒、exit1；实际轮次差值 `3409 != 3464`。脚本按 FAIL/ERROR 的完整测试 ID 比较两次集合，三项完全相等，无新增失败；前后日志摘要和 SHA256 留在本轮审计凭据。第二遍只为授权要求的前后实测对照，不再无变更重复第三遍。
- 标准 round_evidence.py 3463 -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task：17 个文件、76/76、失败0、实际跳过0、858.7秒、exit0。包含 A9-1 至 4c 的旧守卫与全部 11 个本批组件专属测试。59 项非 GUI 和 17 项 GUI 均实际执行；Tk 用例经标准隐藏桌面 runner 等待共享 GUI 令牌，未绕过令牌、未跳过或终止其他树进程。
- [R3463-ui-audit.json](evidence/R3463-ui-audit.json) 保存真实定向机器证据快照及其 SHA256、12 项精确消费者与源码哈希、前后完整拒绝字典、完整架构前后摘要/日志 SHA256、冒烟结果。标准 `R3463-FAIL:` 提交沿用 round_evidence.py 已生成的 R3463.json（76/76）；用该工具的 stamp_result 写入真实凭据摘要，并对最终暂存清单调用其 credential_scan，要求 hits=[]。不重复执行无变更测试，不手写或伪造通过凭据。
- 安全全量未运行：本轮生产/测试源码零变更，结构治理仅改 1 个权威文档模块，没有使用超过三模块的纯元数据例外，不触发分支的 master 累计门槛。dev.py debt 实测：上次绿色全量 R3293，新增本结果前最新 R3456，源码轮次 23/线8，主干 False，后台触发 False；最新后台全量 HEAD0e3fc76 退出1，历史失败 test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。不改 full-safe-receipts.json，不把架构对照当安全全量凭据。
- 最终文档范围 scope 再查 104 分支、errors={}，本轮结果/evidence 无同名新增重叠。未新增规则编号或测试模块，规则生成索引不需改写；源码、运行时行为、导入副作用和既有断言均无变化。

## 下一 UI 批与收尾边界
- 下一 UI 批唯一输入：`ui.edit_habits_dialog`。沿用“源码职责→静态/动态消费者→菜单/入口或历史交付→严格负例→裁定”的顺序；本批虽读到相关线索，不替下一批裁定、不自动启动。
- 同 stem 门面、动态注册反解、TOOLS、五模块环、checkpoint_tree 均未处理；任务书 A9 整体及全书未完成，不生成虚假整书完成文件。
- 状态页只许 master 写；本树 N=3409、最新结果 M=3463，N=M+1 不满足，交主干合入轮按届时最新 M 同步（本结果对应 3464）。不越权改状态页或缺失资产。
- 本结果随标准 dev.py commit 保存为 `R3463-FAIL:` 检查点提交，原因是完整架构仍有三项历史红，不宣称全部门禁通过，不标 [TASK_COMPLETE]。提交哈希以 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3463_result.md` 定位，最终交接给出以避免报告自引用。提交后核验工作树干净，不推送，不启动下一轮。
