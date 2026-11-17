# 任务书 · 文件卡片交互 + 人在回路（HITL）交互模块

> 本任务书自包含，执行者无需本会话上下文。这是一个**跨 8 轮的架构级功能重构**，每轮一个可独立回滚的变更集，
> 按顺序执行；每轮单独领号、验收、提交（`AGENTS.md` §2.5–§2.6、§7）。
> 开工前必读：`程序/AGENTS.md` §0、§2（硬约束）、§5（测试）；分层见 `程序/architecture.md` 第 3 节。
> 收尾要求：全部轮次完成后在 `程序/tasks_round/任务完成/文件卡片与HITL交互任务书·任务完成.md` 输出同名任务完成文件（`runbook.md` §16）。

---

## 0. 背景与结论速览

「漫剧助手」是 Windows 桌面应用（Python + Tkinter，**零第三方依赖**，13 阶段向导）。当前聊天能力**只存在于 01 剧本准备的创意对话气泡区**，02–13 页模型输出直接写阶段文件、无气泡；已有一个跨 13 页的底部共享输入框（`/` 命令、附件、模型选择器、发送门禁）。

本任务书把「文件/产物卡片（Artifact Card）」与「人在回路（HITL）」建成可复用的交互体系，**借鉴 GitHub 成熟框架的概念架构（数据模型/状态机/消息类型体系），不 import 任何库**。选型依据见 §2.2。

---

## 1. 总目标与架构蓝图

```
┌────────────────────────────────────────────────────────────────┐
│ 左侧：13 阶段目录（切换页面 = 切换当前阶段/产物上下文）            │
│ 中部：当前阶段内容                                               │
│   01 剧本准备：完整「产物卡片聊天」（气泡 = 有序 typed parts）      │
│   02–13：无自由聊天气泡；展示「产物卡片流 + 任务进度卡 + HITL 审批」 │
│ 底部：一个【共享输入框】（固定、跨 13 页复用，R2893/R2898 已落地）  │
│   [skill][附件(多模态)] [输入框] [参数滑条][模型][发送]            │
│ 侧边/悬浮：会话分支节点树（可切换对比）；引用溯源侧栏；资产悬浮卡    │
└────────────────────────────────────────────────────────────────┘
  一条消息 = 有序 typed parts：text/reasoning/tool_call/tool_result/
             source/file/artifact/data（每 part 自带子状态）
  两层状态机：会话级 ChatStatus + part 级子状态（后台线程产出增量事件，
              queue 回传 → after() 节流刷新）
  HITL 信封：HITLRequest{kind,payload,risk,timeout} → Decision{…}，
             审批门/选择卡/红绿 Diff 共用，禁止散落弹窗
  断点/分支：json+sqlite3 append-only 树 (thread_id,checkpoint_id,parent_id)，
             存引用不存内容，分支永不覆盖
```

**关键不变**：13 阶段顺序与「下阶段依赖上阶段产物」规则不动（`stage_parallel`/`confirm_gates`/`stage_completion_service` 强制）；阶段 skill 体系不动；**零第三方依赖**；`pet_bus`/`broadcaster` 事件契约不动。

**上下文模型（已拍板）**：延续 R2893 的「共享事实（`ProjectContext`）、不共享对话」；01 单线程对话历史保留，02–13 无对话历史、只有产物卡与审批记录。

---

## 2. 已确认决策清单（执行者必须遵守，不得自行变更）

### 2.1 范围与优先级（用户已确认）

| 项 | 决策 |
| --- | --- |
| Q1 目标落点 | **B**：01 升级为完整产物卡片聊天；02–13 增加「产物/任务卡片流 + HITL 审批」但**不引入自由聊天气泡**（保持 R2893「02–13 无气泡」） |
| Q2 富媒体硬约束 | **A**：图片类（缩略图/Lightbox/多候选对比/代码高亮/红绿 Diff）**原生 Tk 实现**；视频/音频**外部系统播放器**打开（卡片只放封面/缩略图 + 播放按钮）；音频波形用静态近似图。**不打破零依赖** |
| Q3 复用架构 + 冲突裁决 | **确认**：「复用 GitHub 架构」＝借鉴数据模型/状态机/消息类型的概念设计，不 import 任何库；「重复冲突时优先采用框架规则」＝授权在冲突处**重构现有实现**（含同步修改测试契约，见 `AGENTS.md` §2.4） |
| Q4 本轮交付物 | **确认**：本任务书只规划、不实现；实现由后续轮次按本任务书执行 |
| Q5 功能分期 | **确认**：按 P0 → P1 → P2 分期（见 §4 轮次映射） |

### 2.2 框架选型依据（概念层，不 import）

| 模块 | 抄谁（概念） | 落地要点（零依赖） |
| --- | --- | --- |
| 数据模型 | [Vercel AI SDK](https://github.com/vercel/ai) `UIMessage` parts 数组 + [Anthropic content blocks](https://platform.claude.com/docs/en/build-with-claude/streaming) | 一条消息 = 有序 typed parts；Python `dataclass+Enum` 复刻；**第一天版本化 schema**（吸取 AI SDK 4.2 有损迁移教训，见 [ai-sdk-compat](https://www.npmjs.com/package/ai-sdk-compat)） |
| 状态机 | AI SDK `ChatStatus`(submitted/streaming/ready/error) + Anthropic `content_block_start/delta/stop + stop_reason` | 两层解耦；后台线程产 `(block_index,delta)` → `queue` → `after()` 节流；**停止 = 取消令牌**（非关线程，见 [ably: stop 不取消流](https://ably.com/vercel/why-vercel-ai-sdk-stop-doesnt-cancel-the-stream)） |
| 产物卡/版本/Diff | [Vercel ai-chatbot](https://github.com/vercel/ai-chatbot) `Artifact{kind,identifier}` + `Document` 复合主键版本化 | `difflib.SequenceMatcher` 红绿 Diff；更新复用 `identifier` 实现同产物多版本 |
| 分支/节点树 | [LobeChat](https://github.com/lobehub/lobe-chat) topic 树 + [LibreChat](https://github.com/danny-avila/LibreChat) fork 三选项 | `parentId` 树 + 增量索引；「延续 vs 独立」两模式 |
| 引用溯源 | [Open WebUI](https://github.com/open-webui/open-webui) `<sources>` | `Text.tag_bind("cite[n]")` 定位原文档；**引用走独立字段，不原地改历史消息**（见 [issue #33852](https://github.com/open-webui/open-webui/issues/33852)） |
| HITL 协议 | [Temporal](https://github.com/temporalio/temporal)「等 signal+超时竞速」+ [LangGraph](https://github.com/langchain-ai/langgraph)「interrupt 返回值」+ [Anthropic](https://www.anthropic.com/engineering/how-we-contain-claude)「同一信封+允许改输入」 | `HITLRequest→Decision` 统一信封；选择卡=interrupt 返回值；审批门/DIFF 用同一协议 |
| 断点/分支存储 | LangGraph `(thread_id,checkpoint_id,parent_id)` append-only 树 | `json+sqlite3`；存引用不存内容 + 定期剪枝 |
| 工具/思考/计划卡 | [shadcn AI Elements](https://github.com/shadcn-ui/ui) `Trace` 统一步骤形状 | `TraceStep{type,state,args,result}`，UI 分派折叠/展开 |
| 资产悬浮卡 | **全行业空白，自建**（借鉴 LobeChat 角色卡） | `Text.tag_bind("<Enter>")` 弹 `Toplevel` 悬浮卡——Tk 原生最适合 |

### 2.3 补充的缺失功能（新增，非用户原清单；来源=成熟框架缺陷与项目缺陷）

| # | 新增功能 | 来源依据 | 落点轮次 |
| --- | --- | --- | --- |
| A1 | **停止 = 取消令牌语义**（停止真正停后台生成、不扣费；非关线程/丢结果） | AI SDK `stop()` 缺陷 | 轮 2 |
| A2 | **消息 schema 版本化**（parts 数组从第一天写死 `schema_version`） | AI SDK 4.2 有损迁移 | 轮 1 |
| A3 | **引用/产物上下文走独立字段**（不原地改历史消息，保护 prompt-cache） | Open WebUI #33852 | 轮 7 |
| A4 | **审批超时 + 风险分级升级**（低风险自动放行、高风险才人工，避免 93% 橡皮图章） | Anthropic 工程手册 | 轮 4 |
| A5 | **副作用幂等/后置**（中断恢复时副作用不重复执行） | LangGraph 节点重跑坑 | 轮 2、轮 6 |
| A6 | **增量索引 + 分页/懒加载 + 摘要压缩**（长会话性能） | LobeChat #20242 | 轮 6 |
| A7 | **消息队列**（生成中发送自动排队、可撤销、turn 结束 flush） | Claude Code 模式 | 轮 2 |
| A8 | **工具卡耗时统计**（tool_call 卡显示耗时） | Claude Code 模式 | 轮 3 |
| A9 | **多候选并排对比**（图片候选左右滑动/并排） | Open WebUI MultiResponse | 轮 5 |
| A10 | **删除/撤回走 `storage_maintenance.recycle_paths` 语义**（聊天消息进 `已删除消息.json`，可恢复） | 项目硬约束规则 14 + R1247 | 轮 3 |

---

## 3. 现状盘点（执行者必读文件）

| 文件/模块 | 现状 | 本次动作 |
| --- | --- | --- |
| `idea_chat.py`（L2） | 创意对话文件/持久化逻辑；`reply_text` 把 thinking 解析剥离后**丢弃**；`save_reply`/`history_*` 基于扁平 rows | 轮 1 引入 parts 模型；thinking 改为 REASONING part 保留；rows 适配 parts |
| `idea_chat_controller.py`、`orchestrator/idea_chat_controller.py`（L3） | 无 Tk 对话状态、发送节流、取消（取消后**丢弃进度**） | 轮 2 引入 `ChatStatus` + 增量事件 + 取消令牌 + 继续/重新生成 |
| `desktop_idea_chat.py`、`desktop_idea_bubbles.py`（L4） | 01 气泡显示/折叠/复制/编辑、附件、语义简报、`send_message`、`open_flow_agent` | 轮 3 重构为 part 分派渲染器 + 消息工具栏，不保留平行旧实现 |
| `desktop_shared_input.py`、`skill_command.py`、`desktop_shared_send.py`、`desktop_shared_menus.py`（L4/L2） | 共享输入框、`/` 命令面板、发送分流、place 菜单 | 轮 8 `/` 面板对齐 Command Palette；附件入口对齐多模态上传；参数滑条入口 |
| `desktop_file_card.py`、`desktop_files_panel.py`（L4） | 文件表悬停预览卡（`TreeRowCard`/`script_row_card`）、文件表 | 轮 3 扩展为产物卡（一键操作）；轮 5 接富媒体渲染 |
| `confirm_gates.py`（L2） | 阶段审批门（现有） | 轮 4 收编进 HITL 信封；风险分级 + 超时 |
| `pet_bus.py`、`broadcaster.py`（L0） | 事件总线、播报前缀 | 轮 4 新增 HITL 事件（`pet_bus.emit_safe`），前缀走 `broadcaster` |
| `artifact_schema.py`（L1） | 持久化产物版本（`schema_version`） | 轮 1 消息 parts 复用其版本口径 |
| `storage_maintenance.py`（L1） | 删除/回收唯一权威 | 轮 3 撤回/删除走 `recycle_paths` 语义 |
| `stage_execution_service.py`、`stage_path_service.py`（L3/L1） | 阶段成果发布、阶段路径 | 02–13 产物卡读取阶段文件（复用发布器，不改写） |
| `ui_widgets.py`、`ui_tokens.py`、`ui_rounded.py`、`ui_motion.py`、`ui_scroll.py`（L4） | UI 组件/token/圆角/动效/滚轮 | 复用；新增「kind→渲染器」注册表 |
| `design_tokens.md`、`ui_components.md` | 设计 token 与组件契约唯一权威 | 轮 3 新增卡片/HITL 卡 token 与组件契约 |
| 三虎（`pet_dock`/进度界面/暂停恢复）、`BackgroundTaskLifecycle` | 进度、暂停恢复、后台任务生命周期 | 轮 8 后台任务队列 + 通知接入 |
| `notifier`（`app.py`） | 已有状态通知 | 轮 8 系统通知复用 |

---

## 4. 分轮拆解（8 轮，按序执行）

> P0 = 轮 1–4；P1 = 轮 5–7；P2 = 轮 8。每轮改动 + 验收勾选。

### 轮 1：消息 parts 数据模型 + schema 版本化 + 对话.json 迁移

**改动**
- 新增 L0/L1 契约模块（建议 `message_parts.py`，或扩展 `artifact_schema.py`）：`PartType` 枚举（TEXT/REASONING/TOOL_CALL/TOOL_RESULT/SOURCE/FILE/ARTIFACT/DATA）、`PartState`（如 `ARGS_STREAMING/CALL/RESULT/ERROR`、`CREATING/STREAMING/DONE/ERROR`）、`Part{type,payload,state}`、`Message{id,role,created_at,parts}`、`Artifact{kind,identifier,title}`、`Document{id,created_at}` 复合主键。
- `01剧本准备/创意对话/对话.json` 迁移：现有扁平结构（thinking 剥离丢弃）→ parts 数组；thinking 落为 REASONING part；旧文件首次读取一次性迁移（只迁移不删旧），新写入带 `schema_version`；`已删除消息.json` 同口径。
- `idea_chat.reply_text`/`save_reply`/`history_*` 改走 parts；`idea_chat_controller` 消息行适配 parts。

**验收**
- [ ] 新增 `tests/test_message_parts.py`：Part/Message 序列化往返、schema_version、旧扁平→parts 迁移（thinking 保留为 REASONING、正文不丢）。
- [ ] 旧 `对话.json` 打开后迁移成功且原内容不丢；`test_idea_chat*` 相关回归全绿（契约变更断言同步改写）。
- [ ] `python -B smoke_test.py` 8/8；动到 L0 契约则 `--architecture` 全绿。

### 轮 2：两层状态机 + 流式增量事件 + 取消令牌（停止/继续/Regenerate）

**改动**
- `idea_chat_controller`（L3）引入 `ChatStatus`（SUBMITTED/STREAMING/READY/ERROR）+ part 级子状态；后台线程产 `(block_index, delta)` 增量事件 → `queue` 回传 → `after()` 节流刷新（复用现有 `model_metering.metered` 发送/取消链路）。
- **停止 = 取消令牌**（显式 cancel event 交给后台 worker，不再「关线程/丢结果」）；**继续生成**（保存中断点，从 checkpoint 续跑）与**重新生成**（Regenerate：同消息重发）。
- 事件契约对齐 Anthropic `content_block_start/delta/stop + stop_reason`；`stop_reason=max_tokens` 触发「继续」提示；消息队列（生成中发送排队、可撤销、turn 结束 flush）。
- 副作用幂等/后置：中断恢复时副作用不重复执行。

**验收**
- [ ] 新增 `tests/test_chat_status.py`：状态迁移、取消令牌语义（停止后后台真停）、继续/重新生成、消息队列。
- [ ] 逐字渲染经 `after()` 合并（非每 token 一次 `update`）；`-k idea_chat_controller writing_api` 回归全绿。
- [ ] 手动验证：停止后无残留半截 part；继续生成能续上；重新生成重发同消息。

### 轮 3：part 分派渲染器注册表 + 产物卡片 + Thinking/Tool 卡 + 消息工具栏

**改动**
- 新增「kind→渲染器」注册表（对齐 Open WebUI `ContentRenderer` / AI Elements `Message.Part` 分派）：TEXT/REASONING/TOOL_CALL/TOOL_RESULT/ARTIFACT/SOURCE/FILE 各有渲染器。
- **产物卡片**：`Artifact{kind,identifier}` 渲染 + 一键操作（采纳/重新生成/收藏/打开所在目录）；02–13 产物以卡片展示（复用 `desktop_file_card`/`desktop_files_panel`）。
- Thinking/Reasoning 折叠卡 + Tool Call 状态卡（含耗时统计 A8、行号/结果预览）。
- **消息悬浮工具栏**：复制/删除撤回（进 `已删除消息.json`，走 `storage_maintenance` 语义）/编辑重发/引用带入/重新生成。
- 现有气泡折叠/复制/编辑重构为工具栏 + part 渲染，不保留平行旧实现；`design_tokens.md`/`ui_components.md` 新增卡片/HITL 卡 token。

**验收**
- [ ] 新增 `tests/test_part_renderers.py`（真 Tk 隐藏桌面：各 part 渲染/折叠/展开）+ `tests/test_message_toolbar.py`（复制/删除/编辑/引用/重新生成）。
- [ ] 01 气泡区显示 reasoning 折叠卡、tool 卡、artifact 卡；02–13 产物以卡片出现。
- [ ] 删除撤回可恢复；`smoke_test.py` 8/8。

### 轮 4：HITL 协议信封 + 审批门 + 用户选择卡

**改动**
- 新增 L2 契约 `hitl.py`（或扩展 `confirm_gates.py`）：`HITLRequest{kind:CHOICE/APPROVE/DIFF, payload, risk, timeout}` + `Decision{APPROVE/REJECT/REGENERATE/EDIT(updated_payload)}`；审批门/选择卡/红绿 Diff 统一信封；现有 `confirm_gates` 收编进信封，**禁止散落 `messagebox` 审批**。
- **审批门**：确认采用/拒绝/重新生成；**风险分级**（低风险自动放行、高风险才人工）；**超时语义**（`after()` 计时器竞速，超时默认策略可配）。
- **用户选择卡**：模型回复候选（结局/音色/分镜）→ 消息流内嵌选择卡，用户选一个 → 作为 resume 值注入状态机（interrupt 返回值语义）。
- 事件经 `pet_bus.emit_safe` 发送（新增 HITL 事件），播报前缀走 `broadcaster`。

**验收**
- [ ] 新增 `tests/test_hitl.py`（无 Tk：信封序列化、决策枚举、风险分级、超时）+ `tests/test_hitl_ui.py`（真 Tk：选择卡渲染/选择回填、审批门三按钮）。
- [ ] `confirm_gates` 现有调用点全部走信封，无散落弹窗（架构门禁新增「禁止直接 messagebox 审批」检测）。
- [ ] 选择卡选中的值正确注入下游（生成用所选候选）。

### 轮 5：富媒体渲染（图片 Lightbox/多候选对比/收藏 + 代码高亮）+ 红绿 Diff

**改动**
- 图片/分镜缩略图卡 + Lightbox 放大 + 左右滑动多候选对比（A9）+ 一键收藏入库（入库目标走资产库/正典管线，见 §9 待确认 1）。
- JSON/提示词代码高亮块（`Text.tag_config` 高亮 + 折叠/展开 + 一键复制 + 一键应用此提示词）。
- 红绿 Diff：`difflib.SequenceMatcher` + `Text.tag_add("red"/"green")`，接受修改/拒绝（复用轮 4 DIFF 决策信封）。

**验收**
- [ ] 新增 `tests/test_media_render.py`（真 Tk：缩略图/Lightbox/多候选切换/收藏）+ `tests/test_code_highlight.py` + `tests/test_diff_view.py`。
- [ ] 收藏入库走 `asset_batch`/`storage_maintenance` 语义；diff 接受后落盘、拒绝后还原。

### 轮 6：会话分支/节点树 + checkpoint 存储

**改动**
- checkpoint 存储：`json + sqlite3` 实现 `(thread_id, checkpoint_id, parent_id, state, pending_request, artifact_refs)` append-only 树；「存引用不存内容」；定期剪枝。
- 分支/节点树：`parentId` 树 + `ttk.Treeview`/Canvas 侧边节点树；从任意历史消息重新提问（延续模式/独立模式两分支）；分支切换对比（移动 current 指针）。
- 与轮 2「继续生成」打通：中断点 = checkpoint；恢复 = 从 checkpoint 续跑；增量索引 + 懒加载（A6）。

**验收**
- [ ] 新增 `tests/test_checkpoint_tree.py`（无 Tk：append-only、parent 链、fork 不覆盖、剪枝、存引用）+ `tests/test_branch_tree_ui.py`（真 Tk：节点树渲染/切换对比/重新提问）。
- [ ] fork 后原对话不丢、可切回；长会话增量索引（不全量重算）。

### 轮 7：引用溯源 + 资产悬浮卡

**改动**
- 引用溯源：`[n]` 标记（source part），`Text.tag_bind("cite[n]")` 点击侧栏/弹窗定位原剧本/原设定；引用上下文走独立字段，不原地改历史消息（A3）。
- 资产悬浮卡：文本里资产名（角色/场景/道具）特殊下划线/高亮，`Text.tag_bind("<Enter>")` 弹 `Toplevel` 悬浮卡显示正典图 + 属性卡（自建，全行业空白点）。

**验收**
- [ ] 新增 `tests/test_citation.py` + `tests/test_asset_hovercard.py`（真 Tk：tag hover 弹出/关闭、cite 点击定位）。
- [ ] 引用点定位到原文档片段；悬浮卡显示资产正典图/属性。

### 轮 8：视频/音频卡 + 参数滑条 + 多模态上传 + 后台任务 + 通知

**改动**
- 视频/音频卡：封面/缩略图 + 「播放」走外部系统播放器（`contract.platform_tools.open_target`）；音频波形 Canvas 静态近似图；「确认采用/重新生成」「导出 SRT」按钮（复用现有 `subtitle_export`）。
- 参数微调面板：温度/生图步数/画面比例滑条（`ttk.Scale`），写回 `params`（映射各引擎支持参数集，见 §9 待确认 2）。
- 多模态参考上传：拖拽/粘贴图片（垫图）、音频（参考音色）→ 生成 FILE part（复用/扩展 `idea_attachments`）。
- 长任务进度卡 + 转后台运行 + 系统通知：后台任务队列（`threading` + 三虎暂停恢复/`BackgroundTaskLifecycle`），完成经系统通知（复用现有 `notifier`）。

**验收**
- [ ] 新增 `tests/test_video_audio_card.py`（真 Tk：封面/播放按钮/导出 SRT 入口）+ `tests/test_param_panel.py` + `tests/test_multimodal_upload.py`（拖拽/粘贴生成 file part）+ `tests/test_background_task.py`（转后台/通知/断点续跑）。
- [ ] 视频/音频不内嵌播放（零依赖），外部打开正确；参数写回生效；后台任务完成后通知。

---

## 5. 测试方案

- 每轮 `python -B smoke_test.py` 默认冒烟 8/8；改动跨层跑 `python -B smoke_test.py --architecture`；累计 ≥5 个改源码轮次到 master 提交点跑 `run_selftests.py --all --safe`（`AGENTS.md` §5）。
- 含 Tk 的测试由运行器强制经 `scripts/gui_hidden.py` 隐藏桌面执行；新测试一律放 `tests/`。
- 契约变更（对话.json 结构、confirm_gates 收编、气泡渲染重构）时同步改写受影响测试断言，不得弱化/删除/跳过（`AGENTS.md` §2.4）；skip 只引用 `tests/skip_reasons.py` 常量并登记台账。
- 每个「真 Tk」UI 测试用真 Tk 量几何，断言行为而非源码字符串。

---

## 6. 跨轮共享规则（不得破坏）

- **零第三方依赖**：不引任何库；Diff 用 `difflib`，断点存 `json+sqlite3`（stdlib），富媒体走系统播放器/`PhotoImage`/`Canvas`。
- **分层依赖**：只允许 `L5→L4→L3→L2→L1→L0`，反向 import 禁止（`architecture.md` §3）。
- **事件与播报**：新交互事件走 `pet_bus.emit_safe`，播报前缀走 `broadcaster`；不动现有事件契约。
- **正式 JSON 读写**：读 `file_cache.read_json`，写 `agent.core.save`/`save_text` 或 L3 发布器；新产物写 `schema_version`，读侧容忍缺版本。
- **删除与回收**：用户可见删除统一 `storage_maintenance.recycle_paths()`；聊天消息撤回进 `已删除消息.json`。
- **UI token 纪律**：`padx/pady`/颜色/字号/圆角只从 `design_tokens.md` 取，不写内联 hex/魔法数字；新卡片组件写进 `ui_components.md`。
- **右键菜单/快捷键**：经 `ContextMenu`/`ShortcutRegistry`（架构门禁）。
- **阶段依赖规则**：始终由 `stage_parallel`/`confirm_gates`/`stage_completion_service` 强制；UI 只做「发送前提示」，不复制判定逻辑。

---

## 7. 风险与回滚

| 风险 | 缓解 |
| --- | --- |
| 对话.json parts 迁移有损 | 只迁移不删旧文件；迁移失败读旧结构兜底；schema_version 从第一天写死 |
| 停止语义错误（停不掉/扣费） | 取消令牌显式交后台 worker；测试断言「停止后后台真停」 |
| checkpoint 膨胀 | 「存引用不存内容」+ reducer 裁剪 + 定期剪枝；测试覆盖剪枝 |
| 分支树一致性（fork 破坏树） | append-only 树 + parent 链，容忍乱序时间戳/孤儿节点（LibreChat #4778 教训）；增量索引 |
| 审批死锁/橡皮图章 | 超时计时器竞速 + 风险分级（低风险自动放行）；测试覆盖超时 |
| Tk 富媒体能力受限 | 视频/音频走外部播放器（Q2=A）；图片/代码/Diff 原生实现 |
| 长会话性能 | 增量索引 + 懒加载 + 摘要压缩（A6）；不每 token 全量重算 |
| 冲突重构误伤现有功能 | 每轮独立回滚；`confirm_gates`/气泡重构先核验消费者（`AGENTS.md` 规则 28） |

---

## 8. 交付与留痕

- 每轮：按规则 27 领号，`tasks_round/tasks_round_N_result.md` 开头回答三问（轮次类型/测试与三基线/欠账），§7 收尾；提交信息 `R<N>: 文件卡片与HITL·轮X 说明`。
- 每轮更新 `PROJECT_MAP.md` 相关行；轮 1、轮 4 涉及 `AGENTS.md` §2.2 权威源表/`architecture.md` 分层与门禁清单的变更同步。
- 全部轮次收尾后，输出 `程序/tasks_round/任务完成/文件卡片与HITL交互任务书·任务完成.md`（逐条完成证据 + 未完成项处置，`runbook.md` §16）。

---

## 9. 待确认项（实现到对应轮次前需用户拍板；已给推荐默认值）

| # | 待确认 | 推荐默认 |
| --- | --- | --- |
| 1 | 「一键收藏入库」的入库目标 | 项目资产库（走 `asset_batch` 入库管线），非全局正典库；如需全局正典另行确认 |
| 2 | 参数微调面板具体参数集 | 仅暴露各引擎实际支持的参数（温度/最大步数/画面比例 16:9·9:16）；未知参数不硬编码 |
| 3 | HITL 审批超时默认值与风险分级阈值 | 超时 5 分钟；仅「不可逆副作用/对外发布/删除」为高风险需人工，其余自动放行 |
| 4 | 分支树作用域 | 项目级、按「阶段线程」组织（01 对话一线程，其余按阶段产物线程），非全局跨项目 |
| 5 | 系统通知形态 | 复用现有 `notifier`（应用内），Windows 原生 toast 作为可选增强另议 |
| 6 | 多模态参考上传类型范围 | 图片（垫图）+ 音频（参考音色）；PDF/视频参考暂不支持（沿用 `idea_attachments` 文本附档） |

> 执行者不得自行变更 §2 已确认决策；§9 待确认项在对应轮次开工前由用户确认（默认值未被否决即按推荐执行）。
