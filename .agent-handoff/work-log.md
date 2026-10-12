# 近期工作

- 2026-10-12：O26 完成并提交 R1351。白模成果目录与工具安装位置解耦且可配置：`white_model_service` 成果目录默认改为用户数据目录 `%LOCALAPPDATA%/漫剧制作助手/白模项目`（不再取 `blender.parent/'白模项目'`），可用 `MANJU_WHITE_MODEL_WORKSPACE`／`white_model_settings.json` 配置；`blender_candidates()` 保留 PATH／`D:`、`E:/Blender`／Program Files 旧路径只读候选；新增 `write_check`／`blender_version`／`legacy_workspaces`／`diagnose`／`diagnose_text` 首次配置检查，白模页加环境摘要标签＋「白模环境检查」按钮；探针写入下沉 L1 `file_cache.probe_writable`，并同步 `架构统一基数.json` 第四项 `file_cache.py` 行号平移。新增 21 条用例，定向 160/160＋47/47＋360/360＋20/20、架构 312/312、默认冒烟 8/8，0 红（1351−1346=5≥5 命中五轮欠账，收口跑一次全量）。见 [R1351](../程序/tasks_round/tasks_round_1351_result.md)。

- 2026-10-12：O25 完成并提交 R1350。首帧批量任务统一目标集、重试与替换解释：`keyframe_batch` 新增 `batch_plan`（三意图 `missing`／`retry`／`replace`＋六态＋跳过原因＋实际模型与参考图）：`missing` 只取从没提交过的缺帧镜头、已提交跳过不重付费、`deleted` 任何模式不复活、空文件／未配置／越界一律跳过并给原因、单 source 不跨集；`keyframe_comfy` 弹窗新增「批次意图」下拉与目标集预览，Agent／Seedream／本地三条路径与 `auto_batch` 都按统一目标集并记录计划，`pending_shots` 改用 `frame_state`。新增 15 条用例，定向 93/93、关联全绿、架构 312/312、默认冒烟 8/8，0 红（1350−1346=4<5 且未命中 §5，本轮不跑全量）。见 [R1350](../程序/tasks_round/tasks_round_1350_result.md)。

- 2026-10-12：O24 完成并提交 R1348。「尚未开始先不拦」的兼容策略与正式自动生产分开：`stage_parallel` 新增 `BROWSE`（默认，浏览/补录/旧项目）与 `PRODUCTION`（无人值守）两种口径及 `verdict`/`mode`/`exempt`/`missing` 字段，`_apply_mode` 只把「上游未开始」在正式生产下改成前置条件缺失（上游标 `skipped` 即豁免），真问题两口径都拦；`Agent.gate` 默认浏览口径不再随持久档位漂移，`Pet.gate_reason` 按自动链是否在推选口径；`ledger_ready` 加固为「算不出问题行不静默放行」。新增 14 条用例，定向 192/192＋门禁 18/18、快照棘轮 9/9、架构 312/312、默认冒烟 8/8，0 红（1348−1346=2<5 且未命中 §5，本轮不跑全量）。见 [R1348](../程序/tasks_round/tasks_round_1348_result.md)。

- 2026-10-12：O23 完成并提交 R1347。连贯性问题从发现到解除的闭环：`continuity_ledger` 新增结构化 `issues`（稳定编号 `CI-<kind>-<scope>`、涉及镜头/资产、证据、严重度）与 `03_continuity/output/continuity_issues.json` 登记表（`merge_issues`／`sync_issues`／`decide_issue`／`issue_gate`）：同一问题不重复新增、修好解除、解除后再现重开、证据变化重开且清空决定；人工忽略必须写理由并记下作用版本；`stage_parallel.ledger_ready` 改用 `issue_gate`（忽略后不再拦）；`stage_execution_service` 补 L3 门面；桌面连贯性页新增「问题闭环」表与「忽略（写明理由）」按钮。新增 20 条用例，定向 124/124＋160/160、架构 312/312、默认冒烟 8/8，0 红（1347−1346=1<5 且未命中 §5，本轮不跑全量）。见 [R1347](../程序/tasks_round/tasks_round_1347_result.md)。

- 2026-10-12：O22 收口安全全量。干净 master 工作树 `run_selftests.py --all --safe` 第 1 次即绿：4610 条用例／410.3 秒／0 文件红（`test_desktop_startup_perf` 13.5 秒、`test_perf_baseline` 20.0 秒均过）；凭据 round=1346、tree=3488e392，`last_full_safe_all_round` 刷到 1346。见 [R1346](../程序/tasks_round/tasks_round_1346_result.md)。

- 2026-10-12：O22 完成并提交 R1346。资产正典、变体与镜头引用的变更影响视图：`asset_plan` 新增只读 `asset_impact`（正典 `canonical_board`／`character_anchor`、`state_variants`、被哪些采用镜头哪些字段引用、需复核首帧、受影响已生成视频、`orphan`/`protected`）与 `deletion_references`（删前引用清单＋警示），`asset_context.referencing_shots` 与 `references` 同口径，`stage_execution_service` 补 L3 门面，资产详情页顶部提示被引用/可回收；改变体不覆盖正典、删除受引用资产先给引用列表、孤立资产可回收（依赖 O18；O39 回收侧未完成）。新增 10 条用例，定向 64/64、注释快照＋统一棘轮 5/5、架构 312/312、默认冒烟 8/8，0 红（1346−1341=5≥5；收口安全全量 4610/4610、410.3 秒、0 红，凭据 round=1346、tree=3488e392）。见 [R1346](../程序/tasks_round/tasks_round_1346_result.md)。

- 2026-10-12：O21 完成并提交 R1345。资产检索与候选墙完善可追溯性和批量决策：`asset_reference_search` 新增 `score_parts`（五项分项，`score` 由分项派生）、`explain`/`_state`/`STATE_NOTES`（八态＋说明）、`suppressed`（低分/同图重复逐条解释）；`rank` 记同图来源 `alts` 与 `conflict`；`normalize`/`_credit` 增 `collected_at`（来源失效仍可查当时记录）；`reference_wall` 新增许可依据/采集日期/状态/同图来源四列并在状态栏说明挡下候选，剔除候选不影响已入库资产。新增 search 16 条＋wall 3 条用例，定向 118/118、锚定全绿、架构 312/312、默认冒烟 8/8，0 红（1345−1341<5 且未命中 §5 不跑全量）。见 [R1345](../程序/tasks_round/tasks_round_1345_result.md)。

- 2026-10-12：O20 完成并提交 R1344。保留 Animatic 强校验并降低大媒体重复读取成本：`file_cache.file_digest` 按 1 MiB 分块流式 sha256 并按 `(mtime_ns,size)` 缓存（`clear`/`invalidate` 同步清理），`animatic_service.evidence` 源分镜与全体成果改用流式摘要、不再整份读媒体；三项人工确认与「发布前不得代签」不变。实测 64 MiB 文件峰值内存 64.1→2.1 MiB、重复校验 114ms→0.21ms。台账第四项 `file_cache.py` 两处 json.loads 行号平移（53→54、112→140）已同步。新增 3 条用例，定向 41/41、锚定 117/117、架构 312/312、默认冒烟 8/8，0 红（1344−1341<5 且未命中 §5 不跑全量）。见 [R1344](../程序/tasks_round/tasks_round_1344_result.md)。

- 2026-10-12：O19 完成并提交 R1343。初稿/定稿采用差异与影响预览：新增只读 `storyboard_catalog_service.adoption_impact`（同集已采用分镜为基线，逐镜稳定 ID 对比 added/removed/changed/reordered，列出将失效首帧与已生成视频镜头），经 L3/L4 门面在 `check_adoptable` 之后、采用之前把 summary 追加到状态栏（不弹窗、不改状态、不换号）；取消采用不改正式清单。新增 7 条预览用例，定向 78/78、Tk 采用用例 1/1、架构 312/312、默认冒烟 8/8，0 红（1343−1341<5 不跑全量）。见 [R1343](../程序/tasks_round/tasks_round_1343_result.md)。

- 2026-10-12：O18 完成并提交 R1342。来源账本从「仍在」升级为「仍是这个版本」：`artifact_lineage` 新增 `check`/`source_status`（current/stale/missing/unknown）与多来源 `record(sources=…)`、只读 `affected`、显式 `adopt`；`source_available` 语义保留但改为派生（内容变只标过期、不隐藏、不改写成品，仅 missing 隐藏）；剧本/分镜目录对过期项显示「原稿已变更／来源已变更」。新增账本 10 条＋目录回归 1 条，覆盖结构/分镜/首帧/白模/音频/剪辑；定向 136/136、架构 312/312、默认冒烟 8/8，0 红（1342−1341<5 不跑全量）。见 [R1342](../程序/tasks_round/tasks_round_1342_result.md)。

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
