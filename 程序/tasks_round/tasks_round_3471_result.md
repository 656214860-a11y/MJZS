# R3471 — A9-4e 修改习惯弹窗身份独立裁定
<!-- round-evidence: {"commit_base": "8ebd5e2b", "credential_hits": 0, "evidence_sha256": "9aa32ca7c8d41ccb", "exit": 0, "failed": 0, "passed": 102, "round": 3471, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理执行轮，来源《六层架构收口与企业级演进任务书》A9、R3463「下一 UI 批」。仅更新 architecture.md 的身份裁定与本轮结果/evidence，生产及测试源码零改动，普通 ≤3 模块范围；不使用纯元数据十二模块例外。
2. 测试：先通过真实严格入口证明旧拒绝，完整架构前后均 563 项、560 通过、2 failures＋1 error；冒烟含隐藏桌面探针 9/9。定向20个文件102/102、失败0、实际跳过0；详见下文。
3. 欠账：登记 0、移交 A13 1、待定 0；严格拒绝 21→21。明确处置责任不等于清除欠账；不宣称 A9 或整本任务书完成。

## 基线、交接与范围
- 指定基线 `8ebd5e2bb95d8c28f806a9e0fdceffa781b0e436`，初始工作树干净、detached HEAD。在当前树建 `codex/architecture-a9-edit-habits`，由 round_claim.py next 领取 3471；无对应队列 ID，不冒领其他任务。
- 完整读取根及程序 AGENTS、任务书 A9/A13/删除判据、runbook §12–15、R3463 结果。任务点名的 R3466 不在本基线；从工作树台账定位并读取的唯一同号文件属于 b3da 视频选版任务，与 A9 无关。以基线内 R3463 的唯一下一批指针恢复上下文，不挪用无关结果。
- 当前树无运行环境，使用同仓库安装的随附解释器 `D:/漫剧制作助手/运行环境/Python/python.exe`，PYTHONUTF8=1；不使用全局 Python。
- scope 首次传程序内相对名未覆盖仓库相对路径，已在改动前纠正为 `程序/...` 重跑：105 个其他分支，34 条在 architecture.md 有历史/前序改动交集，71 条无重叠；本轮结果/evidence 无同名新增重叠。只加独立裁定及修正前序「下一批」指针，不覆盖其他车道条目。不改 master、不推送。

## 负例与独立裁定
- 调用现有 `LayerDirectionTests.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)`，真实抛出 `Unclassified local modules`，解析异常中的完整字典与现有分类器结果逐项相等。`ui.edit_habits_dialog: unregistered`、总拒绝数 21；默认入口通过。原始拒绝字典及源码 SHA256 在审计 evidence，未新建替代门禁。
- 源码 `ui/edit_habits_dialog.py:25/32/41` 提供 entry_button、open_dialog、HabitsDialog；第 13 行委托 L3 服务，第 118–146 行后台归纳/队列/after 回送。它具备 UI 职责形态，不能据此推断当前产品可达。
- 扫描器限定实体 437、递归生产 Python 文件 705。按精确导入解析、字面量动态导入、模块名/类名引用三种口径，排除自身后均为 0；当前测试模块名/类名引用也为 0。`infra/ui_plugin_registry.py:9` 与阶段注册无该身份。此证据不声称排除仓库外任意拼接式加载。
- 入口历史：归档 R2074:14/21 曾交付风格行按钮和旧 L4 登记；提交 `8f5c2990`（R2862）实际删除 skill_panel 对弹窗的 import 及 entry_button 调用。现 `ui/skill_panel.py:220–255` 构建 SKILL/制作锁界面，未恢复入口。`docs/stages/S01_剧本准备.md:180` 的 DES-S01-60 仍声称有旧风格行入口，属于待 A13 同步的文档漂移，不能当接线证明。
- 路径历史：R3059（`3008566c`）将实体搬入 ui；R3063（`09e8cd8f`）删的是顶层 147 行文件、旧登记与测试补丁，当前包内文件依然存在；R3165（`043cd4f0`）仅迁移其 UI helper 导入。不能把历史删除叙述当作当前文件不存在。
- **裁定：无当前生产接线的包内历史残留，保持严格拒绝并移交 A13；不登记 L4。** 登记 0、移交 1、待定 0；其余 20 项拒绝身份/状态保持不变。

## 独立服务边界与 A13 退出条件
- L3 `orchestrator.edit_habits` 仍有真实消费者：`ui/desktop_script_edit_session.py:45` 记录自然剧本修改；`orchestrator/workflow_settings.py:431` 读取已采用规则；`orchestrator/workflow_engines.py:70`、`writing_api.py:1078/1226` 注入提示词。不可扩大裁定为「修改习惯功能整体废弃」。`tests/test_edit_habits.py` 测服务与 workflow_engines，并不证明弹窗可达。
- 删除路径：A13 重核静态、动态注册、配置/CLI/插件/分发清单和旧项目兼容责任，确认不恢复弹窗后，仅处置 `ui/edit_habits_dialog.py` 的残留及对应覆盖/目录登记，修正 DES-S01-60 和交付说明。保留仍被消费的服务、测试及用户习惯数据；不得只删测试消除拒绝。
- 保留投产路径：明确当前页面/菜单及真实消费者、L3 操作边界；用现有后台生命周期约束验证打开、归纳成功/失败、采用/停用/改写/删除、取消/关闭后无迟到回调，再以精确身份申请登记；若暴露向上边，保留证据并分范围处理。
- 任一路径未满足前继续拒绝。本轮不接线、不删除、不迁移；登记表、TOOLS、豁免、阈值和默认严格模式均不变。已有 A13 原型移交不重新裁定。

## 验证与交付
- 前置完整架构：`smoke_test.py --architecture`，563 项、560 通过、2 failures＋1 error、311.787 秒、exit1；状态断言 `3409 != 3464`。
- 三个历史失败：`test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only` 缺 `维护记录/基准历史.json`；`test_round_baselines.RoundBaselineTests.test_round_number_continuous` 状态页落后；`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references` 缺 `screenplay-gate-engine.md`。分别核对测试报错与文件存在性；范围外资产和主干专属状态页不在本轮修复。
- 后置完整架构：同一标准命令，563 项、560 通过、2 failures＋1 error、273.074 秒、exit1；轮次断言变为 `3409 != 3472`。前后按完整失败 ID 比较，集合完全相同，无新增失败；不再无变更重跑第三遍。
- 后置真实严格入口仍拒绝21项；完整拒绝字典、目标之外20项及目标源码 SHA256 前后一致，默认入口通过。LAYERS、test_layers.py、_scan.py、架构统一基数相对指定基线无 diff；无新规则编号或守卫映射变化，不重写生成索引。
- 默认 `smoke_test.py`：默认基线8/8，加 `scripts/gui_hidden.py --probe` 隐藏桌面探针，总9/9，失败0，exit0。
- 标准 `round_evidence.py 3471 -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring`：20个文件102/102、失败0、实际跳过0、exit0。保留 A9-1 至4d 的17文件76项回归，增加独立修改习惯服务/计量/产物版本接线26项。85条非GUI、17条Tk均实际执行；Tk通过标准隐藏桌面并等待跨树GUI令牌，未绕过令牌或终止其他工作树进程。
- [R3471-edit-habits-audit.json](evidence/R3471-edit-habits-audit.json) 保存前后严格拒绝字典、精确消费者、源码与守卫哈希、前后架构完整失败ID及日志SHA256、冒烟摘要，以及标准工具真实生成的102项定向证据快照及其SHA256。实测 dev.py commit 的自动证据匹配只识别 `R数字:`，`R3471-FAIL:` 保留既有 R3471.json 的102项真实定向凭据，不会生成 docs-only 凭据。使用 round_evidence.stamp_result 补入该凭据摘要，并用其 scan_lines 对本批相对基线的全部新增行执行最终凭据扫描；不修改提交工具、不伪造通过数、不重复运行无变更测试。
- 安全全量未运行：生产与测试源码零改动，仅一个权威文档模块，未触发分支的 master 累计门槛，也未使用十二模块批量例外。dev.py debt 实测上次绿色全量 R3293、基线最新 R3463、源码轮次23/线8、主干False、后台触发False；最新后台全量 HEAD2a63a23 exit1，历史红为 test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。不修改真实 receipts，不把架构对照充作安全全量。
- 状态页只许 master 写；本树 N=3409，本结果写入后 M=3471，N=M+1 不满足。交主干合入轮按届时最新 M 同步（本结果对应3472），本轮不越权更新。
- 后续输入：同 stem 门面涉及的六个 ambiguous 身份 `contract.file_index_contract`、`contract.file_naming`、`domain.global_library_service`、`infra.file_index`、`infra.storage_maintenance`、`orchestrator.legacy_migration`；`agent` 初始化身份；动态注册反解、TOOLS 生产边界。五模块环、checkpoint_tree 和前批 UI 原型保留既有移交。本轮不启动下一轮。
- 本结果随标准 dev.py commit 保存为 `R3471-FAIL:` 检查点，完整架构历史三红尚在，不标整书完成或 [TASK_COMPLETE]；提交哈希用 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3471_result.md` 定位，避免提交自引用。首次提交 `3c73a511760f7cd7c80ab651a45e0beed6110bc1` 后发现上述证据匹配行为，使用同轮标准补记提交纠正说明并补齐最终扫描，不另开轮次。交付范围仅本轮4个文档/evidence文件，最终凭据扫描 hits=[]；提交后核验干净工作树，不推送、不启动下一轮。
