# R2253 结果：视频提示词渲染选 API 模型时直连调用，不经 Qwen（功能轮）

对应：REQ-S10-50、DES-S10-50。第三步（第一步初步分镜 R2205、第二步音频脚本 R2244）；其他阶段与 Qwen 代码不动，MCP 优化子进程与分镜定稿原生路径不动。

## 做了什么
- 文档先行：`docs/stages/S10_视频生成.md` 新增 REQ-S10-50、DES-S10-50，模块表与测试锚定表补行。
- **入口键缺陷**：`desktop_media_pages.py` 原传 `open_flow_agent('final', …)`，`workflow_settings.FLOWS` 无此键，`defaults('final')` 抛「未知的工作流入口」。以 `FLOWS` 实际键为准改为 `video_prompt`（常量 `VIDEO_PROMPT_FLOW`；对应阶段配置 `STAGE_CONFIG_STAGES['video_prompt']=='video'`、锁定阶段 `lock_stage('video_prompt')=='video'`，均已核对）。`skill_panel.show(self,'final')` 是面板阶段名，另一回事，未动。
- 新增 `video_prompt_direct_api.py`（L3）：复用 R2205／R2244 骨架（`direct_model`、`_Batch`、`_ask`、`Job`／`launch`、取消登记），未另立第二套。一次请求让模型只回 `{shot_id, source_signature, video_prompt}`；`validate_reply` 校验 JSON 可解析、镜头号一致、校验值与输入一致、提示词非空且 ≤1500 字。不合格带问题清单重试一次，仍不合格不落盘并报原因。合格由 `agent.core.save`（JSON 序列化器）写 `video_prompts/<镜头>.json`，旧结果先备份到 `历史版本/`。
- 导入与保存沿用既有链路：`video_prompt_results.PromptResults.poll` → `import_result` → `publish_video_prompt`（含分镜校验值比对、生成期间变更保护），**不另立发布器**；完成仍以 REQ-S10-22 视频核验为准，提示词文字不算证据。
- `agent/shot_assets.py`：抽出 `prompt_context()`（镜头上下文与输出路径唯一构造）与 `prompt_direct()`，`prompt_task` 文本不变。
- 新增 `desktop_video_prompt_direct.py`（L4 胶水）；`desktop_idea_chat` 新增 `open_direct_flow_agent`，分流点唯一在 `_FlowAgentLaunch.build()`（stage==`video_prompt`、带载荷、`direct_model` 命中）。`open_flow_agent` 签名不变。
- 门禁登记：`_layers.py`、`architecture.md`、覆盖率基线重测（338 模块 / 52 覆盖，8 组目标全绿）、runbook 数字同步。

## §7.3 三问
- 类型：功能轮（§3.1）。
- 唯一入口：分流只在 `build()`；落盘走 JSON 序列化器，导入走既有 `publish_video_prompt`；停止走 `workflow_engines.terminate`→`cancel_project_requests`。无新增第二入口，Qwen 路径未删。
- 不碰数据边界、不改模型池配置；未调用真实 API（测试全用假适配器；真实联调需用户指定模型）。

## 红灯输出（实现前）
```
AttributeError: module 'desktop_media_pages' has no attribute 'VIDEO_PROMPT_FLOW'
AttributeError: module 'desktop_idea_chat' does not have the attribute '_run_video_prompt_direct'
ModuleNotFoundError: No module named 'video_prompt_direct_api'（其余用例同因）
```
入口键缺陷复现：`workflow_settings.defaults('final')` → `ValueError: 未知的工作流入口`（测试 `test_req_s10_50_flow_key_used_by_media_page_is_known` 锁住）。

## 测试
- `run_selftests.py -k video_prompt_direct`：8 条全绿（先红后绿）。
- `-k video_prompt_direct storyboard_direct audio_direct complexity_ratchet`：绿。
- `-k media_pages video_prompt shot_assets flow_agent requirement_trace desktop_idea_chat`：40 条，0 红。
- `smoke_test.py`：8/8 通过。
- `smoke_test.py --architecture`：411 条，仅 2 项红，均为工作树缺未入库文件、与本轮无关：`test_agents_md`（缺 `维护记录/基准历史.json`）、`test_skill_reference_injection`（缺 `skills/00全流程SKILL/.../screenplay-gate-engine.md`）。本轮引入的 4 类红（类体量、参数个数、覆盖率基线两条）已修。
- `-k idea_chat`（早先一次）：`test_idea_chat` 另有若干红，根因均为工作树缺总控包 `sd-decision-engine/SKILL.md`（剧本流程冻结 SKILL 报「引用缺失」），与本轮无关；本轮另有的 `test_storyboard_direct_api` 一条红是我给 `_FlowAgentRequest` 加槽位导致，已在实现里给 `direct` 设默认值修复（该测试断言未动，复跑全绿）。
- 断言未动：现有测试均未修改；没有测试断言「提示词渲染走 Agent／qwen」。
- 未做：真实 API 联调；全量 `--all --safe`（分支不累计欠账）；非 chat 线路无法在请求中途中断（停止后丢弃结果不落盘）；三虎自动化未接入；程序不核验提示词中的对白是否逐字出自分镜（沿用任务书约束，由模型遵守）。

## 提交
分支 `codex/wip-R2253`（领号时由工具自动切出）；commit 见提交信息。`project_status.md` 留给合并轮在 master 上改。
