# AI 漫剧助手：架构清单

> 初稿基于 2026-09-25 源码；后续按轮次追加，R1022 校正文档口径。本文的 R 编号段落是历史记录，不是当前验收凭据。阶段、路径与事件以 AGENTS.md §2.2 所列代码为准；开发验证规则只在 AGENTS.md §5 定义。

> 轮次专属的改动说明、已验证的发布边界、维护边界已迁入 [架构变更记录](维护记录/架构变更记录.md)；那里的 R 编号段落是历史记录，不是当前验收凭据。

## 1. 目录树

R1124：在 storyboard 与 assets 之间增加 animatic，阶段总数为 13。L2 `animatic_service` 编排共享参考图、本地 ComfyUI 镜头草图、临时音频与图片时间线合成；L3 `stage_execution_service` 注入校验、原子发布及索引更新，L4 只发起回调。SG-A 检查已采用初稿，SG-B 要求预演媒体证据及人工确认节奏、时长和对白同步；正式资产仍使用线上 API，资产提示词、正典与锚点职责不迁移。共享参考图路径由 `stage_path_service` 产出。旧编号目录只读，显式修改经 L3 复制到新编号后重定位，复制失败不改原件；当前同名文件优先。应用内合成不是剪映原生自动导出。

R1040（J5 分轮 1）：`ui_icons.IconLoader.return_arrow()` 支持显式颜色，缓存键包含宿主、尺寸与颜色；默认白色保持兼容。页面迁移在下一轮验证，当前不代表 J5 已完成。

R1041（J5 分轮 2）：app 日志视图清空、desktop 最后剧本回收确认／取消、video_navigation 返回均经语义按钮；返回使用主题色共享箭头及次按钮。现有按钮边界扩展 tk/ttk 静态导入及赋值别名 canary，架构实测 306/306（原 301，新增 5 个用例，测试文件数量不变）；不声称覆盖动态导入、名称遮蔽或跨函数数据流。

协作基础设施：`维护记录/基准脚本/worktree_ledger.py` 只读汇总 Git 工作树、租约及显式容器残差；`--plan` 仅输出待确认命令。`round_claim.py next` 拒绝 detached HEAD 分配轮次。两者不进入生产执行链，不读用户项目正文。

```text
程序/
├─ agent/                 通用 Agent、媒体与视频服务适配器
├─ assets/                图标和程序静态资源
├─ batch_frames_tool/     批量首帧辅助工具
├─ contract/              L0 契约包（error_codes 与 L0 契约族共 30 个模块；顶层同名 .py 为历史门面）
├─ data/                  程序内置数据、示例数据
├─ domain/                 L2 业务服务包（首批 22 个低扇出模块；顶层同名 .py 为历史门面）
├─ episode/               默认/演示剧集输出
├─ infra/                 L1 基础设施包（首批 23 个低扇出模块；顶层同名 .py 为历史门面）
├─ logs/                  运行、模型与三虎日志
├─ orchestrator/           L3 编排包（两批共 27 个低扇出模块；顶层同名 .py 为历史门面）
├─ ui/                     L4 界面组件包（首批 17 个低扇出模块；顶层同名 .py 为历史门面）
├─ private/               本机私有配置和加密密钥副本
├─ scripts/               Python 维护/迁移工具
├─ skills/                可注册 SKILL 与阶段模板
│  ├─ templates/          13 阶段 YAML 流程模板
│  └─ cinematic-director/ 导演工作流资料包
├─ tasks/                 任务记录
├─ tasks_round/           每轮开发结果
├─ 配置/宠物/             三虎全局设置、模型池
├─ 配置/SKILL/            阶段预设
├─ PROJECT_MAP.md         数据边界、门禁地图
├─ project_status.md      当前状态和待办
├─ desktop.py             Tk 主桌面、阶段页面
├─ pet_*.py               三虎 Agent 系列
├─ stage_*.py             阶段配置、执行、并行
├─ skill_*.py             SKILL 注册、面板、编排
├─ model_*.py             模型池、路由、密钥
└─ workflow_*.py          API/桌面 Agent 工作流
```

### 分发边界

`distribution_manifest.md` 是仅供构建/校验工具读取的声明式分发边界：正式副本保留根目录启动器、`运行环境/` 与 `程序/` 的运行所需内容，排除测试、轮次/维护记录、开发脚本、缓存、源码控制元数据、既有日志、私有数据和升级备份。它不在应用启动时读取，也不执行复制、移动或删除；日志保留期与轮转策略不由该清单决定。

## 2. SKILL 清单

R1139：L3 `codex_skill_sync` 通过注册表物化所有已登记阶段（含第 13 阶段）的 `.skill.md` 至 `CODEX_HOME/skills/<name>/SKILL.md`（默认用户 `.codex/skills`）。生成稿仅保留 name/description 元数据，正文的共享资料引用改为应用绝对路径；不复制共享包、不内联正文。首帧后后台同步，Codex 发送 worker 在构建提示词前校验；来源/产物 hash 避免无变化重写。同步器只更新本安装拥有且未被手改的技能，源删除后的同类目录经回收入口保存；手工同名、越界链接或扫描失败均不删除。

注册规则：`skill_registry.py` 只递归扫描 `skills/01`—`12` 阶段目录内的 `.skill.md`，并以目录编号归类 SKILL；根目录遗留 `.skill.md` 仅在用户打开阶段配置后的懒扫描中，按 frontmatter 的 `stage` 自动移动到对应阶段目录，无法判定、目标缺失或重名时保留原文件并报告。`00全流程SKILL` 和其他根目录资料包不作为阶段候选。用户层（R2073）：「新增 SKILL」写入 `data/skills/<与内置同名的阶段目录>/`，注册表两层合并，同名时用户版优先并记软警告，删除用户版后内置版恢复；用户层引用 `../00全流程SKILL/…` 时由 `skill_registry.resolve_reference` 回退到内置层。旧版导进 `skills/` 且记在旧台账里的条目，首帧后由 `skill_import_service.migrate_legacy_imports` 在 Codex 同步线程里迁到用户层；台账外的手放文件不迁。同时只在同一次懒扫描中，将各阶段目录下一层、根部含 `SKILL.md`（或集合包 README）的外部包注册为**一个总入口**，绝不递归展开包内子 SKILL。剧本阶段的总入口还必须登记到 L0 `script_contract.AUDIT`：它们均为支撑性技能，受控默认值不声明 output 或 manifest，不能据此虚构产物归属。`stage_config.py` 将每阶段选中的模型和 SKILL 存入项目 `skill_config.json`，读取时保留失效选择供发送校验阻断，并将错阶段项归位。

制作锁契约（R2862 起替代总控预设契约）：总控机制（`总控.json` 清单、`master_skill`、`master_import_service`、预设套用、面板内模型选择）已整体删除。制作锁是项目级事实，存 `skill_config.json` 顶层 `production_locks`（键取 `contract.script_contract.PRODUCTION_LOCK_DEFINITIONS`），读写权威为 `stage_config.workflow_lock()`／`put_production_locks()` 与 `stage_execution_service.save_writing_production_locks()`；旧项目只在 `workflow.lock.<总控名>` 里有值时按原命名空间回退读取（`workflow_lock_history` 保留历史投影）。阶段配置面板只留 skill 勾选＋技能说明，制作锁经 `skill_panel_workflow.PanelWorkflowMixin.open_lock_dialog` 弹窗预选；必填口径统一走契约 `stage_lock_requirements`（含项目创建日期过滤），`stage_handler_registry._workflow_lock_error` 对手动与自动路径一律阻断，剧本准备简报门禁除外。`skill_import_service`（L4，无 Tk）：阶段配置「新增 SKILL」的整包导入、预检、试冻结、旧版回收与导入台账（`data/skills/导入台账.json`；旧路径 `skills/导入台账.json` 迁移后回收）。R2881 起同模块提供仓库导入：`import_from_repo`／`update_from_repo` 解析 `owner/repo` 简写、完整 URL（可带 `@分支`）与本地目录，`git clone --depth 1` 到 `data/skills/.仓库克隆-*` 暂存（用后回收），扫描 `SKILL.md`／`*.skill.md` 候选后逐个走同一导入管线；阶段按 frontmatter `stage`→仓库内 `NN` 目录→面板当前阶段判定；`uninstall_skill` 经回收站移除、`validate_skill` 即试冻结、`list` 仍是 `skill_registry.getAll()`；面板下拉新增「从仓库地址导入」入口；面板侧导入动作（文件／仓库）在 `skill_panel_import.PanelImportMixin`。

| 名字（文件路径）                                                                                                                                                                   | 阶段    | 一句话职责                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------------------------- |
| 各阶段内容 SKILL（`skills/01 剧本准备SKILL/`） | 剧本准备 | 创意剧本的台词润色与情绪节奏标注。 |
| 各阶段内容 SKILL（`skills/02剧本整理SKILL/`） | 剧本结构 | 将原稿组织为结构化剧本，并提取资产需求、整理世界观。 |
| 各阶段内容 SKILL（`skills/03初步分镜SKILL/`） | 初步分镜 | 拆场、生成镜头链、设计镜头语言并校验节奏和时长。 |
| 各阶段内容 SKILL（`skills/05资产管理SKILL/`） | 资产管理 | 检索/生成候选、版权筛选、去重排序、确认后入库。 |
| 各阶段内容 SKILL（`skills/06连贯性SKILL/`） | 连贯性清单 | 冻结锚点并审计角色、场景、服装、道具和跨批次漂移。 |
| 各阶段内容 SKILL（`skills/07分镜定稿SKILL/`） | 分镜定稿 | 对齐资产、锁定一致性、校验定稿、输出提示词和快照。 |
| 各阶段内容 SKILL（`skills/08首帧管理SKILL/`） | 首帧管理 | 首帧批量生成、质检重试及缩略图缓存。 |
| 各阶段内容 SKILL（`skills/09白模预演SKILL/`） | 白模预演 | 生成白模场景、走位、机位路径、动作和节奏预览。 |
| 各阶段内容 SKILL（`skills/10视频生成SKILL/`） | 视频生成 | 视频批量提交、模型分流、轮询、质检和失败重跑。 |
| 各阶段内容 SKILL（`skills/11配音字幕SKILL/`） | 配音与字幕 | 多角色配音、情绪核验、字幕对齐及 SRT＋ASS 同批导出（`subtitle_timing.ass_text`、`subtitle_export_service.export_ass`）。 |
| 各阶段内容 SKILL（`skills/12后期剪辑SKILL/`） | 后期剪辑 | 粗剪合成、镜头间转场、背景音乐、平台版本导出与剪映交接（音效、配音混音、预览生成未实现）。 |
| 各阶段内容 SKILL（`skills/13质检交付SKILL/`） | 质检与交付 | 质检、合规与风格检查、归档和交付报告。 |

阶段模板位于 `skills/templates/`：`script`、`script_structure`、`storyboard`、`asset`、`continuity`、`final`、`keyframe`、`previs`、`video`、`audio`、`edit`、`delivery` 各一份 YAML。每份均含读取/分析、生成（可确认）和写入产物步骤。

## 3. 分层判定

R1623：运行期诊断统一走 `logging`（`app_logging` 在启动时装好 `logs/app.log` 的文件处理器并脱敏）。生产模块里的 `print` 在 pythonw 下是静默空操作，只允许登记的控制台入口保留——命令行工具（`engine_probe`／`shot_numbering`／`workspace_maintenance`／`log_maintenance`／`exit_maintenance`／`app_icon`／`app_shortcut`／`asset_thumbs`）、子进程协议 `image_agent_runner`、控制台提交 `console_submit` 与双通道 `broadcaster`；由 `test_print_ratchet.py` 冻结，只许下降。

R1125：L3 `skill_notes` 负责阶段配置的中文阅读副本：优先中文说明、本地术语翻译、经现有模型路由后台翻译及内容哈希缓存；L4 `skill_panel` 只处理选择与显示。代码、地址、路径和执行源文件保持原样；失败保留原文并提示，不阻断导入。

R1074：L3 `exit_maintenance.launch_cleanup()` 集中退出后的三路派发顺序、正常／强制退出差异、可选启动 OSError 降级与固定大小的脱敏派发摘要。L4 只传程序位置及退出意图；工作进程保持独立，既有清理实现、范围和回收策略不变。摘要只报告 scheduled／launch-failed／skipped-force／not-attempted，完成状态明确 unobserved；不把启动当作清理完成，不新增等待、重试或持久化出口。

R1073：L3 `pet_chat_coordinator.ChatCoordinator` module 独占待单击任务，合并单／双击消歧、取消与守护关闭规则。L4 `pet_ui.Pet` 保留既有入口并注入调度与视图动作 adapter；测试采用内存队列／视图 adapter。这个 seam 不传入整个 Pet，不复制 chat／visible／shape，动画、Cloud 资源、问候与静默策略仍由原所有者管理。interface 的 locality 与 depth 由跨入口顺序测试证明，不以文件缩短作验收；删除此 module 会把共享协调规则与状态重新分散回 UI。

R1647：把两条「只比事实」的越层依赖从台账豁免降为不再存在：`维护记录/架构统一基数.json` 的 `层级` 条目 **37→35**、`baseline_exempt` 同步下调，不新开豁免，`reason` 仍是「既存越层，待专项收口」。① 资产批量后端名（本地与三个云端模型名）下沉到 L0 `production_model_contract`，L4 `cloud_assets` 按原名字转发并由同一份常量生成节点类型与参考图张数上限，L2 `asset_batch_service` 不再为了比一个字符串 import L4；② `stage_model_value` 按其实际依赖（只有 `file_cache`／`pet_bus`，无 Tk、无编排）由 L3 改登记为 L1，纠正以名字后缀分层的旧账。行为与取值逐字不变。其余越层（含 `asset_batch_service` 仍欠的三条提示词／参考图取值）需要把纯函数下沉到更低一层；**加新顶层模块会触发 `覆盖率基线.json` 口径门禁（282≠281），必须先重跑覆盖率工具**，故按批分轮推进。

R2202（R2178 J5–J7）：`project_settings`、`cloud_assets`、`asset_prompt_rules`、`asset_reference_prompts` 的 Tk 弹窗各拆进 L4 对话模块（`project_settings_dialog`、`cloud_assets_dialog`、`asset_prompt_check_dialog`、`asset_reference_prompts_dialog`），原模块只剩数据与规则：前三者→L1，`asset_reference_prompts`（懒加载 L2 的 `storyboard_catalog_service`）→L2 并记入 `scope_audit_pending`。`层级` 台账 21→8，清 13 项。

R2216（R2178 J10）：新增 L1 模块 `model_metering`，把「授权 → 发送 → 结算」计量序列收成一个入口 `metered(ledger, request, send, usage_of, on_result)`；`pet_llm._attempt` 与 `writing_api.WritingRequestAdapter._call` 原先各抄一份，现都委托它（等价委托，行为不变）。两处各自的诊断目录（`pet_llm` 写 `<项目>/model_diagnostics`，`writing_api` 写 `<项目>/logs/model_diagnostics`）与 reason 文案保留差异，统一会搬数据位置，另行裁决。R2223（J11–J12）起该模块还收口直连文本模型的计量（`chat_metered`）与两种重试口径：`replayable_retry`（对话可重放）、`submission_retryable`（提交可能已受理）。

R2191（R2178 J3）：按真实静态依赖重登记 8 个模块，只改登记与台账、不改生产代码——`artifact_lineage`→L0（无依赖，被 L0 `script_contract` 引用）；`pet_state`、`ui_plugin_registry`、`integrations`、`qwen_setup`→L1（只依赖 L0／L1）；`qwen_adapter`（引擎适配器，与 `workflow_engines` 同层）→L3；`workflow_settings`、`legacy_compat`→L3（依赖 L3 的 `stage_config`／`stage_models`／`skill_registry`／`edit_habits`）。`层级` 条目 **35→21**、`baseline_exempt` 同步下调，`KNOWN_DYNAMIC_UPWARD` 5→3；剩余 21 条是真实的反向依赖，留给后续专项。

R1649：清掉 `tests/architecture/_layers.py` 里 3 个**僵尸登记名**——`project_storage`／`asset_detail_ui`／`workflow`。依据：全仓 AST 与文本检索均无同名 `.py`、无导入、无属性／字符串引用，`architecture.md` 本节表格也从不曾列出它们（现行名分别是 `asset_detail` 与 `workflow*` 家族），即初版登记表里没有采用方的历史残名。同时新增可执行不变量：**登记表每一名须满足「有实体 `.py` ∨ 在 `TOOLS` ∨ 在 `historical_name_audit.entrypoints`」**，由 `test_layers` 断言；僵尸名既已无采用方，就不并入 `historical_name_audit`（该项要求指认现行职责入口）。分层判定、越层豁免数与 `baseline_exempt` 均不变。

| 层       | 模块/职责                                                                                                                                                      | 判定                           |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| L0 合同   | `pet_bus`、`script_contract`、`script_manifest_schema`、`script_output_spec`、`asset_contract`、`service_contract`、`artifact_lineage`、`artifact_schema`、`project_context`、`stage_layout`、`stage_path_service`、`storyboard_paths`、`prompt_templates`、`shot_batches`、`continuity_ledger`       | `service_contract.ServiceResult` 定义四字段结果口径；`project_context.ProjectContext={root, stage_resolver, settings_snapshot, cache}` 定义项目上下文注入契约。采用方及待迁移范围以 `维护记录/架构统一基数.json` 和对应门禁为准，本表不缓存数量。两项于 2026-10-04 经用户授权解冻，按序每轮最多迁移 3 个 service，执行规则见 `维护记录/架构统一路线图_v2.md`。`pet_bus.emit_safe()` 是跨模块状态的唯一安全发送器，`pet_agent._emit()`／`pet_ui._emit()` 仅作受控转发；`broadcaster` 只写用户可见文本日志。`stage_path_service` 是新写/旧读的唯一阶段路径口径；`script_contract.save_natural_script()` 是手改自然剧本的原子发布口径（R2612 起不再做内容闸门，只拦空正文与非 `.md` 目标）；允许被上层依赖，不应反向依赖 UI/编排；`stage_layout.validate_stage_contract()` 保证目录阶段与 `pet_bus.STAGES` 同序；`json_md_rows()` 的人读 MD 路径只使用当前编号阶段目录下的 `docs/`；`artifact_schema` 是正式 JSON 产物版本与字段契约的唯一登记：新写入写 `schema_version`，读取侧容忍缺版本，历史 `version` 键经 `migrate()` 只加键抬升 |
| L1 基础设施 | `client_profiles`、`model_pool`、`model_secrets`、`config_snapshot`、`pet_llm`、`model_metering`、`file_cache`、`hash_backend`、`usage_snapshot`、`usage_history`、`storage_maintenance`、`workspace_maintenance`、`diagnostic_capture`、`line_endings`、`ui_tokens`、`pet_state`、`ui_plugin_registry`、`integrations`、`qwen_setup`、`project_settings`、`cloud_assets`、`asset_prompt_rules`                                                    | `client_profiles` 只读内置与用户客户端档案并解析 PE 头；探测命令仅在用户显式操作时运行，启动路径不扫描目录；`diagnostic_capture` 仅采集程序拥有日志的脱敏现场与已知启动指标，导出固定白名单且不扫描项目目录；模型小环违反此层应无反向依赖的目标；`ui_tokens` 是 design_tokens.md 的只读代码化事实来源；本机路径/浏览器/进程和短 TCP 探测统一由 `platform_tools` 适配，不得由 UI 直连；`workspace_maintenance` 只做仓库级可再生卫生（`__pycache__`、超期 `.selftmp`、已并净的 `.wt` 工作树），用户可见删除仍唯一走 `storage_maintenance.recycle_paths()`，`git gc` 只在开发脚本 `scripts/repo_health.py`            |
| L2 业务   | `writing*`、`idea_chat`、`asset_reference_prompts`、`idea_brief_form`、`idea_attachments`、`idea_script_heuristic`、`idea_document_paths`、`idea_transcript`、`storyboard*`、`asset*`、`keyframe*`、`video_lifecycle_service`、`tts_api`、`speech_api`、`offline_asr_client`、`audio_import_service`、`subtitle_timing`、`subtitle_export_service`、`delivery_import_service`、`confirm_gates`、`desktop_settings_service`、`stage_workspace_service`、`legacy_adoption_service`、`recycle_recovery_service`、`white_model*`、`previs*`、`native_assets`、`handoff_service`、`edit_service`、`animatic_service`、`final_service`、`storyboard_adoption_service` | `writing.prepare()` 负责离线编剧任务书成果包在剧本准备阶段的受控发布；`idea_chat.save_manual_creative()` 负责手动创意的剧本准备分类目录、命名与原子发布；`idea_attachments.prepare()` 受控读取文本附档、限制体积与上下文，并且只向模型提交文件名与带边界的文本，不暴露本地路径；`storyboard_files.storyboard_work_plan()` 是无 Tk/Agent 的分镜输入决策服务；`storyboard_rows_service` 负责首帧行与分镜统计；`storyboard_edit_service` 负责已校验分镜 JSON 的原子编辑保存；`asset_batch_service` 负责资产生成登记、本地导入图片的校验/落盘/索引原子发布与失败回滚、资产改名的可恢复双文件同步、图片回收/恢复与索引失败回滚、无人值守资产计划、设置快照去重与重试决定；`asset_detail_service` 负责正典板视角与状态变体缩略图的格式/非空校验、原子复制、资产清单索引发布及失败回滚；`recycle_recovery_service` 只投影项目内或项目库回收清单，并且逐项/整批恢复始终委托 `storage_maintenance.restore_recycle_batch()` 的既有边界与回滚语义；`local_video_settings_service` 负责经 UI 本机预检后的 ComfyUI 工作流副本和项目设置原子发布，并在配置失败时恢复旧文件；`desktop_settings_service` 负责桌面全局项目选择、本机 ComfyUI 与剪映路径偏好的原子发布；`stage_workspace_service` 负责配音、后期和交付页面的既有阶段目录初始化；`legacy_adoption_service` 负责旧目录归位日志的原子发布；`confirm_gates` 负责门禁候选的确认记录读写，读取走 `file_cache`、写入走 `agent.core.save()`；`keyframe_lifecycle_service` 负责首帧导入替换、回收/恢复、状态发布与失败回滚；`video_lifecycle_service` 负责本地视频镜头删除标记、选项发布与失败回滚；`tts_api` 负责整段及逐句配音的媒体优先发布、幂等复用查询与可续跑时间轴登记；`speech_api`（REQ-S01-71）负责语音输入的后端路由与设置：`create_session()` 按 `backend` 分流 `offline`/`cloud`，设置为内置默认合并 `data/语音识别.json`（`save_settings()` 校验后写入，发布器由 L4 `speech_settings_ui` 注入，入口在模型管理底栏），云端密钥按变量名经 `model_pool` 取，出站只经 `platform_tools.open_websocket`；`offline_asr_client` 负责离线子进程会话：引擎宿主单例常驻、stdio JSON-Lines 喂 PCM/收逐句、超时强杀与崩溃中文原因，引擎不可用时可降级注入的云端会话；`audio_import_service` 负责用户选择音频的格式/非空校验、临时复制校验与原子落盘；`subtitle_export_service` 负责 SRT 与对白脚本的受控阶段目录发布及角色名渲染；`delivery_import_service` 是项目上下文与结果契约的采用方：只消费 L3 注入的 `ProjectContext`，以阶段解析器定位交付目录，不自行拼接项目路径；成功或业务失败均返回 `service_contract` 结果对象，源文件保持不动。其他待迁移范围由 `维护记录/架构统一基数.json` 登记，两项已于 2026-10-04 经用户授权解冻，后续迁移见路线图；均不导入 Tk 或配置页面。 |
| L3 编排   | `stage_flow`、`stage_exec`、`stage_parallel`、`stage_config`、`stage_models`、`stage_handler_registry`、`storyboard_direct_api`、`audio_direct_api`、`video_prompt_direct_api`、`image_direct`、`skill*`、`workflow*`、`agent_dispatch`、`engine`、`legacy_compat`、`qwen_adapter`、`asset_auto_batch_service`、`asset_batch_execution`、`asset_batch_controller`、`asset_page_controller`、`editing_page_controller`、`keyframe_page_controller`、`media_page_controller`、`page_navigation_controller`、`pet_broadcast_state`、`stage_completion_service`、`stage_publication`、`stage_write_preparation_service`、`stage_asset_gateways`、`stage_animatic_gateways`、`stage_previs_gateways`、`stage_gate_gateways`、`stage_handoff_gateways`（均自 `stage_execution_service` 拆出并由其按原名转发）、`stage_download_inbox_service`、`desktop_startup_service`、`desktop_automation_service`、`desktop_auto_state`、`idea_chat_controller`、`idea_semantic_brief_service`、`recycle_recovery_controller`、`storyboard_final_controller`、`storyboard_page_controller` | 三虎启动唯一经 `stage_handler_registry.start()`；无人值守资产批量生成由 L3 编排服务调用执行器；`workflow_engines` 与 `codex_tasks.prepare_task()` 均须在启动进程或创建任务工件前执行统一请求上下文预算预检；`project_context_factory.project_context()` 是 `ProjectContext` 的唯一构造实现；`stage_execution_service.project_context` 静态重导出同一函数，并由交付编排注入统一二进制发布器；`publish_stage_text()`／`publish_stage_bytes()`／`publish_stage_bundle()` 均以调用方既有校验器与索引更新器完成“校验→原子发布→索引更新”，任一写入或索引失败会回滚本次成果并抛错（R1619 起实际定义在 `stage_publication`，`stage_execution_service` 按原名转发；“首次修改前复制历史成果”在 `stage_write_preparation_service`，下载收件箱在 `stage_download_inbox_service`）；L2 仅接收注入发布器，不得反向导入 L3；`desktop_startup_service.DesktopStartupController` 仅编排注入的首帧延迟、空闲选择和取消回调；`desktop_auto_state.AutoState` 是八条自动流程的状态容器（R1985：Desktop.auto 持有，R2017 起旧 auto_* 属性名已退役，一律读写 `self.auto.<字段>`，`AutoStateHolderMixin` 只懒建缺失的 `auto`），队列工厂由 L4 注入，不持有 Tk 或阶段权威；`desktop_automation_service.DesktopAutomationScheduler` 仅编排注入的周期回调、取消、受控异常与到期轮询，不持有 Tk 或阶段状态；`idea_chat_controller.IdeaChatController` 仅保存注入的对话请求、发送节流、附件引用和流式进度回调状态；`RecycleRecoveryController` 只汇总注入的当前项目与项目库根目录，不持有 Tk 控件，委托 L2 列表与恢复；`AssetBatchController` 保存资产批量页的表单默认值、勾选状态、模型检测与启动前门禁，只调用注入的计划及选择服务；`asset_page_controller.AssetPageController` 保存资产主页面的类别筛选、勾选初始化和批量目标判定，不持有 Tk 控件或写入项目数据；`editing_page_controller.EditingPageController` 保存后期页的视频可用性、自动粗剪报告与完成状态文案，只调用注入的工作室对象；`pet_broadcast_state`（R2006，R1983 J5）是 Pet 播报状态容器：`notice`／`last_status`／判重指纹／压住的话／推进节流六件由 `Pet.bstate` 持有，判重、压住、节流只经它的方法写，`notice`／`last_status` 经 `PetBroadcastAliasesMixin` 作为公开属性转发，四个下划线旧名已于 R2015 退役；同模块的 `PetOfferState`（R2281，J-Pet）收「要不要一键执行」追问的五件状态，由 `Pet.offer` 持有、只由 `PetVoiceMixin` 写，旧 `_offer_*` 五个属性名已退役；`pet_cloud_hint.CloudHintState`（J-Cloud）同理收云朵滚动小字的定时器／开关／左沿／用户聚焦四件，由 `Cloud.hint_state` 持有、只由 `CloudHintMixin` 写；`page_navigation_controller`（R2001，R1983 J4）是桌面换页的无 Tk 函数集：侧栏视频模式、整页缓存的失效判据与缓存项、换页前的分镜采用与来源选择闸门、关闭窗口时要取消的 after 任务名单（页序号表与取消回调由 L4 注入，计时器取消仍由 `Desktop.cancel_timers` 驱动）；`media_page_controller`（R1997，R1983 J3）是制作后段页（首帧／连贯性／视频／配音／后期／交付）的无 Tk 函数集：就绪签名、首帧批次可否派发的判据、连贯性清单表格行、剪映查找候选、字幕状态文案、交接包选版、交付页状态行与视频工作区解析，读文件的口子由 `MediaPagesMixin` 注入，Mixin 只留控件与事件绑定；`keyframe_page_controller.KeyframePageController` 保存首帧页多分镜行归属、首帧路径校验与按来源分批选择，不持有 Tk 控件或写入项目数据；`storyboard_final_controller.FinalStoryboardController` 保存定稿预览、编辑和镜头导航状态，只调用既有选择与原子保存边界，并可接收后台读取完成的预览结果；`storyboard_page_controller.StoryboardPageController` 保存初步分镜文件表的扫描、选择、按钮门禁和回收编排，只调用既有目录、选择和回收服务；阶段成果核验由无 Tk 服务处理，桌面视频状态经回调注入；L3 不持有 Tk 控件 |
| L4 UI   | `desktop`、`desktop_direct_dispatch`、`desktop_storyboard_direct`、`desktop_audio_direct`、`desktop_video_prompt_direct`、`desktop_image_direct`、`pet_ui`、`pet_cloud`、`pet_cloud_text`、`pet_cloud_geometry`、`pet_cloud_shape`、`pet_cloud_tail`、`pet_cloud_timing`、`pet_cloud_hint`、`pet_cloud_place`、`responsive_ui`、`ui_theme`、`ui_widgets`、`ui_composer_style`、`ui_splash`、`ui_tooltip`、`ui_stage_popups`、`ui_rounded`、`ui_motion`、`ui_scroll`、`ui_hover_fade`、`ui_usage_indicator`、`ui_usage_detail`、`cell_hover`、`prompt_window`、`asset_detail`、`storyboard_table_ui`、`cloud_video`、`local_video`、`skill_panel`、`skill_panel_support`、`stage_model_picker`（阶段配置按钮右侧的单级「供应商 · 模型」选择器）、`pet_models_tabs`（模型管理窗口的调用方式页签与模态分类 Mixin）、`desktop_page_registry`、`desktop_tk_gc`、`desktop_automation_tick`、`desktop_layout`、`desktop_pet_bridge`、`desktop_async_tasks`、`desktop_page_nav`、`desktop_lifecycle`、`desktop_login_gate`、`workflow_settings_dialog`、`qwen_setup_dialog`、`project_settings_dialog`、`cloud_assets_dialog`、`asset_prompt_check_dialog`、`asset_reference_prompts_dialog`、`script_line_numbers`、`script_find_bar`、`script_outline`、`script_reading`                                | `ui_widgets` 是主/次按钮与卡片的 Tk 组件唯一入口，只消费 L1 `ui_tokens`；`ui_composer_style`（R2082）承载剧本准备页输入框的附件卡片与框内图标按钮样式，由 `ui_widgets.setup_styles` 注入按钮配置函数调用；`pet_cloud_text` 承载云朵框的无 Tk 文本规整与转播文案；`pet_cloud_geometry`、`pet_cloud_shape` 与 `pet_cloud_tail` 分别承载图元几何、形状规则和尾巴曲线的无 Tk 计算；`storyboard_table_ui` 承载分镜文件表的 Tk 构建与渲染；`desktop` 保留 Tk 窗口、页面控件和事件绑定，在启动边界只注入回调给无 Tk 控制器；`desktop`、`storyboard_files`、`asset_batch` 禁止直连进程或网络，只可使用静态登记的 `platform_tools`／`native_apps` 入口；`workflow_settings_dialog`（R2184，R2178 J1）只承载工作流「调用设置」窗口的 Tk 控件与事件，配置解析、校验与保存（`workflow_settings.save_flow()`）留在 `workflow_settings`，后者导入时不再加载 tkinter。`qwen_setup_dialog`（R2189，R2178 J2）只承载 Qwen Code「API 设置」窗口的 Tk 控件与事件，连接设置的读取、校验与密钥读写留在 `qwen_setup`，后者导入时同样不加载 tkinter。UI 延迟加载只能经 `ui_plugin_registry.module()`；登记表外名称拒绝加载，保留按页延迟导入行为 |
| L5 入口   | `app`、`app_icon`、`app_shortcut`                                                                                                                            | 入口只装配依赖，当前 `app.py` 仍动态调用流程  |

### 阶段专属全流程 SKILL

`skills/01 剧本准备SKILL/`、`02剧本整理SKILL/`、`03初步分镜SKILL/`、`05资产管理SKILL/`、`06连贯性SKILL/`、`07分镜定稿SKILL/`、`08首帧管理SKILL/`、`09白模预演SKILL/`、`10视频生成SKILL/`、`11配音字幕SKILL/`、`12后期剪辑SKILL/` 与 `13质检交付SKILL/` 各含一个 `pipeline-*.skill.md`。剧本准备另有 `screenplay-production-line`、`screenplay-writer`、`script-forging`、`短剧编剧搭子`、`编剧技能集` 五个外部包总入口；其审计归属统一以 `script_contract.AUDIT` 为准，均不产生 manifest。
它们从 `skills/00全流程SKILL/` 的全流程资料抽出阶段职责，并以 `dependsOn` 表达强前置关系；
`pipeline-editing` 同时依赖视频与配音字幕。原始全流程资料保留为只读参考。`skill_registry.Registry.files()`
只递归扫描 `skills/01`—`12` 阶段目录内的常规 `.skill.md`；根目录遗留 `.skill.md` 只在该懒扫描中按 frontmatter `stage` 安全归档，无法归档则保留并报告。`00全流程SKILL` 与其他根目录资料包不扫描。阶段下外部包只登记根部 `SKILL.md`（集合包可用根部 README）为一个总入口，不展开内部子目录。该扫描仅由阶段配置面板显式触发，未进入启动路径。

`workflow_engines` 与 `qwen_adapter` 仅在模型最终报告正文非空时发布正式报告；空响应保留原始响应记录供诊断，不覆盖成果。

`script_contract.write_structured_script()` 在原子发布前拒绝空白结构剧本正文，避免阶段存在空成果。

`writing_tools.write_file()` 在剧本模型工具入口拒绝空白正文，确认有实际内容后才经原子写入器发布阶段成果。

`subtitle_export_service.publish_srt_text()` 是字幕 SKILL 指定目标的唯一发布入口，统一负责行尾校验与原子写入；`skill_tools` 仅生成字幕文本并委派该服务。

`video_lifecycle_service.save_video_options()` 已接管视频页资产/声音选项的原子发布，当时记录的架构门禁为 92/92、默认冒烟为 8/8（历史值，非当前基线）；该服务不提交、上传或调用白模视频。`desktop_settings_service.publish_desktop_settings()` 已接管桌面全局的项目选择、本机 ComfyUI 与剪映路径偏好发布；`stage_workspace_service` 已接管分镜导入、音频、后期和交付页面的既有阶段目录初始化；`asset_context.ensure_browser_directory()` 已接管资产页面分类目录初始化；`legacy_adoption_service` 已接管旧目录归位日志的原子发布，仍由 UI 保持日志失败不阻断项目打开；`storyboard_selection.remember_final_view()` 已接管手动与无人值守定稿收尾的查看偏好发布；`edit_service.save_automatic_assemble_marker()` 与 `handoff_service.save_automatic_handoff_marker()` 分别接管无人值守自动粗剪、自动交接完成标记的发布；`subtitle_export_service` 已接管字幕 SRT 与对白脚本的阶段目录发布；`delivery_import_service.import_final_master()` 已接管最终成片格式/非空校验与交付阶段复制；`white_model_service` 已接管白模视频/工程的格式与非空校验、临时复制校验、原子发布和预演记录更新；`cloud_video_service` 已接管云视频会话配置、工作区偏好、工作室设置及桌面视频模式偏好的发布。UI 只提供剧集、角色资产和状态提示。

### 请求上下文预算

工作流引擎与 Codex 任务创建在启动进程或创建任务工件前共用上下文预算预检。预算服务会先合并完全重复的大段上下文，保留首份完整内容并写明去重摘要；唯一内容仍超过上限时安全拒绝，不启动模型或创建任务工件。

项目上下文装配唯一实现为 L3 `project_context_factory.project_context()`；`stage_execution_service.project_context` 仅静态重导出同一函数以兼容既有调用。阶段并行、分镜选择、白模、工作流任务和剧本 API 直接复用装配模块，避免为构造上下文反向依赖阶段总编排器。装配不扫描或写入项目。

项目接续快照：`workflow_context.snapshot()` 消费由 L3 注入的 `ProjectContext`，直接调用同层 `storyboard_catalog_service.catalog()`；L2 不得反向导入编排层。桌面与剧本 API 在进入快照前装配上下文。提示词入口传入预计算 `data` 时仍接受项目路径；省略 `data` 时必须传入上下文，避免 L2 自行构造依赖。

`script_contract.STAGE_LOCK_REQUIREMENTS` 统一阶段必填锁，`PRODUCTION_LOCK_DEFINITIONS` 统一标签与别名；剧本准备要求交付形态、赛道、素材来源三项（旧项目缺后两项时只提示不阻断），首帧／视频／白模要求画幅、视频模型版本、交付形态三项，其他阶段无必填锁。提示词头部仅在白名单阶段裁剪，其他阶段保留既有锁展示。

### 剧本 SKILL 角色审核与编剧风格

角色职责位于 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 的「定向注入（00 包）」，由同一次回复内的三个内部角色承担：编剧角色审核五阶门控、编辑角色审核 12 个情绪节拍、演员角色完成台词七维诊断与语速自检；`writing_quality.prompt()` 在四份规则齐全时把同一角色分工写入辅助质检交付契约。旧框架及适配器的移除证据见 [R1441](tasks_round/tasks_round_1441_result.md)、[R1442](tasks_round/tasks_round_1442_result.md)。

用户可编辑的只有项目级「编剧风格」：保存在项目 `skill_config.json` 的 `script.writer_style`（旧项目的编剧规则读取时迁入，下次保存不再写旧键，其余旧框架键忽略），由 `stage_config.writer_style()` 读取，`workflow_settings.writer_style_prompt()` 在剧本准备的桌面任务书与直连 API 的 system 中各注入一次，空风格不占请求。写作取消异常为 `writing_api.WritingCancelledError`。Claude 桌面程序模型不再作为受控 CLI 对话模型，`writing_api.selected_model()` 对其返回空，走桌面 Agent 通道。

## 4. 三虎 Agent 的阶段定义

R1263：剧本准备发送边界由 `writing_api.capture_request()` 统一解析模型身份、调用方式和 `workflow_settings.current()` 的有效配置；`freeze_skills()` 内联所选技能及直接 Markdown/文本引用并冻结正文，API 与桌面复用该快照。失效选择、缺失引用、空技能和超出请求字符预算均阻止发送，不截断或静默省略；完整请求另沿用既有发送前预算闸门。`idea_chat` 保存脱敏的选中/加载清单、字数及 SHA-256，气泡显示本次加载结果，旧记录不伪造凭据。共享阶段成果、角色顺序、重试及发布边界不变。

唯一阶段定义来源：`pet_bus.STAGES`、`pet_bus.STAGE_NAMES`。

| 序号  | ID                 | 阶段    | 核心产物                                             |
| ---:| ------------------ | ----- | ------------------------------------------------ |
| 01  | `script`           | 剧本准备  | 剧本/设定、`emotion_curve.json`、离线编剧任务书成果包。                    |
| 02  | `script_structure` | 剧本结构  | 原稿整理为结构剧本；新稿写入 `02剧本结构/结构剧本/`，同时派生写入 `02剧本结构/output/` 的角色／场景／道具三份 manifest 并核验（`script_contract.write_structure_manifests`／`structure_manifest_problems`）；具体读写目标由 `script_contract` 解析；需求与设计见 `docs/stages/`。 |
| 03  | `storyboard`       | 初步分镜  | 已采用的分镜 JSON（`03初步分镜/分镜拆分/`，文件名由模型产出；采用时由 `storyboard_selection.sync_draft_outputs` 同步写 `03初步分镜/output/storyboard_draft.json` 与派生的 `scene_breakdown.json`，完成与 SG-A 经 `draft_problems` 核验，见 `docs/stages/S03_初步分镜.md` REQ-S03-43/44）；需求与设计见 `docs/stages/`。 |
| 04  | `animatic`         | 分镜预演  | 参考图与分镜提示词生成的预演草图、Animatic、`animatic_manifest.json`。 |
| 05  | `assets`           | 资产管理  | `assets.json`、正典板、锚点。                            |
| 06  | `continuity`       | 连贯性清单 | `continuity_ledger.json`、`continuity_ledger.md`、`continuity_issues.json`，另发布共享锚点库与三元组字典。 |
| 07  | `final`            | 分镜定稿  | 采用分镜、提示词、批次 ID；落盘为 `07分镜定稿/分镜/<EP>_分镜定稿[_日期]/` 下的 `episode.json` + `assets.json`。 |
| 08  | `keyframe`         | 首帧管理  | 非空首帧；来源证据记在已采用分镜 JSON 的每镜 `frame_evidence`；阶段核验通过时 `stage_completion_service.publish_stage_manifest()` 把各镜首帧回执写入 `08首帧管理/output/frames.json`（只是回执，完成仍以 `frames_ready` 核验为准）。 |
| 09  | `previs`           | 白模预演  | 可播放预演；镜头级记录 `预演记录.json` 存于白模成果目录（项目目录之外），通过校验的预演视频在项目内留副本 `09白模预演/assets/<镜头>/`，并登记汇总索引 `09白模预演/output/previs.json`（权威名；SKILL 里的 `previsManifest` 是它的逻辑别名）。工作区预览缺失时 SG-05 退回该索引判就绪。 |
| 10  | `video`            | 视频生成  | 视频任务/片段；`output/` 下 `videos.json`／`video_manifest.json` 由 `Studio.publish_manifest` 写出；每项目上限 100 镜。 |
| 11  | `audio`            | 配音与字幕 | 音轨、字幕；完成凭据为人工确认的 `成果确认/<hash>.json`；`output/` 下 `voice.json`／`subtitles.json`／`audio_manifest.json` 由 `stage_execution_service.refresh_audio_manifests` 在成果变化后写出，不作完成证据。 |
| 12  | `edit`             | 后期剪辑  | 粗剪成片 `MASTER.mp4`（落 `13质检交付/导出成片/`）、`edit_manifest.json`／`edit_bundle.json`、EDL／FCPXML；需求与设计见 `docs/stages/`。 |
| 13  | `delivery`         | 质检与交付 | 已确认成片的成果确认清单（`成果确认/*.json`，含与成片绑定的 `qc` 质检结论）、`qc_report.json`／`delivery.json`／`delivery_manifest.json`／`delivery_report.md`、商用待填资料。 |

三虎逐步发布 `stage.started/completed/failed/retrying/executing/paused` 等事件，记录检查点，支持恢复；手动模式仅在模板标记确认的步骤等待用户，全自动模式不等待但逐步播报。门禁为资产/锚点 → SG01 → 连贯性 → SG02 → 定稿 → SG03 → 首帧 → SG04 → 预演 → SG05 → 视频。

## 5. 并行配置

来源：`stage_parallel.py`；当前应用进程共享最大在途数为 **8**。`parallel_map` 未显式注入控制器时也使用 `shared()`，Animatic 与 SKILL 并行入口共用额度；显式注入仅供受控装配和测试。此限制不提供跨进程机器总额度，不把多个应用进程的合计并发称为 8；供应商账户限额仍需独立配置与校验。

| 阶段               | 单元    | 并发上限 | 内部串行 | 重试/失败处理   |
| ---------------- | ----- | ----:| ---- | --------- |
| script           | 无     | 1    | 否    | 2 次，阻塞。   |
| script_structure | 无     | 1    | 否    | 2 次，阻塞。   |
| storyboard       | scene | 3    | 是    | 2 次，阻塞。   |
| animatic         | batch | 3    | 是    | 2 次，转人工。  |
| assets           | asset | 5    | 是    | 2 次，阻塞。   |
| continuity       | 无     | 1    | 否    | 2 次，阻塞。   |
| final            | 无     | 1    | 否    | 2 次，阻塞。   |
| keyframe         | shot  | 6    | 否    | 2 次，转人工。  |
| previs           | batch | 3    | 是    | 2 次，转人工。  |
| video            | batch | 3    | 是、限流 | 指数退避，转人工。 |
| audio            | track | 5    | 是    | 2 次，转人工。  |
| edit             | 无     | 1    | 否    | 2 次，阻塞。   |
| delivery         | check | 4    | 否    | 2 次，生成报告。 |

## 6. 模型路由配置

| 层次    | 来源                                                         | 行为                                                                |
| ----- | ---------------------------------------------------------- | ----------------------------------------------------------------- |
| 模型池   | `model_pool.py`、`配置/宠物/配置.json`                            | 保存模型 ID、显示名、厂商、地址、协议、能力、成本、上下文和密钥变量名；不保存密钥值。                      |
| 协议    | `model_router.ModelAdapter`                                | 支持 OpenAI 兼容 `chat/completions`、`responses`、Anthropic `messages`。 |
| 阶段配置  | `<项目>/skill_config.json`、`stage_config.py`                 | 每阶段保存模型与已选 SKILL；默认“自动”。                                          |
| 三虎测试  | `pet_test_service.py`、`<项目>/工作流任务/宠物/测试.json`       | 增量自检的重复运行、成功率摘要和脱敏失败用例名台账；不保存原始日志。                    |
| 三虎优化  | `pet_performance_service.py`、`<项目>/工作流任务/宠物/优化.json` | 只比较离线基准 JSON 的耗时指标；超过 40% 才提示，不执行或改写基准脚本。 |
| 覆盖顺序  | `ModelRouter.override/select()`                            | 单次 > 项目 > 全局 > SKILL 首选 > 能力/预算匹配 > SKILL 降级 > Flash 默认。          |
| 三虎自身  | `agent.models`、`resolve_agent_model()`                     | default/chat/escalate/fallback 四档；复杂自动任务优先升级模型，失效则降级。             |
| 桌面引擎  | `chatgpt-desktop`、`claude-desktop`、`workflow_settings.current()` | 显式选择桌面模型时使用对应本机 Agent；选择 GPT/Anthropic API 且对应本机程序可启动时，也会优先交给本机程序，启动失败才按兼容 API 回退。阶段配置在用户改选时显示该按需探测结果。 |
| 密钥/预算 | `model_secrets.py`、`.env`、`private/.env`、`skill_budget.py` | 只按变量名取密钥，并按 Token/图片/视频额度判定。                                      |

出厂模型池：DeepSeek V4 Flash/Pro、GPT-4o、Qwen-Max、ChatGPT Desktop · Codex、Claude Desktop · Claude Code；用户新增模型以模型池实际记录为准。

## 7. 数据文件清单

| 路径模式                                       | 格式            | 用途                     |
| ------------------------------------------ | ------------- | ---------------------- |
| `配置/宠物/配置.json`                            | JSON          | 全局三虎设置、模型池、Agent 模型档位。 |
| `配置/SKILL/预设.json`                               | JSON          | 按阶段保存的可复制预设。            |
| `<项目>/skill_config.json`                   | JSON          | 项目 13 阶段模型和 SKILL。     |
| `<项目>/data/项目接续.json`                      | JSON          | 项目进度和接续上下文。            |
| `<项目>/01剧本准备/`、`<项目>/02剧本结构/` | Markdown、JSON | 当前剧本阶段目录；由 `stage_path_service` 与 `script_contract` 解析。 |
| `<项目>/03初步分镜/`—`<项目>/13质检交付/` | JSON、媒体、Markdown | 当前后续阶段目录，细表见 PROJECT_MAP；JSON、MD 分别放受控的 output/、docs/。 |
| `<项目>/episode/assets.json` | JSON | 历史资产清单路径，仅说明旧项目兼容，不授权新写入。 |
| `<项目>/episode/continuity_ledger.json` | JSON | 历史台账路径，仅说明旧项目兼容。 |
| `<项目>/episode/*_manifest.json` | JSON | 历史产物路径；当前目标以阶段路径服务及对应契约为准。 |
| `<项目>/logs/sanhu_progress.log`             | 文本            | 三虎进度播报日志。              |
| `logs/claude_empty_response.log`           | 文本            | 脱敏 Claude 空正文协议元数据。    |
| `.env`、`private/.env`、`private/密钥/*.dpapi` | 环境/加密数据       | 密钥来源；不得导出。             |
| `tasks/`、`tasks_round/`                    | Markdown、JSON | 任务轨迹与开发轮结果。            |

## 8. 各阶段输入输出

| 阶段    | 输入                           | 输出                                                              | 格式                |
| ----- | ---------------------------- | --------------------------------------------------------------- | ----------------- |
| 剧本准备  | 创意、剧本阶段输入、接续                | 创意简报、台词润色、情绪曲线                                                  | Markdown、JSON     |
| 剧本结构  | 权威服务解析的被采用自然剧本 | 结构剧本（角色/场景/道具/分场内容），位于 `02剧本结构/结构剧本/`，旧 writing/ 只读兼容；提取 SKILL 可另产出 manifest、世界观（manifest 是否必须产出待定，见 `docs/stages/S02_剧本结构.md` REQ-S02-23） | Markdown、JSON     |
| 初步分镜  | “初步分镜”栏已选的结构剧本                        | 分镜 JSON（经校验后采用）；场次拆分 `scene_breakdown.json` 由已采用分镜派生并核验（REQ-S03-44）                                                     | JSON              |
| 分镜预演  | 分镜初稿、共享参考图、临时声音 | 预演草图、Animatic、`animatic_manifest.json` | 视频、JSON |
| 资产管理  | 分镜、资产需求、参考图                  | 资产表、正典板、锚点                                                      | JSON、图片           |
| 连贯性清单 | 被采用分镜、资产（含锚点）                | 台账（含冲突裁决）、问题闭环登记 `continuity_issues.json`                    | JSON、Markdown     |
| 分镜定稿  | 初稿、资产、台账                     | 采用分镜、提示词、批次                                                     | JSON、Markdown     |
| 首帧管理  | 定稿镜头、提示词、资产参考                | 首帧、缩略图、清单                                                       | 图片、JSON           |
| 白模预演  | 首帧、镜头时间线                     | 预演、清单                                                           | 视频、JSON           |
| 视频生成  | 预演、提示词、关键帧                   | 片段、任务、清单                                                        | 视频、JSON           |
| 配音与字幕 | 时间线、对白、音色                    | 音轨、字幕、清单                                                        | 音频、SRT、JSON        |
| 后期剪辑  | 视频、音频、字幕                     | 预览/成片、剪辑清单                                                      | 视频、JSON           |
| 质检与交付 | 成片、字幕、清单                     | 质检报告、交付包                                                        | Markdown、JSON、压缩包 |

## 9. 现有 Agent / 角色清单

| 名字                               | 归属阶段      | 职责                                |
| -------------------------------- | --------- | --------------------------------- |
| 三虎主控                             | 全局        | 状态、模板、阶段调度、播报、检查点、恢复、模式和门禁。       |
| 模型路由 Agent                       | 全局        | 按覆盖、能力、预算、可用性和降级选择模型。             |
| 剧本工作流 Agent                      | 剧本准备/剧本结构 | 将创意和 SKILL 送入模型，维护 writing 和受控工具。 |
| 分镜 Agent                         | 初步分镜/定稿   | 拆场、镜头链、资产核验、初稿/定稿。                |
| 资产 Agent                         | 资产管理      | 候选、正典板、资产表和恢复。                    |
| 连贯性 Agent                        | 连贯性清单     | 冻结锚点、漂移和冲突审计；实现为本地规则 `continuity_ledger`，不调用模型。 |
| 首帧 Agent                         | 首帧管理      | 批量生成、导入、质检和重试。                    |
| 白模 Agent                         | 白模预演      | 场景、走位、机位和预演。                      |
| 视频 Agent                         | 视频生成      | 本地/云任务、轮询、限流和重试。                  |
| 音频字幕 Agent                       | 配音与字幕     | TTS、多角色音色、字幕对齐和导出。                |
| 后期 Agent                         | 后期剪辑      | 粗剪、转场、背景音乐、平台导出（不含音效）。   |
| 质检/交付 Agent                      | 质检与交付     | 画面/音频/字幕/合规/风格检查、报告、归档。           |
| ChatGPT Desktop / Claude Desktop | 任意显式选择阶段；或 GPT/Anthropic API 且本机程序可启动 | 本机桌面 Agent 引擎；后者是运行时本机优先，启动失败回退原 API。         |

## 权威源补充条款（自 AGENTS §2.2 迁入）

以下条款原写在 `AGENTS.md` §2.2，因属专题／路线图细则迁入此处，AGENTS 保留一句话摘要。

### 权威源表细则

| 类别 | 细则 |
| --- | --- |
| L2 写服务结果 | 第 1 项已解冻（2026-10-04 用户授权）；分批复用 `service_contract` 四字段结果，每轮最多 3 个 service；同轮迁移调用方、测试与采用方棘轮，不创造第三种返回形状。采用方和待迁移范围以 `维护记录/架构统一基数.json` 为准；执行顺序见路线图。 |
| 项目操作上下文 | 第 2 项已解冻（2026-10-04 用户授权）；按路线图顺序复用 L3 注入的 `project_context.ProjectContext`，每轮最多 3 个 service；采用方和待迁移范围以 `维护记录/架构统一基数.json` 为准。 |
| 阶段成果发布器 | `stage_execution_service.publish_stage_text()`／`publish_stage_bytes()`／`publish_stage_bundle()`；L2 写服务只能接收 L3 注入的发布器，音频导入经 `import_stage_audio()`、自动粗剪完成标记经 `save_automatic_assemble_marker()`、自动交接完成标记经 `save_automatic_handoff_marker()`、首帧删除／恢复／替换经 `delete_stage_keyframe()`／`restore_stage_keyframe()`／`replace_stage_keyframe()` 注入 |
| 正式 JSON 读写 | 读取优先 `file_cache.read_json()`，写入只经 `agent.core.save()`／`save_text()` 或 L3 发布器；L2 不得直接向正式路径 `json.dump()` 或裸写入 |
| 持久化产物版本 | rtifact_schema：正式 JSON 产物的版本、必备字段与迁移入口；新写入写 schema_version，读取侧容忍缺版本 |

### SKILL 注册表与制作锁（R2862）

总控宪法已废止（R2862，任务书《共享输入框与skill体系重构》）：① SKILL 唯一来源是 `skill_registry`（内置 `skills/01—13` ＋ 用户 `data/skills/`，同名用户优先），不再有总控清单投影；② 各阶段 SKILL 勾选始终由用户自由决定，面板只提供勾选与技能说明；③ 制作锁是项目级事实，经弹窗预选写入 `production_locks`，门禁（`stage_handler_registry` 与简报门禁）对手动与自动路径一律生效；④ 完整安装 skill 的登记由 R2881 落地（`skill_import_service.import_from_repo` 薄 git 层）；R2893 落地共享输入框：`skill_command`（L2 纯解析：`/skill名`／`/阶段别名`／`/子引擎` 三形态、补全排序）与 `desktop_shared_input.SharedStageInput`（L4 单实例底部输入框，`[技能][附件]|TextArea|[模型][发送]`，`/` 与 `Esc` 经 `ShortcutRegistry` 登记）；发送门禁 `upstream_send_error` 复用 `stage_parallel.evaluate`（UPSTREAM_BLANK／BLOCKED 拦截）与 `stage_completion_service.completion_evidence`（无门禁行阶段看紧邻上游），模型快照在发送瞬间经 `writing_api.capture_request` 捕获、在途期切换只影响下一次请求；R2898 落地 13 页接线：`desktop_shared_send`（L4 发送分流——`/阶段` 切页、`/skill`／`/子引擎` 解析到目标阶段 `open_flow_agent`、自由文本 script 走 `send_message` 其余走流程 Agent、无流程阶段回状态栏提示；会员闸门复用 `account.stage_gate`），`Desktop._init_body_and_status` 建唯一实例、`PageNavMixin._sync_shared_input` 随 `page_index` `set_stage`／`pack_forget`，剧本页 composer 的 `idea_input` 直接指向共享 Text 且页面级绑定按 `page_index` 守卫；按模型隔离取消——`idea_transcript.model_history_path` 统一返回 `01剧本准备/创意对话/对话.json`，`_merge_legacy_model_files` 在首次读取把旧 `模型会话/`、`<提供方>/<模型>/` 目录按 `at` 归并去重进统一文件（只迁移不删），模型名降为行内署名与视图筛选。

## 当前架构门禁清单

（自 AGENTS §5 迁入，内容未改。）

当前架构门禁清单（`tests/architecture/`）：总数以 `python smoke_test.py --architecture` 当轮输出为准，基线只增不减。

- 卡片与忙碌状态补充：`test_card_boundary.py`、`test_busy_state_boundary.py`。
- 分层与一致性：`test_agents_md.py`、`test_layers.py`、`test_no_circular_import.py`、`test_path_authority.py`、`test_stage_paths.py`、`test_storyboard_edit_boundary.py`、`test_storyboard_final_selection_boundary.py`。
- 写入与删除边界：`test_atomic_write_boundary.py`、`test_asset_batch_ledger_boundary.py`、`test_asset_batch_settings_boundary.py`、`test_asset_detail_binding_boundary.py`、`test_asset_generated_import_boundary.py`、`test_asset_image_import_boundary.py`、`test_asset_plan_publication_boundary.py`、`test_asset_rename_boundary.py`、`test_asset_image_removal_boundary.py`、`test_asset_image_restore_boundary.py`、`test_audio_import_boundary.py`、`test_cloud_video_settings_boundary.py`、`test_continuity_publication_boundary.py`、`test_delivery_import_boundary.py`、`test_desktop_settings_boundary.py`、`test_edit_publication_boundary.py`、`test_final_bundle_boundary.py`、`test_handoff_publication_boundary.py`、`test_keyframe_delete_boundary.py`、`test_keyframe_restore_boundary.py`、`test_keyframe_replace_boundary.py`、`test_keyframe_reference_publication_boundary.py`、`test_legacy_adoption_boundary.py`、`test_local_video_settings_boundary.py`、`test_manual_creative_publication_boundary.py`、`test_previs_routing_publication_boundary.py`、`test_stage_workspace_boundary.py`、`test_structured_script_write_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_tts_publication_boundary.py`、`test_video_delete_boundary.py`、`test_video_options_boundary.py`、`test_video_prompt_publication_boundary.py`、`test_video_publication_boundary.py`、`test_white_model_import_boundary.py`、`test_writing_preparation_path_boundary.py`、`test_deletion_gateway.py`、`test_remove_authority.py`、`test_recycle_service.py`。
- 潜伏缺陷防复发（R1854）：`test_subprocess_timeout_boundary.py`（等子进程必须带 timeout）、`test_workflow_dir_ratchet.py`（手拼“工作流任务”只许减少）、`test_read_json_definitions.py`（`read_json` 同名定义不得新增）、`test_pet_error_log_boundary.py`（三虎 errors 必须有上限）；`test_skill_config_path_single_entry.py`（`skill_config.json` 文件名只在 `stage_layout` 写一次）；`test_atomic_write_boundary.py` 另以 AST 限定直接 `os.replace`／`Path.replace` 只在登记写入器内且只许减少。
- 剧本重命名边界：`test_script_rename_boundary.py`。
- 阶段/UI 契约：`test_dynamic_import_registry.py`、`test_stage_command_contract.py`、`test_completion_gate.py`、`test_event_bus_boundary.py`、`test_skill_dependency_dag.py`、`test_pipeline_stage_io_contract.py`、`test_skill_reference_injection.py`、`test_project_entry_boundary.py`。
- 依赖与平台边界：`test_import_error_boundaries.py`、`test_model_provider_boundary.py`、`test_platform_opening.py`、`test_platform_process_boundary.py`、`test_migrated_ui_boundaries.py`。
- 体验与布局：`test_responsive_layout_contract.py`、`test_combobox_boundary.py`。
- 出站与文档预算：`test_outbound_http_authority.py`（直接建连只许在 `platform_tools`）、`test_http_boundary.py`（`urlopen`／`build_opener` 只许在 `http_client` 与存量白名单，白名单只减不增）、`test_agent_doc_budget.py`（规则文件体积与链接）、`test_rule_guard_map.py`（规则→守卫登记，暂无守卫的规则只许减少）、`test_gate_selfaudit.py`（5 个关键门禁的坏／好样本自审）、`test_type_check_baseline.py`（开发期类型检查基线只许减少）、`test_skill_package_pins.py`（外部技能包固定提交与内容树哈希）、`test_test_move_guard.py`（测试搬家轮只许移动文件与修 import）。
- 启动预算：`test_startup_budget.py`。
- 源码文本契约锁：`test_source_text_contracts.py`（原散落在功能测试里的 `inspect.getsource` 断言，内容未动）。
- 历史兼容门面：`test_legacy_facade_manifest.py`。
- 轮次与基线／测试卫生：`test_round_baselines.py`、`test_status_page_size.py`（状态页 ≤500 行）、`test_skip_hygiene.py`、`test_silent_exception_ratchet.py`、`test_module_size_ratchet.py`、`test_todo_comment_snapshot.py`、`test_static_hygiene.py`、`test_function_size_ratchet.py`、`test_complexity_ratchet.py`、`test_print_ratchet.py`、`test_shared_state_ratchet.py`（Mixin 组合类多写者 self 属性只许减少，R1984）、`test_stable_registration.py`。
- 文档先行锚定：`test_requirement_traceability.py`（`docs/stages/` 里 ✅ 须有测试锚定，历史欠账见 `维护记录/需求锚定基线.json`，只许减少）。
- 覆盖率审计棘轮：`test_coverage_audit_ratchet.py`、`test_secret_sink_audit.py`、`test_coverage_baseline.py`、`test_branch_coverage_floor.py`。
  行覆盖度量为定向测量：工具 `scripts/coverage_report.py`（`sys.settrace`，零第三方依赖），基线 `维护记录/覆盖率基线.json`；只记基线＋核心路径下限，不重跑测量，口径与诚实边界见 `tasks_round/tasks_round_1616_result.md`。
  L0/L1 分支覆盖棘轮（T8.4）：工具 `scripts/branch_coverage_report.py`，基线 `维护记录/分支覆盖率基线.json`，下限 `维护记录/分支覆盖率下限.json`（只许上调）；决策点双结果口径与排除项见 runbook §11，均为定向测量非全量套件覆盖率。
  密钥静态审计仅覆盖有限函数内传播，支持范围与漏检／误报边界见 `tasks_round/tasks_round_1054_result.md` D–F，不将零命中解释为全路径安全。
- JSON／服务／统筹补充：`test_confirm_gates_json_boundary.py`、`test_context_menu_boundary.py`、`test_data_table_boundary.py`、`test_dialog_boundary.py`、`test_button_boundary.py`、`test_file_dialog_boundary.py`、`test_simpledialog_boundary.py`、`test_idea_attachment_publication_boundary.py`、`test_input_boundary.py`、`test_json_io_boundary.py`、`test_keyframe_batch_json_boundary.py`、`test_local_previs_json_boundary.py`、`test_notification_boundary.py`、`test_previs_automation_json_boundary.py`、`test_previs_batch_json_boundary.py`、`test_previs_monitor_json_boundary.py`、`test_project_context_boundary.py`、`test_service_return_contract.py`、`test_shortcut_registry_boundary.py`、`test_skill_orchestrator_json_boundary.py`、`test_stage_display_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_text_component_boundary.py`、`test_tooltip_boundary.py`、`test_ui_icons_boundary.py`、`test_scrollbar_theme_boundary.py`、`test_token_boundary.py`、`test_copy_entry_boundary.py`、`test_unification_ratchet.py`、`test_video_navigation_json_boundary.py`、`test_white_model_json_boundary.py`、`test_white_model_service_json_boundary.py`、`test_workflow_settings_json_boundary.py`、`test_writing_api_json_boundary.py`、`test_writing_publication_boundary.py`。
- 剧本 API 低层反向依赖（R2443）：`test_writing_api_stage_config_boundary.py`（读阶段模型走 L1 `stage_model_value`、回退口令走 L2 `idea_script_heuristic`，不得反向依赖 L3 `stage_config`／`workflow_tasks`）。

新增或删除架构测试时，必须在同一轮更新以上清单、架构基线和结果报告；不得只更新测试而遗漏本入口说明。
