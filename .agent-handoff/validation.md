# 验证证据

## 2026-10-12 O26 完成

- 2026-10-12 O26：新增 `tests/test_white_model_workspace.py` 21 条（默认成果目录在用户数据目录且不等于 Blender 安装目录旁／环境变量与设置文件都能改成果目录与 blender 路径／`workspace()` 随目标变更失效／中文＋空格目录可写且探针不留痕／权限不足与缺盘符给可执行提示／轻量检查不建目录／版本读取与缓存、失败返回空串、无 exe 不执行／配置路径优先、旧盘符仍在候选表、PATH 只扫一次／旧成果目录只读发现且不误报当前目录／诊断给出缺 Blender、不可写、旧目录提示与版本，`diagnose_text` 成文）。`file_cache.py` 两处 `json.loads` 行号平移（54→55、140→141）同步 `维护记录/架构统一基数.json` 第四项。定向 `-k white_model previs native_apps` 160/160、`-k white_model_workspace file_cache` 47/47、`-k ui_edges core paths stage_flow stage_parallel notification` 360/360、`-k stage_execution stdlib_closure import_error` 20/20、注释快照／统一棘轮／覆盖率棘轮／跳过卫生全绿、架构 312/312、默认冒烟 8/8，全 0 红。1351 − 1346 = 5 ≥ 5，收口在干净 master 工作树跑全量：第 1 次 4680/4680 中 1 红（`continuity_ledger.py:596` 文案规则，R1347 遗留，定向用例当时未覆盖），把该短语改为 `人工关闭` 后第 2 次全量 4680/4680、416.2 秒、0 红（`test_desktop_startup_perf` 13.8 秒、`test_perf_baseline` 20.5 秒均过）；凭据刷新 round=1351、tree=c97c1336，`last_full_safe_all_round`=1351。

## 2026-10-12 O25 完成

- 2026-10-12 O25：新增 `tests/test_keyframe_batch_plan.py` 15 条（`missing` 只取从没提交过的缺帧镜头／提交过的跳过不重付费／`deleted`·`empty`·`unset`·`outside` 跳过并给原因；`retry` 只取有记录仍缺帧；`replace` 只对点名且已有可用首帧；切集换 source 不跨集；`plan_summary` 文案；`pending_shots` 口径；Tk `DialogPlanTests` 显示「批次意图」下拉与目标集预览）。新增一条 Tk 平台限制，同步 `维护记录/skip台账.json`（+1，手写插入不整份重写）。定向 `-k batch_plan keyframe` 93/93、`-k keyframe previs stage_execution` 全绿、`-k batch_frames todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 27/27、`tests.architecture.test_skip_hygiene` 3/3、架构 312/312、默认冒烟 8/8，全 0 红。1350 − 1346 = 4 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O24 完成

- 2026-10-12 O24：新增 `tests/test_stage_gate_modes.py` 14 条（默认浏览放行且各 `*_ready` 口径不变；正式生产把「上游未开始」当作缺前置并点明缺哪一步、怎么豁免；上游标 `skipped`＝主动豁免；两种口径只差「上游未开始」这一种；真问题两口径都拦；台账格式异常不静默放行；结论标签；页面/审计文案；`Agent` 默认浏览口径与档位无关＋显式 `PRODUCTION` 拦截＋`skipped` 豁免；`Pet.gate_reason` 链在推要 `PRODUCTION`、浏览要 `BROWSE`、分镜历史豁免仍优先）。`tests/test_stage_parallel.py` 两处桩函数放宽为接受可选 `mode` 关键字（断言不变）。定向 `-k stage_parallel stage_flow pet_agent stage_completion` 192/192、`-k stage_gate` 18/18、`-k todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 9/9（pet_ui 快照行号 2792→2801）、架构 312/312、默认冒烟 8/8，全 0 红。1348 − 1346 = 2 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O23 完成

- 2026-10-12 O23：新增 `tests/test_continuity_issues.py` 20 条（稳定编号＋证据＋严重度／同一台账编号稳定／不同批次不串号／干净台账无问题；不重复新增／修好解除／解除后再现重开／忽略后证据变了重开且清空决定；忽略必须理由／决定记理由与作用版本／未知编号与非法决定拒收／重新打开清忽略；只读预览不写盘／注入发布器才落盘／无登记表读成空／门禁只拦待处理／修好清空／`stage_parallel.ledger_ready` 忽略后放行）。定向 `-k continuity stage_parallel confirm_gates` 124/124、`-k ui_edges todo_comment unification_ratchet desktop` 160/160、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1347 − 1346 = 1 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O22 完成

- 2026-10-12 O22：新增 `tests/test_asset_impact.py` 10 条（`referencing_shots` 命中字段命名/`location`+`props` 可命中/未知资产不命中；受引用资产带镜头与首帧文件且 `protected`、孤立资产 `orphan` 可回收、`canon`/`variants` 只读回显、非法编号 `ValueError`、删除引用清单列出镜头并警示、孤立资产删除清单为空；写状态变体不覆盖正典键）。定向 `-k asset_impact asset_context asset_plan asset_detail asset_reference` 64/64、`test_todo_comment_snapshot`＋`test_unification_ratchet` 5/5、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1346 − 1341 = 5 ≥ 5；收口安全全量第 1 次 4610/4610、410.3 秒、0 红（凭据 round=1346、tree=3488e392，last_full_safe_all_round=1346）。

## 2026-10-12 O21 完成

- 2026-10-12 O21：`tests/test_reference_search.py` 新增 5 组（分项结构/总分=分项和/`score` 与分项一致；缺地址/缺来源/缺许可/低分/不可商用/可入库六态＋note；许可依据与采集日期随条目、同图不同源记进 `alts`、许可冲突标 `source_conflict`、同许可不算冲突；低分与同图落后分逐条解释、已上墙不重复列；credit 记 license_url/collected_at 且 `rank`/`suppressed` 对已入库资产只读）。`tests/test_reference_wall.py` 新增 3 条（图墙显示许可依据与采集日期列；同图冲突只展示一条且状态提示「不一致」、同图来源为 1；右键剔除候选后 assets.json 字节不变）。定向 `-k reference` 118/118、锚定 `-k asset_detail asset_plan asset_reference workflow_context skill_tools` 全绿、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1345 − 1341 = 4 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O20 完成

- 2026-10-12 O20：新增 `tests/test_file_cache.py::FileDigestTests` 2 条（`file_digest` 与 `hashlib.sha256` 整份结果一致且第二次命中不再打开文件；内容变化后刷新、`invalidate()` 后重算）＋ `tests/test_animatic_service.py` 1 条（确认后对 `.mp4/.wav/.png` 的 `Path.read_bytes` 打补丁抛错、清缓存后 `evidence` 仍 True，证明成果校验不再整份读媒体）。定向 `-k animatic file_cache` 41/41、锚定 `-k animatic_timeline stage_completion previs` 117/117、架构 312/312、默认冒烟 8/8，全 0 红。台账第四项 `file_cache.py` 两处 json.loads 行号平移（53→54、112→140）已同步，`-k unification_ratchet` 3/3。实测 64 MiB 文件：旧法峰值 64.1 MiB／114ms，新法冷算 2.1 MiB／118.7ms、命中 0.002 MiB／0.211ms。1344 − 1341 = 3 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O19 完成

- 2026-10-12 O19：新增 `tests/test_adoption_impact.py` 7 条（同文件重排只报 reordered 且文件字节不变；删镜 → 首帧+已生成视频入失效清单；仅改对白 → fields=[dialogue] 且无媒体失效；换资产/改时长 → 首帧失效；无基线 → 全部 added + `+2 镜`；预览对 ui_settings.json 与候选文件只读）。`-k adoption_impact storyboard file_cache row_targets workflow_context` 78/78、`test_ui_edges.BatchContinuationTests.test_adopt_skips_adopted_without_confirm` 1/1（Tk）、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1343 − 1341 = 2 < 5，本轮不跑全量。

## 2026-10-12 O18 完成

- 2026-10-12 O18：新增 `tests/test_artifact_lineage.py` 10 条（同路径内容变更标 stale 但仍 available、恢复回 current；改无关文件不失效；删源标 missing 且 unavailable；无账本 UNKNOWN 且 available None；旧单来源账本可读；多来源逐角色状态；重记覆盖旧来源；`affected` 只列非 current 且按 source 过滤；`adopt` 后 current；结构/分镜/首帧/白模/音频/剪辑六类都能登记并检出过期）；`tests/test_file_cache.py` 增 1 条（定稿来源变更后仍在目录且标题含「来源已变更」）。定向 `-k artifact_lineage file_cache storyboard script_structure script_contract` 136/136、架构门禁 312/312、默认冒烟 8/8，全 0 红。未动 `script_contract.py`／`storyboard_final.py` 登记调用点，未增删 `json.loads`（台账未平移）。1342 − 1341 = 1 < 5，本轮不跑全量。

## 2026-10-12 O17 收口全量

- 2026-10-12 O17 收口：干净 master 工作树（`o07-fullsafe-master`，HEAD=00d3a80）`run_selftests.py --all --safe` 第 1 次即绿：4561 条用例／420.2 秒／0 文件红；`test_desktop_startup_perf` 13.6 秒、`test_perf_baseline` 22.4 秒均通过，未出现已知阈值抖动。内容树全量凭据刷新 round=1341、tree=06c23252d59254ca25619e76b7de8c650cd23749。收口文档提交在绿凭据之后，文档树与凭据树不同树。

## 2026-10-12 O17 完成

- 2026-10-12 O17：新增 `tests/test_script_structure.py::ExtractionProvenanceTests` 6 条（结构稿标本地规则提取且阶段 detail 不再写 Writer 已提取；无对白标签与未知道具尺寸保留待确认/出处；别名与跨集 ID 保留出处且跨集稳定；回忆场景标时间线待确认；同名特征矛盾给同名提醒；规则校验要求出处但仍接受待确认字段）。`test_ui_edges` 结构页说明断言同步为「本地规则提取」。定向 `-k script_structure script_contract stage_templates` 71/71、`-k ui_edges` 全绿、`-k skills` 全绿、`-k agents_md todo_comment line_endings structured_script_write_boundary json_io_boundary unification_ratchet` 35/35、`-k copy_rules` 14/14、默认冒烟 8/8，全 0 红。`desktop.py` 只改 1 行文案，行数不变（TODO 注释快照 2753 未平移）。本轮 1341 − 1336 = 5 ≥ 5，收口须补一次干净 master 全量。

## 2026-10-12 O16 完成

- 2026-10-12 O16：新增 `tests/test_hollmwood_roles.py::ReviewTraceabilityTests` 5 条（同一冻结输入 `review_basis` 四键一致且为 64 位摘要；记录区分规则合格/创意满意并保留退回原文与通过条件；返工 prompt 只含明确问题、节奏正文只在 system 出现一次、prompt 不含节奏；最终判退异常带 basis 与 records；断点恢复前缀记为「上一轮已审核通过」）；`tests/test_hollmwood_performance.py` 2 条（成功结果透出 `hollmwood_review_audit`；失败结果带 basis/scope/records）；`tests/test_hollmwood_ui_queue.py` 1 条（完成文案区分规则合格与创意满意、仍用「您」）。定向 `-k hollmwood` 51/51、关联 `-k writing` 139/139、`-k idea_chat` 全绿、`-k stage_prompt_governance` 15/15、`-k copy_rules` 14/14、`-k todo_comment` 2/2、默认冒烟 8/8，全 0 红。`writing_api.py` 加行后第 4 项 `json.loads` 台账 486→490（已同步），`-k unification_ratchet` 3/3 复验通过；`desktop.py` 只改 1 行文案，行数不变（TODO 注释快照 2753 未平移）。本轮 1340 − 1336 = 4 < 5，且未命中 §5 升级条件，不跑全量。

## 2026-10-12 O15 完成

- 2026-10-12 O15：新增 `tests/test_request_freeze_entries.py` 3 条（`capture_request` 冻结后改技能文件与阶段配置只影响新任务、同一次捕获的 `frozen_skill_prompt` 与 sha256 摘要不变；直连 API 与桌面 Agent 两入口对同一技能 `selected`／`loaded.sha256` 一致；静态核对 desktop 直连走 `capture_request`、writing 投递走 `validate_selected_skills`＋`freeze_skills`、`open_flow_agent` 的 `current(...)` 先于 `def build()`、桌面 `launch_interactive(` 仅一处）。定向 `-k request_freeze_entries` 3/3、关联 `-k workflow_settings request_freeze_entries writing` 全绿、默认冒烟 8/8，全 0 红。未改生产代码，台账不变。本轮 1339 − 1336 = 3 < 5，不跑全量。

## 2026-10-12 O14 完成

- 2026-10-12 O14：新增 `tests/test_idea_chat.py::SessionOverviewTests` 1 条（`gpt-4o`＝API 直连、`claude-code`＝桌面 Agent（claude），已确认阶段文件 1 份，摘要含模型名与「不隐藏也不复制项目成果」）；新增 Tk 用例 `ComposerLayoutTests::test_session_label_explains_dimensions_and_follows_model_switch`（首帧含「当前会话：」「按模型隔离」，切「另一模型」后标签更新）。定向 `-k idea_chat` 131/131、关联 `-k ui_edges idea_inline_brief writing` 全绿、架构相关全绿、`-k desktop_startup_perf` 14/14（13.3 秒）、默认冒烟 8/8，全 0 红。`desktop.py` 增 Tk 标签 → TODO 注释快照行号 2749→2753。本轮 1338 − 1336 = 2 < 5，不跑全量。

## 2026-10-12 O13 收口全量

- 2026-10-12 O13 收口：干净 master 工作树（`o07-fullsafe-master`，HEAD=baf816c）`run_selftests.py --all --safe` 第 1 次 4542 条用例／385.8 秒／0 文件红；`test_desktop_startup_perf` 13.0 秒、`test_perf_baseline` 20.4 秒均通过，未出现已知阈值抖动。内容树全量凭据刷新 round=1336、tree=d934dd219a8ff155f7330220e12081af3f4efabc。收口文档提交在绿凭据之后，文档树与凭据树不同树。

## 2026-10-12 O13 完成

- 2026-10-12 O13：新增 `tests/test_writing_response_preservation.py::PreparationReplyStateTests` 3 条（状态判据区分四态／无状态消息为空串；确认成功后为「阶段稿待确认」且消息含路径与确认；取消后迟到错误含「原始响应已保存」「不等于正式采用」与归档路径且台账未变）；扩展既有 2 条（格式不合格与截断带 `原始响应已保存`＋原因标签且消息点明归档不等于正式采用；版本变化经 `reply_to_writing` 带 `因版本变化未采用`）。定向 `-k writing` 139/139、关联 `-k idea_inline_brief writing_response_preservation` 46/46、桌面 `-k ui_edges` 115/115、架构相关 22/22、默认冒烟 8/8，全 0 红。`desktop.py` 增 1 行 → TODO 注释快照 desktop.py 行号 2748→2749。本轮 1336 − 1330 = 6 ≥ 5，收口补一次干净 master 全量。

## 2026-10-12 O12 完成

- 2026-10-12 O12：新增 `tests/test_tts.py::TtsBatchIdentityTests` 6 条（清单记身份／中途改设置不混用／换模型与换端点失效旧缓存／截断与空文件不续用／旧清单无摘要时文件非空即沿用／密钥不入指纹清单批次记录）；定向 `-k tts` 49/49、`-k tts audio animatic subtitle` 全绿、关联 `-k ui_edges` 115/115、架构相关 `-k unification_ratchet json_io_boundary layers tts_publication_boundary todo_comment_snapshot` 12/12、默认冒烟 8/8，全 0 红。夹具 `fake_synthesize` 跟随新签名补 `**_kwargs`（`tests/test_ui_edges.py` 两处，只改夹具）。本轮 1334−1330=4<5，不跑全量。

## 2026-10-12 O11 完成

- 2026-10-12 O11：新增 `tests/test_confirm_gates.py::ConfirmationBindingTests` 5 条（换候选只失效那一个角色且门禁重问／改冲突优先级重问／跨集同批次 ID 内容不同即复核／无关字段不扰动／旧记录无摘要仍算已确认）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 101/101、接缝 `-k ui_edges stage_execution stage_parallel` 172/172、架构相关 `-k unification_ratchet confirm_gates_json_boundary todo_comment_snapshot layers no_circular_import stage_paths` 15/15、默认冒烟 8/8，全 0 红。台账无变化（`stage_execution_service.py` json.loads 仍 108/1039/1070/1086）。本轮 1333−1330=3<5，不跑全量。

## 2026-10-12 O10 完成

- 2026-10-12 O10：新增 `tests/test_confirm_gates.py::AdoptTransactionTests` 6 条（落盘失败留 failed 且门禁不通过／应用前中断留 pending／成功记 applied 不再问／重复点击幂等／旧记录无 state 按 applied／未知 key 空相位），改 `tests/test_asset_detail.py` 两条（第二步失败事件 `['record','apply','record']` 且不刷新不报成功；第一步失败不落盘）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 96/96、架构棘轮 `-k unification_ratchet confirm_gates_json_boundary` 5/5、默认冒烟 8/8，全 0 红。台账 `架构统一基数.json` 第四项三处行号随 adopt 加长平移（1025/1056/1072→1039/1070/1086，exempt 不变），`TODO注释快照_20261003.json` 的 asset_detail.py 注释行号 346→350。
- 2026-10-12 O10 收口全量（干净 master 工作树 `--all --safe`）：第 1 次 4528 条／445.5 秒／1 文件红（`architecture.test_todo_comment_snapshot` 行号平移，定向 2/2 修绿）→ 第 2 次 4528 条／449.2 秒／0 红，绿凭据 round=1330、tree=3281c7c7，`last_full_safe_all_round`=1330。文档收尾在绿凭据之后，非同树全量。

## 2026-10-12 O09 完成

- 2026-10-12 O09：新增 `tests/test_previs.py::PrevisEvidenceTests` 2 条（改调度失效／改回复用／换文件失效且不删成果／旧记录无来源时退回旧口径）；定向 `-k previs white_model` 138/138、关联 `-k stage_execution_service stage_parallel` 57/57 与 `-k ui_edges` 115/115、默认冒烟 8/8，全 0 红。架构（干净 master 工作树 `--layer architecture --all`）312/312、0 红。台账 `架构统一基数.json` 第四项三处行号随插入平移（exempt 不变）。

## 2026-10-12 O08 完成

- 2026-10-12 O08：新增 `tests/test_previs.py::RoutingGateConsistencyTests` 4 条（自动→复杂、复杂→简单、跨集同镜头 ID、删除覆盖）；定向 `previs stage_parallel` 143/143、0 红；接缝 `previs stage_parallel stage_execution local_previs stage_completion white_model stage_models manual_gate row_targets ui_edges desktop` 398/398、119.2 秒、0 红；架构 `smoke_test.py --architecture` 312/312 OK；默认冒烟 8/8。回归修复仅颜色：`test_previs_monitor.py`、`test_ui_edges.py` 的 `ready` 打桩补 `source=None`。本轮号 1316 − 上次绿全量 1312 = 4 < 5，未跑全量。

## 2026-10-12 O07 完成

- 收口全量：干净 master 工作树（`HEAD=b0c6716`、`HEAD:程序`=12ad4759）`run_selftests.py --all --safe`——第 1 次 4500 条／528.7 秒／21 文件红（缺嵌套子模块致写作与技能组假红；补子模块后同树定向 489/489、0 红），第 2 次 4516 条／388.1 秒／0 红，凭据 round=1312、tree=12ad4759。

- 定向：新增 `tests/test_white_model_identity.py` 12 条＋ `white_model_identity previs` 相关 136/136、5.0 秒、0 红。
- 接缝：`white_model previs project stage_execution local_previs desktop stage_parallel stage_completion storyboard keyframe asset` 669/669、48.9 秒、0 红（`test_desktop_startup_perf` 本轮通过）。
- 门禁：默认冒烟 8/8；`smoke_test.py --architecture` 312/312（首次 311/312，因本轮在 `stage_execution_service.py` 插入 7 行使 `架构统一基数.json` 第四项三处豁免行号漂移，同步行号后全绿）。
- 全量：见 [R1312](../程序/tasks_round/tasks_round_1312_result.md) 文末；按用户 2026-10-12 指令只在收口跑一次，先查 7 天内同内容树绿凭据（无），本轮未命中 AGENTS §5 升级条件。

## 2026-10-12 O06 完成

定向 591/591（含接缝）、修复后相关 128/128、默认冒烟 8/8。第 1 次全量（树 e0df829a）4 文件红，均为夹具/环境；第 2 次全量（树 0e2a2f06）4504/4504、536.7 秒通过，但检出为 detached 工作树，执行器未写绿凭据；第 3 次全量为取凭据在 master 临时工作树重跑，行至性能用例被并发活动中断退出 1，未取得凭据，不再重跑。O05 历史全量不覆盖本轮树。详见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。

## R1265

- 最终受影响 14 文件 458/458、156.7 秒；冒烟 9/9，日志 程序/outputs/r1265-affected-final.log。
- 本轮架构 307/311；四处失败修复后相关 3 文件 10/10，日志 程序/outputs/r1265-architecture-fix.log。未改门禁断言。
- R1264 历史真实全量 tree=9ea232b7027c6e77b4ef9516c146a8e9c5ae2b95、413.396 秒；不覆盖本次树。中央 validate 0 errors/0 warnings，未实发 API 或重启。见 [报告](../程序/tasks_round/tasks_round_1265_result.md)。

## R1208

- 正式 master fe4a923 安全全量 4291/4291、397.379 秒、含架构 311/311，执行器凭据 round=1208、tree=3831b1e0fe2e20cf1ea6c7b0b8afb9c881c3bff9；日志 TEMP/r1208-full-final.log。
- 首次全量 2 条旧取消 fixture 失败，补齐前置后定向 73/73，再完整复验通过。默认冒烟 8/8、受影响冒烟 9/9。全量后的缓存隔离补丁先红后绿、定向 68/68，日志 TEMP/r1208-cache-green.log；最终树未同树全量。见 [R1208](../程序/tasks_round/tasks_round_1208_result.md)。

## R1200

- 定向 129/129、默认冒烟 8/8、受影响冒烟 9/9。首次全量仅架构登记行号漂移，修正后定向 71/71。
- 干净 e1f2d26 安全全量 4283/4283、539.0 秒、exit=0（含架构 311/311）。后续仅文档收尾；不声称最终文档树或用户主目录同树全量。
- 后续干净 master 808a972 正式全量 4283/4283、511.725 秒，R1202 凭据已写入；未实发 API、未重启。原始日志 TEMP/R1200-full-recheck.log、TEMP/R1202-master-full.log；见 [报告](../程序/tasks_round/tasks_round_1200_result.md)。

## R1162

- 定向 137/137、受影响冒烟 9/9（含默认 8/8）、相关边界 5/5；主目录两项回归 2/2。先红后绿与命令目录错误记录见 [报告](../程序/tasks_round/tasks_round_1162_result.md)。
- 实现 db0e878，主目录同步回执 6523465；既有 6 项已跟踪改动保持原样。未重启应用、未真实桌面粘贴或模型发送。本次交接补记仅文档与只读代码核验，不重复运行测试，以上均为 R1162 已有凭据。

## R1139

- 技能/Codex 定向 197 条通过，默认冒烟 8/8；补充定向 27 条和 ratchet/coverage 7 条通过。
- 干净 master 191ef05 全量安全回归 exit=1，旧 UI 按钮样式及剧本输出契约断言失败；没有本轮绿色全量凭据。详情与未运行项见 [报告](../程序/tasks_round/tasks_round_1139_result.md)。
- 实际 67 技能安装，重复 67 unchanged；只读 Codex skills/list 确认 pipeline-script-preparation enabled，不冒称已验证模型加载执行。

## R1074

- 旧实现内存对照 17/17，迁移后定向 58/58，默认冒烟 8/8，受影响 9/9；原断言未改，新增 11 条。
- 干净 master 813b662 正式安全全量 4026/4026，含架构 309/309，exit=0。tree=c924740a7a042954a6e4e086736a15fe5c31437c、round=1074、seconds=295.657、at=2026-10-06T00:23:14；执行器真实凭据，不手改。
- 初次 runner 无写锁权限中止；获授权后通过。旧实现对照首次 cwd 导入错误，修正绝对导入路径后通过；详见本轮报告。全量后仅文档回填，不冒称最终文档树受测。
- 收尾文档／轮次门禁 15/15、0.8 秒；中央任务 completed，validate 0 errors、1 条既有租约警告。

## R1073

- 迁移前 test_pet_ui 574/574（含新增 G3 7 条）；迁移后定向 588/588，默认 smoke 8/8。冻结 100 个 ID 的摘要与 R1059 一致，前后方法 AST 不变。
- 干净 master d6bfe1e 正式全量 4015/4015，含架构 309/309，exit=0。新增 G3 7 条及内存协调 10 条，未删原测试。
- 执行器凭据：tree=68211bcc962eff5e40fe0722c0735a920044e7ec，round=1073，seconds=359.982，at=2026-10-05T17:51:24。临时日志 R1073-full.log。
- 后续仅文档回填，最终文档树未重跑全量；不声称实机视觉体验已验收。
- a517dd1 后文档／轮次 15/15；中央 R1073-CHAT-COORDINATION completed，validate 0 errors、1 条既有租约警告。

## R1072

- 定向 70/70；默认 smoke 8/8；失败集合修复后 200/200。首轮 5 文件／6 失败均已关闭，位置快照仅同步行号，不增加豁免。
- 正式安全全量：干净 master 6cf0911e6f7b9f86e27433f72031201a734fe6e5，3998/3998，含架构 309/309，exit=0。
- 执行器真实凭据：tree=ba1498584b9be6c5e89736ebc21fef649ae8a594，round=1072，seconds=357.954，at=2026-10-05T17:35:42。后续仅文档收尾，不冒称最终文档树已全量。
- 日志：系统临时目录 R1072-master-full.log；长期事实摘要见 R1072 结果文件。

## R1070

- 周期安全全量：干净 master bc6358e719fea403a0e74a09f06786a0a7ab7bf7 执行 run_selftests.py --all --safe，exit=0，ALL TESTS PASSED，313.560 秒。
- 执行器真实凭据：tree=69a5dd97bc85aebed4f89780683ae3ecce1ee34c，round=1069，at=2026-10-05T08:44:11。round 取执行时最新报告，不手工改为 1070。
- 输出仅保留尾部，未保留本次总用例计数，不沿用历史 3994 冒充本次计数。全量后仅文档收尾，不声称最终文档树同树全量通过。
- 中央 validate：0 errors、1 既有租约 warning，详见 risks。文档链接与 diff --check 通过，凭据形态扫描 0 命中；默认 smoke_test.py：8/8、0 失败。未独立重跑架构门禁。

## R1069

静态检查：11 份入口/接力文档链接有效、标记唯一、无模板占位符；diff --check 通过。
在 程序/ 执行 ../运行环境/Python/python.exe -B -m unittest tests.architecture.test_agents_md tests.test_round_claim：23/23，10.982 秒。
同一解释器执行 -B smoke_test.py：8/8，0 失败；默认模式未启动独立架构门禁。
仅文档改动；全量凭据轮次 1067 至本轮 1069 差 2，按既有周期不重复全量。
最终结果见 [R1069](../程序/tasks_round/tasks_round_1069_result.md)。

## 历史基线（不是当前树验收）

- R1068 主树全量：干净提交 1b36059d5e7c8036b50cbf8118d41b3d0aa2ed84，3994 条通过。
- 凭据 tree=8466f0109fe30c54a31d1ea8890e5b05843553d6，round=1067，at=2026-10-05T08:20:53。
- R1068 收尾：冒烟 8/8，test_agents_md + test_round_claim 23/23。
- R1068 隔离副本：批量删除定向 90/90、冒烟 8/8、架构 309/309；不是生产删除或逐候选独立证明。
