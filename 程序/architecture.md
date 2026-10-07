# AI 漫剧制作助手：架构清单

> 初稿基于 2026-09-25 源码；后续按轮次追加，R1022 校正文档口径。本文的 R 编号段落是历史记录，不是当前验收凭据。阶段、路径与事件以 AGENTS.md §2.2 所列代码为准；开发验证规则只在 AGENTS.md §5 定义。

## 1. 目录树

R1040（J5 分轮 1）：`ui_icons.IconLoader.return_arrow()` 支持显式颜色，缓存键包含宿主、尺寸与颜色；默认白色保持兼容。页面迁移在下一轮验证，当前不代表 J5 已完成。

R1041（J5 分轮 2）：app 日志视图清空、desktop 最后剧本回收确认／取消、video_navigation 返回均经语义按钮；返回使用主题色共享箭头及次按钮。现有按钮边界扩展 tk/ttk 静态导入及赋值别名 canary，架构实测 306/306（原 301，新增 5 个用例，测试文件数量不变）；不声称覆盖动态导入、名称遮蔽或跨函数数据流。

协作基础设施：`维护记录/基准脚本/worktree_ledger.py` 只读汇总 Git 工作树、租约及显式容器残差；`--plan` 仅输出待确认命令。`round_claim.py next` 拒绝 detached HEAD 分配轮次。两者不进入生产执行链，不读用户项目正文。

```text
程序/
├─ agent/                 通用 Agent、媒体与视频服务适配器
├─ assets/                图标和程序静态资源
├─ batch_frames_tool/     批量首帧辅助工具
├─ data/                  程序内置数据、示例数据
├─ episode/               默认/演示剧集输出
├─ logs/                  运行、模型与三虎日志
├─ private/               本机私有配置和加密密钥副本
├─ scripts/               Python 维护/迁移工具
├─ skills/                可注册 SKILL 与阶段模板
│  ├─ templates/          12 阶段 YAML 流程模板
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

注册规则：`skill_registry.py` 只递归扫描 `skills/01`—`12` 阶段目录内的 `.skill.md`，并以目录编号归类 SKILL；根目录遗留 `.skill.md` 仅在用户打开阶段配置后的懒扫描中，按 frontmatter 的 `stage` 自动移动到对应阶段目录，无法判定、目标缺失或重名时保留原文件并报告。`00全流程SKILL` 和其他根目录资料包不作为阶段候选。同时只在同一次懒扫描中，将各阶段目录下一层、根部含 `SKILL.md`（或集合包 README）的外部包注册为**一个总入口**，绝不递归展开包内子 SKILL。剧本阶段的总入口还必须登记到 L0 `script_contract.AUDIT`：它们均为支撑性技能，受控默认值不声明 output 或 manifest，不能据此虚构产物归属。`stage_config.py` 将每阶段选中的模型和 SKILL 存入项目 `skill_config.json`，读取时清理失效项并将错阶段项归位。

统筹预设契约：`workflow_settings.WORKFLOW_PRESETS` 的结构为 `label → {package, stage_skills{阶段 → [注册id]}, locks[{key, label, options}]}`。项目配置在 `skill_config.json` 顶层以 `workflow: {name, skill_ref, lock: {统筹名称: {键: 值}}}` 投影；`lock` 按统筹名称分命名空间，切换统筹时不得丢弃旧值。统筹声明可提供锁键和默认值，但外部包 frontmatter 仍不是执行字段来源，继续遵守注册表不信任原则。

| 名字（文件路径）                                                                                                                                                                   | 阶段    | 一句话职责                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------------------------- |
| 各阶段内容 SKILL（`skills/01 剧本准备SKILL/`） | 剧本准备 | 创意剧本的台词润色与情绪节奏标注。 |
| 各阶段内容 SKILL（`skills/02剧本整理SKILL/`） | 剧本结构 | 将原稿组织为结构化剧本，并提取资产需求、整理世界观。 |
| 各阶段内容 SKILL（`skills/03初步分镜SKILL/`） | 初步分镜 | 拆场、生成镜头链、设计镜头语言并校验节奏和时长。 |
| 各阶段内容 SKILL（`skills/04资产管理SKILL/`） | 资产管理 | 检索/生成候选、版权筛选、去重排序、确认后入库。 |
| 各阶段内容 SKILL（`skills/05连贯性SKILL/`） | 连贯性清单 | 冻结锚点并审计角色、场景、服装、道具和跨批次漂移。 |
| 各阶段内容 SKILL（`skills/06分镜定稿SKILL/`） | 分镜定稿 | 对齐资产、锁定一致性、校验定稿、输出提示词和快照。 |
| 各阶段内容 SKILL（`skills/07首帧管理SKILL/`） | 首帧管理 | 首帧批量生成、质检重试及缩略图缓存。 |
| 各阶段内容 SKILL（`skills/08白模预演SKILL/`） | 白模预演 | 生成白模场景、走位、机位路径、动作和节奏预览。 |
| 各阶段内容 SKILL（`skills/09视频生成SKILL/`） | 视频生成 | 视频批量提交、模型分流、轮询、质检和失败重跑。 |
| 各阶段内容 SKILL（`skills/10配音字幕SKILL/`） | 配音与字幕 | 多角色配音、情绪核验、字幕对齐及 SRT/ASS 导出。 |
| 各阶段内容 SKILL（`skills/11后期剪辑SKILL/`） | 后期剪辑 | 合成、配乐、预览、转场和多平台导出。 |
| 各阶段内容 SKILL（`skills/12质检交付SKILL/`） | 质检与交付 | 质检、合规与风格检查、归档和交付报告。 |

阶段模板位于 `skills/templates/`：`script`、`script_structure`、`storyboard`、`asset`、`continuity`、`final`、`keyframe`、`previs`、`video`、`audio`、`edit`、`delivery` 各一份 YAML。每份均含读取/分析、生成（可确认）和写入产物步骤。

## 3. 分层判定

R1074：L3 `exit_maintenance.launch_cleanup()` 集中退出后的三路派发顺序、正常／强制退出差异、可选启动 OSError 降级与固定大小的脱敏派发摘要。L4 只传程序位置及退出意图；工作进程保持独立，既有清理实现、范围和回收策略不变。摘要只报告 scheduled／launch-failed／skipped-force／not-attempted，完成状态明确 unobserved；不把启动当作清理完成，不新增等待、重试或持久化出口。

R1073：L3 `pet_chat_coordinator.ChatCoordinator` module 独占待单击任务，合并单／双击消歧、取消与守护关闭规则。L4 `pet_ui.Pet` 保留既有入口并注入调度与视图动作 adapter；测试采用内存队列／视图 adapter。这个 seam 不传入整个 Pet，不复制 chat／visible／shape，动画、Cloud 资源、问候与静默策略仍由原所有者管理。interface 的 locality 与 depth 由跨入口顺序测试证明，不以文件缩短作验收；删除此 module 会把共享协调规则与状态重新分散回 UI。

| 层       | 模块/职责                                                                                                                                                      | 判定                           |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| L0 合同   | `pet_bus`、`script_contract`、`asset_contract`、`service_contract`、`project_context`、`stage_layout`、`stage_path_service`、`storyboard_paths`、`prompt_templates`、`shot_batches`、`continuity_ledger`       | `service_contract.ServiceResult` 定义四字段结果口径；`project_context.ProjectContext={root, stage_resolver, settings_snapshot, cache}` 定义项目上下文注入契约。采用方及待迁移范围以 `维护记录/架构统一基数.json` 和对应门禁为准，本表不缓存数量。两项于 2026-10-04 经用户授权解冻，按序每轮最多迁移 3 个 service，执行规则见 `维护记录/架构统一路线图_v2.md`。`pet_bus.emit_safe()` 是跨模块状态的唯一安全发送器，`pet_agent._emit()`／`pet_ui._emit()` 仅作受控转发；`broadcaster` 只写用户可见文本日志。`stage_path_service` 是新写/旧读的唯一阶段路径口径；`script_contract.save_natural_script()` 是手改自然剧本的内容闸门与原子发布口径；允许被上层依赖，不应反向依赖 UI/编排；`stage_layout.validate_stage_contract()` 保证目录阶段与 `pet_bus.STAGES` 同序；`json_md_rows()` 的人读 MD 路径只使用当前编号阶段目录下的 `docs/` |
| L1 基础设施 | `model_pool`、`model_secrets`、`pet_llm`、`file_cache`、`hash_backend`、`storage_maintenance`、`workspace_maintenance`、`diagnostic_capture`、`line_endings`、`ui_tokens`                                                    | `diagnostic_capture` 仅采集程序拥有日志的脱敏现场与已知启动指标，导出固定白名单且不扫描项目目录；模型小环违反此层应无反向依赖的目标；`ui_tokens` 是 design_tokens.md 的只读代码化事实来源；本机路径/浏览器/进程和短 TCP 探测统一由 `platform_tools` 适配，不得由 UI 直连；`workspace_maintenance` 只做仓库级可再生卫生（`__pycache__`、超期 `.selftmp`、已并净的 `.wt` 工作树），用户可见删除仍唯一走 `storage_maintenance.recycle_paths()`，`git gc` 只在开发脚本 `scripts/repo_health.py`            |
| L2 业务   | `writing*`、`idea_chat`、`idea_attachments`、`storyboard*`、`asset*`、`keyframe*`、`video_lifecycle_service`、`cloud_video`、`local_video`、`tts_api`、`audio_import_service`、`subtitle_timing`、`subtitle_export_service`、`delivery_import_service`、`confirm_gates`、`desktop_settings_service`、`stage_workspace_service`、`legacy_adoption_service`、`recycle_recovery_service`、`white_model*`、`previs*`、`native_assets`、`handoff_service`、`edit_service`、`final_service`、`storyboard_adoption_service` | `writing.prepare()` 负责离线编剧任务书成果包在剧本准备阶段的受控发布；`idea_chat.save_manual_creative()` 负责手动创意的剧本准备分类目录、命名与原子发布；`idea_attachments.prepare()` 受控读取文本附档、限制体积与上下文，并且只向模型提交文件名与带边界的文本，不暴露本地路径；`storyboard_files.storyboard_work_plan()` 是无 Tk/Agent 的分镜输入决策服务；`storyboard_rows_service` 负责首帧行与分镜统计；`storyboard_edit_service` 负责已校验分镜 JSON 的原子编辑保存；`asset_batch_service` 负责资产生成登记、本地导入图片的校验/落盘/索引原子发布与失败回滚、资产改名的可恢复双文件同步、图片回收/恢复与索引失败回滚、无人值守资产计划、设置快照去重与重试决定；`asset_detail_service` 负责正典板视角与状态变体缩略图的格式/非空校验、原子复制、资产清单索引发布及失败回滚；`recycle_recovery_service` 只投影项目内或项目库回收清单，并且逐项/整批恢复始终委托 `storage_maintenance.restore_recycle_batch()` 的既有边界与回滚语义；`local_video_settings_service` 负责经 UI 本机预检后的 ComfyUI 工作流副本和项目设置原子发布，并在配置失败时恢复旧文件；`desktop_settings_service` 负责桌面全局项目选择、本机 ComfyUI 与剪映路径偏好的原子发布；`stage_workspace_service` 负责配音、后期和交付页面的既有阶段目录初始化；`legacy_adoption_service` 负责旧目录归位日志的原子发布；`confirm_gates` 负责门禁候选的确认记录读写，读取走 `file_cache`、写入走 `agent.core.save()`；`keyframe_lifecycle_service` 负责首帧导入替换、回收/恢复、状态发布与失败回滚；`video_lifecycle_service` 负责本地视频镜头删除标记、选项发布与失败回滚；`tts_api` 负责整段及逐句配音的媒体优先发布、幂等复用查询与可续跑时间轴登记；`audio_import_service` 负责用户选择音频的格式/非空校验、临时复制校验与原子落盘；`subtitle_export_service` 负责 SRT 与对白脚本的受控阶段目录发布及角色名渲染；`delivery_import_service` 是项目上下文与结果契约的采用方：只消费 L3 注入的 `ProjectContext`，以阶段解析器定位交付目录，不自行拼接项目路径；成功或业务失败均返回 `service_contract` 结果对象，源文件保持不动。其他待迁移范围由 `维护记录/架构统一基数.json` 登记，两项已于 2026-10-04 经用户授权解冻，后续迁移见路线图；均不导入 Tk 或配置页面。 |
| L3 编排   | `stage_flow`、`stage_exec`、`stage_parallel`、`stage_config`、`stage_models`、`stage_handler_registry`、`skill*`、`workflow*`、`agent_dispatch`、`engine`、`integrations`、`asset_auto_batch_service`、`asset_batch_execution`、`asset_batch_controller`、`asset_page_controller`、`editing_page_controller`、`keyframe_page_controller`、`stage_completion_service`、`desktop_startup_service`、`desktop_automation_service`、`idea_chat_controller`、`recycle_recovery_controller`、`storyboard_final_controller`、`storyboard_page_controller` | 三虎启动唯一经 `stage_handler_registry.start()`；无人值守资产批量生成由 L3 编排服务调用执行器；`workflow_engines` 与 `codex_tasks.prepare_task()` 均须在启动进程或创建任务工件前执行统一请求上下文预算预检；`project_context_factory.project_context()` 是 `ProjectContext` 的唯一构造实现；`stage_execution_service.project_context` 静态重导出同一函数，并由交付编排注入统一二进制发布器；`stage_execution_service.publish_stage_text()`、`publish_stage_bytes()`、`publish_stage_bundle()` 均以调用方既有校验器与索引更新器完成“校验→原子发布→索引更新”，任一写入或索引失败会回滚本次成果并抛错；L2 仅接收注入发布器，不得反向导入 L3；`desktop_startup_service.DesktopStartupController` 仅编排注入的首帧延迟、空闲选择和取消回调；`desktop_automation_service.DesktopAutomationScheduler` 仅编排注入的周期回调、取消、受控异常与到期轮询，不持有 Tk 或阶段状态；`idea_chat_controller.IdeaChatController` 仅保存注入的对话请求、发送节流、附件引用和流式进度回调状态；`RecycleRecoveryController` 只汇总注入的当前项目与项目库根目录，不持有 Tk 控件，委托 L2 列表与恢复；`AssetBatchController` 保存资产批量页的表单默认值、勾选状态、模型检测与启动前门禁，只调用注入的计划及选择服务；`asset_page_controller.AssetPageController` 保存资产主页面的类别筛选、勾选初始化和批量目标判定，不持有 Tk 控件或写入项目数据；`editing_page_controller.EditingPageController` 保存后期页的视频可用性、自动粗剪报告与完成状态文案，只调用注入的工作室对象；`keyframe_page_controller.KeyframePageController` 保存首帧页多分镜行归属、首帧路径校验与按来源分批选择，不持有 Tk 控件或写入项目数据；`storyboard_final_controller.FinalStoryboardController` 保存定稿预览、编辑和镜头导航状态，只调用既有选择与原子保存边界，并可接收后台读取完成的预览结果；`storyboard_page_controller.StoryboardPageController` 保存初步分镜文件表的扫描、选择、按钮门禁和回收编排，只调用既有目录、选择和回收服务；阶段成果核验由无 Tk 服务处理，桌面视频状态经回调注入；L3 不持有 Tk 控件 |
| L4 UI   | `desktop`、`pet_ui`、`pet_cloud`、`pet_cloud_text`、`pet_cloud_geometry`、`pet_cloud_shape`、`pet_cloud_tail`、`responsive_ui`、`ui_theme`、`ui_widgets`、`cell_hover`、`prompt_window`、`asset_detail`、`storyboard_table_ui`、`skill_panel`、`ui_plugin_registry`                                | `ui_widgets` 是主/次按钮与卡片的 Tk 组件唯一入口，只消费 L1 `ui_tokens`；`pet_cloud_text` 承载云朵框的无 Tk 文本规整与转播文案；`pet_cloud_geometry`、`pet_cloud_shape` 与 `pet_cloud_tail` 分别承载图元几何、形状规则和尾巴曲线的无 Tk 计算；`storyboard_table_ui` 承载分镜文件表的 Tk 构建与渲染；`desktop` 保留 Tk 窗口、页面控件和事件绑定，在启动边界只注入回调给无 Tk 控制器；`desktop`、`storyboard_files`、`asset_batch` 禁止直连进程或网络，只可使用静态登记的 `platform_tools`／`native_apps` 入口；UI 延迟加载只能经 `ui_plugin_registry.module()`；登记表外名称拒绝加载，保留按页延迟导入行为 |
| L5 入口   | `app`、`app_icon`、`app_shortcut`                                                                                                                            | 入口只装配依赖，当前 `app.py` 仍动态调用流程  |

### 已验证的发布边界

R806 将三虎增量自检账本纳入 L3 发布边界：`pet_test_service.record()` 不再自行发布项目 JSON，`stage_execution_service.poll_pet_test_check()` 通过 `pet_test_gateway()` 注入原子发布器；`pet_ui` 只经 `stage_handler_registry.start()` 启动并由 L3 轮询。重复次数、失败用例脱敏摘要与失败时不落账本的语义不变。

R808 将定稿分镜编辑发布纳入 L3 发布边界：`storyboard_edit_service.save_edited_json()` 仅接收注入的 JSON 发布器，`storyboard_final_controller` 只委托 `stage_execution_service.save_edited_stage_storyboard()`，并由 `storyboard_edit_gateway()` 装配。路径格式校验、原子失败不覆盖旧文件与返回路径语义不变。

R807 将白模预演进度发布纳入 L3 发布边界：`previs_progress_service.publish()` 与 Blender 回调安装仅接收注入的文本发布器，`stage_execution_service` 通过 `previs_progress_gateway()` 装配，宿主兼容门面仍以原有 `publish()`／`install_blender_progress()` 名称委托 L3。进度 JSON 字段、原子发布与真实帧数回调时序不变。

R805 将三虎优化账本纳入 L3 发布边界：`pet_performance_service.record()` 不再自行发布项目 JSON，`stage_execution_service.poll_pet_performance_check()` 通过 `pet_performance_gateway()` 注入原子发布器；`pet_ui` 只委托 L3 启动与轮询。离线基准脚本、阈值比较、摘要格式与失败时不落账本的语义不变。

R713 将确认门禁的项目确认记录 JSON 纳入“读走缓存、写走原子服务”迁移：`confirm_gates.confirmations()` 改经 `file_cache.read_json()` 读取，`record()`／`forget()` 仍只经 `agent.core.save()` 原子发布；缓存随发布失效，确认项的缺失／损坏回退与门禁语义不变。

R714 将工作流调用设置 JSON 纳入“读走缓存、写走原子服务”迁移：`workflow_settings.load()`、Qwen 模型同步及设置窗保存均经 `file_cache.read_json()` 读取既有项目设置，写入仍只经 `agent.core.save()` 原子发布；缓存随发布失效，设置格式、默认值和 UI 行为不变。

R715 将剧本 API 已确认简报读取纳入同一正式 JSON 入口：`writing_api._complete_brief()` 改经 `file_cache.read_json()` 读取当前阶段或旧目录的只读兼容简报，既有 `script_contract.brief_document()` 复核、错误语义与任何写入路径不变；原子重发后缓存读可立即观察新简报。

R716 将白模批处理对正式分镜 `episode.json` 的消费纳入同一 JSON 入口：`previs_batch_service.prepare_batch()` 改经 `file_cache.read_json()` 读取选镜源，任务清单仍仅经 `agent.core.save()` 原子发布；分镜原子重发后，下一次批处理会立刻按新镜头清单校验，不复用旧选镜。

R717 将首帧批次候选对正式分镜 `episode.json` 的消费纳入同一 JSON 入口：L2 `keyframe_batch.candidates()` 改经 `file_cache.read_json()` 读取镜头与首帧状态，分镜原子重发后下一次候选计算立即使用新清单；候选校验、路径越界保护和首帧生成语义不变。

R718 将无人值守白模编排派发前的正式分镜读取纳入同一 JSON 入口：L3 `previs_automation.start()` 改经 `file_cache.read_json()` 冻结本批镜头快照；外部 `ffprobe` 的进程内 JSON 响应仍按外部响应解析，不混入项目数据缓存。选镜变更门禁、原子快照发布与后台执行语义不变。

R719 将白模预演记录的正式 JSON 读取纳入同一入口：L2 `white_model_service.read_record()` 改经 `file_cache.read_json()` 读取 `预演记录.json`，原子重发后下一次读取立即刷新；历史 `preview` 到 `project_file` 的兼容转换、格式校验和 `agent.core.save()` 写入语义不变。

R720 将白模页面对当前正式分镜的读取纳入同一入口：L4 `local_previs.show()` 改经 `file_cache.read_json()` 读取镜头清单，保留页面构建、默认勾选、复杂度路由和所有交互语义；写入边界不变。

R1096 白模页面启动、线上入口和刷新复用既有 `adjust_targets()`，即时读取勾选优先／高亮兜底的工作目标；不缓存选择，不改变查看行规则或发布边界。

R721 将白模入口选择器对当前正式分镜的读取纳入同一 JSON 入口：L4 `white_model.choose_previs()` 改经 `file_cache.read_json()` 获取可选镜头；弹窗、选择与进入白模预演的交互语义不变。

R712 将三虎项目运行状态 JSON 作为第二个“读走缓存、写走原子服务”的迁移：`skill_orchestrator.load_project_status()` 改经 `file_cache.read_json()` 读取，`save_project_status()` 保持 `agent.core.save_text()` 原子发布；缓存会随发布失效，运行状态语义和容错回退不变。

R711 将自动交接完成标记纳入同一 L3 发布器注入边界：`handoff_service.save_automatic_handoff_marker()` 只接收目标与发布器，`stage_execution_service.save_automatic_handoff_marker()` 负责定位 edit 阶段并注入 `publish_stage_text()`；桌面不再直连 L2。标记字段、路径和原子发布语义保持不变。

R710 将自动粗剪完成标记纳入 L3 发布器注入：`edit_service.save_automatic_assemble_marker()` 仅接收已定位目标与发布器，`stage_execution_service.save_automatic_assemble_marker()` 负责定位 edit 阶段并注入 `publish_stage_text()`；桌面只调用 L3 编排入口。该迁移保留标记 JSON 的字段、路径和原子发布语义，其他 L2 写服务仍逐批迁移。

R709 将白模预演进度 JSON 作为“读走缓存、写走原子服务”的首批迁移：`previs_progress_service` 读取经 `file_cache.read_json()`，发布保留 `agent.core.save_text()`；缓存失效由原子发布的既有 `published` 事件保证。专门门禁禁止该 L2 服务退回裸读写正式路径，其他 JSON 路径继续逐批审计。

R708 将音频导入列为首个“L3 发布器注入”迁移：`audio_import_service.import_audio()` 只接收调用方给定的发布器，`stage_execution_service.import_stage_audio()` 注入统一的 `publish_stage_bytes()`，桌面不再直连 L2。该迁移不改变格式、非空和发布后大小校验；其他 L2 写服务仍按路线图逐批迁移。

当前架构门禁的文件清单以 `AGENTS.md`「当前架构门禁清单」为入口，并由 `test_agents_md.py` 强制与 `tests/architecture/test_*.py` 的实际集合完全一致；总数以 `python smoke_test.py --architecture` 当轮输出为准，基线只增不减。R706 增加 `service_contract` 与交付成片导入试点的结果契约门禁，后续 L2 写服务须逐批迁移。R567 将历史兼容入口收口到 `legacy_compat.FACADE_MANIFEST`，逐项记录唯一所有者、真实调用方与 2027-03-31 淘汰日；`tests/architecture/test_legacy_facade_manifest.py` 的 AST 门禁拒绝未登记调用与到期未处置 facade。R565 在 `workflow_context` 定义“剧本完整索引／非剧本阶段摘要”两种上下文策略，`desktop` 在保留原任务、SKILL、阶段契约与续接语义的前提下选择策略；`workflow_context_budget` 对最终初始/续接提示统一去重、执行既有上限并生成不含正文的预算元数据，收据可观察阶段、策略、字符数、上限和余量。R564 将剧本结构页 `Desktop.script_structure()` 的颜色、字体与间距完全收口到 L1 `ui_tokens`，并以 L4 `PrimaryButton`／`SecondaryButton` 承担高亮和次级操作的状态样式；组件悬停态保持可读的主色文字，页面不再自行定义按钮视觉值。 R563 将缓存失效收口为 L1 `file_cache` 的 `published`、`recycled` 与 `externally_overwritten` 事件：`agent.core` 原子发布和 `storage_maintenance` 回收/恢复在文件操作成功后通知该权威，统一淘汰 JSON、文本及字节缓存；外部适配器覆写时必须显式通知，mtime/哈希只保留为旧路径安全兜底，页面不得以刷新承担一致性。R562 使定稿大 JSON 读取按需后台完成、以页面代次取消旧结果并以空闲分片写入 Tk，仍复用 `file_cache` 的签名/内容哈希缓存；资产缩略图任务绑定可销毁页面控件，离页由既有任务失活检查丢弃。R561 将剧本准备文件表改为无 Tk 服务逐项发现、L4 每批 24 条空闲提交及销毁/刷新代次取消，最终仍按修改时间排序；R560 新增迁移 UI 边界门禁，防止服务重新导入 Tk、视图重新直连进程/网络或新增未登记适配器入口。

R841 固化事件总线边界：跨模块状态发送只能走 `pet_bus.emit_safe()`，`pet_agent._emit()` 与 `pet_ui._emit()` 是仅有的受控转发器；`Bus.emit()` 的实现仅留在 L0，`broadcaster` 则仅用于 `desktop`／`pet_ui` 的用户可见文本日志，不能成为状态传输旁路。

R842 开始收口后台任务生命周期：桌面唯一的主动异步入口 `Desktop.async_()` 将代次提交、逻辑取消、成功／失败收尾集中给无 Tk 的 `BackgroundTaskLifecycle`。任意 Python 线程不可安全地被强杀，因此取消的语义是拒绝迟到结果进入 UI；模型、媒体及预演的专用进程仍维持其既有可终止协议，后续按同一边界逐批迁移。

R843 将该生命周期扩到自动粗剪与自动交接包：两类后台文件任务各自拥有代次，关闭窗口后会拒绝队列中的迟到结果，成功／失败仍只由主线程完成原有页面刷新、退避和自动链推进。自动视频因含连续进度消息，保留为下一批，避免以不同的交付结构掩盖取消边界。

R788 将桌面 12 个制作页名称收口到 `pet_bus.STAGES`／`STAGE_NAMES`：`desktop.PAGES` 只生成阶段页，另保留“参考网站”这一工具页；`test_stage_display_boundary.py` 防止页面名称退回手写。R789 复核基准趋势门禁时实测架构套件为 156/156，基线据实校正；该轮仅补充离线基准归档的窗口与测量条件回归，不进入产品启动路径。

R721 后架构门禁基线为 118/118，默认冒烟基线仍为 8/8。R722 后架构门禁基线为 119/119，默认冒烟基线仍为 8/8。R723 后架构门禁基线为 120/120，默认冒烟基线仍为 8/8。

R722 将视频生成入口的正式项目 JSON 读取纳入同一入口：L4 `video_navigation` 保留页面级“坏文件即空表”容错包装，底层改委托 `file_cache.read_json()`；分镜、首帧、云端配置和本地模型的展示文案与优先级不变。

R723 将白模监视页的制作进度 JSON 纳入同一入口：L2 `previs_monitor.progress_of()` 改经 `file_cache.read_json()` 读取，保留进度文件缺失/损坏时显示“制作中”的容错及浏览器监视页刷新节奏。

R724 将字幕 SRT 与对白脚本两类音频阶段成果纳入 L3 发布器注入边界：L2 `subtitle_export_service.export_srt()`／`export_dialogue_script()` 只准备文本并接收调用方注入的发布器，`stage_execution_service.export_stage_srt()`／`export_stage_dialogue_script()` 注入 `publish_stage_text()`，桌面只调用 L3 编排入口。文件名、UTF-8 BOM 编码、空对白拒绝与发布后返回路径语义不变。

R724 后架构门禁基线为 122/122，默认冒烟基线仍为 8/8。

R725 将剧本模型工具、直接 API 自动保存和 HOLLMWOOD 原稿三条剧本成果路径纳入 L3 发布器注入边界：L2 `writing_tools.write_file()` 与 `writing_api._write_script_raw()` 均只接收发布器，`stage_execution_service.reply_to_writing()` 统一注入 `publish_stage_text()`，桌面不再直调 `writing_api.reply()`。无发布器的写请求明确拒绝，绝不降级直写；剧本内容闸门、路径和模型交互语义不变。

R725 后架构门禁基线为 124/124，默认冒烟基线仍为 8/8。

R726 将剧本准备的用户创意附档归档纳入 L3 发布器注入边界：L2 `idea_attachments.store()` 只接收发布器，`stage_execution_service.archive_idea_attachments()` 注入 `publish_stage_text()`，后台控制器只经 L3 发起。附档类型、内容上限、Markdown 命名、非空校验和读取语义不变。

R726 后架构门禁基线为 126/126，默认冒烟基线仍为 8/8。

R727 将后期剪辑的用户维护清单纳入 L3 发布器注入边界：L2 `edit_service.save_editing_checklist()` 只接收发布器，`stage_execution_service.save_stage_editing_checklist()` 注入 `publish_stage_text()`，桌面仅调用 L3 编排入口。通用发布器默认拒绝空正文；仅该 L3 入口以显式 `allow_empty=True` 保留用户清空清单的原有语义，L2 无权自行放宽。

R727 后架构门禁基线为 126/126，默认冒烟基线仍为 8/8。

R728 将剪映交接包纳入 L3 发布器注入边界：L2 `handoff_service.publish_bundle()` 只准备受控的文件描述并接收发布器，`stage_execution_service.publish_handoff_bundle()` 负责阶段目录定位、逐份原子字节发布、自动包的完整构建后切换及旧自动包回收；桌面仅注入 L3。镜头顺序、字幕、说明文案、自动标记和手动包“一事一目录”的语义不变。

R728 后架构门禁基线为 127/127，默认冒烟基线仍为 8/8。

R729 将剧本准备离线工作区纳入 L3 发布器注入边界：L2 `writing.prepare()` 只校验并组织任务书、剧集模板、SKILL 位置与附档文件描述，`stage_execution_service.publish_writing_preparation()` 负责剧本阶段目录定位和完整成果包的原子发布；`app.py` 仅注入该 L3 发布器。任务书命名、模板内容、附档复制与当前编号阶段语义不变。

R729 后架构门禁基线为 128/128，默认冒烟基线仍为 8/8。

R730 将剧本准备的用户可见创意文件纳入 L3 发布器注入边界：L2 `idea_chat.save_reply()`／`save_manual_creative()` 只校验并组织 Provider、模型、创意版本、分类目录与文件内容描述，`stage_execution_service.publish_idea_creative()` 负责剧本阶段目录定位与原子发布；桌面仅注入该 L3 发布器。模型下载、手动创意、文件命名与每版三类分类目录的既有语义不变。

R1087 将正式回复的纯路径计算集中到 L2 `idea_chat.reply_path_parts()`；下载保存与 L3 Agent 任务书共同使用，不通过伪发布器取路径。桌面入口显式启用正式交付条款并固定本次时间；API 默认不启用。内部工作稿保留，正式稿仍优先，三类目录和文件名规则不在调用方复制。

R730 后架构门禁基线为 128/128，默认冒烟基线仍为 8/8。

R731 将首帧删除、恢复与替换的 `episode.json` 状态发布完全纳入 L3 发布器注入边界：L2 `keyframe_lifecycle_service` 只接收图片及索引发布器，绝不保留 `save()`／`save_bytes()` 直写回退；`stage_execution_service.delete_stage_keyframe()`／`restore_stage_keyframe()`／`replace_stage_keyframe()` 分别注入 JSON 文本及 PNG 原子发布器，桌面只调用这些 L3 编排入口。镜头编号和路径校验、回收站处理、索引失败时的图片与内存状态回滚均保持不变。

R731 后架构门禁基线为 129/129，默认冒烟基线仍为 8/8。

R732 将首帧生命周期服务接入统一服务结果契约：`keyframe_lifecycle_service.delete_keyframe()`／`restore_keyframe()`／`replace_keyframe()` 成功时均返回 `success(data)`，可预期的参数或状态错误归为 `UserError`，受控发布期间的 I/O 故障归为 `SystemError`；遗漏发布器等编程错误仍抛出。L3 `stage_execution_service` 透传结果，桌面沿用既有失败提示，不改变镜头校验、回收站、回滚或事件绑定语义。

R771 将项目登记与项目内配置的读写、媒体复制及事务回滚纳入 L3 注入边界：L2 `projects.Projects` 必须接收 `stage_execution_service.project_registry_gateway()`，缺少网关即拒绝；该 L3 网关统一注入缓存读取、原子 JSON／字节发布、回滚和复制操作。桌面与项目导入仅装配该网关，项目字段、路径、授权和回滚语义不变。

R732 后架构门禁基线为 130/130，默认冒烟基线仍为 8/8。
R733 后架构门禁基线为 132/132，默认冒烟基线仍为 8/8。R734 后为 133/133；R735 固定架构统一审计范围、处置状态与 AGENTS 清单集合门禁后为 134/134。R775 增设测试 skip 卫生门禁后为 143/143：每项必须引用受控原因常量、说明恢复条件，并与 `维护记录/skip台账.json` 双向一致。R784 增设 Tooltip 首迁边界后为 150/150：截断 SKILL 名称提示只能经 `ui_widgets.Tooltip`，不得退回页面内手写浮层。R785 增设共享图标首迁边界后为 151/151：视频页返回箭头只能经 `ui_icons.IconLoader`，不得重新手写 `PhotoImage`。R786 增设全局滚动条主题边界后为 152/152：横、纵 `TScrollbar` 必须共用 token、active 反馈与唯一主题入口。R787 增设统一复制入口边界后为 153/153：应用文本写剪贴板只能经 `prompt_window.copy_text()`，并必须持有跨进程锁且可对状态栏回执脱敏。

### 阶段专属全流程 SKILL

`skills/01 剧本准备SKILL/`、`02剧本整理SKILL/`、`03初步分镜SKILL/`、`04资产管理SKILL/`、`05连贯性SKILL/`、`06分镜定稿SKILL/`、`07首帧管理SKILL/`、`08白模预演SKILL/`、`09视频生成SKILL/`、`10配音字幕SKILL/`、`11后期剪辑SKILL/` 与 `12质检交付SKILL/` 各含一个 `pipeline-*.skill.md`。剧本准备另有 `screenplay-production-line`、`screenplay-writer`、`script-forging`、`短剧编剧搭子`、`编剧技能集` 五个外部包总入口；其审计归属统一以 `script_contract.AUDIT` 为准，均不产生 manifest。
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

## 4. 三虎 Agent 的阶段定义

唯一阶段定义来源：`pet_bus.STAGES`、`pet_bus.STAGE_NAMES`。

| 序号  | ID                 | 阶段    | 核心产物                                             |
| ---:| ------------------ | ----- | ------------------------------------------------ |
| 00  | `script`           | 剧本准备  | 剧本/设定、五类 manifest、离线编剧任务书成果包。                    |
| 01  | `script_structure` | 剧本结构  | 原稿整理为结构剧本；当前 MD 目录为 `02剧本结构/docs/`，具体读写目标由 `script_contract` 解析。 |
| 02  | `storyboard`       | 初步分镜  | `storyboard_draft.json`。                         |
| 03  | `assets`           | 资产管理  | `assets.json`、正典板、锚点。                            |
| 04  | `continuity`       | 连贯性清单 | `continuity_ledger.json`、检查清单。                   |
| 05  | `final`            | 分镜定稿  | 采用分镜、提示词、批次 ID。                                  |
| 06  | `keyframe`         | 首帧管理  | 非空首帧、`keyframe_manifest.json`。                   |
| 07  | `previs`           | 白模预演  | 可播放预演、`previs_manifest.json`。                    |
| 08  | `video`            | 视频生成  | 视频任务/片段、`video_manifest.json`。                   |
| 09  | `audio`            | 配音与字幕 | 音轨、字幕、`audio_manifest.json`。                     |
| 10  | `edit`             | 后期剪辑  | 预览/成片、`edit_manifest.json`。                      |
| 11  | `delivery`         | 质检与交付 | 报告、交付包、`delivery_manifest.json`。                 |

三虎逐步发布 `stage.started/completed/failed/retrying/executing/paused` 等事件，记录检查点，支持恢复；手动模式仅在模板标记确认的步骤等待用户，全自动模式不等待但逐步播报。门禁为资产/锚点 → SG01 → 连贯性 → SG02 → 定稿 → SG03 → 首帧 → SG04 → 预演 → SG05 → 视频。

## 5. 并行配置

来源：`stage_parallel.py`；全局最大在途数为 **8**。

| 阶段               | 单元    | 并发上限 | 内部串行 | 重试/失败处理   |
| ---------------- | ----- | ----:| ---- | --------- |
| script           | 无     | 1    | 否    | 2 次，阻塞。   |
| script_structure | 无     | 1    | 否    | 2 次，阻塞。   |
| storyboard       | scene | 3    | 是    | 2 次，阻塞。   |
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
| `<项目>/skill_config.json`                   | JSON          | 项目 12 阶段模型和 SKILL。     |
| `<项目>/data/项目接续.json`                      | JSON          | 项目进度和接续上下文。            |
| `<项目>/01剧本准备/`、`<项目>/02剧本结构/` | Markdown、JSON | 当前剧本阶段目录；由 `stage_path_service` 与 `script_contract` 解析。 |
| `<项目>/03初步分镜/`—`<项目>/12质检交付/` | JSON、媒体、Markdown | 当前后续阶段目录，细表见 PROJECT_MAP；JSON、MD 分别放受控的 output/、docs/。 |
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
| 剧本结构  | 权威服务解析的剧本原稿、创意简报 | 结构剧本（角色/场景/道具/分场内容）；当前 MD 位于编号阶段 docs/，旧 writing/ 只读兼容；既有提取 SKILL 可另产出 manifest、世界观 | Markdown、JSON     |
| 初步分镜  | 已确认剧本                        | 场次、分镜初稿                                                         | JSON              |
| 资产管理  | 分镜、资产需求、参考图                  | 资产表、正典板、锚点                                                      | JSON、图片           |
| 连贯性清单 | 分镜、资产、锚点                     | 台账、冲突/修复清单                                                      | JSON              |
| 分镜定稿  | 初稿、资产、台账                     | 采用分镜、提示词、批次                                                     | JSON、Markdown     |
| 首帧管理  | 定稿镜头、提示词、资产参考                | 首帧、缩略图、清单                                                       | 图片、JSON           |
| 白模预演  | 首帧、镜头时间线                     | 预演、清单                                                           | 视频、JSON           |
| 视频生成  | 预演、提示词、关键帧                   | 片段、任务、清单                                                        | 视频、JSON           |
| 配音与字幕 | 时间线、对白、音色                    | 音轨、字幕、清单                                                        | 音频、SRT、ASS、JSON   |
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
| 连贯性 Agent                        | 连贯性清单     | 冻结锚点、漂移和冲突审计。                     |
| 首帧 Agent                         | 首帧管理      | 批量生成、导入、质检和重试。                    |
| 白模 Agent                         | 白模预演      | 场景、走位、机位和预演。                      |
| 视频 Agent                         | 视频生成      | 本地/云任务、轮询、限流和重试。                  |
| 音频字幕 Agent                       | 配音与字幕     | TTS、多角色音色、字幕对齐和导出。                |
| 后期 Agent                         | 后期剪辑      | 时间线、转场、音效、导出。                     |
| 质检/交付 Agent                      | 质检与交付     | 画面/音频/字幕/合规/风格检查、报告、归档。           |
| ChatGPT Desktop / Claude Desktop | 任意显式选择阶段；或 GPT/Anthropic API 且本机程序可启动 | 本机桌面 Agent 引擎；后者是运行时本机优先，启动失败回退原 API。         |

## 维护边界

- R1072：资产详情成功反馈统一由 `asset_detail._complete()` 在页面重建成功后发布；候选采用与重新生成分别委托既有 L3 的 `adopt_asset_plan_choice()`、`reopen_asset_plan_choices()`，封装确认/应用及正典板/锚点撤销顺序。保留第二步失败后的部分完成状态，不引入隐式回滚；Tk 输入与呈现不移动。

- R1057 仅删除 `pet_cloud.Cloud._parent_work_area()` 与 `pet_ui.Pet._build_mode_menu()` 两个无消费者私有方法。云朵仍经 `_place_window()` → `_origin()` 按贴片锚点定位，模式切换仍由猫爪及既有 `set_mode()` 接管；保留模式变量同步、聊天计时、动画取消与退出清理。引用复核和前后定向回归见 R1057 报告，不代表新增实机视觉验收。

- R1056 仅删除 `idea_chat._numbered_path()`、`white_model._base_directory()` 两个零消费者私有辅助函数。创意发布仍经 `stage_execution_service.publish_idea_creative()` 定位当前阶段；白模镜头路径仍委托 `white_model_service.shot_directory()`，四个共享缓存别名及旧读兼容不变。静态引用复核与前后回归见 R1056 报告。

- R1055 仅移除 `cloud_video` 三个无消费者的 `_legacy_*` 私有副本；公开 `provider_label()` 仍委托 `cloud_video_service`，`session_folder()`／`saved_provider_key()` 仍经 `stage_execution_service` 注入上下文。旧会话与凭据只读兼容保留在现行服务，未退役兼容门面或改变云端提交行为；引用扫描与前后回归见 R1055 报告。

- 密钥 sink 静态门禁 `tests/architecture/test_secret_sink_audit.py` 只解析根目录生产 Python AST，不执行取钥代码。R1054 用 30 个假代码子场景覆盖已支持的源／出口、局部别名与容器传播及无来源反例；新增 3 个测试方法，生产算法不变。跨函数返回／参数、调用别名、直接嵌套取钥和容器变更等仍需人工复核，赋值覆盖、嵌套作用域与容器字段可能误报；完整实测矩阵见 R1054 D–F。该审计完成不等于扩展扫描能力或证明全项目安全。

- 视频页结果渲染失败由 `App.tick()` 沿用 `diagnostic_capture.record_degradation()` 记录固定阶段和异常类型，不传结果正文、原始异常文字或项目路径；每个页面实例 30 秒内最多尝试一次，诊断写入失败不得阻断后续查询。关闭后不再消费结果，Tk 销毁与下次调度之间的竞态只在定时器收尾边界处理；不新增日志出口，不重提生成任务。

- 程序日志维护职责唯一归属 `log_maintenance`；运行期由 `Desktop.finish_close()` 在窗口销毁后委托 `exit_maintenance.launch_cleanup()`，其非强制退出分支调用 `log_maintenance.launch_cleanup()`，后台工作进程复用该模块的 `--cleanup` 实现。启动路径不调度日志维护，强制退出不调度；日志启动 OSError 不阻断已经完成的退出，其他异常保持原有传播语义。
- `scripts/maintain_logs.py` 仅是同一实现的显式运维入口，不是另一套运行期调度或保留策略；人工核查先用 `--dry-run`，实际维护会轮转或删除受管日志。本轮仅确认既有链路，不执行真实日志维护；保留、轮转、容量参数仍以 `log_maintenance.py` 现有常量为准。范围仅程序自有 `logs/` 与 `维护记录/` 的受管日志，不递归用户项目。

- 阶段顺序唯一权威：`pet_bus.py`；并行/重试唯一权威：`stage_parallel.py`。
- 阶段命令入口唯一权威：`stage_handler_registry.start()`；`tests/architecture/test_stage_command_contract.py` 约束三虎自动启动、手动分镜与自动分镜均经该 L3 入口，并区分自动失败事件与手动页面结果。
- 资产批次台账正式发布唯一经 `stage_execution_service.asset_batch_gateway()` 注入；L4 的未知提交放开请求经 `release_uncertain_asset_batch()` 委托，L2 不得自行持久化台账。
- 资产详情图片绑定的回滚字节发布唯一经 `stage_execution_service.asset_detail_gateway()` 注入；详情页只调用 L3 的正典板／状态变体编排入口。
- 资产详情辅助文字按语义分批统一：R1051 的推荐理由、正典板页脚、锚点补充说明和参考职责两行共 5 处复用 `ui_widgets.DescriptionBlock`／`TEXT_DESC`，由文字组件门禁精确约束。标题、锁定／就绪状态色、窄缩略图文件名及其他未迁移项仍为后续分类范围，不宣称整页已统一；不得用描述组件默认宽度机械替换窄格文字。
- 生成资产自动导入的临时 PNG 发布唯一使用 `stage_execution_service.asset_batch_gateway()` 注入；缺少发布器时 L2 显式拒绝。
- 最终成片导入的字节发布唯一经 `stage_execution_service.import_delivery_master()` 注入；L2 不得保留复制回退。
- 本地视频设置的工作流、配置及回滚发布唯一经 `stage_execution_service.publish_local_video_settings()` 注入；L2 不得直连正式发布器。
- 本机加密密钥唯一实现入口：`model_secrets.PROTECTOR`，默认实现为同模块 `protect()`；测试替身只能替换该 L1 协议入口，不得恢复 `seedream_api` 反向密钥依赖。
- SKILL 唯一权威：`skills/01`—`12` 阶段目录内的 `.skill.md` 与 `skill_registry.py`；根目录遗留文件仅由懒迁移归档；模型唯一权威：模型管理保存的模型池。
- `<项目>` 是用户项目根目录占位符，非 `程序/episode/` 演示目录。

### 项目回收恢复编排

回收恢复补充（R1091）：`RecycleRecoveryController` 在 L2 完成磁盘恢复后，仅把项目库中此次恢复的一级目录交给注入的 `Projects.register_restored_projects`；不扫描其他项目，不持有 Tk，不自行发布登记。项目服务经原注入网关保存登记，桌面层仅刷新列表；原文件恢复入口与层级不变。

### 历史层级名称的审计边界

R1094 内部等价简化：`pet_cloud.Cloud` 三个关闭入口复用私有定位定时器取消方法，先清空重试标识再取消任务；入口顺序、返回值和异常吞并不变。`storyboard_final` 移除只原样重抛的异常包装，正式发布与工作稿退役顺序不变。不新增模块、分层关系或公开接口。

`asset_gating`、`keyframe`、`keyframe_api`、`previs`、`writing_files`、`writing_roles`、`writing_workflow` 是已有分层表中未实体化的名称：可查初始树和当前树无同名模块，不能称为已迁移模块。R1028 在 `维护记录/架构统一基数.json` 的 `historical_name_audit` 登记现行职责入口；这是职责索引，不是历史重命名证明。两个迁移台账保留 `historical_name_audited` 与原基数，门禁检查缺失名称集合守恒、审计分类及现行模块/符号存在。生产层级、采用方和豁免数量均不变；不得据此宣布第 1、2 项整体完成。
