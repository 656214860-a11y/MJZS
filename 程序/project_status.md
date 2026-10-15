# 项目状态（可独立接续）

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

更新：2026-10-15｜当前轮次：1448（R1447 切页性能与重复提示修复；R1446 改名与布局；R1443 全量风险触发代码强制、钩子自愈、后台失败提示；R1442 清理 HOLLMWOOD 遗留；R1441 HOLLMWOOD 并入剧本 SKILL 并移除；R1440 全量欠账改源码轮次计数、阈值 8、后台自动补跑；R1439 侧栏切换项目加确认与运行中拦截；R1437 清掉其余 8 条全量红；R1436 测试替身补 sync_master_skill；R1435 字符上限提至 30 万；R1434 见另一任务提交；R1433 统筹改总控；R1432 新增 SKILL 稳定导入；R1431 见另一任务提交；R1430 视频／配音逐笔台账；R1429 项目用量总览；R1428 镜头版本锁定回退；R1427 成片导出 EDL/FCPXML；R1426 环境自检；R1425 CLI 失败提示与图形程序误配拦截；R1424 自动搜寻识别商店版 Claude Desktop；R1423 修复模型管理本机 Claude 的 Provider 显示与表单；R1422 已完成交接收尾；R1420 缓存修复安全全量 5024 项、0 失败，R1419 已由 R1421 合入，合并后定向验证见对应报告。历史缺失报告不补造验收。）

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

本节保留历轮能力记录，不是当前待办队列；旧记录中的“下一轮”“待迁移”只指当时安排，不应直接执行。现状与剩余边界见[当前待办](#已知阻塞与待办)，逐项验收来源见[优化队列](维护记录/优化待办队列.md)。未搬移或归档本节历史内容。

- R965 协作治理轮：唯一队列已迁到 Git common-dir/maintenance-queue.json，工作树仅保留忽略的自动快照；show/claim/release 后主树干净。所有自检入口共享 GUI 令牌，超时显式 GUI_DEFERRED，竞争期失败提示 SUSPECT_CONCURRENCY。默认冒烟 8/8、架构 279/279、定向 58/0；检查点 76c1dd3 全量 3808/0，439.508 秒，实测凭据清零历史欠账；最终内容树凭据由收尾后的完整复验写入。C4 的 ≤420 秒性能目标仍未完成。详见 `tasks_round/tasks_round_965_result.md`。

- R962 验收串行化与运行态隔离：共享全量锁禁止提交，完整测量要求根工作树干净且 HEAD 不变；关闭清理记录不再受跟踪，绿凭据改存 Git 元数据。固定 5658fc6 实测 3 路 3797 条/370.1 秒、4 路 3797 条/372.5 秒，均在资产首帧行数和宠物默认等级测试失败。未采纳高并发，C4 未完成；详见 `tasks_round/tasks_round_962_result.md`。

- R960 UI 统一入口覆盖轮（卡片，**部分迁移**）：资产参考图候选墙已接入 `Card`；候选筛选、勾选、版权过滤、异步入库与取消保持不变。详见 `tasks_round/tasks_round_960_result.md`。

- R958 UI 统一入口覆盖轮（卡片，**部分迁移**）：背景人物识别窗已接入 `Card`；候选滚动、批量勾选、确认写入与阶段跳转保持不变。详见 `tasks_round/tasks_round_958_result.md`。

- R957 UI 统一入口覆盖轮（卡片，**部分迁移**）：云图片模型设置表单已接入 `Card`；密钥脱敏、保存、状态反馈与外部账户入口保持不变。详见 `tasks_round/tasks_round_957_result.md`。

- R956 UI 统一入口覆盖轮（卡片，**部分迁移**）：资产参考图导入窗的表单承载区已接入 `Card`；分类选择、文件选择、保存、解除绑定与回收路径保持不变。详见 `tasks_round/tasks_round_956_result.md`。

- R955 UI 统一入口覆盖轮（卡片，**部分迁移**）：视频页的云端工作室设置表单已接入 `Card`；预算校验、联网开关、Wan 适配器校验与经 L3 发布的保存路径保持不变。详见 `tasks_round/tasks_round_955_result.md`。

- R953 UI 统一入口覆盖轮（卡片，**部分迁移**）：本地 ComfyUI 视频设置的完整表单已接入 `Card`，工作流文件选择、节点检测与经 L3 发布的保存路径保持不变。详见 `tasks_round/tasks_round_953_result.md`。

- R951 第 1 项迁移：分镜编辑保存接入四字段结果，调用方仅在成功后刷新；旧清单剩余 34 项，发现当前 L2 与旧清单差异，须完成范围审计后才能宣称全量收口。定向 14 项及默认冒烟通过，完整验证结果见 `tasks_round/tasks_round_951_result.md`。

- R946 全量安全回归自举：完整 `--all --safe` 的锁持有者及其测试子进程可以在收据生成前通过轮次门禁；锁外运行仍必须有七日内同内容树的真实绿凭据。超时回收、失败记录与最终凭据写入逻辑均保持不变。详见 `tasks_round/tasks_round_946_result.md`。

- R952 UI 统一入口覆盖轮（卡片，**部分迁移**）：云端视频 API 设置的完整表单已接入 `Card`；阶段模型确认改由 L4 呈现器注入，消除 L3 对 UI 的反向依赖。密钥遮蔽、连接检测、保存和模型门禁均经定向回归验证。详见 `tasks_round/tasks_round_952_result.md`。

- R938 UI 统一入口覆盖轮（卡片，**部分迁移**）：白模预演的镜头选择窗与主预演窗已接入 `Card`，导入、保存与 Blender 启动逻辑保持不变。详见 `tasks_round/tasks_round_938_result.md`。

- R937 UI 统一入口覆盖轮（卡片，**部分迁移**）：三虎模型设置／模型管理共用的建窗内容区已接入 `Card`，模型表格、连接检测与密钥逻辑保持不变。详见 `tasks_round/tasks_round_937_result.md`。

- R936 UI 统一入口覆盖轮（卡片，**部分迁移**）：齿轮入口的设置枢纽主内容区已接入 `Card`，内部多标签设置与操作逻辑不变。详见 `tasks_round/tasks_round_936_result.md`。

- R935 UI 统一入口覆盖轮（卡片，**部分迁移**）：阶段调用设置的主表单已接入 `Card`，底部操作区与原有流程配置逻辑保持不变。详见 `tasks_round/tasks_round_935_result.md`。

- R934 UI 统一入口覆盖轮（卡片，**部分迁移**）：提示词优化器的设置表单已接入 `Card`；其 UI 回归测试改按行列语义定位，以支持统一容器而不放松功能断言。详见 `tasks_round/tasks_round_934_result.md`。

- R933 UI 统一入口覆盖轮（卡片，**部分迁移**）：Seedream API 设置的配置承载区已接入 `Card`，并纳入卡片边界测试；卡片全页面覆盖仍待逐页审计。详见 `tasks_round/tasks_round_933_result.md`。

- R932 UI 统一入口覆盖轮（卡片，**部分迁移**）：TTS API 设置的配置承载区已接入 `Card`，并纳入卡片边界测试；卡片全页面覆盖仍待逐页审计。详见 `tasks_round/tasks_round_932_result.md`。

- R931 UI 统一入口覆盖轮（卡片，**首批迁移**）：Qwen API 设置的配置承载区已接入 `Card`；卡片全页面覆盖仍待逐页审计。详见 `tasks_round/tasks_round_931_result.md`。

- R930 UI 统一入口覆盖轮（图标，**完成全量创建审计**）：递归门禁确认 UI 图标仅由 `IconLoader` 创建；`asset_thumbs` 的 `PhotoImage` 为媒体缩略图缓存实现，非图标例外。详见 `tasks_round/tasks_round_930_result.md`。

- R929 UI 统一入口覆盖轮（复制，**完成全量写入审计**）：递归门禁确认生产代码的剪贴板写入仅由 `prompt_window.copy_text` 承担，并保留锁与脱敏回执；详见 `tasks_round/tasks_round_929_result.md`。

- R928 UI 统一入口覆盖轮（输入框，**完成全量创建审计**）：递归门禁确认业务 UI 不直接创建 `tk/ttk.Entry`／`Text`，统一经 `LineInput`／`TextArea`；详见 `tasks_round/tasks_round_928_result.md`。

- R927 UI 统一入口覆盖轮（表格，**完成全量创建审计**）：递归门禁确认业务数据表均经 `DataTable`；仅 `desktop.py` 三处项目树形导航保留裸 `Treeview` 作为语义例外。详见 `tasks_round/tasks_round_927_result.md`。

- R926 UI 统一入口覆盖轮（快捷键，**完成命令加速键审计**）：递归门禁确认业务页面的 Ctrl／Command 命令快捷键均经 `ShortcutRegistry` 登记；控件原生局部交互不在命令注册范围。详见 `tasks_round/tasks_round_926_result.md`。

- R925 UI 统一入口覆盖轮（文字层级，**部分迁移**）：Qwen 与 TTS API 设置页的长说明与异步状态已接入 `DescriptionBlock`／`ProgressLabel`；文字层级全量覆盖仍待继续。详见 `tasks_round/tasks_round_925_result.md`。

- R924 UI 统一入口覆盖轮（文字层级，**部分迁移**）：提示词优化设置与 Seedream 设置页的说明／进度文字已接入 `DescriptionBlock`／`ProgressLabel`；文字层级全量覆盖仍待继续。详见 `tasks_round/tasks_round_924_result.md`。

- R923 UI 统一入口覆盖轮（滚动条，**完成全量样式审计**）：递归架构门禁确认业务滚动条不私设 style，统一继承 `ui_theme` 的全局 `TScrollbar` token 样式；详见 `tasks_round/tasks_round_923_result.md`。

- R922 UI 统一入口覆盖轮（Tooltip／弹窗，**完成全量创建审计**）：递归架构门禁确认业务模块不直接创建 `tk.Toplevel`，提示与弹窗统一经 `Tooltip` 或 `BaseDialog`；详见 `tasks_round/tasks_round_922_result.md`。

- R921 UI 统一入口覆盖轮（下拉框，**完成全量样式审计**）：递归架构门禁确认所有生产模块未私自定义 `TCombobox` 样式，桌面根窗口统一初始化 `setup_styles()`；详见 `tasks_round/tasks_round_921_result.md`。

- R920 UI 统一入口覆盖轮（文件选择，**完成全量审计**）：递归架构门禁确认所有生产模块不再直接调用 `filedialog`，文件与目录选择统一经 `FileDialog`；详见 `tasks_round/tasks_round_920_result.md`。

- R919 UI 统一入口覆盖轮（右键菜单，**完成全量审计**）：递归架构门禁确认所有生产模块不再直接创建 `tk.Menu`，右键菜单统一经 `ContextMenu`；详见 `tasks_round/tasks_round_919_result.md`。

- R918 UI 统一入口覆盖轮（忙碌态，**完成主后台链审计**）：中断剧本 Agent 已从直接停止进度条改为经 `BusyState.set_busy(False)` 恢复；架构门禁要求主后台开始、完成及中断成对使用统一忙碌态；详见 `tasks_round/tasks_round_918_result.md`。

- R917 UI 统一入口覆盖轮（通知，**完成全量审计**）：递归架构门禁确认所有生产模块不再直接调用 `messagebox.show*`，显示反馈统一经 `notify` / `NotificationDispatcher`；详见 `tasks_round/tasks_round_917_result.md`。

- R916 UI 统一入口覆盖轮（按钮，**完成裸控件清理**）：主壳的导航、项目选择、链接、连贯性与视频入口全部接入语义按钮；生产 Python 中仅 `ui_widgets.py` 的组件实现保留 `ttk.Button`。按钮边界测试覆盖增至十八个模块；详见 `tasks_round/tasks_round_916_result.md`。

- R915 UI 统一入口覆盖轮（按钮，**部分迁移**）：应用页的 MCP 优化与离线编剧任务书生成已接入语义按钮；付费优化仍保留高亮层级。按钮边界测试覆盖增至十七个已迁移模块；详见 `tasks_round/tasks_round_915_result.md`。

- R914 UI 统一入口覆盖轮（按钮，**部分迁移**）：资产详情页与资产清单中的所有操作按钮已接入语义化主／次按钮；按钮边界测试覆盖增至十六个已迁移模块。详情页全量 GUI 回归在既有状态变体用例处超过运行时限，未作为通过依据；详见 `tasks_round/tasks_round_914_result.md`。

- R913 UI 统一入口覆盖轮（按钮，**部分迁移**）：阶段配置面板的统筹简报编辑入口已接入语义化次按钮；按钮边界测试覆盖增至十五个已迁移模块。详见 `tasks_round/tasks_round_913_result.md`。

- R912 UI 统一入口覆盖轮（按钮，**部分迁移**）：资产生成页的账号设置、启动检测和取消检测均已接入语义化主／次按钮；按钮边界测试覆盖增至十四个已迁移模块。详见 `tasks_round/tasks_round_912_result.md`。

- R911 UI 统一入口覆盖轮（按钮，**部分迁移**）：首帧管理的模型设置、执行、停止、检查、记录和关闭操作均已接入语义化主／次按钮；按钮边界测试覆盖增至十三个已迁移模块。详见 `tasks_round/tasks_round_911_result.md`。

- R910 UI 统一入口覆盖轮（按钮，**部分迁移**）：白模预演页的进入、制作、保存、导入和外部打开操作均已接入语义化主／次按钮；按钮边界测试覆盖增至十二个已迁移模块。详见 `tasks_round/tasks_round_910_result.md`。

- R909 UI 统一入口覆盖轮（按钮，**部分迁移**）：提示词复制窗和参考图候选墙的操作均已接入语义化主／次按钮；按钮边界测试覆盖增至十一个已迁移模块。详见 `tasks_round/tasks_round_909_result.md`。

- R908 UI 统一入口覆盖轮（按钮，**部分迁移**）：本地视频控制条的 H3／ComfyUI 启动操作已接入语义化次按钮；按钮边界测试覆盖增至九个已迁移模块。详见 `tasks_round/tasks_round_908_result.md`。

- R907 UI 统一入口覆盖轮（按钮，**部分迁移**）：阶段调用设置窗的文件选择、Qwen API、检查、保存和取消均已接入语义化按钮；按钮边界测试覆盖增至八个已迁移表单。详见 `tasks_round/tasks_round_907_result.md`。

- R906 UI 统一入口覆盖轮（按钮，**部分迁移**）：Seedream 火山 API 设置窗的保存、检测、外部帮助、删除和取消均已接入语义化主／次按钮；按钮边界测试覆盖增至七个已迁移表单。详见 `tasks_round/tasks_round_906_result.md`。

- R905 UI 统一入口覆盖轮（按钮，**部分迁移**）：Comfy 云图片、Qwen Code 与 Prompt Optimizer 的设置窗均已接入语义化主／次按钮；按钮边界测试覆盖增至六个已迁移表单。详见 `tasks_round/tasks_round_905_result.md`。

- R904 UI 统一入口覆盖轮（按钮，**部分迁移**）：资产参考图绑定及参考图查看两个窗口的操作按钮已接入语义化组件；边界测试扩展为三个已迁移表单。详见 `tasks_round/tasks_round_904_result.md`。

- R903 UI 统一入口覆盖轮（按钮，**部分迁移**）：背景人物识别弹窗的全选、全不选、确认和取消已统一到语义化按钮；按钮边界测试扩展为两个已迁移表单。详见 `tasks_round/tasks_round_903_result.md`。

- R902 UI 统一入口覆盖轮（按钮，**部分迁移**）：资产参考图导入窗的选择、保存、删除、取消均已改用语义化主／次按钮；新增边界测试防止该已迁移表单退回裸 `ttk.Button`。详见 `tasks_round/tasks_round_902_result.md`。

- R901 UI 统一入口覆盖轮（确认对话框，**完成直接调用清理**）：阶段配置、剧本／分镜文件与三虎一键执行的确认均已接入统一入口；生产 Python 中不再存在 `messagebox.ask*` 直接调用（仅统一适配器说明文字保留字面量）。定向回归 18 条／0 红，确认覆盖仍需配合路线图其它项目持续审计。详见 `tasks_round/tasks_round_901_result.md`。

- R900 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：主壳剩余 11 个直接确认调用（剧本、项目、资产、首帧及 Codex 发送）均已接入统一确认；危险或可逆删除使用危险确认，首帧批删回归 1 条／0 红。主壳不再直接调用 `messagebox.ask*`，其他模块仍待迁移。详见 `tasks_round/tasks_round_900_result.md`。

- R899 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：主壳的首帧删除/恢复及逐句配音付费提交已接入统一确认；删除与付费提交均为危险确认，语法检查通过，主壳仍余 11 处历史直接确认调用。详见 `tasks_round/tasks_round_899_result.md`。

- R898 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：主壳项目列表的失效登记清理与移入项目回收站已接入危险确认；语法检查通过，主壳仍余 14 处历史直接确认调用。详见 `tasks_round/tasks_round_898_result.md`。

- R897 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：桌面主壳新增同步统一确认适配器，诊断导出与强制关闭已迁移；语法检查通过。主壳仍余 16 处历史直接确认调用。详见 `tasks_round/tasks_round_897_result.md`。

- R896 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：资产批量的不确定提交结果确认已接入危险确认，保留云端重复计费风险提示；语法与差异检查通过。其他直接确认调用仍待迁移。详见 `tasks_round/tasks_round_896_result.md`。

- R895 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：阶段模型的默认确认已接入统一入口，测试可注入 `ASKER` 保持兼容；语法检查与手动门禁回归 15 条／0 红。其他直接确认调用仍待迁移。详见 `tasks_round/tasks_round_895_result.md`。

- R894 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：首帧旧任务放弃并重提已接入危险确认；重提回归 2 条／0 红、语法检查通过。其他直接确认调用仍待迁移。详见 `tasks_round/tasks_round_894_result.md`。

- R893 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：资产详情的状态变体删除和参考图解除绑定已接入危险确认；语法检查与状态变体回归 5 条／0 红。其余直接确认调用仍待迁移。详见 `tasks_round/tasks_round_893_result.md`。

- R892 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：资产批量、云视频、Qwen、首帧 ComfyUI 与提示词优化的模型配置删除已接入危险确认；语法检查与提示词优化设置回归 8 条／0 红。其他直接确认调用仍待迁移。详见 `tasks_round/tasks_round_892_result.md`。

- R891 UI 统一入口覆盖轮（确认对话框，**部分迁移**）：主视频页的导入预览、删除本地视频、批量删除与云端付费提交已接入统一确认入口；菜单回归 40 条／0 红，自动提交回归 8 条／0 红。完整视频 UI 套件受单次执行窗口限制未收尾，未声明全套通过；其他直接确认调用仍待迁移。详见 `tasks_round/tasks_round_891_result.md`。

- R889 C4 安全自测执行器调整（**已完成定向验证**）：`--safe` 的 Tk 测试池固定最多两路，非 Tk 仍并行，性能单元仍独占串行；新增 `--force` 用于绕过同内容树凭据并强制全量复核。定向 27 条／0 红。详见 `tasks_round/tasks_round_889_result.md`。

- R890 UI 统一入口覆盖轮（确认对话框，**进行中**）：已新增 `ask_confirmation()`，同步调用者也经 `ConfirmDialog` 呈现，窗口关闭或销毁一律拒绝；无人值守开启与 Seedream 不确定请求重提已迁移。其余历史确认调用待分批替换，路线图尚未完成。

- R888 UI 统一入口覆盖轮（文字层级，**部分迁移**）：云视频、原生资产及白模预演的说明／进度文字迁至统一组件；语法检查、云视频 12 条与白模 54 条通过。详见 `tasks_round/tasks_round_888_result.md`。

- R887 UI 统一入口覆盖轮（文字层级，**部分迁移**）：资产批量、参考图与云图设置的说明／状态文字已迁至 `DescriptionBlock`／`ProgressLabel`；语法检查及输入、表格门禁合计 21 条／0 红。全页文字层级尚未收口，不能计作路线图完成。详见 `tasks_round/tasks_round_887_result.md`。

- R886 UI 统一入口覆盖轮（下拉框，**已完成审计**）：移除模型管理页的私有 `TCombobox` 样式；业务页面不得定义 Combobox 样式，根窗口须调用 `setup_styles()`。定向 2 条／0 红，模块语法检查通过。详见 `tasks_round/tasks_round_886_result.md`。

- R885 UI 统一入口覆盖轮（输入框，**已完成审计**）：根目录及子模块业务 UI 的 `Entry`／`Text` 直构为零，统一经 `LineInput`／`TextArea`。门禁由主页面历史数量上限收紧为零容忍，定向 4 条／0 红。详见 `tasks_round/tasks_round_885_result.md`。

- R884 UI 统一入口覆盖轮（表格，**已完成审计**）：业务数据表均经 `DataTable`；根目录仅保留 `desktop.py` 的 3 个项目树形导航选择器，不承担数据表语义。门禁由历史上限收紧为全根目录扫描及明确语义例外，定向 17 条／0 红。详见 `tasks_round/tasks_round_884_result.md`。

- R883 UI 统一入口覆盖轮（弹窗，**已完成审计**）：根目录业务模块不再直接构造 `Toplevel`；`BaseDialog`／`FormDialog`／`ConfirmDialog` 是唯一业务弹窗入口。门禁由历史文件上限收紧为扫描全部根目录生产模块的零容忍规则，定向 5 条／0 红。一次完整 `--all --safe` 执行中 `test_asset_gating` 出现 1 条瞬态失败；单独隔离复跑 18 条／0 红，故未写入绿色全量凭据。详见 `tasks_round/tasks_round_883_result.md`。

- R882 UI 统一入口覆盖轮（通知分发，**局部验收；完整全量待补**）：业务根目录的非确认型提示全部经 `ui_widgets.notify()`／`NotificationDispatcher`；静态门禁覆盖所有根目录生产模块并要求零个直接 `messagebox.show*`。语法检查、通知边界与通知行为共 9 条／0 红；扩展回归实际执行 230 条／0 红；完整安全全量受 R881 有效锁阻塞。详见 `tasks_round/tasks_round_882_result.md`。

- R873 协作治理轮（全量安全自测错峰锁，**已验收**）：`run_selftests.py --all --safe` 在 Git common-dir 使用原子锁跨工作树互斥；活动持有者会被拒绝并显示 PID／轮次，失效锁会回收，Windows 使用进程句柄判断存活。相关回归 35 条／0 红。详见 `tasks_round/tasks_round_873_result.md`。

- R871 协作治理轮（Git hooks 协议，**已验收**）：版本受控的 `commit-msg`／`pre-commit` 模板可由安装脚本写入共享 Git hooks；提交消息受 R 轮次前缀约束，`程序/` 中的非默认文档必须显式列入白名单，非 master 不可改 `project_status.md`。定向 10 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_871_result.md`。

- R870 协作治理轮（队列认领强制化，**已验收**）：`round_claim.py` 新增 `claim`／`release`，队列更新与轮次计数共用 Git common-dir 排他锁和原子写入；默认 60 分钟租约会拒绝已完成项或他人有效认领，过期抢占和释放均记入 note。`AGENTS.md` 已纳入开工协议。回归 6 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_870_result.md`。

- R869 协作治理轮（共享轮次分配器，**已验收**）：新增 `维护记录/基准脚本/round_claim.py`，在 Git common-dir 以排他锁和临时文件原子替换维护轮次计数；每轮开工按 `AGENTS.md` 领取唯一轮次，消除跨工作树同号提交。并发回归 3 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_869_result.md`。

- R868 结构治理轮（任务 C 合并点，验收中）：已将 `codex/r856-workspace-maintenance` 合并入主干；R857 与主干 4c4d472／22c3755 的阶段配置同题改动已按主干版本去重，工作树维护、内容树全量凭据与共享增量台账机制保留。本轮完整安全全量的最终结果见 `tasks_round/tasks_round_868_result.md`。

- R866 缺陷治理轮（ComfyUI 就绪等待取消，**已验收**）：`wait_comfy()` 接受取消回调；自动资产、首帧、视频和原生资产将既有 stop 事件传入，因此不再在取消后继续等待重试。定向 150 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_866_result.md`。

- R865 台账收口轮（Qwen 就绪等待，**已验收**）：已将 R864 的线程边界证据回写 sleep 台账；Qwen 项自服务重试 B 组拆出并标记收口。R844/J2 的自动视频连续进度迁移已由 R847 完成，不重复实施。轮次基线 4 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_865_result.md`。

- R864 缺陷治理轮（Qwen 就绪等待线程边界，**已验收**）：交互会话启动后的命名等待由独立线程执行；复用会话的续发由 `Desktop.async_()` 提交，Qwen 就绪轮询不会占用 Tk 回调。Qwen 定向 3 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_864_result.md`。

- R863 缺陷治理轮（退出维护 sleep 线程边界，**已验收**）：关闭后的项目维护三秒等待只在脱离标准流的独立 `--cleanup` 进程中运行；退出 UI 不会等待它。存储专项 9 条／0 红、完整安全全量 3,706 条／641.2 秒／0 红，基线已更新至 R863。详见 `tasks_round/tasks_round_863_result.md`。

- R862 缺陷治理轮（原生素材 sleep 线程边界，**已验收**）：原生素材的 ComfyUI 检测重试与生成进度轮询均由 `Desktop.async_()` 提交，不在 Tk 按钮回调执行；新增 UI 契约回归防止未来重构回退。原生素材门禁 6 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_862_result.md`。

- R861 缺陷治理轮（缩略图 UI 阻塞回退，**已验收**）：后台缩略图 worker 不可用时不再在 Tk 当前回调同步解整图；页面保留既有文字占位，避免大图卡住滚动或切页，待后台可用或下次打开再补图。缩略图专项 21 条／0 红、轮次基线 4 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_861_result.md`。

- R860 缺陷治理轮（资产自动导入 watcher，**已验收**）：批次台账读取、格式或键缺失错误不再被 watcher 静默吞没；轮询仍每约两秒重试，但页面明确显示原因。故障注入 1 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_860_result.md`。

- R859 缺陷台账治理轮（TODO 注释快照，**已验收**）：生产顶层代码的 TODO／暂时等关键词现由 AST 所属函数与 tokenize 注释位置冻结为逐条快照；当前 3 条均为 C 类已实现行为说明，新增或移动关键词必须先分类，不会再把注释文本误报成产品缺陷。快照门禁 2 条／0 红、默认冒烟 8/8；完整安全分层全量：架构 228 条／81.8 秒、服务 1,661 条／71.9 秒、GUI 短生命周期 1,141 条／320.4 秒、GUI 端到端 673 条／341.3 秒，均 0 红。详见 `tasks_round/tasks_round_859_result.md`。

- R858 测试基础设施治理轮（**已验收**）：安全模式改为当前进程依次执行真实测试单元，不再依赖 Windows 可能拒绝的隔离子进程句柄派生；非安全串行模式的隔离与超时回收不变。定向 21 条／0 红、架构层 226 条／69.9 秒／0 红。R856 新增异常类型造成的两处既存 JSON 读取行号漂移已同步冻结棘轮；未新增读取入口。详见 `tasks_round/tasks_round_858_result.md`。

- R857 测试基础设施治理轮（**已验收**）：安全串行全量在 Windows 拒绝复制新隔离子进程句柄时，回退为同进程执行真实测试单元，正常路径仍保留进程隔离与超时回收。定向 20 条／0 红，安全模式定向 20 条／0 红。详见 `tasks_round/tasks_round_857_result.md`。

- R856 缺陷治理轮（异常 AST 网络路径，**已验收**）：ComfyUI 提交回执中断后，队列与历史若均无法读取，不再静默当作“未找到任务”；记录保留 `unknown`，界面明确提示连接核对且不重复提交。定向 6 条／0 红、默认冒烟 8/8、轮次基线 4 条／0 红。R855 的已验证完整安全全量 3,698 条／996.8 秒／0 红已同步基线轮次。详见 `tasks_round/tasks_round_856_result.md`。

- R855 缺陷治理轮（异常 AST 网络路径，**已验收**）：旧版 ComfyUI `/dispatch` 返回异常但可能已排队时，立即显示“继续核对、不重复提交”的可行动提示，批次记录保留警告。定向 6 条／0 红、默认冒烟 8/8。详见 `tasks_round/tasks_round_855_result.md`。

- R854 审计轮（sleep 调用链，**已验收**）：确认素材生成／检测的 sleep 处于 `Desktop.async_()` worker，缩略图 sleep 位于测试收敛或独立 worker，维护脚本 sleep 仅由 CLI 清理入口触发；没有静态证据证明 Tk 回调直达 sleep。保留实机卡顿复验挂账。详见 `tasks_round/tasks_round_854_result.md`。

- R853 回归维护轮（**已验收**）：白模自动派发回归夹具适配 ticket 生命周期参数，继续验证复杂镜头仅派一次、首帧完成后才派发；状态轮次与结果报告连续。定向 2 条／0 红。详见 `tasks_round/tasks_round_853_result.md`。

- R852 缺陷治理轮（异常 AST 分类首项，**已验收**）：本地 ComfyUI 已接受制图任务但认领回执断网时，批次记录与进度状态会明确说明“按输出目录核对、不重复提交”，不再静默伪装成正常认领。定向 6 条／0 红、默认冒烟 8/8；完整安全全量 3698 条中 R852 专项通过，轮次基线与白模替身回归在 R853 收口。详见 `tasks_round/tasks_round_852_result.md`。

- R851 结构治理轮（架构统一第 6 项第七批，**已验收**）：白模预演专用进程的完成／失败播报以 ticket 接纳，取消、禁用或新代次后的旧线程不能再交付桌宠或主界面；外部引擎仍仅按项目登记精确终止。定向 99 条／0 红、默认冒烟 8/8；完整安全全量按三轮门禁后续补跑。详见 `tasks_round/tasks_round_851_result.md`。

- R850 结构治理轮（架构统一第 6 项第六批，**已验收**）：云端跨页监控以 ticket 隔离旧结果，关闭或替换代次后不再改变 UI、忙碌状态或节流。定向 122 条／0 红、默认冒烟 8/8、完整安全全量 3696 条／0 红（1021.0 秒），`last_full_safe_all_round=R850`。详见 `tasks_round/tasks_round_850_result.md`。

- R849 结构治理轮（架构统一第 6 项第五批，**已验收**）：自动首帧的共享派发、日志和最终结果均受后台代次约束；替换、禁用或关窗后的旧 worker 不能刷新 UI 或推进阶段。定向 681 条／0 红、默认冒烟 8/8；详见 `tasks_round/tasks_round_849_result.md`。

- R848 结构治理轮（架构统一第 6 项第四批，**已验收**）：自动资产的进度、最终结果与缺图续跑台账均受后台代次约束；旧 worker 在替换、禁用或关窗后不能刷新 UI、写台账或推进阶段。定向 120 条／0 红、默认冒烟 8/8；详见 `tasks_round/tasks_round_848_result.md`。

- R847 结构治理轮（架构统一第 6 项第三批，**已验收**）：自动视频接入带代次的后台生命周期；连续进度与最终结果均在主线程按 ticket 校验，替换、禁用或关窗后的旧 worker 不能刷新 UI 或推进无人值守链。完整安全全量 3693 条／0 红（994.9 秒），`last_full_safe_all_round=R847`；第 6 项继续迁移资产、首帧、白模与云端监控。详见 `tasks_round/tasks_round_847_result.md`。

- R843 结构治理轮（架构统一第 6 项第二批，**已验收**）：自动粗剪和自动交接包分别接入独立的生命周期代次；关窗后的迟到队列结果不再刷新页面、状态栏或推进下游，正常成功／失败仍沿用原有主线程收尾、退避与自动链语义。自动视频因包含连续进度消息留待下一批，第 6 项尚未整体收口。定向 563 条／0 红、默认冒烟 8/8、架构门禁 226/226；R843−R841=2，未触发完整安全全量，`last_full_safe_all_round` 保持 R841。详见 `tasks_round/tasks_round_843_result.md`。

- R842 结构治理轮（架构统一第 6 项首批，**已验收**）：桌面唯一主动异步入口 `Desktop.async_()` 现以无 Tk 的 `BackgroundTaskLifecycle` 统一登记提交、逻辑取消、成功／失败收尾；中断、关闭或新代次替换后，旧线程即使迟到返回也不能再交付 UI 回调。该轮不强杀任意 Python 线程，预演、媒体等可终止专用进程仍按原协议运行，后续继续迁移。定向 5 条／0 红、默认冒烟 8/8、架构门禁 226/226；R842−R841=1，未触发完整安全全量，`last_full_safe_all_round` 保持 R841。详见 `tasks_round/tasks_round_842_result.md`。

- R839 安全契约轮（覆盖率审计 27，**已验收**）：新增受控密钥 source→日志、任务 JSON、prompt sink 的同函数最小数据流审计；`model_secrets.load`、`model_pool.credential`、`pet_llm.credential`、`api_endpoints.configured_key` 与敏感环境读取均受覆盖，三类金丝雀均命中。生产扫描未发现泄漏，审计 27 真候选、pending 与判据数字均为 0，未触发 `[SECURITY]` 修复轮。定向安全集 7 条／0 红、默认冒烟 8/8、架构门禁 222/222；R839−R837=2，未触发完整安全全量，基线保持 R837。详见 `tasks_round/tasks_round_839_result.md`。

- R840 审计契约轮（覆盖率审计 20，**已验收**）：本地视频工作流与配置的原子替换／发布现在均经 L3 网关注入 `file_cache.published` 失效缓存；回滚路径同样通知。新增 JSON 替换后漏发缓存失效的冻结扫描与金丝雀，生产 pending、台账与判据三源均为 0。定向 28 条／0 红、默认冒烟 8/8、架构门禁 222/222；按每三轮一次门禁补跑完整安全全量 3667 条／0 红（965.1 秒），`last_full_safe_all_round=R840`。详见 `tasks_round/tasks_round_840_result.md`。

- R841 契约轮（架构统一第 5 项，**已验收**）：补齐事件总线边界门禁，跨模块状态只能经 `pet_bus.emit_safe()`；`pet_agent._emit()` 与 `pet_ui._emit()` 是仅有受控转发器，`Bus.emit()` 只能在 L0 实现层出现。`broadcaster` 被明确限制为 `desktop`／`pet_ui` 的用户可见文本日志，不能作为状态通知旁路。没有改产品行为。定向 20 条／0 红、默认冒烟 8/8、架构门禁 226/226；完整安全全量 3671 条／0 红（1005.4 秒），`last_full_safe_all_round=R841`。详见 `tasks_round/tasks_round_841_result.md`。

- R838 审计契约轮（覆盖率审计 25，**已验收**）：事件名审计改以 `pet_bus.CONTRACT` 作为唯一权威源；扫描器现正确读取 `emit_safe(bus, errors, kind, ...)` 的第三参数并覆盖所有 `*._emit(kind)` 调用。38 个静态字面量事件均已登记，审计 25 真候选、pending 与判据数字均为 0。定向安全集 4 条／0 红、默认冒烟 8/8、架构门禁 219/219；R838−R837=1，未触发完整安全全量，基线保持 R837。详见 `tasks_round/tasks_round_838_result.md`。

- R837 审计收口轮（覆盖率审计 21，**已验收**）：阶段目录 junction 回退由 `platform_tools.run_process` 统一执行，仍维持静默输出和返回码判定；`platform_tools` 的跨平台适配职责校准为 L0，供 L0 阶段布局安全调用。审计 21 pending 由 1 降至 0，扫描器、判据文档与台账三源一致为 0。定向安全集 29 条／0 红、默认冒烟 8/8、架构门禁 219/219、完整安全全量 3663 条／0 红（928.3 秒）；R836 遗漏的全量门禁已于本轮补齐，`last_full_safe_all_round=R837`。详见 `tasks_round/tasks_round_837_result.md`。

- R836 审计收口轮（覆盖率审计 21，**已验收**）：宠物增量自检的同步与后台进程分别收口到 `platform_tools.run_process`、`platform_tools.launch_background`，保留输出流、失败处理及可替换钩子。审计 21 pending 由 2 降至 1；定向安全集 26 条／0 红、默认冒烟 8/8、架构门禁 219/219；详见 `tasks_round/tasks_round_836_result.md`。

- R835 审计收口轮（覆盖率审计 21，**已验收**）：ffmpeg PNG 转码改由 `platform_tools.run_process` 统一执行，保留命令、输入输出、超时与失败语义。审计 21 pending 由 3 降至 2；定向安全集 23 条／0 红、默认冒烟 8/8、架构门禁 219/219；详见 `tasks_round/tasks_round_835_result.md`。

- R834 审计收口轮（覆盖率审计 21，**已验收**）：缩略图 worker 的后台启动收口到 `platform_tools.launch_background`，保留白名单环境、可替换启动钩子、静默流和无控制台策略。审计 21 pending 由 4 降至 3；定向安全集 28 条／0 红、默认冒烟 8/8、架构门禁 219/219；详见 `tasks_round/tasks_round_834_result.md`。

- R833 审计收口轮（覆盖率审计 21，**已验收**）：程序日志与程序自有回收清理的后台进程改由 `platform_tools.launch_background` 统一启动，保留静默、无控制台与启动失败语义。审计 21 pending 由 6 降至 4；缩略图进程因凭据隔离与可替换启动钩子保持待办。定向安全集 32 条／0 红、默认冒烟 8/8、架构门禁 219/219、完整安全全量 3663 条／0 红（924.0 秒）；`last_full_safe_all_round=R833`。详见 `tasks_round/tasks_round_833_result.md`。

- R832 审计收口轮（覆盖率审计 26，**已验收**）：无凭据 API 根地址探测改由 `platform_tools.probe_http_endpoint` 承担，保留状态码及失败提示；`api_endpoints` 不再直接建立网络连接。审计 26 pending 由 1 降至 0，三源数字均为 0。定向安全集 61 条／0 红、默认冒烟 8/8、架构门禁 219/219；详见 `tasks_round/tasks_round_832_result.md`。

- R831 结构治理轮（架构统一第 4 项正式读取收口，**已验收**）：分镜工作文件的并发稳定快照读取收口至 `file_cache.read_stable_json_snapshot`，仍在读取前后比较文件签名并拒绝写入中的半份内容；集中入口因而成为唯一的 JSON 解码位置。第 4 项 pending 由 1 降至 0，定稿基数仍为 35，第一批第 3、4 项均已收口。定向安全集 34 条／0 红、默认冒烟 8/8、架构门禁 219/219；详见 `tasks_round/tasks_round_831_result.md`。

- R830 结构治理轮（架构统一第 4 项正式读取收口，**已验收**）：剧本 manifest 由 L0 `agent.core.read` 统一读取，镜头编号重排分镜与阶段 JSONL 日志文本读取改经 `file_cache`；原子发布校验、编辑器输入、发布前验证与 JSONL 单行解码均确认非正式文件读取并保留审计理由。资产页补行改为首个 idle 后再计时 2 秒，避免慢机首帧与补行同帧批量插入。第 4 项 pending 由 9 降至 1，定稿基数仍为 35。定向安全集 101 条／0 红、默认冒烟 8/8、架构门禁 219/219、完整安全全量 3663 条／0 红（991.6 秒），`last_full_safe_all_round` 已回写 R830；详见 `tasks_round/tasks_round_830_result.md`。

- R829 审计校准轮（架构统一第 4 项视频提示词外部结果解析，**已验收**）：`video_prompt_results` 的三处 JSON 解码均用于外部 Agent 结果文本及其格式修复片段，不属于正式项目文件读取，均保留为具理由豁免；未改导入、格式修复或发布行为。第 4 项 pending 由 12 降至 9，定稿基数仍为 35。审计定向安全集 7 条／0 红、默认冒烟 8/8、架构门禁 219/219；R829−R827=2，未触发完整安全全量，`last_full_safe_all_round` 保持 R827。详见 `tasks_round/tasks_round_829_result.md`。

- R828 审计校准轮（架构统一第 4 项模型路由响应解析，**已验收**）：`model_pool.py` 的 HTTP 响应体与 SSE `data` 事件 JSON 解析经审计确认均非文件读取，保留为具理由豁免，未改模型调用或产品行为。第 4 项 pending 由 14 降至 12，定稿基数仍为 35。模型池与审计定向安全集 66 条／0 红、默认冒烟 8/8、架构门禁 219/219；R828−R827=1，未触发完整安全全量，`last_full_safe_all_round` 保持 R827。详见 `tasks_round/tasks_round_828_result.md`。

- R827 结构治理轮（架构统一第 4 项引擎验证台账读取，**已验收**）：引擎真机验证台账读取改由 `file_cache.read_json`；外部 CLI 标准输出的 JSON 解析经审计判定为非文件读取并豁免。资产页补行延迟由 1 秒调整为 2 秒，防止慢首帧消息循环提前插入第二批行，恢复“首帧仅 24 行”的性能契约。第 4 项 pending 由 16 降至 14，定稿基数仍为 35。定向安全集 30 条／0 红、资产专项 17 条／0 红、默认冒烟 8/8、完整安全全量 3,663 条／0 红／912.6 秒；全量基线推进至 R827。详见 `tasks_round/tasks_round_827_result.md`。

- R826 结构治理轮（架构统一第 4 项连贯性台账读取，**已验收**）：连贯性台账读取现统一经 `file_cache.read_json`；发布后复核的 JSON 往返复制改为标准深拷贝。`continuity_ledger` 因持久化读取职责由 L0 校准为 L1，未添加越层豁免。第 4 项 pending 由 18 降至 16，定稿基数仍为 35。定向安全集 27 条／0 红、默认冒烟 8/8、架构门禁 219/219；R826−R824=2，未触发完整安全全量，`last_full_safe_all_round` 保持 R824。详见 `tasks_round/tasks_round_826_result.md`。

- R825 结构治理轮（架构统一第 4 项缓存读取首批，**已验收**）：候选清单的 JSON 读取统一经 `file_cache.read_json`，JSONL 兼容输入则经 `file_cache.read_text` 后逐行解析；缩略图后台任务描述也统一经 `file_cache.read_json`。数据格式、候选筛选、JSONL 兼容与后台缩略图语义不变。第 4 项 pending 由 21 降至 18，定稿基数仍为 35。定向安全集 80 条／0 红、默认冒烟 8/8、架构门禁 219/219；R825−R824=1，未触发完整安全全量，`last_full_safe_all_round` 保持 R824。详见 `tasks_round/tasks_round_825_result.md`。

- R824 结构治理轮（架构统一第 3 项发布器全量接入收口，**已验收**）：项目接续索引与剧本 JSON 导入报告均改为 L2 仅接收发布器；独立 L3 `workflow_context_controller` 负责接续提示词索引发布，避免与 `writing_api` 形成循环，`stage_execution_service.import_writing_project()` 负责编排导入登记与报告发布。第 3 项 pending 清单已归零，原 66 条定稿基数和全量审计记录保留。定向安全集 68 条／0 红、完整安全全量 3,663 条／0 红／879.7 秒；全量基线推进至 R824。详见 `tasks_round/tasks_round_824_result.md`。

- R823 结构治理轮（架构统一第 3 项字幕与视频提示词发布边界，**已验收**）：字幕文本发布现必须由独立 L3 `subtitle_export_controller` 注入行尾校验发布器，避免引入静态循环；视频提示词草稿／成果发布及导入的读取、回滚、清理由 `stage_execution_service.video_prompt_gateway()` 注入。顺带收紧 R821 资产计划的桌面自动补全与分镜同步调用，均只经 L3 入口。本轮修正资产页建页时强制清空 Tcl 空闲队列导致的首帧补行／性能波动，保留映射和空闲回调的真实可视区盖图语义。第 3 项 pending 由 5 降至 2；默认冒烟 8/8、架构门禁 218/218、UI 定向 113 条／0 红、资产与性能定向 26 条／0 红、完整安全全量 3,662 条／0 红／907.7 秒；全量基线推进至 R823。详见 `tasks_round/tasks_round_823_result.md`。

- R822 结构治理轮（架构统一第 3 项设置与审计发布边界，**已验收**）：桌面偏好、HOLLMWOOD 四角色日志与旧目录归位记录现均必须接收 L3 发布器；设置值、日志内容／位置、归位目录和审计失败提示不变。第 3 项 pending 由 8 降至 5；默认冒烟 8/8、架构门禁 215/215、定向安全集 168 条／0 红、层级／循环导入门禁 6 条／0 红。R822−R820=2，未触发完整安全全量，`last_full_safe_all_round` 保持 R820。详见 `tasks_round/tasks_round_822_result.md`。

- R821 结构治理轮（架构统一第 3 项资产计划发布边界，**已验收**）：`asset_plan.publish_plan_bundle()`、`update_planned()` 与 `asset_resume.note_round()` 现必须接收 L3 注入的发布器；桌面、资产详情、批处理、引用导入与分镜采纳／定稿均只经 `stage_execution_service` 编排。资产格式、事务回滚及授权语义不变。第 3 项 pending 由 11 降至 8；默认冒烟 8/8、架构门禁 214/214、定向安全集 194 条／0 红。R821−R820=1，未触发完整安全全量，`last_full_safe_all_round` 保持 R820。详见 `tasks_round/tasks_round_821_result.md`。

- R820 性能与 UI 契约修复轮（**已验收**）：资产页首帧同步行数由 48 收窄至 24，仍保留三屏余量，避免首次绘制同时登记过多缩略图任务；余项继续分帧补齐。资产门禁改为断言首批渐进加载和可视区真实盖图，宠物“查看详情”门禁改为按统一 `BaseDialog` 的后代控件验证，业务显示与复制出口不变。性能专项 9 条／0 红、资产专项 17 条／0 红、宠物专项 560 条／0 红、默认冒烟 8/8、架构门禁 214/214、完整安全全量 3,657 条／0 红／918.0 秒；全量基线推进至 R820。详见 `tasks_round/tasks_round_820_result.md`。

- R819 功能轮（D 池规则承接第五阶段簇，**已验收**）：配音与字幕现只按需读取 AI 对白、时长预算、单说话人片段和画外音章节，时间线或来源缺失即拒绝 `audioManifest`；后期剪辑只按需读取节奏、切点、衔接与装配章节，逐段保留媒体及处置依据；质检交付只按需读取诊断、失败码、装配与种子/参考登记章节，未通过项留在 `qualityReport` 并拒绝标记交付。至此 D1 的 01—12 阶段定向引用均完成，D2 已随 R814B 完成；D3 保持显式推迟。定向引用门禁 9 条／0 红、SKILL 定向 149 条／0 红、注册表 73 且 `problems()==[]`、默认冒烟 8/8。详见 `tasks_round/tasks_round_819_result.md`。

- R818（已合并）：首帧管理、白模预演和视频生成已分别按需引用图像关键帧与光色、调度与风险预算、视频工具能力与失败诊断章节；首帧证据不完整、预演不可播放或超预算、视频生成没有可追溯任务状态均不能作为下游通过证据。该阶段簇的定向注入由 R818 提交承载，并已纳入 R819 的完成审计。

- R817 功能轮（D 池规则承接第三阶段簇，**已验收**）：资产管理现按需使用身份、schema、命名和图像模型一致性章节，拒绝不完整资产入正典；连贯性清单按需使用连续性轴、镜间状态与 F7／F19 诊断，未解冲突保留 `repairList`，不越权取得 D 锁。定向引用门禁 6 条／0 红、SKILL 定向 146 条／0 红、注册表 73 且 `problems()==[]`、默认冒烟 8/8。详见 `tasks_round/tasks_round_817_result.md`。

- R816 功能轮（D 池规则承接第二阶段簇，**已验收**）：初步分镜现按需读取调度、镜头职责与连续性几何，只作段缝风险预检；分镜定稿按需读取镜头职责、提示词转换、单主运镜、镜间连续性与状态账本，并成为 D 锁唯一放行点。每段缝须冻结五项状态，缺项或冲突即退回。定向引用门禁 4 条／0 红、SKILL 定向 144 条／0 红、注册表 73 且 `problems()==[]`、默认冒烟 8/8。详见 `tasks_round/tasks_round_816_result.md`。

- R814B 功能轮（SKILL 定向注入，**已验收**）：剧本准备／整理阶段现只按需引用 00 包的计划门控与镜头职责章节；情绪曲线采用来源的 12 节拍 0～10 模型与第 9 节拍 ≥9.5 峰值，未注入全文、风格库或示例库。新增定向引用门禁，SKILL 定向 142 条／0 红、注册表实测 73 且 `problems()==[]`、默认冒烟 8/8。R814C 通知统一已冻结为两个连续 stash，原 B1 DataTable stash 已顺延；详见 `tasks_round/tasks_round_814b_result.md`。

- R814A 结构治理轮（执行子场景，**已验收**）：执行页与“手动制作”精简窗改由 L4 `ui_widgets` 持有，L3 `stage_exec`／`stage_models` 仅通过注入 presenter 提供运行器、阶段数据和回调；因此两处 `L3 → ui_widgets(L4)` 反向 import 已消失，未登记任何越层台账。定向 UI 回归 30 条／0 红、默认冒烟 8/8；完整架构实测中 `test_layers` 两项均绿，余下 2 红均为 R815 完整安全全量挂账及其他在途 JSON 债，R814A 新红为 0。详见 `tasks_round/tasks_round_814a_result.md`。

- R815 修复轮（项目登记空壳启动崩溃，**已验收**）：无 `projects.json` 且延后旧版迁移时，`Projects` 现会规范化空登记为 `{'active': None, 'projects': []}`；初始化与后台迁移完成后的 `refresh_registry()` 均保留未知字段并补齐必需键。没有在桌面层吞错或改写真实用户登记。启动回归与项目登记专项 15 条／0 红、默认冒烟 8/8；架构门禁的 4 项红均为既有 R814／门禁债，R815 新红为 0。详见 `tasks_round/tasks_round_815_result.md`。

- R813 文档补正轮（**已验收**）：补全 R810 结果中 `8f2c24d` WIP 保留、AGENTS 门禁 +2 合法登记及候选路径断言未弱化的可审计说明；确认 R810 提交标题的历史预期数与实测 177/177 不一致，仅更正记录、不重写历史。详见 `tasks_round/tasks_round_813_result.md`。

- R812 结构治理轮（架构统一第 3 项首批，**已验收**）：`white_model_service.write_record()`、`asset_batch_settings_service.remove_model()`／`save_settings()` 的正式 JSON 发布均改为由 L3 注入；白模使用独立 `white_model_persistence_controller` 避免静态循环，资产批量设置使用 `stage_execution_service`。L4 入口仅委托 L3，读取、媒体复制、记录格式与失败语义不变。第 3 项 pending 由 14 降至 11；专项 69 条／0 红、默认冒烟 8/8、架构门禁 178/178。详见 `tasks_round/tasks_round_812_result.md`。

- R811 工程基础设施整理轮（**已验收**）：轮次史已入库，worktree 可取得 664 份 `tasks_round/*.md`；任务队列、原子租约认领器和轮次机械门禁已入库。T2 诊断确认注册表为 73，`.qwen` 悬挂包装链接是环境差异；T3 定位到 `tests/test_skills.py:1400–1401` 的候选路径断言。C 线 UI 路线图已校正，密钥流报告探针已脱敏，SKILL 映射草案待产品负责人裁定。详见 `tasks_round/tasks_round_811_result.md`。

- R810 结构治理轮（SKILL 流水线契约对齐，**已验收**）：对齐 12 阶段 pipeline 的输入、输出与上游依赖；对白润色迁至剧本结构、音画同步预检迁至后期剪辑，资产链为“自动补全→版权过滤”。新增注册 SKILL DAG 与 pipeline 阶段 IO／manifest 归属门禁。默认冒烟 8/8、架构冒烟 177/177、契约定向 198 条／0 红、注册表 73 且 `problems()==[]`；完整安全全量重跑 3,614 条／0 红／882.9 秒。详见 `tasks_round/tasks_round_810_result.md`。

- R809 结构治理轮（架构统一第 3 项定稿分镜退役别名发布，**已验收**）：`storyboard_lifecycle.retire()` 的别名 JSON 发布必须接收 L3 `storyboard_lifecycle_gateway()` 注入；定稿流程仍仅经控制器退役工作分镜。专项 117 条／0 红、默认冒烟 8/8、架构门禁 171/171；R810 已补齐完整安全全量。详见 `tasks_round/tasks_round_809_result.md`。

- R808 结构治理轮（架构统一第 3 项定稿分镜编辑发布，**已验收**）：`storyboard_edit_service.save_edited_json()` 现必须接收 L3 `storyboard_edit_gateway()` 注入的 JSON 发布器；定稿控制器只委托 `stage_execution_service.save_edited_stage_storyboard()`。JSON 路径校验、原子失败不覆写旧文件与返回路径语义不变。第 3 项 pending 由 16 降至 15，第 4 项仅重定位既存行号，数量保持 21；服务与控制器专项 14 条／0 红、架构与台账专项 17 条／0 红、默认冒烟 8/8、架构门禁 171/171（43.103 秒）。R808−R806=2，不触发完整安全全量。详见 `tasks_round/tasks_round_808_result.md`。

- R807 结构治理轮（架构统一第 3 项白模预演进度发布，**已验收**）：`previs_progress_service.publish()` 与 Blender 回调安装现必须接收 L3 `previs_progress_gateway()` 注入的原子文本发布器；宿主 `previs_progress` 兼容门面仍提供同名发布与安装入口，只委托 L3。进度 JSON 字段、真实帧数进度和缓存失效语义不变。第 3 项 pending 由 17 降至 16，第 4 项仅重定位既存行号，数量保持 21；白模预演专项 88 条／0 红、架构与台账专项 12 条／0 红、默认冒烟 8/8、架构门禁 171/171（42.486 秒）。R807−R806=1，不触发完整安全全量。详见 `tasks_round/tasks_round_807_result.md`。

- R806 结构治理轮（架构统一第 3 项宠物域第二批，**已验收**）：`pet_test_service.record()` 的增量自检账本发布现必须由 L3 `pet_test_gateway()` 注入；`pet_ui` 只经 `stage_handler_registry.start()` 启动并由 L3 轮询。重复次数、失败用例脱敏摘要与失败时不写账本的产品语义不变。第 3 项 pending 由 18 降至 17，第 4 项保持 21；专项 28 条／0 红、默认冒烟 8/8、架构门禁 171/171（43.009 秒）、强制完整安全全量 3,604 条／0 红／1,026.4 秒通过，`last_full_safe_all_round` 推进至 R806。详见 `tasks_round/tasks_round_806_result.md`。

- R805 结构治理轮（架构统一第 3 项宠物域首批，**已验收**）：`pet_performance_service.record()` 的优化账本发布现必须由 L3 `pet_performance_gateway()` 注入；`pet_ui` 只经 `stage_handler_registry.start()` 启动并由 L3 轮询离线基准。基准脚本、40% 阈值、仅保存摘要及失败不写账本的产品语义不变。第 3 项 pending 由 19 降至 18，第 4 项保持 21；专项 25 条／0 红、默认冒烟 8/8、架构门禁 171/171（42.940 秒）。R805−R803=2，不触发完整安全全量。详见 `tasks_round/tasks_round_805_result.md`。

- R804 修复轮（阶段配置页 SKILL 展示，**已验收**）：说明正文现在优先读取同目录 `README.md`（大小写无关，兼容 `readme.MD`），仅在 README 缺失时回退 `SKILL.md`；注册 SKILL 勾选框改为从实际文件名取值，只显示中文字符，去除路径、显示名及装饰符号。专项 140 条／0 红、默认冒烟 8/8、架构门禁 171/171 通过；距 R803 完整安全全量仅一轮，按三轮算式不重复跑全量。详见 `tasks_round/tasks_round_804_result.md`。

- R803 结构治理轮（架构统一第 3 项本地视频设置，**已验收**）：`local_video_settings_service.save_local_video_settings()` 的工作流复制、替换、配置发布和回滚字节发布现必须由 L3 `publish_local_video_settings()` 注入统一网关；本地视频设置窗口只调用该 L3 入口。设置预检、哈希命名、原子替换、回滚与既有路径语义不变。第 3 项 pending 由 20 降至 19，第 4 项保持 21。专项 5 条／0 红、性能专项 9 条／0 红、默认冒烟 8/8、架构门禁 171/171 通过；R803−R800=3 的完整安全全量 3597 条／0 红（1159.4 秒），全量基线已推进至 R803。详见 `tasks_round/tasks_round_803_result.md`。

- R802 结构治理轮（架构统一第 3 项交付域首批，**已验收**）：`delivery_import_service.import_final_master()` 的最终成片发布现必须由既有 L3 `import_delivery_master()` 注入统一二进制发布器；L2 不再保留 `shutil.copy2` 回退，缺少注入会明确拒绝。桌面入口继续只调用 L3，成片校验、路径、来源保留及错误结果语义不变。第 3 项 pending 由 21 降至 20，第 4 项保持 21。默认冒烟 8/8、交付专项 11 条／0 红、架构门禁 170/170 通过；R802−R800=2，未触发完整安全全量。详见 `tasks_round/tasks_round_802_result.md`。

- R801 结构治理轮（架构统一第 3 项资产域第三批，**已验收**）：`asset_generated_import_service.import_pending_generated()` 对自动导入临时 PNG 的发布现必须使用既有 L3 `asset_batch_gateway()` 注入；缺少网关会明确拒绝。自动扫描、PNG 转换、登记及错误回报语义不变。第 3 项 pending 由 22 降至 21，第 4 项保持 21。默认冒烟 8/8、自动导入专项 4 条／0 红、架构门禁 169/169 通过；R801−R800=1，未触发完整安全全量。详见 `tasks_round/tasks_round_801_result.md`。

- R800 结构治理轮（架构统一第 3 项资产域第二批，**已验收**）：`asset_detail_service._publish()` 的回滚字节发布现必须由 L3 `asset_detail_gateway()` 注入；资产详情页的正典板与状态变体绑定均只调用 L3 编排入口。图片、资产索引及失败后的双文件回滚语义不变。第 3 项 pending 由 23 降至 22；第 4 项保持 21，仅重定位三条既有 `stage_execution_service.py` 裸 JSON 读取行号。默认冒烟 8/8、详情专项 6 条／0 红、架构门禁 168/168、完整安全全量 3,591 条／0 红／958.6 秒通过；全量基线推进至 R800。详见 `tasks_round/tasks_round_800_result.md`。

- R799 结构治理轮（架构统一第 3 项资产域首批，**已验收**）：`asset_batch_state_service.save_ledger()` 的正式 JSON 发布现必须由 L3 `asset_batch_gateway()` 注入；L3 同时承接“核实后放开未知提交记录”的唯一入口，L4 仅作兼容委托。资产批次台账的数据格式、路径与恢复语义不变。第 3 项 pending 由 24 降至 23；第 4 项保持 21，仅随新增 L3 函数重定位三条既有裸 JSON 读取行号。默认冒烟 8/8、资产定向安全集 82 条／0 红、架构门禁 167/167 通过；R799−R797=2，未触发完整安全全量。详见 `tasks_round/tasks_round_799_result.md`。

- R798 验证基线轮（显式推迟待办登记，**已验收**）：仅在“已知阻塞与待办”登记会员订阅制（Mode A 软件授权）的既定决策、开工前置清单与两项服务器权威约束；未改产品代码、台账或路线图，未新增功能。本轮为文档轮，按 798−797=1 且无逻辑改动，不运行完整安全全量；默认冒烟 8/8、架构门禁不低于既有 166/166 后收尾。详见 `tasks_round/tasks_round_798_result.md`。

- R797 覆盖率审计契约轮（指令 15，**已验收**）：覆盖率审计 21、24、26 现以同一冻结扫描器驱动判据文档数字与台账 pending，并对每段建立双向集合相等、跨段 `(file:point)` 不相交的棘轮。`api_endpoints.py:47` 从进程段改由网络段 26 唯一登记；`model_pool.py:538`、`:566` 改为模型路由网络白名单豁免；审计 24 的 27 条固定字面量普通模块延迟加载均保留记录并改为具理由的 exempt，pending 27→0。三源当前一致：21=6、24=0、26=1。新增每三轮完整安全全量算式门禁；强制全量安全自检 3,587 条／0 红／955.4 秒通过，`last_full_safe_all_round` 推进至 R797。默认冒烟 8/8、架构门禁 166/166 通过。详见 `tasks_round/tasks_round_797_result.md`。

- R796 版本控制兼容轮（指令 14，**已验收**）：仓库根 `.gitignore` 逐项说明并排除用户项目／生成媒体、本机私有凭据、日志、运行数据、字节码、工作流任务、回收站、升级备份、`.bak_*` 与本机配置；新增架构断言确保必排除项缺失即红。`AGENTS.md` §7 与 `CLAUDE.md` 均记录“结果文件、基线与凭据扫描通过后每轮收尾提交”的纪律，成功使用 `RN:`、失败诊断仅使用 `RN-FAIL:`。保留历史 `升级备份/` 与 `.bak_*`，Git 承担后续回滚；`.git` 损坏或误提交密钥的人工处置说明见 `说明/版本控制处置说明.md`。定向门禁 10/10、默认冒烟 8/8、架构门禁 163/163 通过；全量按 796−795=1 未触发。详见 `tasks_round/tasks_round_796_result.md`。

- R795 性能/资源修复轮（R794 验收收尾，**已验收**）：资产表缩略图覆盖层将连续滚动重排合并为 250ms 防抖、复用已在可视区的图层并将首帧刷新绑定到 Treeview 首次映射，避免重列表逐帧解图及首次打开的空白缩略图；云气泡测试补齐“指针不在气泡上”的确定前置条件。同步修正轮次连续性、跳过台账与架构统一行号基数。默认冒烟 8/8、受影响冒烟 9/9、资产门禁 17/17、定向安全集 89 条／0 红、回归集 666 条／0 红、架构门禁 162/162、完整安全全量 3,583 条／0 红／956.8 秒通过；`test_perf_baseline` 9/9 通过，R794 的滚动性能阻断已关闭，全量基线推进至 R795。详见 `tasks_round/tasks_round_795_result.md`。

- R794 结构治理轮（架构统一第 3、4 项第六批，**已由 R795 完整复验关闭**）：`confirm_gates.py` 与 `previs_routing.py` 的四个正式 JSON 发布点现必须接收 L3 `stage_execution_service` 注入的发布器；桌面与白模预演页面仅委托 L3，数据格式、路径与授权语义不变。第 3 项 pending 由 28 降至 24，第 4 项保持 21；白模按钮截图发现的旧测试替身签名已补齐，专项回归 118 条／0 红，分镜整理的 L3 网关漏接也已定向修复。R794 的原始完整安全全量曾因 300 行滚动中位 151.4ms／167.0ms 高于 150ms 硬线而阻断；该阻断已由 R795 修复并完整复验关闭。详见 `tasks_round/tasks_round_794_result.md`。

- R793 结构治理轮（架构统一第 3、4 项第五批，**已验收**）：`storyboard_storage.py` 与 `video_lifecycle_service.py` 的六个正式发布点现必须接收 L3 `stage_execution_service` 网关；应用、分镜定稿和分镜整理只调用 L3 编排入口，缺少注入会明确拒绝。分镜资产／清单、视频删除索引、视频选项与白模上传记录的数据格式、路径结果、回滚及授权语义不变。第 3 项 pending 由 34 降至 28，第 4 项保持 21；仅重定位四条既存裸 JSON 读取行号。默认冒烟 8/8、受影响冒烟 9/9、定向安全集 40 条／0 红、补充边界门禁 5 条／0 红、架构门禁 159/159 通过；R793−R791=2，未触发完整安全全量，`last_full_safe_all_round` 保持 791。详见 `tasks_round/tasks_round_793_result.md`。

- R792 结构治理轮（架构统一第 3、4 项第四批，**已验收**）：`tts_api.py` 与 `cloud_video_service.py` 的正式配置、音频及标记发布均改为必须接收 L3 `stage_execution_service` 网关；缺少注入会明确拒绝，桌面、云视频设置和应用装配层只调用 L3 编排入口。音频、配置、工作区与工作室偏好的数据格式、路径结果和授权语义不变。第 3 项 pending 由 41 降至 34，第 4 项保持 21；同时仅重定位 `stage_execution_service.py` 三条既存裸 JSON 读取的行号，未改变其基数。默认冒烟 8/8、受影响冒烟 9/9、定向安全集 63 条／0 红、架构门禁 158/158 通过；R792−R791=1，未触发完整安全全量，`last_full_safe_all_round` 保持 791。详见 `tasks_round/tasks_round_792_result.md`。

- R791 结构治理轮（架构统一第 3、4 项第三批，**已验收**）：`asset_batch_service.py` 与 `asset_batch_lifecycle.py` 的正式读写均改为必须接收 L3 `asset_batch_gateway()`；缺少注入会明确拒绝，L4 仅负责装配。资产登记、导入、改名、删除、恢复及批次状态读写的用户数据格式、路径结果和授权语义不变。第 3 项 pending 由 50 降至 41，第 4 项保持 21。默认冒烟 8/8、受影响冒烟 9/9、定向安全集 48 条／0 红、架构门禁 156/156、完整安全全量 3,572 条／0 红／901.3 秒通过；全量基线推进至 R791。详见 `tasks_round/tasks_round_791_result.md`。

- R790 结构治理轮（架构统一第 3、4 项第二批，**已验收**）：`idea_chat.py` 的正式写入与 JSON 读取现必须接收 L3 `stage_execution_service.idea_chat_gateway()`；缺少注入会明确拒绝，桌面只负责装配，不改变聊天记录、简报、回收或授权语义。第 3 项 pending 由 56 降至 50，第 4 项由 24 降至 21。默认冒烟 8/8、受影响冒烟 9/9、定向安全集 81 条／0 红、架构门禁 156/156 通过；R790−R788=2，未触发完整安全全量。详见 `tasks_round/tasks_round_790_result.md`。

- R789 性能轮（基准趋势与阈值回归补强，**已验收**）：保持 `维护记录/基准历史.json` 作为启动／长列表／内存长跑的唯一归档，不改探针或产品代码；新增回归验证归档严格只保留 `MAX_HISTORY` 最近窗口，以及每条提交历史均含机器、项目登记名、冷／热、首帧和真实凭据条件。趋势仍只比较同条件最近五次成功样本的中位数。默认冒烟 8/8、启动／历史定向 16/16、架构门禁实测 156/156 通过；R789−R788=1，按 §5 不跑完整安全全量，`last_full_safe_all_round` 保持 788。详见 `tasks_round/tasks_round_789_result.md`。

- R788 UI 统一入口第三批第 15 项（阶段显示，**已验收**）：`desktop.PAGES` 的 12 个制作阶段页不再手写名称，现由 `pet_bus.STAGES` 与 `stage_name()`／`STAGE_NAMES` 生成；唯一的非阶段工具页“13 参考网站”保持独立。新增阶段显示边界防止桌面页表回退成硬编码名称。为维持跨平台剪贴板锁，Unix 专用 `fcntl` 仅在非 Windows 分支加载，且覆盖率动态导入门禁明确登记其为标准库平台豁免，不影响业务动态导入扫描范围。默认冒烟 8/8、受影响冒烟通过、架构门禁 154/154、完整安全全量 3,568 条／0 红／859.6 秒；全量基线推进至 R788。详见 `tasks_round/tasks_round_788_result.md`。

- R787 UI 统一入口第三批第 14 项（文案与复制，**已验收**）：`prompt_window.copy_text()` 成为文本写剪贴板的唯一入口，借助 `clipboard_lock` 保持跨进程互斥且支持同线程嵌套；聊天气泡选中与整条复制已首迁，失败会明确提示而非静默吞掉。`copy_preview()` 只用于状态回执并掩盖疑似凭据，复制原文不改写。默认冒烟 8/8、受影响冒烟 9/9、复制／锁／边界定向 19 条／0 红，另 `idea_chat` 安全回归通过；架构门禁 153/153。R787−R785=2，按 §5 不触发完整安全全量。详见 `tasks_round/tasks_round_787_result.md`。

- R786 UI 统一入口第三批第 13 项（滚动条，**已验收**）：`ui_theme.apply()` 现在是横、纵 `TScrollbar` 视觉和 active 反馈的唯一入口，所有颜色与边框值收口到 `ui_tokens.SCROLLBAR_*`；页面继续只建立标准 `ttk.Scrollbar`，未迁移或改动滚动容器的业务结构。默认冒烟 8/8、受影响冒烟 9/9、主题／清单定向 10 条／0 红、架构门禁 152/152。距 R785 全量仅 1 轮，按 §5 不触发完整安全全量。详见 `tasks_round/tasks_round_786_result.md`。

- R785 UI 统一入口第三批第 12 项（图标，**已验收**）：新增 L4 `ui_icons.IconLoader`，统一图标按 Tk 宿主与尺寸的缓存和构建；仅将视频页“返回生成方式”的既有手绘箭头首迁，文本、按钮命令和页面业务语义不变。新增首迁边界，禁止该页退回直接 `PhotoImage`。默认冒烟 8/8、受影响冒烟 9/9、图标与层级定向 7 条／0 红、架构门禁 151/151；完整安全全量 627 工作单元／0 红／871.373 秒，全量基线推进至 R785。详见 `tasks_round/tasks_round_785_result.md`。

- R784 UI 统一入口第二批第 11 项（Tooltip，**已验收**）：`ui_widgets.Tooltip` 统一短说明浮层的 400ms 延迟、鼠标悬停／键盘焦点触发、离开／失焦／控件销毁清理，且不取得 grab 或焦点。仅将 `skill_panel.Panel.add_skill_control()` 中被截断 SKILL 名称的手写 `Toplevel` 提示首迁，完整名称与布局语义不变；其他悬停效果留待独立批次。默认冒烟 8/8、受影响冒烟 9/9、Tooltip 单元与边界 5 条／0 红、架构清单一致性 10 条／0 红、架构门禁 150/150、完整安全全量 3,556 条／0 红；全量基线推进至 R784。详见 `tasks_round/tasks_round_784_result.md`。

- R783 UI 统一入口第二批第 10 项（快捷键，**已验收**）：新增 L4 `ui_shortcuts.ShortcutRegistry`，以作用域、语义名称与 Tk 序列集中登记，拒绝同作用域不同语义的重复快捷键；同一语义在页面重建时替换旧控件登记，重复调用幂等。仅将剧本准备聊天气泡 Ctrl+C 首迁，原两种大小写序列与复制行为不变。默认冒烟 8/8、受影响冒烟 9/9、定向 UI 边界 117 条／0 红、架构门禁 149/149、完整安全全量 3,551 条／0 红／878.1 秒；全量基线推进至 R783。详见 `tasks_round/tasks_round_783_result.md`。

- R782 UI 统一入口第二批第 9 项（文件／目录选择，**已验收**）：新增 L4 `ui_dialogs.FileDialog`，统一选择、取消的空元组结果与打开失败的既有通知链反馈；仅将 `Desktop.choose_idea_attachments()` 首迁，附档后台入库、禁用发送按钮和状态提示的业务语义不变。新增分层登记和首迁边界门禁，禁止该页退回直接 `filedialog`。默认冒烟 8/8、受影响冒烟 9/9、定向 79 条／0 红、架构门禁 148/148；首次全量仅性能抖动红，复测通过后重跑完整安全全量 3,546 条／0 红／878.9 秒，全量基线推进至 R782。详见 `tasks_round/tasks_round_782_result.md`。

- R781 UI 统一入口第二批第 8 项（右键菜单，**已验收**）：`ui_widgets.ContextMenu` 统一菜单项声明、`tk_popup` 定位和 grab 释放；仅将 `Desktop.open_bubble_menu()` 的聊天气泡右键菜单首迁，复制、删除、恢复等领域回调与返回 `break` 语义不变。新增架构门禁，禁止这个首迁页退回裸 `tk.Menu`；其余历史右键菜单留待独立批次。默认冒烟 8/8、受影响冒烟 9/9、定向 82 条／0 红、架构门禁 147/147；R781−R779=2，未触发完整安全全量。详见 `tasks_round/tasks_round_781_result.md`。

- R780 UI 统一入口第二批第 7 项（忙碌／加载态，**已验收**）：`ui_widgets.BusyState` 统一主后台任务的状态栏、进度条和可选控件恢复；仅将 `Desktop.async_()` 与 `_tick_async_result()` 首迁，线程、队列、取消和自动任务的既有编排语义不变。默认冒烟 8/8、受影响冒烟 9/9、定向 31 条／0 红、架构门禁 146/146；R780−R779=1，未触发完整安全全量。详见 `tasks_round/tasks_round_780_result.md`。

- R779 UI 统一入口第二批第 6 项（通知，**已验收**）：`ui_widgets.NotificationDispatcher` 统一状态栏优先、按级别和按需模态的通知投递；仅将 `Desktop.safe()` 的全局未处理操作错误首迁，诊断记录仍先执行，错误保持既有“状态栏＋操作提示”可见行为。其他历史 `status.set`／`messagebox` 不批量迁移，留待后续页面批次。默认冒烟 8/8、受影响冒烟 9/9、定向 31 条／0 红、架构门禁 146/146、完整安全全量 3,540 条／0 红／885.2 秒；全量基线推进至 R779。详见 `tasks_round/tasks_round_779_result.md`。

- R778 UI 统一入口第一批第 3 项（输入框，**已验收**）：`ui_widgets.LineInput`／`TextArea` 统一承载占位提示、只读态、错误态及输入视觉；仅将“填写创作信息”表单的紧凑与详细创意字段首迁至 `TextArea`，保留既有 `Text.get('1.0', 'end-1c')` 取值、字段采集和提交业务语义，其他历史 `Entry`／`Text` 留待独立批次迁移。新增表单输入边界门禁，阻止该首迁页退回裸 `tk.Text`。默认冒烟 8/8、受影响冒烟 9/9、定向 10 条／0 红、架构门禁 145/145、完整安全全量 3,536 条／0 红／878.9 秒；全量基线推进至 R778。详见 `tasks_round/tasks_round_778_result.md`。

- R777 UI 统一入口第一批第 2 项（表格，**已验收**）：`ui_widgets.DataTable` 统一承载列定义、滚动条、空态、选择回调和通用排序，并复用既有样式与表格 token；仅将 `storyboard_table_ui.file_table()` 的剧本／分镜文件选择表首迁，原有勾选列、全选、行高适配与回调语义不变，其他历史 `Treeview` 留待分批迁移。首个全量验收发现表格壳被误计为额外 Card（2→4），已改为中性容器并由定向 144 条与重跑全量确认。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 144/144、完整安全全量 3,533 条／0 红／866.2 秒；全量基线推进至 R777。详见 `tasks_round/tasks_round_777_result.md`。

- R776 性能轮（基准趋势与阈值回归，**已验收**）：`维护记录/基准历史.json` 成为启动／长列表／内存长跑的唯一滚动归档（最多保留 30 份）；记录从 `程序/projects.json` 获取活动项目名和登记来源，绝不硬编码项目路径。趋势门禁只以同一冷/热缓存、首帧、凭据条件和行数的最近五次成功样本中位数比较；三族指标与启动性能断言共用 `tests/performance_contract.py` 的常量。默认冒烟 8/8、启动／历史定向 15/15、架构门禁不低于基线、完整安全全量 4,931 条／0 红／856.5 秒通过；全量基线推进至 R776。详见 `tasks_round/tasks_round_776_result.md`。

- R775 契约轮（skip 卫生门禁，**定向验收通过／完整安全全量受性能基线阻断**）：新增 `tests/skip_reasons.py` 作为跳过原因的唯一常量表；29 个测试模块的 208 处 skip 已机械迁为受控常量，分别为平台限制 205、缺外部程序 1、需实机复验 2，均含“为什么＋何时恢复”。`test_skip_hygiene` 以 AST 扫描源码并与 `维护记录/skip台账.json` 双向相等校验，拒绝空理由、行内注释、未知原因和失效的“待修复缺陷”引用；本轮待修复缺陷类为 0。默认冒烟 8/8、skip 定向 3/3、架构门禁 143/143 通过。因 R775−R769=6 强制运行完整安全全量，最终 3,526 条中仅 `test_perf_baseline` 的 300 行滚动中位 163.9ms 超过 150ms 红线，故 `last_full_safe_all_round` 保持 R769。详见 `tasks_round/tasks_round_775_result.md`。

- R774 修复轮（`app.py` 网关名称补全，**定向验证通过／完整安全全量受性能基线阻断**）：`import_json()` 已在使用处导入 `stage_execution_service.project_registry_gateway`，解除 R771 遗留的未定义名称静态错误；静态检查与默认冒烟均通过。完整安全全量随后仅剩环境滚动性能基线红项，未推进基线。详见 `tasks_round/tasks_round_774_result.md`。

- R773 可靠性轮（静默失败可见化，**实现与定向验收通过／完整安全全量受既有问题阻断**）：新增 L1 `diagnostic_capture`，只在程序 `logs/` 的固定白名单内记录脱敏的降级异常、启动壳耗时、最近门禁结果和未处理 Tk 崩溃；崩溃仍合并写入既有 `启动错误.log`。项目首页新增唯一“导出诊断包…”动作，导出前列明包含路径，ZIP 对凭据逐行脱敏并拒绝受保护文件，绝不遍历项目目录。新增回归覆盖假凭据不外泄、无 Tk/销毁场景、既有错误日志合并与零递归扫描。默认冒烟 8/8、最终诊断／门禁／层级回归 29/29、诊断/密钥/层级定向 13 条／0 红、架构门禁 140/140；最终完整安全全量 3,523 条中有两项既有红项：R771 的 `app.py:import_json` 未定义 `project_registry_gateway`，以及 `test_perf_baseline` 的环境测量 176.8ms 超过 150ms 灾难线，故 `last_full_safe_all_round` 保持 R769。详见 `tasks_round/tasks_round_773_result.md`。

- R772 修复轮（Toplevel Map grab 输入锁，**自动回归通过／完整安全全量待 R771 静态错误解除／待实机复验**）：根因是 `ui_theme` 的 Toplevel `<Map>` 绑定会收到子 Label／Frame／Button 映射事件，并错误对该子控件 `grab_set()`，可造成页面不可点或透明窗口持锁。现仅接受 `event.widget is window`；窗口 withdraw 时释放 grab；定位失败恢复不透明、释放 grab，并经 Desktop 既有状态栏提示。`BaseDialog.close()` 不再以当前 grab 必须等于自身为前提。R1–R5、默认冒烟 8/8、受影响冒烟 9/9、定向安全集 593 条／0 红、架构门禁 140/140 均通过；完整安全全量 3,518 条仅被 R771 `app.py` 未定义 `project_registry_gateway` 的既有静态错误阻断，未更新全量基线。须真机重启确认主页面可点击、选择项目窗按钮一次生效、× 一次可关。详见 `tasks_round/tasks_round_772_result.md`。

- R771 结构治理轮（架构统一第一批第 3 项首轮，**已验收**）：按用户授权的单模块例外，仅迁移 `projects.py`。L2 `Projects` 不再直接读写、复制或回滚项目文件；必须接收 L3 `stage_execution_service.project_registry_gateway()`，缺少注入即明确拒绝。桌面、项目导入入口仅装配网关；项目路径、登记字段、授权和事务回滚语义不变。第 3 项 pending 由 66 降至 56；第 4 项保持 24。默认冒烟 8/8、受影响冒烟 9/9、项目／棘轮定向 4 条／0 红、架构门禁 140/140；R771−R769=2，未触发完整安全全量。详见 `tasks_round/tasks_round_771_result.md`。

- R770 修复轮（回收站恢复入口补全，**实现与定向验证通过，完整验收受外部工作区文件阻塞**）：兑现“移入回收站后可恢复”的既有承诺：`recycle_recovery_service` 仅投影既有 `恢复位置.json` 并复用唯一的 `restore_recycle_batch()`；控制器汇总项目内与项目库两个回收站；项目首页、项目选择窗和项目右键均可打开“恢复回收站内容…”，支持整批或单条恢复，目标冲突／越界批次均零移动。默认冒烟 8/8、受影响冒烟 9/9、回收／存储定向 26 条／0 红、架构冒烟 139/139 通过；完整安全全量 3,511 条中仅 `architecture.test_layers` 因既有未追踪 `_diag_winprobe.py` 未在层级表登记而红，未推进全量基线。详见 `tasks_round/tasks_round_770_result.md`。

- R769 功能轮（UI 统一入口第一批第 1 项：弹窗，**已验收**）：`ui_widgets` 新增 `BaseDialog`、`FormDialog`、`ConfirmDialog`；只将“填写创作信息”迁至 `FormDialog`，字段采集、统筹锁与提交语义不变，其他历史 `Toplevel`／`messagebox` 未迁移。统一组件处理模态、Esc、首个可交互控件焦点、销毁时释放 grab 与危险确认样式；新增弹窗边界棘轮使历史裸 `Toplevel` 数量只能下降。默认冒烟 8/8、受影响冒烟 9/9、定向安全自检 12 条／0 红、架构门禁 139/139、完整安全全量 3,504 条／0 红；架构基线 138→139，全量基线推进至 R769。详见 `tasks_round/tasks_round_769_result.md`。
- R768 验证基线轮（UI 统一入口路线图登记与优先级置顶，**已验收**）：已将桌面路线图的三栏结构校正后登记为仓内 `维护记录/UI统一入口路线图_v1.md`，并明确该文件只定义权威、审计点与完成判据，进度只记本台账。`ui_widgets`／`ui_tokens` 已补入权威源表；第一批“弹窗→表格→输入框”已置于缺陷反馈链之前。默认冒烟 8/8、架构门禁 138/138；文档轮不触发完整安全全量。详见 `tasks_round/tasks_round_768_result.md`。
- R767 可靠性／数据迁移轮（Git 初始化与提交门禁，**已提交**）：用户明确授权“可以入库”后，已创建首次提交（`chore: 初始化版本控制，排除用户数据与密钥`，哈希记于本轮结果文件）；`.gitignore` 现排除用户项目、私有配置、日志、缓存、维护记录、任务轨迹、回收站／升级备份、运行环境与临时备份，以及运行态 `程序/data/` 与本地诊断脚本。提交前安全路径复核为 0；未执行推送。`AGENTS.md` 的 2.6 Git 提交门禁继续生效；详见 `tasks_round/tasks_round_767_result.md`。
- R766 性能轮（启动路径探针与递归扫描收口，**已验收**）：用同条件临时项目分别运行旧递归策略与本轮策略；首次选择项目页出现为 0.3999→0.3807 秒、选择后到剧本准备为 0.4438→0.3885 秒；当天自动续开为 0.5410→0.8152 秒，仍在 1.0 秒契约内，故未将一次样本波动宣传为“整体变快”。启动至剧本准备可见壳的递归扫描计数现为 0；固定层级的剧本、创意和 SKILL 发现不再递归扫描。真实登记表只读核验显示改名项目的活路径引用已同步，且无失效登记，故认领扫描未被触发。默认冒烟 8/8、受影响冒烟 9/9、启动性能安全自检 10 条／0 红、架构门禁 138/138；R766−R765=1，未触发完整安全全量。详见 `tasks_round/tasks_round_766_result.md`。
- R765 修复轮（启动 tick 解冻＋聊天键盘导航，**已验收**）：回归先证实剧本准备页的 40ms 延后建页在用户切页后走守卫返回时，会让 `_startup_tick_paused` 永久保持真、创意历史结果无法消费；守卫返回前现调用既有幂等解冻入口。聊天只读记录区不再吞掉方向、翻页、Home/End 与 Tab/Shift+Tab，普通字符仍被拦截，编辑气泡边界保护不变。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量通过；全量基线推进至 R765。详见 `tasks_round/tasks_round_765_result.md`。
- R745 修复轮（UI 异常反馈首批，**已验收**）：已定位并修复关闭窗口后 Tcl 队列残留回调这一根因；`pet_ui` 将销毁竞态收窄至 `TclError`，异步回调均可取消，SKILL 面板的生产模型读取失败改为可见提示，桌面资产续跑清理失败亦有状态反馈。默认冒烟 8/8、受影响冒烟通过、安全定向 0 红、架构门禁通过、完整安全全量 602 工作单元／0 红／854.7 秒；全量基线推进至 R745。详见 `tasks_round/tasks_round_745_result.md`。
- R746 修复轮（阶段事件可靠性，**已验收**）：`desktop` 不再吞掉剧本、结构剧本及首帧自动链的阶段失败／执行／完成事件异常；权威总线不可用会显式上抛，不会把自动链留在假进度。新增总线故障回归；默认冒烟 8/8、受影响定向与架构门禁通过。距 R745 完整安全全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_746_result.md`。
- R747 只读诊断轮（启动停留项目页，**待实机证据**）：实际设置／登记表满足当天自动续开的全部静态前置条件，代码与现有 Tk 回归均显示应在首帧后进入剧本准备；本环境无法取得已运行 Tk 窗口，未把“无法复现”误判成修复或随意改启动链。详见 `tasks_round/tasks_round_747_result.md`。
- R748 修复轮（主界面幽灵登记，**已验收**）：主界面右键现在在目录不存在时提供与项目选择弹窗一致的“只清除失效项目登记”，不会再进入回收流程并误报占用。新增回归、默认冒烟 8/8、完整安全全量 603 工作单元／0 红／869.518 秒通过；全量基线推进至 R748。详见 `tasks_round/tasks_round_748_result.md`。
- R749 修复轮（自动门禁失败反馈，**已验收**）：自动采用待办写资产／确认账本失败不再被内部 `continue` 吞没；异常交给既有 20 秒节流器，状态会显示失败原因与自动重试说明。新增两条无 Tk 回归；默认冒烟 8/8、受影响桌面冒烟与直接回归通过，架构门禁 138/138。距 R748 完整安全全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_749_result.md`。
- R750 修复轮（幽灵登记清理失败反馈，**已验收**）：项目选择弹窗和主界面共用失效登记清理；注册表写入失败会展示原因并允许稍后重试，且不会刷新列表或假报已清理。新增无 Tk 回归；默认冒烟 8/8、受影响桌面冒烟 9/9、架构门禁 138/138。距 R748 完整安全全量仅 2 轮，未触发全量。详见 `tasks_round/tasks_round_750_result.md`。
- R751 修复轮（阶段报告链异常传播，**已验收**）：`desktop.pet_report()` 与 `pet_ui.report_done()` 不再把报告器故障压成 `None`；权威事件失败继续上抛，调用方不会再显示假进度。新增无 Tk 故障传播回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量 3,482 条／0 红／827.2 秒通过；全量基线推进至 R751。详见 `tasks_round/tasks_round_751_result.md`。
- R752 修复轮（对话动作失败反馈，**已验收**）：云朵对话的已放行动作失败不再只记内部错误并返回空串；原生与替换宿主均向用户显示脱敏的可行动重试提示。新增两条故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量 3,484 条／0 红／807.9 秒通过；全量基线推进至 R752。详见 `tasks_round/tasks_round_752_result.md`。
- R753 修复轮（缩略图空白状态反馈，**已验收**）：已绑定图片在缩略图暂不可用时不再被误报“缺图／还没绑定”，而会显示可解释状态并保留重新选择图片的既有入口；真正缺图语义不变。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、定向安全自检 48 条／0 红、架构门禁 138/138。距 R752 完整安全全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_753_result.md`。
- R754 只读诊断轮（CellHover 销毁与悬停回调，**已完成**）：逐项核对历史聚集的 8 处异常路径，均为已销毁控件／已删除行的受控 Tk 容错；编辑保存失败走 `on_error`，未发现可复现的业务静默或残留回调，故未伪修。`tests/test_cell_menu.py` 39 条／0 红。详见 `tasks_round/tasks_round_754_result.md`。
- R755 修复轮（确认窗口故障失败安全，**已验收**）：`stage_models.plan()` 不再把确认窗口异常误当成用户选择“直接执行”；现在停止动作并给出可行动状态提示。故障注入回归证明旧逻辑会返回 `'run'`、修复后返回 `None`；手动计划／门禁 44 条、默认冒烟 8/8、完整安全全量 3,485 条／820.6 秒／0 红通过；全量基线推进至 R755。详见 `tasks_round/tasks_round_755_result.md`。
- R756 修复轮（阶段配置打开失败反馈，**已验收**）：阶段配置面板注册／展示异常不再静默吞掉，按钮点击会显示可行动的稍后重试提示。新增注册表故障注入回归；手动计划／门禁 45 条、默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R755 全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_756_result.md`。
- R757 修复轮（项目打开后维护失败反馈，**已验收**）：重复原始取回图的可选清理若遇文件／回收站错误，不再静默伪装成没有待清理项；项目照常打开且状态提示可重试。新增文件系统故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R755 全量仅 2 轮，未触发全量。详见 `tasks_round/tasks_round_757_result.md`。
- R758 修复轮（阶段目录补齐失败反馈，**已验收**）：按需补齐阶段目录遇文件系统错误时，不再静默返回空列表并留下陈旧页面状态；项目仍可使用，状态会说明“阶段目录未补齐”及稍后重试。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量 3,487 条／0 红／840.3 秒通过；全量基线推进至 R758。详见 `tasks_round/tasks_round_758_result.md`。
- R759 修复轮（旧目录归位失败反馈，**已验收**）：旧目录向阶段树归位的目录联接失败不再静默返回空结果；项目照常可用，状态会说明“旧目录未归入新架构”及稍后重试。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R758 全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_759_result.md`。
- R760 修复轮（生成资产自动导入失败反馈，**已验收**）：项目加载后的生成资产检查读取失败、或发现待导入图片后后台任务排队失败，均不再静默伪装为无待办；项目照常可用，状态会给出可行动原因。新增两条故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R758 全量仅 2 轮，未触发全量。详见 `tasks_round/tasks_round_760_result.md`。
- R761 修复轮（资产续跑恢复失败反馈，**已验收**）：项目打开时读取自动补资产续跑台账失败，不再静默降级为“没有待续跑任务”；项目仍照常打开，状态会说明续跑记录未恢复并可稍后重试。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量 3,491 条／0 红／853.7 秒通过；全量基线推进至 R761。详见 `tasks_round/tasks_round_761_result.md`。
- R762 修复轮（项目模型同步失败反馈，**已验收**）：启动后项目模型对账的受控文件／数据错误不再吞成空结果；工作线程只回传错误，主线程状态栏提示“项目模型同步未完成”，项目照常打开。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R761 全量仅 1 轮，未触发全量。详见 `tasks_round/tasks_round_762_result.md`。
- R763 修复轮（创意历史发现失败反馈，**已验收**）：首屏后台发现创意历史的受控文件／数据错误不再吞成“没有示例”；错误随队列回到主线程，状态栏提示“创意历史未加载”，输入框与项目打开均不受阻。新增故障注入回归；默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138 通过。距 R761 全量仅 2 轮，未触发全量。详见 `tasks_round/tasks_round_763_result.md`。
- R764 修复轮（旧目录审计记录＋资产首帧性能，**已验收**）：旧目录归位虽完成但审计记录写入失败时，不再静默伪装为可追溯；状态栏会提示“旧目录归位记录未写入”及稍后重试。完整安全全量实测还定位到资产页首帧 `update()` 会连锁跑完 300 行补行回调，现先显示 48 行并在首帧后渐进补齐；新增故障注入与首帧行数回归。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 138/138、完整安全全量 3,495 条／0 红／845.2 秒通过；全量基线推进至 R764。详见 `tasks_round/tasks_round_764_result.md`。

- R743 契约轮（22／24／25／26 分阶段入账，**部分验收**）：报告扫描器与金丝雀固定范围／白名单；24 入账 27 条裸动态导入 pending，26 入账 1 条模型路由外调用 pending，并由真实命中子集断言守卫。22／25 无命中且未写零基数段落。默认冒烟 8/8、聚焦棘轮 2/0 红；架构冒烟摘要未保留，下一轮需复跑后才可完全验收。详见 `tasks_round/tasks_round_743_result.md`。
- R742 只读诊断轮（覆盖率审计 19–27 判据，**已完成，未入账**）：确认宽口径扫描含大量权威／基建噪声，窄口径零结果不可信，故未向基数台账写入虚假分母，也未修改产品代码或路线图。已形成三元判据、三档实测、候选语义裁定清单、归并映射与金丝雀方案；密钥项须在下一契约轮做 source→sink 追踪，若确认流入日志、任务 JSON 或 prompt 立即单开 `[SECURITY]` 修复轮。**待办：覆盖率审计：判据已定稿，待契约轮入账。**详见 `维护记录/覆盖率审计判据_20261001.md` 与 `tasks_round/tasks_round_742_result.md`。
- R741 契约轮（层级补登与越层豁免基数，**已验收**）：固定顶层运行期扫描范围实际为 210 个模块，均已登记至 L0–L5 或显式外围工具白名单；`broadcaster`、`asset_thumbs`、`projects` 与 13 个此前漏登 service 均已按实际职责／依赖补登。层级门禁不再跳过未登记源模块；38 项既存越层逐项登记为可定位豁免，新增越层或删台账未修源码都会失败。第 3 项 L2 写入棘轮由旧 37 重算为 66，新增 29 项来自补登后首次进入 L2 扫描的模块。默认冒烟 8/8、架构门禁通过、聚焦测试 0 红、完整安全全量 3,470 条／0 红／869.0 秒；全量基线已推进至 R741。详见 `tasks_round/tasks_round_741_result.md`。
- R740 功能轮（项目目录改名后的自动认领与登记同步，**定向验收通过，全量凭据待补**）：项目库仅一级扫描，以旧配置路径指纹优先认领改名目录；多候选必须人工确认，回收站永不扫描。认领以原子写入回滚同步登记与活路径，历史记录不改写；项目选择窗新增“重新查找项目”，已不存在的普通目录可只清登记。新增六场景临时目录回归，唯一认领／多候选／新登记／回收站排除／回滚／非递归均通过；默认冒烟 8/8、受影响冒烟 9/9、架构门禁未低于 134/134。R740−R735=5，故全量安全门槛已触发；本轮尝试的全量运行未留下成功台账，下一轮先复跑并归档汇总。详见 `tasks_round/tasks_round_740_result.md`。
- R737 只读诊断轮（同日自动续开实机阻塞，**已登记**）：用户在 R736 两次修复后复验仍停在“我的项目／正在载入今日项目”；R736 的自动化绿灯不足以证明真实启动路径已恢复。详见 `tasks_round/tasks_round_737_result.md`。
- R738 只读根因诊断（同日自动续开实机阻塞，**已确认**）：项目日选记录、项目登记和正式启动器均正确，`open_studio()` 仅 0.005 秒；实际项目路径探针显示 `show_loaded_project()` 已在 80ms 后进入 `show(0)`，但 `show(0)` 同步构建剧本准备页占 Tk 主线程 490.6ms，令窗口持续显示旧项目页。下一轮只可拆分首屏建页并做正式启动器实机复验；详见 `tasks_round/tasks_round_738_result.md`。
- R739 修复轮（同日自动续开首屏壳，**代码级已验收**）：自动续开先展示“剧本准备”可见壳，完整 `writing()` 建页改由 40ms 后回调执行；项目恢复与启动心跳亦后移，关闭时取消待建页回调。定向 130/130、默认冒烟 8/8 通过；正式启动器的用户实机复验仍待完成。详见 `tasks_round/tasks_round_739_result.md`。
- R736 修复轮（当天项目选择记忆与首屏卡顿，**代码级验证通过，实机未收口**）：侧栏／项目首页打开、新建和导入项目成功后，统一写入当天项目选择；同日自动续开先显示“01 剧本准备”，再延后资产导入、清理与恢复。定向 130 条/0 红、默认冒烟 8/8；但用户实机复验仍失败，不能标记为问题关闭；详见 `tasks_round/tasks_round_736_result.md`。
- R735 契约轮（架构统一棘轮可信度与门禁清单纪律，**已验收**）：第 3 项由原单文件扫描的 1 个模块重判为 L2 登记表全部实际源码 AST 扫描的 37 个 pending 正式发布分支；第 4 项由固定源集合扫描，66 个实际 `json.loads` 命中均逐项登记；删除／回收权威、一次性迁移与独立工具等 42 项有理由豁免，真实 pending 为 24。台账不再决定扫描范围；每项的处置状态、原因及可定位性均由棘轮校验。AGENTS 架构门禁清单现与实际 `tests/architecture/test_*.py` 严格相等。默认冒烟 8/8、架构门禁 134/134、定向 14 条/0 红、完整安全全量 246 文件／600 工作单元／0 红；详见 `tasks_round/tasks_round_735_result.md`。
- R733 契约轮（架构统一第一批第 3、4 项基数，**已验收**）：以 AST/正则棘轮把 L2 正式发布回退定为 1 个模块、裸 JSON 解析定为 63 个读点/36 个文件；新增债务、已迁移残留台账项和基数不符都会被架构门禁拦截。默认冒烟 8/8、架构门禁 132/132、定向 2 条/0 红；按 R732 分档未跑完整安全全量，距 R731 全量 2 轮。详见 `tasks_round/tasks_round_733_result.md`。
- R734 契约轮（架构统一第一批第 1、2 项冻结，**已验收**）：第 1 项仅保留交付导入与首帧生命周期两个 ServiceResult 试点，其余 35 个 L2 模块豁免；第 2 项仅保留交付导入的 ProjectContext 试点，其余 36 个 L2 模块豁免。两项在第 3、4 项基数清空前暂停；新增 L2 范围采用方棘轮。默认冒烟 8/8、架构门禁 133/133、定向 12 条/0 红；按用户指定分档未跑完整安全全量。详见 `tasks_round/tasks_round_734_result.md`。
- R732 验证基线轮（**已验收**）：统一 `AGENTS.md` 的风险分档与 §5 规则表：完整安全全量仅在每满 3 轮、路线图条目收口、发布前或用户明确要求时执行，跨层契约漂移仍由每轮架构门禁拦截；启动路径、Tk 生命周期/绑定、删除语义与层级登记表改动当轮升级全量。默认冒烟 8/8、架构门禁 130/130、`agents_md`／`round_baselines` 定向 11 条/0 红；文档轮按新规则未跑全量，距 R731 全量 1 轮。详见 `tasks_round/tasks_round_732_result.md`。
- R731 结构治理轮（执行，架构模块接口统一第一批第 3 项第八批，**已验收**）：首帧删除、恢复、替换的 `episode.json` 状态发布均由 L2 `keyframe_lifecycle_service` 接收 L3 注入发布器；`stage_execution_service` 统一编排图片和索引的原子发布，桌面仅调用 L3。镜头校验、回收与索引失败回滚语义不变。专项 11 条、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 129/129、完整安全全量 3,455 条/0 红/840.9 秒；详见 `tasks_round/tasks_round_731_result.md`。
- R730 结构治理轮（执行，架构模块接口统一第一批第 3 项第七批，**已验收**）：剧本准备的模型下载与手动创意由 L2 `idea_chat` 只组织分类成果描述，`stage_execution_service.publish_idea_creative()` 统一定位剧本阶段并原子发布；桌面仅注入该 L3 发布器，三类分类空目录语义不变。专项 73 条、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 128/128、完整安全全量 3,453 条/0 红/783.4 秒；详见 `tasks_round/tasks_round_730_result.md`。

- R729 结构治理轮（执行，架构模块接口统一第一批第 3 项第六批，**已验收**）：剧本准备工作区由 L2 `writing.prepare()` 仅组织任务书、模板、SKILL 位置和附档的成果描述，`stage_execution_service.publish_writing_preparation()` 统一定位剧本阶段并原子发布整包；入口仅注入该 L3 发布器。专项 112 条（1 跳过）、受影响冒烟 0 红、默认冒烟 8/8、架构门禁 128/128、完整安全全量 3,452 条/0 红/758.7 秒；详见 `tasks_round/tasks_round_729_result.md`。

- R728 结构治理轮（执行，架构模块接口统一第一批第 3 项第五批，**已验收**）：剪映交接包由 L2 仅组织文件描述，`stage_execution_service.publish_handoff_bundle()` 负责统一字节发布、自动包目录切换及旧自动包回收；桌面仅向 L2 注入该 L3 发布器。专项 8/8、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 127/127、完整安全全量 3,450 条/0 红/759.1 秒；详见 `tasks_round/tasks_round_728_result.md`。

- R727 结构治理轮（执行，架构模块接口统一第一批第 3 项第四批，**已验收**）：剪辑优化清单由 `stage_execution_service.save_stage_editing_checklist()` 注入统一文本发布器；L2 不再直写，桌面仅调用 L3。用户将清单清空的既有语义由 L3 明确授权，其他阶段成果仍默认拒绝空正文。专项 8/8、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 126/126、完整安全全量 3,447 条/0 红/782.2 秒；详见 `tasks_round/tasks_round_727_result.md`。

- R726 结构治理轮（执行，架构模块接口统一第一批第 3 项第三批，**已验收**）：创意附档归档由 `stage_execution_service.archive_idea_attachments()` 注入统一文本发布器；L2 不再直写，控制器仅调用 L3 入口。专项 8/8、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 126/126、完整安全全量 3,446 条/0 红/759.6 秒；详见 `tasks_round/tasks_round_726_result.md`。

- R725 结构治理轮（执行，架构模块接口统一第一批第 3 项第二批，**已验收**）：剧本模型工具、自动保存与 HOLLMWOOD 原稿均改由 `stage_execution_service.reply_to_writing()` 注入统一文本发布器；没有注入发布器的写请求会拒绝。专项 27/27、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 124/124、完整安全全量 3,444 条/0 红/760.8 秒；详见 `tasks_round/tasks_round_725_result.md`。

- R724 结构治理轮（执行，架构模块接口统一第一批第 3 项首批，**已验收**）：字幕 SRT 与对白脚本的 L2 导出服务不再直写阶段成果，改由 `stage_execution_service` 注入统一 `publish_stage_text()`；桌面仅经 L3 发起。文件命名、UTF-8 BOM、空对白拒绝与返回值不变。专项 9/9、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 122/122、完整安全全量 3,442 条/0 红/781.6 秒；详见 `tasks_round/tasks_round_724_result.md`。

- R723 结构治理轮（执行，架构接口统一第一批第 4 项第十三批，**已验收**）：L2 `previs_monitor.progress_of()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；监视页刷新节奏和进度缺失/损坏时“制作中”的容错不变。专项 28/28、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 120/120、完整安全全量 3,439 条/0 红/749.9 秒；详见 `tasks_round/tasks_round_723_result.md`。

- R722 结构治理轮（执行，架构接口统一第一批第 4 项第十二批，**已验收**）：L4 `video_navigation` 的正式项目 JSON 展示读取已委托 `file_cache.read_json()`，同时保留损坏文件返回空表的页面容错。专项 67/67、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 119/119、完整安全全量 3,437 条/0 红/753.4 秒；详见 `tasks_round/tasks_round_722_result.md`。

- R721 结构治理轮（执行，架构接口统一第一批第 4 项第十一批，**已验收**）：L4 `white_model.choose_previs()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；入口弹窗、选镜与跳转白模预演的交互不变。专项 53/53、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 118/118、完整安全全量 3,434 条/0 红/754.3 秒；详见 `tasks_round/tasks_round_721_result.md`。

- R720 结构治理轮（执行，架构接口统一第一批第 4 项第十批，**已验收**）：L4 `local_previs.show()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；页面构建、默认勾选与复杂度路由不变。受影响冒烟 9/9、默认冒烟 8/8、架构门禁 117/117、完整安全全量 3,433 条/0 红/747.7 秒；详见 `tasks_round/tasks_round_720_result.md`。

- R719 结构治理轮（执行，架构接口统一第一批第 4 项第九批，**已验收**）：L2 `white_model_service.read_record()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；原子重发后下一次读取会采用新记录，历史 preview 兼容转换不变。专项 53/53、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 116/116、完整安全全量 3,432 条/0 红/751.0 秒；详见 `tasks_round/tasks_round_719_result.md`。

- R718 结构治理轮（执行，架构接口统一第一批第 4 项第八批，**已验收**）：L3 `previs_automation.start()` 已由裸 JSON 读取收口至 `file_cache.read_json()`，仅用于派发前冻结正式分镜快照；外部 ffprobe 响应解析不变。专项 52/52、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 115/115、完整安全全量 3,430 条/0 红/749.0 秒；详见 `tasks_round/tasks_round_718_result.md`。

- R717 结构治理轮（执行，架构接口统一第一批第 4 项第七批，**已验收**）：L2 `keyframe_batch.candidates()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；正式分镜原子重发后，下一次候选计算会采用新镜头清单。专项 8/8、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 114/114、完整安全全量 3,429 条/0 红/748.1 秒；详见 `tasks_round/tasks_round_717_result.md`。

- R716 结构治理轮（执行，架构接口统一第一批第 4 项第六批，**已验收**）：`previs_batch_service.prepare_batch()` 已由裸 JSON 读取收口至 `file_cache.read_json()`；正式分镜原子重发后，下一次批处理会按新镜头清单重新校验。输出任务清单仍只经 `agent.core.save()` 原子发布。专项 4/4、受影响冒烟 9/9、默认冒烟 8/8、架构门禁 113/113、完整安全全量 3,427 条/0 红/765.7 秒；详见 `tasks_round/tasks_round_716_result.md`。

- R715 结构治理轮（执行，架构接口统一第一批第 4 项第五批，**已验收**）：剧本 API 已确认简报读取已由裸 `read_text/json.loads` 收口到 `file_cache.read_json()`；当前阶段及旧目录只读兼容路径、`script_contract.brief_document()` 复核和错误语义不变。新增原子重发后立即可读回归和 AST 架构门禁。首次完整安全全量仅因结果文件建立后未先推进台账轮次而触发连续性守卫（715 != 716），更正后完整安全全量 3,425 条/0 红/751.2 秒；详见 `tasks_round/tasks_round_715_result.md`。

- R714 结构治理轮（执行，架构接口统一第一批第 4 项第四批，**已验收**）：工作流调用设置的三处裸 JSON 读取已收口到 `file_cache.read_json()`，写入保持唯一 `agent.core.save()`；缓存命中后 Qwen 模型同步可立即读取更新设置。设置格式、默认值和 UI 行为不变。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 111/111、完整安全全量 3,423 条/0 红；详见 `tasks_round/tasks_round_714_result.md`。

- R713 结构治理轮（执行，架构接口统一第一批第 4 项第三批，**已验收**）：确认门禁承担项目确认记录持久化，故从 L0 事实层更正登记为 L2 领域服务；其项目确认记录已由裸 `read_text/json.loads` 收口到 `file_cache.read_json()`，写入仍保持唯一 `agent.core.save()` 原子发布入口。缓存命中后再次记录会读取到新选择，新增正式 JSON 读写架构门禁，禁止退回裸读。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 110/110、完整安全全量 3,421 条/0 红；详见 `tasks_round/tasks_round_713_result.md`。

- R712 结构治理轮（执行，架构接口统一第一批第 4 项第二批，**已验收**）：三虎项目运行状态 JSON 已由裸 `read_text/json.loads` 收口到 `file_cache.read_json()`，写入保持唯一 `agent.core.save_text()` 原子发布入口；缓存命中后再次保存会读取到新状态。新增该 L2 正式 JSON 读写架构门禁，禁止退回裸读。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 109/109、完整安全全量 3,419 条/0 红；详见 `tasks_round/tasks_round_712_result.md`。

- R711 结构治理轮（执行，架构接口统一第一批第 3 项第三批，**已验收**）：自动交接完成标记的 L2 服务已改为只接收 L3 给定的目标与发布器；`stage_execution_service.save_automatic_handoff_marker()` 统一定位 edit 阶段并注入 `publish_stage_text()`，桌面仅调用编排入口。标记字段、路径和原子发布语义不变，架构守卫覆盖 UI→L3→L2 依赖方向。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 108/108、完整安全全量 3,417 条/0 红；详见 `tasks_round/tasks_round_711_result.md`。

- R710 结构治理轮（执行，架构接口统一第一批第 3 项第二批，**已验收**）：自动粗剪完成标记的 L2 服务不再定位阶段目录或直连原子保存；它只接收 L3 给定的目标与发布器，`stage_execution_service.save_automatic_assemble_marker()` 统一定位 edit 阶段并注入 `publish_stage_text()`，桌面仅调用该编排入口。标记字段、路径和原子发布语义不变，新增 UI→L3→L2 发布边界守卫。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 108/108、完整安全全量 3,417 条/0 红；详见 `tasks_round/tasks_round_710_result.md`。

- R709 结构治理轮（执行，架构接口统一第一批第 4 项首批，**已验收**）：白模预演进度 JSON 的读取已由裸 `read_text/json.loads` 收口到 `file_cache.read_json()`，写入保持唯一 `agent.core.save_text()` 原子发布入口；缓存命中后再次发布会经既有 `published` 事件失效，界面可读取新进度。新增 L2 JSON 读写架构门禁，禁止该服务退回直接读写正式路径。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 108/108、完整安全全量 3,417 条/0 红；详见 `tasks_round/tasks_round_709_result.md`。

- R708 结构治理轮（执行，架构接口统一第一批第 3 项，**已验收**）：音频导入 L2 服务现强制只接收由 L3 注入的二进制发布器，移除其直写／临时复制分支；`stage_execution_service.import_stage_audio()` 是 UI 到服务的唯一编排入口，`desktop` 不再直接调用 L2。新增 UI→L3→L2 AST 守卫并保留发布器校验、源文件不改与格式／非空输入断言。默认冒烟 8/8、受影响冒烟 9/9、架构门禁 107/107、完整安全全量 3,415 条/0 红；详见 `tasks_round/tasks_round_708_result.md`。

- R707 结构治理轮（执行，架构接口统一第一批第 2 项，**已验收**）：新增 L0 `project_context.ProjectContext` 四字段契约 `{root, stage_resolver, settings_snapshot, cache}`。L3 `stage_execution_service.project_context()` 是唯一构造入口，并为交付成片导入注入阶段解析器、缓存与统一发布器；L2 `delivery_import_service` 只消费该上下文，不再自行决定阶段目录或拼接项目内部路径。新增上下文构造／快照隔离回归和两条 AST 架构门禁；默认冒烟 8/8、架构门禁 107/107、完整安全全量 3,415 条/0 红。未修改用户项目数据；详见 `tasks_round/tasks_round_707_result.md`。

- R706 结构治理轮（执行，架构接口统一第一批第 1 项，**已验收**）：新增 L0 `service_contract` 作为 L2 写服务的四字段结果权威；`UserError` 可直接提示，`SystemError` 仅记录详情、上层显示通用文案，`Cancelled` 不计失败。交付成片导入已完成首个生产试点，成功／用户输入错误／运行环境失败不再以裸路径或业务异常混用。新增分层与结果契约门禁；默认冒烟 8/8、架构门禁 105/105、完整安全全量 3,411 条/0 红。未修改用户项目数据；详见 `tasks_round/tasks_round_706_result.md`。

- R705 验收轮（统筹锁语义与全量收口，**已验收**）：制作锁保持简报建议档，未填不阻断手动简报发送；无人值守剧本启动缺锁时仅以 `stage.failed` 阻断并指引填写创作信息。新增两项契约回归，未改变产品逻辑或用户项目数据。默认冒烟 8/8、架构门禁 103/103、完整安全全量 3,405 条/0 红；详见 `tasks_round/tasks_round_705_result.md`。

- R704 功能轮（统筹行逐项确认与偏离明细，**已验收**）：统筹行选择后先展示对照确认；首次套用严格只填显式空阶段，既有勾选不覆盖。切换显示旧建议／当前勾选／新建议，由用户逐项套用或保留；偏离徽标可点击查看只读明细。默认冒烟 8/8、受影响冒烟 9/9、GUI-short 安全全量 1,079 条/0 红；页面改动需重启应用，详见 `tasks_round/tasks_round_704_result.md`。

- R703 可靠性／数据迁移轮（统筹迁移干跑与画幅默认收口，**已验收**）：迁移工具默认只读生成报告，按项目登记扫描并将旧工作流路径／ID 与注册表归一；`--apply` 才会写统筹键，且只补显式空阶段、保留已有勾选、旧字段及未知顶层数据，重复执行无文件改写。本次 3 个登记项目均无可映射旧清单，故未写用户项目。资产场景、首帧和云资产的画幅优先级统一为制作锁→已存偏好→各自旧默认（16:9／9:16／1:1）；“画幅三处默认冲突”已关闭。默认冒烟 8/8、受影响冒烟 9/9、完整安全全量 3,403 条/0 红；详见 `tasks_round/tasks_round_703_result.md`。

- R702 修复轮（启动期自动链收尾，**已验收**）：首帧期不再因外部装配项目而无条件恢复全局 tick；已派发的自动粗剪与自动交接包各有独立、可取消的 50ms 结果投递，既不会饿死，也不会在页面稳定前触发新的自动决策。视频检查先于白模派发，避免状态栏覆盖。默认冒烟 8/8、gui-short 安全全量 1,079 条/0 红、完整安全全量 3,398 条/0 红；详见 `tasks_round/tasks_round_702_result.md`。页面行为改动需重启应用。

- R701 修复轮（启动期后台任务结果回填，**未验收**）：`Desktop.async_()` 现有独立、可取消的 50ms 结果轮询，保证 R697 暂停全局 tick 的首帧窗口里，用户主动的后台任务完成后仍能解除 worker 并回填状态；“强制关闭 ComfyUI”专项由红转绿，默认冒烟 8/8、gui-short 安全全量 1,079 条/0 红。完整安全全量为 3,398 条/24 个文件有红，集中于旧三虎 UI 几何和无人值守自动链，故未按全量验收关闭；同时登记两条架构门禁待下一批收口。详见 `tasks_round/tasks_round_701_result.md`。

- R700 修复轮（选择项目后的查询风暴与聊天首现）：注册表热查询以 2 秒时间片复用文件键/指纹，根 manifest 迁移只在首次建表或强刷运行；阶段配置以项目配置 mtime 记忆化并在所有写入口失效；聊天模型键慢时先显示软件示例/空壳，键回后按代次重绘历史。真实项目探针为聊天首现 1.086 s、文件键调用 0、模型键 0.000 s，均达本轮线。默认冒烟 8/8、gui-short 安全全量 1,079 条完成；唯一 `test_asset_gating` 既存异步状态时序红未由本轮引入。前一轮未单列的 `after(80)` 延后建页改动已在 R700 承接说明补登，轮次连续为 R699→R700→R701。页面行为改动需重启应用，详见 `tasks_round/tasks_round_700_result.md`。

- R699 功能轮（统一文字组件）：`ui_tokens.py` 已定义 `TEXT_HINT`、`TEXT_DESC`、`TEXT_PROGRESS`；`ui_widgets.py` 的 `HintLabel`、`DescriptionBlock`、`ProgressLabel` 是对应文字唯一构建入口。阶段配置弹窗已优先迁移模型/外部包提示、HOLLMWOOD/路由说明及预设/统筹状态；文字组件边界守卫禁止该页面重新以原始 Label 手设字体或前景色。UI 专项 13/13、阶段配置定向 136/136、默认冒烟 8/8 通过；架构门禁 103 条中两条既存分层／阶段入口红未由本轮引入。页面改动需重启应用，详见 `tasks_round/tasks_round_699_result.md`。

- R698 功能轮（全局 Combobox 样式）：`ui_tokens.py` 已定义下拉框默认宽度、字体、内边距、字段色、文字色和箭头色；`ui_widgets.setup_styles(root)` 是 `TCombobox`、只读态和弹出 Listbox 的唯一视觉入口。业务页面、用户项目数据和既有按钮／输入框 token 未改。UI 专项 11/11、默认冒烟 8/8 通过；架构门禁 102 条中 2 条既存分层／阶段入口红，未由本轮引入。页面改动需重启应用，详见 `tasks_round/tasks_round_698_result.md`。

- R695 功能轮（SKILL 仅注入编剧）：HOLLMWOOD 的全局节奏模板仍注入全部角色，所选 SKILL 指令则只进入编剧初稿与返工改写；导演规划、导演审核、编辑和演员均不接收。调用签名、96k 预算、取消令牌、空正文重试、APPROVED 门禁和逐步日志不变；面板已明确提示该口径。专项 11/11、HOLLMWOOD 16/16、受影响门禁 35/35、默认冒烟 8/8 通过，详见 `tasks_round/tasks_round_695_result.md`。

- R694 契约轮（剧本外部包总入口审计，**未验收**）：`script_contract.AUDIT` 已登记 screenplay-production-line、screenplay-writer、script-forging、短剧编剧搭子、编剧技能集五个剧本阶段外部包总入口，均按“支撑”分类；其理由与 `skill_registry.imported_package_meta` 的受控默认值一致：仅 `creative-writing`、不自动展开内部子 SKILL、无 output/manifest。严格全覆盖清单守卫已同步（本次改测试因契约变更〔外部包登记〕，断言未弱化）；`AuditTests` 7/7、默认冒烟 8/8、受影响门禁 26 路均通过。全量安全自检为 3380 条、28 个文件有红，包含本轮开始前已存在的 UI/阶段等红项，故按硬判定 `[TASK_FAILED]`，不得验收关闭；完整日志为 `维护记录/r694_contract_safe_all.log`，详见 `tasks_round/tasks_round_694_result.md`。

- R693 修复轮（三虎日报/周报关闭键）：三虎日报和周报使用的标签框现与其他提示框一致显示右上角关闭键，点击后沿用既有淡出/关闭流程；不改变报表生成、保存、自动停留时长或对话框逻辑。日报标签关闭键专项 1/1、默认冒烟 8/8 通过；页面改动需重启应用，详见 `tasks_round/tasks_round_693_result.md`。

- R692 修复轮（阶段配置紧凑对齐）：预设、厂商、SKILL 三个标签统一 10 字符宽度，控件间距和行距收束为 4px token；路由/外部包空提示不再占额外行距。HOLLMWOOD 和默认操作说明均改为短句，外部包提示压缩为“外部包总入口：桌面引擎可完整执行；API 仅传入入口。”手动与全局状态提示同步简化；配置、编辑和执行逻辑未变。专项 4/4、默认冒烟 8/8 通过；页面改动需重启应用，详见 `tasks_round/tasks_round_692_result.md`。

- R691 功能轮（HOLLMWOOD 编辑下拉）：阶段配置页的 HOLLMWOOD 行现置于 SKILL 勾选区上方；“四角色协作”保留，节奏模板、导演/编剧/编辑/演员规则五颗按钮收束为“选择要编辑的内容”下拉框。选择任一内容会立即打开原有项目级编辑页，随后下拉自动复位，便于再次编辑同一项。配置字段、默认规则及保存/恢复入口未变。专项 3/3、默认冒烟 8/8 通过；页面改动需重启应用，详见 `tasks_round/tasks_round_691_result.md`。

- R690 修复轮（阶段配置 SKILL 说明区自适应）：底部“SKILL 说明”区现以说明框上方控件的实际底边为界，占用窗口剩余高度；拖动阶段配置窗口时，目录和 Markdown 正文同步伸缩，目录增加垂直滚动条，优先显示更多 SKILL。新增窗口由 680px 缩至 460px 的实际 Tk 高度回归，以及目录/正文并列与滚动条存在性断言。专项 3/3、默认冒烟 8/8 通过；页面改动需重启应用，详见 `tasks_round/tasks_round_690_result.md`。

- R689 修复轮（阶段配置 SKILL 中文显示）：阶段配置面板的勾选项、悬停全文、说明目录和保存结果提示均从显示名中移除拉丁字符；例如“Drama 分镜”显示为“分镜”，“TTS 配音合成”显示为“配音合成”。内部 SKILL ID、路径和持久化格式保持不变；纯英文自定义名回退为“自定义技能”。新增专项 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_689_result.md`。

- R688 修复轮（阶段配置窗口尺寸）：阶段配置弹窗打开时现以主界面实际宽高减去设计 token 留白计算初始尺寸与可调整上限，默认不超过 880×720，因而始终小于主界面；窗口仍允许在该范围内调整。新增主界面 1200×800 时弹窗宽高及 `maxsize` 的 Tk 回归。新增专项 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_688_result.md`。

- R687 修复轮（启动首帧全栈终裁，**未验收**）：全栈 `after` 树确认旧 10.713s 卡顿的主因是已选项目 `Desktop.load()` 同步阶段模型配置，非注册表冷解析；三虎启动期嵌套 `update_idletasks` 同时放大。模型配置现经代次校验后台同步，首帧前暂停既有 automation tick，三虎量测改为合并 idle 回调且销毁时取消。单次 Tk spin 已降至 44.9ms、空项目 0.393s，但真实项目最终一测为 3.614s，未达 ≤3.0s，故本轮不得关闭；默认冒烟 8/8、受影响门禁 10 文件、gui-short 39 文件/153 工作单元已执行。页面改动需重启应用，详见 `tasks_round/tasks_round_687_result.md`。

- R686 修复轮（阶段配置 SKILL 双源渲染去重）：注册表已渲染的阶段 SKILL 与工作流设置中保存的同一 `SKILL.md` 现按规范 `resolve()` 路径去重，面板只显示注册表框；隐藏的工作流路径仍随流程框选择写回，故 CLI 引擎消费不会丢外部包入口。新增同源单框、隐藏路径持久化保全、未注册路径仍显示三条回归；未改注册表扫描、缓存、用户配置格式或用户数据。默认冒烟 8/8、受影响门禁 9/9、SKILL 关联回归 136 条均通过；页面改动需重启应用，详见 `tasks_round/tasks_round_686_result.md`。

- R685 功能轮（HOLLMWOOD 四角色模式开关 + 关闭态自动落盘，**未验收**）：项目级 `hollmwood_enabled` 缺键默认开启；关闭时剧本准备走通用 API 并保留完整简报，正文仅在既有自然剧本闸门通过且不少于 800 字符时，经唯一 `_write_script_raw()` 自动发布，重复正文幂等。阶段配置已提供“四角色协作”复选框，桌面提示按本次模式区分；页面改动需重启应用。默认冒烟 9/9、受影响门禁 163 条、关联回归 27 条均通过；全量安全自检 3377 条有 `test_script_contract` 与 `test_token_saver` 两个既存失败，故不得验收关闭。完整日志为 `维护记录/r685_safe_all.log`，详见 `tasks_round/tasks_round_685_result.md`。

- R683 功能轮（岗位3内嵌 HOLLMWOOD 四步 + 目录映射）：`短剧工业化流水线` 的岗位3参考文档现明确导演规划→编剧初稿→编辑改写→演员润色的内部串行流程；编剧/编辑/演员每步由导演以 `APPROVED` / `REVISE:` 审核、每步最多返工一次，仍不放行时交岗位8总编裁定。SKILL 同时明确过程文档落入 `01剧本准备/docs/`、正文只由程序发布到 `script_raw.md`、Gate A/B 为界面暂停确认。仅改 3 份指定 Markdown/txt 文档；默认冒烟 8/8、`-k skill` 132 条均通过，详见 `tasks_round/tasks_round_683_result.md`。

- R682 功能轮（外部包 SKILL 引擎适配提示）：阶段配置面板现会在已勾选外部包总入口且当前模型非既有桌面引擎时，明确提示 API 仅注入入口指针、不会展开本地岗位/子模块；提示仅读取注册表元数据，未改扫描、注入、执行或用户配置。新增面板回归覆盖 API 显示、桌面引擎隐藏与普通 SKILL 隐藏；默认冒烟 8/8、`--affected skill_panel skill_registry` 128 条均通过。页面改动需重启应用生效，详见 `tasks_round/tasks_round_682_result.md`。

- R681 功能轮（剧本准备过程文档输出契约）：剧本准备仍只交付完整自然语言剧本原稿；所选 SKILL 的大纲、节点表、审查报告和确认清单可作为过程文档写入相对 `docs/`，不得替代剧本结构阶段的结构化剧本。未改剧本落盘闸门、调用链或路径实现；默认冒烟 8/8、受影响门禁 21 条、`-k workflow` 93 条均通过，详见 `tasks_round/tasks_round_681_result.md`。

- R649 结构治理轮（首帧管理页）：`Desktop.storyboard()` 的多分镜行归属、首帧路径安全校验及按来源批次选择已迁至无 Tk 的 `KeyframePageController`；控件、绑定、刷新、缩略图和状态文案仍留在 UI。专项 3/3、默认冒烟 8/8 通过；已声明的全量安全自检未取得汇总，按硬判定未验收完成，原始片段见 `维护记录/r649_safe_all.log`，详见 `tasks_round/tasks_round_649_result.md`。

- R648 结构治理核验轮（初步分镜页）：`Desktop.storyboard_creation()` 仅作为 3 行页面委派入口，初步分镜文件表的无 Tk 状态已由 `StoryboardPageController` 承接，故不重复拆分。控制器专项 2/2、默认冒烟 8/8、`--affected desktop` 7/7 通过；详见 `tasks_round/tasks_round_648_result.md`。

- R647 验证/基线轮（执行 R630 候选 8.1）：复核“启动剪映”未找到标准安装路径时仅将开始菜单扫描排入 `async_()`，既有 `EditorStartMenuScanTests` 仍覆盖点击只排队、快捷方式匹配及未找到后的受控错误。专项 3/3、默认冒烟 8/8、`--affected desktop` 7/7 通过；未改生产代码或测试，详见 `tasks_round/tasks_round_647_result.md`。

- R646 结构治理轮（执行 R630 候选 6.1，用户指定剧本准备页）：`Desktop.writing()` 的剧本文档表加载代次、批次和排序状态已迁至无 Tk 的 `writing_page_controller.ScriptListLoadController`；控件构造、事件绑定、页面重建和状态文案仍在 `desktop.py`，既有 `IdeaChatController` 对话逻辑未重复迁移。控制器专项 2/2、默认冒烟 8/8、`--affected desktop` 7/7 通过；已声明的架构门禁命中既存 `test_platform_process_boundary` 与 `test_recycle_service` 红项，按硬判定 `[TASK_FAILED]`，不得验收关闭。详见 `tasks_round/tasks_round_646_result.md`。

- R645 结构治理轮（执行 R630 K-6.1，用户指定 04 资产管理）：已将类别筛选、勾选初始化与批量目标判定抽至无 Tk 的 `asset_page_controller.AssetPageController`，页面控件、删除、导入与项目数据写入仍留在 `desktop.py`。聚焦回归 8/8、默认冒烟 8/8 通过；全量安全自检 3350 条、19 个既存失败文件，按硬判定 `[TASK_FAILED]`，不得验收关闭。详见 `tasks_round/tasks_round_645_result.md`。

- R644 功能轮（执行 R630 候选 4.2）：已实现程序自有 `logs/*.log` 与 `维护记录/*.log` 的 30 天保留、10 MiB 单文件三份轮转与 150 MiB 目录上限，并仅在正常退出后无窗口异步维护；手动入口为 `scripts/maintain_logs.py`。聚焦回归 15/15、默认冒烟 8/8 通过，但已声明的全量安全自检为 3347 条、19 个文件有红，按硬判定 `[TASK_FAILED]`，不得验收关闭。详见 `tasks_round/tasks_round_644_result.md`。

- R643 结构治理轮（执行 R630 候选 4.1）：复核现有 `distribution_manifest.md` 仍以声明方式界定正式分发的保留与排除项，`architecture.md` 仍登记其不参与启动、不执行文件操作；默认冒烟 8/8、架构门禁 102/102 通过。未实施构建器、未改生产代码、测试、配置或用户项目数据。详见 `tasks_round/tasks_round_643_result.md`。

- R642 验证/基线轮（执行 R630 候选 3.2）：当前源码仍显示创意 Markdown 发现先以默认路径建页、再由 `async_()` 后台递归发现，并以页面代次和编辑器身份隔离旧结果；未改生产代码、测试、配置或用户项目数据。默认冒烟 8/8 通过；已声明的架构门禁因轮次台账写入时序触发 `test_round_number_continuous`（`642 != 643`）失败，按硬判定 `[TASK_FAILED]`，不能验收关闭。详见 `tasks_round/tasks_round_642_result.md`。

- R641 验证/基线轮（执行 R630 候选 3.1）：复核“未找到剪映时在 Tk 主线程递归扫描开始菜单”已由现有 `launch_editor()` 经 `async_()` 排队解决；递归 `glob` 只在后台 `find_editor_shortcut()` 运行，结果回调保留原有受控提示。默认冒烟 8/8、`--affected desktop` 7 条/0 红通过；未改生产代码、测试、产品配置或用户项目数据。详见 `tasks_round/tasks_round_641_result.md`。

- R640 验证/基线轮（执行 R630 候选 1.2）：未完成真实用户环境的启动白屏复验。桌面自动化服务返回 `Trusted RPC service is not configured: sky`，无法取得窗口、截图或计时；默认冒烟 8/8 通过，但声明的全量安全自检为 3342 条、19 个文件有红，按硬判定 `[TASK_FAILED]`。未改生产代码、测试、产品配置或用户项目数据；全量原始日志为 `维护记录/r640_safe_all.log`，详见 `tasks_round/tasks_round_640_result.md`。

- R639 修复结果复核轮（执行 R630 候选 1.1）：确认运行时引擎选择的配置、模型池和本机程序探测异常不再被 `current()` 静默吞掉；仅预期的未安装 `ValueError` 可回退 API。R636 的对应四条回归仍有效，默认冒烟 8/8、workflow 定向门禁 9/9 通过；未改生产代码、测试、产品配置或用户项目数据。详见 `tasks_round/tasks_round_639_result.md`。

- R638 性能轮（执行 R630 K-3.2）：剧本准备页的创意历史发现现由既有后台队列执行，页面先使用无扫描默认路径；页面切换或重建后旧代次结果不会覆盖当前编辑目标。新增 240 份临时 Markdown 的排序/明显退化阈值与旧代次保护回归；专项 23/23、默认冒烟 8/8、架构门禁 102/102 通过。未改用户项目数据，详见 `tasks_round/tasks_round_638_result.md`。

- R637 验证/基线轮（执行 R630 K-3.1）：复核剪映开始菜单扫描仍由 `launch_editor()` 经 `async_()` 排队，递归扫描只在后台 `find_editor_shortcut()` 执行，未找到时仍为受控提示；现有专项 `EditorStartMenuScanTests` 3/3、默认冒烟 8/8、`--affected desktop` 7 条/0 红通过。无生产或测试代码变更、无用户数据改动。详见 `tasks_round/tasks_round_637_result.md`。

- R636 验证/基线轮（执行 R630 K-1.1）：补齐桌面引擎路由异常边界回归。`stage_config.get`、`model_pool.pool` 和本机程序探测的非预期异常均必须原样暴露，只有“未安装”的预期 `ValueError` 可回退 API；每条路径均断言读取不写临时项目 `skill_config.json`。默认冒烟 8/8、工作流受影响门禁 93 条/0 红通过；未改生产代码、产品配置或用户数据。详见 `tasks_round/tasks_round_636_result.md`。

- R635 结构治理轮（执行 R630 J-5 的 4.1）：新增声明式 `distribution_manifest.md`，界定正式分发必须保留的启动器、运行环境和程序资源，以及构建时必须排除的测试、开发记录、脚本、缓存、历史日志、私有数据和升级备份；`architecture.md` 已登记其不参与运行时。默认冒烟 8/8 通过；架构门禁首次因结果文件已是 R635 而台账仍为“635 待执行”，触发 `test_round_number_continuous`（`635 != 636`），按用户硬判定 `[TASK_FAILED]`。未改生产代码、配置或用户数据；详见 `tasks_round/tasks_round_635_result.md`。

- R634 结构治理轮（子场景：执行；来源 R630 J-4）：后期剪辑页的“已下载视频门禁、自动粗剪报告与完成文案”迁入无 Tk 的 `editing_page_controller.EditingPageController`；`desktop.py` 保留控件、调度、布局和剪映启动。专项 2/2、默认冒烟 8/8、架构门禁 102/102 通过；跨层全量安全自检为 3338 条、16 个既有失败文件，按硬判定本轮 `[TASK_FAILED]`，未越界修复。详见 `tasks_round/tasks_round_634_result.md`。

- R629 功能轮：新增开发专用 `scripts/clean_dev.py`，可演练或清理非受保护的程序缓存、明确测试残留及临时目录；`--deep` 清理过期日志、`--archive` 归档 R500 及之前结果均默认不执行。默认实测释放 37.70 MiB，三组 data 测试残留和生产缓存已删除；系统 ACL 拦住的 `.selftmp` 残留被如实报告，脚本不越权。默认冒烟 8/8、架构 102/102 通过，详见 `tasks_round/tasks_round_629_result.md`。
- R628 只读诊断轮：对 `D:\漫剧制作助手` 做逻辑字节体积盘点（不扫描用户项目）。总计 104.30 MiB；`程序` 72.41 MiB、`运行环境` 30.99 MiB，另有 0.90 MiB 根目录运行时零散项。结果含一级/二级目录、缓存、日志、媒体及前 20 大文件清单；未改分发内容，详见 `tasks_round/tasks_round_628_result.md`。
- R627 功能轮：阶段配置的用户主动改选模型或套用预设后，若 GPT/Anthropic API 对应本机程序可启动，会显示“优先由本机程序执行、启动失败回落 API”的只读说明；DeepSeek 和本机不可用时不显示改走提示。路由与保存逻辑不变，`architecture.md`/`PROJECT_MAP.md` 已与实现同步。新增专项 3/3、默认冒烟 8/8 通过；受影响门禁仍有既存 SKILL 顺序、工具注册基线失败，完整记录见 `tasks_round/tasks_round_627_result.md`。
- R625 功能轮：模型池与阶段配置中的 ChatGPT Desktop / Claude Desktop 现在按需复用既有程序探测，未找到程序（含探测异常）时在显示名后标注“未安装”；模型 ID、历史选择、保存读取与既有受控执行错误均不变。状态仅缓存于当前进程，不在启动期探测或落盘。专项 16/16、默认冒烟 8/8、架构 101/101 通过；受影响门禁仍有既存 DPAPI、工具注册和 SKILL 顺序基线失败，详见 `tasks_round/tasks_round_625_result.md`。
- R618 修复轮：阶段配置中新增自定义工作流 SKILL 后，说明目录和正文立即重建并选中该条目；勾选区改为宽度驱动的自动换行网格，窗口缩窄时不再裁掉勾选项。待执行布局回调在面板或顶层窗口销毁时取消，避免 Tk 残留回调。专项 3/3、默认冒烟 8/8 通过；受影响 SKILL 门禁仍被两条既有独立失败阻塞，详见 `tasks_round/tasks_round_618_result.md`。
- R617 修复轮：阶段配置的个人 SKILL 删除改为“勾选目标 → 删除已勾选”，保留二次确认、个人目录范围校验和可恢复回收站；内置/外部 SKILL 不会删除。专项 3/3、默认冒烟 8/8 通过；受影响 SKILL 门禁仍有两条既有独立失败，详见 `tasks_round/tasks_round_617_result.md`。
- R616 功能轮：新增个人已安装 SKILL 删除入口及可恢复回收站路径；后续 R617 已按用户反馈替换为勾选式操作。详见 `tasks_round/tasks_round_616_result.md`。
- R615 修复轮：按用户要求移除剧本准备输入框的 `/` SKILL 搜索/补全。删除候选加载、菜单、插入逻辑及键盘绑定；输入框保留普通文本与 `@` 创意附件引用。默认冒烟 8/8 通过，详见 `tasks_round/tasks_round_615_result.md`。
- R614 修复轮：Registry 文件清单缓存键已从仅 `skills/` 根目录 mtime 扩至“根目录 mtime + 有序一级阶段目录 mtime”。因此在 `01 剧本准备SKILL/` 等目录内新增或删除 `.skill.md` 时，同一进程的默认注册表会重新递归生成清单；常规未变化查询仍只 stat 根与一级目录，不重新 rglob。新增真实阶段目录增删回归先红后绿。默认冒烟 8/8 通过；受影响门禁仍有两条既存独立失败，详见 `tasks_round/tasks_round_614_result.md`。重启应用后即可使用该修复。
- R612 修复轮：修复剧本准备输入 `/` 时 SKILL 补全菜单可能卡死页面的问题。根因是 `<KeyRelease>` 在 Tk 主线程同步查询注册表，首次查询可递归扫描 SKILL 目录；现改为后台加载、主线程轮询渲染，并按阶段配置签名缓存候选。新增慢查询不阻塞 Tk 回归；补全／输入框回归 4/4、受影响冒烟 9/9、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_612_result.md`。
- R611 验证/基线轮（来源：用户指定 `tasks_round/tasks_round_609_result.md` I/J/K）：复核确认 I 的目录自动发现机制保持不改，J 的历史兼容门面测试登记、56 个文件和 101/101 基线已由 R610 收口，K 无需测试迁移；当下架构门禁 101/101、默认冒烟 8/8 通过。未修改产品或测试逻辑，详见 `tasks_round/tasks_round_611_result.md`。
- R610 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_609_result.md` J 节）：补齐历史兼容门面架构门禁登记和验证地图；架构基线以实测更新为 56 个测试文件、101/101，默认冒烟 8/8。轮次台账已由滞后的 R608 校正并推进至 R611，恢复连续性守卫。
- R609 结构治理轮（子场景：只读诊断）：确认 `test_legacy_facade_manifest.py` 已被 `--architecture` 自动发现执行，但此前未在 AGENTS.md 第 5 节登记；诊断建议已在 R610 收口。
- R607 功能轮：剧本准备输入框支持 `/` SKILL 指令补全；候选严格来自当前项目“剧本准备”阶段已勾选、未弃用的 SKILL，输入可按 ID/显示名筛选，点击、Tab 或 Enter 会插入规范 `/skill-id` 文本。发送、附件和模型调用链不变。专项 1/1、输入框布局 2/2、定向门禁 7/7、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_607_result.md`。

- R605 功能轮：阶段配置的“SKILL 说明”目录现在严格复用上方工作流勾选区的顺序：当前工作流 SKILL 在前、阶段专属 SKILL 在后，且不再仅限剧本阶段。说明正文优先显示配置项对应的完整 SKILL Markdown；文件不可用时回退同目录 `README.md`，不会再出现空白说明区。新增排序和 README 回退回归 3/3；默认冒烟 8/8 通过。`--affected skill_registry` 仍被两条既存注册表基线失败阻塞，详见 `tasks_round/tasks_round_605_result.md`。

- R604 性能轮：长会话模型上下文统一为“较早对话摘录 + 最近 6 条”，总量严格受 12,000 字符预算约束。摘录本地确定性生成、不调用模型、不改写聊天 JSON；完整记录仍保留。与 R602 的 mtime/大小增量读取缓存一起，避免重复解析与全量重传；严格四角色质量路径不变。专项 21/21、定向 9 项、架构 101/101、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_604_result.md`。

- R603 性能轮：剧本准备选择创意附件后，入库、DOCX 解析、文本校验和字符统计均走独立后台任务；主线程只定时接收结果。预处理期间发送被禁用且控制器拒绝提交，完成后才可引用或发送；失败不会产生半成品模型请求。该队列不复用模型调用的 `async_()` 票据或阶段并发槽。无 Tk 回归 4/4、界面接线 1/1、定向 9 项、架构 101/101、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_603_result.md`。

- R602 性能轮：剧本准备的模型分区对话按文件 mtime 纳秒和大小缓存，未变更文件不再重复 JSON 解析；外部覆盖自动失效，读取副本不会污染编辑流程。缓存最多 16 份，既有最近 6 条/字符上限和单 JSON 原子写格式不变。新增专项通过、剧本 API 20/20、架构 101/101、默认冒烟 8/8；全量 idea_chat 尚有既存选区颜色基线漂移，详见 `tasks_round/tasks_round_602_result.md`。

- R601 性能轮：剧本准备桌面 Agent 的续发改为短续接任务，不再重传完整工作流提示词；当前 SKILL、阶段契约和项目续接摘要仍由原有统一入口注入。本轮只减少重复上下文，不改变直接 API 的严格四角色质量路径。工作流 82/82、定向 9 项、架构 101/101、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_601_result.md`。

- R600 性能轮：剧本准备的直接模型调用已并入既有阶段并发槽。获得槽位后立即执行；槽满时以 Tk 定时器轮询并显示位次，界面保持响应。完成、异常均归还槽位，中断会撤销未开始票据；严格四角色质量路径及发布语义不变。精确回归 43/43、定向 9 项、架构 101/101、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_600_result.md`。

- R599 性能轮：SSE 流在建连前及每段读取前检查剧本准备取消令牌；取消明确终止，不回退为一次新完整请求。UI 中断立刻移除临时流式气泡，旧队列消息被请求令牌丢弃，HOLLMWOOD 不再启动后续角色或正式发布。普通非流式供应商保留当前连接返回后停止协作的既有语义。精确回归 37/37 通过。详见 `tasks_round/tasks_round_599_result.md`。

- R598 性能轮：剧本准备严格四角色流程新增可回退的流式体验。OpenAI 兼容 chat 模型以 SSE 接收分段；演员成稿通过线程安全队列在对话区显示临时“生成中”气泡，成功后才写入正式回复／剧本，非 chat 协议、协议不支持或流失败自动复用完整响应。导演、编剧、编辑与三次导演审核未减少。精确回归 36/36、定向门禁 100 条、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_598_result.md`。

- R597 性能轮：为剧本准备 HOLLMWOOD 四角色链路的每个模型调用记录安全耗时 `elapsed_ms` 与请求字符数 `request_chars`，并写入既有 `model_diagnostics` 的上下文；不记录任何提示词或回复正文，不改变四角色协作、重试、取消边界或产物写入。本轮建立后续流式与并发优化的基线，并非实际加速；严格质量路径仍为默认。角色专项 10/10、关联定向门禁 30/30、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_597_result.md`。

- R596 修复轮：修复主界面从最小化恢复后，用户立刻在页面底部滚动时偶发无法显示被遮挡内容。根因是恢复窗口的滚轮事件可能早于画布恢复尺寸后的合并布局批次，旧滚动区域没有及时重算。主窗口 `<Map>` 现在仅为主窗口重新映射补排既有 `fit_content()` 空闲任务，滚轮路由、页面布局和局部控件滚动语义不变。新增恢复后首枚滚轮回归；定向 UI 回归、默认冒烟与架构门禁结果见 `tasks_round/tasks_round_596_result.md`。

- R595 状态接续轮：校正 R547 的历史结果标题。该轮工作仅为静态审计与长期架构债务拆分，原“R182 长期架构债务只读拆分报告”不是 `AGENTS.md` 第 3 节登记的轮次类型；现统一记为“只读诊断轮：R182 长期架构债务拆分报告”。轮次连续性复核确认：本轮前最大结果为 R594、台账为 R595；新增 R595 后台账前进为 R596，满足 `N == M + 1`。未改 `.py`、用户项目数据或既有技术结论。详见 `tasks_round/tasks_round_595_result.md`。

- R594 状态接续轮：复核 `legacy_compat.FACADE_MANIFEST` 与生产调用方后，五个 facade 仍分别被 `engine`、`confirm_gates`、`local_previs`、`idea_chat`、`pet_ui` 使用，且统一淘汰日仍为 2027-03-31；因此 P3-2 的删除条件仍未成立。同步清除了“P0-3 仍阻塞、R182 债务余 8 项”的过期台账描述，现行债务准确为 P3-2 一项。轮次连续性架构回归 3/3 通过。详见 `tasks_round/tasks_round_594_result.md`。

- R593 结构治理轮（P0-3 拆分四·视频提示）：视频提示的手动保存、切镜自动保存和自动结果写回均由外层注入 `publish_stage_bundle()`；提示词 JSON、两份可见文本副本和分镜索引作为整包发布，任一写入或索引失败即恢复整包旧版本，成功后才更新内存分镜。`video_prompt_publication` 保留兼容直调回退，但不反向导入 L3；静态门禁冻结三条生产入口的注入关系。与 R589–R592 合并后，P0-3 所列交付、音频、首帧、视频提示均已迁入统一发布入口，字幕继续为 R512 回归样本；债务由 2 项降为 1 项。联合回归 28/28、定向冒烟通过、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_593_result.md`。

- R592 结构治理轮（P0-3 拆分三·首帧）：首帧替换生产 UI 已注入 `publish_stage_bytes()`；服务仍先将旧帧安全回收，再发布 PNG，并仅在发布成功后保存镜头引用。镜头索引失败时会删除新帧、恢复原引用并从回收位置恢复旧帧，保留既有恢复语义。统一发布器新增关联成果整包原子发布原语并完成回滚回归；该原语由 R593 视频提示入口使用。首帧／发布器回归 12/12、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_592_result.md`。

- R591 结构治理轮（P0-3 拆分二·音频）：音频导入生产 UI 已注入 `publish_stage_bytes()`；L2 服务先保留格式／非空检查及“读入字节长度必须等于原文件大小”校验，再将字节交由统一发布器原子发布。服务无注入的既有临时副本校验路径保持兼容。音频／交付／阶段发布联合回归 11/11、受影响冒烟通过、默认冒烟 8/8、架构门禁 101/101 通过。P0-3 尚待首帧与视频提示成果迁移。详见 `tasks_round/tasks_round_591_result.md`。

- R590 结构治理轮（P0-3 拆分二·交付）：交付最终成片路径已经由桌面向 L2 `delivery_import_service` 注入 L3 `publish_stage_bytes()`，服务继续拥有格式校验、唯一命名和阶段目录，未形成 L2→L3 反向依赖。旧服务直调保持兼容，生产 UI 路径现具备统一发布器的空内容校验、原子写入及失败传播语义。交付／阶段发布联合回归 8/8、受影响冒烟通过、默认冒烟 8/8、架构门禁 101/101 通过。P0-3 尚待首帧与其余媒体路径迁入。详见 `tasks_round/tasks_round_590_result.md`。

- R589 结构治理轮（P0-3 拆分一）：统一阶段发布器新增二进制成果入口 `publish_stage_bytes()`，与既有文本入口同样强制“内容校验 → 原子写入 → 索引更新”，索引失败则恢复发布前字节且不给调用方成功返回值。新增二进制发布与回滚回归，未越过 L2/L3 边界修改首帧、媒体、交付调用链；它们将于拆分二迁入该入口。阶段发布回归 5/5、受影响冒烟通过、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_589_result.md`。

- R588 只读诊断轮：复核定向 UI 回归结束时出现的“自检增量台账临时文件权限不足”。当前受限诊断环境复现失败，但项目真实权限上下文执行同一 `run_selftests.save_cache(load_cache())` 原子写入成功，正式台账可正常覆盖；故该提示是沙箱写入边界，不是产品、用户环境或自检代码缺陷。未改任何生产／测试 `.py`、用户项目数据或台账格式；从已知阻塞中移除。详见 `tasks_round/tasks_round_588_result.md`。

- R587 修复轮：完成 UI 回归治理中 Tk 退出残留 `after` 回调的根因修复。`Desktop.fit_content()` 的匿名空闲布局回调此前未保留任务 ID，关闭链路无法在销毁 Tcl 命令前取消它，故退出时偶发 `invalid command name "...run"`。现将该任务纳入 `cancel_timers()` 的统一所有权与取消路径，并新增“关闭前取消待执行内容布局任务”回归；精确 2/2、完整 UI 边界 109/109、默认冒烟 8/8、架构门禁 101/101 均通过。本次完整 UI 回归 stderr 已无该 Tk 告警；仅剩维护自检增量台账临时文件权限提示，与应用 UI 生命周期无关，另作环境观察项。详见 `tasks_round/tasks_round_587_result.md`。

- R586 修复轮：修复同页重建后滚动位置回顶的布局竞态。`Desktop.show()` 将原滚动位置登记为待恢复状态；`fit_content()` 在相同的最终布局测量连续稳定后才恢复该位置，新页仍立即置顶。避免使用固定延时或同步强制布局，首帧仍保持异步。精确滚动回归 1/1、完整 UI 边界回归 109/109、默认冒烟 8/8、架构门禁 101/101 均通过。Tk 测试进程退出时仍有少量过期 `after` 回调告警，以及自检增量台账临时文件权限告警；虽不影响结果，仍保留为 UI 回归治理 P0 的剩余观察项。详见 `tasks_round/tasks_round_586_result.md`。

- R585 修复轮：完成 token 化后过期 UI 契约迁移：初步分镜卡片断言转为 `Tokens.Card.TFrame`，定稿选中镜头转为 `Tokens.Primary.TButton`，剧本准备发送按钮间距明确为 `SPACING['xs']` 的 4px 防误触间隔；精确回归 4/4、默认冒烟 8/8 通过。同步定位同页页面重建滚动恢复的真实 P0：异步 `fit_content()` 与立即 `restore_scroll()` 存在布局完成顺序竞态，精确用例从约 381px 回顶。未提交不稳定延迟修复，登记下一轮专项。详见 `tasks_round/tasks_round_585_result.md`。

- R584 修复轮：修复自动定稿发布前的实际生产错误。精确回归复现 `storyboard_final.finalize()` 在定稿文本校验调用 `json.dumps()`／`json.loads()` 时因漏导入标准库而抛出 `NameError`，致使定稿文件未生成、工作稿也未能进入统一回收站。仅补 `import json`；既有阶段发布、原子替换、别名更新与 `storage_maintenance.recycle_paths()` 语义未改。自动定稿／回收精确回归 1/1、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_584_result.md`。

- R583 修复轮：完成 P0 UI 回归治理第一簇。`Desktop.tick()` 已在 R555 自动调度器迁移中收束为 `_tick_once()`，但 3 条旧测试仍直调已移除入口；现仅迁移其调用点，保留自动粗剪／交接的产物、状态、幂等和失败恢复断言。启动对账用例同时取消未到期的异步项目选择计时器，防止其状态提示覆盖被测对账结果，动作与断言不变。精确回归 3/3、默认冒烟 8/8 通过；生产代码与用户数据未改。详见 `tasks_round/tasks_round_583_result.md`。

- R582 修复轮：修正 `test_ui_edges` 中与现行剧本准备响应式发送框规则冲突的旧测试契约，**未改生产代码**。旧断言要求 200 行文本框撑至 200 行；现行 `desktop.py` 规则明确将其限制为 6–15 行，以保留发送操作和文件表。新断言同时验证高度落在既有边界内及第 200 行文本仍保留，未弱化数据完整性覆盖。精确分组 8/8、默认冒烟 8/8 通过。完整 `--affected ui_edges` 为 109 条／321.8 秒，第 3 分组已通过，但另外 8 个分组有 14 条独立失败，并伴随 Tk `after` 残留回调 `invalid command name "...run"`；登记为 P0 UI 回归治理阻塞，不将其错误归因于本轮。详见 `tasks_round/tasks_round_582_result.md`。

- R581 修复轮：针对全应用按钮悬停高亮块过大的问题，未逐项替换 100 处直接 `ttk.Button`，而是在 `ui_widgets.setup_styles(root)` 统一覆盖默认 `TButton`、旧 `Primary.TButton`／`Secondary.TButton` 与 token 组件按钮。所有这些按钮现在均使用 `SPACING['md']` × `SPACING['xs']`（12×4）紧凑内边距；悬停均为浅主色背景＋主色文字，禁用态为边框背景＋弱文字。`Desktop.__init__` 在既有主题后调用一次该安装入口，因此同一 Tk 根上的历史直接按钮和新组件同时生效。新增默认／旧样式回归，`test_ui_theme` 10/10、受影响 desktop 7/7、默认冒烟 8/8 通过；未改按钮事件、布局结构或用户数据。详见 `tasks_round/tasks_round_581_result.md`。

- R580 修复轮：修复剧本准备页底部“项目设定／项目大纲／项目剧本”三列表不显示。根因是 R561 的渐进加载排序在 `desktop.py:3651` 调用 `Treeview.move()` 时漏传 `parent` 参数，Tk 回调抛出 `TypeError` 并在恢复表格可见性前中止；同时，加载启动时先隐藏容器会放大该故障的可见影响。现改为正确调用 `move(item, '', 'end')`，并在扫描期间保留三列表列头，仅在确认没有文件后收起空表。补充已有文件时容器映射回归。精确 Tk 回归 1/1、默认冒烟 8/8、架构门禁 101/101 通过；完整 `--affected ui_edges` 门禁另有 1 项既有失败，未在本修复轮扩大范围处理。详见 `tasks_round/tasks_round_580_result.md`。

- R579 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：核查确认 `desktop.py` 仅挂接三虎，实际“设置窗口”由 `pet_settings_ui.open_hub()` 构造，模型配置及模型管理专属子窗由 `pet_models_ui` 构造；故仅迁移这两个真实入口。窗口填充、页标题、字段间距及紧凑输入样式复用 `FONTS`／`SPACING`；全部操作按钮改复用 `PrimaryButton`／`SecondaryButton`，页签选中态为主按钮、未选中态为次按钮。为使受影响门禁真实覆盖该范围，`smoke_test.py` 登记两个入口至既有 `test_pet_settings.py`。未新增 token／组件，未改设置读取写入、模型连接、密钥处理、宠物逻辑、布局结构或用户数据。定向 52/52、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_579_result.md`。

- R578 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：核查确认 `desktop.py` 仅通过 `pet_ui.attach()` 挂接三虎，实际“**三虎对话框**”构造入口为 `pet_cloud.py:Cloud.build()`；因此仅迁移该真实入口及其专属关闭控件。云框／提示框的填充、描边、正文、提示、输入提示、关闭控件和字体复用 `COLORS`、`FONTS`、`SPACING`；关闭控件悬停为浅底＋危险色文字，避免白字不可见。该无边框 Canvas `Toplevel` 没有普通 `ttk.Button`，所以未强行套用不兼容的按钮组件；未改对话、动画、位置、事件、宠物交互或用户数据。专项 4/4、受影响 pet_cloud 门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_578_result.md`。

- R577 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移 `desktop.py:Desktop.delivery()` 的“质检与交付”页面视觉构造。操作栏与阶段配置间距复用 `SPACING`；“手动制作交付”和“导入剪映最终成片”使用主按钮，打开交付／报告目录使用次按钮，仍复用既有安全回调与事件包装。该页面没有自建弹窗，导入动作仅调用系统文件选择器，未越界修改通用“阶段配置”或系统对话框；未新增 token／组件，未改质检、导入、发布、事件、目录或用户数据。交付页面构建回归 1/1、受影响 desktop 门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_577_result.md`。

- R576 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移 `desktop.py:Desktop.editing()` 的后期剪辑页面视觉构造。操作栏与阶段配置间距复用 `SPACING`；手动制作与两项主要产出操作使用主按钮，交接、启动剪映、打开目录等辅助操作使用次按钮。该页面没有自建弹窗，未越界修改其它阶段的共用配置入口；未新增 token／组件，未改自动粗剪、交接、启动外部编辑器、清单保存、事件、目录或用户数据。后期剪辑 UI 回归 1/1、受影响 desktop 门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_576_result.md`。

- R575 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移 `desktop.py:Desktop.audio()` 的配音与字幕主页面，以及其“配音设置”唯一自建弹窗 `tts_settings.show()`。操作行的间距复用 `SPACING`；主／次操作统一映射既有 `Tokens.Primary.TButton`／`Tokens.Secondary.TButton`，弹窗直接复用 `PrimaryButton`／`SecondaryButton`。未新增 token／组件，未改变配音、字幕导出、设置持久化、回调、目录或用户数据。TTS 回归 38/38、受影响 desktop 门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_575_result.md`。

- R574 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：核查确认 `desktop.py:Desktop.videos()` 仅负责路由／宿主，实际视频工作台与两个直接设置弹窗分别在 `app.py`、`cloud_video.py`、`local_video.py`。三个入口的间距、颜色、字体与常规操作现复用 `COLORS`／`FONTS`／`SPACING` 和 `PrimaryButton`／`SecondaryButton`；MCP 优化保留既有琥珀色高亮，表达额外调用成本而不降级为普通主按钮。未新增 token／组件，未改视频提交、轮询、设置持久化、路由、事件、目录或用户数据；应用模块恰为三个。视频 UI 64/64、云端设置 11/11、默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_574_result.md`。

- R573 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：核查确认 `desktop.py:Desktop.previs()` 只委派给 `local_previs.show()`，白模预演及其唯一直接创建的线上白模弹窗实际由 `local_previs.py` 构造，故仅迁移这一实际入口。卡片、间距、完成态颜色及页内所有操作统一复用 `COLORS`／`SPACING` 与 `Card`／`PrimaryButton`／`SecondaryButton`；未新增 token/组件，未改变预演、导入、停止、打开目录、视频生成、事件、目录或用户数据逻辑。`--affected local_previs` 目前没有映射而产生 0 条筛选失败，使用阶段既有别名 `previs` 的受影响门禁 78/78 通过；默认冒烟 8/8、架构门禁 101/101 通过。详见 `tasks_round/tasks_round_573_result.md`。

- R572 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移 `desktop.py:Desktop.storyboard()` 的“首帧管理”页面视觉常量。选中镜头行、操作行与阶段配置间距均复用 `SPACING`；完成态／首帧行颜色复用 `COLORS`；“手动制作首帧”同步为 `Tokens.Primary.TButton`，页内六个次操作同步为 `Tokens.Secondary.TButton`，仍使用原共享安全回调和事件包装。该入口没有直接构造 `Toplevel`；独立提示词窗、首帧制作窗和 Tk 原生对话框未越界改动。未新增 token/组件、未改首帧业务流程、事件、目录或用户数据。首帧精确布局回归 1/1、受影响门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过；详见 `tasks_round/tasks_round_572_result.md`。

- R571 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：核查确认 `desktop.py:final_storyboard()` 仅委派，实际“分镜定稿”视觉构造在 `storyboard_files.show_final()`；因此只迁移该入口的工具栏、状态操作、卡片、镜头导航、预览文本区和提示区。颜色、字体与间距统一复用 `COLORS`／`FONTS`／`SPACING`，主动作与选中镜头使用 `PrimaryButton`，其他操作与未选中镜头使用 `SecondaryButton`；未新增 token/组件，未改定稿控制器、保存、后台读取、事件、目录或用户数据。同步既有高亮样式断言至 token 组件，断言语义未弱化。定向 40/40、默认冒烟 8/8、架构门禁 101/101 通过；详见 `tasks_round/tasks_round_571_result.md`。

- R570 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移资产管理主页面的视觉构造、其名称／外观详情弹窗，以及资产批量制作弹窗。`desktop.py` 和 `asset_batch.py` 现复用 `COLORS`／`FONTS`／`SPACING` 与 `PrimaryButton`／`SecondaryButton`；分类选中态以主按钮、未选中态以次按钮统一呈现。未新增 token/组件，未触及资产详情子路由、业务流程、事件、目录或用户数据。受影响 asset_batch 9/9、desktop 9/9、默认冒烟 8/8、架构门禁 101/101 通过；详见 `tasks_round/tasks_round_570_result.md`。

- R569 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅将 `storyboard_files.show()` 的“初步分镜”视觉构造迁入既有设计系统；工具栏、操作栏、卡片、手动制作按钮与阶段配置间距统一使用 `SPACING`，新建按钮统一使用 `PrimaryButton`／`SecondaryButton`，卡片使用 `Card`。未新增或修改 token/组件，未触及 `show_final()`、事件、数据、目录或分层。初步分镜布局回归 1/1、受影响门禁 9/9、默认冒烟 8/8、架构门禁 101/101 通过；详见 `tasks_round/tasks_round_569_result.md`。

- R567 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P3-1）：`legacy_compat.FACADE_MANIFEST` 现逐项登记五个历史兼容入口的唯一所有者、真实生产调用方与统一淘汰日（2027-03-31）；调用分别来自 `engine`、`confirm_gates`、`local_previs`、`idea_chat`、`pet_ui`。新增架构门禁反查生产 AST，要求公共 facade、调用方与清单完全一致，并在淘汰日到期时明确失败，避免遗漏、绕过或静默延期。未删改兼容行为、用户数据或对外接口；定向 8/8、默认冒烟 8/8、架构 101/101 通过。R182 拆分债务由 3 项减至 2 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_567_result.md`。
- R568 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P3-2）：依据 R567 清单反查，五个 facade 均仍有真实生产调用，且统一淘汰日为 2027-03-31，故没有可安全删除的零调用或过期包装。`stage_path_service` 已验证旧项目目录在到期后不再作为只读候选，但尚无用户可见迁移失败提示；补充该提示会新增行为，受本轮禁止加功能／不改契约约束，不能擅自实施。P3-2 登记阻塞，债务仍为 2 项（P0-3、P3-2）。详见 `tasks_round/tasks_round_568_result.md`。

- R566 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P2-5）：跨阶段交互模型请求在既有全局／阶段并发上限满额时不再立即失败：注册表生成内存排队票据，桌面以 200ms Tk 空闲轮询显示“模型请求排队中（第 N 位）”，领取可用槽位后仍从既有后台线程启动，未阻塞主线程。强制停止或窗口关闭会撤销本项目尚未启动的票据，已运行进程继续由既有登记／终止路径收束；阶段并发配置、模型调用和状态机未变。新增释放后领取、项目取消回归；定向 5/5 与受影响门禁通过，默认冒烟 8/8、架构 98/98 通过。R182 拆分债务由 4 项减至 3 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_566_result.md`。

- R565 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P2-4）：非剧本阶段的初始 Agent 请求现只携带阶段级项目续接摘要及可按需读取的持久化进度文件路径，不再重复携带完整通用项目索引；剧本准备仍沿用完整索引策略。请求仍执行既有 96,000 字符硬上限与重复段去重；发送收据新增不含正文的初始/续接预算元数据（阶段、策略、字符数、上限、余量），可审计不同模型调用的上下文规模。应用代码仅改动 `desktop.py`、`workflow_context.py`、`workflow_context_budget.py` 三模块；上下文/预算回归 24/24、定向 desktop 9/9、默认冒烟 8/8、架构 98/98 通过。R182 拆分债务由 5 项减至 4 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_565_result.md`。

- R564 结构治理轮（子场景：执行；来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`）：仅迁移 `Desktop.script_structure()` 的视觉常量：容器/文本区/操作栏的间距、文本区颜色与字体均改用 `SPACING`、`COLORS`、`FONTS`；“手动制作结构剧本”和“保存修改”改经 `PrimaryButton`，修改/恢复操作改经 `SecondaryButton`，主按钮的悬停态保持浅主色背景配主色文字，不会出现白字不可见。该方法没有自建 `Toplevel` 弹窗，右键菜单也没有显式可迁移的视觉常量；未新增 token/组件、未变更事件、逻辑或用户数据。定向 desktop 9/9、默认冒烟 8/8、架构 98/98 通过。详见 `tasks_round/tasks_round_564_result.md`。

- R563 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P2-3）：`file_cache` 新增正式发布、回收（含恢复）与外部覆盖三个语义化缓存失效事件，统一按正式路径清除 JSON、文本及字节缓存；`agent.core` 的原子替换/新建发布在成功后触发发布事件，`storage_maintenance` 的回收/恢复在移动完成后一次性失效来源与目标路径。页面不再需要以刷新来驱动缓存一致性；不经过原子发布边界的外部适配器必须在覆写成功后显式调用外部覆盖事件，原有 mtime/哈希检测仅保留为未接入旧路径的安全兜底。应用代码改动 3 个模块；相关单测 32/32、默认冒烟 8/8、架构 98/98 通过。R182 拆分债务由 6 项减至 5 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_563_result.md`。

- R562 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P2-2）：分镜定稿页对大 JSON 保持“选择偏好先落既有控制器、读取在后台、结果按页面代次接收”的路径；文本经空闲回调每批约 64 KiB 写入 `Text`，换选、刷新或拆页即取消待提交结果。读取仍经 `file_cache` 复用文件签名/内容哈希缓存。资产详情的缩略图请求由既有 `asset_thumbs` 队列改绑至可销毁的页面控件，离页时已有失活检测自动丢弃未消费任务；未改变图片缓存、预览内容或文件契约。补齐 `smoke_test.py --affected storyboard_files/asset_detail` 映射。应用代码改动 3 个模块；定向 38 条、相关单测 39/39、默认冒烟 8/8、架构 98/98 通过。R182 拆分债务由 7 项减至 6 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_562_result.md`。

- R561 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P2-1）：剧本准备页剩余三列表的文件扫描改为 `script_workspace_service.iter_script_document_rows()` 逐项发现；`desktop.py` 以每批 24 条 `after_idle` 提交，最后再以同样受限的批次恢复既有“修改时间倒序”。刷新、页面重建或销毁会失效并取消旧代次，避免大项目一次枚举/渲染堵塞 Tk；分镜文件页已有后台扫描机制，未重复改造。未改用户数据、目录契约或控件动作。服务定向 14/14、受影响门禁 21 条、默认冒烟 8/8、架构 98/98 通过。R182 拆分债务由 8 项减至 7 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_561_result.md`。

- R560 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-7）：新增静态架构门禁，守卫五个已迁移的 desktop／分镜／资产无 Tk 控制器不得导入 `tkinter`，并禁止 `desktop.py`、`storyboard_files.py`、`asset_batch.py` 直接调用浏览器、socket 或子进程 API；已冻结它们允许使用的 `platform_tools`／`native_apps` 入口。既有浏览器打开与 Comfy 端口短探测等同语义移至 `platform_tools`，未增加产品功能。R182 拆分债务由 9 项减至 8 项，P0-3 继续阻塞。定向 3/3、默认冒烟 8/8、架构 98/98 通过。详见 `tasks_round/tasks_round_560_result.md`。

- R559 修复轮：修复剧本准备页“发送”主按钮悬停为浅色背景后仍保留白字、因而近乎不可见的问题；`PrimaryButton` 现将悬停文字映射为主色，禁用态为弱文字。“阶段配置”从旧暖色 `StageConfig.TButton` 迁入 `SecondaryButton`，全阶段入口统一为卡片底、主色文字的可读悬停态。阶段配置主弹窗、HOLLMWOOD 规则弹窗及预设共享弹窗的标题、操作按钮、文本区、字体和间距同步改用 token/组件；新增主/次按钮状态回归与阶段入口语义定位回归。默认冒烟 8/8、桌面定向 7/7、架构 95/95 通过。详见 `tasks_round/tasks_round_559_result.md`。

- R558 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-6）：`asset_batch.show()` 的类别勾选、表单默认值/选项归一、Comfy 模型检测重试与已删除模型过滤、以及启动前范围/清单/提示词/本地模型门禁已迁入无 Tk 的 `asset_batch_controller.AssetBatchController`；`asset_batch.py` 保留 `show()` 兼容入口、Tk 控件组装、异步投递及用户确认弹窗。既有设置持久化、执行器和用户数据语义不变。新增控制器无 Tk 回归 3/3，定向 12 条、默认冒烟 8/8、架构 95/95 通过；R182 拆分债务由 10 项减至 9 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_558_result.md`。

- R557 功能轮：三虎右键「进度面板」和「待确认项」（原“查看待确认详情”）均改为在三虎旁的既有提示框展示完整对应内容，不再调用 `pet_show_text()` 创建只读弹窗；定向 16/16、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_557_result.md`。

- R556 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-5）：`storyboard_files.show()` 的文件表扫描结果、选择持久化、按钮门禁和回收/恢复编排已迁入无 Tk 的 `storyboard_page_controller.StoryboardPageController`；页面仅保留 Treeview 渲染、弹窗确认与事件绑定。目录、选择和回收仍分别调用既有服务，未改用户数据或页面功能。定向 35 条、默认冒烟 8/8、架构 95/95 通过；R182 拆分债务由 11 项减至 10 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_556_result.md`。

- R555 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-4）：`storyboard_files.show_final()` 的定稿预览、编辑保存、选中偏好与镜头导航状态已迁入无 Tk 的 `storyboard_final_controller.FinalStoryboardController`；页面仅保留控件组装、控件更新、弹窗和事件绑定。原子 JSON 保存仍经 `storyboard_edit_service`，查看偏好仍经 `storyboard_selection`，未改数据或 UI 行为。定向 15 条、默认冒烟 8/8、架构 95/95 通过；R182 拆分债务由 12 项减至 11 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_555_result.md`。

- R554 结构治理轮（子场景：执行；来源：`design_tokens.md` + `ui_components.md`）：剧本准备页 `Desktop.writing()` 的直接间距、Text 颜色和字体已改为 `SPACING`、`COLORS`、`FONTS`；发送与次级操作改经 `PrimaryButton` / `SecondaryButton`，不改变页面逻辑、事件或布局结构。新增 L1 `ui_tokens` 与 L4 `ui_widgets` 作为设计系统的代码入口；定向 7/7、默认冒烟 8/8、架构 95/95 通过。详见 `tasks_round/tasks_round_554_result.md`。

- R553 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-3）：剧本准备页对话的请求状态、发送节流、附件注入和流式角色进度回调已迁入无 Tk 的 `idea_chat_controller.IdeaChatController`；`desktop` 保留所有控件绑定、队列投递和状态文案，`idea_chat.py` / `idea_attachments.py` 的既有契约未改变。新增无 Tk 回归覆盖附件标记、节流与取消后旧进度丢弃；定向控制器 3/3、桌面/对话 6 个匹配文件、默认冒烟 8/8、架构 95/95 通过。R182 拆分债务由 13 项减至 12 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_553_result.md`。

- R552 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-2）：桌面自动流程的两条周期回调、取消、回调异常兜底及九类自动阶段的到期/节流轮询已迁入无 Tk 的 `desktop_automation_service.DesktopAutomationScheduler`；`desktop` 仅注入 Tk 调度器并保留队列收尾、状态文案与既有阶段动作，未改变阶段状态机。新增无 Tk 回归覆盖周期异常后重排/取消及到期失败的节流语义；定向 2/2、默认冒烟 8/8、架构 95/95 通过。R182 拆分债务由 14 项减至 13 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_552_result.md`。

- R551 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P1-1）：`Desktop.__init__` 的首帧“150ms 延迟 → Tk 空闲项目选择”时序及取消已迁入无 Tk 的 `desktop_startup_service.DesktopStartupController`；桌面在该启动边界创建窗口、绑定关闭事件并注入现有调度器/状态/项目选择回调，未改变项目恢复或页面构建语义。无 Tk 首帧时序/停止分支 2/2、默认冒烟 8/8、架构 95/95 通过；R182 拆分债务由 15 项减至 14 项，P0-3 继续阻塞。详见 `tasks_round/tasks_round_551_result.md`。

- R550 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P0-3）：实施审阅确认该条不能在“最多 3 个模块、不改契约、不改分层”的并存约束下安全完成。统一入口仅支持文本且在 L3；首帧／交付主成果是二进制，三个目标服务属于 L2，直接导入会形成禁止的 L2→L3 依赖；交付也没有可迁移的既有文本索引。未改生产 `.py`，字幕继续只作为 R512 回归样本。默认 8/8、架构 95/95、相关定向门禁通过；R182 拆分债务仍为 15 项，等待用户选择“放宽模块上限并增加二进制入口”或“拆为两轮”。详见 `tasks_round/tasks_round_550_result.md`。

- R549 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P0-2）：剧本结构的正式 L3 执行路径已向 L0 剧本契约注入 `stage_execution_service.publish_stage_text()`；分镜定稿在既有双文件发布服务外先经相同入口执行内容校验与主成果原子发布，再以双文件服务更新索引。剧本来源登记、分镜双 JSON 回滚与来源关系保持原有恢复语义；没有 L0→L3 反向依赖。R182 拆分债务由 16 项减至 15 项，P0-3 仍待。定向 10 文件、默认 8/8、架构 95/95 通过；详见 `tasks_round/tasks_round_549_result.md`。

- R548 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_547_result.md` J/P0-1）：`stage_execution_service.publish_stage_text()` 已成为阶段文本成果的通用编排入口：调用方先给出既有内容校验器，随后复用 `agent.core.save_text()` 原子发布，最后更新既有索引；索引回调失败会回滚本次成果并抛错，调用方不会取得成功返回值，不能据此标记阶段完成。新增无 Tk 回归覆盖成功顺序、校验失败不落盘、索引失败恢复旧成果。R182 拆分债务由 17 项减至 16 项；P0-2/P0-3 仍负责各阶段迁移。定向 3/3、默认冒烟 8/8、架构门禁 95/95 通过；详见 `tasks_round/tasks_round_548_result.md`。

- R546 功能轮：新增 `tests/architecture/test_startup_budget.py`，静态守卫 `app.py` 入口、`Desktop` 自动打开项目/页面构建链与 `pet_ui` 启动挂接，禁止其直接调用 `rglob`、`glob`、`walk`；未改启动代码。架构门禁现为 54 文件 / 95 检查且实测 95/95，默认冒烟 8/8 通过。`<3 秒` 可交互计时因尚无稳定无界面钩子未虚构断言；详见 `tasks_round/tasks_round_546_result.md`。

- R545 契约轮：新增 `design_tokens.md` 与 `ui_components.md`，统一定义颜色、间距、圆角、字体及主/次按钮、卡片、输入框的唯一写法；`AGENTS.md` 第 34 条指定其为 UI 设计唯一权威，Reviewer 每轮必查。未改 `.py` 或现有页面。默认冒烟 8/8、架构门禁 94/94 通过；详见 `tasks_round/tasks_round_545_result.md`。

- R544 修复轮：剧本准备页输入框与下方“发送 / 阶段配置”等操作栏之间恢复 3px 缓冲间距，保持页面紧凑并减少贴边误触；剧本准备 UI 回归通过。详见 `tasks_round/tasks_round_544_result.md`。

- R543 功能轮：剧本准备页支持将 `.md/.txt/.docx` 上传并转存为 `01剧本准备/输入/故事创意_<时间戳>.md`；DOCX 只以标准库 `zipfile + xml.etree` 提取正文。归档文件会显示在“项目设定”列；输入 `@` 可选择已上传文件，发送时显式引用优先，否则受控注入最多最近三份；输入框下显示文件名与字数。未改 `brief_raw.md`，不读取或暴露原始本机路径。服务测试 15/15、用户指定 `smoke_test.py --affected idea_chat writing` 完成；详见 `tasks_round/tasks_round_543_result.md`。

- R542 修复轮：`smoke_test.py` 的受影响别名表新增 `skill_registry → skills`，使 `--affected skill_registry` 正确筛选 `tests/test_skills.py`；实测命中 1 个测试文件、17 个工作单元，不再是 0 条。默认冒烟 8/8 通过。该定向门禁仍因 `test_skills` 既有 SKILL 数量/顺序和工具登记断言失败而不全绿；本轮只修映射，未改 SKILL、测试或产品逻辑，需独立授权处理。详见 `tasks_round/tasks_round_542_result.md`。

- R541 只读诊断轮：真实受控启动两次确认，R539 消除的 `skill_registry.rglob` 约 20 秒扫描阻塞未复现；启动后 1 秒主线程在 `desktop.py:3361` 构建剧本准备页时首次导入 `skill_panel.py:25`，稳定后 2.5 秒采样如预期位于 `tkinter.mainloop`。窗口约 0.48–0.53 秒映射，但自动打开记住项目的同步 `Desktop.load()` 达 1.310 秒、`show()` 达 1.206 秒，事件循环约 1.95–1.98 秒才重新空闲。因此旧根因已解决，但启动响应性尚未“彻底解决”；P1 剩余阻塞是主线程项目页构建，不是多线程死锁。仅观测，未修改 `.py` 或运行测试；详见 `tasks_round/tasks_round_541_result.md`。

- R540 性能/资源轮：自动打开当日项目保留 150ms 启动延迟，但不再直接在该定时回调中同步 `load()`；现在先经 Tk `after_idle` 交还一次首窗绘制，再在主线程安全构建原剧本准备页。未使用后台线程，未改其他页面或最终 UI。真实启动计时显示窗口约 0.449s 映射、0.631s 开始内容构建、1.864s 完成；与旧直接调度的 0.440s / 0.615s / 1.761s 差异处于本机波动范围，不能宣称缩短了构建本身，但首帧优先顺序现有自动化回归守护。**R540 的价值是防回归结构，不是性能改进。真实加速由 R539 完成。** desktop 定向门禁 5 条、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_540_result.md`。

- R539 性能/资源轮：`skill_registry.Registry` 现以 `skills/` 根目录的纳秒 mtime 为目录级缓存键；首次扫描保留一次递归建表，之后查询仅 `stat` 根目录并复用内存中的“路径 / mtime / 大小”清单及已解析 SKILL，避免每次 `_fresh()` 重复 `rglob`。新增稳定目录不再递归扫描的回归。真实 GUI 启动的 10 秒 faulthandler 栈已进入 `tkinter.mainloop`，不再停在 `skill_registry.rglob`；默认冒烟 8/8、架构门禁 94/94 通过。`smoke_test.py --affected skill_registry` 因筛选键未映射测试文件而执行 0 条并按设计失败，已如实记录，未改无关门禁模块。详见 `tasks_round/tasks_round_539_result.md`。

- R538 只读诊断轮：真实启动 faulthandler 堆栈确认主线程在 `skill_registry.Registry.files()` 的递归扫描停留超过 10 秒，调用链来自自动打开项目时的阶段配置与 SKILL 面板；20 秒采样后又见 Tk 字体测量，未发现线程互等。R535—R537 的布局改动不是该首个卡点的直接调用者。详见 `tasks_round/tasks_round_538_result.md`。

- R537 修复轮：剧本准备“对话AI”、聊天框、输入区与操作栏已收紧垂直间距；“发送”和“阶段配置”紧贴输入框。未附档时状态标签不再留空行，选择附件后才显示文件名摘要。上传文件图标已移至输入框左侧，并继续在窄窗口优先保留可点击宽度。剧本准备定向 Tk 回归 2/2、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_537_result.md`。

- R536 性能/资源轮：修复无当前项目启动时“项目首页已创建却被 Canvas 以首次 1px 高度裁掉”的白屏。`Desktop.show()` 的无项目、参考网站及前置条件拦截等提前返回现在也会安排既有合并空闲布局，不重新引入同步空闲刷新。新增无项目真实 Tk 首屏可见性回归；性能门禁 8/8、默认冒烟 8/8、架构门禁 94/94 通过。此前 R523/R527/R535 未覆盖该提前返回路径；已记录用户重启后的 P1 环境复验边界。详见 `tasks_round/tasks_round_536_result.md`。

- R535 性能/资源轮：剧本准备页面的固定高度测量不再调用 `update_idletasks()` 同步耗尽 Tk 空闲队列，现随既有合并 `after_idle` 布局批次执行，减少首屏及回到该页时的主线程阻塞风险。新增静态性能门禁；性能回归 7/7、默认冒烟 8/8 通过，架构基线沿用已验证 94/94。详见 `tasks_round/tasks_round_535_result.md`。

- R534 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_532_result.md` J2/J3）：历史结果标题与状态摘要中把“执行”误写为独立类型的条目，均已统一为“结构治理轮（子场景：执行）”；R454 按主性质归为修复轮。新增轮次类型静态门禁，只检查结果标题与状态摘要类型字段，保留诊断正文的历史证据。定向 3/3、架构门禁 94/94、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_534_result.md`。

- R533 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_532_result.md` J1）：R526 的结果文件和状态摘要已统一为“结构治理轮（子场景：执行）”，清除一个未定义轮次类型；来源、改动事实、历史验收数字均未改动。J2 历史台账统一及 J3 类型词汇表门禁仍待独立授权。架构门禁 93/93、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_533_result.md`。

- R532 结构治理轮（子场景：只读诊断）：静态复核轮次类型台账后，确认 R518 已更正为“结构治理轮（子场景：执行）”，但 R526 的结果文件与状态摘要仍使用未定义的“结构治理执行轮”，且更早台账还存在“修复/结构治理轮”等组合类型。现有轮次基线测试只校验编号连续，未校验类型词汇表。未改 `.py`、测试或用户项目数据，未运行测试；详见 `tasks_round/tasks_round_532_result.md`。

- R531 修复轮：左上角“漫剧制作助手”右侧设置齿轮在根窗口安全层中的纵坐标由 8px 下移至 11px；22px 图标现与 16px 标题的文字中线对齐，且仍不受侧栏和页面画布裁切。设置入口、提示文本和点击行为不变。定向 Tk 接缝回归 1/1、默认冒烟 8/8、架构门禁 93/93 通过。详见 `tasks_round/tasks_round_531_result.md`。

- R530 修复轮：剧本准备底部“项目设定 / 项目大纲 / 项目剧本”三个独立文件表已移除“修改日期”列，行内仅保留勾选框与文件名；文件扫描、排序、选择与删除动作不变。同步收紧页面 UI 回归为单列与单值断言；并校正该用例此前漏算输入行容器的父级断言，仍验证发送框在对话区内。页面回归 1/1、默认冒烟 8/8、架构门禁 93/93 通过。详见 `tasks_round/tasks_round_530_result.md`。

- R529 修复轮：剧本准备输入行改为先固定右侧附件图标，再让左侧输入框填充剩余宽度；窗口缩窄时输入框会相应缩短，文件上传图标不会被挤出或遮挡。新增 360px 窄窗口 Tk 回归，验证图标映射、实际宽度与右侧边界。定向 Tk 回归 2/2、默认冒烟 8/8、架构门禁 93/93 通过。详见 `tasks_round/tasks_round_529_result.md`。

- R528 修复轮：剧本准备输入框已删除 35ms 横向滚动提示；空框失焦时的说明文字改为以输入框中心静态展示，点击提示仍会把焦点交给真实输入框，开始输入后立即隐藏。同步更新 UI 回归，明确禁止恢复滚动实现或动画回调。剧本准备定向 Tk 回归 2/2、默认冒烟 8/8、架构门禁 93/93 通过。详见 `tasks_round/tasks_round_528_result.md`。

- R527 修复轮：修复启动及切换页面期间的主线程布局阻塞。`Desktop.show()` 不再强制同步执行两次整页尺寸递归与 `update_idletasks()`，而是统一排入既有合并空闲布局；文本框扩展也走相同入口。性能门禁新增该回归并修复其模块化导入路径。性能回归 6/6、架构门禁 93/93、默认冒烟 8/8 通过；历史全量安全基线仍为 3,230 条。详见 `tasks_round/tasks_round_527_result.md`。

- R526 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_525_result.md` I/J/K）：将 `skill_panel` 依其 Tk 控件和窗口生命周期统一登记为 L4 UI；将无 Tk 的 `idea_attachments` 作为 L2 剧本准备文本附档服务纳入分层门禁，并新增“已登记且不越层”的专用架构回归。附件解析单测已从 `test_idea_chat.py` 原样迁至 `test_idea_attachments.py`，未改变断言、fixture 或测试数据。`architecture.md` / `PROJECT_MAP.md` 的 SKILL 与附件说明已按注册器实际扫描的 01—12 阶段目录校对；`AGENTS.md` 全量安全基线统一为 R501 的 3,230，架构基线为 93/93。附件单测 1/1、聊天回归、架构门禁 93/93 与默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_526_result.md`。

- R524 功能轮：剧本准备的上方“软件示例”已成为可右键命中的独立气泡，可直接复制整条示例；下方输入框右侧新增文件夹入口，可选择最多 5 个、单个不超过 1 MB 的 UTF-8/GB18030 文本附档（`.txt`、`.md`、`.json`、`.csv`、`.yaml`、`.log`）。桌面端会在提交前受控读取内容、加上文件名与文本边界交给模型；聊天记录仅显示已附档名称，不泄露本地路径或重复展示正文。PDF、Word 与图片不会伪装成已提交内容，当前会明确拒绝。同步将 SKILL 注册表检查从 L0 剧本契约层移回 L3 报告层，消除一项现存越层依赖。剧本准备回归、架构门禁 92/92、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_524_result.md`。

- R523 修复轮：R522 后仍可复现剧本准备页卡顿，进一步定位为“点击空输入框扩至聊天区半高”与聊天框/画布尺寸监听之间的 `Configure` 反馈环；两处同步整页重排会使抖动持续。输入框现仅随实际文本（最多 8 行）扩展，点击空框只聚焦；输入框/聊天框高度变化统一走已合并的空闲页面重排，不再在 `Configure` 回调中同步递归扫描整页。定向 Tk 回归 4/4、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_523_result.md`。

- R522 修复轮：修复剧本准备页空闲输入提示覆盖 `Text` 编辑器后吞掉点击的问题。现在点击提示会把焦点和展开动作交还给真实输入框，并立即取消 35ms 动画，避免鼠标停留在输入区时持续重绘、画面抖动和助手失去响应；主线程无事可做时的统一调度心跳由 80ms 调整为 150ms，仍及时回收后台结果，减少空闲轮询对点击与输入的抢占。新增提示层点击回归；定向 3/3、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_522_result.md`。

- R521 状态接续轮：按轮次类型契约复核并修复 R504—R507 的历史标题与状态台账漂移。R504 未改产品或测试资产，统一登记为“只读诊断轮”；R505 密钥迁移/输入布局、R506 Responses 协议、R507 云视频凭据界面均实际修复缺陷，统一登记为“修复轮”。P0/P1/P2 仅保留整改优先级，不再冒充轮次类型；事实结论、修改范围与历史验收数字均未改动。轮次基线契约测试及默认冒烟通过。详见 `tasks_round/tasks_round_521_result.md`。

- R520 修复轮：剧本整理页的“自然剧本目录”现将剧本准备阶段受控 `项目剧本/` 分类目录内的 Markdown 识别为自然剧本，即使用户重命名后文件名不含“剧本 / script / 集数”；仍保留正文自然剧本校验、结构稿排除及新旧目录去重。同步修复 SKILL 已按阶段目录分类后的剧本审计：管线 SKILL 不混入内容产物审计，归属 SKILL 通过注册表定位。剧本契约/结构/工作区 73/73、受影响门禁 0 红、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_520_result.md`。

- R518 结构治理轮（子场景：执行；来源：用户指定的全流程 SKILL 阶段拆分）：`00全流程SKILL` 的流程职责已拆为 12 个阶段专属 `pipeline-*.skill.md`，分别登记在 01—12 阶段目录；`dependsOn` 构成单向强依赖图，后期剪辑等待视频与配音字幕。注册器已递归扫描子目录，因此未修改 `skill_registry.py` 或阶段配置面板逻辑；原始全流程资料保留。SKILL 注册定向 20/20、架构门禁 92/92、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_518_result.md`。

- R517 结构治理：HOLLMWOOD 唯一自然剧本发布入口的空正文拒绝已具备直接回归；不得创建 `script_raw.md` 空成果。定向 20/20、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_517_result.md`。

- R516 结构治理：结构剧本契约层在原子发布前拒绝空白正文，防止模型或编排路径生成空成果。定向 60/60、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_516_result.md`。

- R515 结构治理：后台模型报告的非空校验已纳入原子写入架构门禁，校验不得落在正式发布之后。门禁 4/4、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_515_result.md`。

- R514 结构治理：Claude 与 Qwen 后台引擎在报告正文为空时不再覆盖正式制作报告，保留响应记录供诊断并返回明确错误。定向 91/91、默认冒烟 8/8、架构门禁 91/91 通过。详见 `tasks_round/tasks_round_514_result.md`。

- R513 结构治理：剧本模型工具在发布前拒绝空白正文，避免空响应生成可被误判为成果的空文件；保留原有路径授权和原子写入。定向 19/19、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_513_result.md`。

- R512 结构治理：字幕 SKILL 的指定输出不再由 L3 工具层直接写入，统一委派 `subtitle_export_service.publish_srt_text()` 执行行尾校验与原子发布；保留原 `subtitle_file` / `output` 兼容性。定向 6/6、默认冒烟 8/8 通过；R182 的全阶段统一写入项仍待逐项迁移。详见 `tasks_round/tasks_round_512_result.md`。

- R511 主窗口恢复与退出修复：任务栏最小化恢复现按映射、`normal`、布局刷新、置前与临时聚焦顺序执行；聚焦被系统拒绝不会撤销恢复。若后台任务触发强制关闭确认，桌面会先通过同一恢复入口显示主窗口，避免确认框随最小化窗口隐藏。专项 4/4、编译与默认冒烟 8/8 通过；界面改动需重启应用生效。详见 `tasks_round/tasks_round_511_result.md`。

- R510 轮次类型契约修复：R502 的历史名称已从未定义的“契约复核轮”统一为“契约轮”。`AGENTS.md` 明确：仅审计、核对或记录 L0 契约而未改实现时，仍归契约轮，且必须遵守其范围、验证与文档要求。详见 `tasks_round/tasks_round_510_result.md`。

- R509 轮次类型契约修复：R501 的历史名称已从未定义的“回归修复／基线轮”统一为“修复轮（含全量基线验证）”。`AGENTS.md` 明确：有根因修复时归修复轮，全量自检只是验证范围；仅复核/记录基线且未改实现时才归验证/基线轮。详见 `tasks_round/tasks_round_509_result.md`。

- R508 任务栏最小化恢复修复：主窗口可见性现在区分 Tk 的 `normal`、`iconic` 与 `withdrawn` 状态；从最小化恢复时先切回 `normal`，再显示、置顶和聚焦，避免主窗口卡在任务栏。专项 2/2、编译和默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_508_result.md`。

- R507 修复轮（P2 云视频凭据界面保护）：云视频设置的 API Key 不再在打开窗口时回填；输入框默认掩码，用户只能通过显式按钮临时查看已保存凭据，十秒后自动重新掩码并清空。仅临时查看不会触发重新保存或覆盖密钥。Tk 定向 122/122、编译和默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_507_result.md`。

- R506 修复轮（P1 Responses 协议与回归收口）：`responses` 请求现仅使用 `max_output_tokens`，并只拼接真实 `output[*].content[*].type=output_text` 文本；成功、空/工具输出、HTTP 错误与 `input_tokens`/`output_tokens` 用量均有回归。云视频 DPAPI 读取改为直接依赖 `model_secrets`，消除 `api_endpoints ↔ model_pool` 循环；原子边界登记同步收紧。专项 335/335、架构 4/4、完整安全自检 3,239/3,239（852.9 秒）、默认冒烟 8/8 均通过。详见 `tasks_round/tasks_round_506_result.md`。

- R505 修复轮（P0 密钥安全迁移与剧本输入布局修复）：模型密钥新写入统一为当前 Windows 用户 DPAPI，实际旧 `private/.env` 已在成功迁移后清理且未回显密钥；云视频会话改以 `key_provider=model_pool` 运行时取钥，旧会话仅保留只读兼容。剧本准备页点击输入框的尺寸循环亦已修复。定向 250/250、输入页 18/18、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_505_result.md`。

- R504 只读诊断轮（全项目质量审查与治理登记）：完成源码、关键服务、模型路由、云视频、存储、测试与文档的只读审查；确认三项待整改风险：`private/.env` 的明文密钥落盘、`responses` 协议适配错误、云视频设置明文回填 API Key。未修改 `.py`、用户项目数据或密钥；模型路由既有定向测试 59/59 通过，但该结果不覆盖真实 Responses JSON。已将未完成项、阻塞分类、整改顺序和测试迁移计划登记于本状态文件及 `tasks_round/tasks_round_504_result.md`。

- R503 兼容/平台适配轮：后台制作引擎和剧本 Agent 不再直接调用 Windows `taskkill`；`platform_tools.terminate_process_tree()` 在 Windows 保留 `/F /T` 进程树终止，在其他宿主改用标准 `process.terminate()`。新增平台适配单测及直接 `taskkill` 静态边界，未触及用户项目数据或可见本地应用启动行为；定向 64/64、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_503_result.md`。

- R502 契约轮：仅审计 L0 的 `stage_layout`／`stage_path_service`／阶段命令注册契约；12 阶段的运行时顺序、编号阶段目录、JSON/MD 职责分离、旧目录只读兼容及 L4 命令入口均一致，未发现可安全修复的契约漂移，故不改产品代码或用户数据。定向 25/25、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_502_result.md`。

- R501 修复轮（含全量基线验证）：安全全量回归发现发行包默认创意示例缺少 `故事集数`，与 `IDEA_FIELDS` 的首字段契约不一致，导致 `test_ui_edges` 拒绝该内置示例。现已补齐示例字段，不写入用户项目数据；精确回归 1/1、完整 `run_selftests.py --all --safe` 3,230/3,230（855.9 秒、0 个失败文件）、默认冒烟 8/8 均通过，增量台账已刷新。详见 `tasks_round/tasks_round_501_result.md`。

- R500 结构治理轮（来源：R461 E4）：已打开项目时，分镜 JSON 导入器不再直接创建初步分镜阶段目录；`stage_workspace_service.ensure_storyboard_workspace()` 统一初始化并返回该目录，未打开项目仍使用项目库根目录。新增服务行为和导入入口委托边界；定向 12/12、编译、架构 90/90、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_500_result.md`。

- R499 结构治理轮（来源：R461 E4）：资产页不再直接创建用户可见资产分类目录；无 Tk 的 `asset_context.ensure_browser_directory()` 校验类别并仅初始化所选分类目录。新增服务行为和资产页 UI→服务静态边界；定向 84/84、编译、架构 89/89、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_499_result.md`。

- R498 结构治理轮（来源：R461 E2）：手动和无人值守定稿共用的 `Desktop.apply_final()` 不再直接写 `ui_settings.json`；其保留当前分镜采用动作，并委托无 Tk 的 `storyboard_selection.remember_final_view()` 原子发布定稿查看指针。补充桌面收尾 UI→服务静态边界；定向 17/17、编译、架构 88/88、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_498_result.md`。

- R497 结构治理轮（来源：R461 E4）：旧目录归位日志不再由 `desktop.py` 直接创建归档目录或写 JSON；无 Tk 的 `legacy_adoption_service.record_legacy_adoption()` 原子发布日志，桌面页保留原有“日志失败不阻断打开项目”语义。新增服务行为与 UI→服务静态边界；定向 23/23、编译、架构 87/87、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_497_result.md`。

- R496 结构治理轮（来源：R461 E4）：配音、后期和交付页的既有阶段目录初始化不再由 `desktop.py` 直接 `mkdir`；无 Tk 的 `stage_workspace_service` 统一按 `project_stages` 返回并创建音频/字幕、后期、交付/导出目录，页面仅保留控件与文件选择。新增服务行为与五入口 UI→服务静态边界；定向 8/8、编译、架构 86/86、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_496_result.md`。

- R495 结构治理轮（来源：R461 E4）：桌面全局的当日项目选择、本机 ComfyUI 与剪映路径偏好不再由 `desktop.py` 直接写 `desktop_settings.json`，统一由无 Tk 的 `desktop_settings_service.publish_desktop_settings()` 合并并原子发布；失败时不改调用方内存设置。新增服务行为与三入口 UI→服务静态边界，定向 110/110、架构 85/85、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_495_result.md`。

- R494 全量回归收口轮：创意示例保存修复后的 `run_selftests.py --all --safe` 已完成 3,213/3,213（849.6 秒、0 个失败文件），此前失败的 `test_ui_edges#13` 已在全量中通过；增量台账已刷新，最慢单元 34.8 秒，未触发性能阈值。详见 `tasks_round/tasks_round_494_result.md`。

- R493 回归修复轮：安全全量回归定位到“内置创意示例 + 用户补充”会把示例字段表格提交给自然剧本校验的唯一失败。`Desktop.save_brief()` 现先剥离前置软件示例，仅保存用户补充；回归锁定示例不得写入项目。精确 1/1、架构 84/84、默认冒烟 8/8 通过；完整安全回归已由 R494 修复后重跑收口。详见 `tasks_round/tasks_round_493_result.md`。

- R492 结构治理轮（来源：R461 E4）：剧本页不再直接创建剧本准备阶段目录，`script_workspace_service.ensure_script_workspace()` 统一取得并初始化该阶段路径，UI 保持控件装配与交互职责。补充无 Tk 目录创建测试与页面委托边界；定向 14/14、架构 84/84 通过。详见 `tasks_round/tasks_round_492_result.md`。

- R491 结构治理轮（来源：R461 E4）：剧本准备页的实际文件重命名已从 `Desktop.writing()` 收敛到 `script_workspace_service.rename_script_document()`；服务复用项目内路径筛选和目标命名校验，仅在名称变更时执行改名，UI 只负责请求、刷新和提示。新增服务行为测试及 UI→服务静态边界，架构门禁同步扩展至 50 个文件、83/83。定向 12/12、服务层 1,483/1,483、架构 83/83、默认冒烟 8/8 均通过。详见 `tasks_round/tasks_round_491_result.md`。

- R489 验证/基线轮（来源：R488 I/J1）：按架构、服务、GUI E2E 的顺序完成分层实测，并以可观测的安全全量回归收口。架构层 49 个文件、82/82；服务层 1,482 条、25.2 秒；GUI E2E 层 662 条、261.7 秒；完整 `run_selftests.py --all --safe` 为 3,209 条、817.5 秒、0 个失败文件，增量台账已刷新。最慢全量工作单元为 `test_ui_edges#14` 的 34.1 秒，未达到 180 秒阈值，因此不触发性能整改；无台账写入失败，亦不触发可靠性整改。K1 未迁移测试文件。默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_489_result.md`。

- R488 只读诊断轮（来源：R486 全量回归收口待办）：盘点到 191 个测试模块、49 个架构模块与 2 个端到端 GUI 模块；`test_pet_ui`（555 条）和 `test_ui_edges`（107 条）是优先实测候选。确认当前无新死锁或失败证据，台账写入提示属于受限会话目录权限；未改 `.py`、未跑全量。已给出 J 整改路线与 K 测试迁移计划，详见 `tasks_round/tasks_round_488_result.md`。

- R487 可靠性轮（来源：R486 自检执行器可靠性复核）：安全串行测试器改为先从子进程结果队列取回结果、再等待子进程退出，避免大量测试输出占满管道时父进程先 `join()` 造成假超时并误杀已通过单元。超时回收、用例语义与产品代码均未改变。`test_selftests` 19/19、受影响门禁 9/9、默认冒烟 8/8 通过；全量回归仍待后续收口。详见 `tasks_round/tasks_round_487_result.md`。

- R486 性能轮（来源：全量回归暂停后的可观测性待办）：全量测试执行器的并行模式现在按完成顺序报告单元结果，若 30 秒未有单元完成则输出未完成数心跳，并在结束时汇总最慢 10 路；不改变用例选择、断言、并发上限或安全串行超时。同期完成桌面视频模式偏好服务化及合法项目名末尾下划线保留修复。`test_selftests` 18/18、受影响门禁 9/9、默认冒烟 8/8 通过；架构基线已验证至 82/82。全量回归仍待以新入口重跑，不能登记为全绿；详见 `tasks_round/tasks_round_486_result.md`。

- R485 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描，以及本轮自检表补漏）：桌面视频工作区选择不再由 `desktop.py` 直接写项目 `ui_settings.json`；既有 `cloud_video_service.publish_workspace_preference()` 统一发布已经过项目边界校验的工作区偏好。补齐 `AGENTS.md` 自检表遗漏的 `test_local_video_settings_boundary.py` 与 `test_asset_detail_binding_boundary.py`，并新增桌面工作区 UI→服务静态边界。定向 12/12、架构 81/81、默认冒烟 8/8、全量 3,205/3,205（535.4 秒）通过；详见 `tasks_round/tasks_round_485_result.md`。

- R484 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描）：云视频工作室设置不再由 `app.py` 直接写根目录 `config.json`；`cloud_video_service.publish_studio_config()` 统一发布经界面预算、联网与凭据路径预检后的配置。扩展既有云视频设置边界，定向 11/11、架构 80/80、默认冒烟 8/8、全量 3,204/3,204（540.3 秒）通过；详见 `tasks_round/tasks_round_484_result.md`。

- R483 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描）：云视频设置页不再直接写会话 `config.json` 或项目 `ui_settings.json`；`cloud_video_service` 统一发布经 UI 校验的会话配置与工作区偏好。新增服务行为与 UI→服务静态边界。定向 9/9、架构 79/79、默认冒烟 8/8、全量 3,202/3,202（539.3 秒）通过；详见 `tasks_round/tasks_round_483_result.md`。

- R482 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描）：白模预演页不再自行复制视频/工程或写 `预演记录.json`；既有 `white_model_service` 统一校验镜头编号、格式和非空、临时复制校验、原子发布、记录更新及备注保存，源文件保持不动。补齐 `AGENTS.md` 自检表遗漏的 `test_delivery_import_boundary.py`，并新增白模导入 UI→服务边界。定向 51/51、架构 78/78、默认冒烟 8/8、全量 3,200/3,200（538.7 秒）通过；详见 `tasks_round/tasks_round_482_result.md`。

- R481 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描）：本地 ComfyUI 视频设置页不再由 `local_video.py` 直接复制 API 工作流或写项目 `config.json`；`local_video_settings_service` 统一发布工作流副本与设置，并在配置失败时恢复旧工作流和旧配置。UI 保留本机连接与工作流图预检。定向 3/3、架构 77/77、默认冒烟 8/8、全量 3,197/3,197（553.5 秒）通过；详见 `tasks_round/tasks_round_481_result.md`。

- R480 结构治理轮（来源：R461 E2 的剩余 UI 正式写入扫描）：资产详情页的正典板视角与状态变体缩略图不再由 `asset_detail.py` 直接复制文件或写资产索引；`asset_detail_service` 统一校验图片格式/非空、原子复制到资产库、发布 `assets.json`，索引失败时恢复旧图片和旧索引。新增服务行为与 UI→服务静态边界；定向 4/4、架构 76/76、默认冒烟 8/8、全量 3,194/3,194（675.6 秒）通过；详见 `tasks_round/tasks_round_480_result.md`。

- R479 全量回归收口/可靠性修复轮：全量 `unittest discover -f` 依次发现并消除了三类宿主耦合或时序缺口：模型密钥与连通性测试改为注入带格式校验的可逆假保护器，开发信息页测试改为验证对唯一剪贴板出口的调用，已登记制作进程在 `taskkill` 后等待真实退出、超时再直接终止。产品密钥保存仍保留现有加密路径。定向 4/4、架构 75/75、默认冒烟 8/8、全量 3,190/3,190（547.8 秒）通过；详见 `tasks_round/tasks_round_479_result.md`。

- R478 结构治理轮（子场景：执行；来源：R461 E2 的剩余 UI 正式写入扫描）：交付页“导入剪映最终成片”不再由 `desktop.py` 直接校验并复制用户选定文件；`delivery_import_service.import_final_master()` 统一校验格式/非空并复制至唯一交付阶段，源文件保持不动。定向 3/3、架构 75/75、默认冒烟 8/8 通过；全量安全自检待后续跨轮收口验证。详见 `tasks_round/tasks_round_478_result.md`。

- R477 测试迁移/全量收口轮：全量 `unittest discover -f` 在 1,252 项后定位到 `test_pet_llm` 的两项密钥回归直接依赖当前桌面会话 DPAPI，导致在系统保护接口不可用时误报产品失败。测试现改为注入带格式校验的可逆假保护器，仍覆盖本地密钥最后回退、`.env` 优先和损坏密文拒绝。定向 3/3 通过；待继续全量 fail-fast 收口。详见 `tasks_round/tasks_round_477_result.md`。

- R476 结构治理轮（子场景：执行；来源：R461 E2 的剩余 UI 正式写入扫描）：无人值守自动交接包完成的 `自动交接.json` 不再由 `desktop.py` 直接落盘，统一由 `handoff_service.save_automatic_handoff_marker()` 在唯一后期阶段原子发布；页面保留只读决策、队列与状态。新增服务行为和 UI→服务静态边界回归。定向 5/5、架构 74/74、默认冒烟 8/8 通过；全量安全自检待后续跨轮收口验证。详见 `tasks_round/tasks_round_476_result.md`。

- R475 结构治理轮（子场景：执行；来源：R461 E2 的剩余 UI 正式写入扫描）：无人值守自动粗剪完成的 `自动粗剪.json` 不再由 `desktop.py` 直接落盘，统一由 `edit_service.save_automatic_assemble_marker()` 在唯一后期阶段原子发布；页面仍只负责编排、状态与队列。新增服务行为和 UI→服务静态边界回归。定向 7/7、架构 73/73、默认冒烟 8/8 通过；全量安全自检待后续跨轮收口验证。详见 `tasks_round/tasks_round_475_result.md`。

- R474 状态接续/验证轮：复核 R473 后发现 `AGENTS.md` 的架构与全量基线、测试清单仍停在 R458 前的 63/63、3,143 与 40 文件，和已完成的 R473 验收不一致。已只更新入口、架构说明和状态台账至事实基线：架构 72/72、默认冒烟 8/8、全量安全自检 3,183/3,183；架构测试清单为 44 文件。复跑架构门禁 72/72、默认冒烟 8/8 通过。未改生产代码、用户项目数据或测试逻辑；详见 `tasks_round/tasks_round_474_result.md`。

- R473 契约轮：修正 `stage_layout.json_md_rows()` 的人读 MD 映射，全部改为当前编号阶段目录下的 `docs/` 路径，不再向界面或文档泄漏 `02_assets`、`04_storyboard_final` 等旧内部目录名；回归同时强制每条映射的目录属于 `stage_layout.names()`。定向 21/21、架构 72/72、默认冒烟 8/8、全量安全自检 3,183/3,183（796.6 秒）通过。详见 `tasks_round/tasks_round_473_result.md`。

- R472 结构治理轮（来源：R461 E5）：`workflow_context_budget` 在统一预算预检中先合并完全重复的大段上下文、保留首份完整内容并附去重摘要；唯一内容仍超限则安全拒绝。`workflow_engines` 与 `codex_tasks.prepare_task()` 均实际使用压缩后的请求，因而不会在启动进程或创建任务工件前重复传递全文。定向 5/5、架构 72/72、默认冒烟 8/8、全量安全自检 3,183/3,183（774.2 秒）通过。详见 `tasks_round/tasks_round_472_result.md`。

- R471 结构治理轮（来源：R461 E4；E3 删除扫描确认当前 UI 入口均已收口至回收服务）：配音页“导入音频/音乐”不再由 `desktop.py` 直接校验或复制文件，统一交由 `audio_import_service.import_audio()` 校验格式和非空、临时复制校验并原子发布至编号配音阶段，原文件保留。定向 43/43、架构 72/72、默认冒烟 8/8、全量安全自检 3,182/3,182（786.3 秒）通过。详见 `tasks_round/tasks_round_471_result.md`。

- R470 结构治理轮（来源：R461 E2/J 的正式 UI 直写扫描）：配音页整段 TTS 的已完成音频与幂等标记不再由 `desktop.py` 直接发布，统一由 `tts_api` 查询复用并以“媒体优先、标记随后”的顺序发布；标记失败时已完成音频保留但不误登记可复用。定向 40/40、架构 71/71、默认冒烟 8/8、全量安全自检 3,179/3,179（768.6 秒）通过。详见 `tasks_round/tasks_round_470_result.md`。

- R469 结构治理轮（来源：R461 E2/J 的正式 UI 直写扫描）：资产页本地图片导入不再由 `desktop.py` 直接复制图片、改名或写资产索引，统一由 `asset_batch_service.import_asset_image()` 校验、落盘并发布；索引失败时恢复旧图或将新图安全送入项目回收站。定向 9/9、架构 70/70、默认冒烟 8/8、全量安全自检 3,176/3,176（765.3 秒）通过。详见 `tasks_round/tasks_round_469_result.md`。

- R468 结构治理轮（来源：R461 未完成项的正式 UI 直写扫描）：白模上传勾选不再由 `app.py` 直接改写 `episode.json`，统一由 `video_lifecycle_service.save_white_model_upload()` 原子发布；UI 保留忙碌、可编辑、白模就绪与锁保护，服务只发布选择、失败时回滚内存记录，绝不提交或上传。定向 37/37、架构 69/69、默认冒烟 8/8、全量安全自检 3,173/3,173（765.4 秒）通过。详见 `tasks_round/tasks_round_468_result.md`。

- R467 结构治理轮（来源：R461 未完成项的上下文预算盘点）：内置 Codex 的公共任务书创建入口 `codex_tasks.prepare_task()` 现统一在取得任务锁、创建任务目录或 `codex_tasks.json` 前执行 96,000 字符请求上下文预检；超限请求不会留下本地工件，也不会连接 RPC。定向 5/5、架构 68/68、默认冒烟 8/8、全量安全自检 3,170/3,170（789.2 秒）通过。详见 `tasks_round/tasks_round_467_result.md`。

- R466 结构治理轮（来源：R461 未完成项的路径权威扫描）：离线“生成编剧任务书”成果包已从旧 `writing/` 目录迁至唯一的 `01剧本准备/` 阶段目录；`writing.prepare()` 继续生成同一任务书、技能位置、资产表和模板，旧目录不再新建。定向 6/6、架构 68/68、默认冒烟 8/8、全量安全自检 3,169/3,169（744.2 秒）通过。详见 `tasks_round/tasks_round_466_result.md`。

- R465 结构治理轮（来源：R464 剩余正式直写扫描）：剪辑优化清单保存已从 `desktop.py` 下沉至既有 `edit_service.save_editing_checklist()`；服务统一定位后期剪辑阶段目录并原子发布，页面仅负责读取与编辑器取值。定向 5/5、架构 67/67、默认冒烟 8/8、全量安全自检 3,168/3,168（747.8 秒）通过。详见 `tasks_round/tasks_round_465_result.md`。

- R464 结构治理轮（来源：R462 剩余正式直写扫描）：手动创意另存已从 `desktop.py` 下沉至既有 `idea_chat.save_manual_creative()`；服务统一分配剧本准备分类目录、自然剧本命名与原子发布，页面只负责示例拦截和编辑状态。定向 63/63、架构 66/66、默认冒烟 8/8 通过；全量安全自检待本轮结束后执行。详见 `tasks_round/tasks_round_464_result.md`。

- R463 结构治理轮（来源：R462 的剩余正式直写扫描）：结构页手改自然剧本改由既有 `script_contract.save_natural_script()` 校验并原子发布，`desktop.py` 仅保留编辑状态与提示；结构化正文或非 Markdown 目标均拒绝写入。定向 45/45、架构 65/65、默认冒烟 8/8、全量安全自检 3,164/3,164（741.4 秒）通过。详见 `tasks_round/tasks_round_463_result.md`。

- R462 结构治理轮（来源：`tasks_round/tasks_round_461_result.md` E2）：配音与字幕页的 SRT、对白脚本正式导出不再由 `desktop.py` 直接落盘；`subtitle_export_service` 统一生成、原子发布至既有字幕阶段目录，并保持估算标记和角色资产显示名。新增服务行为与 UI→服务静态边界回归；定向 36/36、架构 64/64、默认冒烟 8/8、全量安全自检 3,161/3,161（742.9 秒）通过。详见 `tasks_round/tasks_round_462_result.md`。

- R461 结构治理续接：补齐 R458 中断前缺失的验收；架构门禁进程退出码 0、默认冒烟 8/8 通过，故视频选项原子发布边界可作为已验收基线。同期完成优化清单阻塞归类、整改路线与测试迁移盘点；全量安全自检 3,157/3,157 通过（772.3 秒）。详见 `tasks_round/tasks_round_461_result.md`。白模视频真实上传仍需用户对具体素材授权。

- R460 修复轮：按最新截图将主界面根层设置齿轮从 `(154, 8)` 左移至 `(138, 8)`，视觉上贴近应用名右缘且保持 `y=8`，不会遮挡下方文案；设置窗口入口保持不变。真实桌面接缝测试 2/2、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_460_result.md`。

- R459 修复轮：按截图将主界面根层设置齿轮从 `(112, 8)` 右移至箭头所指的 `(154, 8)`；保持 `y=8`，因此不遮挡下方文案，点击仍打开原“设置”窗口。真实桌面接缝测试 2/2、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_459_result.md`。

- R458 结构治理轮（用户中止，待续接验证）：视频页的资产勾选与声音选项不再由 `app.py` 直接改写 `episode.json`，统一由 `video_lifecycle_service.save_video_options()` 原子发布；云端/本地字段口径不变，保存失败恢复内存记录，服务不提交、不上传。定向 71/71 已通过；用户要求停止前，架构门禁与默认冒烟未执行，不得视为本轮完成。详见 `tasks_round/tasks_round_458_result.md`。

- R457 修复轮：按用户要求删除侧栏应用名旁的重复版本号，侧栏宽度恢复 154px；根层设置齿轮左移至 `(112, 8)`，位于应用名右侧，不遮挡下方文案，点击仍打开原“设置”窗口。接缝测试 52/52、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_457_result.md`。

- R456 结构治理轮：本地视频镜头删除的任务状态拦截、`video_deleted` 标记与原子 `episode.json` 发布已迁入 `video_lifecycle_service.mark_video_deleted()`；未知/运行中任务仍拒绝删除，保存失败会恢复内存记录，历史素材和任务记录不删。新增服务行为回归及 UI→服务静态边界。定向 58/58、架构 63/63、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_456_result.md`。

- R455 修复轮：根层齿轮原先放在 `(8, 8)`，会覆盖侧栏标题与下方文案；现给侧栏扩至 184px 并预留根层安全位 `(154, 8)`，齿轮保持最上层、可点开“设置”，且不遮住侧栏或正文。真实接缝测试 52/52、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_455_result.md`。

- R454 修复轮：齿轮不再嵌在可能被裁掉的侧栏标题行，而是直接创建在 `Desktop` 主窗口根层 `(8, 8)`；真实接缝测试锁定主窗口父容器和坐标，确保“齿轮 → 设置”保持最上层可见。同期将首帧“导入/替换”的原子图片写入、旧图回收、JSON 发布与失败回滚收敛至 `keyframe_lifecycle_service.replace_keyframe()`，旧图进入项目回收站。定向 59/59、架构 62/62、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_454_result.md`。

- R453 结构治理轮：首帧恢复的文件移动与 `episode.json` 状态发布已由 `keyframe_lifecycle_service.restore_keyframe()` 统一；优先从项目回收站恢复，旧“历史版本”目录仅作只读兼容，状态保存失败会将刚恢复首帧回收到项目回收站。新增 UI→服务静态边界与失败回归。定向 6/6、架构 61/61、默认冒烟 8/8 通过。主界面“齿轮 → 设置”入口未改动；详见 `tasks_round/tasks_round_453_result.md`。

- R452 修复轮：主界面左侧栏缩至 154px 后，齿轮仍排在“应用名＋版本号”之后而被横向裁掉；现将其固定在同一标题行右侧，设置入口持续可见且仍打开原“设置”窗口。新增窄侧栏布局回归断言。定向 52/52、架构 60/60、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_452_result.md`。

- R451 验证/基线轮：全量安全自检发现旧首帧批量删除测试仍断言已废弃的本地回收目录；已改为验证权威全局回收站中的实际目标文件，不降低“只删高亮行”的断言。定向 17/17、架构 60/60、默认冒烟 8/8 通过；全量安全自检 3,143/3,143 通过（799.5 秒）。主界面“齿轮 → 设置”入口未改动；详见 `tasks_round/tasks_round_451_result.md`。

- R450 结构治理轮（子场景：执行）：首帧删除的回收与 `episode.json` 删除标记已由 `keyframe_lifecycle_service.delete_keyframe()` 统一；JSON 保存失败会恢复首帧和内存状态。主界面“齿轮 → 设置”入口未改动。定向 3/3；架构 60/60、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_450_result.md`。

- R449 结构治理轮（子场景：执行）：资产图片恢复的“回收站取回＋登记表恢复”已由 `asset_batch_service.restore_asset_image()` 统一；登记表保存失败会把刚恢复的图片重新移入回收站，避免文件已恢复而索引未登记。UI 仍负责确认、刷新与提示。主界面“齿轮 → 设置”入口未改动。定向 13/13、架构 59/59、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_449_result.md`。

- R448 结构治理轮（子场景：执行）：资产图片删除的“回收站移动＋登记表清空”已由 `asset_batch_service.remove_asset_image()` 统一；登记表保存失败会恢复刚回收的原图与旧索引，UI 仍负责确认、批量选择、刷新和提示。主界面“齿轮 → 设置”入口未改动。定向 13/13、架构 58/58、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_448_result.md`。

- R447 结构治理轮（子场景：执行）：资产重命名的资产清单、旧名别名与已登记图片索引已从 `desktop.py` 迁至既有 `asset_batch_service.rename_asset()`；两次写入任一步失败会恢复两个原文件。新增行为与静态边界测试。主界面“齿轮 → 设置”入口未改动。定向 5/5、架构 57/57、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_447_result.md`。

- R446 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_445_result.md` 整改路线 1—3）：分镜定稿正文编辑已从 `storyboard_files.py` 的直接写入迁至 `storyboard_edit_service.save_edited_json()`；页面仍负责 JSON 校验、用户确认、刷新与状态文案，服务仅原子保存已校验 JSON 并拒绝非 JSON 目标。新增行为与静态边界测试。主界面“齿轮 → 设置”入口未改动。定向 17/17、架构 56/56、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_446_result.md`。

- R445 只读诊断轮（来源：`tasks_round/tasks_round_418_result.md` J3/K）：重新分类现存 UI 直接写入点。`storyboard_files.py:339` 是分镜文件页唯一直接成果写入，且已有定稿查看/选择/目录/回收服务与行为测试支撑，确定为下一最小服务化闭环；`desktop.py` 资产管理遗留写入仍需另立范围，未与本轮混改。未改 `.py`、未运行测试，详见 `tasks_round/tasks_round_445_result.md`。

- R444 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J3/K）：`storyboard_files.py` 已移除未登记的 `importlib.import_module()`，分镜选择服务改为模块级静态依赖；动态导入门禁的 L4 扫描范围补入该真实页面，防止同类绕行再次漏检。未改 UI 行为、用户数据或主界面“齿轮 → 设置”入口。定向 38/38、架构 55/55、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_444_result.md`。

- R443 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J3/K）：分镜定稿页的“最近查看定稿”偏好写入已从 `storyboard_files.py` 迁至既有 `storyboard_selection.remember_final_view()`；服务验证项目路径并保留其他偏好，页面继续负责选择、预览与编辑正文。主界面“齿轮 → 设置”入口未改动。定向 3/3、架构 55/55、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_443_result.md`。

- R442 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J3/K）：资产批处理窗口不再自行合并或持久化 `asset_batch` 设置；`asset_batch_settings_service` 统一保留非资产偏好、合并批量设置、维护已删除模型标记并以原子写入落盘。窗口仍负责确认框、控件、异步检测与提示，主界面“齿轮 → 设置”入口未改动。服务定向 4/4、架构 54/54、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_442_result.md`。

- R441 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J2/K）：Agent 自动提示词结果导入不再直接发布 JSON、文本或分镜索引；`video_prompt_results.import_result()` 保留校验、占用保护和格式修复原文备份，并委托 `video_prompt_publication.publish()` 原子发布可见成果。定向 14/14、架构 52/52、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_441_result.md`。

- R440 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J2/K）：手工“导入提示词”不再由 `app.py` 直接备份/写入候选 JSON，统一委托 `video_prompt_publication.stage_import()`。该服务仅原子暂存导入记录与旧草稿可恢复历史，不提前更新 `episode.json`；写入失败会恢复旧草稿并清理本轮历史副本。定向 7/7、架构 51/51、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_440_result.md`。

- R439 修复轮：`storage_maintenance.restore_latest_recycled_child()` 保持项目回收站清单优先；当旧项目仅有同目录 `历史版本` 留存时，只读兼容最近的同资产、允许后缀文件。恢复目标已存在则拒绝覆盖，正常删除仍统一走回收服务。资产恢复/回收/视频提示词定向 9/9、架构 50/50、默认冒烟 8/8、全量安全自检 3116/3116（801.7 秒）均通过；详见 `tasks_round/tasks_round_439_result.md`。

- R438 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J2/K）：视频提示词的手工保存和切镜自动保存已统一委托 `video_prompt_publication.publish()`；该服务先发布 JSON、文本和镜头副本，最后更新分镜索引，任一步失败即恢复已有文件和内存索引。视频提示词定向 7/7、架构 50/50、默认冒烟 8/8 通过；组合后的全量安全自检结果见 R439。详见 `tasks_round/tasks_round_438_result.md`。

- R437 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J/K）：剪映交接包的复制、字幕、清单、说明和自动包替换已下沉至 `handoff_service.publish_bundle()`；`desktop.py` 只选择镜头与字幕输入。自动包仍先在暂存目录完成构建，再通过回收服务替换旧包；直接字幕写入已改为原子 `save_bytes()`。交接包 UI 定向 2/2、架构 48/48、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_437_result.md`。

- R436 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J/K）：后期剪辑的 `MASTER.mp4` 现先编码到同目录临时文件并完成媒体核验，再原子替换正式成片，最后经 `Studio.publish_edit_bundle()` 写入绑定的 QC 与剪辑清单；编码/核验失败会清理临时文件且不覆盖旧成片。未调用真实上传或白模服务。剪辑定向 6/6、架构 46/46、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_436_result.md`。

- R435 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J/K）：逐句配音的 MP3 与时间轴登记已收敛为 `tts_api.publish_line()`；音频先原子保存，才原子更新可续跑索引。索引写入失败时旧索引不受损，已发布音频保留。未调用 TTS API。音频/字幕定向 69/69、架构 44/44、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_435_result.md`。

- R434 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J/K）：云端与本地视频轮询在视频完整落盘后，统一经 `Studio.publish_downloaded_video()` 发布 QC 与状态索引；QC 异常仍保留视频并登记为已下载，避免下次轮询重复覆盖成果。未发起云端/ComfyUI 请求或白模上传。视频定向 37/37、架构 43/43、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_434_result.md`。

- R433 结构治理轮（子场景：执行；来源：`tasks_round/tasks_round_418_result.md` J/K）：首帧导入已将“独占发布媒体”与“原子更新分镜关联”拆为 `register()` → `publish_frame_reference()`。关联保存失败时旧分镜 JSON 保持原字节，新生成图保留供用户恢复；未触及批次请求记录或白模上传。首帧定向 31/31、架构 42/42、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_433_result.md`。

- R432 结构治理轮：连贯性台账、Markdown 人读版、共享锚点库和三元组字典已收敛为 `continuity_ledger.publish_bundle()`；逐份原子发布并落盘复核，任一步失败即恢复全量旧内容。兼容入口 `write()` 只能委托该发布包。连续性定向 40/40、架构 41/41、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_432_result.md`。

- R431 只读诊断轮：已建立阶段写入清单并按成果、内部状态、配置和临时文件分类。已收敛的成果族为结构剧本、分镜定稿与资产计划；下一优先成果族为连续性清单（JSON 正文加 Markdown 视图），随后是首帧、视频、音频、剪辑/交付。完成事件仍经 `stage_completion_service`，白模真实上传仍等待授权；详见 `tasks_round/tasks_round_431_result.md`。默认冒烟 8/8 通过。

- R430 结构治理轮：资产计划的名称编号、资产正文、来源及导入进度四份成果已收敛为 `asset_plan.publish_plan_bundle()`。发布前校验内容类型，逐份原子写入并落盘复核；任一写入失败会恢复全部旧内容，新增项受控清理。`sync_plan()` 只能委托此发布包。资产计划定向 82/82、架构 40/40、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_430_result.md`。

- R429 结构治理轮：结构剧本阶段的发布闭环新增失败回归与静态边界。`stage_exec` 只能委托 `script_contract.write_structured_script()`；该发布服务成功调用 `save_text` 后才记录产物血缘，发布失败不会遗留血缘条目。结构剧本定向 16/16、架构 39/39、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_429_result.md`。

- R428 结构治理轮：分镜定稿 JSON 发布的服务边界现由静态门禁锁定，`storyboard_final` 只能委托 `storyboard_storage.publish_final_bundle()`，不再保留未使用的直接 JSON 写入导入。定稿相关 14/14、架构 38/38、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_428_result.md`。

- R427 结构治理轮：资产批处理窗口的类别选择、单项反选、全选/全不选和全选判定已下沉到既有 `asset_batch_selection_service`，窗口只保留 Tk 事件与刷新编排；新增三项无界面回归。资产定向 79/79、架构 37/37、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_427_result.md`。

- R426 修复轮：补齐资产批处理页遗漏的 L4 动态导入入口；工作流设置按需读取已改经 `ui_plugin_registry.module()`，并将资产批处理页纳入同一静态扫描范围。动态导入 3/3、默认冒烟 8/8、架构门禁 37/37 通过；详见 `tasks_round/tasks_round_426_result.md`。

- R425 契约轮：修正 AGENTS 第 2.5 节的过期架构基线 36/36 为实际的 37/37；第 5 节的 19 个架构测试文件与 37 项检查已核对一致。默认冒烟 8/8、架构门禁 37/37 通过；详见 `tasks_round/tasks_round_425_result.md`。

- R424 验证/基线轮：R419—R423 的变更后，默认冒烟 8/8、架构门禁 37/37 均通过；已启动并等待一趟 `run_selftests.py --all --safe` 全量安全回归结束，但其实时标准输出未被调用会话保留，不能据此重报全量用例总数或将历史 3,059 条基线更新为新数字。详见 `tasks_round/tasks_round_424_result.md`。

- R423 结构治理轮（子场景：执行）：资产批处理页的技能批处理和原生控件两处 L4 延迟加载均已登记并经 `ui_plugin_registry.module()` 调用。动态导入 3/3、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_423_result.md`。

- R422 结构治理轮（子场景：执行）：分镜定稿的 `assets.json` 与 `episode.json` 原子发布、落盘复核和失败回滚已收敛至 `storyboard_storage.publish_final_bundle()`；`storyboard_final` 保留领域校验与来源/回收编排。定稿 13/13、架构 37/37、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_422_result.md`。

- R421 结构治理轮（子场景：执行）：完成统一阶段写入的入口分批，资产批次台账已收敛；下一批仅处理剧本结构和分镜产物，明确排除配置、密钥、诊断、缓存、临时文件与未授权白模上传。未改生产代码或测试；详见 `tasks_round/tasks_round_421_result.md`。

- R420 结构治理轮（子场景：执行）：为 R419 的资产批次台账入口收敛补齐服务输入校验与静态边界门禁，执行器必须经状态服务读写台账。资产定向 77/77、架构 37/37、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_420_result.md`。

- R419 结构治理轮（子场景：执行）：资产批次执行器的 `资产批量记录.json` 已不再自行拼路径或直接写入，统一经 `asset_batch_state_service.read_ledger()` / `save_ledger()` 读写；底层继续复用 `agent.core.save()` 的原子发布。该收敛只覆盖资产批次台账，尚不足以关闭全阶段统一写入总待办。资产定向 75/75、架构 36/36、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_419_result.md`。

- R418 只读诊断轮：已审计 R182 优化清单、写入链、View/Service/Adapter 边界与现有架构门禁。确认核心原子写入基元已集中在 `agent/core.py`，但“统一阶段写入服务”仍未形成可关闭的阶段产物闭环；下一实际轮优先处理资产批次状态或分镜结构化成果之一。未改生产代码、状态以外的权威文档或用户数据，未运行测试；详见 `tasks_round/tasks_round_418_result.md`。

- R417 功能轮：交互式工作流的首次任务继续使用完整本地接续文件；后续任务改用短续接摘要，只保留阶段、进度文件、成果计数、读取异常状态与按需读取动作，避免重复发送完整约束和索引。上下文定向 113/113、架构 36/36、默认冒烟 8/8 通过。

- R416 修复轮：模型后台与交互式工作流均在启动前按 `stage_parallel.CONFIG` 预留阶段槽位，并受全局 8 槽上限保护；满额时提示用户等待。槽位在后台任务结束、交互进程停止或启动失败时释放，Qwen 交互进程也重新登记到统一台账。工作流定向 84/84、架构 36/36、默认冒烟 8/8 通过。

- R415 功能轮：新增轮次与基线架构门禁。状态中的当前轮次必须等于最新 `tasks_round` 结果轮次加一；默认冒烟保持 8 项，架构门禁不得低于历史 14 项。当前架构门禁 36/36、默认冒烟 8/8 通过。

- R414 功能轮：资产页的已导入图片删除、批量删除和确认重做均改为统一项目回收站；回收服务可按精确路径或资产目录/ID/图片后缀恢复最近单项，不会连带恢复同批其他文件，目标冲突仍安全拒绝。定向 20/20 与补充删除—恢复回归 8/8、架构 34/34、默认冒烟 8/8 通过。

- R413 功能轮：新增响应式布局架构契约，锁定桌面、视频工作台、分镜文件和资产批处理四个主要页面复用 `responsive_ui.FlowBar`，以及该组件保持请求按钮宽度、窄窗口换行与受控定位的实现。未改生产代码；全页面小窗口人工体验验收仍是待办。架构 34/34、默认冒烟 8/8 通过。

- R412 验证/基线轮：新增 `test_platform_process_boundary.py`，直接 `subprocess.Popen` 仅允许在 `platform_tools` 与六个受控后台边界；可见本地程序启动都经平台适配器。平台适配优化项已闭合；架构 32/32、默认冒烟 8/8 通过。

- R411 兼容/平台适配轮：Codex/Claude 的可见交互 CLI 启动已接入 `platform_tools.launch_windows_app()`；仅实际宿主启动失败可进入既有兼容 API 回退，非 Windows 或程序缺失直接给出可操作提示。工作流定向 79/79、默认冒烟 8/8 通过。

- R410 兼容/平台适配轮：Blender 的可见启动已接入 `platform_tools.launch_windows_app()`；原有已启动进程去重、窗口检测和 `.blend` 工程校验保持不变。Blender 接缝 1/1、平台定向 10/10、受影响冒烟 9/9、默认冒烟 8/8 通过。

- R409 兼容/平台适配轮：Qwen Code 的可见交互启动已接入 `platform_tools.launch_windows_app()`，将 Windows 宿主、可执行文件、命令参数、工作目录、环境与启动失败提示集中到平台边界；启动前也会先执行阶段上下文预算预检，超限不创建任务文件或进程。平台定向 10/10、Qwen 定向 2/2、受影响冒烟均 9/9、默认冒烟 8/8 通过。

- R408 兼容/平台适配轮：后期剪辑页的剪映启动已移至 `platform_tools.launch_windows_app()`；仅在 Windows 启动已定位可执行文件，缺失文件、非 Windows 或系统启动失败均返回可操作提示。平台测试 10/10、受影响冒烟 9/9、默认冒烟 8/8 通过。

- R407 契约轮：AGENTS.md 第 5 节已从“分层/循环/路径/删除四类”更新为完整架构门禁范围，登记当前 `tests/architecture/` 的 15 个测试文件、31 项检查及四个覆盖分组；并要求未来同轮同步更新清单、基线与报告。架构 31/31、默认冒烟 8/8 通过。

- R406 性能/资源轮：后台与交互式阶段引擎启动现共用 `workflow_context_budget.ensure_request_context()`；超过 96,000 字符会在启动进程或交互客户端前给出缩短/拆分/摘要提示。工作流定向 78/78、默认冒烟 8/8 通过；首次按模块名的空筛选已更正为 `workflow` 测试组，未改断言。

- R405 性能/资源轮：超过 512 KiB 的剧本预览仍在后台读取，并在 Tk 空闲回调中以 32 KiB 文本块投递；切换文件、进入编辑态或窗口销毁会使过期结果失效。分镜目录监听既有的后台全量扫描与主线程批量提交保持不变。预览服务 4/4、受影响冒烟 9/9、默认冒烟 8/8 通过。

- R404 性能/资源轮：`file_cache` 在文件签名变化时复核 SHA-256 内容哈希；同内容的外部重写复用既有 JSON 解析对象、文本和字节对象，内容实际变化才重新解析。现有分镜后台目录扫描与大文本后台预览不变。缓存定向 22/22、受影响冒烟 9/9、默认冒烟 8/8 通过。

- R403 兼容/平台适配轮：已经现有产品入口启动本机 Comfy Desktop，并只读核验 `system_stats`、节点类型与已保存的 Flux Klein / Qwen 编码器 / Flux VAE 配置。服务已就绪，三项模型均在相应节点清单中存在；未提交素材或生成任务。本地 Flux/ComfyUI 真实启动阻塞已解除，定向 95/95、默认冒烟 8/8 通过。

- R402 验证/基线轮：已校正入口与状态中的过期架构基线；当前架构门禁为 31/31 全绿，全量安全自检权威最近结果为 3,059 条全绿，默认冒烟为 8/8。未改生产代码。

- R401 功能轮：资产跨重启续跑台账的物理清除已迁至 `storage_maintenance.clear_generated_workflow_state()`；入口只允许项目 `workflows/资产续跑台账.json` 的精确内部状态路径，拒绝任意路径、符号链接和用户可见成果。回收架构门禁现可识别 `path(...).unlink()` 一类间接接收者调用。定向 17/17、架构 31/31、默认冒烟 8/8 通过。

- R400 验证/基线轮：阶段模型来源定向回归 95/95、默认冒烟 8/8 通过；本机已发现 Comfy Desktop，但按应用配置探测 `/system_stats` 返回 HTTP 502，故 Flux 的真实启动验收仍未通过，未启动软件或生成素材。

- R399 功能轮：完成旧接口兼容收敛；`ImportError` 仅许可于带淘汰日期的历史 facade、平台能力探测、解释器能力探测和成果核验失败边界，新增架构门禁防止业务模块自行捕获。架构 31/31、定向 26/26、默认冒烟 8/8 通过。

- R398 功能轮：新增正式成果写入静态边界门禁；根目录生产模块的直接覆盖写入仅允许原子替换、模型响应校验发布和快捷方式临时脚本等受控边界，其他模块须走 `agent.core` 或 `line_endings`。架构 28/28、写入相关定向 144/144、默认冒烟 8/8 通过。

- R397 状态接续轮：清理 3 项已由后续修复和 R396 全量安全回归验证解决的历史阻塞（首帧夹具兼容、手动计划标签兼容、分镜续跑状态）；白模视频上传真机验收仍等待用户指定镜头与上传授权。

- R396 状态接续轮：修复 R395 结果文件已存在但状态仍停在 394 的轮次不同步；全量安全自检 3,059/3,059 通过（788.2 秒，0 个失败文件），默认冒烟 8/8 通过。白模视频上传真机验收仍等待用户授权。

- R395 功能轮：新建 `_supervisor/README.md`，规定该目录仅放监督 Codex 的建议文件；执行 Codex 不读、不写，由人工转交。按本轮要求未运行测试。

- R394 功能轮：`PROJECT_MAP.md` 的“11 阶段页面/目录”已校正为 12；新增 7 条 AGENTS、地图、架构与运行时阶段数/权威模块一致性测试，7/7 通过。架构门禁共 25 项，22 通过；余下 3 项为 R393 已记录的动态导入、完成事件与回收服务生产违规，本轮未改生产代码。

- R393 功能轮：新增/扩展动态导入、阶段命令、完成核验、回收服务四类架构静态门禁；`smoke_test.py --architecture` 发现 3 类既存契约违规（动态导入 1 处、UI 完成事件 2 处、物理删除 21 处），均已记录文件:行号；生产 `.py` 未修改。

- R392 契约收敛：`AGENTS.md` 已纳入阶段启动、动态导入、阶段路径、完成核验及回收服务的唯一入口；状态更新、删除边界、结构治理自检分级和新增轮次类型均已按 R391 修订方案更新。默认冒烟 8/8、架构冒烟 14/14。

- 产品：Windows Tkinter「漫剧制作助手」，零第三方依赖，12 阶段由 `skill_orchestrator` 执行；“剧本结构”位于剧本准备与初步分镜之间。剧本输入与结构化输出由 `script_contract`、`stage_path_service` 解析；旧 `writing/` 仅作历史读取兼容。当前可选 SKILL 以 `skill_registry` 懒加载登记结果为准。
- 三虎：带前缀播报和 UTF-8 日志、检查点/恢复、12 阶段 YAML 模板、手动/全自动模式、暂停/阻塞控制、资产跨重启续跑；`auto_*_var` 的写入权只属于三虎，页面不显示自动制作勾选框。
- 剧本准备：模型/用户气泡左右分列，模型名、折叠、思考提示、原位编辑、拖选复制、右键整条复制/删除及恢复最近删除、输入草稿持久化、输入框自适应和文件表刷新均已实现。每个模型保留独立聊天页并使用稳定浅色主题；下方无标题文件表按项目设定、项目大纲、项目剧本分为三列独立紧凑排列，单元格仅显示文件名，不列出用户简报、聊天记录或无关文件。
- 模型：模型管理是唯一池；阶段按所选厂商/协议/模型/密钥/SKILL 直连 API，不回退到 Qwen。GPT API 与 ChatGPT Desktop 归类为 GPT；自定义 Provider 与模型保存后刷新阶段配置。
- Claude：Messages 调用只显示可见正文；thinking/signature 不进入聊天框。剧本阶段仅可读 `writing/`、`data/项目接续.json`，仅可写 `writing/`，不访问资产清单。
- HOLLMWOOD：LLM 请求在既有后台线程运行；角色进度通过 `queue.Queue` 交给 Tk 主线程每 100ms 消化，并写入三虎进度日志。中断会阻止当前请求进入后续角色及 `script_raw.md` 落盘。
- 文件/删除：生成剧本会刷新文件表；允许删除最后一份剧本、无 `episode.json` 的残留项目链接及其项目目录。
- Python：测试统一使用 `D:\漫剧制作助手\运行环境\Python\python.exe`；Round 136 已实测全局 Python 3.14 与项目内置解释器均可初始化 Tcl/Tk。
- Round 131 二次核验：自动粗剪/交接标记、JSON 导入、创意历史和参考脚本扫描均以 `project_stages` 为唯一新路径；剧本/分镜目录清单继续只读兼容旧目录，项目接续资产优先读取 `04资产管理/assets.json`。

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

以下保留历史完成记录，按各段轮次理解；当前最新完成项与验证结果见文首轮次头、[验证基线](#验证基线)及[优化队列](维护记录/优化待办队列.md)，不以旧章节名称推断“最近”。

- Round 390（P1 可维护性）：完成 R386--R390 的状态接续；云朵框的形状规则、主体图元、图元命中和公开纯函数兼容契约均具备无 Tk 测试边界，未扩展修改 Tk 生命周期或其他页面。云朵框定向/公开契约 14/14、架构层级与默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_386_result.md` 至 `tasks_round/tasks_round_390_result.md`。
- Round 385（P1 可维护性）：完成 R381--R385 的状态接续；`run_selftests.py` 保存最近五次可比耗时的中位基线；云朵框的文本、图元几何和尾巴曲线均拆为无 Tk 模块且保留原公共入口。自检 16/16、云朵框定向 7/7、架构层级与默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_381_result.md` 至 `tasks_round/tasks_round_385_result.md`。
- Round 380（P1 状态接续）：登记 P2-1 剩余死符号清理与 P3 重复块复核；SKILL 110/110、回收 8/8、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_380_result.md`。
- Round 379（P3 代码审计）：复核 `pet_ui.py` 旧贴纸重复块清单已与当前共用逻辑不符，未做猜测性 Tk 重构；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_379_result.md`。
- Round 378（P2 代码精简）：完成五项死符号候选收尾审计，保留仍被调用的 `asset_thumbs.forget`；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_378_result.md`。
- Round 377（P2 代码精简）：删除无调用点的单路径回收包装 `storyboard_files.recycle_file`；回收 8/8、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_377_result.md`。
- Round 376（P2 代码精简）：删除无调用点的 `skill_tools.page_of`；SKILL 110/110、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_376_result.md`。
- Round 375（P1 状态接续）：登记优化模式容错与 P2-1 死符号审计/清理；性能服务 13/13、预演相关 76/76、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_375_result.md`。
- Round 374（P2 代码精简）：删除无静态调用点的 `previs_progress.ProgressCells`，保留预演进度服务协议；预演相关 76/76、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_374_result.md`。
- Round 373（P2 代码审计）：复核 `model_pool.has_local_key` 已在当前代码库中不存在，无需重复删除；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_373_result.md`。
- Round 372（P2 代码审计）：复核死符号清单，发现 `asset_thumbs.forget` 已有桌面、测试与基准调用，其余候选待独立兼容性审计；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_372_result.md`。
- Round 371（P2 优化模式可靠性）：优化报告缺失可比耗时指标时安全写入零退化摘要；服务/路由 13/13、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_371_result.md`。
- Round 370（P1 状态接续）：登记三虎优化模式的长列表入口、显式指令、帮助发现性和失败台账边界；服务/路由 12/12、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_370_result.md`。
- Round 369（P2 优化模式可靠性）：优化子进程失败时仅返回截短提示，绝不将子进程输出写入项目优化台账；服务/路由 12/12、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_369_result.md`。
- Round 368（P2 优化模式可发现性）：三虎帮助文本登记增量自检和优化检查指令；服务/路由 11/11、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_368_result.md`。
- Round 367（P2 优化模式接缝）：新增显式“运行长列表优化检查”指令，避免普通短检查隐式触发耗时列表测量；服务/路由 10/10、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_367_result.md`。
- Round 366（P2 优化模式服务）：新增 300/1000 行资产列表基准的安全调度入口，运行报告仍只写项目；服务/路由 9/9、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_366_result.md`。
- Round 365（P1 状态接续）：登记三虎优化模式的离线比较、可重定向基准输出、短基准轮询与聊天接缝；服务/路由 8/8、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_365_result.md`。
- Round 364（P2 优化模式接缝）：三虎聊天可按用户指令运行短离线优化检查，既有心跳轮询并仅播报超过阈值的退化；服务/路由 8/8、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_364_result.md`。
- Round 363（P2 优化模式服务）：新增短启动基准子进程调度，运行报告写入项目后与只读维护基线比较；服务 7/7、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_363_result.md`。
- Round 362（P1 性能基准）：两份离线基准脚本支持显式运行报告输出路径，自动检查不再覆盖维护基线；编译、参数契约、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_362_result.md`。
- Round 361（P2 优化模式）：新增 L2 离线基准比较服务，仅提示超过 40% 的耗时退化并保存脱敏摘要台账；服务 6/6、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_361_result.md`。
- Round 360（P1 状态接续）：登记三虎测试模式的服务、心跳接缝、CLI 兼容和启动命令回归；服务/自检调度 20/20、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_360_result.md`。
- Round 359（P2 测试模式回归）：验证三虎派发 `run_selftests.py --incremental`，并解析重复次数；服务/自检调度 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_359_result.md`。
- Round 358（P2 测试模式可靠性）：将 `--incremental` 设为显式 CLI 兼容参数，避免被误当筛选词而运行 0 个文件；服务/自检调度 19/19、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_358_result.md`。
- Round 357（P2 测试模式）：三虎聊天可启动增量自检，既有心跳轮询子进程并播报成功率/失败用例；服务与路由 4/4、宠物 Agent 77/77、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_357_result.md`。
- Round 356（P2 测试模式）：新增 L2 `pet_test_service`，记录增量自检重复运行、成功率和脱敏失败用例台账；服务 2/2、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_356_result.md`。
- Round 355（P1 状态接续）：登记本批未使用导入、两处轻量重复块和配置职责说明；模型提醒 121/121、列宽 17/17、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_355_result.md`。
- Round 354（P2 配置治理）：新增三类配置文件的职责、读写入口和密钥边界说明，不合并不同生命周期的配置；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_354_result.md`。
- Round 353（P3 代码精简）：`responsive_ui` 的两处防抖配置绑定改由同一内部调度器承载；列宽 17/17、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_353_result.md`。
- Round 352（P3 代码精简）：`stage_models` 的模型提醒会话集合初始化收口至 `_model_asked()`；模型提醒 121/121、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_352_result.md`。
- Round 351（P2 代码精简）：移除 `stage_exec` 与 `skill_tools` 的三处当前未使用导入；SKILL 110/110、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_351_result.md`。
- Round 350（P1 状态接续）：登记本批正式写入边界复核，以及后期剪辑和创意文本读取/保存比较的缓存收口；缓存 20/20、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_350_result.md`。
- Round 349（P1 性能）：创意保存的“内容未变”比较复用文本缓存，未变文件不再重复读取；`desktop.py` 编译通过、缓存 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_349_result.md`。
- Round 348（P1 性能）：创意简报读取复用文本缓存，避免同一轮界面刷新重复读取；`desktop.py` 编译通过、缓存 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_348_result.md`。
- Round 347（P1 性能）：后期剪辑优化清单预览改由文本缓存读取，避免重复打开未变化文件；`desktop.py` 编译通过、缓存 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_347_result.md`。
- Round 346（P0 可靠性）：复核正式代码的文本/字节写入边界，未发现绕过 `write_text` 等统一写入接口的直接写入；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_346_result.md`。
- Round 345（P1 状态接续）：登记本批自动采用分镜与自动补首帧轮询决策、接缝、架构边界和回归；首帧 29/29、采用接缝 1/1、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_345_result.md`。
- Round 344（P1 多职责函数治理）：自动补首帧轮询的静默、重复跳过与阻塞提示决定收口至 `keyframe_batch`；首帧 29/29、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_344_result.md`。
- Round 343（P1 测试保障）：自动采用分镜桌面接缝复验模式开关、采用轮询和工作集同步；接缝 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_343_result.md`。
- Round 342（P0 架构文档一致性）：架构文档登记 `storyboard_adoption_service` 的无人值守分镜采用轮询决策职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_342_result.md`。
- Round 341（P0 视图/服务拆分）：自动采用分镜的定稿占用等待、重复跳过与待写入重扫判断迁入 L2 `storyboard_adoption_service`；服务 1/1、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_341_result.md`。
- Round 340（P1 状态接续）：登记本批无人值守自动定稿决策、桌面接缝、架构边界、派发签名与重复优先级回归；服务与桌面接缝 2/2、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_340_result.md`。
- Round 339（P1 测试保障）：补齐自动定稿重复签名优先于生产占用等待的直接回归；服务 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_339_result.md`。
- Round 338（P1 测试保障）：补齐自动定稿派发决策回传当前签名的直接回归；服务 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_338_result.md`。
- Round 337（P0 架构文档一致性）：架构文档登记 `final_service` 的自动定稿重复跳过、生产占用等待和派发决定职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_337_result.md`。
- Round 336（P0 视图/服务拆分）：自动定稿的重复、生产占用等待和派发判断迁入 L2 `final_service`，桌面层保留目标扫描、后台定稿和收尾同步职责；服务与桌面接缝 2/2、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_336_result.md`。
- Round 335（P1 状态接续）：登记本批无人值守自动粗剪决策、桌面接缝、架构边界、摘要去重和损坏标记容错回归；服务与桌面接缝 2/2、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_335_result.md`。
- Round 334（P1 稳定性）：补齐自动粗剪完成标记损坏时不阻断当前摘要派发的直接回归；服务 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_334_result.md`。
- Round 333（P1 测试保障）：补齐旧粗剪完成摘要不得阻断新摘要派发的直接回归；服务 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_333_result.md`。
- Round 332（P0 架构文档一致性）：架构文档登记 `edit_service` 的无人值守自动粗剪等待、完成标记去重和派发决定职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_332_result.md`。
- Round 331（P0 视图/服务拆分）：自动粗剪的重复、等待、完成标记和派发判断迁入 L2 `edit_service`，桌面层保留对齐工作集、后台拼接和落盘职责；服务与桌面接缝 2/2、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_331_result.md`。
- Round 330（P1 状态接续）：登记本批无人值守交接包决策、桌面接缝、架构边界与完成摘要去重回归；服务 1/1、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_330_result.md`。
- Round 329（P1 测试保障）：补齐旧完成摘要不得阻断新交接包派发的直接回归；服务 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_329_result.md`。
- Round 328（P0 架构文档一致性）：架构文档登记 `handoff_service` 的无人值守交接包等待、完成标记去重和派发决定职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_328_result.md`。
- Round 327（P1 测试保障）：自动交接包桌面接缝复验未验收等待、验收后整理、重复去重和用户同名目录保护；接缝 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_327_result.md`。
- Round 326（P0 视图/服务拆分）：无人值守交接包的等待、重复、已完成和派发判断迁入 L2 `handoff_service`，桌面层保留复制、落盘与线程职责；服务 1/1、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_326_result.md`。
- Round 325（P1 状态接续）：登记本批资产自动批次去重、重试决定、UI 接缝与架构边界；资产与 UI 接缝 20/20、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_325_result.md`。
- Round 324（P0 架构文档一致性）：架构文档登记 `asset_batch_service` 的无人值守资产计划、设置快照去重与重试决定职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_324_result.md`。
- Round 323（P1 多职责函数治理）：自动资产批次的去重、重试上限及派发决定已收口至 `asset_batch_service`，UI 接缝测试改为替换实际 L3 执行器；资产与 UI 接缝 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_323_result.md`。
- Round 322（P1 测试保障）：补齐生图设置变化必须改变资产无人值守批次指纹的服务回归；资产 18/18、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_322_result.md`。
- Round 321（P1 多职责函数治理）：资产无人值守批次的缺图清单与设置快照去重键已迁入 `asset_batch_service`；资产 17/17、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_321_result.md`。
- Round 320（P1 状态接续）：登记本批自动视频轮询决策、架构边界与静默契约；视频 35/35、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_320_result.md`。
- Round 319（P1 测试保障）：补齐自动视频没有待提交、待查询或跳过镜头时保持静默的决策契约；视频 35/35、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_319_result.md`。
- Round 318（P0 架构文档一致性）：架构文档明确 `local_video` 负责自动视频计划、跳过原因与轮询决策的无 Tk 边界；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_318_result.md`。
- Round 317（P1 多职责函数治理）：自动视频轮询的提示、重复派发跳过和执行决策已收口至 `local_video`；视频 35/35、桌面接缝 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_317_result.md`。
- Round 316（P1 多职责函数治理）：自动视频跳过提示与去重键已收口至 `local_video`，桌面层仅展示结果；视频 34/34、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_316_result.md`。
- Round 315（P1 状态接续）：登记本批首帧无人值守批次指纹与本地 ComfyUI 设置校验收口；首帧 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_315_result.md`。
- Round 314（P1 稳定性）：仅含空白的本地 ComfyUI 设置会被识别为缺失，避免无人值守错误启动；首帧 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_314_result.md`。
- Round 313（P1 多职责函数治理）：本地 ComfyUI 自动首帧必填设置校验已收口至执行器，桌面预检复用同一规则；首帧 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_313_result.md`。
- Round 312（P1 测试保障）：补齐资产就绪变化必须改变首帧无人值守批次指纹的服务回归；服务 2/2、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_312_result.md`。
- Round 311（P1 多职责函数治理）：首帧无人值守批次指纹已迁入既有 `keyframe_batch` 服务，桌面兼容入口仅委派；服务与 UI 接缝 2/2、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_311_result.md`。
- Round 310（P1 状态接续）：登记本批自动白模设置解析、异常契约、畸形分镜容错和架构职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_310_result.md`。
- Round 309（P0 架构文档一致性）：架构文档明确 `previs_routing` 的无人值守候选、首帧等待、提示/去重和注入式引擎解析职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_309_result.md`。
- Round 308（P1 稳定性）：白模路由读取分镜时跳过畸形镜头条目，保留有效镜头继续分流；预演 47/47、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_308_result.md`。
- Round 307（P1 测试保障）：补齐未知白模引擎配置的拒绝契约；预演 46/46、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_307_result.md`。
- Round 306（P1 多职责函数治理）：无人值守白模引擎设置解析已收口至注入式路由函数；预演与桌面接缝 47/47、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_306_result.md`。
- Round 305（P1 状态接续）：登记本批自动白模无人值守路由收口与回归结果；默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_305_result.md`。
- Round 304（P1 多职责函数治理）：自动白模派发批次的稳定去重键已收口至 `previs_routing`，桌面层仅消费结果；预演与桌面接缝 46/46、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_304_result.md`。
- Round 303（P1 测试保障）：补齐空值或无镜头编号输入不得进入自动白模候选的直接回归；预演 43/43、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_303_result.md`。
- Round 302（P1 多职责函数治理）：自动白模的可展示提示和提示去重指纹已收口至路由模块；预演与桌面接缝 44/44、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_302_result.md`。
- Round 301（P1 多职责函数治理）：无人值守白模候选、首帧等待及中等动作分流已收口至无 Tk 路由模块；预演与桌面接缝 44/44、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_301_result.md`。
- Round 300（P1 状态接续）：登记本批阶段成果核验、分镜统计服务迁移和写入审计；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_300_result.md`。
- Round 299（P0 架构文档一致性）：架构文档补充 `storyboard_rows_service` 的首帧统计职责；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_299_result.md`。
- Round 298（P0 视图/服务拆分）：分镜镜头／真实首帧统计已从 `pet_ui` 迁入无 Tk 的 `storyboard_rows_service`，UI 保留兼容委派；服务与 UI 10/10、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_298_result.md`。
- Round 297（P0 写入服务审计）：生产阶段模块未发现尚存的直接正式 `write_text`/`open(..., "w")` 写入点，现有写入仍经原子或行尾校验服务；未改业务语义。详见 `tasks_round/tasks_round_297_result.md`。
- Round 296（P0 架构文档一致性）：架构文档已登记阶段成果核验 L3 服务与视频回调边界；架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_296_result.md`。
- Round 295（P1 状态接续）：登记本批 facade 收敛与阶段成果核验服务拆分；服务与接缝 16/16、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_295_result.md`。
- Round 294（P1 多职责函数治理）：阶段成果核验服务的媒体目录／扩展名规则已独立抽取；服务与接缝 16/16、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_294_result.md`。
- Round 293（P1 测试保障）：补齐桌面视频就绪回调的无 Tk 服务回归；服务与接缝 15/15、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_293_result.md`。
- Round 292（P0 视图/服务拆分）：阶段成果核验已从 `pet_ui` 提取为无 Tk 的 L3 服务，视频状态经回调注入；服务 2/2、接缝 12/12、架构 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_292_result.md`。
- Round 291（P1 旧接口 facade）：资产统计可选服务容错已集中到 `legacy_compat`，页面仅委派调用；定向 77/77、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_291_result.md`。
- Round 290（P1 状态接续）：登记本批旧任务恢复边界拆分与回归结果；资产 72/72、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_290_result.md`。
- Round 289（P1 测试保障）：补齐未确认提交不得重复提交的直接回归；资产 72/72、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_289_result.md`。
- Round 288（P1 测试保障）：补齐旧任务恢复身份不一致时的拒绝回归；资产 71/71、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_288_result.md`。
- Round 287（P1 测试保障）：补齐匹配旧任务可接续记录的直接回归；资产 70/70、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_287_result.md`。
- Round 286（P1 多职责函数治理）：从资产批执行主流程提取旧任务恢复兼容性校验；资产 69/69、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_286_result.md`。
- Round 285（P1 状态接续）：登记本批资产批执行边界拆分与回归结果；资产 69/69、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_285_result.md`。
- Round 284（P1 测试保障）：补齐任务结果轮询的完成及超时直接回归；资产 69/69、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_284_result.md`。
- Round 283（P1 多职责函数治理）：从资产批执行主流程提取单资产结果轮询；资产 67/67、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_283_result.md`。
- Round 282（P1 测试保障）：补齐 Comfy 就绪等待超时的直接回归；资产 67/67、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_282_result.md`。
- Round 281（P1 多职责函数治理）：从资产批执行主流程提取 Comfy 就绪等待，并验证停止中断；资产 66/66、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_281_result.md`。
- Round 280（P1 多职责函数治理）：资产批执行的筛选、预检和恢复配置快照均已拆出纯函数并完成本批回归；资产 65/65、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_280_result.md`。
- Round 279（P1 测试保障）：补齐恢复一致性配置快照字段的直接回归；资产 65/65、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_279_result.md`。
- Round 278（P1 多职责函数治理）：从资产批执行主流程提取恢复一致性生成配置快照；资产 64/64、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_278_result.md`。
- Round 277（P1 测试保障）：预检错误汇总已有直接回归；资产 64/64、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_277_result.md`。
- Round 276（P1 多职责函数治理）：资产批执行的结构化预检提取为纯函数；资产 63/63、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_276_result.md`。
- Round 275（P1 多职责函数治理）：资产批执行的纯筛选边界已有直接回归，后续可继续从预检、提交和台账状态机分段拆分；资产 63/63、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_275_result.md`。
- Round 274（P1 测试保障）：新增资产可执行筛选的直接测试，确保普通道具及已有图片均不进入提交队列；资产 63/63、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_274_result.md`。
- Round 273（P1 多职责函数治理）：从资产批执行主流程提取无副作用的 `eligible_items()` 筛选边界；资产 62/62、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_273_result.md`。
- Round 272（P1 多职责函数治理）：完成资产批执行热点职责审查，明确后续按筛选/预检/提交恢复/轮询/导入台账拆分；未改业务语义。详见 `tasks_round/tasks_round_272_result.md`。
- Round 271（P0 架构文档一致性）：架构文档同步资产 L3 编排与执行器边界；分层/循环测试 2/2、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_271_result.md`。
- Round 270（P0 架构治理复验）：资产批处理拆分后的全套架构门禁 14/14 通过，默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_270_result.md`。
- Round 269（P1 测试保障）：无人值守资产批生成回归改为直接覆盖 L3 编排服务；定向 64/64、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_269_result.md`。
- Round 268（P0 架构层级治理）：资产批执行器登记为 L3，资产规则服务与执行器的依赖关系持续受层级门禁保护；定向 64/64、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_268_result.md`。
- Round 267（P0 架构层级治理）：无人值守资产批编排从 L2 规则服务迁至独立 L3 服务，消除资产批执行循环依赖；资产定向 64/64、架构 14/14、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_267_result.md`。
- Round 266（P0 架构层级治理）：白模预演进度 UI 适配模块登记为 L4；定向 41/41、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_266_result.md`。
- Round 265（P0 视图/服务拆分）：白模 Blender 进度发布和原子落盘迁至 L2 进度服务，原模块仅保留 UI 覆盖层及兼容导出；定向 67/67、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_265_result.md`。
- Round 264（P0 视图/服务拆分）：白模进度文件读取、帧数校验和状态映射迁至 L2 纯服务，并纳入层级门禁；定向 66/66、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_264_result.md`。
- Round 262（P0 架构层级治理）：白模预演监控服务纳入 L3 门禁，防止后台流程回流 UI 依赖；定向 27/27、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_262_result.md`。
- Round 261（P0 架构层级治理）：在线白模窗口从 L2 路由层移回 L4 页面，路由层改依赖白模服务；定向 67/67、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_261_result.md`。
- Round 260（P1 测试保障）：补齐白模批任务服务的直接用例，验证冻结清单仅含选中镜头且变更镜头会拒绝派发；定向 68/68、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_260_result.md`。
- Round 259（P0 架构层级治理）：白模批任务构建迁至 L3 服务，自动编排不再导入 L4 页面，并纳入层级门禁；定向 69/69、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_259_result.md`。
- Round 258（P0 门面收敛）：本地白模页面和自动编排直接依赖 `white_model_service`，不再经由 `white_model` UI 门面；定向 66/66、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_258_result.md`。
- Round 257（P0 视图/服务拆分）：剧本结构页的可见文件选择校验迁至无 Tk 工作区服务；定向 25/25、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_257_result.md`。
- Round 256（P0 视图/服务拆分）：剧本结构页的来源/输出目录、兼容回退和当前来源补位迁至无 Tk 工作区服务；定向 24/24、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_256_result.md`。
- Round 255（P0 视图/服务拆分）：剧本文件列表的分类、稳定项 ID、文件名和时间标签组装迁至无 Tk 服务；定向 9/9、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_255_result.md`。
- Round 254（P0 视图/服务拆分）：剧本删除计划统一提供经校验路径集与“是否删除全部”标记，单删/批删共享判定；定向 8/8、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_254_result.md`。
- Round 253（P0 视图/服务拆分）：剧本重命名的路径边界、文件名和目标冲突校验迁至无 Tk 服务；定向 7/7、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_253_result.md`。
- Round 252（P0 视图/服务拆分）：剧本批量删除的勾选优先、当前高亮回退及路径校验迁至无 Tk 服务；定向 6/6、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_252_result.md`。
- Round 251（P0 视图/服务拆分）：剧本准备页的初始创意文件选择（分类创意、旧文件回退、默认路径）迁至无 Tk 服务；定向 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_251_result.md`。
- Round 250（P1 性能）：分镜下游选择列表每份 JSON 只读取一次；定向 24/24、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_250_result.md`。
- Round 249（P0 视图/服务拆分）：资产批量工作流预选的初始排除规则迁至无界面服务；定向 67/67、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_249_result.md`。
- Round 248（P0 视图/服务拆分）：已采用分镜的下游选择标签、排序与当前项定位迁至无界面服务；定向 23/23、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_248_result.md`。
- Round 247（P1 测试保障）：补齐资产批量选择服务的无 Tk 单元测试；定向 66/66、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_247_result.md`。
- Round 246（P0 视图/服务拆分）：资产批量范围标签与可选/待生成资产筛选迁至无界面服务；定向 63/63、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_246_result.md`。

- Round 245（P0 视图/服务拆分）：阶段执行上下文与编排器创建迁至无面板依赖的编排服务，`stage_exec` 不再导入配置面板；定向 125/125、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_245_result.md`。
- Round 244（P0 架构层级治理）：按实际 Tk 界面职责将本地视频与白模模块登记为 L4；定向 73/73、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_244_result.md`。
- Round 243（P0 视图/服务拆分）：白模记录、目录和 Blender 查找迁至无 Tk 服务，参考视频模块直接使用服务；定向 40/40、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_243_result.md`。
- Round 242（P0 视图/服务拆分）：云视频供应商常量与标签查询下沉服务，导航页直连服务；定向 41/41、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_242_result.md`。
- Round 241（P0 视图/服务拆分）：云视频供应商标签、会话目录和已保存供应商查询下沉服务；定向 8/8、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_241_result.md`。

- Round 240（P0 视图/服务拆分）：生成资产批次清理迁入无 Tk 服务；自动导入与分层校验 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_240_result.md`。
- Round 239（P0 视图/服务拆分）：生成图扫描与自动导入迁入 L2 服务，桌面直接调用；自动导入与分层校验 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_239_result.md`。
- Round 238（P0 视图/服务拆分）：三虎资产统计直连资产状态服务；计数与分层校验 5/5、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_238_result.md`。
- Round 237（P0 视图/服务拆分）：参考图墙直连资产计划服务；参考墙与分层校验 14/14、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_237_result.md`。
- Round 236（P0 视图/服务拆分）：参考图导入直连资产计划服务；参考图与分层校验 22/22、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_236_result.md`。

- Round 235（P1 多职责函数治理）：从 `workflow_context.snapshot()` 抽取参考资料文件发现为 `_reference_documents()`；目录范围、过滤条件和排序规则保持不变。工作流与分层校验 78/78、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_235_result.md`。

- Round 234（P0 视图/服务拆分）：三虎项目概览的剧本／分镜计数直接读取 `storyboard_catalog_service`，不再经由分镜页面门面。计数与分层校验 5/5、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_234_result.md`。

- Round 233（P0 视图/服务拆分）：三虎自动链的结构剧本同步直接调用 `storyboard_selection`；相关测试 mock 目标同步迁移，断言不变。桌面三虎接缝与分层校验 20/20、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_233_result.md`。

- Round 232（P0 视图/服务拆分）：技能层的分镜登记直接调用 `storyboard_selection.remember_many()`，以单元素列表保持原单项登记语义。技能流程与分层校验 111/111、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_232_result.md`。

- Round 231（P0 视图/服务拆分）：`workflow_context` 的目录发现由 L4 `storyboard_files` 改为直接依赖 L2 `storyboard_catalog_service`。工作流与分层校验 78/78、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_231_result.md`。

- Round 230（P1 多职责函数治理）：首帧自动入口的“未派发”完成／失败判定收拢到 `_finish_unsent_auto_keyframe()`，入口仅负责批次调度；同时删除不可达返回。定向首帧出口与分层校验 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_230_result.md`。

- Round 229（P1 多职责函数治理）：结构剧本异步结果的同步、阶段事件、状态提示和页面刷新收拢到 `_receive_structure_stage_result()`，派发函数仅负责前置校验与后台调度。定向结构剧本与分层校验 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_229_result.md`。

- Round 228（P0 视图/服务拆分）：桌面层的资产就绪、异常资产与原始输出清理查询改为直接依赖 `asset_batch_state_service`；相关 UI mock 目标同步迁移，断言不变。资产与分层校验 63/63、UI 定点回归 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_228_result.md`。

- Round 227（P0 视图/服务拆分）：桌面后台链直接使用分镜目录与选择服务；保留 `storyboard_files` 的页面显示入口。相关 UI mock 目标同步迁移，断言不变。定向回归与分层校验 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_227_result.md`。

- Round 226（P0 视图/服务拆分）：桌面无人值守资产链直接使用 `asset_batch_service`；相关 UI mock 目标同步迁移，断言不变。资产自动批处理与分层校验 7/7、UI 定点回归 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_226_result.md`。

- Round 225（P0 视图/服务拆分）：无人值守资产生成、ComfyUI 就绪检查、执行委托与日志适配迁入 `asset_batch_service`；资产页面保留同名兼容门面。资产自动批处理与分层校验 7/7、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_225_result.md`。

- Round 224（P0 视图/服务拆分）：分镜 JSON 工作目录与用户可读文档目录的阶段路径派生迁入无 Tk 目录服务，页面仅保留兼容入口。服务与路径兼容回归 6/6、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_224_result.md`。

- Round 223（P0 视图/服务拆分）：新增 L4 `storyboard_table_ui`，承接分镜 Treeview 构建、列宽与目录行渲染；`storyboard_files` 保留同名导出。列宽与分层校验 18/18、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_223_result.md`。

- Round 222（P0 视图/服务拆分）：目录变更快照迁入无 Tk 的分镜目录服务，页面观察器继续通过兼容入口调用；覆盖空文件与内部目录过滤。服务回归 4/4、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_222_result.md`。

- Round 221（P0 视图/服务拆分）：分镜同步资产判定迁入无 Tk 的分镜目录服务，页面模块保留兼容入口。服务回归 3/3、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_221_result.md`。

- Round 220（P1 多职责函数治理）：主心跳末尾的三虎事件聚合收拢到 `_tick_pet_events()`，保持在所有自动阶段调度后执行；宠物 Agent 回归 78/78、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_220_result.md`。

- Round 219（P1 多职责函数治理）：Tk 回收与流程进程轮询收拢到 `_tick_pre_automation()`，保持在自动调度之前执行；计时器回归 8/8、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_219_result.md`。

- Round 218（P1 多职责函数治理）：主后台结果消费、失败 UI 恢复及自动结构剧本重派发收拢到 `_tick_async_result()`；队列回归 2/2、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_218_result.md`。

- Round 217（P1 多职责函数治理）：待办与裁决的自动调度收拢到 `_tick_auto_gates()`，保持 20 秒节流及原错误去重；编译与默认 `smoke_test.py` 8/8 通过。既有资产详情整包测试在本机两次超时，未作为通过依据，待后续单独定位。详见 `tasks_round/tasks_round_217_result.md`。

- Round 216（P1 多职责函数治理）：自动采用分镜调度收拢到 `_tick_auto_adopt()`，保持 5 秒节流和原异常提示；自动采用 UI 回归 1/1、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_216_result.md`。

- Round 215（P1 多职责函数治理）：将 `desktop._tick_once()` 中云端任务监控的结果消费与
  轮询调度收拢到 `_tick_cloud_monitor()`；5/30 秒调度节流及失败提示保持不变。视频轮询回归
  33/33、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_215_result.md`。

- Round 214（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动整理交接包的队列收尾、
  失败清指纹、编辑页刷新与轮询调度收拢到 `_tick_auto_handoff()`；调用顺序、退避和节流保持不变。
  自动交接定点 UI 回归 2/2、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_214_result.md`。

- Round 213（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动补视频的消息消化、
  结果去重、后台收尾与轮询调度收拢到 `_tick_auto_video()`；状态栏去重、失败退避和节流间隔保持不变。
  自动视频定点 UI 回归 1/1、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_213_result.md`。

- Round 212（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动补资产的消息消化、
  续跑台账、后台收尾与轮询调度收拢到 `_tick_auto_asset()`；重试阈值、退避和页面刷新顺序保持不变。
  资产自动链与跨重启续跑 UI 回归 2/2、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_212_result.md`。

- Round 211（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动补白模的轮询、错误提示与
  工作线程消息播报收拢到 `_tick_auto_previs()`；Tk 主线程播报边界、调用顺序和节流间隔保持不变。
  自动白模定点 UI 回归 2/2、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_211_result.md`。

- Round 210（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动补首帧的消息消化、
  落盘复核、三虎播报与轮询调度收拢到 `_tick_auto_keyframe()`；调用顺序与节流间隔保持不变。
  自动补首帧定点 UI 回归 1/1、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_210_result.md`。

- Round 209（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动粗剪的队列收尾、
  页面刷新、失败退避与轮询调度收拢到 `_tick_auto_edit()`；调用顺序与节流间隔保持不变。
  自动粗剪定点 UI 回归 2/2、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_209_result.md`。

- Round 208（P1 多职责函数治理）：将 `desktop._tick_once()` 中自动定稿的队列收尾、
  失败退避与轮询调度收拢到 `_tick_auto_final()`；调用顺序与节流间隔保持不变。自动定稿
  定点 UI 回归 2/2、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_208_result.md`。

- Round 207（P0 架构治理）：将同时暴露目录与选择兼容接口的 `storyboard_catalog` 正确登记
  为 L3 编排门面，保留兼容期公开接口而不再误报 L2→L3 依赖。架构门禁 14/14、默认
  `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_207_result.md`。

- Round 206（P0 架构治理）：新增无编排依赖的 `stage_model_value` 只读服务，资产与首帧
  模型解析不再导入阶段配置/UI 模型编排；资产批服务的两项跨层依赖已清除。模型相关回归
  4/4、资产回归 66/66、默认 `smoke_test.py` 8/8 通过；架构层仅余分镜目录的一项既有
  跨层依赖。详见 `tasks_round/tasks_round_206_result.md`。

- Round 205（P0/P1 架构治理）：首帧模型解析服务改为直接读取模型契约、阶段配置与
  工作流候选，移除对含 Tk 弹窗的 `stage_models` 的依赖；同时修复分镜选择服务对 UI
  模块的上行导入。首帧模型与来源服务回归 5/5、循环依赖门禁通过、默认
  `smoke_test.py` 8/8 通过；架构层仍报告三项既有跨层依赖，留待后续专项。详见
  `tasks_round/tasks_round_205_result.md`。

- Round 204（P0 视图/服务拆分）：当前分镜 JSON 的已保存指针、旧版指针和默认来源回退
  解析迁入既有 `storyboard_selection` 服务；桌面层只传递兼容设置与迁移回调。服务回归
  3/3、首帧页面回归 4/4、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_204_result.md`。

- Round 203（P0 视图/服务拆分）：剧本列表所选路径的项目目录边界和批量操作文件存在性
  校验迁入无 Tk 的 `script_workspace_service`；桌面页面仅保留 Treeview 选择交互。服务回归
  4/4、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_203_result.md`。

- Round 202（P0 视图/服务拆分）：首帧生产模型解析迁入无 Tk 的 `keyframe_model_service`，
  `keyframe_comfy` 仅保留兼容转发；阶段配置模型解析回归 1/1、默认 `smoke_test.py` 8/8 通过。
  详见 `tasks_round/tasks_round_202_result.md`。

- Round 201（P2 平台适配）：剪贴板跨进程锁在 POSIX 使用非阻塞 `fcntl.flock`，Windows 保持
  `msvcrt`；超时仍安全降级。锁竞争回归 1/1、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_201_result.md`。

- Round 200（P2 平台适配）：快捷方式模块在非 Windows 直接跳过 PowerShell 探测并返回不创建，
  避免无效外部进程调用；模拟 POSIX 回归与快捷方式全量回归 37/37，默认 `smoke_test.py` 8/8 通过。
  详见 `tasks_round/tasks_round_200_result.md`。

- Round 199（P2 平台适配）：Codex 项目任务锁改为 Windows 使用 `msvcrt`、POSIX 使用非阻塞
  `fcntl.flock`，并保持同一并发占用提示；不再因导入 `msvcrt` 使非 Windows 环境无法加载任务模块。
  受影响模块编译通过，平台与 Token 设置回归 96/96，默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_199_result.md`。

- Round 198（P2 删除与恢复统一）：创意对话右键删除改为在当前模型会话旁保留最多 100 条删除记录，
  可从同一右键菜单恢复最近一条，且不同模型的恢复记录严格隔离。新增持久层恢复回归通过，
  默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_198_result.md`。

- Round 197（P1 旧接口 facade 收敛）：分镜计划、定稿、回收和工作流任务模块改为直连
  `storyboard_catalog_service` / `storyboard_selection`；`storyboard_catalog` 仅保留兼容层职责。
  受影响模块编译通过，循环门禁及分镜计划、定稿、回收、工作流回归 101/101，默认
  `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_197_result.md`。

- Round 196（P2 平台适配）：新增 `platform_tools.require_windows()`；ComfyUI 进程检测、
  强制关闭和 Blender 窗口检测经该统一边界在非 Windows 返回可操作说明，不再尝试执行
  PowerShell、taskkill 或 tasklist。受影响模块编译通过，平台/资产/工作流回归 164/164，
  默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_196_result.md`。

- Round 195（P0 架构循环依赖）：资产上下文、资产计划及分镜选择服务改为直连
  `storyboard_catalog_service` / `project_stages`，不再经旧 `storyboard_catalog` facade 或
  `asset_context` 反向绕行；消除资产—分镜与 facade—选择的静态循环。受影响模块编译通过，
  静态循环门禁及资产、文件缓存、工作流、回收回归 165/165，默认 `smoke_test.py` 8/8 通过。
  详见 `tasks_round/tasks_round_195_result.md`。

- Round 194（P0 资产批处理拆分）：将无人值守资产设置读取、阶段模型解析和计划组装迁入
  无界面的 `asset_batch_service`，`asset_batch` 保留兼容入口及 Tk 编排；新增服务级设置读取
  回归。`tests.test_assets` + `tests.test_workflow` 139/139、默认 `smoke_test.py` 8/8 通过。
  架构循环门禁另发现既有 `asset_context → asset_plan → asset_reference_prompts → storyboard_catalog
  → storyboard_catalog_service → storyboard_selection → storyboard_storage → asset_context` 链，
  未归因于本轮且总架构项保持未完成。详见 `tasks_round/tasks_round_194_result.md`。

- Round 193（P0 文件层拆分 / P2 删除恢复统一）：将分镜文件回收站的实际执行、视频来源
  解绑、最近批次查询和恢复迁入无界面的 `storyboard_recycle_service`；`storyboard_files`
  仅保留兼容入口，现有页面行为不变。相关模块编译通过，回收、恢复、文件缓存与工作流
  回归 105/105，默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_193_result.md`。

- Round 192（P1 阶段上下文预算·后台工作流）：新增无界面
  `workflow_context_budget`，通用工作流及直调 Qwen 的后台入口在启动前均限制 96,000 字符；
  超限给出拆分/摘要建议，不启动本地或 API 引擎。受影响模块编译通过，
  `tests.test_workflow` + `tests.test_force_quit` + `tests.test_previs` 126/126、
  默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_192_result.md`。

- Round 191（P1 模型配置一致性）：`workflow_settings.summary()` 改为复用实际调度的
  `current()` / `effective_model()` 解析链；阶段选定 DeepSeek 等 API 模型时，摘要不再错误显示
  保存的默认 Codex 引擎。受影响模块编译通过，工作流回归 76/76、配置相关组合测试零退出、
  默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_191_result.md`。

- Round 190（P2 平台适配·Qwen 后台）：Qwen Code 的后台制作进程改用
  `platform_tools.hidden_console_flags()`，不再嵌入 Windows 魔法常量；需要用户操作的 Qwen
  新控制台仍保留可见。受影响模块编译通过，工作流与平台定向回归 83/83、默认
  `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_190_result.md`。

- Round 189（P2 平台适配·后台命令）：将本地应用、引擎探测、白模校验、工作流引擎与桌面
  中断入口的 Windows 魔法隐藏控制台标志统一迁移至
  `platform_tools.hidden_console_flags()`；非 Windows 安全降级为零，用户可见的交互启动未改。
  受影响模块编译通过，平台/引擎/预演/工作流回归 145/145、默认 `smoke_test.py` 8/8 通过。
  详见 `tasks_round/tasks_round_189_result.md`。

- Round 188（P1 删除入口·分镜页计划收口）：将分镜页删除前的项目归属、来源关联、已采用
  阻断和影响范围计算迁移至无 Tk 的 `storyboard_recycle_service`；实际回收、恢复及页面提示
  未改。受影响模块编译通过，删除/文件/工作流定向回归 102/102、默认 `smoke_test.py` 8/8
  通过。详见 `tasks_round/tasks_round_188_result.md`。

- Round 187（P1 兼容门面收敛·分镜目录）：`storyboard_catalog` 现在直接委派无 Tk 的目录与
  选择服务，不再反向动态导入 `storyboard_files` 页面模块；保留历史调用名，并标注 2027-03-31
  兼容淘汰边界。受影响模块编译通过，`tests.test_core` + `tests.test_file_cache` +
  `tests.test_workflow` 201/201、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_187_result.md`。

- Round 186（P0 架构与设计·分镜目录服务收口）：将分镜/剧本候选目录、可交付筛选、
  稳定排序、剧本—分镜来源关联及已制作状态计算迁移至无 Tk 的
  `storyboard_catalog_service`；`storyboard_files` 保留兼容门面，删除与页面构建未改。
  受影响模块编译通过，`tests.test_core` + `tests.test_file_cache` + `tests.test_workflow`
  201/201、默认 `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_186_result.md`。

- Round 185（P0 架构与设计·分镜文件选择收口）：将已选剧本/分镜的读取、写入、去重和结构剧本
  同步迁移至无 Tk 的 `storyboard_selection`；`storyboard_files` 保留兼容门面，删除及页面构建未改。
  受影响模块编译通过，`tests.test_file_cache` + `tests.test_workflow` 95/95、默认
  `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_185_result.md`。

- Round 184（P0 架构与设计·分镜文件收口）：将分镜/剧本文件的内容预览迁移至无 Tk 的
  `storyboard_catalog_service.content_preview()`；`storyboard_files.content_preview()` 保留兼容转发，
  不触及页面构建和删除流程。受影响模块编译通过，`tests.test_file_cache` 20/20、默认
  `smoke_test.py` 8/8 通过。详见 `tasks_round/tasks_round_184_result.md`。

- Round 183（P0 架构与设计·资产批处理收口）：将无人值守资产自动计划的纯业务筛选下沉至无 Tk 的
  `asset_batch_service.automatic_plan()`；`asset_batch.py` 仅保留项目设置读取、缺失设置提示和服务
  委派，未触及 `desktop.py` 或 `storyboard_files.py`。新增无 Tk 服务回归；受影响模块编译通过，
  `tests.test_assets` 61/61、默认 `smoke_test.py` 8/8 通过。详见
  `tasks_round/tasks_round_183_result.md`。

- Round 182（优化清单收尾）：模型后台响应与云端/本地媒体下载均改为“唯一临时文件 → 完整校验
  → 原子发布”；损坏的响应不会覆盖旧诊断，下载中断会清理临时文件。首帧跨分镜行发现抽为无 Tk
  的 `storyboard_rows_service`，结构剧本大文件预览后台加载，平台打开/注册表访问经统一适配器。
  全量安全回归 2,942 条、831.3 秒、0 失败文件；架构门禁 14/14 通过。未完成的结构性专项保留为
  明确待办，详见 `tasks_round/tasks_round_182_optimization_checklist.md` 与
  `tasks_round/tasks_round_182_closure_report.md`。

- Round 153（修复轮）：收口架构门禁中的三个直接删除点：快捷方式 PowerShell 临时脚本、引擎探针临时目录转由 `file_cache` 的临时资源接口处理；项目内部 junction 节点转由 `storage_maintenance` 的受限接口移除，不进入连接目标。删除权威门禁 1/1、存储与核心回归 106/106、默认冒烟 8/8 通过。白模真机上传仍需用户指定已采用预演镜头并授权；依赖层/循环/路径权威三类历史架构红灯须后续逐模块治理。详见 `tasks_round/tasks_round_153_result.md`。

- Round 152（功能轮）：剧本准备聊天历史现保存至 `01剧本准备/<Provider>/<模型>/创意对话/对话.json`；旧统一记录首次使用对应模型时按模型筛选迁移，迁移后不保留会回流的镜像。剧本结构上下目录栏新增右键“删除（移入回收站）”；删除自然剧本后，来源标记指向该原稿的结构剧本会隐藏而不删除，保留可恢复性。剧本结构 13/13、剧本准备 57/57、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_152_result.md`。

- Round 151（功能轮）：剧本准备新保存的自然剧本与剧本结构新保存的结构剧本统一采用 `项目名_文件类型_文件内容_年月日.md`；旧文件继续以只读兼容方式导入列表。剧本路径收敛为当前 `01剧本准备` 优先，同一相对路径或相同内容的历史 `writing` 副本不再重复显示；指定项目的 `writing/...` 同名副本实际不存在，故未执行删除，`01剧本准备/...` 原稿未改动。剧本结构上下两栏的文件目录改为水平可拖动分栏，主界面左侧阶段栏缩短约三分之一。命名/去重 12/12、剧本保存 56/56、结构页面 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_151_result.md`。

- Round 150（修复轮）：项目选择不再将“尚未制作初步分镜、缺少 `episode.json`”误报为“剧本已删除”。打开项目时仅延迟分镜工作集初始化，剧本准备与剧本结构可正常进入；仅项目根目录真实不存在/已移动时才保留残留清理提示。未触碰用户项目数据。残留判定与真实加载回归 4/4、核心回归 100/100、受影响冒烟 9/9（定向自检 100 条、0 红）通过。详见 `tasks_round/tasks_round_150_result.md`。

- Round 144（结构治理·Round 139 模型小环收尾）：`model_secrets` 的读写实际统一经 `PROTECTOR` 协议入口；`test_model_pool` 的 DPAPI 替身由失效的 `seedream_api.protect` 迁至该入口。夹具还临时屏蔽同名用户环境变量，避免正式优先级覆盖“本机加密密钥”测试分支；三条原断言均未改动、未弱化或跳过。模型池定向 57/57、受影响冒烟 9/9（定向自检 108 条、0 红）通过。已按附件调用全量 `run_selftests.py --all --safe`，但本轮工具回传未保留末尾汇总，不能据此声明全量绿；既有全量红灯基线仍有效。详见 `tasks_round/tasks_round_144_result.md`。

- Round 143（K4/K5：阶段命令契约与历史测试迁移）：新增 `tests/test_stage_command_contract.py`，锁定 `Desktop.pet_start()`、手动分镜和自动分镜都只能经 L3 `stage_handler_registry.start()`；自动分镜缺少结构剧本时仍发布 `stage.failed`，手动调用则保持页面本地空结果，避免错误广播。盘点时根目录历史 `test_*.py` 为 0、既有 99 份测试均已在 `tests/`；新增本轮测试后为 100 份，故未进行伪迁移、未新增无意义兼容 shim。新测试按现有非递归测试发现规则放在 `tests/` 顶层。定向契约 4/4、受影响冒烟 9/9 通过。详见 `tasks_round/tasks_round_143_result.md`。

- Round 142（阶段路径服务）：新增 L0 `stage_path_service`，以 `write_dir()` 固定当前编号阶段目录、以 `legacy_read_dirs()` 在 2027-03-31 前只读兼容旧英文目录；`script_contract` 已迁入该服务，避免自行拼写 `writing` 作为新写入位置。新增路径服务回归，覆盖新路径、旧读淘汰和未知阶段；路径服务/剧本契约/阶段布局 66/66、受影响冒烟 9/9 通过。G 节其余业务模块仍需在后续小轮逐项迁移，不能据此删除旧目录。详见 `tasks_round/tasks_round_142_result.md`。

- Round 141（分镜 view/service/adapter 与三虎 L3 启动入口）：新增无 Tk 的 L3 `stage_handler_registry.start()`；三虎自动启动和分镜批次入口均经此唯一指令入口。`storyboard_files.storyboard_work_plan()` 收回已选结构剧本、已生成分镜与已采用分镜的纯文件决策，`desktop.py` 只保留页面回调及尚未拆分阶段的回退回调。默认冒烟 8/8、适配器内存行为检查和三模块编译通过；`--architecture` 仍报 4 项既有治理红灯。详见 `tasks_round/tasks_round_141_result.md`。

- Round 140（L4 动态导入登记制）：新增 `ui_plugin_registry`，以白名单集中承接桌面页面打开时才需加载的 L2/L3 插件；`desktop.py` 与 `skill_panel.py` 不再使用裸 `__import__`，标准库动态导入也已改为顶层静态导入。L3 阶段处理器登记表和 L5 `app.py` 仍保留到后续治理轮，未在本轮触碰。默认冒烟 8/8 通过；L4 静态扫描无裸动态导入。详见 `tasks_round/tasks_round_140_result.md`。

- Round 139（模型基础设施小环拆解）：新增纯协议 `model_protocol.BytesProtector`；`model_secrets` 将 DPAPI 实现收回本层，不再导入 `seedream_api`；`model_pool` 收回配置、密钥解析和通用 HTTP 传输，不再导入 `pet_llm`；`pet_llm` 仅经模型池兼容门面访问这些能力；`seedream_api` 仅依赖 `pet_llm`。静态链为 `seedream_api → pet_llm → model_pool → model_secrets → model_protocol`。附件指定 smoke 已确认 import 方向正确，但定向回归仍有 3 条旧 DPAPI 测试替身失败：它们只 monkeypatch 已移除反向入口 `seedream_api.protect`，未能替换新的密钥层实现；因本轮禁止为迁就实现改测试，不能标记为全绿。详见 `tasks_round/tasks_round_139_result.md`。

- Round 137（三处 P0 删除点收口）：`Projects.delete()` 不再递归永久删除已登记用户项目，改为经既有 `storage_maintenance.recycle_paths()` 移入项目库回收站后才移除注册记录。`desktop.py` 的两处首帧 `unlink()` 经逐项判定均为 JSON 保存失败时撤销刚创建/刚复制的临时副本，用户原件分别仍在原始导入文件或回收站，已补注释；`storyboard_final.py` 的 `unlink()` 仅回滚本次验证失败、尚未采用的定稿输出 JSON，已补注释。`test_core + test_lifecycle` 103/103、默认冒烟 8/8 通过；按模块别名运行的冒烟门禁未匹配测试文件，已改用实际测试文件验证。详见 `tasks_round/tasks_round_137_result.md`。

- Round 136（已知阻塞核验与启动迁移修复）：全局 Python 3.14 与项目内置解释器均已实测 Tcl/Tk 可用；以无敏感固定字串实测 DPAPI 加解密通过，先前两项系统阻塞已解除。恢复并完成 `run_selftests.py --all --safe`：2856 条、53 个红灯文件，暴露出项目根目录缺少旧 `config.json` 时 `Projects.migrate()` 二次强读配置的启动缺陷；现改为安全建立空项目注册表并交由新建/打开项目流程接管。性能基准 5/5、默认冒烟 8/8 通过。真实白模上传仍须用户选定素材并授权。详见 `tasks_round/tasks_round_136_result.md`。

- Round 134（架构测试落地）：新增只读 AST 架构扫描测试集和 `smoke_test.py --architecture` 独立入口；默认冒烟流程不加载此测试集。扫描仅覆盖程序根目录生产 `.py`，并检测架构第 3 节登记层级的逆向依赖、Tarjan SCC 循环、非路径权威模块的工作流路径字面量，以及非删除权威模块的直接删除调用。首次基线按预期红灯：4/4 项均发现既有违规（越层、3 个 SCC、211 处路径候选、4 处直接删除）；入口已无调度异常。详见 `tasks_round/tasks_round_134_result.md`。

- Round 133（契约轮）：新增 `stage_layout.validate_stage_contract()`，强制目录阶段 ID 顺序与 `pet_bus.STAGES` 一致，并拒绝重复/空阶段标识；新增阶段布局回归，修正 `PROJECT_MAP.md` 的“11 阶段”旧标题，`architecture.md`/`AGENTS.md` 已记录守卫。阶段布局 21/21、默认冒烟 8/8 通过。已启动全量安全自检，但可见输出含资产 UI 既有失败且未返回最终汇总，不能标记全绿；详见 `tasks_round/tasks_round_133_result.md`。

- Round 132：完成只读结构治理诊断，不修改 `.py`、配置、用户项目数据或目录。AST 核心扫描覆盖 136 个生产模块并发现 96 个测试文件；识别模型基础设施小环、需动态验证的巨型静态 SCC、UI/业务/编排的动态导入边界混杂、旧阶段路径直拼及非白名单直接删除候选。治理结论：先建立动态导入登记、阶段路径单一服务与删除网关，再进行模块合并/删除；详见 `tasks_round/tasks_round_132_result.md`。

- Round 131：完成文件增删改查路径专项审计后的最小修复。资产导入同目录重名时不再直接删除原图，改为经 `storage_maintenance.recycle_paths()` 移入项目回收站并记录恢复位置；不能安全回收时保留原图；参考图解绑提示同步为“移入回收站，可恢复”。资产图删除后新增“恢复删除资产”，仅恢复该资产最近历史版本且拒绝覆盖现有文件；分镜定稿后的原始工作 JSON 同样统一进入回收站，失败则保留。配音、字幕、后期、交付及自动粗剪导出统一写进 `10配音与字幕`、`11后期剪辑`、`12质检交付/导出成片`，不再新建旧英文顶层目录。`PROJECT_MAP.md` 更新为当前 12 阶段目录，旧目录仅标记为兼容别名；`script_contract` 在检查 SKILL 文档落点时将旧 manifest 键解析为当前阶段，避免文档契约检查失效。工作流接续上下文补齐旧剧本/分镜的只读目录清单，并优先从 `04资产管理/assets.json` 注入当前资产。同步修正剧本契约及引擎验证测试把 `tests/` 误作程序根的问题。剧本契约/阶段布局 62/62、资产恢复 2/2、分镜退役 1/1、阶段路径 1/1、引擎验证 23/23、上下文 14/14、受影响门禁 88/88、默认冒烟均通过；详见 `tasks_round/tasks_round_131_result.md`。

- Round 122：修复分镜定稿链路仅识别旧 `storyboard/分镜拆分` 的问题；当前 `03初步分镜/分镜拆分` 原稿同样会在定稿成功后备份进回收站、更新别名并退役，旧路径继续只读兼容。定稿目标的安全校验收敛为“当前项目内”，原稿仍严格限制在工作分镜目录。定向 5/5、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_122_result.md`。

- Round 121：剧本准备文件表的单个、批量删除改为移动至项目回收站，状态文字同步说明“已移入回收站”；最后一份剧本触发的“删除整个项目”确认逻辑不变。新增通用回收接口的恢复清单回归。资产/存储回归 87/87、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_121_result.md`。

- Round 120：参考图解绑、参考图更新遗留文件与未登记的 `comfy_*.png` 原始资产图不再直接删除，统一复用项目回收站与恢复位置清单；共享引用、外部文件、软链接和资产登记图的既有保护仍保留。同步修复 `test_reference_images.py` 将源码误定位到 `tests/` 的测试路径错误。资产/存储回归 86/86、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_120_result.md`。

- Round 119：`storage_maintenance.py` 的关闭后自动维护不再永久删除 `历史版本`、`分镜历史` 或过期生成版本，而是移动到项目 `工作流任务/回收站/自动维护_时间戳/`；同批写入 `恢复位置.json`，记录原相对路径和回收位置。扫描会跳过既有回收站，防止递归清理；项目外路径及软链接/联接点继续拒绝处理。存储安全测试 5/5、默认冒烟 8/8 通过。详见 `tasks_round/tasks_round_119_result.md`。

- Round 118：完成项目路径链路审计的首批最小修复。HOLLMWOOD 原稿统一写入 `01剧本准备/`；旧 `writing/brief_complete.json` 仅作为历史项目的只读兼容输入，避免流程退化为单轮模型调用；剧本列表的重命名/删除权限校验改为当前阶段目录；初步分镜自动采用签名与媒体根目录均识别 `03初步分镜/分镜拆分`。定向回归 22/22、默认冒烟 8/8 通过。`storage_maintenance.py` 的不可恢复自动清理及资产解绑的永久删除仍列为下一轮 P0/P1 收口项，未修改用户项目数据。详见 `tasks_round/tasks_round_118_result.md`。

- Round 110：新增 `architecture.md`，集中导出目录树、SKILL/模块/Agent 清单、三虎阶段、并行、模型路由、数据文件和阶段 I/O；不包含密钥或用户内容。
- Round 111：压缩本状态文件为独立接续摘要，移除逐轮历史，作为关闭旧对话后的唯一状态入口；默认 `smoke_test.py` 8/8 通过。
- HOLLMWOOD Round 1：完成剧本阶段只读诊断。现有链路为 Tk 输入 → `workflow_tasks.script_prompt`（工作流/SKILL 门禁）→ 显式 API 时 `writing_api.reply` / 否则桌面 Agent → `idea_chat` 持久化 → 用户下载后写入 `writing/`。已确认缺少 HOLLMWOOD 四角色编排、`brief_raw.md`/`brief_complete.json` 完整性流程、节奏模板及“剧本结构”阶段；未改业务代码，等待确认进入 Round 2。
- HOLLMWOOD Round 2：定义新增窄职责编排模块 `hollmwood_roles.py`，由既有 `writing_api.reply` 在选中剧本结构化 SKILL 时调用，并复用 `model_router.PoolAdapter`。四角色串行运行，最终仅由 API 层落盘 `writing/script_raw.md`；桌面 Agent 保持原备用路径。详见 `tasks_round/tasks_round_2_result.md`。
- HOLLMWOOD Round 3：新增 `skills/templates/rhythm_template.yaml`，定义黄金 3 秒、冲突升级、场景情绪转折、结尾卡点、60–90 秒集时长和单句 20 字限制。`script_contract.py` 增加节奏模板路径及 `rhythm_template` 引用字段，不纳入五类 manifest 输出。`test_script_contract.py` 41/41、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_3_result.md`。
- HOLLMWOOD Round 4：在 `reference/HoLLMwood` 留存外部仓库只读参考，新增 `hollmwood_roles.py`。Director 依据节奏模板规划并审查 Writer、Editor、Actor；任一审查未通过最多返工一次后停止。模块只接收既有 `model_router.ModelAdapter`，不另建 Agent、不改路由、不写剧本文件；每个生成/审查步骤写入 `logs/hollmwood_step_N.log`。`test_hollmwood_roles.py` 3/3、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_4_result.md`。
- HOLLMWOOD Round 5：`idea_chat.py` 将用户输入追加到当前项目 `writing/brief_raw.md`，只追问故事梗概、主要角色、题材类型和篇幅这四项缺失内容；物理特征作为建议项、特殊要求可选。信息完整后按 `script_contract.py` 的统一契约写入 `writing/brief_complete.json`。剧本页在简报不完整时不会启动 API/Agent，启动既有工作流失败时保留用户输入。`test_script_contract.py` 42/42、`test_idea_chat.py` 47/47、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_5_result.md`。
- HOLLMWOOD Round 6：writing_api.py 发现有效 writing/brief_complete.json 后，复用 PoolAdapter 运行导演→编剧→编辑→演员；节奏模板与所选剧本 SKILL 指令注入每个角色。导演全部放行后，唯一业务落盘为 writing/script_raw.md，每步记录到当前项目 logs/hollmwood_step_N.log。无完整简报的既有普通 API 对话与 Claude 受控文件工具保持不变。test_hollmwood_roles.py 3/3、test_writing_api.py 13/13、默认冒烟 8/8 通过；详见 tasks_round/tasks_round_6_result.md。
- HOLLMWOOD Round 7：在 `pet_bus.py` 插入 `script_structure`，UI 显示为“02 剧本结构”，并在原“初步分镜”之前。新增独立页面、串行阻塞并行策略和 `script_structure_process_template.yaml`；模板输入 `writing/script_raw.md`、输出 `writing/script.md`。为避免破坏既有项目门禁与数据目录，旧阶段的内部目录编号未重命名。相关集成测试 103/103、状态测试 28/28、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_7_result.md`。
- HOLLMWOOD Round 8：未删除或重命名任何 SKILL；仅将 `script-structured-generation`、`script-character-extraction`、`script-worldbuilding` 的阶段元数据迁至 `script_structure`，保留 `script-dialogue-polish`、`script-emotion-curve` 于剧本准备。注册表本已动态按阶段索引；剧本契约审计现覆盖两个剧本阶段，兼容保留既有 `00_script` 落盘目录。同步修复 12 阶段页面工具路由编号。`test_skills` + `test_script_contract` 150/150、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_8_result.md`。
- HOLLMWOOD Round 9：复用 `script_contract.py` 提供唯一的 Markdown 结构化转换和原子写入接口；`stage_exec.py` 按现有“剧本结构”YAML 模板执行读取、分析、整理、写入四步，且不改 `script_raw.md`、不引入 JSON 或 HOLLMWOOD。阶段依赖改为剧本准备 → 剧本结构 → 初步分镜。定向测试 107/107、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_9_result.md`。
- HOLLMWOOD Round 10：复用 `Desktop.async_` 与 Tk 的 `after` 调度，不新建线程框架。HOLLMWOOD 的导演/编剧/编辑/演员进度经 `queue.Queue` 每 100ms 回到主线程显示并用 `Broadcaster` 记录；取消令牌在角色调用边界生效，取消后不进入后续角色、不落盘 `script_raw.md`。定向测试 67/67、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_10_result.md`。
- HOLLMWOOD Round 11：复核并回归锁定三虎 `set_mode()` 的唯一控制路径：全自动将全部登记的 `auto_*_var` 与项目持久化开关置为 True，手动模式统一置为 False；页面仅获取变量读取，未创建自动制作 Checkbutton。模式播报复用 `Broadcaster` 的 `【模式】` 前缀。定向测试 8/8、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_11_result.md`。
- HOLLMWOOD Round 12：复用既有 `Orchestrator.before_step()`、恢复询问和 `pet_bus.STAGES` 定位；补充模板阶段成功后只清理本阶段检查点，避免下次启动误报中断。定向检查点测试 4/4、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_12_result.md`。
- HOLLMWOOD Round 13：复用 `skill_templates.py`、既有 12 个阶段 YAML 与 `run_stage_with_template()`；阶段播报总数改为随 `pet_bus.STAGES` 动态输出，新增所有登记阶段均有可加载模板的回归。定向模板/模式测试 10/10、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_13_result.md`。
- Round 14（暂停）：`asset_thumbs.py` 的缩略图缓存改用当前用户临时目录，避免安装目录无写权限时退回主线程同步解码；UI/API 历史测试改用 `pet_state.PAGE_OF`，消除新增“剧本结构”阶段后的硬编码页码。冒烟 8/8、`test_api` 53/53、页面构建异常 1/1 通过；用户要求暂停全量自检，未完成的全量门禁留待后续优化。
- Round 15：剧本准备的文件表改名为“项目剧本”，并按文件名展示在“项目设定”或“项目大纲”列；未知命名默认保留在项目设定列。原有勾选、打开、删除与刷新逻辑不变。定向 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_15_result.md`。
- Round 16：简报完整性检查会汇总当前项目各模型聊天页中的用户历史消息，并继续忽略模型文本，避免用户已提供的角色、题材、篇幅被再次追问。工作流先读 `writing/brief_complete.json`，仅在该已确认简报确实缺项且 SKILL 要求时追问。`test_idea_chat` 48/48、`test_workflow` 69/69、`test_writing_api` 14/14、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_16_result.md`。
- Round 17：下方文件表移除“项目剧本”标题，改为第三列“项目剧本”；只显示分类明确的项目设定/大纲/剧本，按实际记录数紧凑显示。用户简报与聊天记录继续作为私有对话上下文，不显示或落成项目文档；无关模型回复会被拒绝写入项目文件。`test_idea_chat` 49/49、页面 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_17_result.md`。
- Round 18：剧本输入框在空闲且未聚焦时显示四角色创作提示，聚焦即隐藏；总进度条下方用绿色状态行显示导演、编剧、编辑、演员的工作进度。右键菜单移除与猫爪重复的手动/全自动入口，猫爪成为自动化唯一入口。修复 API 剧本请求发出即误报完成的问题：仅在 `script_raw.md` 成功落盘后才向三虎发送 script.completed，从而在全自动模式交接到剧本结构。详见 `tasks_round/tasks_round_18_result.md`。
- Round 19：剧本文件表改为项目设定、项目大纲、项目剧本三列独立列表，避免不同类别共用行导致的空白格；各列均按修改时间由新到旧从上到下排列，修改时间随文件保留在所属列。显示文本统一使用文件名，目录仅用于分类和安全校验。UI 回归 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_19_result.md`。
- Round 20：模型网关 TLS EOF 在传输层最多重连两次（共三次请求）；四角色任一角色仍失败时，API 返回可恢复失败结果而不抛过异步边界。剧本页恢复发送按钮并以状态栏提示重新发送，不弹出通用“操作未完成”。网络/剧本 API 回归 17/17、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_20_result.md`。
- Round 21：剧本输入框空闲提示改为沿输入框垂直中线定位，避免压住下边框；空白且失焦时从居中位置缓慢横向滚动，输入、获取焦点或控件销毁时立即停止并取消回调。UI 回归 2/2、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_21_result.md`。
- Round 22：剧本结构页新增只读“剧本目录内容”框，优先预览 `writing/script.md`、缺正稿时预览原稿，并提供“手动打开剧本目录”。三虎自动链为 `script_structure` 接入与手动入口相同的异步模板执行；成功写入正稿后发出阶段完成并推进下游，失败则发出阶段失败并停止自动链。定向 13/13、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_22_result.md`。
- Round 23：剧本准备输入框的空闲提示改为向右移动，完整离开右侧后从左侧重新进入；下方三列文件表将“修改时间”改为“修改日期”，仅显示月-日。定向 UI 回归 2/2、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_23_result.md`。
- Round 24：剧本结构模板改为 Writer 提取结构化要素 → Editor 审校角色物理特征/服装、场次、道具及尺寸一致性 → Writer 按反馈重提取 → Editor 复审 → 写入 `writing/script.md`。源稿同一道具存在冲突尺寸时停止写入并明确提示先修正 `script_raw.md`，不臆造事实。定向 15/15、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_24_result.md`。
- Round 25：定位并修复剧本结构只读取固定 `writing/script_raw.md` 的兼容性缺陷。现在优先读取该原稿；不存在时自动读取剧本准备下载的 `writing/创意_日期/创意与剧本_日期.md` 或导入剧本。页面显示实际来源，三虎自动结构化也复用相同解析规则。定向 17/17、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_25_result.md`。
- Round 26：剧本结构页改为上方只读展示剧本准备来源、下方只读展示 `writing/script.md`，中间左侧设置“手动制作结构剧本”和“阶段配置”。手动入口通过三虎异步 Writer/Editor + SKILL 执行链完成，成功后重建页面以刷新下方输出框；触发来源保留为手动。定向 UI/结构化/三虎 18/18、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_26_result.md`。
- Round 27：剧本准备输入提示每轮从输入框最左侧起步向右滚动。统一发送、手动制作与阶段配置为相同主操作尺寸；配音、剪辑、交付的阶段配置移至各自手动制作按钮右侧，视频与白模入口同步对齐。UI/三虎定向 11/11、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_27_result.md`。
- Round 28：DeepSeek/OpenAI Chat 响应现记录 `finish_reason`、顶层/消息字段形状及推理字段存在性，不记录正文或推理内容。导演审核空正文仅受控重试一次；仍为空时返回“模型未生成审核正文”及诊断，而非跨异步边界弹窗异常。DeepSeek V4 Flash 配置已复核为 `/chat/completions` + OpenAI Chat。定向 77/77、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_28_result.md`。
- Round 29：剧本准备下载剧本时，按 `writing/<Provider>/<模型名>/创意_日期/` 自动创建并保存，未知来源也落入明确的“未知Provider/未知模型”目录。最近剧本、剧本准备预览、剧本结构来源解析与后续 Agent 成果目录均兼容新层级及旧目录。定向 23/23、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_29_result.md`。
- Round 30：修复三虎全自动的异步阶段抢跑。自动推进器派发“剧本结构”后会记录执行中状态，只有收到 `stage.completed` 或 `stage.failed` 后才允许进入下游，避免结构化 `script.md` 写入与下一阶段同时执行。定向 26/26、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_30_result.md`。
- Round 31：剧本结构页面上下文本框支持双向联动滚动，并各自提供“修改内容／保存修改”。保存采用临时文件替换；修改上方原稿会提示重新生成下方结构化剧本。定向 18/18、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_31_result.md`。
- Round 32：剧本准备页的项目文件表排除后续“剧本结构”阶段生成的 `writing/script.md`；该文件仍保留在原位置供剧本结构及下游阶段读取，剧本准备产生或导入的剧本不受影响。定向 UI 2/2、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_32_result.md`。
- Round 33：剧本准备对话框的软件示例改为无底色灰色提示文本；单击可直接编辑，修改只保留在本次打开期间，既不伪装成用户消息也不写入项目。定向 UI 5/5、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_33_result.md`。
- Round 34：剧本结构页的上、下内容框左侧分别新增“自然剧本目录”和“结构剧本目录”。前者打开实际来源文件所在目录（兼容 Provider/模型子目录），后者打开 `writing/` 正稿目录；移除会混淆位置的通用目录入口。定向 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_34_result.md`。
- Round 35：剧本结构页移除“剧本准备阶段剧本”和“结构化生成剧本”两个内容框标题；Writer/Editor 流程说明从页面顶部移至两个内容框之后的右下方。定向 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_35_result.md`。
- Round 36：剧本结构完成后会先将 `writing/script.md` 同步为初步分镜的首个已选剧本，再通知三虎推进下游；`script.md` 也被识别为有效剧本，故全自动模式可立即派发分镜制作，并保留用户原已选剧本。定向 3/3、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_36_result.md`。
- Round 37：首个 `director` 角色与导演审核一样，在模型调用成功但正文为空时受控重试一次；两次仍为空会返回“模型未生成导演正文”及安全响应诊断，且不写入不完整 `writing/script_raw.md`。网络/协议错误不额外重试。HOLLMWOOD 定向 21/21、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_37_result.md`。
- Round 38：剧本结构上下内容框滚动时，会识别当前可见镜头号（兼容 `SH001`、`镜头号：001`、`第 1 镜`）并将另一框定位到同镜头；缺少对应镜头时才按原滚动比例回退。定向 2/2、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_38_result.md`。
- Round 39：修复首个导演空正文的“同请求重试无效”问题。第二次请求会明确要求可见导演计划、禁止仅输出推理内容，并将输出额度从 4096 提升至 8192；仍为空才安全停止且不写入原稿。HOLLMWOOD/API 定向 21/21、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_39_result.md`。
- Round 40：按最新交互要求移除“剧本结构”上、下内容框的镜头号联动滚动及相关锚点辅助逻辑；两个文本框现各自使用独立滚动条，编辑、保存和目录打开功能不变。`test_core` 98/98、剧本结构页定向 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_40_result.md`。
- Round 112：初步分镜自动化改以已落盘且非空的 `writing/script.md` 作为历史项目的结构剧本完成证据，自动将其登记为已选分镜输入；三虎切换“全自动”后立即派发首个待办阶段，避免模式反馈气泡及旧心跳节流阻止分镜启动。分镜产物仍沿既有自动采用链同步至后续页面。定向 + 核心 100/100、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_112_result.md`。
- Round 113：修复初步分镜阶段配置与三虎自动派发的模型路由不一致。模型池中已选的任何非桌面 API 模型（含 DeepSeek）均由兼容 API 调用器实际执行，不再因默认工作流为 Codex 而静默启动 Codex；阶段配置选“自动”时按钮显示当前实际引擎，选定模型时仍显示对应 Provider。`test_workflow.DesktopModelPoolTests` 7/7、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_113_result.md`。
- Round 114：剧本准备底部操作栏改用全阶段共用的 `FlowBar` 响应式布局；窗口变窄时按钮自动分行而非左右互挤，完整保留“删除剧本”等标签。其他已使用 `FlowBar` 的制作阶段同步保持同一行为。剧本页布局定向 3/3、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_114_result.md`。
- Round 115：剧本结构页移除“自然剧本目录／结构剧本目录”按钮，在下方新增“自然剧本／结构剧本”两列展示实际文件路径；结构化输出改存 `writing/结构剧本/script.md`，下游分镜和三虎自动化同步读取该路径，兼容保留旧 `writing/script.md` 的读取能力。定向 26/26、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_115_result.md`。
- Round 116：按用户确认永久删除项目 `摄像头3_20260924` 下 15 个旧阶段骨架目录，保留“工作流任务”及现有工作目录。剧本准备的用户可见保存文件统一命名为 `项目_对应集数_年月日.md`：项目标题与集号来自 `episode/episode.json`，缺失时回退项目目录名与 `EP001`；旧“创意与剧本”文件仍可读取，结构剧本来源解析也兼容新文件名。定向 39/39、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_116_result.md`。
- Round 117：剧本结构上、下内容框的“修改内容”右侧新增“恢复删除”。编辑时可撤销最近一次文本删除，保存后自动禁用；初始预览不进入撤销栈，避免误恢复页面初始文本。定向 UI 1/1、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_117_result.md`。
- Round 130：`stage_layout` 不再以旧内部标识创建 `00_script`、`03_continuity` 等第二套顶层目录。旧标识仅在读取时解析到当前编号阶段；归位链接、README 文档清单和门禁表均落在 `01剧本准备` 至 `12质检交付`。分镜自动去重也改为回收重复工作稿并记录恢复清单，同时支持当前 `03初步分镜` 目录；旧分镜选择会只读回退到旧工作目录。核心/阶段/门禁/连贯性/去重 158/158、默认冒烟 8/8 通过；详见 `tasks_round/tasks_round_130_result.md`。
