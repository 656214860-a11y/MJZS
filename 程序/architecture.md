# AI 漫剧助手：架构清单

R1592：模型池 `call_mode=Desktop`（兼容旧 `provider=desktop`）的自定义模型由 `workflow_settings.current` 解析为 `desktop-app`，沿用所选程序路径及阶段技能；`writing_api` 不将其识别为直连 API。`desktop_idea_chat` 生成任务、复制正文并打开对应应用，回执为 `prepared`，提示用户粘贴并发送；不套用 Codex/Claude 的自动粘贴或 CLI 参数。后台及 CLI 入口明确拒绝此模式。

R1556：L2 video_source_evidence 从已脱敏实际视频请求解析首帧与白模媒体摘要，不读当前媒体猜测历史版本；L3 engine 在预留前校验，保存至镜头资产清单，剪辑来源清单和商用核验继续消费。

R1506：`pet_ui.Pet`（3894 行、230 个方法）按主题原样迁入 4 个 L4 Mixin 模块——`pet_ui_stages.PetStagesMixin`（阶段推进、自动流程、一键制作，58 个方法）、`pet_ui_settings.PetSettingsMixin`（模型、档位、预算与设置，33 个）、`pet_ui_voice.PetVoiceMixin`（播报、对话、报告、项目概览，66 个）、`pet_ui_view.PetViewMixin`（窗口绘制、动画、菜单、点击，58 个）；被迁出方法用到的模块级常量、辅助函数与小类（104 个名字）迁入 `pet_ui_support`，`pet_ui` 重新导入。`TIER_CYCLE／TIER_NAMES／TIER_MODELS／register_tier／tier_models` 被测试和 `register_tier` 在模块级改写，使用它们的 5 个方法留在 `pet_ui`。`pet_ui.py` 4832→915 行。检查 Pet 源码的门禁读 `_scan.pet_ui_text()`。R1948：新增第 5 个 Mixin `pet_ui_popup.PetPopupMixin`（弹窗节制：`stage_has_todo` 有待办才弹、`cloud_dwell_ms` 云朵停留随操作疏密伸缩、`dismissed` 主动关闭后安静期逐次加长，4 个方法），时长常量在 `ui_tokens`。
R1505：`Desktop` 的其余页面与方法按主题原样迁入 5 个 L4 Mixin 模块——`desktop_asset_pages.AssetPagesMixin`（资产页与资产相关 39 个方法）、`desktop_script_pages.ScriptPagesMixin`（剧本结构页等 15 个）、`desktop_media_pages.MediaPagesMixin`（首帧／视频／配音／剪辑／交付／连贯性／动态分镜 49 个）、`desktop_project_pages.ProjectPagesMixin`（项目首页与项目管理 28 个）、`desktop_idea_menus.IdeaMenusMixin`（创意对话菜单与附件确认 6 个）；`desktop_page_support` 增加 `open_studio／open_directory／find_editor_shortcut／comfy_executable／messagebox／Desktop` 的宿主转发及多页共用常量（`STAGE_ACTION_WIDTH`、`ASSET_*`、`_prefs`）。`desktop.py` 5003→2226 行，只保留外壳、启动、异步任务、自动链调度与页面路由。检查 Desktop 源码的门禁统一读 `desktop_text()／parse_desktop()`。
R1504：L4 `desktop_storyboard_page.StoryboardPageMixin` 承载从 `desktop.Desktop` 原样迁出的首帧管理页构建 `storyboard`（323 行；页索引 `PAGE['keyframe']`=7，方法名历史沿用）。新增 `desktop_page_support`：测试按 `desktop.<名字>` 打补丁的 `confirm／open_path／ContextMenu／FileDialog／confirm_project_removal_from_last_script` 的转发函数（`desktop` 模块级 `bind_host` 登记自身，无导入环）与多页共用的 `THUMB_SIZE／ASSET_ROW_HEIGHT`，R1499 的剧本准备页同步改用它。`desktop.py` 5328→5003 行。
R1499：L4 `desktop_writing_page.WritingPageMixin` 承载从 `desktop.Desktop` 原样迁出的剧本准备页构建 `writing`（576 行）及其行数常量 `TALK_MIN_LINES／TALK_MAX_LINES`；`Desktop(WritingPageMixin, IdeaChatMixin, AutoFlowsMixin)`。测试按 `desktop.confirm／open_path／ContextMenu` 打补丁的名字在新模块里用转发函数取 `desktop` 的当前值，`desktop` 模块级调用 `bind_host` 登记自身（新模块不导入 `desktop`，无环）。启动链门禁对 `writing` 改查新位置。`desktop.py` 5906→5328 行。
R1490：L4 `desktop_idea_chat.IdeaChatMixin` 承载从 `desktop.Desktop` 原样迁出的创意对话与 Agent 派发方法（气泡显示／折叠／复制／编辑、创意附件、语义简报、`send_message`、`submit_idea_api_request`、`open_flow_agent` 等 60 个方法，共 1295 行）及其常量／辅助（`IDEA_FIELDS`、`BUBBLE_*`、`DRAFT_*`、`script_raw_saved_notice`、`model_error_display`，`desktop` 里重新导入）；`Desktop(IdeaChatMixin, AutoFlowsMixin)`。依赖被测试按 `desktop.<名字>` 打补丁的方法（confirm／ContextMenu／open_path 共 6 个）留在 `desktop.py`。门禁检查 Desktop 源码时用 `tests.architecture._scan.desktop_text()／parse_desktop()`。`desktop.py` 7241→5906 行。
R1806：L4 `desktop_idea_bubbles.IdeaBubblesMixin` 承载从 `IdeaChatMixin` 原样迁出的 25 个气泡方法（排版、选取复制、编辑守卫、添加与思考气泡）及 9 个 `BUBBLE_*` 常量；`desktop_idea_chat` 按原名转发常量，`IdeaChatMixin` 继承它。
R1895：账户会员客户端（`说明/账户会员云端设计.md` §5.1）按层落地——L1 `lease_verifier`（纯 Python RSA-2048/SHA-256 PKCS#1 v1.5 验签，公钥内置）、L1 `account_store`（`private/账户/session.json`，与 `private/密钥` 分开，不走 DPAPI）、L2 `entitlement_service`（§4.3 离线状态机与免费阶段＝`pet_bus.STAGES` 前 2 项）、L2 `account_client`（§3.2 接口，出站只经 `platform_tools.open_https`，测试期钉自签证书）、L3 `account_controller`（登录／续签／退出状态机，后台经注入的 `async_queued`）、L4 `desktop_account_page.AccountPageMixin`（「00 会员账户」页）、L4 `desktop_login_gate.LoginGateMixin`（真实启动时未登录先盖全屏登录页，登录成功才进主界面；侧栏常驻试用／会员到期摘要）；会员闸门在 `stage_handler_registry.start()` 入口前置，宿主未挂 `account` 时不设闸。`platform_tools.open_https` 增加可选 `method`／`context`。

R1480：L4 `desktop_auto_flows.AutoFlowsMixin` 承载从 `desktop.Desktop` 原样迁出的无人值守流程方法（自动定稿／粗剪／首帧／资产／视频／白模／交接／采用的 `_tick_auto_*`、`poll_auto_*`，云监控、下载收件箱及相关判定），`Desktop` 通过继承获得；方法体未改，`self` 语义不变；无 Tk 的周期调度仍由 L3 `desktop_automation_service` 承担。`desktop.py` 7820→7241 行。
R1250：API 剧本准备通过 L3 `restart_writing_preparation` 显式从设定、大纲或角色卡重写；L2 `writing_api` 在既有 `preparation_state.json` 内暂存 revision，确认前保留采用 documents，确认后替换当前及下游确认。旧正文不删除；旧自然稿撤销采用须重新生成或显式采用。请求发布核对阶段文件、brief、确认台账及模型选择，拦截等待期间变更后的迟到结果；桌面仅绑定菜单和显示版本标记。

R1247：剧本准备显示会话和发送请求分别固定模型身份；请求路由、历史及发布复用提交快照。聊天以稳定模型 ID 分区，兼容迁移显示名目录及回收站，模型池保存历史目录别名。`natural_script_selection.json` 经 L3 注入发布器记录采用自然稿的相对路径和 SHA256；多稿不再按时间自动采用。`WritingRequestAdapter` 复用 ModelAdapter 协议逐次检查模型容量与输出预留，累计已报告用量；估算与实报元数据归属对应回复，不含密钥。已确认简报及阶段成果仍按项目共享。

> 初稿基于 2026-09-25 源码；后续按轮次追加，R1022 校正文档口径。本文的 R 编号段落是历史记录，不是当前验收凭据。阶段、路径与事件以 AGENTS.md §2.2 所列代码为准；开发验证规则只在 AGENTS.md §5 定义。

R1122：统一下拉框创建入口为 `ui_widgets.SelectBox`（继承 ttk.Combobox），18 个业务文件的 39 处构造迁移完成。只读默认、CJK 按 2 宽估算并封顶 28、弹出最多 12 行；动态选项经 set_values 重算。保留可编辑/禁用状态、分镜选择 width=1 与既有 Tcl 滚轮保护；分镜选择服务由 desktop 注入 SelectBox 工厂，不反向依赖 UI 层。现有 test_combobox_boundary 增加裸构造门禁，豁免统一组件、测试、维护记录及附加工具目录。

R1212：剧本准备 API 的阶段确认仅使用 L4 输入框原文，经 L3 独立传入；含附件的完整请求继续作为创作上下文。L2 `idea_chat.reply_document_path` 统一自动阶段保存与下载命名，复用正文相同的文件，异稿在模型名后加 `(N)`；具体名称仍由 `script_contract.stage_file_name` 产出，发布仍经 L3，确认台账绑定最新修订文件。下载优先按文档标题分类，保留全文。

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
├─ data/                  程序内置数据、示例数据
├─ episode/               默认/演示剧集输出
├─ logs/                  运行、模型与三虎日志
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

总控预设契约（原统筹预设契约，R1433）：唯一来源是 `skills/00全流程SKILL/总控.json`，形如 `{version, presets: {名称 → {package, stage_skills{阶段 → [注册id]}, locks[锁键]}}}`；`workflow_settings.refresh_workflow_presets()` 按文件指纹原地刷新 `WORKFLOW_PRESETS`（锁键换成 `PRODUCTION_LOCK_DEFINITIONS` 定义），清单缺失／损坏退回 `BUILTIN_WORKFLOW_PRESETS` 并记入 `MASTER_MANIFEST_PROBLEMS`。项目配置在 `skill_config.json` 顶层以 `workflow: {name, skill_ref, lock: {总控名称: {键: 值}}, applied: {name, fingerprint, stage_skills, problems, at}}` 投影；`lock` 按总控名称分命名空间，切换总控时不得丢弃旧值；`applied` 是 `master_skill.sync` 的同步基线。总控声明可提供锁键和默认值，但外部包 frontmatter 仍不是执行字段来源，继续遵守注册表不信任原则。`master_skill`（L4，无 Tk）：指纹、自动同步、体检与门禁；`skill_import_service`（L4，无 Tk）：阶段配置「新增 SKILL」的整包导入、预检、试冻结、旧版回收与导入台账（`data/skills/导入台账.json`；旧路径 `skills/导入台账.json` 迁移后回收）。

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

R2191（R2178 J3）：按真实静态依赖重登记 8 个模块，只改登记与台账、不改生产代码——`artifact_lineage`→L0（无依赖，被 L0 `script_contract` 引用）；`pet_state`、`ui_plugin_registry`、`integrations`、`qwen_setup`→L1（只依赖 L0／L1）；`qwen_adapter`（引擎适配器，与 `workflow_engines` 同层）→L3；`workflow_settings`、`legacy_compat`→L3（依赖 L3 的 `stage_config`／`stage_models`／`skill_registry`／`edit_habits`）。`层级` 条目 **35→21**、`baseline_exempt` 同步下调，`KNOWN_DYNAMIC_UPWARD` 5→3；剩余 21 条是真实的反向依赖，留给后续专项。

R1649：清掉 `tests/architecture/_layers.py` 里 3 个**僵尸登记名**——`project_storage`／`asset_detail_ui`／`workflow`。依据：全仓 AST 与文本检索均无同名 `.py`、无导入、无属性／字符串引用，`architecture.md` 本节表格也从不曾列出它们（现行名分别是 `asset_detail` 与 `workflow*` 家族），即初版登记表里没有采用方的历史残名。同时新增可执行不变量：**登记表每一名须满足「有实体 `.py` ∨ 在 `TOOLS` ∨ 在 `historical_name_audit.entrypoints`」**，由 `test_layers` 断言；僵尸名既已无采用方，就不并入 `historical_name_audit`（该项要求指认现行职责入口）。分层判定、越层豁免数与 `baseline_exempt` 均不变。

| 层       | 模块/职责                                                                                                                                                      | 判定                           |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| L0 合同   | `pet_bus`、`script_contract`、`script_manifest_schema`、`script_output_spec`、`asset_contract`、`service_contract`、`artifact_lineage`、`artifact_schema`、`project_context`、`stage_layout`、`stage_path_service`、`storyboard_paths`、`prompt_templates`、`shot_batches`、`continuity_ledger`       | `service_contract.ServiceResult` 定义四字段结果口径；`project_context.ProjectContext={root, stage_resolver, settings_snapshot, cache}` 定义项目上下文注入契约。采用方及待迁移范围以 `维护记录/架构统一基数.json` 和对应门禁为准，本表不缓存数量。两项于 2026-10-04 经用户授权解冻，按序每轮最多迁移 3 个 service，执行规则见 `维护记录/架构统一路线图_v2.md`。`pet_bus.emit_safe()` 是跨模块状态的唯一安全发送器，`pet_agent._emit()`／`pet_ui._emit()` 仅作受控转发；`broadcaster` 只写用户可见文本日志。`stage_path_service` 是新写/旧读的唯一阶段路径口径；`script_contract.save_natural_script()` 是手改自然剧本的内容闸门与原子发布口径；允许被上层依赖，不应反向依赖 UI/编排；`stage_layout.validate_stage_contract()` 保证目录阶段与 `pet_bus.STAGES` 同序；`json_md_rows()` 的人读 MD 路径只使用当前编号阶段目录下的 `docs/`；`artifact_schema` 是正式 JSON 产物版本与字段契约的唯一登记：新写入写 `schema_version`，读取侧容忍缺版本，历史 `version` 键经 `migrate()` 只加键抬升 |
| L1 基础设施 | `client_profiles`、`model_pool`、`model_secrets`、`pet_llm`、`file_cache`、`hash_backend`、`storage_maintenance`、`workspace_maintenance`、`diagnostic_capture`、`line_endings`、`ui_tokens`、`pet_state`、`ui_plugin_registry`、`integrations`、`qwen_setup`                                                    | `client_profiles` 只读内置与用户客户端档案并解析 PE 头；探测命令仅在用户显式操作时运行，启动路径不扫描目录；`diagnostic_capture` 仅采集程序拥有日志的脱敏现场与已知启动指标，导出固定白名单且不扫描项目目录；模型小环违反此层应无反向依赖的目标；`ui_tokens` 是 design_tokens.md 的只读代码化事实来源；本机路径/浏览器/进程和短 TCP 探测统一由 `platform_tools` 适配，不得由 UI 直连；`workspace_maintenance` 只做仓库级可再生卫生（`__pycache__`、超期 `.selftmp`、已并净的 `.wt` 工作树），用户可见删除仍唯一走 `storage_maintenance.recycle_paths()`，`git gc` 只在开发脚本 `scripts/repo_health.py`            |
| L2 业务   | `writing*`、`idea_chat`、`idea_brief_form`、`idea_attachments`、`idea_script_heuristic`、`idea_document_paths`、`idea_transcript`、`storyboard*`、`asset*`、`keyframe*`、`video_lifecycle_service`、`tts_api`、`speech_api`、`audio_import_service`、`subtitle_timing`、`subtitle_export_service`、`delivery_import_service`、`confirm_gates`、`desktop_settings_service`、`stage_workspace_service`、`legacy_adoption_service`、`recycle_recovery_service`、`white_model*`、`previs*`、`native_assets`、`handoff_service`、`edit_service`、`animatic_service`、`final_service`、`storyboard_adoption_service` | `writing.prepare()` 负责离线编剧任务书成果包在剧本准备阶段的受控发布；`idea_chat.save_manual_creative()` 负责手动创意的剧本准备分类目录、命名与原子发布；`idea_attachments.prepare()` 受控读取文本附档、限制体积与上下文，并且只向模型提交文件名与带边界的文本，不暴露本地路径；`storyboard_files.storyboard_work_plan()` 是无 Tk/Agent 的分镜输入决策服务；`storyboard_rows_service` 负责首帧行与分镜统计；`storyboard_edit_service` 负责已校验分镜 JSON 的原子编辑保存；`asset_batch_service` 负责资产生成登记、本地导入图片的校验/落盘/索引原子发布与失败回滚、资产改名的可恢复双文件同步、图片回收/恢复与索引失败回滚、无人值守资产计划、设置快照去重与重试决定；`asset_detail_service` 负责正典板视角与状态变体缩略图的格式/非空校验、原子复制、资产清单索引发布及失败回滚；`recycle_recovery_service` 只投影项目内或项目库回收清单，并且逐项/整批恢复始终委托 `storage_maintenance.restore_recycle_batch()` 的既有边界与回滚语义；`local_video_settings_service` 负责经 UI 本机预检后的 ComfyUI 工作流副本和项目设置原子发布，并在配置失败时恢复旧文件；`desktop_settings_service` 负责桌面全局项目选择、本机 ComfyUI 与剪映路径偏好的原子发布；`stage_workspace_service` 负责配音、后期和交付页面的既有阶段目录初始化；`legacy_adoption_service` 负责旧目录归位日志的原子发布；`confirm_gates` 负责门禁候选的确认记录读写，读取走 `file_cache`、写入走 `agent.core.save()`；`keyframe_lifecycle_service` 负责首帧导入替换、回收/恢复、状态发布与失败回滚；`video_lifecycle_service` 负责本地视频镜头删除标记、选项发布与失败回滚；`tts_api` 负责整段及逐句配音的媒体优先发布、幂等复用查询与可续跑时间轴登记；`speech_api`（REQ-S01-71）负责语音输入的实时云端识别：设置为内置默认合并 `data/语音识别.json`（`save_settings()` 校验后写入，发布器由 L4 `speech_settings_ui` 注入，入口在模型管理底栏），密钥按变量名经 `model_pool` 取，出站只经 `platform_tools.open_websocket`；`audio_import_service` 负责用户选择音频的格式/非空校验、临时复制校验与原子落盘；`subtitle_export_service` 负责 SRT 与对白脚本的受控阶段目录发布及角色名渲染；`delivery_import_service` 是项目上下文与结果契约的采用方：只消费 L3 注入的 `ProjectContext`，以阶段解析器定位交付目录，不自行拼接项目路径；成功或业务失败均返回 `service_contract` 结果对象，源文件保持不动。其他待迁移范围由 `维护记录/架构统一基数.json` 登记，两项已于 2026-10-04 经用户授权解冻，后续迁移见路线图；均不导入 Tk 或配置页面。 |
| L3 编排   | `stage_flow`、`stage_exec`、`stage_parallel`、`stage_config`、`stage_models`、`stage_handler_registry`、`skill*`、`workflow*`、`agent_dispatch`、`engine`、`legacy_compat`、`qwen_adapter`、`asset_auto_batch_service`、`asset_batch_execution`、`asset_batch_controller`、`asset_page_controller`、`editing_page_controller`、`keyframe_page_controller`、`media_page_controller`、`page_navigation_controller`、`pet_broadcast_state`、`stage_completion_service`、`stage_publication`、`stage_write_preparation_service`、`stage_download_inbox_service`、`desktop_startup_service`、`desktop_automation_service`、`desktop_auto_state`、`idea_chat_controller`、`idea_semantic_brief_service`、`recycle_recovery_controller`、`storyboard_final_controller`、`storyboard_page_controller` | 三虎启动唯一经 `stage_handler_registry.start()`；无人值守资产批量生成由 L3 编排服务调用执行器；`workflow_engines` 与 `codex_tasks.prepare_task()` 均须在启动进程或创建任务工件前执行统一请求上下文预算预检；`project_context_factory.project_context()` 是 `ProjectContext` 的唯一构造实现；`stage_execution_service.project_context` 静态重导出同一函数，并由交付编排注入统一二进制发布器；`publish_stage_text()`／`publish_stage_bytes()`／`publish_stage_bundle()` 均以调用方既有校验器与索引更新器完成“校验→原子发布→索引更新”，任一写入或索引失败会回滚本次成果并抛错（R1619 起实际定义在 `stage_publication`，`stage_execution_service` 按原名转发；“首次修改前复制历史成果”在 `stage_write_preparation_service`，下载收件箱在 `stage_download_inbox_service`）；L2 仅接收注入发布器，不得反向导入 L3；`desktop_startup_service.DesktopStartupController` 仅编排注入的首帧延迟、空闲选择和取消回调；`desktop_auto_state.AutoState` 是八条自动流程的状态容器（R1985：Desktop.auto 持有，R2017 起旧 auto_* 属性名已退役，一律读写 `self.auto.<字段>`，`AutoStateHolderMixin` 只懒建缺失的 `auto`），队列工厂由 L4 注入，不持有 Tk 或阶段权威；`desktop_automation_service.DesktopAutomationScheduler` 仅编排注入的周期回调、取消、受控异常与到期轮询，不持有 Tk 或阶段状态；`idea_chat_controller.IdeaChatController` 仅保存注入的对话请求、发送节流、附件引用和流式进度回调状态；`RecycleRecoveryController` 只汇总注入的当前项目与项目库根目录，不持有 Tk 控件，委托 L2 列表与恢复；`AssetBatchController` 保存资产批量页的表单默认值、勾选状态、模型检测与启动前门禁，只调用注入的计划及选择服务；`asset_page_controller.AssetPageController` 保存资产主页面的类别筛选、勾选初始化和批量目标判定，不持有 Tk 控件或写入项目数据；`editing_page_controller.EditingPageController` 保存后期页的视频可用性、自动粗剪报告与完成状态文案，只调用注入的工作室对象；`pet_broadcast_state`（R2006，R1983 J5）是 Pet 播报状态容器：`notice`／`last_status`／判重指纹／压住的话／推进节流六件由 `Pet.bstate` 持有，判重、压住、节流只经它的方法写，`notice`／`last_status` 经 `PetBroadcastAliasesMixin` 作为公开属性转发，四个下划线旧名已于 R2015 退役；`page_navigation_controller`（R2001，R1983 J4）是桌面换页的无 Tk 函数集：侧栏视频模式、整页缓存的失效判据与缓存项、换页前的分镜采用与来源选择闸门、关闭窗口时要取消的 after 任务名单（页序号表与取消回调由 L4 注入，计时器取消仍由 `Desktop.cancel_timers` 驱动）；`media_page_controller`（R1997，R1983 J3）是制作后段页（首帧／连贯性／视频／配音／后期／交付）的无 Tk 函数集：就绪签名、首帧批次可否派发的判据、连贯性清单表格行、剪映查找候选、字幕状态文案、交接包选版、交付页状态行与视频工作区解析，读文件的口子由 `MediaPagesMixin` 注入，Mixin 只留控件与事件绑定；`keyframe_page_controller.KeyframePageController` 保存首帧页多分镜行归属、首帧路径校验与按来源分批选择，不持有 Tk 控件或写入项目数据；`storyboard_final_controller.FinalStoryboardController` 保存定稿预览、编辑和镜头导航状态，只调用既有选择与原子保存边界，并可接收后台读取完成的预览结果；`storyboard_page_controller.StoryboardPageController` 保存初步分镜文件表的扫描、选择、按钮门禁和回收编排，只调用既有目录、选择和回收服务；阶段成果核验由无 Tk 服务处理，桌面视频状态经回调注入；L3 不持有 Tk 控件 |
| L4 UI   | `desktop`、`pet_ui`、`pet_cloud`、`pet_cloud_text`、`pet_cloud_geometry`、`pet_cloud_shape`、`pet_cloud_tail`、`pet_cloud_timing`、`pet_cloud_hint`、`pet_cloud_place`、`responsive_ui`、`ui_theme`、`ui_widgets`、`ui_composer_style`、`ui_splash`、`ui_tooltip`、`ui_stage_popups`、`ui_rounded`、`ui_motion`、`ui_scroll`、`ui_hover_fade`、`cell_hover`、`prompt_window`、`asset_detail`、`storyboard_table_ui`、`cloud_video`、`local_video`、`skill_panel`、`skill_panel_presets`、`skill_panel_support`、`desktop_page_registry`、`desktop_tk_gc`、`desktop_automation_tick`、`desktop_layout`、`desktop_pet_bridge`、`desktop_async_tasks`、`desktop_master_update`、`desktop_page_nav`、`desktop_lifecycle`、`desktop_login_gate`、`master_skill_update`、`workflow_settings_dialog`、`qwen_setup_dialog`                                | `ui_widgets` 是主/次按钮与卡片的 Tk 组件唯一入口，只消费 L1 `ui_tokens`；`ui_composer_style`（R2082）承载剧本准备页输入框的附件卡片与框内图标按钮样式，由 `ui_widgets.setup_styles` 注入按钮配置函数调用；`pet_cloud_text` 承载云朵框的无 Tk 文本规整与转播文案；`pet_cloud_geometry`、`pet_cloud_shape` 与 `pet_cloud_tail` 分别承载图元几何、形状规则和尾巴曲线的无 Tk 计算；`storyboard_table_ui` 承载分镜文件表的 Tk 构建与渲染；`desktop` 保留 Tk 窗口、页面控件和事件绑定，在启动边界只注入回调给无 Tk 控制器；`desktop`、`storyboard_files`、`asset_batch` 禁止直连进程或网络，只可使用静态登记的 `platform_tools`／`native_apps` 入口；`master_skill_update`（R1996）检测并更新总控包：联网只经 `platform_tools.open_https`，下载 GitHub 压缩包后与本机逐文件比对，按各阶段总控 SKILL 的直接引用归类成“每个阶段的变化”，用户在 `desktop_master_update` 的确认窗点确定后才覆盖，旧包进回收站并触发 `master_skill.sync`；总控包带 `.git` 时只提示不覆盖；已装提交号记在 `data/总控包更新.json`；`workflow_settings_dialog`（R2184，R2178 J1）只承载工作流「调用设置」窗口的 Tk 控件与事件，配置解析、校验与保存（`workflow_settings.save_flow()`）留在 `workflow_settings`，后者导入时不再加载 tkinter。`qwen_setup_dialog`（R2189，R2178 J2）只承载 Qwen Code「API 设置」窗口的 Tk 控件与事件，连接设置的读取、校验与密钥读写留在 `qwen_setup`，后者导入时同样不加载 tkinter。UI 延迟加载只能经 `ui_plugin_registry.module()`；登记表外名称拒绝加载，保留按页延迟导入行为 |
| L5 入口   | `app`、`app_icon`、`app_shortcut`                                                                                                                            | 入口只装配依赖，当前 `app.py` 仍动态调用流程  |

### 已验证的发布边界

R1599：阶段文本、二进制与成果包发布使用 `agent.publication` 持久化写前日志，回调内经 `agent.core.replace` 写入的索引属于同一事务。安装目录内的发布进程通过文件锁串行化；`core.read`、缓存读取及桌面打开项目前恢复未提交事务。旧文件采用流式备份，提交或回滚标记落盘后才清理。保证范围为受控发布入口及恢复后的读取；外部编辑器、任意裸路径并发读取和物理介质断电不据此宣称整包原子。

R806 将三虎增量自检账本纳入 L3 发布边界：`pet_test_service.record()` 不再自行发布项目 JSON，`stage_execution_service.poll_pet_test_check()` 通过 `pet_test_gateway()` 注入原子发布器；`pet_ui` 只经 `stage_handler_registry.start()` 启动并由 L3 轮询。重复次数、失败用例脱敏摘要与失败时不落账本的语义不变。

R808 将定稿分镜编辑发布纳入 L3 发布边界：`storyboard_edit_service.save_edited_json()` 仅接收注入的 JSON 发布器，`storyboard_final_controller` 只委托 `stage_execution_service.save_edited_stage_storyboard()`，并由 `storyboard_edit_gateway()` 装配。路径格式校验、原子失败不覆盖旧文件与返回路径语义不变。

R807 将白模预演进度发布纳入 L3 发布边界：`previs_progress_service.publish()` 与 Blender 回调安装仅接收注入的文本发布器，`stage_execution_service` 通过 `previs_progress_gateway()` 装配，宿主兼容门面仍以原有 `publish()`／`install_blender_progress()` 名称委托 L3。进度 JSON 字段、原子发布与真实帧数回调时序不变。

R805 将三虎优化账本纳入 L3 发布边界：`pet_performance_service.record()` 不再自行发布项目 JSON，`stage_execution_service.poll_pet_performance_check()` 通过 `pet_performance_gateway()` 注入原子发布器；`pet_ui` 只委托 L3 启动与轮询。离线基准脚本、阈值比较、摘要格式与失败时不落账本的语义不变。

R713 将确认门禁的项目确认记录 JSON 纳入“读走缓存、写走原子服务”迁移：`confirm_gates.confirmations()` 改经 `file_cache.read_json()` 读取，`record()`／`forget()` 仍只经 `agent.core.save()` 原子发布；缓存随发布失效，确认项的缺失／损坏回退与门禁语义不变。

R714 将工作流调用设置 JSON 纳入“读走缓存、写走原子服务”迁移：`workflow_settings.load()`、Qwen 模型同步及设置窗保存均经 `file_cache.read_json()` 读取既有项目设置，写入仍只经 `agent.core.save()` 原子发布；缓存随发布失效，设置格式、默认值和 UI 行为不变。R2184（R2178 J1）起设置窗保存收进 `workflow_settings.save_flow()`（校验所选引擎 → 写回本流程 → Qwen 同步共享模型），窗口本体移到 L4 `workflow_settings_dialog`。

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

当前架构门禁的文件清单以本文件末尾 §“当前架构门禁清单”为入口，并由 `test_agents_md.py` 强制与 `tests/architecture/test_*.py` 的实际集合完全一致；总数以 `python smoke_test.py --architecture` 当轮输出为准，基线只增不减。R706 增加 `service_contract` 与交付成片导入试点的结果契约门禁，后续 L2 写服务须逐批迁移。R567 将历史兼容入口收口到 `legacy_compat.FACADE_MANIFEST`，逐项记录唯一所有者、真实调用方与 2027-03-31 淘汰日；`tests/architecture/test_legacy_facade_manifest.py` 的 AST 门禁拒绝未登记调用与到期未处置 facade。R565 在 `workflow_context` 定义“剧本完整索引／非剧本阶段摘要”两种上下文策略，`desktop` 在保留原任务、SKILL、阶段契约与续接语义的前提下选择策略；`workflow_context_budget` 对最终初始/续接提示统一去重、执行既有上限并生成不含正文的预算元数据，收据可观察阶段、策略、字符数、上限和余量。R564 将剧本结构页 `Desktop.script_structure()` 的颜色、字体与间距完全收口到 L1 `ui_tokens`，并以 L4 `PrimaryButton`／`SecondaryButton` 承担高亮和次级操作的状态样式；组件悬停态保持可读的主色文字，页面不再自行定义按钮视觉值。 R563 将缓存失效收口为 L1 `file_cache` 的 `published`、`recycled` 与 `externally_overwritten` 事件：`agent.core` 原子发布和 `storage_maintenance` 回收/恢复在文件操作成功后通知该权威，统一淘汰 JSON、文本及字节缓存；外部适配器覆写时必须显式通知，mtime/哈希只保留为旧路径安全兜底，页面不得以刷新承担一致性。R562 使定稿大 JSON 读取按需后台完成、以页面代次取消旧结果并以空闲分片写入 Tk，仍复用 `file_cache` 的签名/内容哈希缓存；资产缩略图任务绑定可销毁页面控件，离页由既有任务失活检查丢弃。R561 将剧本准备文件表改为无 Tk 服务逐项发现、L4 每批 24 条空闲提交及销毁/刷新代次取消，最终仍按修改时间排序；R560 新增迁移 UI 边界门禁，防止服务重新导入 Tk、视图重新直连进程/网络或新增未登记适配器入口。

R841 固化事件总线边界：跨模块状态发送只能走 `pet_bus.emit_safe()`，`pet_agent._emit()` 与 `pet_ui._emit()` 是仅有的受控转发器；`Bus.emit()` 的实现仅留在 L0，`broadcaster` 则仅用于 `desktop`／`pet_ui` 的用户可见文本日志，不能成为状态传输旁路。

R842 开始收口后台任务生命周期：桌面唯一的主动异步入口 `Desktop.async_()` 将代次提交、逻辑取消、成功／失败收尾集中给无 Tk 的 `BackgroundTaskLifecycle`。任意 Python 线程不可安全地被强杀，因此取消的语义是拒绝迟到结果进入 UI；模型、媒体及预演的专用进程仍维持其既有可终止协议，后续按同一边界逐批迁移。

R843 将该生命周期扩到自动粗剪与自动交接包：两类后台文件任务各自拥有代次，关闭窗口后会拒绝队列中的迟到结果，成功／失败仍只由主线程完成原有页面刷新、退避和自动链推进。自动视频因含连续进度消息，保留为下一批，避免以不同的交付结构掩盖取消边界。

R788 将桌面 12 个制作页名称收口到 `pet_bus.STAGES`／`STAGE_NAMES`：`desktop.PAGES` 只生成阶段页，另保留“参考网站”这一工具页；`test_stage_display_boundary.py` 防止页面名称退回手写。R789 复核基准趋势门禁时实测架构套件为 156/156，基线据实校正；该轮仅补充离线基准归档的窗口与测量条件回归，不进入产品启动路径。

R721 后架构门禁基线为 118/118，默认冒烟基线仍为 8/8。R722 后架构门禁基线为 119/119，默认冒烟基线仍为 8/8。R723 后架构门禁基线为 120/120，默认冒烟基线仍为 8/8。

R722 将视频生成入口的正式项目 JSON 读取纳入同一入口：L4 `video_navigation` 保留页面级“坏文件即空表”容错包装，底层改委托 `file_cache.read_json()`；分镜、首帧、云端配置和本地模型的展示文案与优先级不变。

R723 将白模监视页的制作进度 JSON 纳入同一入口：L2 `previs_monitor.progress_of()` 改经 `file_cache.read_json()` 读取，保留进度文件缺失/损坏时显示“制作中”的容错及浏览器监视页刷新节奏。

R724 将字幕 SRT 与对白脚本两类音频阶段成果纳入 L3 发布器注入边界：L2 `subtitle_export_service.export_srt()`／`export_dialogue_script()` 只准备文本并接收调用方注入的发布器，`stage_execution_service.export_stage_srt()`／`export_stage_dialogue_script()` 注入 `publish_stage_text()`，桌面只调用 L3 编排入口。文件名、UTF-8 BOM 编码、空对白拒绝与发布后返回路径语义不变。

R724 后架构门禁基线为 122/122，默认冒烟基线仍为 8/8。

R725 将剧本模型工具、直接 API 自动保存和 script_raw 原稿三条剧本成果路径纳入 L3 发布器注入边界：L2 `writing_tools.write_file()` 与 `writing_api._write_script_raw()` 均只接收发布器，`stage_execution_service.reply_to_writing()` 统一注入 `publish_stage_text()`，桌面不再直调 `writing_api.reply()`。无发布器的写请求明确拒绝，绝不降级直写；剧本内容闸门、路径和模型交互语义不变。

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

R1244 补齐 API 自然剧本自动归档：四角色审核通过或关闭四角色后的合格正文，保留内部原稿，并由 `writing_api` 复用 `idea_chat.reply_document_path()` 计算正式稿路径，经既有 L3 注入发布器写入对应 Provider／模型／日期批次的项目剧本目录。同稿复用、异稿编号；失败或取消不进入正式发布，页面显示正式保存路径。此处是程序发布，不要求 API 模型自行写文件。 R1245 的文档发现仅在正式文本内容一致时隐藏内部稿条目；文件仍保留，不同内容或尚未正式交付的内部稿继续可见。

R730 后架构门禁基线为 128/128，默认冒烟基线仍为 8/8。

R731 将首帧删除、恢复与替换的 `episode.json` 状态发布完全纳入 L3 发布器注入边界：L2 `keyframe_lifecycle_service` 只接收图片及索引发布器，绝不保留 `save()`／`save_bytes()` 直写回退；`stage_execution_service.delete_stage_keyframe()`／`restore_stage_keyframe()`／`replace_stage_keyframe()` 分别注入 JSON 文本及 PNG 原子发布器，桌面只调用这些 L3 编排入口。镜头编号和路径校验、回收站处理、索引失败时的图片与内存状态回滚均保持不变。

R731 后架构门禁基线为 129/129，默认冒烟基线仍为 8/8。

R732 将首帧生命周期服务接入统一服务结果契约：`keyframe_lifecycle_service.delete_keyframe()`／`restore_keyframe()`／`replace_keyframe()` 成功时均返回 `success(data)`，可预期的参数或状态错误归为 `UserError`，受控发布期间的 I/O 故障归为 `SystemError`；遗漏发布器等编程错误仍抛出。L3 `stage_execution_service` 透传结果，桌面沿用既有失败提示，不改变镜头校验、回收站、回滚或事件绑定语义。

R771 将项目登记与项目内配置的读写、媒体复制及事务回滚纳入 L3 注入边界：L2 `projects.Projects` 必须接收 `stage_execution_service.project_registry_gateway()`，缺少网关即拒绝；该 L3 网关统一注入缓存读取、原子 JSON／字节发布、回滚和复制操作。桌面与项目导入仅装配该网关，项目字段、路径、授权和回滚语义不变。

R732 后架构门禁基线为 130/130，默认冒烟基线仍为 8/8。
R733 后架构门禁基线为 132/132，默认冒烟基线仍为 8/8。R734 后为 133/133；R735 固定架构统一审计范围、处置状态与 AGENTS 清单集合门禁后为 134/134。R775 增设测试 skip 卫生门禁后为 143/143：每项必须引用受控原因常量、说明恢复条件，并与 `维护记录/skip台账.json` 双向一致。R784 增设 Tooltip 首迁边界后为 150/150：截断 SKILL 名称提示只能经 `ui_widgets.Tooltip`，不得退回页面内手写浮层。R785 增设共享图标首迁边界后为 151/151：视频页返回箭头只能经 `ui_icons.IconLoader`，不得重新手写 `PhotoImage`。R786 增设全局滚动条主题边界后为 152/152：横、纵 `TScrollbar` 必须共用 token、active 反馈与唯一主题入口。R787 增设统一复制入口边界后为 153/153：应用文本写剪贴板只能经 `prompt_window.copy_text()`，并必须持有跨进程锁且可对状态栏回执脱敏。

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

## 维护边界

- R1327 将创意对话的聊天记录持久化从 L2 `idea_chat` 拆到新的 L2 `idea_transcript`：`load()`、`append()`、`replace()`、`remove()`、`remove_all()`、`restore_latest_removed()`、`compact_context()`、`repair_internal_replies()` 原签名、原返回与原缓存上限不变，并随迁其必需的私有读写辅助（`_all_rows`、`_read_rows`、`save_rows`、`_row_indexes`、`_stamp`、`_visible_claude_text`）与模型会话路径（`folder()`、`history_path()`、`chat_model()`、`model_history_path()`、`deleted_history_path()`）。`_context` 沿用本项目各 L2 模块各自持有 ProjectContext 校验的惯例，在新模块内保留独立一份，`idea_chat` 继续持有自身校验。调用方 `writing_api` 的 `load` 改从新模块导入；`desktop` 仍以 `idea_chat.load`／`idea_chat.append`／`idea_chat.repair_internal_replies` 等模块属性调用，来源经必要 re-export 指向新模块，调用方式与断言未动（`test_project_context_boundary` 的桌面断言与 `test_writing_quality`／`test_idea_chat` 的 patch 目标仍为活引用）。新模块只做对话记录的读写与迁移，读写仍走 L3 注入网关，按第 1 项登记为豁免（`第一项.exempt_count` 38→39），并把 `第三项`／`第四项` 中随迁函数的台账项归属同步到新模块。
- R1315 将剧本准备页的简报表单解析与校验从 L2 `idea_chat` 拆到新的 L2 `idea_brief_form`：`extract_brief_creation()`、`merge_brief_creation()`、`inline_required_missing()`、`brief_creation_values()`、`format_brief_creation()` 及解析辅助 `_brief_plain_text()`／`strip_inline_required_markers()`／`inline_template_labels()`、字段契约 `BRIEF_CREATION_FIELDS` 原签名、原返回值与原判定门槛不变；`brief_creation_values()` 依赖的简报文件路径按同一权归属随迁 `brief_raw_path()`／`legacy_brief_raw_path()`／`brief_complete_path()` 及其文件名常量到既有 L2 路径权威 `idea_document_paths`（否则 `idea_brief_form` 与 `idea_chat` 将形成静态互引，被 `test_no_circular_import.py` 禁止），`idea_chat` 仅保留必要 re-export。调用方 `writing_api`、`stage_execution_service` 改从新模块导入；`desktop` 的 `strip_inline_required_markers` from-import 改指新模块，其余 `idea_chat.extract_brief_creation`／`merge_brief_creation`／`inline_required_missing` 模块属性调用经 re-export 保持不变（`test_idea_inline_brief.py` 的 patch 目标仍为活引用）。新模块只做纯文本解析，不读 Tk、不发网络，按第 1 项登记为豁免（`第一项.exempt_count` 37→38）。

- R1313 将剧本准备页的路径与命名策略从 L2 `idea_chat` 拆到新的 L2 `idea_document_paths`：`storage_identity()`、`reply_path_parts()`、`reply_document_path()`、`project_script_filename()`、`project_document_directory()`、`PROJECT_DOCUMENT_DIRS` 原签名、原返回与原命名规则不变，并随迁其必需的私有命名辅助（`ChatModel`、`_storage_name`、`_file_day`、`_file_part`、`_project_file_type`、`_OVERWRITE_FILE_TYPES`）。`_context` 沿用本项目各 L2 模块各自持有 ProjectContext 校验的惯例，在新模块内保留独立一份，`idea_chat` 继续持有自身校验。调用方 `workflow_tasks`、`writing_api` 改从新模块导入；`desktop` 仍以 `idea_chat.storage_identity` 模块属性调用，来源经必要 re-export 指向新模块，调用方式与断言未动。新模块仍只读模型身份、纯计算路径，不读写、不发布项目数据；对 `legacy_compat` 的既存越层豁免由 `idea_chat` 项原位改为 `idea_document_paths`（层级台账项数 37→37 不变），并按第 1 项登记为豁免（`第一项.exempt_count` 36→37）。

- R1310 把"像不像剧本"的启发式判断从 L2 `idea_chat` 拆成独立 L2 `idea_script_heuristic`：`looks_like_script()`、`SCRIPT_MARKS`、`SCRIPT_MIN` 原值原语义搬移，判定门槛（300 字 ＋ 至少两个要素）不变。`idea_chat` 保留同名静态重导出，供既有界面与测试继续以 `idea_chat.looks_like_script` 调用；`desktop.update_script_download_button()`／`download_script()` 改从新模块导入，调用方式与断言未动。新模块不读写任何项目数据，按第 1 项登记为豁免（`维护记录/架构统一基数.json` 第一项 `exempt_items`，`exempt_count` 35→36）。

- R1309 将创意简报的语义提取请求与结果校验从 L2 `idea_chat` 拆到 L3 `idea_semantic_brief_service`：只搬 `semantic_brief_request`、`semantic_brief_values` 与 `SEMANTIC_BRIEF_TIMEOUT`／`SEMANTIC_BRIEF_POLL_SECONDS`／`SEMANTIC_BRIEF_MAX_BYTES`／`SEMANTIC_BRIEF_INFERRED`，函数签名、返回结构、轮询与体积阈值原值不变。简报文件路径与 ProjectContext 校验仍委托 L2 `idea_chat.brief_raw_path()`，不新造路径权威；L2 不反向依赖 L3，故 `idea_chat` 不保留这批符号的兼容 re-export，原调用点改指新模块。

- R1098 经逐候选授权移除 `idea_chat.project_document_kind`、`Projects.remove_internal_links`、`workflow_process_registry.cancel_process_slot_request` 三个无仓内消费者的接口；文件分类、项目回收与项目级排队取消继续使用现有入口。仅删函数定义，不迁移职责、层级或测试；外部动态调用风险已提示并获准实施。

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
- SKILL 唯一权威：`skills/01`—`12` 阶段目录内的 `.skill.md`、用户层 `data/skills/` 与 `skill_registry.py`；根目录遗留文件仅由懒迁移归档；模型唯一权威：模型管理保存的模型池。
- `<项目>` 是用户项目根目录占位符，非 `程序/episode/` 演示目录。

### 项目回收恢复编排

回收恢复补充（R1091）：`RecycleRecoveryController` 在 L2 完成磁盘恢复后，仅把项目库中此次恢复的一级目录交给注入的 `Projects.register_restored_projects`；不扫描其他项目，不持有 Tk，不自行发布登记。项目服务经原注入网关保存登记，桌面层仅刷新列表；原文件恢复入口与层级不变。

### 历史层级名称的审计边界

R1094 内部等价简化：`pet_cloud.Cloud` 三个关闭入口复用私有定位定时器取消方法，先清空重试标识再取消任务；入口顺序、返回值和异常吞并不变。`storyboard_final` 移除只原样重抛的异常包装，正式发布与工作稿退役顺序不变。不新增模块、分层关系或公开接口。

`asset_gating`、`keyframe`、`keyframe_api`、`previs`、`writing_files`、`writing_workflow` 是已有分层表中未实体化的名称：可查初始树和当前树无同名模块，不能称为已迁移模块。R1028 在 `维护记录/架构统一基数.json` 的 `historical_name_audit` 登记现行职责入口；这是职责索引，不是历史重命名证明。两个迁移台账保留 `historical_name_audited` 与原基数，门禁检查缺失名称集合守恒、审计分类及现行模块/符号存在。生产层级、采用方和豁免数量均不变；不得据此宣布第 1、2 项整体完成。

R1305：`writing_quality`（L2）解析自然剧本附带的四项辅助质检，核对正文证据并生成按正文 SHA256 分版本的报告；文件发布器和目录由 L3 `writing_api` / `stage_execution_service` 注入。`workflow_settings` 在完整加载四份规则时追加辅助交付契约；桌面仅监听任务指定的单一自然剧本路径。报告不进入02输入，不新增模型调用。

## R1606 / O8：剧本页面服务注入
来源：tasks_round/tasks_round_1596_result.md 的 O8/J/K，逐页迁移策略。Desktop 在构造入口向 ScriptPagesMixin 注入不可变 ScriptPageServices，仅提供 open_path 与 context_menu。默认服务在组合入口绑定，保持现有 desktop 测试替换点；页面不再读取 desktop_page_support 的全局宿主。独立页面可注入假服务，不构建 Desktop/Tk 主窗口。

R1988 / J2（writing 页）：来源 R1983 J2。Desktop 另向 WritingPageMixin 注入不可变 `WritingPageServices`（`desktop_writing_page.py` 内定义；`open_path`、`context_menu`、`confirm`、`confirm_project_removal` 四项），默认服务在 `_init_window_and_sidebar` 里按调用时取 desktop 模块名字，测试补丁点不变；`desktop_writing_page` 不再导入 `desktop_page_support` 的全局宿主转发。仍走全局宿主的页面：project、asset、media（idea_menus 随 project）。

R1989 / J2（storyboard 页）：来源 R1983 J2。Desktop 向 StoryboardPageMixin 注入不可变 `StoryboardPageServices`（`desktop_storyboard_page.py` 内定义；`open_path`、`file_dialog`、`confirm` 三项），做法同 writing 页；`desktop_storyboard_page` 不再导入全局宿主转发。仍走全局宿主的页面：project、asset、media（idea_menus 随 project）。

R1992 / J2（project 页，含 idea_menus）：来源 R1983 J2。Desktop 向 ProjectPagesMixin 与 IdeaMenusMixin 共同注入不可变 `ProjectPageServices`（`desktop_project_pages.py` 内定义；`open_path`、`context_menu`、`confirm` 三项），两个 Mixin 不再导入全局宿主转发。仍走全局宿主的页面：asset、media。

R1993 / J2（asset 页）：来源 R1983 J2。Desktop 向 AssetPagesMixin 注入不可变 `AssetPageServices`（`desktop_asset_pages.py` 内定义；`open_path`、`file_dialog`、`confirm` 三项）；页面里对 `Desktop` 类的自引用（`Desktop.asset_write_base`／`asset_batch_gateway`）改为 `AssetPagesMixin.<同名>`，不再经全局宿主取 `Desktop`。`desktop.py` 五个默认服务统一用模块级 `_late(名字)` 在调用时取 desktop 模块当前值。仍走全局宿主的页面：media（R1995 已迁完）。

R1995 / J2（media 页，收尾）：来源 R1983 J2。Desktop 向 MediaPagesMixin 注入不可变 `MediaPageServices`（`desktop_media_pages.py` 内定义；`open_path`、`file_dialog`、`confirm`、`open_studio`、`comfy_executable`、`find_editor_shortcut`）；剧本页 `ScriptPageServices` 增 `confirm`，取代 `page_confirm`。`Desktop.__init__` 改收 `**page_services`，六页默认服务由模块级 `_page_services()` 统一构建（调用时按名字取 desktop 模块当前值）。`desktop_page_support` 的 `bind_host`／`_HostAttribute`／转发函数全部删除，只留页面常量与 `_prefs`；全局宿主已不存在，J2 完成。

剩余跨页依赖（未声称消除）：
- 剧本页面仍通过 self 使用项目上下文、通知器、导航、safe、工作流启动及聊天状态；本轮只迁移两个外部 UI 服务，不搬业务状态。
- desktop_writing_page：菜单、确认、删除最后剧本时项目确认、打开路径。
- desktop_storyboard_page：文件选择、确认、打开路径。
- desktop_asset_pages：Desktop 类静态工具转发、文件选择、确认、打开路径。
- desktop_media_pages：文件选择、确认、编辑器/ComfyUI启动工具、工作区打开。
- desktop_project_pages：菜单、确认、打开路径。
上述旧页面仍使用 desktop_page_support 兼容入口。后续按页面提供最小服务集合并迁移各自调用方；不建立包含整个 Desktop 的万能接口，不改变阶段状态权威来源。常量继续共用，不算宿主调用。

## R1607 / O9：云图生成溯源字段
来源：tasks_round/tasks_round_1596_result.md 的 O9，先建覆盖矩阵再补漏。矩阵见 维护记录/多模态溯源覆盖矩阵_20261016.md。
本轮补齐 native_asset_codec.seedream_provenance()：对已组好的 Seedream 载荷只记录摘要（payload_schema／model／size／watermark／prompt_sha256／reference_sha256），不写密钥与图片字节；keyframe_comfy.run_seedream 与 native_assets._run_seedream_direct 的每次状态写入都带 provenance。未核验的路径字段在矩阵中记未知，不据此声称全链路可复现。

## R1608 / O10：大媒体发布内存
来源：tasks_round/tasks_round_1596_result.md 的 O10。agent.core.save_file 按 1 MiB 块复制来源到目标同目录临时文件，复制期间计算 sha256 并核对来源长度，可选与调用方给的摘要比对，然后走既有 replace（登记发布事务与缓存失效）；媒体不进内存。stage_execution_service.collect_download_inbox 改用该入口并包在 publication.transaction() 内，收回下载不再是 read_bytes 加 save_bytes 的整份拷贝。文本与小产物继续用 save_text／save_bytes，既有接口语义不变。

## R1609 / O12：不付费场景与成本估算
来源：tasks_round/tasks_round_1596_result.md 的 O12。usage_overview.estimate_scenario 按场景给定的阶段用量乘费率，复用 pet_llm.RequestLedger._model_price；缺模型费率、币种或价格表版本时整场景金额返回 None 并单列未知阶段，绝不补零。场景矩阵与公式见 维护记录/成本估算与场景矩阵_20261016.md。O12 的真实账单核对部分仍按既有延期处理，不自行发起付费任务。

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

### 总控 SKILL 宪法

总控宪法（R1433 起取代统筹宪法，用户 2026-10-14 授权）：总控 SKILL 负责统一调度与内容更新。① 唯一来源是 `skills/00全流程SKILL/总控.json`，清单缺失或损坏时退回出厂内置表并在体检中报明；② 指纹覆盖清单、全流程包入口、各阶段总控 SKILL 及其直接引用，指纹一变即由 `master_skill.sync` 自动同步各阶段并提示——只替换上次总控给的项，用户自加的 SKILL 保留、用户取消勾选的总控项不重新勾上、整体弃用总控建议的阶段不追加；③ 各阶段 SKILL 勾选始终由用户自由决定，总控不锁定勾选，一切既有 SKILL 编辑与试跑入口（浏览新增、改 md 即生效、重置、按引擎附加清单）不得因总控模式而移除或变灰；④ 门禁（`master_skill.gate` 与 `stage_handler_registry` 制作锁检查）在总控模式下对手动与自动路径一律阻断：本阶段必填制作锁缺失、已勾选 SKILL 的引用不可加载；剧本准备的简报采集对话除外，由简报门禁负责。

## 当前架构门禁清单

（自 AGENTS §5 迁入，内容未改。）

当前架构门禁清单（`tests/architecture/`）：总数以 `python smoke_test.py --architecture` 当轮输出为准，基线只增不减。

- 卡片与忙碌状态补充：`test_card_boundary.py`、`test_busy_state_boundary.py`。
- 分层与一致性：`test_agents_md.py`、`test_layers.py`、`test_no_circular_import.py`、`test_path_authority.py`、`test_stage_paths.py`、`test_storyboard_edit_boundary.py`、`test_storyboard_final_selection_boundary.py`。
- 写入与删除边界：`test_atomic_write_boundary.py`、`test_asset_batch_ledger_boundary.py`、`test_asset_batch_settings_boundary.py`、`test_asset_detail_binding_boundary.py`、`test_asset_generated_import_boundary.py`、`test_asset_image_import_boundary.py`、`test_asset_plan_publication_boundary.py`、`test_asset_rename_boundary.py`、`test_asset_image_removal_boundary.py`、`test_asset_image_restore_boundary.py`、`test_audio_import_boundary.py`、`test_cloud_video_settings_boundary.py`、`test_continuity_publication_boundary.py`、`test_delivery_import_boundary.py`、`test_desktop_settings_boundary.py`、`test_edit_publication_boundary.py`、`test_final_bundle_boundary.py`、`test_handoff_publication_boundary.py`、`test_keyframe_delete_boundary.py`、`test_keyframe_restore_boundary.py`、`test_keyframe_replace_boundary.py`、`test_keyframe_reference_publication_boundary.py`、`test_legacy_adoption_boundary.py`、`test_local_video_settings_boundary.py`、`test_manual_creative_publication_boundary.py`、`test_previs_routing_publication_boundary.py`、`test_stage_workspace_boundary.py`、`test_structured_script_write_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_tts_publication_boundary.py`、`test_video_delete_boundary.py`、`test_video_options_boundary.py`、`test_video_prompt_publication_boundary.py`、`test_video_publication_boundary.py`、`test_white_model_import_boundary.py`、`test_writing_preparation_path_boundary.py`、`test_deletion_gateway.py`、`test_remove_authority.py`、`test_recycle_service.py`。
- 潜伏缺陷防复发（R1854）：`test_subprocess_timeout_boundary.py`（等子进程必须带 timeout）、`test_workflow_dir_ratchet.py`（手拼“工作流任务”只许减少）、`test_read_json_definitions.py`（`read_json` 同名定义不得新增）、`test_pet_error_log_boundary.py`（三虎 errors 必须有上限）；`test_atomic_write_boundary.py` 另以 AST 限定直接 `os.replace`／`Path.replace` 只在登记写入器内且只许减少。
- 剧本重命名边界：`test_script_rename_boundary.py`。
- 阶段/UI 契约：`test_dynamic_import_registry.py`、`test_stage_command_contract.py`、`test_completion_gate.py`、`test_event_bus_boundary.py`、`test_skill_dependency_dag.py`、`test_pipeline_stage_io_contract.py`、`test_skill_reference_injection.py`、`test_project_entry_boundary.py`。
- 依赖与平台边界：`test_import_error_boundaries.py`、`test_model_provider_boundary.py`、`test_platform_opening.py`、`test_platform_process_boundary.py`、`test_migrated_ui_boundaries.py`。
- 体验与布局：`test_responsive_layout_contract.py`、`test_combobox_boundary.py`。
- 启动预算：`test_startup_budget.py`。
- 源码文本契约锁：`test_source_text_contracts.py`（原散落在功能测试里的 `inspect.getsource` 断言，内容未动）。
- 历史兼容门面：`test_legacy_facade_manifest.py`。
- 轮次与基线／测试卫生：`test_round_baselines.py`、`test_skip_hygiene.py`、`test_silent_exception_ratchet.py`、`test_module_size_ratchet.py`、`test_todo_comment_snapshot.py`、`test_static_hygiene.py`、`test_function_size_ratchet.py`、`test_complexity_ratchet.py`、`test_print_ratchet.py`、`test_shared_state_ratchet.py`（Mixin 组合类多写者 self 属性只许减少，R1984）、`test_stable_registration.py`。
- 文档先行锚定：`test_requirement_traceability.py`（`docs/stages/` 里 ✅ 须有测试锚定，历史欠账见 `维护记录/需求锚定基线.json`，只许减少）。
- 覆盖率审计棘轮：`test_coverage_audit_ratchet.py`、`test_secret_sink_audit.py`、`test_coverage_baseline.py`。
  行覆盖度量为定向测量：工具 `scripts/coverage_report.py`（`sys.settrace`，零第三方依赖），基线 `维护记录/覆盖率基线.json`；只记基线＋核心路径下限，不重跑测量，口径与诚实边界见 `tasks_round/tasks_round_1616_result.md`。
  密钥静态审计仅覆盖有限函数内传播，支持范围与漏检／误报边界见 `tasks_round/tasks_round_1054_result.md` D–F，不将零命中解释为全路径安全。
- JSON／服务／统筹补充：`test_confirm_gates_json_boundary.py`、`test_context_menu_boundary.py`、`test_data_table_boundary.py`、`test_dialog_boundary.py`、`test_button_boundary.py`、`test_file_dialog_boundary.py`、`test_simpledialog_boundary.py`、`test_idea_attachment_publication_boundary.py`、`test_input_boundary.py`、`test_json_io_boundary.py`、`test_keyframe_batch_json_boundary.py`、`test_local_previs_json_boundary.py`、`test_notification_boundary.py`、`test_previs_automation_json_boundary.py`、`test_previs_batch_json_boundary.py`、`test_previs_monitor_json_boundary.py`、`test_project_context_boundary.py`、`test_service_return_contract.py`、`test_shortcut_registry_boundary.py`、`test_skill_orchestrator_json_boundary.py`、`test_stage_display_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_text_component_boundary.py`、`test_tooltip_boundary.py`、`test_ui_icons_boundary.py`、`test_scrollbar_theme_boundary.py`、`test_token_boundary.py`、`test_copy_entry_boundary.py`、`test_unification_ratchet.py`、`test_video_navigation_json_boundary.py`、`test_white_model_json_boundary.py`、`test_white_model_service_json_boundary.py`、`test_workflow_settings_json_boundary.py`、`test_writing_api_json_boundary.py`、`test_writing_publication_boundary.py`。

新增或删除架构测试时，必须在同一轮更新以上清单、架构基线和结果报告；不得只更新测试而遗漏本入口说明。
