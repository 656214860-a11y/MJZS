# 近期工作

- 2026-10-12：O17 收口安全全量。干净 master 工作树 `run_selftests.py --all --safe` 第 1 次即绿：4561 条用例／420.2 秒／0 文件红（`test_desktop_startup_perf` 13.6 秒、`test_perf_baseline` 22.4 秒均过）；凭据 round=1341、tree=06c23252，`last_full_safe_all_round` 刷到 1341。见 [R1341](../程序/tasks_round/tasks_round_1341_result.md)。

- 2026-10-12：O17 完成并提交 R1341。剧本结构「形式合格」与「内容完备」分开：`script_contract.structure_script` 标「本地规则提取（未调用模型）」＋「结构合法≠信息齐全」，角色卡加别名与跨集 ID（同名跨集稳定），无对白标签／未知道具尺寸／回忆场景／同名矛盾保留出处或待确认；`review_structured_script` 只要求出处字段、不要求待确认填满；模板步骤／`stage_exec` detail／桌面说明／`skill_tools` 描述统一为「规则提取／规则校验（未调用模型）」。定向 71/71、ui_edges 与 skills 全绿、架构相关 35/35、copy_rules 14/14、默认冒烟 8/8、0 红。见 [R1341](../程序/tasks_round/tasks_round_1341_result.md)。

- 2026-10-12：O16 完成并提交 R1340。四角色审核依据与修订范围：`hollmwood_roles._run` 每次算 `review_basis`（brief／SKILL／节奏／审核 system 四组 sha256）与逐条 `review_records`（位置／违反规则／修订建议／通过条件都保留在审核原文），`review_audit.scope`＋`creative_signoff` 区分「规则合格」与「创意满意」；返工 prompt 只针对退回意见里的明确问题且不重复注入节奏；失败异常与 API 成功/失败结果带 `hollmwood_review_audit`；桌面完成文案点明「规则合格；创意满意由您确认」。定向 51/51、关联 139/139、idea_chat 全绿、stage_prompt_governance 15/15、copy_rules 14/14、todo_comment 2/2、默认冒烟 8/8、0 红。见 [R1340](../程序/tasks_round/tasks_round_1340_result.md)。

- 2026-10-12：O15 完成并提交 R1339（验证项）。核对各生成入口都消费发送边界一次捕获的请求快照：直连 API `capture_request`→`freeze_skills`；桌面 Agent 投递唯一入口 `open_flow_agent` 在 `build()` 前捕获 `config`，writing 分支 `validate_selected_skills`＋`freeze_skills`；手动任务书不发模型请求；媒体生成冻结由 O12 关闭。新增 `tests/test_request_freeze_entries.py` 3 条（冻结后改配置只影响新任务／两入口摘要一致／静态入口与捕获顺序），未改生产逻辑。定向 3/3、关联全绿、默认冒烟 8/8、0 红。见 [R1339](../程序/tasks_round/tasks_round_1339_result.md)。

- 2026-10-12：O14 完成并提交 R1338。会话维度说明：`writing_api.chat_session_overview`／`chat_session_summary`（只读）给出会话模型与调用方式（API 直连／桌面 Agent）、请求身份（Provider／模型）、上下文来源（按模型隔离的对话记录）、已确认阶段文件数与自然剧本采用状态；桌面剧本页新增只读标签 `idea_session_label` 并随模型切换刷新。定向 131/131、关联全绿、架构全绿、`desktop_startup_perf` 14/14、默认冒烟 8/8、0 红。见 [R1338](../程序/tasks_round/tasks_round_1338_result.md)。

- 2026-10-12：O13 收口安全全量。干净 master 工作树 `run_selftests.py --all --safe` 第 1 次即绿：4542 条用例／385.8 秒／0 文件红（`test_desktop_startup_perf` 13.0 秒、`test_perf_baseline` 20.4 秒 均过）；凭据 round=1336、tree=d934dd21，`last_full_safe_all_round` 刷到 1336。见 [R1336](../程序/tasks_round/tasks_round_1336_result.md)。

- 2026-10-12：O13 完成并提交 R1336。剧本准备回复状态：`writing_api.preparation_reply_state`／`preparation_reply_message` 给出四态（已采用／阶段稿待确认／原始响应已保存／因版本变化未采用）＋落点＋下一步；`_preparation_step` 在格式不合格／截断／正文为空／模型失败／版本变化各分支打状态与原因标签，`saved` 与取消后迟到的错误都点明 responses/ 归档不等于正式采用；桌面 `received` 三处状态栏改用同一判据。定向 139/139、关联 46/46、桌面 115/115、架构 22/22、默认冒烟 8/8、0 红。见 [R1336](../程序/tasks_round/tasks_round_1336_result.md)。

- 2026-10-12：O12 完成并提交 R1334。TTS 批次冻结配置与缓存身份：`request_identity`／`freeze_settings`／`batch_identity`，逐句清单带端点／模型／音色／语速，开批冻结、沿用前 `sha256` 复核成品、整段指纹加 endpoint、批次记录带 identity（不含密钥）。定向 49/49、关联 115/115、架构 12/12、默认冒烟 8/8、0 红。见 [R1334](../程序/tasks_round/tasks_round_1334_result.md)。

- 2026-10-12：O11 完成并提交 R1333。确认绑内容：`confirm_gates.content_digest` 给 G-05／G-06／G-08 候选各带摘要，`record(..., digest=)` 落摘要，`pending()` = 已确认且摘要对得上；`adopt_asset_plan_choice`／`pick_gate`／`auto_decide_gates` 三处写入路径都带摘要，旧记录无摘要按旧口径放行。定向 101/101、接缝 172/172、架构 15/15、默认冒烟 8/8、0 红。见 [R1333](../程序/tasks_round/tasks_round_1333_result.md)。

- 2026-10-12：O10 完成并提交 R1330。采用事务化：`confirm_gates` 相位 pending／applied／failed、`pending()` 只认 applied（旧记录无 state 按已确认），`stage_execution_service.adopt_asset_plan_choice` 先记 pending → 落盘 → 成功记 applied，失败记 failed、中断留 pending，`asset_detail._pick` 失败给恢复提示。定向 96/96、架构棘轮 5/5、默认冒烟 8/8、0 红。

- 2026-10-12：O10 收口安全全量。干净 master 工作树第 1 次 4528/445.5 秒／1 文件红（TODO 注释快照行号随 `_pick` 加长平移 346→350），定向修绿后第 2 次 4528/449.2 秒／0 红，凭据 round=1330、tree=3281c7c7，`last_full_safe_all_round` 刷到 1330。见 [R1330](../程序/tasks_round/tasks_round_1330_result.md)。

- 2026-10-12：O10 提交 dcf3719（实现＋测试＋台账）／ef1488e（快照行号修复）。

- 2026-10-12：O09 完成并提交 R1322。就绪绑定来源分镜摘要与预演文件：`white_model_service` 新增 `shot_digest`／`source_digest`／`evidence_state`／`record_evidence`，`previs_routing.ready` 按证据失效，`previs_automation.verify` 校验通过即登记，`local_previs` 状态列与导入共用。定向 138/138、关联 172/172、默认冒烟 8/8、架构 312/312。

- 2026-10-12：O09 收口安全全量。干净 master 工作树第 1 次 4522/475.5 秒／1 文件红（SG-05 探针夹具只写 preview，同符新语义），定向补 `record_evidence`（R1328）后第 2 次 4522 条〈437.4 秒、0 红，凭据 round=1322、tree=42e782ea，`last_full_safe_all_round` 刷到 1322。见 [R1322](../程序/tasks_round/tasks_round_1322_result.md)。

- 2026-10-12：O07 完成并收口。白模镜头目录加项目身份与集维度（`white_model_service`）、新建项目即写 `project_id`、旧目录迁移（可重复／不覆盖／失败回滚＋来源版本清单）、白模页打开时调用一次；同步 `架构统一基数.json` 第四项三处行号。定向与接缝 805 条、默认冒烟 8/8、架构 312/312。见 [R1312](../程序/tasks_round/tasks_round_1312_result.md)。

- 2026-10-12：O07 收口全量。干净 master 工作树第 2 次 `--all --safe` 4516/4516、388.1 秒、0 红，绿凭据写入 `.git/full-safe-receipts.json`（round=1312、tree=12ad4759）；第 1 次的 21 文件红全部来自新建工作树缺嵌套子模块。

- 2026-10-12：O08 完成并提交 R1316。`previs_routing.decisions_for` 成为唯一有效决策（覆盖优先），门禁 `stage_parallel.previs_ready` 改用它；`ready` 增开 `source` 按集解析并连接到 dispatch、automatic_candidates、previs_automation.start 与 L3。新增 4 条四场景一致性用例；定向 143/143、接缝 398/398、架构 312/312、默认冒烟 8/8。见 [R1316](../程序/tasks_round/tasks_round_1316_result.md)。

- 2026-10-12：O06 完成并收口。修复新门禁暴露的三处测试/探针回归与 `platform_tools.tool_path` 缓存遮蔽缺陷，台账轮次 1307→1308。提交 a167b7c / 8760e41 / fbdd23d；干净内容树 0e2a2f06 全量 4504/4504 通过（无执行器绿凭据）。见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。

- R1162 收尾：Claude Desktop 改为与 Codex 共用全文任务书投递；提交 db0e878、同步回执 6523465。后续问答只读确认 CLI 仍传任务文件路径，并澄清任务书与素材正文的区别；真实窗口是否完成全文粘贴仍未知。仅补交接记录，不扩展生产改动。

- R1070：按用户要求核验并更新交接；确认 R1069 提交 bc6358e、中央状态 completed，开始时工作树干净。仅接力/状态/报告文档，未继续优化。

- R1069：接力入口、分类记忆及会话提示完成；定向 23/23、冒烟 8/8；master 提交 bc6358e，中央任务 completed。见 [报告](../程序/tasks_round/tasks_round_1069_result.md)。
- R1068：隔离批量删除证明定向 90/90、冒烟 8/8、架构 309/309；真实源码未删除。提交 c80b965，见 [报告](../程序/tasks_round/tasks_round_1068_result.md)。
