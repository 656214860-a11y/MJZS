# R1441 结果：HOLLMWOOD 框架并入「全流程AIGC·剧本」SKILL 并移除

三个收尾问题：
- 本轮类型：功能轮（用户要求移除 HOLLMWOOD 框架、由 SKILL 吸收其角色；含删除 `hollmwood_roles`／`hollmwood_rules` 两个模块，涉及 L0 白名单与架构台账的有意变更）。
- 测试与基线：定向 `test_writing_api`／`test_idea_chat`／`test_skills`／`test_stage_prompt_governance`／`test_writing_quality`／`test_writer_style_agent_delivery`／`test_script_agent_delivery_assembly`／`test_claude_writing_roles` 等 319 项通过；默认冒烟 8/8；`smoke_test.py --architecture` 340 项中仅 `test_full_safe_all_is_required_after_eight_source_rounds`（R1440 欠一次完整安全全量，本轮之前就存在）一条红。**完整安全全量未跑**。
- 欠账：未减少；本轮新增一个改过源码的轮次，全量欠账 +1。

## 改动

1. **角色并入 SKILL**：`skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 的「定向注入（00 包）」改为三角色同一次回复内自检并直接修订：编剧角色审核五阶门控、编辑角色审核 12 节拍、演员角色做台词七维诊断与语速自检；`writing_quality.prompt()` 同步。
2. **编剧风格**：`stage_config` 以项目级 `script.writer_style` 取代 `hollmwood_*` 字段（旧 `hollmwood_writer_rules` 读取时迁入，其余旧键忽略，下次保存不再写出）；`workflow_settings.writer_style_prompt()`／`writer_style_summary()` 取代 `hollmwood_prompt()`／`hollmwood_summary()`，桌面任务书与直连 API 的 system 各注入一次，空风格不占请求；阶段配置面板「四角色协作」勾选与五个规则弹窗换成「编辑编剧风格」。
3. **移除框架**：删除 `hollmwood_roles.py`、`hollmwood_rules.py`；`writing_api` 去掉 `_hollmwood_reply`／`hollmwood_gateway`，直连 API 一律一次请求＋自动保存；`selected_model()` 不再把 Claude 桌面程序当受控 CLI 对话模型；`RoleCancelledError` 由 `writing_api.WritingCancelledError` 取代；`desktop.py` 去掉角色进度条、进度队列与轮询；`reply`／`reply_to_writing` 去掉 `progress`／`stream` 参数。
4. **文档与台账**：`AGENTS.md` 契约轮白名单与架构门禁清单、`architecture.md`、`_layers.py`、`架构统一基数.json`（采用方、`writing_roles` 逻辑名、豁免计数 42→41、`writing_api` json.loads 行号 548→474）、TODO 注释快照行号 2846→2786。

## 测试契约变化（断言未动处另列）

- 删除：`test_hollmwood_roles`／`test_hollmwood_performance`／`test_hollmwood_ui_queue`／`test_stage_config_hollmwood`／`test_hollmwood_log_publication_boundary`，以及各文件里只验证四角色执行器的用例（逐步审核、返工、角色进度、四角色预算）。
- 改写：`test_hollmwood_agent_delivery` → `test_writer_style_agent_delivery`（风格到达首发／续发、空风格不注入、旧字段迁移）；`test_writing_api` 中「进入阶段④」的哨兵由 `_hollmwood_reply` 改为 `workflow_tasks.script_prompt`，已确认阶段文件改从请求里的 `<brief_complete>` 取；`test_project_context_boundary` 台账总数 37→36。
- 其余断言（取消、归档、发布边界、预备阶段确认）保持原样，仅同步类名与导入。

## 未验证

- 未重启应用、未真实点击阶段配置面板与编剧风格弹窗；Tk 面板只有单元用例覆盖。
- 未用真实模型跑一次完整自然剧本，质检附块在新角色分工下的实际表现待下一次生成后观察。
- 疑似遗留：`workflow_engines.ClaudeWritingAdapter`（现已无生产调用方）、`desktop._stream_text`、`短剧工业化流水线` SKILL 里关于 HOLLMWOOD 的描述、`维护记录/自检增量.json` 中的旧条目；均在范围外，仅记录。

## 提交

分支 `codex/wip-R1441`，未 push；commit hash 见 `git log`。
