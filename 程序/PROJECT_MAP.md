# 漫剧助手 · 项目地图

本图只描述源码职责和数据边界；用户项目、生成媒体和密钥都不属于源码树。

R1250：项目共享的准备文件可通过文件右键“从本阶段重新创作”进入重写。既有 preparation_state 的 documents 保留采用版本，revision.documents 保存当前待确认分支；确认后撤销下游确认并清空自然稿采用选择，历史文件不删除。切换模型本身不清空确认。API 输出发布前校验输入版本及模型选择；与按模型隔离的聊天历史分开管理。

R1247 数据边界：剧本聊天及回收站位于 `01剧本准备/模型会话/<稳定模型ID--摘要>/创意对话/`；显示名仅作展示，旧目录首次读取迁移。自然稿采用记录 `01剧本准备/natural_script_selection.json` 绑定相对路径与内容摘要，多稿须明确采用。API 快照、历史和输出归属同一次提交；用量为本模型最近回复的估算／实报，项目已确认资料仍共享。

执行与验证规则统一见 `AGENTS.md`；分层说明见 `architecture.md`，当前验收事实见 `project_status.md`；
数据字段见 `data_model.md`，任务状态与尝试链见 `task_states.md`，部署与运维见 `runbook.md`（R1625）；联调/测试阶段出口、需求→用例三态映射与缺陷守护索引见 `说明/联调测试出口基线.md`（R1627）。下列目录表是 `pet_bus.STAGES`／`STAGE_NAMES` 与 `stage_layout.STAGES` 的阅读投影，变更契约时须同步代码及文档；本轮仅校正文档，不改变权威定义。

## 核心模块

| 区域 | 入口 | 职责 |
| --- | --- | --- |
| 桌面与页面 | `app.py`、`desktop.py`、`desktop_startup_service.py`、`storyboard_files.py` | `desktop` 创建窗口和绑定事件；无 Tk 启动控制器编排首帧延迟、项目选择与取消；其余负责项目选择、13 阶段页面、文件表及关闭清理 |
| UI 设计系统 | `ui_tokens.py`、`ui_widgets.py`、`design_tokens.md`、`ui_components.md` | 设计 token 的代码化事实来源，以及主/次按钮、卡片的 Tk 组件唯一入口 |
| 三虎与自动化 | `pet_ui.py`（含 `pet_ui_stages／settings／voice／view／support`）、`pet_cloud.py`、`stage_flow.py`、`desktop_automation_service.py`、`desktop_auto_flows.py`、`desktop_idea_chat.py`、`desktop_writing_page.py`、`desktop_storyboard_page.py`、`desktop_page_support.py`、`desktop_asset_pages.py`、`desktop_script_pages.py`、`desktop_media_pages.py`、`desktop_project_pages.py`、`desktop_idea_menus.py` | 前缀播报、手动/全自动、检查点、暂停和强制停止；桌面自动流程的周期调度、取消、受控异常与到期轮询由无 Tk 服务统一编排 |
| 阶段配置 | `stage_config.py`、`stage_models.py`、`skill_panel.py` | 单次 > 项目模型优先级、SKILL、预设 |
| Codex 技能同步 | `codex_skill_sync.py` | L3：阶段单文件技能物化、来源 hash、所有权保护与孤儿回收；首帧后台和发送前校验 |
| Agent 工作流 | `workflow_settings.py`、`workflow_engines.py`、`workflow_tasks.py` | GPT/Anthropic API 在对应本机程序可启动时优先本机执行、启动失败兼容 API 回退；桌面模型显式选择、任务文件与进程台账 |
| 模型与安全 | `model_pool.py`、`model_router.py`、`pet_llm.py`、`model_secrets.py` | 厂商/模型池、协议路由、唯一密钥判据、DPAPI |
| 剧本与契约 | `idea_chat.py`、`idea_attachments.py`、`idea_chat_controller.py`、`script_contract.py`、`prompt_templates.py` | 聊天、受控文本附档、无 Tk 对话请求/节流/流式进度编排、创意工作流、五类 manifest、提示词模板 |
| 资产与连续性 | `asset_contract.py`、`asset_batch_controller.py`、`asset_thumbs.py`、`continuity_ledger.py` | 资产契约；无 Tk 批量页表单、模型检测与启动前门禁编排；受控缩略图 worker、连续性台账 |
| 分镜与批次 | `shot_batches.py`、`storyboard_selection.py` | 已采用分镜、批次/三元组约束、定稿输入 |
| 首帧/预演/视频 | `keyframe_comfy.py`、`local_previs.py`、`cloud_video.py`、`local_video.py`、`engine.py` | 首帧、白模预演；`cloud_video`／`local_video` 是 L4 云端会话设置与本地 ComfyUI 页面，云端提交与轮询在 L3 `engine.Studio`（经 `agent/wan.py`、`agent/volcengine.py` 适配器） |
| 阶段基础设施 | `stage_layout.py`、`stage_path_service.py`、`project_context.py`、`project_context_factory.py`、`stage_execution_service.py`、`stage_parallel.py`、`confirm_gates.py` | 13 阶段目录、唯一写入路径、L3 唯一工厂装配并注入的项目上下文、成果发布编排、并发限制、SG 门禁与确认门禁 |
| 成本与运行保障 | `token_saver.py`、`tk_timers.py`、`storage_maintenance.py`、`log_maintenance.py`、`workspace_maintenance.py`、`recycle_recovery_service.py`、`recycle_recovery_controller.py` | Token/媒体预算、Tk 回调回收、退出后保守清理；程序日志保留/轮转/容量帽；仓库级可再生卫生（__pycache__、超期 .selftmp、已并净 .wt 工作树）；回收清单的项目内／项目库受控恢复 |

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
| 后期剪辑 | `12后期剪辑` | 已验收的镜头视频（采用版本） | 粗剪成片与剪辑清单（落 `13质检交付/导出成片/`）、剪辑优化清单、成果确认 |
| 质检与交付 | `13质检交付` | 全部上游交付 | 验收报告与交付包 |

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
| `run_selftests.py --all --safe` | 安全全量回归、受控 Tk 工作池与清理；实际调度与超时策略以执行器为准，不等同于强制串行 |
| `test_stage_parallel.py` | SG-01~05、并发上限、阶段提示 |
| `test_script_contract.py` | 五类 manifest 与剧本契约 |
| `test_idea_chat.py` | 聊天布局、草稿、发送工作流 |
| `test_idea_chat_controller.py` | 无 Tk 对话状态、发送节流、附件注入与取消后进度丢弃 |
| `test_workflow.py` | 模型选择、本机客户端、API 回退 |
| `test_asset_thumbs.py` | 缩略图缓存、worker 回收、环境隔离 |
| `test_video_ui.py`、`test_integration.py` | 视频链路、页面接力与交付 |
| `tests/architecture/test_skip_hygiene.py` | skip 原因常量、恢复条件与源码／台账双向一致性 |

## 数据边界

- 项目数据：用户选定项目目录，阶段配置为 `<项目>/skill_config.json`。
- 全局配置：`配置/宠物/配置.json`；最后项目位于项目 UI 设置。
- 密钥：`.env`、`private/.env` 或 `private/密钥/*.dpapi`；读取判据为 `pet_llm.credential`，日志/任务 JSON 不存明文。
- 真实云端提交不自动发生；需要有效服务配置、选定素材和用户授权。

- `production_lock_fields.py`：阶段配置与创作信息窗共用制作锁视图；契约来自 `script_contract`，写入仍走 `stage_execution_service`。
