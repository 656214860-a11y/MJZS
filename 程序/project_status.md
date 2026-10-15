# 项目状态（可独立接续）

R1464：功能轮+文档（优化清单第 13、6 项）。新增只读「运行状况」面板（汇总任务状态、耗时、模型调用结果、被忽略异常）；状态页当前能力 R1000 以前 494 条迁出归档（340KB→约 100KB）。详见 [R1464](tasks_round/tasks_round_1464_result.md)。
R1463：结构治理轮（优化清单第 12、14 项可安全部分）。新增 scripts/dev.py 开发者统一入口（九个子命令只转调既有脚本）并写入 CLAUDE.md；根目录整理核查后不动。详见 [R1463](tasks_round/tasks_round_1463_result.md)。
R1462：可靠性轮（优化清单第 10、11 项）。分发清单补全 41 个未登记文件（此前 --build 直接拒绝）；新增分发自检（副本解释器导入主入口）；模型 HTTP 结果计数落盘。详见 [R1462](tasks_round/tasks_round_1462_result.md)。
R1461：结构治理轮（优化清单第 5、8、9 项）。新增模块行数棘轮（6 个超限老模块登记上限只降不升）；清理 85 个已并入分支（114→30）；app_logging.timed 计时埋点接入切页与模型 HTTP。详见 [R1461](tasks_round/tasks_round_1461_result.md)。
R1460：文档与版本轮（优化清单第 6、7 项）。最近完成一节迁至 维护记录/状态历史归档.md（425KB→339KB）；新增 说明/更新记录.md 与版本小节测试；启动日志带版本与提交号。「当前能力」242KB 未动（协议级决策）。详见 [R1460](tasks_round/tasks_round_1460_result.md)。
R1459：可靠性轮（优化清单第 1 项）。110 处 except Exception: pass 改为 app_logging.swallowed() 留痕（带位置、同点限频）；新增静默吞异常棘轮；行号基线平移。详见 [R1459](tasks_round/tasks_round_1459_result.md)。
R1458：可靠性轮（优化清单第 4 项）。新增标准库可用性门禁（随附裁剪版 Python 缺库在开发机即红）；启动失败日志改追加并带时间/版本头。详见 [R1458](tasks_round/tasks_round_1458_result.md)。
R1457：可靠性轮（优化清单第 2、3 项）。新增 app_logging：根日志落盘脱敏、线程/主线程/Tk 回调/faulthandler 崩溃钩子，真实启动入口接线（此前 .pyw 未接 Tk 回调钩子）；新增 5 项测试，冒烟 8/8，架构 340 项全绿。详见 [R1457](tasks_round/tasks_round_1457_result.md)。
R1455：契约轮（文档收口，Codex 执行、Claude 验收）。精简 AGENTS.md 422→328 行（语义不变），清理 architecture.md 中已删除模块的现行引用；文档相关 19/19 通过。本轮未跑全量；R1441–R1451 的轮次索引缺口未补写，缺账区间只声明不补造。详见 [R1455](tasks_round/tasks_round_1455_result.md)。
R1453：功能轮（界面，车道 R1449）。三虎弹窗：10 秒自动关闭（`ui_tokens.PET_CLOUD_AUTO_CLOSE_MS` 单一配置；悬停／输入框聚焦暂停，只收起不丢待决询问，并入既有 WATCH_RECHECK_MS 机制）、字号缩一档（`pet_body`／`pet_hint` token）、气泡顶对齐头像顶、相邻完全相同消息合并显示。验收发现并修掉 7 条红（4 条合同数值同步，3 条恢复既有悬停复检）；未做肉眼视觉验收。详见 [R1453](tasks_round/tasks_round_1453_result.md)。
R1451：修复轮（性能＋界面，车道 R1448）。页面切换：快速连点合并只建最后一页、缓存页切回复用、02 页内容签名判断是否重建、构建期间减少重排；侧栏项目列表高度随内容自适应、阶段导航上移；齿轮与标题垂直居中。真实项目「摄影侠」副本上 02→03 来回的绘制耗时约降 45%、点击同步返回 60–190 ms→1–13 ms，首次进入 03 约 510→420 ms；Codex 自报未达 40% 门槛，04–13 页完整对比未做。缓存陈旧风险靠签名测试覆盖，未做真实操作回归。详见 [R1451](tasks_round/tasks_round_1451_result.md)。
R1450：功能轮（界面，单点）。剧本页「删除剧本」改名「删除」并移到「刷新」右侧。详见 [R1450](tasks_round/tasks_round_1450_result.md)。
R1447：修复轮（性能，车道 R1445 合并）。03 初步分镜／07 成片切页时的目录扫描移出 UI 线程、目录快照复用（含 120 份剧本压力样例：同步切入 690→142 ms、完整显示 1230→736 ms；小项目几乎无变化），验收复测发现并修掉 07 页坏 JSON 重复提示回归；05／06 同类扫描未修，留作后续。另修 R1440 脚本 `auto_full_safe.py` 的裸 JSON 读取棘轮红。详见 [R1447](tasks_round/tasks_round_1447_result.md)。
R1446：功能轮（界面）。应用改名「漫剧助手」（`app_metadata.APP_NAME` 单一来源，启动文件名／目录名／持久化键不变）；侧栏按钮减半、项目列表伸展、齿轮对齐标题、页头标题上移、聊天区顶对齐列表、三虎缩小并收紧；显示层可读性优化与审计见 [R1446](tasks_round/tasks_round_1446_result.md)。验收复测修掉 800×600 文件区溢出；全量未跑。
R1443：可靠性轮（R1440 后续）。全量风险触发改为代码强制（启动入口／`storage_maintenance.py`／`_layers.py` 改动立即欠全量；Tk 生命周期仍人工），`round_claim.py next` 自检并自动安装 git 钩子，后台全量结果写 `auto-full-safe-result.json` 并在每次提交的 post-commit 输出里提示上次是否未通过。新增相关用例，62 条通过；未跑全量；并行 R1441 改了 `_layers.py`，按新规则欠一次全量待后台补跑。在独立工作树分支 `codex/wip-R1443` 领号提交。见 [R1443](tasks_round/tasks_round_1443_result.md)
R1442：功能轮。清理 R1441 遗留：删除 `短剧工业化流水线` 的 HOLLMWOOD 描述与 `集成HOLLMWOOD框架.txt`，删除无生产调用方的 `ClaudeWritingAdapter` 与桌面流式气泡；定向与默认冒烟通过，全量待干净树。见 [R1442](tasks_round/tasks_round_1442_result.md)
R1441：功能轮。HOLLMWOOD 四角色框架并入「全流程AIGC·剧本」SKILL 并移除：编剧角色审核五阶门控、编辑角色审核 12 节拍、演员角色做台词七维诊断与语速自检；阶段配置「四角色协作」勾选改为项目级「编剧风格」（`script.writer_style`）；删除 `hollmwood_roles`／`hollmwood_rules`，直连 API 一次请求。定向 319 项、默认冒烟 8/8、架构门禁仅剩 R1440 全量欠账一条红；完整安全全量未跑。见 [R1441](tasks_round/tasks_round_1441_result.md)
R1440：可靠性轮（治理变更，用户批准）。全量欠账阈值 5 → 8，只数改过源码的轮次（文档／测试／记录轮不计），欠账到门禁线前 2 个源码轮次由 git post-commit 钩子调 `scripts/auto_full_safe.py` 在 `.wt/ci` 干净检出上后台补跑，凭据写 common-dir。新增 3 项用例，默认冒烟通过；架构层仅余一条真实欠账红（本机最后凭据 R1420，其后 16 个源码轮次），待后台全量补清；后台端到端首次实测见 `程序/logs/auto_full_safe.log`。详见 [R1440](tasks_round/tasks_round_1440_result.md)。
R1439：修复轮。侧栏单击项目不再直接切换：先弹确认（写明目标与当前项目），后台任务／创意对话请求／剧本 Agent 运行中直接拒绝，取消后高亮回到当前项目；当前项目行加「●」，窗口标题显示当前项目名。新增 4 项用例，定向与默认冒烟通过；未跑全量、未实机点选。「创意文件丢失防护」WIP 因根因是误切项目而弃用，存于 git stash。详见 [R1439](tasks_round/tasks_round_1439_result.md)。
R1437：修复轮。清掉 R1436 之后 Windows 全量里其余 8 条红：`gate_level` 替身 ×2、白模弹窗 67 字缩到 39 字、TODO 快照行号 2811→2846、R1434 交付提示词新措辞断言（含反向断言）、`test_idea_chat` ×4 改引用 `ui_tokens.COLORS`（更正 R1436：其中 3 条是 R1431 调色板变更的陈旧断言，不是大小写）。断言未弱化；另补 `test_workflow` 对 R1431「交付方式」说明的断言。**Windows 随附解释器干净树 `--all --safe` 全量：5102 条、0 红（master 9a59a47）**，详见 [R1437](tasks_round/tasks_round_1437_result.md)。
R1436：修复轮（仅测试夹具）。R1435 后 Windows 随附解释器全量（581 路）9 条红／7 个文件，逐条归因：仅 `test_idea_inline_brief` 一条是 R1433 引入（面板替身缺 `sync_master_skill`），已修；其余属另一任务 R1431／R1434（`gate_level` 2 项、弹窗过长、TODO 快照行号、交付提示词措辞）或 Windows 环境差异（`test_idea_chat` 4 条），未处理。全量回归仍有红，未产生绿凭据。详见 [R1436](tasks_round/tasks_round_1436_result.md)。
R1435：性能/资源轮（用户要求提高上限）。请求与 SKILL 内联字符硬上限 96,000 → 300,000，`workflow_context_budget.REQUEST_CONTEXT_MAX_CHARS` 为唯一常量（`workflow_settings` 内联默认值、`hollmwood_roles` 改为引用，消除三处写死的 96000）；按模型上下文窗口的 token 判断不变。连贯性／分镜定稿／视频生成／质检交付 4 个总控 SKILL（9.7 万—13.5 万字）恢复可发送，总控体检 4 → 0。详见 [R1435](tasks_round/tasks_round_1435_result.md)。

R1433：功能轮（含治理变更，用户授权）。阶段配置「统筹 SKILL」改为「总控」：对应表从代码搬到 `skills/00全流程SKILL/总控.json`；`master_skill` 按指纹（清单＋全流程包入口＋各阶段总控 SKILL 及其直接引用）自动同步各阶段，只替换上次总控给的项，用户自加与取消勾选保留，首检只记基线；体检报告断链与超内联上限；门禁 `workflow_settings.master_gate` 在总控模式下对手动与自动一律阻断（必填制作锁缺失、已勾选 SKILL 引用不可加载；剧本准备简报采集除外）。AGENTS.md 统筹宪法改写为总控宪法。实机体检发现连贯性、分镜定稿、视频生成、质检交付 4 个总控 SKILL 连同引用超过 96000 字内联上限（既有问题，API／Claude Desktop 发送被阻断，命令行 Agent 不受影响），待用户决定拆分。新增 18 项用例；Linux 副本定向与架构目录通过（既有失败项与未改动副本一致）；未跑随附解释器冒烟、全量与实机。详见 [R1433](tasks_round/tasks_round_1433_result.md)。

R1432：修复轮。阶段配置「新增 SKILL」原先只复制选中的单个文件（外部包丢 references／assets／scripts）、同名静默丢弃、覆盖不留旧版、断链要到发送才报。新增 `skill_import_service`：整包导入、暂存＋原子换入、重名硬拦、换入后按真实发送流程试冻结（失败撤回并恢复旧版）、旧版进程序回收站、导入台账 `skills/导入台账.json`。新增 6 项用例。R1432—R1433 在分支 `codex/r1432-skill-master` 完成后快进合入 master。详见 [R1432](tasks_round/tasks_round_1432_result.md)。

R1430：功能轮（路线图 C 收尾）。视频下载成功后记次数与镜头标称秒数（estimated）、逐句配音成功后记一次请求，写入请求台账（幂等、失败不影响主流程），「用量总览」随之有内容；生图逐笔未做（调用点无项目句柄）。相关模块对比未改动副本，无新增失败，Linux 专有的既有失败（msvcrt／LOCALAPPDATA）不变；架构目录 341 项通过；未跑随附解释器冒烟与全量（欠账 10 轮），未在真实任务上实机记账。详见 [R1430](tasks_round/tasks_round_1430_result.md)。

R1429：功能轮（路线图 C）。设置 → 预算新增「用量总览」：只读汇总当前项目已落盘的模型调用事件（按模型／阶段／天，token 分列，未上报用量不当 0）与请求台账。核查发现调用事件本就逐条落盘，故未新增写入路径；视频秒数、生图、配音的逐笔用量仍只有预算计数器，需另轮补写 `RequestLedger`。新增 3 项用例，Linux 副本与架构目录 341 项通过；安全全量欠账待 Windows 补跑。详见 [R1429](tasks_round/tasks_round_1429_result.md)。

R1428：功能轮（路线图 E）。交付页新增「选择采用版本…」：可锁定某个已验收旧版进成片，或恢复为最新已验收版；锁定只落在已验收版本，不删文件、不改验收记录，文件缺失／被替换仍按原因报告不回落。新增 3 项用例，Linux 副本与架构目录 341 项通过；安全全量欠账待 Windows 补跑。详见 [R1428](tasks_round/tasks_round_1428_result.md)。

R1427：功能轮（路线图 D）。成片合成后在同一目录写出 `剪辑清单.edl`（CMX3600）、`剪辑清单.fcpxml`、`分轨素材清单.json`；写出失败只记日志不影响成片；剪映草稿无稳定格式未实现。新增 5 项用例；EDL／FCPXML 尚未在剪辑软件实机导入确认。详见 [R1427](tasks_round/tasks_round_1427_result.md)。

R1426：功能轮（路线图 B）。设置 → 开发信息新增「环境自检」，只读核对 FFmpeg／FFprobe、ComfyUI、Blender、桌面 Claude／Codex、API 密钥并给下一步。新增 6 项用例。详见 [R1426](tasks_round/tasks_round_1426_result.md)。R1426—R1428 在分支 `codex/r1426-env-check` 完成后快进并入 master（主目录另一任务有未提交改动，合入时保留）。路线图见 [路线图_20261014](维护记录/路线图_20261014.md)。

R1425：修复轮（路线图 A）。命令行 Claude 条目误指向 Claude Desktop 图形程序时，保存被拒并说明改法，调用前直接给出明确错误而非「未返回有效 JSON」；剧本页模型调用失败统一弹窗。新增 3 项用例，Linux 副本定向通过（已知失败与未改代码一致）；命中五轮欠账，需在 Windows 补跑安全全量。新增[路线图](维护记录/路线图_20261014.md)。详见 [R1425](tasks_round/tasks_round_1425_result.md)。

R1424：修复轮。模型管理「自动搜寻」识别商店版 Claude Desktop（WindowsApps，经注册表包清单，新版本优先），旧安装器路径优先不变；新增 3 项用例，Linux 副本定向通过（唯一失败依赖 Windows，未改代码同样失败）。需重启加载。详见 [R1424](tasks_round/tasks_round_1424_result.md)。

R1423：修复轮。模型管理中本机 Claude／ChatGPT 条目的 Provider 显示厂商名（anthropic／GPT），改选 anthropic 仍保持「应用安装路径」表单，存储仍为 desktop；普通 Anthropic API 不变。仅改 `pet_models_ui.py` 与 `tests/test_pet_ui.py`（Provider 期望值按用户要求改为 anthropic，新增 1 项）。Linux 副本定向 20/21（唯一失败在未改代码上同样失败）、架构抽样 56/56；随附解释器冒烟未实测。需重启助手加载。详见 [R1423](tasks_round/tasks_round_1423_result.md)。

R1422：状态接续轮，完成 R1418/R1420 缓存修复的交接记录，核准 R1421 已合入事实；原始证据与双方记录保留，仅清理本任务临时验证检出，不改程序或用户数据。详见 [R1422 交接报告](tasks_round/tasks_round_1422_result.md)。

R1421：用户授权将 R1419 修复合入主目录；合并提交 `643c39a`，默认冒烟 8/8、受影响 93/93（16.6 秒）、受影响冒烟 9/9。原启动器重启即可加载；未自动关闭软件、未调用真实模型。合入时保留了另一任务未提交的 R1420 报告及用户 `projects.json`；交接现由 R1422 收尾。详见 [R1421 合入报告](tasks_round/tasks_round_1421_result.md)。

R1419：手动修改项目设定／大纲／角色卡后，显式重写采用当前前置与目标正文，不再因旧确认摘要失配而拒绝；保留原稿，普通确认及生成过程版本保护不变。实现 `4cd7581`，分支验证 93/93、默认冒烟 8/8，已由 R1421 合入 master。详见 [R1419](tasks_round/tasks_round_1419_result.md)。

R1357：O32 剪辑输出规格不能固定替代项目规格。`script_contract.py`（L0）新增 `resolve_output_spec`／`preview_spec`／`output_filter`／`loudness_filter`／`overlay_metrics`／`describe_output_spec`（画幅→分辨率按 1080 短边推算、宽高取偶，等比缩小＋居中留边不裁切），`PRODUCTION_LOCK_DEFINITIONS` 增加 `resolution`／`fps`；`engine.py`（L3）`_encode` 改用项目制作锁规格（内嵌字幕字号/边距与音量随规格，`qc.json` 记 `output_spec`），新增 `output_spec`／`output_spec_text`；`edit_service.assemble_image_timeline(..., spec=)`＋`animatic_service.build_bundle(..., spec=)`＋`stage_execution_service.animatic_preview_spec` 让预演低清但画幅跟项目；后期页导出前显示实际规格。新增 15 条用例，定向 15/15＋关联 136/136、架构与端到端 66/66＋153/153＋120/120、默认冒烟全绿，0 红；1357 − 1356 = 1 < 5 且未命中 §5，本轮不跑全量。见 tasks_round/tasks_round_1357_result.md。

R1356：O31 声音角色映射与音轨用途绑定到具体集/用途。`tts_api.py`（L1）新增 `AUDIO_KINDS`／`AUDIO_KIND_LABELS`（对白/旁白/BGM/音效/整轨）、`audio_kind`／`marked_audio_name`、`voice_for`（稳定角色 ID 优先、显示名兜底）、`missing_voices`／`silent_lines`／`voice_snapshot`，`save_key` 在音色变化时自增 `voice_version`；`batch_signature`／`resume_folder`／`run_lines` 增至集标识，两集同名台词不再共用缓存；`audio_import_service`（L2）`import_audio(kind=)` 给非对白加前缀；`stage_completion_service` 对白音轨要求（导入 BGM 不算对白完成）；`desktop.generate_tts_per_line` 带上当前集 token；新增 18 条用例，定向 18/18＋关联 427/427、架构 312/312、默认冒烟 8/8，0 红；1356 − 1351 = 5 ≥ 5 命中五轮欠账，收口在干净 master 跑 `--all --safe`：第 1 次 4749/4749 中 1 红（`video_progress.py:94` 文案规则，R1353 遗留，定向当时未覆盖），改第二人称后第 2 次 4749/4749、425.3 秒、0 红。见 tasks_round/tasks_round_1356_result.md。

R1355：O30 字幕估算轴与实际音频轴建立校准流程。`subtitle_timing.py`（L1）保留等分低成本估算（`timed_entries` 行为不变），新增 `calibrate_entries(episode, audio=None)`：在镜内按权重重排字幕轴（有真实音频秒数／对齐区间就按真实值并计 `audio`，否则按 `line_weight` 句长分摊并记为「未校准」），超镜头整镜压缩并记 `overflow`；新增 `validate_entries`（非有限／负数／反向／重叠／越界明确报错）、`rows_from_entries`，`srt_rows` 改用校准轴；`subtitle_export_service.py`（L2）`export_srt`／`export_dialogue_script` 改用校准轴并返回 `(target, report)`，另写 `字幕校准.json`（来源音频摘要＋校准状态），新增 `pending_calibration`／`export_calibration`；`desktop.py` 导出后按状态提示已校准句数或未校准句数；新增 23 条用例，定向 690/690、架构 312/312、默认冒烟 8/8，0 红；1355 − 1351 = 4 < 5 且未命中 §5，本轮不跑全量（上次绿全量 1351、tree c97c1336，下一欠账点 1356）。见 tasks_round/tasks_round_1355_result.md。

R1354：O29 预算由多个计数器汇总为请求级可对账记录。`pet_llm.py` 新增 `RequestLedger`（幂等预留 `reserve`、同一远端任务唯一账单 `link`、`settle` 缺量转未知、`cancel` 只改本机不伪造远端退款、`report` 按 token／秒／次数分列不跨量纲相加、价格表可选并标时间）；`model_pool.probe` 增 `ledger` 与 `PROBE_USAGE_NOTE`（探测标「可能产生用量」并记未知），`pet_models_ui` 探测文案同步标注；新增 11 条用例，定向 73/73、架构 312/312、默认冒烟 8/8，0 红；1354 − 1351 = 3 < 5 且未命中 §5，本轮不跑全量（上次绿全量 1351、tree c97c1336，下一欠账点 1356）。见 tasks_round/tasks_round_1354_result.md。

R1353：O28 本地/云端任务统一可恢复状态与错误分类。`video_progress` 新增只读 `task_status`／`status_label`／`status_next`／`status_detail`／`error_kind`：把提交中／结果不确定／排队／生成中／下载中／下载失败／技术不合格／待审核／已采用统一成一套名并各给「下一步」（查询／补配置／显式重做），错误只归鉴权／限额／模型协议／内容拒绝／网络／本机磁盘／未分类（复用 `pet_agent.classify` ＋磁盘标记，本机磁盘先判）；`engine.poll` 记 `download_error`（取回失败保留 `succeeded`，再查询续取、不重生成、不重投）；视频页状态行与交付页逐镜行（「下一步」只在未采用时显示）改用统一状态；新增 13 条用例＋1 条下载续取集成用例，定向 332/332、架构 312/312、默认冒烟 8/8，0 红；1353 − 1351 = 2 < 5 且未命中 §5，本轮不跑全量（上次绿全量 1351、tree c97c1336，下一欠账点 1356）。见 tasks_round/tasks_round_1353_result.md。

R1352：O27 视频技术合格与创意验收分开。`engine.py` 新增 `review_source`／`content_reviewed`／`review_label` 与 `review_by` 标记：无人值守自动技术放行写 `review_by='auto'`＋`AUTO_REVIEW_NOTE`、真人验收写 `review_by='user'`，老记录无 `review_by` 时按 `review_note` 前缀回推；`app.py`／`desktop.py` 验收列改用 `review_label`，交付页新增「采用」列；`approved_versions`／自动粗剪／交接包取版口径不变。新增 3 条集成用例＋交付页断言，定向 318/318、架构 312/312、默认冒烟 8/8，0 红；1352 − 1351 = 1 < 5 且未命中 §5，本轮不跑全量（上次绿全量 1351、tree c97c1336，下一欠账点 1356）。见 tasks_round/tasks_round_1352_result.md。

R1351：O26 白模及外部工具工作区可配置且可写。成果目录默认改为用户数据目录 `%LOCALAPPDATA%/漫剧制作助手/白模项目`，与 Blender 安装位置解耦，可用 `MANJU_WHITE_MODEL_WORKSPACE` 或 `white_model_settings.json` 配置；Blender 发现保留 PATH／`D:`、`E:/Blender`／Program Files 旧路径只读候选；新增 `write_check`／`blender_version`／`legacy_workspaces`／`diagnose` 首次配置检查（版本＋写权限＋可执行提示），白模页加环境摘要标签与「白模环境检查」按钮；探针写入下沉 L1 `file_cache.probe_writable`；新增 21 条用例，定向 160/160＋47/47＋360/360＋20/20、架构 312/312、默认冒烟 8/8，0 红；1351−1346=5≥5 命中五轮欠账：第 1 次全量 1 红为 R1347 遗留文案（`continuity_ledger.py:596`），定向修复后第 2 次全量 4680/4680、416.2 秒、0 红（凭据 round=1351、tree=c97c1336）。见 tasks_round/tasks_round_1351_result.md。

R1350：O25 首帧批量任务统一目标集、重试与替换解释。`keyframe_batch` 新增 `batch_plan`（三意图 `missing`／`retry`／`replace`＋六态＋跳过原因＋实际模型与参考图）：`missing` 只取从没提交过的缺帧镜头、已提交跳过不重付费、`deleted` 任何模式不复活、空文件／未配置／越界一律跳过并给原因；`keyframe_comfy` 弹窗新增「批次意图」下拉与目标集预览，Agent／Seedream／本地三条路径与 `auto_batch` 都按统一目标集并记录计划。定向 93/93、关联全绿、架构 312/312、默认冒烟 8/8，0 红；1350 − 1346 = 4 < 5 且未命中 §5，本轮不跑全量。见 tasks_round/tasks_round_1350_result.md。

R1348：O24「尚未开始先不拦」的兼容策略与正式自动生产分开。`stage_parallel` 新增 `BROWSE`（默认，浏览/补录/旧项目）与 `PRODUCTION`（无人值守）两种口径及 `verdict`/`mode`/`exempt`/`missing` 字段：只有「上游未开始」在正式生产下当前置条件缺失（上游标 `skipped` 即主动豁免），真问题（上游做了没做全）两口径都拦；`Agent.gate` 默认浏览口径不再随持久档位漂移，`Pet.gate_reason` 按自动链是否在推选口径。定向 192/192＋门禁 18/18、快照棘轮 9/9、架构 312/312、默认冒烟 8/8，0 红；1348 − 1346 = 2 < 5 且未命中 §5，本轮不跑全量。见 tasks_round/tasks_round_1348_result.md。

R1347：O23 连贯性问题从发现到解除的闭环。`continuity_ledger` 新增结构化 `issues`（稳定编号 `CI-<kind>-<scope>`、涉及镜头/资产、证据、严重度）与 `03_continuity/output/continuity_issues.json` 登记表（`merge_issues`／`sync_issues`／`decide_issue`／`issue_gate`）：同一问题不重复新增、修好解除、解除后再现重开、证据变化重开且清空决定；人工忽略必须写理由并记下作用版本（当时证据摘要）；`stage_parallel.ledger_ready` 改用 `issue_gate`（忽略后不再拦）；`stage_execution_service` 补 L3 门面；桌面连贯性页新增「问题闭环」表与「忽略（写明理由）」按钮。定向 124/124＋160/160、架构 312/312、默认冒烟 8/8，0 红；1347 − 1346 = 1 < 5 且未命中 §5，本轮不跑全量。见 tasks_round/tasks_round_1347_result.md。

R1346：O22 资产正典、变体与镜头引用提供变更影响视图。`asset_plan` 新增只读 `asset_impact`（正典 `canonical_board`／`character_anchor`、`state_variants`、被哪些采用镜头哪些字段引用、需复核首帧、受影响已生成视频、`orphan`／`protected`）与 `deletion_references`（删前引用清单＋警示），`asset_context.referencing_shots` 与 `references` 同口径，`stage_execution_service` 补 L3 门面，资产详情页顶部提示被引用／可回收；改变体不覆盖正典、删除受引用资产先给引用列表、孤立资产可回收（依赖 O18；O39 回收侧未完成）。定向 64/64、注释快照＋统一棘轮 5/5、架构 312/312、默认冒烟 8/8，0 红；1346 − 1341 = 5 ≥ 5；收口安全全量第 1 次 4610/4610、410.3 秒、0 红（凭据 round=1346、tree=3488e392，last_full_safe_all_round=1346）。见 tasks_round/tasks_round_1346_result.md。

R1345：O21 资产检索与候选墙完善可追溯性和批量决策。`asset_reference_search` 新增 `score_parts`（清晰度/提示词/构图/来源/许可五项分项，`score` 由分项派生且口径不变）、`explain`/`_state`/`STATE_NOTES`（缺地址/缺来源/缺许可/低分/不可商用/来源冲突/重复/可入库八态＋说明）、`suppressed`（低分与同图重复逐条解释）；`rank` 记同图来源 `alts` 与 `conflict`；`normalize`/`_credit` 增 `collected_at`；`reference_wall` 新增许可依据/采集日期/状态/同图来源四列并在状态栏说明挡下的候选，剔除候选不影响已入库资产。定向 118/118、锚定全绿、架构 312/312、默认冒烟 8/8，0 红；1345 − 1341 = 4 < 5，本轮不跑全量。见 tasks_round/tasks_round_1345_result.md。

R1344：O20 保留 Animatic 强校验并降低大媒体重复读取成本。新增 `file_cache.file_digest`（1 MiB 分块流式 sha256 + `(mtime_ns,size)` 缓存，`clear`/`invalidate` 同步清理），`animatic_service.evidence` 源分镜与全体成果改用流式摘要、不再整份读媒体；三项人工确认与「发布前不得代签」不变。实测 64 MiB 文件峰值内存 64.1→2.1 MiB、重复校验 114ms→0.21ms。定向 41/41、锚定 117/117、架构 312/312、默认冒烟 8/8，0 红；1344 − 1341 = 3 < 5，本轮不跑全量。见 tasks_round/tasks_round_1344_result.md。

R1343：O19 初稿/定稿采用增加差异与影响预览。新增只读 `storyboard_catalog_service.adoption_impact`（同集已采用分镜为基线，逐镜稳定 ID 对比 added/removed/changed/reordered，列出将失效首帧与已生成视频镜头），经 L3/L4 门面在 `check_adoptable` 之后、采用之前把 summary 追加到状态栏（不弹窗、不改状态、不换号）；取消采用不改正式清单。定向 78/78、Tk 采用用例 1/1、架构 312/312、默认冒烟 8/8，0 红；1343 − 1341 = 2 < 5，本轮不跑全量。见 tasks_round/tasks_round_1343_result.md。

R1342：O18 来源账本从「仍在」升级为「仍是这个版本」。`artifact_lineage` 新增 `check`/`source_status`（current/stale/missing/unknown）与多来源 `record(sources=…)`、只读 `affected`、显式 `adopt`；`source_available` 语义保留但改为派生（内容变只标过期、不隐藏、不改写成品，仅 missing 隐藏）；剧本/分镜目录对过期项显示「原稿已变更／来源已变更」。定向 136/136、架构 312/312、默认冒烟 8/8，0 红；1342 − 1341 = 1 < 5，本轮不跑全量。见 tasks_round/tasks_round_1342_result.md。

R1341：O17 剧本结构把「形式合格」与「内容完备」分开。`script_contract.structure_script` 头部标明「本地规则提取（未调用模型）」与「结构合法不等于制作信息齐全」；角色卡新增别名（只认原稿声明）与跨集 ID（`char-xxxxxxxx`，同名跨集稳定，可人工改名）；无对白标签、未知道具尺寸、回忆场景（关键词识别）与同名特征矛盾都保留出处或标待确认，程序不臆造。`review_structured_script` 只要求出处字段存在、不要求待确认项填满（原稿冲突尺寸仍阻断）。模板步骤、`stage_exec` 执行器 detail、桌面结构页说明与 `skill_tools` 描述统一改为「规则提取／规则校验（未调用模型）」。定向 71/71、ui_edges 与 skills 全绿、架构相关 35/35、copy_rules 14/14、默认冒烟 8/8，0 红；1341 − 1336 = 5 ≥ 5；收口安全全量第 1 次 4561/4561、420.2 秒、0 红（凭据 round=1341、tree 06c23252，last_full_safe_all_round=1341）。见 tasks_round/tasks_round_1341_result.md。

R1340：O16 四角色审核结果可定位的依据与修订范围。`hollmwood_roles._run` 每次算 `review_basis`（brief／SKILL／节奏／审核 system 四组 sha256）并逐条记 `review_records`（role／attempt／verdict／rule_compliant／creative_signoff／review_text），`review_audit.scope` 点明「APPROVED 只等于规则合格，创意满意由用户在阶段面板确认」；审核 system 收口要求退回逐条给「位置／违反规则／修订建议／通过条件」；返工 prompt 只针对退回意见里的明确问题且不重复注入节奏；`RoleExecutionError` 与 `writing_api` 成功/失败结果都带 `hollmwood_review_audit`；桌面完成文案改为「…已通过（规则合格；创意满意由您确认）」。定向 51/51、关联 139/139、idea_chat 全绿、stage_prompt_governance 15/15、copy_rules 14/14、todo_comment 2/2、默认冒烟 8/8，0 红；1340 − 1336 = 4 < 5，且未命中 §5 升级条件，本轮不跑全量。见 tasks_round/tasks_round_1340_result.md。

R1339：O15 请求冻结与「已加载」清单核对各生成入口。核对结论：直连 API（`capture_request`→`freeze_skills`）与桌面 Agent 投递（唯一入口 `open_flow_agent`，writing 分支 `validate_selected_skills`＋`freeze_skills`）都消费发送边界一次捕获的快照（含 sha256 版本摘要、不含密钥）；手动任务书不发模型请求；媒体生成的批次冻结由 O12 关闭；`idea_chat.skill_injection_summary` 已在气泡展示「已勾选／本次实际加载」。新增 `tests/test_request_freeze_entries.py` 3 条入口差异测试，未改生产逻辑。定向 3/3、关联全绿、默认冒烟 8/8，0 红；1339 − 1336 = 3 < 5，本轮不跑全量。见 tasks_round/tasks_round_1339_result.md。

R1338：O14 会话、请求身份、上下文与项目共享成果分开说明。`writing_api` 新增只读 `chat_session_overview`／`chat_session_summary`：会话模型与调用方式（API 直连／桌面 Agent）、请求身份（Provider／模型目录）、上下文来源（按模型隔离的对话记录）、已确认阶段文件数与自然剧本采用状态，并说明切模型只换对话记录、不隐藏也不复制项目成果；桌面剧本页新增只读标签 `idea_session_label`，随当前显示模型刷新。定向 131/131、关联全绿、架构全绿、desktop_startup_perf 14/14、默认冒烟 8/8，0 红；1338 − 1336 = 2 < 5，本轮不跑全量。见 tasks_round/tasks_round_1338_result.md。

R1336：O13 剧本准备把「对话、工作稿、正式采用」显示为明确状态。`writing_api` 新增 `preparation_reply_state`／`preparation_reply_message`：一次回复唯一状态（已采用／阶段稿待确认／原始响应已保存／因版本变化未采用），带落点文件与下一步；`_preparation_step` 在格式不合格／截断／正文为空／模型失败／版本变化各分支打状态与原因标签，`saved` 与取消后迟到的错误都点明 responses/ 归档不等于正式采用；桌面回复处理器三处状态栏改用同一判据，气泡仍显示正文。定向 139/139、关联 46/46、桌面 115/115、架构 22/22、默认冒烟 8/8，0 红；1336 − 1330 = 6 ≥ 5；收口安全全量第 1 次 4542/4542、385.8 秒、0 红（凭据 round=1336、tree d934dd21，last_full_safe_all_round=1336）。见 tasks_round/tasks_round_1336_result.md。

R1334：O12 TTS 批次冻结配置与缓存身份。`tts_api` 新增 `request_identity`／`freeze_settings`／`batch_identity`：逐句清单带端点＋模型＋音色＋语速身份，`run_lines` 开批冻结配置，`line_done` 沿用前按 `sha256` 复核成品（旧清单退回「文件非空」），`publish_line` 记 `bytes`／`sha256`，整段指纹加 endpoint，`批次.json` 记 `identity`（不含密钥）。定向 49/49、关联 115/115、架构 12/12、默认冒烟 8/8；1334 − 1330 = 4 < 5，本轮不跑全量。见 tasks_round/tasks_round_1334_result.md。

R1333：O11 人工确认绑定被确认的内容摘要。`confirm_gates.content_digest` 给三条候选各带 sha1 摘要（G-05 编号＋名字＋简介／G-06 编号＋名字／G-08 批次＋优先级），`record(..., digest=)` 落摘要，`pending()` 变成「已确认且摘要还对得上」；摘要缺一边按旧口径放行。资产详情页、连贯性页「采用推荐」、Agent 自动三处写入路径都带上候选摘要。定向 101/101、接缝 172/172、架构 15/15、默认冒烟 8/8；1333 − 1330 = 3 < 5，且不命中 §5 升级条件，本轮不跑全量。见 tasks_round/tasks_round_1333_result.md。

R1330：O10 资产「确认并采用」改为可恢复事务。`confirm_gates` 新增相位 pending／applied／failed，`pending()` 只把 applied 当已确认；`adopt_asset_plan_choice` 改成「先记 pending → 落盘 → 成功记 applied」，失败记 failed、中断留 pending，都不再算人工确认；`asset_detail._pick` 失败给出「可再点一次」的恢复提示。定向 96/96、架构棘轮 5/5、默认冒烟 8/8；收口安全全量第 1 次 4528 条唯一红是 TODO 注释快照行号平移（定向修绿）后第 2 次 4528/4528、0 红（tree 3281c7c7）。见 tasks_round/tasks_round_1330_result.md。

R1322：O09 白模就绪绑定来源版本与预演文件。`white_model_service` 新增 `shot_digest`／`source_digest`／`evidence_state`／`record_evidence`：登记采用分镜的镜头调度摘要与预演文件的字节数／mtime／媒体事实；`previs_routing.ready` 按证据收口（来源或文件变过即失效，不知道来源时保持旧口径），`previs_automation.verify` 校验通过即登记，白模页状态列与线上导入共用同一判据。定向 138/138、关联 172/172、默认冒烟 8/8；架构 312/312；收口安全全量 4522/4522（0 红，tree 42e782ea，顺带清掉 R1318 欠的五轮全量）。见 tasks_round/tasks_round_1322_result.md。

R1318：O08 白模复杂度手工覆盖在页面、调度与阶段门禁之间统一。新增 `previs_routing.decisions_for` 作唯一有效决策（覆盖优先，读不到来源时退回 classify），门禁 `stage_parallel.previs_ready` 改用它；`ready` 增开 `source` 按集解析白模目录，`dispatch`／`automatic_candidates`／`previs_automation.start`／L3 `previs_ready` 一并传本次集。跨集同镜头 ID、删除覆盖、自动↔手工切换四场景显示／调度／门禁一致。定向 143/143、接缝 398/398、架构 312/312、默认冒烟 8/8；本轮号 1318 − 上次绿全量 1312 = 4 < 5，未跑全量。见 tasks_round/tasks_round_1318_result.md。

R1312：O07 白模工作目录按「项目身份／集／镜头」隔离。身份取项目 `config.json` 的 `project_id`（随项目改名／移动走），集号按 `EP…_` 前缀／本次传入分镜／聚焦分镜判定；旧布局只读兼容，白模页打开时一次性迁移（可重复、不覆盖、失败原样回滚），迁移清单记来源版本；新建项目当场写入身份。定向与接缝 805 条全绿、默认冒烟 8/8、架构门禁 312/312、收口全量 4516/4516（0 红，tree 12ad4759）。O01—O06 已完成，O08 起继续按序推进。见 tasks_round/tasks_round_1312_result.md。

R1306：四项剧本质检跨 API、托管 CLI、本地桌面保存并提示，候选正文保留；实现 7878b01/1cb4023 已同步。首轮分支全量 4489 条唯一台账连续性失败，当前同步轮次后待干净树复验。定向 124/124，新增边界及审计复验 16/16，冒烟 8/8。未收费实调/重启；O06 并行未提交内容保留。

R1297：Claude CLI 开启 HOLLMWOOD 时由程序逐角色调用并审核，正常 7 次请求；关闭仍走交互式。实现 8e8e576 已同步，定向 67/67、关联 216/216、默认冒烟 8/8；完整架构未重跑，正式历史全量 R1293 4465/4465，本轮欠账 4 轮。未收费实调/重启，需重启加载。见 tasks_round/tasks_round_1297_result.md。其他 O05—O48 持续任务不变。

R1288：Claude CLI 剧本准备限定输入已同步 45884c8；附件仅引用 Markdown，取消全项目扫描/索引注入，阶段①不读取旧 brief；连续确认按独立请求去重。关联 178/178、核心 34/34、冒烟 8/8；架构唯一行号失败修正后 5/5。未实发模型/重启，需重启助手加载；见 tasks_round/tasks_round_1288_result.md。

更新：2026-10-15｜当前轮次：1465（R1464 运行状况面板与状态页归档；R1463 开发者统一入口；R1462 分发清单补全与自检；R1461 行数棘轮、分支清理、计时埋点；R1460 状态页历史迁出与更新记录；R1459 静默吞异常留痕；R1458 标准库门禁与启动日志；R1457 统一日志与崩溃钩子；R1455 文档收口；R1453 三虎弹窗；R1451 切页性能与侧栏；R1450 删除按钮；R1447 切页性能与重复提示修复；R1446 改名与布局；R1443 全量风险触发代码强制、钩子自愈、后台失败提示；R1442 清理 HOLLMWOOD 遗留；R1441 HOLLMWOOD 并入剧本 SKILL 并移除；R1440 全量欠账改源码轮次计数、阈值 8、后台自动补跑；R1439 侧栏切换项目加确认与运行中拦截；R1437 清掉其余 8 条全量红；R1436 测试替身补 sync_master_skill；R1435 字符上限提至 30 万；R1434 见另一任务提交；R1433 统筹改总控；R1432 新增 SKILL 稳定导入；R1431 见另一任务提交；R1430 视频／配音逐笔台账；R1429 项目用量总览；R1428 镜头版本锁定回退；R1427 成片导出 EDL/FCPXML；R1426 环境自检；R1425 CLI 失败提示与图形程序误配拦截；R1424 自动搜寻识别商店版 Claude Desktop；R1423 修复模型管理本机 Claude 的 Provider 显示与表单；R1422 已完成交接收尾；R1420 缓存修复安全全量 5024 项、0 失败，R1419 已由 R1421 合入，合并后定向验证见对应报告。历史缺失报告不补造验收。）

R1283：Claude CLI 明确重新创作新建会话，限制旧资料读取；定向 133/133、冒烟 8/8，架构唯一行号失败修正后原文件 2/2。实现 fcc39ae 已同步，未重跑全量，需重启加载。见 tasks_round/tasks_round_1283_result.md。

R1269 / R1271：模型正文直接显示气泡，检查失败也可展开查看。历史失败已在后续 O47 授权内闭环；集成 R1273/R1276/R1277 后的 a0aaa9b 全量 4419/4419，通过正式 R1279 验证。收尾文档非同树全量。详见 tasks_round/tasks_round_1281_result.md。用户配置保留，未实发 API / 重启。

R1264：制作锁与统筹 SKILL 同排，缩短输入框、删除说明及按钮，修改自动保存且重复值不写。实现 a2f4081；定向 185/185、冒烟 9/9，干净 master a521730 安全全量 4389/4389、413.4 秒，正式 R1264 凭据。此前环境缺失及复验见 tasks_round/tasks_round_1264_result.md；最终文档更新非同树全量。未重启，需重启加载。

R1255 验证：附档明确制作参数同步到配置与简报，手动编辑以 Enter/保存提交，已有剧本不自动改写。历史真实全量 R1251 / 0084579：4365/4365、597.524 秒，不覆盖本轮树。1255−1251=4，无升级项，本轮未跑全量；下一执行轮应核对五轮周期。本轮无功能欠账，并行未提交测试和用户预设均保留。

历史验收记录：更新：2026-10-10｜当前轮次：1223（R1222 文档收尾，R1219 修复阶段旧路径阻断，实现 7faa7ae。干净 master f40beb4 安全全量 --jobs 4：4304/4304、347.409 秒，含架构 311/311；前两次并发保存失败及定向复验详见 tasks_round/tasks_round_1219_result.md。正式全量 R1219，未重启或实发 API。）
阅读索引：[当前待办](#已知阻塞与待办)｜[验证基线](#验证基线)｜[优化队列](维护记录/优化待办队列.md)｜[R504 历史快照](#r504-阻塞归类与整改路线)。带 R 编号的历史条目仅证明对应轮次；当前范围、未验收条件与后续顺序以当前待办及队列为准。

R1159 补充：c9b69fd 已同步主目录，剧本准备气泡区右键清屏保留历史、草稿及附件，刷新恢复。聊天回归 100/100、冒烟 9/9、菜单边界 4/4；未重启，历史全量 R1155，本轮未触发全量。详见 tasks_round/tasks_round_1159_result.md。

R1160：普通弹窗首次宽高不超过主窗口，后续可自由缩放；阶段配置移除永久主窗口上限。定向 177/177、冒烟 9/9；干净 master dfdbf27 安全全量 4264/4264、438.574 秒（含架构），正式 round=1160 凭据已写入。原有 41 路径改动恢复并核对，未重启。详见 tasks_round/tasks_round_1160_result.md。

## 新对话接续协议

R1036 后续文档收尾（用户明确授权）：归档原诊断报告与优化待办队列，中央计数器同步既有报告号 1036，登记 J1；不改原诊断报告、不补造当时测试。收尾当次默认冒烟 8/8、架构门禁 301/301（100.552 秒），与既有 301 基线一致；仅文档及 Git 元数据，无生产逻辑改动，未重复全量。提交回执以 Git 的 `R1036: 归档优化诊断与待办队列` 为准。

1. 按程序目录 `AGENTS.md` §0 读取接续资料；本文按轮次记载的旧事实不等于当前树已验收。
2. 架构、目录、SKILL、模型和数据边界参见同目录 `architecture.md` 与 `PROJECT_MAP.md`；唯一权威索引见 `AGENTS.md` §2.2。
3. 每轮范围、验证和收尾分别按 `AGENTS.md` §2、§5、§7；本文不另设测试周期或只读诊断例外。
4. 密钥、用户数据及重启提示边界见 `AGENTS.md` §2.1。
5. 主界面的“齿轮 → 设置”入口必须保留；界面或服务拆分不得删除、隐藏或使该路径不可达。
6. 架构统一待办见 `维护记录/架构统一路线图_v2.md`，第 3、4 项基数见 `维护记录/架构统一基数.json`；UI 统一待办见 `维护记录/UI统一入口路线图_v1.md`。

- 收尾凭据缺口声明（用户 2026-10-04 裁定）：R963–R995（主树干）与 R996–R1016（codex/architecture-contracts、
  codex/architecture-reconcile-996 分支段）区间存在缺 `tasks_round_N_result.md` 的轮次，
  其中主树干 900 号之后缺号 26 个。经用户决定不逐轮补写历史结果文件（补写不构成凭据），
  该区间的改动内容一律以 git 提交历史为唯一事实来源，不得引用为已验收基线。
  自 R1017 起由 pre-commit 硬拦缺结果文件提交，编号由 round_claim.py 中央分配器唯一发放。

## 当前能力

本节保留历轮能力记录，不是当前待办队列；旧记录中的“下一轮”“待迁移”只指当时安排，不应直接执行。现状与剩余边界见[当前待办](#已知阻塞与待办)，逐项验收来源见[优化队列](维护记录/优化待办队列.md)。R1000 以前的条目已迁出（见下一段）。

本节「R1000 以前」的 494 条逐轮能力记录已原文迁至 [状态历史归档](维护记录/状态历史归档.md)；R1000 及以后与跨轮现状条目保留在此。

- 产品：Windows Tkinter「漫剧制作助手」，零第三方依赖，12 阶段由 `skill_orchestrator` 执行；“剧本结构”位于剧本准备与初步分镜之间。剧本输入与结构化输出由 `script_contract`、`stage_path_service` 解析；旧 `writing/` 仅作历史读取兼容。当前可选 SKILL 以 `skill_registry` 懒加载登记结果为准。
- 三虎：带前缀播报和 UTF-8 日志、检查点/恢复、12 阶段 YAML 模板、手动/全自动模式、暂停/阻塞控制、资产跨重启续跑；`auto_*_var` 的写入权只属于三虎，页面不显示自动制作勾选框。
- 剧本准备：模型/用户气泡左右分列，模型名、折叠、思考提示、原位编辑、拖选复制、右键整条复制/删除及恢复最近删除、输入草稿持久化、输入框自适应和文件表刷新均已实现。每个模型保留独立聊天页并使用稳定浅色主题；下方无标题文件表按项目设定、项目大纲、项目剧本分为三列独立紧凑排列，单元格仅显示文件名，不列出用户简报、聊天记录或无关文件。
- 模型：模型管理是唯一池；阶段按所选厂商/协议/模型/密钥/SKILL 直连 API，不回退到 Qwen。GPT API 与 ChatGPT Desktop 归类为 GPT；自定义 Provider 与模型保存后刷新阶段配置。
- Claude：Messages 调用只显示可见正文；thinking/signature 不进入聊天框。剧本阶段仅可读 `writing/`、`data/项目接续.json`，仅可写 `writing/`，不访问资产清单。
- HOLLMWOOD：LLM 请求在既有后台线程运行；角色进度通过 `queue.Queue` 交给 Tk 主线程每 100ms 消化，并写入三虎进度日志。中断会阻止当前请求进入后续角色及 `script_raw.md` 落盘。
- 文件/删除：生成剧本会刷新文件表；允许删除最后一份剧本、无 `episode.json` 的残留项目链接及其项目目录。
- Python：测试统一使用 `D:\漫剧制作助手\运行环境\Python\python.exe`；Round 136 已实测全局 Python 3.14 与项目内置解释器均可初始化 Tcl/Tk。
## 检查点

以下为 2026-09-24 的历史格式示例，不是当前检查点；`02_assets` 是旧标识，现行阶段 ID 以 `pet_bus.STAGES` 为准。

```json
{
  "stage": "02_assets",
  "step": 3,
  "step_name": "生成缺失的正典板",
  "completed_steps": [1, 2],
  "interrupted_at": "2026-09-24 10:40"
}
```

## 验证基线

R1418 首轮历史记录：缓存边界 8/8（13.862 秒）、受影响 44/44（18.6 秒）、默认冒烟 8/8；架构/文档定向 28/29（10.419 秒），唯一失败为当时 R1418 完整安全全量欠账，现已由 R1420 闭环。当时最近真实全量为 R1403：5006/5006、557.302 秒，tree=`f44ace210cffd75885fa71c39ac3627f3c5ffaa4`，来源 common-dir `full-safe-receipts.json`。详见 [R1418](tasks_round/tasks_round_1418_result.md)。

R1420 最终验收：干净 master `4297564` 安全全量 5024 项、0 失败、437.376 秒，含架构 341 项；正式凭据 round=1420、tree=`8efa76a596ed682f2d3b57a1b2249553c5f9669b`，旧全量欠账已清零，凭据写入后轮次基线再验 5/5（0.325 秒）。缓存配置隔离 8/8、历史门禁样本隔离 7/7；首轮两个失败已闭环且原日志保留。收尾仅改文档，不冒称新树实测。详见 [R1420](tasks_round/tasks_round_1420_result.md)。

R1402 本轮实测：UI 路线图 §一 第 2 项（设计 token）末页迁移——`agent/prompt_optimizer.py` 10 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（**零视觉变更**）＋行号平移同步（架构统一基数 第四项 175→176、覆盖率审计21 位点 173→174）；`test_token_boundary` 计数 16→6。定向 8/8、默认冒烟 8/8、架构 341/341。1402−1400=2<5 且未命中 §5，**不跑全量**（最近绿全量 R1401 `tree=60d4e23d…`）。提交内容 `8274dee`；报告／状态／接力 `0962173`。详见 [R1402](tasks_round/tasks_round_1402_result.md)。

R1401 本轮实测：UI 路线图 §一 第 2 项（设计 token）`desktop.py` 内联间距迁移——13 处 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（**零视觉变更**；无新增 import、行数 7498 不变、无行号平移）；`test_token_boundary` `desktop.py` 计数 40→27。默认冒烟 8/8、架构 341/341。**命中 §5（启动路径，且 1401−1396=5）**：干净 master `o07-fullsafe-master` `--all --safe` 4983/4983、558.1 秒、0 红（凭据 tree=`60d4e23d…`＝`a8a0803:程序`，`last_full_safe_all_round` 1396→1400）。提交内容 `a8a0803`；报告／状态／接力 `71b7d3f`。详见 [R1401](tasks_round/tasks_round_1401_result.md)。

R1400 本轮实测：UI 路线图 §一 第 2 项（设计 token）第 3 批单页迁移——5 页 24 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）＋`keyframe_comfy.py` 1 处等值 `#ffffff→COLORS['background_card']` 改 token（**零视觉变更**）；`test_token_boundary` 计数 `keyframe_comfy.py` 36→25、`workflow_settings.py` 11→6、`white_model.py` 12→8、`native_assets.py` 9→6、`background_characters.py` 3→2、HEX `keyframe_comfy.py` 3→2。定向 168/168、默认冒烟 8/8、架构 341/341。1400−1396=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1399 `tree=250b6384…`）。提交内容 `e81df9c`；报告／状态／接力 `e0c8a75`。详见 [R1400](tasks_round/tasks_round_1400_result.md)。

R1399 本轮实测：UI 路线图 §一 第 2 项（设计 token）第 2 批单页迁移——4 页 21 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）＋`asset_detail.py` 1 处等值 `#ffffff→COLORS['background_card']` 改 token（**零视觉变更**）；`test_token_boundary` 计数 `asset_detail.py` 21→10、`prompt_window.py` 3→0、`qwen_setup.py` 9→6、`seedream_settings.py` 9→5、HEX `asset_detail.py` 21→20。行号平移：TODO注释快照 `asset_detail.py` 353→354、架构统一基数 第四项 `qwen_setup.py` 48→49／170→171。定向 50/50＋70/70、默认冒烟 8/8、架构 341/341（首次 2 红，同步后复验全绿，共 2 次）。**命中 §5 五轮（1399−1394=5）**：干净 master `o07-fullsafe-master` `--all --safe` 4983/4983、609.6 秒、0 红（凭据 tree=`250b6384…`＝`4ed81e9:程序`，`last_full_safe_all_round` 1394→1396）。提交内容 `4ed81e9`；报告／状态／接力 `d6dd313`。详见 [R1399](tasks_round/tasks_round_1399_result.md)。

R1396 本轮实测：UI 路线图 §一 第 2 项（设计 token）单页迁移——`asset_reference_images.py` 13 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（`SPACING['md']`×11、`SPACING['xs']`×2），**零视觉变更**（取值相等且间距与调色板无关）；`test_token_boundary` 该文件数字间距 18→5。定向 `test_reference_images`＋`test_token_boundary` 26/26、默认冒烟 8/8、架构 341/341。1396−1394=2<5 且未命中 §5 升级条件，**不跑全量**。提交内容 `ac01f9f`；报告／状态／接力 `d5aeffc`。详见 [R1396](tasks_round/tasks_round_1396_result.md)。

R1395 本轮实测：出站 HTTP 收口（`platform_tools.open_https`；覆盖率审计26 清零）；定向 7/7、默认冒烟 8/8、架构 341/341。**1395−1390=5 命中 §5 五轮规则**：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d93993e`）跑 `run_selftests.py --all --safe` **4983 条、602.9 秒、0 文件有红**（凭据 tree=`886cfd07…`＝内容提交 `d93993e:程序`；`last_full_safe_all_round` 刷新为 1394）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `d93993e`；报告／状态／接力 `0e5dd5d`。详见 [R1395](tasks_round/tasks_round_1395_result.md)。

R1394 本轮实测：agent 进程原语收口（`platform_tools.run_process`；覆盖率审计21 清零）；定向 7/7、默认冒烟 8/8、架构 `smoke_test.py --architecture` 341/341（数量不变，改既有门禁）。1394−1390=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。提交内容 `a966c41`；报告／状态／接力 `0c1e471`。详见 [R1394](tasks_round/tasks_round_1394_result.md)。

R1393 本轮实测：覆盖率审计棘轮递归化（`production_runtime_files`）；定向 7/7、默认冒烟 8/8、架构 `smoke_test.py --architecture` 341/341（数量不变，改既有门禁）。1393−1390=3<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。提交 `8f1a1fc`。详见 [R1393](tasks_round/tasks_round_1393_result.md)。

R1391 本轮实测：新增 `test_project_entry_boundary.py` 5/5；默认冒烟 8/8；架构 `smoke_test.py --architecture` 341/341（336→341，+5）。1391−1386=5 命中 §5 五轮规则 → 干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` 4983 条、546.4 秒、0 文件有红（凭据 round=1390、tree=a8cfd2f0…＝`37ed5bc:程序`；`last_full_safe_all_round` 刷新为 1390）。

R1390 本轮实测：§三 覆盖率门禁递归对齐（`_scan.production_files_recursive`）；定向 4 文件 8/8、默认冒烟 8/8、架构 `smoke_test.py --architecture` 336/336（数量不变，改既有门禁）。1390−1386=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1387 `tree=000477da…`）。提交 `fdb1daf`。详见 [R1390](tasks_round/tasks_round_1390_result.md)。

R1389 本轮实测：新增 `test_token_boundary.py` 5/5；默认冒烟 8/8；架构 `smoke_test.py --architecture` 336/336（331→336，+5）。1389−1386=3<5 且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动），**不跑全量**（最近绿全量 R1387 `tree=000477da…`）。提交 `c8dbdb0`。详见 [R1389](tasks_round/tasks_round_1389_result.md)。

R1388 只读诊断实测：设计 token 内联视觉常量审计（269 个生产 .py）。默认冒烟 `smoke_test.py` 8/8（只读诊断 §5 默认不跑测试；此为该轮陈述基线的附加冒烟，不计验收）。**不跑全量**（距最近绿全量 R1387 `tree=000477da…`、`last_full_safe_all_round=1386` 仅 2 轮，且本轮无生产改动）。不改生产代码/测试/台账/路线图。提交 `7377586`。详见 [R1388](tasks_round/tasks_round_1388_result.md)。

R1387 实测：按钮门禁递归零容忍（`test_button_boundary` +2）；定向 25/25、默认冒烟 8/8、架构 `smoke_test.py --architecture` 331/331（329→331）。**1387−1382=5≥5 命中 §5 五轮规则**：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d5f597f`）跑 `run_selftests.py --all --safe` **4973 条、572.5 秒、0 文件有红**（凭据 round=1386、tree=`000477da…`＝内容提交 `d5f597f:程序`；`last_full_safe_all_round` 刷新为 1386）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `d5f597f`；报告／状态／接力 `ec2320b`。详见 [R1387](tasks_round/tasks_round_1387_result.md)。

R1386 实测：`pet_bus.stage_label` 新入口＋阶段编号漂移纠正；定向 1275/1275、0 文件红、305.5 秒；默认冒烟 8/8；架构 `smoke_test.py --architecture` 329/329（326→329，+3 门禁）。路线图条目收口（§5）触发全量：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`4cb02d3`）跑 `run_selftests.py --all --safe` **4971/4971、0 红、534.1 秒**（凭据 round=1382、tree=`d9aee73c…`＝内容提交 `4cb02d3:程序`；同一内容树不重跑第二次）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `4cb02d3`；报告／状态／接力 `580d043`。详见 [R1386](tasks_round/tasks_round_1386_result.md)。

R1381 实测：`tests/architecture/test_dialog_boundary` 6/6（含新 canary）、定向 `-k "dialog prompt_window qwen tts_settings cloud_assets"` 24/24、默认冒烟 8/8、架构 `smoke_test.py --architecture` 326/326（原 325，+1）0 红。本轮只改架构门禁与文档、不改生产代码；1381−1380=1<5 且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动），不跑全量；R1380 全量 4967/4967 为历史凭据（tree 不同不复用）。提交 `3ced47d`。详见 [R1381](tasks_round/tasks_round_1381_result.md)。

R1265 当前实测：受影响 458/458、冒烟 9/9；本轮架构首次 307/311，行号/轮次/周期四项问题修复后相关 10/10 复验通过。历史真实全量 R1264（干净 master a521730，4389/4389、413.396 秒）不覆盖本次实现；1265−1264=1，无升级项，不重复全量。完整证据见 tasks_round/tasks_round_1265_result.md。

R1253／R1255：制作锁修复定向 179/179、受影响 236/236、冒烟 9/9（默认 8/8）、架构 311/311、113.479 秒。生产实现 5b88c01，GUI 测试独立迁移 6ecb8e7 后另 1/1；均已同步主目录。全量未触发且未执行，R1251 为历史证据。Tk 非致命焦点告警及首次失败见报告。

R1251：模型切换隔离五项修复。干净 master 0084579 完整安全全量 4365/4365、597.524 秒，架构 311/311；执行器真实 round=1251、tree=8b48b1df35feda0afbd77fb5fedacb82da1b037a。关联 331/331、冒烟 9/9。首轮环境缺件及台账／夹具失败已闭环，见 R1249／R1251 报告。此后仅文档收尾，未实发 API、未重启。

R1248：关联 80/80、受影响冒烟 9/9（含默认 8/8）。首轮全量 1 条历史测试缺少发布器参数，用户授权后仅补齐注入，保留原断言，复测 3/3。干净 master 8512e06 正式安全全量（--jobs 4 --gui-jobs 2）4356/4356、585.006 秒，含架构 311/311；真实 round=1248、tree=37b32d6f6e54e581226fefeb92bbe91ce10761b4。此后仅文档收尾；主目录另一任务未提交修改不属于此凭据。

R1242：关联回归 199/199、115.7 秒，受影响冒烟 9/9（含默认 8/8），注释台账 2/2。首轮全量 10 条失败已闭环，相关复验 209/209、148/148。干净 master df9717d 正式安全全量（--jobs 4 --gui-jobs 2）4337/4337、634.517 秒，含架构 315/315；真实 round=1242、tree=264059cdc559997f5a19dba957ebccef671d33e5。此后仅文档收尾，见本轮报告。

R1213：干净 master 07d440c 正式全量 4302/4302、416.918 秒，含架构 311/311；执行器 round=1213、tree=807bfe5241ffb6e0e6fd48a57f3b1d5f7e8b5cf4。定向 145 条、默认 8/8、受影响冒烟 9/9；补齐隔离依赖后 61/61。最终收尾文档及用户脏树未同树全量；未实发 API、未重启。

R1212：受影响 192/192、默认 8/8、受影响冒烟 9/9、架构 311/311（104.715 秒）；核心 70/70、保存 34/34、取消/交付 12/12 有交集不累加。1212−1208=4，未触发全量升级；历史 R1208 非本轮同树凭据。实现 40f87ac，六项用户修改保持，未重启/实发 API。

R1208：干净 master fe4a923 正式安全全量 4291/4291、397.379 秒，含架构 311/311；执行器已写入 round=1208、tree=3831b1e0fe2e20cf1ea6c7b0b8afb9c881c3bff9。定向 111/111，位置登记修正后 72/72，取消 fixture 补齐后 73/73，默认冒烟 8/8、受影响冒烟 9/9。全量后发现共享缓存隔离细节，补丁先红后绿并定向 68/68；最终缓存补丁、文档树及含六项用户修改的主目录未同树全量。见 R1208 报告。

R1200/R1202：干净 e1f2d26 安全全量 4283/4283、539.0 秒（含架构 311/311），定向 129/129、默认冒烟 8/8、受影响冒烟 9/9；首次全量仅既有 SSE 架构登记行号漂移，修正后定向 71/71 并完整复验通过。后续干净 master 808a972 正式全量 4283/4283、511.725 秒，执行器已写入 R1202 凭据，tree=c4088b61e6cfeea289ff0cbd7dc9daca06628b38。原目录含用户六项修改，最终文档树及用户脏树未同树全量。

- R1198 本轮实测：干净实现基点 `445445f` 安全全量 4279/4279、559.7 秒、0 红（含架构 311/311）；定向 71/71、受影响冒烟 9/9、文档一致性 11/11。实现及审计已同步 master；全量不含六项用户未提交改动，分支未发布正式 master 凭据，历史仍 R1160。收尾仅文档，不冒称最终文档树同树全量。详见 [R1198](tasks_round/tasks_round_1198_result.md)。

- R1180 本轮实测：干净分支 `65649b0` 安全全量 `--gui-jobs 1` 4271/4271、582.2 秒（含架构 310/310）。首次默认并发 1 红，资产模块原断言复跑 18/18；定向 71/71、冒烟门禁 9/9。实现已同步 master；不含六项既有用户改动，分支不写正式 master 凭据，历史仍 R1160。收尾仅文档，不冒称最终文档树同树全量；未实发模型或重启。详见 R1180 报告。

- R1149 实测：模型池/工作流/模型管理 166/166，补充 Codex 路径优先级后定向 17/17；受影响冒烟 9/9（含默认 8/8）。架构 310 条首次 1 红，三处既有解码台账行号同步后失败模块 3/3（2.828 秒），未重复整套。实现 `8bd6241` 已合入；未运行真实 Claude Desktop 或验证登录/回复，历史安全全量 R1145 不代表本轮同树全量。

- R1140 当前实测：干净 master `947a3a7` 安全全量 4226/4226、501.415 秒（含架构）；凭据 round=1140、tree=`2b6e3b0819dda6756f30edb9c0a9dbdbb22118c2`、at=2026-10-08T16:14:45。附件 21/21、冒烟 9/9、入口 3/3；全量首跑两红先增量修绿再复验通过。收尾仅文档变化，不冒称同树全量；未调用外部模型。

- R1134 当前实测：干净 master `f2df26a` 全量 4214/4214、437.628 秒（含架构），受影响 140/140、21.7 秒、冒烟 9/9、默认 8/8。正式凭据 `round=1134`、`tree=a21c2baaaf8db6b3c924a047cc34c8e7b5eee209`、`at=2026-10-08T09:15:03`。收尾仅文档变化，不冒称最终文档树同树全量；真实外部生成和视觉验收未运行。

- R1127 当前实测：干净 master `66fffca` 全量 4187/4187、444.522 秒，含架构 309/309；默认 8/8、受影响 464/464、失败修复增量 59/59。执行器正式凭据 round=1127、tree=`f779114fa9a3d5429bffecbfc653814af11ae82d`；收尾仅文档变化，不冒称同树全量。阶段治理已同步，下一轮 1128。

- R1125 当前实测：干净分支 `c366345` 安全全量 4174/4174、420.9 秒（架构 309/309）；受影响定向 152/152、失败修复定向 26/26、默认冒烟 8/8、注册表 73。实现已快进同步 master；本次分支实跑未写入正式 master 全量凭据，历史 R1122 凭据保持原样。

- R1118 实跑：定向修绿 60/60、追加 14/14、受影响 9/9（含默认 8/8）；干净分支 884835c 全量 4157/4157、419.9 秒，含架构。分支全量不写 master 凭据，正式记录仍 R1115；后续仅文档收尾，不冒称文档树同树全量。

- R1115 实跑：定向 171/171、默认 8/8、受影响 9/9（96 用例）；注释快照行号同步后定向 6/6，最终干净 master 536ebcd 全量 4153/4153、397.524 秒，含架构，中央凭据 round=1115、tree=92d56dd4daa677db8553a9c939077cb4d53cf80a。收尾文档树变化不冒称同树全量。真实用户项目及外部模型未操作，未重启应用。

- R1113 实跑收尾：干净分支 dc8e922 完整安全回归 4148/4148、424.6 秒、0 红项（含架构）；失败闭环及语义专项 24/24、6.678 秒，默认 8/8。实现 412daae 已在 master，R1111 验收闭环；分支执行器不写 master 正式凭据，中央记录仍 R1110。未运行真实外部 Agent/API 端到端，未重启应用；文档收尾后的树不冒称同树全量。

- R1102 实跑：专项 22/22、相关/UI 365/365（200.1 秒）、架构 308/308（36.171 秒）、受影响冒烟 9/9、默认 8/8。旧回调测试桩补齐新方法且原断言全部保留。未改 Tk 生命周期/事件绑定，距 R1101 全量 1 轮，不触发全量；最近正式凭据仍 R1101，不冒称本轮树全量通过。
- R1101 实跑：定向/UI 360/360、独立架构 308/308、受影响冒烟 9/9、默认 8/8；首次全量的旧示例气泡断言冲突已按追加授权迁移，启动性能 14/14。e1179af 干净 master 安全全量 4128/4128、349.289 秒，中央 R1101 凭据已写入；收尾仅文档更新，不冒称文档更新树同树全量。

- R1100 本轮实测：定向 241/241、默认 8/8、受影响 9/9、独立架构 308/308；干净 master 检查点 `4a8d8f3` 全量 4124/4124、447.831 秒。中央真实凭据 round=1100、tree=`c8b8902486cad4ea3bec84d26368bda118cbc4f7`、at=2026-10-07T21:30:56；全量欠账闭环。随后仅回填文档，不冒称最终文档树同树全量；无真实项目/API/实机视觉验收，Tk 非失败警告见报告。新增 6 项测试，既有断言零删除零弱化。

- R1099 本轮实测：分支干净检查点 52c4ff0 安全全量 4118/4118、367.1 秒；定向 235/235，布局修复后 UI/内联 123/123、架构 308/308、默认 8/8，受影响 9/9。78aeef1 合入后仅文档收尾，生产代码/测试与该检查点相同。分支执行器不写主树全量凭据，common-dir 最近正式记录仍 R1097。Tk `greet/run` 非失败警告与未做实机视觉验收的限制见结果报告；旧表单测试获准删除/迁移，未弱化保留功能断言。

- R1097 实测：四项修复专项 29/29、默认冒烟 8/8、跟踪 Python/pyw AST 591/591；干净 master `76b8b77` 正式安全全量 4119/4119、390.132 秒，tree=`3a9db263bae14cd2b5971d0b1986fedf64498eec`，真实回执 round=1097、at=2026-10-07T18:06:30。其后仅回填文档，不冒称最终文档树同树全量；本次四项修复和分批简化目标完成，真实应用与真实用户项目未运行。

- R1088 实测：定向 168/168（59.2 秒）、默认冒烟 8/8、受影响 9/9、独立架构 309/309（23.8 秒），实现 `7c092a3`。未触发本轮全量，不将上一轮凭据冒称本轮验证。
- R1087 实测：定向 242/242、默认冒烟 8/8、受影响 9/9、独立架构 309/309；干净 master 检查点 `88eb04e` 全量 4075/4075、353.079 秒，tree=`7bfadad80296c3be43991a6aaf82646e4f44d41c`，真实凭据 round=1087、at=2026-10-07T07:44:15。详见 R1087 结果，不冒称后续文档树或 R1088 同树全量。

- R1085 实测：定向 115/115、失败项复测 23/23、默认冒烟 8/8、受影响 9/9、独立架构 309/309（30.4 秒）。检查点 `cd7cfae` 安全全量 4064/4064、348.967 秒，tree=`24cb94f0911cb0fc070e0cd52ad95c5d85ea1bad`，真实凭据 round=1085、at=2026-10-07T06:49:53。R1083 的 fcntl 闭包阻塞已消除；随后只归档文档与执行器生成的架构耗时元数据，不冒充最终文档树同树全量。

- R1068 实测：真实干净检查点 `1b36059` 安全全量 3994 条、0 个文件失败（333.662 秒），tree=`8466f0109fe30c54a31d1ea8890e5b05843553d6`，执行器凭据 round=1067。独立副本基线全量 3994 条通过；三个符号试删后的定向 90/90、冒烟 8/8、架构 309/309（120.944 秒）。两处凭据不混用，随后文档归档不冒充最终同树全量。
- R1066 实测：定向 40/40、受影响检查 9/9、冒烟 8/8；检查点 `e7f65b3` 安全全量 3991 条、0 失败（336.8 秒，含架构用例）；树 `8a93b15524b47c306b12ecb1cf5d2228327dcb12`。执行器按运行时最新报告记录 round=1065，未手改凭据；回填文档不冒充同树全量。
- R1065 实测：受影响检查 9/9、默认冒烟 8/8、独立架构 309/309（95.225 秒）；干净检查点 `fed586a` 安全全量 3988 条、0 个文件失败（333.9 秒），程序树 `e95eac4dbc3d49ca8a7c6ea8fd2d47ff3da0250c`。随后仅补本轮报告和状态，不冒充最终文档树的同树全量凭据。普通启动自动消息顺序已有回归，未以真实用户项目验收检查点恢复弹窗。
- R1058 历史实测：文档／轮次 15/15（0.332 秒）、新增链接／锚点 20 处通过、默认冒烟 8/8、独立架构 309/309（104.159 秒）；纯文档，未重复安全全量。
- R1057 历史实测：J16 删除后定向 711/711（166.1 秒）、冒烟 8/8、独立架构 309/309（101.609 秒），文档／轮次回归 15/15；未重复安全全量，下条 R1056 全量凭据仅代表其检查点。

- R1056 历史实测：删除前后定向均 203/203（40.0／38.7 秒）、冒烟 8/8、独立架构 309/309（104.334 秒）。截至 R1058 开工，最近安全全量为 R1056 干净 master 检查点 `70a25ad`，3973/3973、388.9 秒，tree=`67590ad058708133dbee5adc5c1614b39d9b0f29`；随后仅补报告、状态与人工队列，不冒充最终文档树全量凭据。R1054 假凭据审计及下列 R1034、更早条目均为各轮历史记录。
- R1034 历史实测：架构 301/301、109.237 秒；当轮安全全量受测提交 `509b6da`：3937/3937、334.510 秒，tree=`5113c0c2571b9cf256d4509cfff9a2f8f37f1f59`，不是当前最近全量；随后仅补报告/状态文档，不冒充当前文档树的全量凭据。C4 同树连续两遍达标的历史证据仍为 R1032 的 `acde93c`：3934/3934、341.614/341.134 秒，不能把 R1034 单次测量当作新的两遍证据。R1026 六项失败已在 R1027 清空；凭据以 common-dir 真实记录为准。
- R993 完整安全全量的历史记录为 3824/0、306.312 秒；是否可复用必须由 common-dir 的 `full-safe-receipts.json` 按内容树与有效期判定，不由本文授予通过。
- 下列 Round 403 及更早记录均为历史快照；测试触发规则只认 `AGENTS.md` §5。

- Round 403：经 `comfy_runtime.open_comfy()` 启动并读取 `http://127.0.0.1:8188/system_stats`；ComfyUI 0.37.0、RTX 4060 就绪，已保存的 Flux Klein、Qwen 编码器、Flux VAE 均在对应节点选项中。`run_selftests.py --safe --serial -k workflow keyframe_model_service stage_model_value keyframe_comfy` **95/95 通过**；默认 `smoke_test.py` **8/8 通过**。未提交生成任务。

- Round 402：复跑 `smoke_test.py --architecture` **31/31 通过**、默认 `smoke_test.py` **8/8 通过**；`AGENTS.md` 的入口基线已同步为架构 31/31、全量安全自检 3,059 条。历史 Round 182 的 14/14 与 2,942 条仍仅作为当时记录保留。

- Round 401：`tests.test_storage`、`tests.test_asset_resume`、`tests.architecture.test_recycle_service` **17/17 通过**；`smoke_test.py --architecture` **31/31 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 400：本机只读发现 Comfy Desktop 可执行文件；配置端点 `/system_stats` 返回 **HTTP 502**。`run_selftests.py --safe --serial -k workflow keyframe_model_service stage_model_value keyframe_comfy` **95/95 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 399：`smoke_test.py --architecture` **31/31 通过**；`run_selftests.py --safe --serial -k legacy_compat stage_completion_service platform_tools hash_backend` **26/26 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 398：新增原子写入边界架构门禁后，`smoke_test.py --architecture` **28/28 通过**；`run_selftests.py --safe --serial -k workflow force_quit model_pool model_secrets` **144/144 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 396：`run_selftests.py --all --safe` 覆盖 **137 个测试文件、3,059 条用例**，**788.2 秒、0 个失败文件**；默认 `smoke_test.py` **8/8 通过**。白模视频上传真机验收未经用户授权，未执行。

- Round 182 收尾：`run_selftests.py --all --safe --jobs 6` 覆盖 **115 个测试文件、2,942 条用例**，
  **831.3 秒、0 个失败文件**；完整输出：`维护记录/round182_closure_safe_all_20260927.out.log`。
  `smoke_test.py --architecture` **14/14 通过**、7.584 秒，覆盖删除网关、动态导入登记、层级、
  模型边界、循环依赖、路径权威、平台和阶段路径门禁。

- 历史快照：Round 404 默认冒烟 **8/8 通过**；Round 402 架构检查 **31/31 通过**，不代表当前树的结果。
- Round 17：项目文件落盘过滤回归 **49/49**、剧本页面文件表 UI 回归 **1/1**、默认冒烟 **8/8 通过**。
- Round 18：HOLLMWOOD 队列 2/2、剧本 API 14/14、三虎模式 7/7、默认冒烟 8/8 通过。完整 `test_pet_ui.py` 仍有剧本结构阶段插入前的旧断言（期待 storyboard 而非 script_structure），不作为本轮新增失败。
- Round 19：剧本文件三列独立紧凑排列、文件名去除目录前缀的 UI 回归 1/1，默认冒烟 8/8 通过。
- Round 20：TLS EOF 传输重试与四角色剧本失败回退回归 17/17，默认冒烟 8/8 通过。
- Round 21：剧本输入提示垂直居中与空闲滚动 UI 回归 2/2，默认冒烟 8/8 通过。
- Round 16：历史对话简报回归 **48/48**、工作流 **69/69**、API **14/14** 通过；默认冒烟 **8/8 通过**。
- Round 15：剧本准备文件表分类回归 **1/1 通过**，默认冒烟 **8/8 通过**。
- Round 14 定向：`test_api` **53/53 通过**；页面构建异常回归 **1/1 通过**。全量安全自检已按用户指示暂停，未可作为发布通过依据。
- 历史定向记录：Round 13 `test_skill_templates` + `test_sanhu_mode` 10/10 通过；Round 12 `test_skill_templates` 2/2、检查点恢复相关 `test_skills` 2/2 通过；Round 11 `test_sanhu_mode` 7/7、页面构建 1/1 通过。

## 已知阻塞与待办

R1265：用户授权四项技能保障已完成，无本轮功能待办。超过预算的技能组合会明确阻断，需用户减少选择；未实发外部 API／桌面应用，程序注入保障不等于模型绝对遵从。完成后停止，不自动执行下列历史任务。

- R1198 日报周报清理修复及其他生成文件机制扫描已完成，当前请求无阻塞。其他清理风险 J1～J8 仅诊断，见 [审计与测试计划](tasks_round/tasks_round_1198_cleanup_audit.md)；未执行真实项目清理，不自动扩展整改范围。回收不释放总磁盘空间，未重启应用。

- R1139 既有回归阻塞已在 R1140 闭环：旧按钮样式/剧本文案断言已同步用户批准行为，另补齐两页蓝色覆盖；干净 master 947a3a7 全量 4226/4226 通过。技能同步的真实模型创作验证仍未执行，不用自动化通过冒称外部模型行为。

本阶段一般范围锁定（2026-10-01 用户裁决）：只做入口统一、性能与缺陷修复；新功能先登记。Animatic 为用户后续明确授权的例外，见 R1134；此例外不授权其他新功能。

### 【已完成·R1134】新增 Animatic 分镜预演阶段（animatic）

- 授权变更：R1123 仅登记延期；用户后续明确授权新增阶段，并选择应用内部合成与旧目录只读、首次修改复制方案。R1134 完成自动化验收，历史登记保留在 R1123 报告。
- 目标位置：初步分镜 `storyboard` 之后、资产管理 `assets` 之前，不替换白模预演 `previs`。
- 阶段职责：参考图 + 分镜提示词经本地 ComfyUI 生成镜头预演草图，配临时 TTS／导入音频，应用内部合成 Animatic。SG-A/SG-B 约束进入及确认；未实跑外部生成与成片视觉验收。
- 参考图边界：将资产管理的参考图目录在职责上提前为跨阶段共享参考图目录，由分镜预演负责准备、资产管理复用；不物理移动用户数据。
- 资产提示词边界：资产提示词保留在资产管理，不移动到分镜预演。
- 生成边界：资产管理复用相同功能代码，走线上 API 正式生成资产图；分镜预演使用本地 ComfyUI 生成预演草图。
- 验收与边界：全量 4214/4214、默认 8/8；不移动用户数据，不生成正式资产或首帧。完成证据见 [R1134](tasks_round/tasks_round_1134_result.md)，历史登记见 [R1123](tasks_round/tasks_round_1123_result.md)。

### 【待办·显式推迟】会员订阅制（Mode A 软件授权）——开工前置决策清单

- 决定：软件授权制（入口闸门）；用户仍自带 API Key，不碰模型调用链。
- 定价：3 天试用／月 39／季 99／年 399。
- 状态：**显式推迟·非现在实现**，待“入口统一＋性能＋缺陷修复”阶段收尾后再立项。本待办只登记决策与前置项；现在不搭后端、不写登录或付款、不预留接口、不做任何实现。
- 开工前必须先定的 11 项决策：身份（设备／账号）、登录最小范围、试用时长（服务器时间权威，防改本地钟）、计费与自动续费代扣、授权判定的唯一入口位置、订阅凭据存储（禁走 DPAPI 机器绑定）、离线／验权失败宽限策略、验权网络出口（统一经 `platform_tools`）、订阅令牌不得入日志／任务 JSON（靠覆盖率审计 27）、付款资质（商户＋对公／ICP备案／托管收银台不碰卡号／PIPL）、反作弊与 DRM 容忍度。
- 两大先决架构约束：(1) **服务器权威**——本地“是否已付费”被改也不算数；桌面只缓存带签名、带过期时间的续验结论。(2) **试用时长以服务器时间为准**，防系统钟回拨或前调白嫖。
- 与当前阶段的依赖关系：覆盖率审计 21（平台适配）、26（模型路由）、27（密钥）是订阅未来应挂接的接缝；收尾三项即为订阅打地基。订阅闸门应落在统一的 L3 入口，不得内联散写。

UI 统一入口已存在且有多批历史迁移。R1031 的 4 处 tk.Button 候选已由 [R1041](tasks_round/tasks_round_1041_result.md) 完成迁移；50 个带字体/颜色标签是历史扫描候选，R1051 只完成资产详情的 5 处说明文字迁移，不能据此宣布全页面统一。架构第 3、4 项台账 pending 已为空，不再将其写作当前迁移主线。R1032 的“本次清单停止”是当时范围；后续 R1036 队列有独立授权与验收记录，不受该历史停止语句误导。

更新（R1376—R1380，UI 统一入口覆盖轮）：路线图 v1 中此前未收口的 4 项已按各自完成判据收口并**完成全量覆盖审计**——卡片容器（页面级承载区 `ttk.LabelFrame`→`ui_widgets.Card`，21 页已用 Card，其余为卡内小节／锁定几何阅读区／独立工具脚本豁免）、文字层级（说明→`DescriptionBlock`、状态→`ProgressLabel`、标题→`Tokens.Title.TLabel`，7 页门禁固化于 `tests/architecture/test_text_component_boundary.py`）、忙碌态（提交/取消/成功/失败/迟到结果全链路收口到 `BusyState.set_busy`，生产 `ttk.Progressbar.start/stop` 零容忍门禁）、文案与复制（复制失败固定术语＋递归生产扫描门禁）。R1380 命中 §5 五轮规则，干净 master 全量 4967/4967、0 红；架构 325/325。R1381 复核校正：**上述「其余项均未收口」为高估**——路线图其余待审计项多数早已由递归零容忍门禁收口（表格 `test_data_table_boundary` 固定 `{'desktop.py': 3}`，项目树为唯一语义例外；输入／下拉／提示／右键菜单／文件选择／快捷键／Tooltip／图标／滚动条／文案与复制／忙碌态 均为递归 `violations==[]`；弹窗由 R883／R922 收口，R1381 再把 `test_dialog_boundary` 门禁递归化）。**真正剩余**的只剩尚无专用门禁的项：设计 token 内联视觉常量（R1388 只读审计：业务页 111 处内联 hex／8 文件、213 处数字 padx/pady／19 文件、189 处数字字号尺寸候选／32 文件，且 ui_tokens 与 ui_theme 双调色板并存）、§三 覆盖率审计 7 项（R1390 裁定 6 项收口、R1391 收口第 4 项「项目进入路径」，7 项全部收口）。阶段显示已由 R1386 收口（`pet_bus.stage_label` 现算＋`test_stage_display_boundary` 编号一致性／位点冻结门禁）；按钮门禁已由 R1387 由「固定页清单」收紧为递归零容忍（全生产 269 模块 0 裸 `tk/ttk.Button`，架构 331/331）。按路线图各项「完成判据」逐页推进。文字层级旧页面为已登记 backlog。完成依据见 [R1376](tasks_round/tasks_round_1376_result.md)–[R1381](tasks_round/tasks_round_1381_result.md)，范围与判据以 `维护记录/UI统一入口路线图_v1.md` 为准。

### 【已完成·R1386】生产文案阶段编号漂移（R1382 只读审计 → R1386 修复轮收口）

- 现象：R1375（O48）已把用户可见「第N步」收口到 pet_bus.stage_step，但散落的「NN 阶段名」旧编号未同批处理；R1124 插入 animatic（第 04 步）后，资产起整体 +1／+2 偏移（资产 03→05、连贯性 04→06、定稿 05→07、首帧 06→08、白模 07→09、视频 08→10、配音 09→11、剪辑 10→12、质检 11→13）。
- 权威：pet_bus.STAGES（顺序即步号）＋pet_bus.STAGE_NAMES（显示名）＋desktop.PAGES 标签格式；阶段目录名见 stage_layout.STAGES。
- 命中（排除 stage_path_service.LEGACY_NUMBERED 旧目录兼容常量）：R1382 初报生产 14 文件 97 处、tests/ 19 文件 56 处；R1386 复核修正 1 处误报（animatic_service.py:1 的「L2 分镜预演」＝层级前缀 L2，非阶段步号），准确＝生产 13 文件 96 处。
- 用户可见优先：keyframe_batch.py:51/52/141/236、desktop.py:2484、desktop.py:7015/7058、pet_ui.py:2956/2959、stage_parallel.py:477/480/483/486/489、skill_tools.py 的 PAGES 说明列。
- 勿误改：stage_path_service.LEGACY_NUMBERED（旧目录只读兼容常量）、desktop.py:5180（01剧本准备）、desktop.py:5212（02剧本结构）。
- 收口判据（路线图 §二 第 15 项原文）：任何阶段名称展示均从权威表取值 → 修复轮须同时新增/扩展架构门禁（AST 扫生产字符串常量，排除 docstring 与 LEGACY）并同步更新 tests/ 里写死旧编号的 56 处断言。
- 状态：**已收口（R1386 修复轮 §3.2）**。`pet_bus.stage_label` 为「NN 阶段名」唯一权威；6 个展示位点改现算、注释／docstring 按权威序纠正；`test_stage_display_boundary.py` 新增 3 条门禁（编号一致性＋位点冻结＋导航序对齐），架构 326→329；定向 1275/1275、默认冒烟 8/8、干净 master 全量 4971/4971、0 红（tree=`d9aee73c`＝`4cb02d3:程序`）。见 [R1386](tasks_round/tasks_round_1386_result.md)。

### 【待办·已审计未实现】设计 token 内联视觉常量（R1388 只读审计）

- 现象：规则 34 要求 padx/pady、颜色、字号、圆角一律从 token 取值；实际业务页仍大量内联视觉常量，且无自动化门禁。
- 命中（269 个生产 .py，排除 tests／tasks_round／维护记录；权威＝ui_tokens.py／ui_theme.py／ui_widgets.py／ui_icons.py／skills 独立脚本）：① 内联 hex 业务页 **111 处/8 文件**（pet_ui.py 45、desktop.py 31、asset_detail.py 21、cell_hover.py 6、keyframe_comfy.py 3、app.py 2、storyboard_table_ui.py 2、previs_monitor.py 1）；② 数字 padx/pady **213 处/19 文件**（desktop 40、keyframe_comfy 36、asset_detail 21…）；③ 数字 font/wraplength/width/height 候选 **189 处/32 文件**（desktop 41、pet_settings_ui 18、pet_ui 18…；width/height 部分属布局非纯视觉）。
- **双调色板风险**：ui_tokens.py（14 hex）与 ui_theme.py（53 hex）各自硬编码，ui_theme.py **未** import ui_tokens；全生产仅 desktop.py import ui_theme，ui_tokens 被 14 个模块 import。同一 hex 多点重复 → 改色易漂移。
- 现状：tests/architecture 无 token 专用门禁（仅 test_scrollbar_theme_boundary.py）。
- 收口判据（路线图 §一 第 2 项原文「页面是否仍内联视觉常量待审计」）：页面视觉常量从 token 取值 ＋ 棘轮门禁冻结（只减不增）。
- 状态：已审计；**R1389 已加棘轮门禁** `tests/architecture/test_token_boundary.py`（内联 hex 与数字 padx/pady 按文件「只减不增」，新增文件即违规；架构 336/336）。**迁移仍待做**：先统一调色板（`ui_theme` 复用 `ui_tokens`，可能改视觉须先确认），再逐页迁 hex；padx/pady 与字号按单页粒度另批。**R1396／R1399 起**按「值恰等于 token」的可证明零视觉变更子集、单页粒度推进（R1396 `asset_reference_images.py` 数字间距 18→5；R1399 `asset_detail.py`／`prompt_window.py`／`qwen_setup.py`／`seedream_settings.py` 共 21 处间距＋1 处等值色；R1400 五页 24 处间距＋1 处等值色；R1401 `desktop.py` 13 处间距；R1402 `agent/prompt_optimizer.py` 10 处（累计 81 处）。**决策-free 子集至此全部迁完**：全站内联标量 `padx/pady` 只剩非 token 值与 0 值间距。再推进必须先有调色板决议——hex（含 `desktop.py` 31 处）、103 处旧调色板值、非 token 间距值、旧页面文字层级均依赖它。见 [R1388](tasks_round/tasks_round_1388_result.md)／[R1389](tasks_round/tasks_round_1389_result.md)。

### 【已收口·R1391】项目进入路径覆盖门禁（R1390 §三 裁定 → R1391 收口）

- 现象：路线图 v1 §三 第 4 项「项目选择／切换」（权威＝`DesktopStartupController`／`desktop_settings_service`）缺一条架构覆盖门禁断言「所有项目进入路径必经控制器」。
- 现状证据：`desktop.py` 已统一经 `DesktopStartupController`（410/415）；功能级测试 `test_ui_edges`／`test_timers`／`test_desktop_startup_perf`＋`test_project_context_boundary`（project_context 仅 L3 构造）。
- 收口判据（路线图 §三 第 4 项原文「所有项目进入路径可由同一控制器与设置服务审计」）：新增覆盖门禁（desktop 项目进入相关方法不得绕过 `startup_controller`）并证明扫描为空。
- 状态：**R1391 已收口**——新增 `tests/architecture/test_project_entry_boundary.py`（5 条）冻结项目进入入口集合、断言首帧首次选择必经 `DesktopStartupController`、当天选择委托 `desktop_settings_service`；架构 336→341、全量 4983/4983。见 [R1391](tasks_round/tasks_round_1391_result.md)。

### 【已收口·R1393】覆盖率审计棘轮口径递归化（R1390 §三 后续）

- 现象：R1390 只把删除／事件总线／阶段完成三类门禁升为递归；覆盖率审计棘轮仍走 `production_files()`（仅根目录），对 `agent/`（被 30+ 产品模块导入的运行时子包）失明。
- 实现（**不改生产代码**）：`tests/architecture/_scan.py` 新增 `NON_PRODUCT_PARTS`＋`production_runtime_files()`（递归再排除 skills／scripts／reference／outputs／附加工具，239 个运行时模块）；`test_coverage_audit_ratchet.scan()` 默认范围改它、台账键改相对路径 `_key()`；`维护记录/架构统一基数.json` 覆盖率审计21／26 各 +2 pending（count 21→2、26→2；26 baseline_pending 1→2）；判据文档第 21／26 行真候选 0→2。
- 新暴露真候选（pending 待裁定）：`agent/core.py:173`／`agent/prompt_optimizer.py:172`（进程）、`agent/core.py:189/208`（网络）。
- 验证：定向 7/7、默认冒烟 8/8、架构 341/341；1393−1390=3<5 且未命中 §5 升级条件，不跑全量。见 [R1393](tasks_round/tasks_round_1393_result.md)。

### 【已收口·R1394／R1395】agent 包进程原语与出站 HTTP 真候选

- 范围＝R1393 新暴露的 4 条 pending：`agent/core.py:173`、`agent/prompt_optimizer.py:172`（subprocess）；`agent/core.py:189/208`（urllib）。
- R1394 已收口 2 处 subprocess：`agent/core.py` `command()` 改经 `platform_tools.run_process`（惰性 import、移除模块级 `import subprocess`）；`agent/prompt_optimizer.py` MCP 桥子进程同改（模块级 import，保留 `subprocess` 供 `TimeoutExpired`／`SubprocessError`）。行为与异常类型不变；台账 `覆盖率审计21` 两条 pending→migrated、count 2→0，`第四项` `json.loads` 行号平移（core 13→12、prompt_optimizer 174→175）；判据第 21 项真候选 2→0。
- R1395 已收口 2 处 HTTPS：`platform_tools` 新增唯一出站 HTTP 入口 `open_https(url,*,timeout=60,data=None,headers=None)`，`agent/core.py` `request()`／`download()` 改经它（错误分类、密钥脱敏、HTTPS 强制、`geturl()` 重定向校验、1GB 上限、原子发布不变）。裁定：两处均为应用自身资产 I/O（参考图／云端视频下载）非模型路由，且 `download()` 依赖 `agent.core` 原子发布权威不能外移 → 只把出站调用收口到宿主适配层。台账 `覆盖率审计26` 两条 pending→migrated、count 2→0；判据第 26 项真候选 2→0。
- 结果：**覆盖率审计 21／26 真候选全部清零**，双向棘轮相等（再现裸 `subprocess.run`／`urllib.request.urlopen` 会被立即拦下）；占位类型 20／24／25 无真候选。见 [R1394](tasks_round/tasks_round_1394_result.md)／[R1395](tasks_round/tasks_round_1395_result.md)。
- 另：secret sink（覆盖率审计 27）仍为根目录口径，是否同批递归化待评估。

### 项目优化清单（R1058 事实校正）

以下是当前待办的优先级索引，不新增执行授权；每轮只处理一类任务。优先级是建议顺序，不代表未验证项已被认定为缺陷。

| 优先级 / 状态 | 项目 | 下一步与完成边界 |
| --- | --- | --- |
| 已完成 | 三虎聊天瞬时关闭、动画吞单击 | R1034 已分离动画取消与退出清理；新增 3 条回归，全量 3937/3937。部署后的阅读体验仍需重启旧进程确认，不重新列为待开发功能。 |
| 已完成本次审计/核验 | 依赖与历史名称、后台生命周期、文档事实、C4 | R1027–R1032 证据保留；不等于全页面 UI 或全部技术债清零，不重复迁移已采用服务。 |
| 隔离场景已验收；真实环境边界保留 | 启动、同日续开、项目改名认领、幽灵条目 | [R1043](tasks_round/tasks_round_1043_result.md) 验证空项目取消恢复，[R1044](tasks_round/tasks_round_1044_result.md) 验证同日续开，[R1048](tasks_round/tasks_round_1048_result.md) 验证改名认领；[R1050](tasks_round/tasks_round_1050_result.md) 以隐藏 Tk／服务集成验证幽灵登记同步，不是新增实机视觉验收。真实项目、旧运行实例和三虎重启阅读体验未据此关闭。 |
| 已完成 / 不重复立项 | 4 处 tk.Button 统一入口 | [R1040](tasks_round/tasks_round_1040_result.md) 完成图标适配，[R1041](tasks_round/tasks_round_1041_result.md) 完成 3 模块 4 处迁移及别名门禁；原行号仅为 R1035 历史定位，不再作为当前待迁移清单。 |
| 已完成 / 已入门禁 | 覆盖率审计棘轮递归化（产品运行时子包） | [R1393](tasks_round/tasks_round_1393_result.md) 把 `test_coverage_audit_ratchet` 扫描范围由根目录改产品运行时口径（239 模块），覆盖率审计21／26 各 +2 pending；[R1394](tasks_round/tasks_round_1394_result.md)／[R1395](tasks_round/tasks_round_1395_result.md) 已把新暴露的 4 条 agent 真候选全部收口（进程→`platform_tools.run_process`、出站→`platform_tools.open_https`），覆盖率审计21／26 各清零。 |
| P2 / 部分完成，余项待分类 | 文字层级、Card/token、焦点与忙碌反馈 | [R1051](tasks_round/tasks_round_1051_result.md) 完成资产详情 5 处普通说明；[R1052](tasks_round/tasks_round_1052_result.md) 仅完成 Busy／焦点覆盖矩阵，不代表缺口已修。标题、状态色、窄格文字及后续交互修复仍需独立范围，不批量机械替换。 |
| P2 / 持续守护 | 性能、服务契约与上下文覆盖 | 保留现行棘轮和同条件性能验证；新增实际服务再纳入，不因历史名称重复造模块或迁移。 |
| 条件阻塞 | 白模视频真实上传验收 | 等待用户指定镜头和授权发送素材；不自行上传。 |
| 条件阻塞 | P3-2 兼容 facade 退役 | 先查生产调用方及兼容窗口；既有台账淘汰日 2027-03-31，未满足条件不删除。 |
| 显式推迟 | 会员订阅、完整分段流水线方案 3b | 保留原前置决策和需求触发条件；当前不新增用户可见功能。 |

下一项以[优化待办队列](维护记录/优化待办队列.md)的最高优先级未完成项为准；条件项未满足不得勾选。J18 完成后是 J19 的只读职责边界诊断，不重新执行已完成的按钮迁移。本节不新增真实项目操作或上传授权。

UI 待办见 `维护记录/UI统一入口路线图_v1.md`。

性能基准（路线图第 18 项）：R776 已冻结统一归档、同条件中位趋势阈值和共享绝对上限；后续性能轮只可在同条件样本上比较，严禁以冷/热缓存或项目路径差异掩盖回归。

缺陷普查台账 `维护记录/缺陷台账_20261001.md` 保留 R744 时点记录；不能把其中旧“未关闭”直接当作现状。后续授权范围内的启动取消、改名认领和幽灵登记验收见上表 R1043／R1048／R1050；真实用户环境的剩余边界仍保留，本轮不修改原台账或追认历史验收。

回收站恢复入口已有整批／单条／旧 `files` 清单兼容、冲突零移动及越界拒绝的回归覆盖。R770 当时的 `_diag_winprobe.py` 全量阻塞不再是当前状态：R1029 干净提交 66539c3 安全全量 3934/3934。此事实只证明当前受测版本，不追认 R770 或历史缺口轮次验收。

0. 架构统一第 1、2 项已解冻，第 3、4 项台账 pending 均为 0。现行结果采用方 26 个、只读/既有豁免 34 个，范围待审计为空；上下文采用方 22 个、豁免 8 个、7 个未实体化历史名称保留独立审计记录，pending 为空。`storyboard_edit_service` 已采用四字段结果，不能重复列为“下一批迁移”。R1028 只完成历史职责索引，不冒充迁移；完整范围由 `维护记录/架构统一基数.json` 与门禁约束。后续如出现新增实际服务，仍按每轮最多 3 个 service 同步调用方、测试及棘轮，不为清空数字重复改代码。
1. R182 的可执行拆分项仅余 P3-2（facade 退役治理）：P0-1/P0-2 已完成，P0-3 已由 R589–R593 完成；P1-1 至 P1-7、P2-1 至 P2-5、P3-1 均已逐项关闭。当前五个 facade 仍各有生产调用方，且统一淘汰日为 2027-03-31；在任一 facade 零调用或兼容窗口到期前不得删除。旧项目只读迁移的用户可见失败提示尚未有获批交互契约，不能擅自新增。详见 `tasks_round/tasks_round_547_result.md`、`tasks_round/tasks_round_568_result.md` 与 `tasks_round/tasks_round_593_result.md`。R182 以外的全页面响应式布局和删除入口统一是独立专项，不纳入 R182 拆分债务。
2. 白模视频上传真机验收仍未做：需用户指定已采用且已生成预演视频的镜头，并授权向万相/Seedance 发送素材；程序不会擅自上传用户素材。
3. P1 启动白屏用户侧复验：R536 已以真实 Tk 首屏覆盖“无当前项目首页未安排 Canvas 布局”的根因，但无法替代用户重启当前已运行实例后的环境验收。若重启后仍白屏，须保留启动时刻、是否自动打开今日项目及截图，按该新证据诊断；不得把 R523/R527/R535 的局部性能结论当作已解决证明。
4. 流水线代码级分段编排（方案3b）：将剧本准备拆为 岗位1-2（桌面引擎任务）→ Gate A 确认门禁 → 岗位3（程序调用 `hollmwood_roles.run`，API 链）→ 岗位4-8（桌面引擎接力）→ Gate B。前置条件：新增 L3 分段控制器并接 `stage_handler_registry.start()` 唯一入口；中间产物路径经 `stage_path_service` 登记；CLI→API→CLI 两跳的上下文预算需 `workflow_context_budget` 新策略；确认暂停复用 `confirm_gates` 既有机制。触发条件：API 用户需要完整流水线成为真实需求时再立项。
同日续开已完成项（不再列为待执行）：[R1044](tasks_round/tasks_round_1044_result.md) 在隔离正式启动器中完成正常退出→同日重开→01 剧本准备→02/01 切页→正常退出。该证据关闭原第 5 项的隔离正式启动器复验，不涵盖真实项目、大项目、旧运行实例或精确启动耗时；未经另行授权不操作真实项目。

## R504 阻塞归类与整改路线

历史快照：下表及紧随的测试迁移计划描述 R504–R507 当时的安排，不是当前执行顺序，也不授权重新实施密钥迁移。R182 剩余项与当前阻塞见[当前待办](#已知阻塞与待办)；表内“结构治理待办”不得覆盖后续完成证据。

| 优先级 | 分类 | 阻塞条件 | 最小整改闭环 | 完成判据 |
| --- | --- | --- | --- | --- |
| P0 | 已完成（R505） | 新写入已改 DPAPI，旧程序明文文件已受控迁移清理 | 仅保留历史会话的只读兼容 | 保存、读取、迁移失败回滚、云视频取钥及实迁检查均通过 |
| P1 | 已完成（R506） | `responses` 分支现按原生请求/响应格式处理 | 仅提取 `output_text`，保留空文本和错误的真实语义 | 协议专项、架构门禁、安全全量和默认冒烟均通过 |
| P2 | 已完成（R507） | 云视频凭据默认不回填且输入框保持掩码 | 显式查看仅短暂生效，到期后清空；只在新输入时替换 | Tk 无头测试验证默认掩码、无回填、显式显示与自动重新掩码 |
| P3 | 结构治理待办 | R182 清单仍未逐项关闭 | 按既有专项一项一轮，不与上述安全修复混改 | 每项有边界测试和状态记录 |

R504 当时的整改顺序为：P0 密钥迁移 → P1 Responses 协议 → P2 界面掩码 → P3 既有结构专项。P0—P2 在 R505–R507 完成；“进入 P3”仅指当时阶段，不是当前指令。

## R504 测试迁移计划

以下为历史计划，保留追溯；不是本轮测试命令或新增任务。当前验证规则唯一来源为 AGENTS.md §5。

1. 不移动现有测试文件：本次发现属于缺失契约覆盖，不是测试目录组织问题；继续遵守“新测试只放 `tests/`”。
2. 为 P0 新增独立的凭据迁移回归：使用临时目录与假保护器，覆盖旧 `.env` 发现、加密迁移、原子替换失败、旧明文清理和不得回显；禁止读取或使用真实 `private/.env`。
3. 为 P1 在 `tests/test_model_pool.py` 或新增 `tests/test_model_router_responses.py` 固化真实 HTTP JSON fixture；现有 `choices` 桩保留作 Chat 兼容覆盖，不得冒充 Responses 覆盖。
4. 为 P2 在既有云视频测试模块补 UI 状态断言；若 Tk 生命周期使其不稳定，先将“Entry 配置/回填决策”提取为无 Tk 纯函数再测试，不能降低断言或跳过。
5. 迁移与修复完成后依次运行定向测试、默认冒烟、架构门禁；P0/P1 跨模块变更收口时再运行 `run_selftests.py --all --safe`，并记录总数、耗时、失败模块和密钥脱敏检查结果。

## 最近完成

Round 390 及更早的逐轮完成记录已原文迁至 [状态历史归档](维护记录/状态历史归档.md)；当前最新完成项与验证结果见文首轮次头、[验证基线](#验证基线)及[优化队列](维护记录/优化待办队列.md)。
