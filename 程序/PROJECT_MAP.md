# 漫剧助手 · 项目地图

本图只描述源码职责和数据边界；用户项目、生成媒体和密钥都不属于源码树。

R1250：项目共享的准备文件可通过文件右键“从本阶段重新创作”进入重写。既有 preparation_state 的 documents 保留采用版本，revision.documents 保存当前待确认分支；确认后撤销下游确认并清空自然稿采用选择，历史文件不删除。切换模型本身不清空确认。API 输出发布前校验输入版本及模型选择；与按模型隔离的聊天历史分开管理。

R1247 数据边界（R2898 更新）：剧本聊天及回收站统一位于 `01剧本准备/创意对话/`（对话.json／已删除消息.json），不再按模型分目录；旧 `模型会话/<稳定模型ID--摘要>/创意对话/` 与 `<提供方>/<模型>/创意对话/` 目录首次读取时只迁移不删地并入统一文件，显示名仅作行内署名与筛选视图。自然稿采用记录 `01剧本准备/natural_script_selection.json` 绑定相对路径与内容摘要，多稿须明确采用。API 快照、历史和输出归属同一次提交；用量为本模型最近回复的估算／实报，项目已确认资料仍共享。

执行与验证规则统一见 `AGENTS.md`；分层说明见 `architecture.md`，当前验收事实见 `project_status.md`；
数据字段见 `data_model.md`，任务状态与尝试链见 `task_states.md`，部署与运维见 `runbook.md`（R1625）；联调/测试阶段出口、需求→用例三态映射与缺陷守护索引见 `说明/联调测试出口基线.md`（R1627）。下列目录表是 `pet_bus.STAGES`／`STAGE_NAMES` 与 `stage_layout.STAGES` 的阅读投影，变更契约时须同步代码及文档；本轮仅校正文档，不改变权威定义。

## 核心模块

| 区域 | 入口 | 职责 |
| --- | --- | --- |
| 桌面与页面 | `app.py`、`desktop.py`、`orchestrator/desktop_startup_service.py`、`ui/storyboard_files.py` | `desktop` 创建窗口和绑定事件；无 Tk 启动控制器编排首帧延迟、项目选择与取消；其余负责项目选择、13 阶段页面、文件表及关闭清理 |
| UI 设计系统 | `ui_tokens.py`、`ui_widgets.py`（`Tooltip`／`Splash` 已拆到 `ui/ui_tooltip.py`／`ui/ui_splash.py`，原路径仍可导入）、`ui/ui_stage_popups.py`（阶段执行窗／手动制作窗呈现器）、`ui/ui_rounded.py`（圆角底图生成）、`ui/ui_motion.py`（行悬停淡入、加载转圈、空态提示）、`ui/ui_scroll.py`（滚轮缓动）、`ui/ui_hover_fade.py`（按钮悬停渐变）、`ui/ui_part_renderers.py`（消息 part 分派渲染：思考卡/产物行/工具行）、`ui/ui_media.py`（缩略图卡/Lightbox/多候选/收藏）、`ui/ui_code_block.py`（JSON/提示词高亮块）、`ui/ui_diff.py`（红绿 Diff）、`ui/ui_citation.py`（引用溯源）、`ui/ui_asset_card.py`（资产悬浮卡）、`ui/ui_media_player.py`（视频/音频卡）、`ui/ui_param_panel.py`（参数滑条）、`ui/ui_multimodal.py`（多模态参考）、`ui/ui_task_progress.py`（长任务进度卡）、`design_tokens.md`、`ui_components.md` | 设计 token 的代码化事实来源，以及主/次按钮、卡片的 Tk 组件唯一入口 |
| 三虎与自动化 | `ui/pet_ui.py`（Mixin 分布在 `ui/pet_ui_stages.py`／`ui/pet_ui_support.py` 与 `ui/pet_ui_settings.py`／`ui/pet_ui_voice.py`／`ui/pet_ui_view.py`／`ui/pet_ui_popup.py`）、`ui/pet_cloud.py`、`orchestrator/stage_flow.py`、`orchestrator/stage_handler_registry.py`、`orchestrator/stage_exec.py`、`orchestrator/desktop_automation_service.py`、`ui/desktop_auto_flows.py`、`ui/desktop_idea_chat.py`、`ui/desktop_writing_page.py`、`ui/desktop_files_panel.py`（主界面右上角「项目文件」入口与右侧停靠文件面板，REQ-S01-90）、`ui/desktop_storyboard_page.py`、`ui/desktop_page_support.py`、`ui/desktop_asset_pages.py`、`ui/desktop_script_pages.py`（含 `ui/desktop_script_edit_session.py` 剧本框编辑会话：自动保存／右键菜单／撤销快捷键；剧本结构页双阅读框的装配点，经 `ui/script_line_numbers.py` 行号槽、`ui/script_find_bar.py` 查找替换条、`ui/script_outline.py` 大纲面板、`ui/script_reading.py` 阅读辅助编排四个 L4 模块实现，REQ-S02-36）、`ui/desktop_media_pages.py`、`ui/desktop_project_pages.py`、`ui/desktop_idea_menus.py` | 前缀播报、手动/全自动、检查点、暂停和强制停止；桌面自动流程的周期调度、取消、受控异常与到期轮询由无 Tk 服务统一编排；阶段启动唯一入口 `stage_handler_registry.start()`，全自动档按阶段配置已勾选 SKILL（面板顺序）派发（R2905），无勾选阶段标 skipped 跳过并提示，成果仍经 `stage_completion_service` 核验 |
| 阶段配置 | `orchestrator/stage_config.py`、`orchestrator/stage_models.py`、`ui/skill_panel.py`（＋`ui/skill_panel_workflow.py` 制作锁弹窗、`ui/skill_panel_import.py` SKILL 导入、`ui/skill_panel_support.py`）、`orchestrator/skill_registry.py`（＋`orchestrator/skill_project_layer.py` 项目层路径口径与禁用登记、`orchestrator/skill_package_meta.py` 外部包受控元数据）、`ui/skill_archive.py`／`ui/skill_remote_service.py`（ZIP／远程链接导入）、`ui/skill_lifecycle_service.py`（SKILL 定位/改名/启停用/删除入口）、`ui/skill_security_service.py`（外部包可执行内容警示）、`domain/skill_command.py`（`/` 命令解析与触发 token 扫描）、`desktop_shared_input.py`（共享底部输入框）、`desktop_shared_send.py`（13 页发送分流）、`ui/desktop_shared_menus.py`（✦／＋ 图标下拉面板 R2971＋`/`/`@` 光标候选浮层 R2980） | 单次 > 项目模型优先级、SKILL 勾选与说明（三层：内置 `skills/`＋用户 `data/skills/`＋项目 `<项目>/skills/`，同名 项目＞用户＞内置，R3054；体检 `orchestrator.workflow_settings.skill_health_report`、检查更新 `ui.skill_import_service.check_updates`）、`production_locks` 制作锁（R2862 起无总控预设）、`/` 命令与上游发送门禁（R2893）、13 页共用输入框与按模型隔离取消（R2898） |
| Agent 技能同步 | `orchestrator/agent_skill_sync.py`（`orchestrator/codex_skill_sync.py` 为 Codex 单目标兼容入口） | L3：阶段单文件技能物化到 codex／claude／agents 三目标、来源 hash、所有权保护与孤儿回收；首帧后台和发送前校验 |
| Agent 工作流 | `orchestrator/workflow_settings.py`、`orchestrator/workflow_engines.py`、`orchestrator/workflow_tasks.py` | GPT/Anthropic API 在对应本机程序可启动时优先本机执行、启动失败兼容 API 回退；桌面模型显式选择、任务文件与进程台账 |
| Agent 运行时 | `agent/core.py`（命令执行、JSON 读写、hash、原子复制发布）、`agent/media.py`（ffprobe/ffmpeg 媒体探测与技术质检；`is_png`/`PNG_SIGNATURE` 事实已下沉 L0 `contract/media_signature.py`，此处再导出）、`agent/publication.py`（可恢复发布事务与期刊）、`agent/shot_assets.py`（分镜身份→项目图片解析）、`agent/video.py`＋`agent/wan.py`＋`agent/volcengine.py`（`VideoAdapter` 抽象与万相/火山方舟适配）、`agent/h3_reference_adapter.py`（H3 Ref2VA 参考资产接入，自 `infra/` 上移 L2）、`agent/voice_mcp_server.py`、`agent/optimizer_mcp_bridge.py`（两个 MCP stdio 服务）、`agent/prompt_optimizer.py`（提示词优化器桌面集成） | R3255 起 `agent/` 为第六个分层包并纳入 `_scan.PACKAGE_NAMES`：core/media/publication→L1、shot_assets/volcengine/wan/video/h3_reference_adapter→L2、voice_mcp_server/optimizer_mcp_bridge→L3、prompt_optimizer→L4；媒体签名判定是 L0 事实 |
| 模型与安全 | `infra/model_pool.py`、`infra/model_router.py`、`infra/pet_llm.py`、`infra/model_secrets.py`、`infra/http_client.py`、`contract/error_codes.py`、`contract/diagnostics.py`、`contract/selfcheck.py` | 厂商/模型池、协议路由、唯一密钥判据、DPAPI；`http_client` 是 L1 统一 JSON HTTP 传输（超时必填、错误码分类、有界重试、响应上限、凭据脱敏），直连 `urlopen`／`build_opener` 由 `test_http_boundary` 白名单棘轮守卫；L0 错误码注册表实体在 `contract/error_codes.py`（R3267 起每码带 `severity` 闭集并有 `analyze()` 派发链；R3300 起有 `classify()` 错误文本分类器与 `TEXT_RULES` 关键词表，retryable 为「是否重试」唯一权威、接线在轮 5B），顶层 `error_codes.py` 为历史门面；`contract/diagnostics.py` 是启动诊断类型唯一权威（`Severity`／`Diagnostic` 含 `escape_hint`／`StartupPhase`），`contract/selfcheck.py` 是注入式自检运行器 `run(checks)`（检查由上层注入、自身异常记 DEGRADED，R3267，启动器接线在后续轮）；`contract/infra_errors.py` 是 L1 技术异常层级唯一权威（`InfraError` 根＋七族，`code` 经 `error_codes` 登记校验、兼容内置异常多重继承，R3407／I6）；共享输入发送瞬间锁定模型快照（`desktop_shared_input.request_snapshot`，R2893），在途请求不受中途切模影响 |
| 人在回路 | `domain/hitl.py`（HITL 请求/决策信封）、`ui/ui_hitl.py`（审批门三按钮/选择卡） | 选择卡/审批门/红绿 Diff 共用 `HITLRequest{kind,payload,risk,timeout}` → `Decision` 协议；低风险自动放行、高风险人工、超时竞速；`from_confirm_result` 把 `confirm_gates.ask` 转成选择卡 |
| 分支与断点 | `domain/checkpoint_tree.py`（append-only checkpoint 树）、`ui/ui_branch_tree.py`（节点树） | `(thread_id, checkpoint_id, parent_id)` 树，分支只追加不覆盖；state 小 JSON + `artifact_refs` 存引用；剪枝改挂根；节点树切换/延续/独立提问 |
| 剧本与契约 | `idea_chat.py`、`domain/idea_attachments.py`、`orchestrator/idea_chat_controller.py`（`ChatStatus` 会话状态机＋取消令牌＋发送排队＋继续/重新生成计划）、`domain/message_parts.py`、`script_contract.py`、`prompt_templates.py` | 聊天、受控文本附档、无 Tk 对话请求/节流/流式进度编排、会话级状态机、创意工作流、消息 typed parts 契约（schema v2：一条消息 = 有序 text/reasoning/tool_call/artifact 等 part）、五类 manifest、提示词模板 |
| 离线语音识别 | `voice_engine/`（独立 ASR 运行时：`offline_asr_server` 常驻引擎、`funasr_config` 模型配置、`download_models` ModelScope 缓存解析、`bootstrap` venv 引导）、`domain/speech_api.py`（后端路由：`create_session` 按 `backend` 分流 offline/cloud，设置合并 `data/语音识别.json`；`data/语音词典.json` 热词/同音替换表/AI 配置读写校验并注入会话）、`domain/offline_asr_client.py`（离线子进程会话：宿主常驻、JSON-Lines 喂 PCM/收逐句、超时强杀、崩溃降级云端）、`domain/voice_ai.py`（听写文本模板化 AI 优化，`chat` 注入式）、`ui/desktop_voice_input.py`（跨页听写组件：`MicrophoneRecorder` PCM → 会话事件 → 输入框光标处 partial/final 浅色渲染，`BackgroundTaskLifecycle` 代次、输入框销毁即停；会话关闭后按词典运行 AI 优化并复核区域再回写）、`desktop_shared_input.py`（麦克风按钮＋唯一听写实例，13 页共用）、`agent/voice_mcp_server.py`（MCP stdio `voice_transcribe`：WAV/PCM→离线转写，供 agent 客户端调用）、`ui/speech_settings_ui.py`（后端/离线运行时/词典/AI/MCP 设置弹窗） | 离线为主的语音输入后端：主程序零第三方依赖，经 stdio JSON Lines 与独立子进程通信；FSMN-VAD 逐句断句 → Paraformer ASR → CT-punc 逐句出字；模型首次自动下载至 `data/voice_models/`（`local_files_only` 优先），依赖只装独立 venv `data/voice_asr_venv/`；麦克风入口统一在共享底部输入框（按钮全平台常驻，非 Windows 由录音机层报原因），剧本页 composer 工具行重复入口已收敛；热词随 `start.hotword` 下发（仅支持热词的上下文模型生效，否则忽略并记诊断），同音纠错由替换表确定性完成 |
| 资产与连续性 | `asset_contract.py`、`orchestrator/asset_batch_controller.py`、`ui/asset_thumbs.py`、`infra/continuity_ledger.py` | 资产契约；无 Tk 批量页表单、模型检测与启动前门禁编排；受控缩略图 worker、连续性台账 |
| 分镜与批次 | `shot_batches.py`、`orchestrator/storyboard_selection.py` | 已采用分镜、批次/三元组约束、定稿输入 |
| 首帧/预演/视频 | `ui/keyframe_comfy.py`、`ui/local_previs.py`、`ui/cloud_video.py`、`local_video.py`、`orchestrator/engine.py` | 首帧、白模预演；`ui/cloud_video`／`local_video` 是 L4 云端会话设置与本地 ComfyUI 页面，云端提交与轮询在 L3 `engine.Studio`（经 `agent/wan.py`、`agent/volcengine.py` 适配器） |
| 阶段基础设施 | `stage_layout.py`、`stage_path_service.py`、`project_context.py`、`orchestrator/project_context_factory.py`、`stage_execution_service.py`、`orchestrator/stage_parallel.py`、`domain/confirm_gates.py` | 13 阶段目录、唯一写入路径、L3 唯一工厂装配并注入的项目上下文、成果发布编排、并发限制、SG 门禁与确认门禁 |
| 成本与运行保障 | `infra/token_saver.py`、`infra/tk_timers.py`、`infra/storage_maintenance.py`、`infra/temporary_sweep.py`、`infra/log_maintenance.py`、`infra/workspace_maintenance.py`、`infra/executors.py`（命名有界执行器 io/cpu/network/gpu/stream 五池＋供应商并发闸门，I10／L1-H8；I11 起 L2/L3 线程全经此边界）、`infra/metrics.py`（结构化指标 counter/observe/query：维度白名单＋project 哈希，raw JSONL＋sqlite 日汇总，后台保留期清理，I14／L1-H3）、`infra/resources.py`（资源感知：snapshot 内存/磁盘空间/磁盘IO/网络计数/可选显存，ensure_free 写前磁盘闸门原语，429＋Retry-After 限额学习取配置 rpm 较小值；psutil/nvidia-ml-py 惰性导入，I15／L1-Q12）、`infra/budget.py`（预算引擎机制：check_amount 超限判定／headroom 剩余量／reserve·settle·cancel 转 request_ledger，limits 越线抛 BudgetRejected／summary 按 kind·stage·provider 成本聚合，I16／L1-Q13）＋`orchestrator/pet_budget.py`（pet 五类配额策略 L3：kind/别名/默认额度/90% 预警/会话计数，判定委托 infra.budget，I16／FL-13）、`domain/recycle_recovery_service.py`、`orchestrator/recycle_recovery_controller.py` | Token/媒体预算、Tk 回调回收、退出后保守清理与项目打开后遗留临时文件清扫；程序日志保留/轮转/容量帽；仓库级可再生卫生（__pycache__、超期 .selftmp、已并净 .wt 工作树）；回收清单的项目内／项目库受控恢复；线程工作经执行器提交（队列满 `QuotaError`、取消标记、限时关闭），L2/L3 直接建线程由 `test_thread_boundary` 棘轮守卫 |
| 用量统计 | `infra/usage_snapshot.py`、`infra/usage_history.py`、`ui/ui_usage_indicator.py`、`ui/ui_usage_detail.py`；`infra/request_ledger.py` 结算挂接、`desktop.py` 右上角挂载 | 模型调用用量快照（今日明细＋项目累计 `usage_summary.json`＋跨天归档 `usage_history/YYYY-MM.json`）；金额只在有 `cost_profile.json` 价格表时由 `request_ledger.report(price_table)` 折算，全程 Decimal；结算后经 `pet_bus` `usage_updated` 事件刷新右上角指示器（Token/¥/余额，三档阈值色）与详情、今日明细弹窗（CSV 导出 UTF-8-SIG） |

### 日志维护归属

程序日志运行期维护由 `Desktop.finish_close()` 在窗口销毁后委托 L3 `exit_maintenance.launch_cleanup()`，其正常退出分支调用 `log_maintenance.launch_cleanup()`，委托后台 `--cleanup` 工作进程；强制退出跳过，启动路径不调用。`log_maintenance` 统一负责程序自有日志的保留、轮转和容量限制，参数以其代码常量为准。协调入口的有界脱敏摘要只说明派发情况，不声称后台已完成。

`scripts/maintain_logs.py` 仅复用同一实现供显式运维，不另设调度或策略；手动检查用 `--dry-run`，实际维护会改变受管日志，不应为验证文档而执行。维护范围为程序 `logs/`、`维护记录/` 的受管日志，不递归用户项目。

## 13 阶段目录与交付契约

| 阶段 | 当前目录 | 主要输入 | 主要交付 |
| --- | --- | --- | --- |
| 剧本准备 | `01剧本准备` | 创意、对话、SKILL | 原稿、下载剧本、`emotion_curve.json` |
| 剧本结构 | `02剧本结构` | 被采用的自然剧本 | 结构化剧本 |
| 初步分镜 | `03初步分镜` | 已确认结构剧本 | 分镜初稿 JSON |
| 分镜预演 | `04分镜预演` | 分镜提示词、共享参考图、临时声音 | `animatic_manifest.json`、镜头草图、Animatic 视频 |
| 资产管理 | `05资产管理` | 已采用分镜初稿、预演确认（SG-B）、参考图 | `assets.json`、正典板、锚点 |
| 连贯性清单 | `06连贯性清单` | 被采用分镜、资产 | `continuity_ledger.json`、`continuity_ledger.md`、`continuity_issues.json` |
| 分镜定稿 | `07分镜定稿` | 初稿、资产、台账 | 已采用分镜、`batch_id`（`episode.json` + `assets.json`） |
| 首帧管理 | `08首帧管理` | 批次、锚点 | 非空首帧文件 |
| 白模预演 | `09白模预演` | 首帧、镜头动作 | 复杂与中等动作镜头的可播放预演（镜头级 `预演记录.json` 在白模成果目录；项目内副本与索引 `output/previs.json`） |
| 视频生成 | `10视频生成` | 预演、视频提示词 | 视频任务/成片 |
| 配音与字幕 | `11配音与字幕` | 定稿分镜、台词 | 音频、字幕 |
| 后期剪辑 | `12后期剪辑` | 已验收的镜头视频（采用版本） | 粗剪成片（含可选转场与背景音乐）、`edits.json`、平台版本与剪辑清单（落 `13质检交付/导出成片/`）、剪辑优化清单、成果确认 |
| 质检与交付 | `13质检交付` | 全部上游交付 | 质检结论与交付包（`qc_report.json／delivery.json／delivery_manifest.json`） |

旧 `00_script`—`10_qc_delivery` 仅由 `stage_layout.LEGACY_STAGE_ALIASES`
在读取历史项目时兼容；不得创建或作为新项目写入目录。

R1124 插入 Animatic 后，旧中文编号目录由 `stage_path_service.read_dirs()` 只读兼容。
首次修改经 L3 `prepare_stage_write()` 复制至 `write_dir()` 的新编号目录：保留新目录已有文件、复制缺失文件，发布失败恢复新目录，旧目录不搬移、不删除、不回写。
共享参考图由 `shared_reference_dir()` 定位；分镜预演准备参考图，正式资产复用，资产提示词及正典板仍归资产管理。

## 门禁与契约关系

```text
分镜初稿               ── SG-A ──> 分镜预演
预演节奏/时长/对白确认  ── SG-B ──> 资产管理
资产逐项导图 + 角色锚点 ── SG-01 ──> 连贯性台账
连续性台账              ── SG-02 ──> 分镜定稿
已采用分镜 + batch_id   ── SG-03 ──> 首帧管理
非空首帧                ── SG-04 ──> 白模预演
复杂镜头的可播放白模预演 ── SG-05 ──> 视频生成
```

五类剧本 manifest 是 `character_manifest`、`scene_manifest`、`prop_manifest`、`scene_breakdown`、`emotion_curve`；它们为资产、分镜和连续性阶段提供结构化输入。产出方与落盘阶段唯一定义在 `script_manifest_schema.PRODUCERS`（各阶段 outputs 同源于 `script_manifest_contract.STAGE_MANIFESTS`；02 的三份由结构剧本派生写入并核验，03 的 `scene_breakdown` 由已采用分镜派生并核验）：`emotion_curve` 由 01 剧本准备产出，`character_manifest`／`scene_manifest`／`prop_manifest` 由 02 剧本结构产出，`scene_breakdown` 由 03 初步分镜产出。门禁只在上游已开始却不完整时拦截；空项目始终放行。

## 验证地图

| 测试 | 守护内容 |
| --- | --- |
| `smoke_test.py` | 快速导入、静态名称、受影响模块门禁 |
| `run_selftests.py --all --safe` | 安全全量回归、受控 Tk 工作池与清理；薄壳入口＋`selftest_env`/`selftest_discovery`/`selftest_receipts`/`selftest_scheduling`/`selftest_reporting`（基座/发现/凭据/调度/报告）；实际调度与超时策略以执行器为准 |
| `test_stage_parallel.py` | SG-01~05、并发上限、阶段提示 |
| `test_script_contract.py` | 五类 manifest 与剧本契约 |
| `test_idea_chat.py` | 聊天布局、草稿、发送工作流 |
| `test_idea_chat_controller.py` | 无 Tk 对话状态、发送节流、附件注入与取消后进度丢弃 |
| `test_chat_status.py` | 对话状态机（ChatStatus）、取消令牌、继续/重新生成计划、发送排队、副作用幂等 |
| `test_part_renderers.py` | 消息 part 分派渲染（思考卡折叠、产物/工具行、skip_text） |
| `test_message_toolbar.py` | 单条消息工具栏（复制/删除/编辑重发/引用/重新生成） |
| `test_hitl.py` | HITL 信封（风险分级、自动放行、超时、EDIT 回填、confirm_gates 适配） |
| `test_hitl_ui.py` | 审批门三按钮、选择卡单选回填 |
| `test_media_render.py` | 缩略图卡多候选切换/收藏/Lightbox |
| `test_code_highlight.py` | JSON 词法高亮、代码块收起/复制/应用 |
| `test_diff_view.py` | 行级红绿 Diff 与接受/拒绝 |
| `test_checkpoint_tree.py` | append-only checkpoint 树、fork 不覆盖、剪枝 |
| `test_branch_tree_ui.py` | 分支节点树渲染、切换、延续/独立提问 |
| `test_citation.py` | `[n]` 引用标记、tag 绑定、source 序号映射 |
| `test_asset_hovercard.py` | 资产名高亮、悬浮卡弹出/关闭 |
| `test_video_audio_card.py` | 视频/音频卡试听/播放、确认采用、导出 SRT |
| `test_param_panel.py` | 参数面板读取与写回 |
| `test_multimodal_upload.py` | 图片/音频参考 → FILE part |
| `test_background_task.py` | 长任务进度、完成回调、转后台 |
| `test_workflow.py` | 模型选择、本机客户端、API 回退 |
| `test_asset_thumbs.py` | 缩略图缓存、worker 回收、环境隔离 |
| `test_video_ui.py`、`test_integration.py` | 视频链路、页面接力与交付 |
| `tests/architecture/test_skip_hygiene.py` | skip 原因常量、恢复条件与源码／台账双向一致性 |

## 数据边界

- 项目数据：用户选定项目目录，阶段配置为 `<项目>/skill_config.json`。
- 全局配置：`配置/宠物/配置.json`；最后项目位于项目 UI 设置。
- 密钥：`.env`／`private/.env` 首次读取时迁进 `private/密钥/*.dpapi`（`infra.model_secrets.import_env_keys`，记录在 `private/env_imported.json`，之后不再读 .env、文件不删）；读取判据为 `infra.pet_llm.credential`，日志/任务 JSON 不存明文。
- 真实云端提交不自动发生；需要有效服务配置、选定素材和用户授权。

- `production_lock_fields.py`：阶段配置与创作信息窗共用制作锁视图；契约来自 `script_contract`，写入仍走 `stage_execution_service`。
