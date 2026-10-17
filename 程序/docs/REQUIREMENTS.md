# 需求（REQUIREMENTS）

本文件描述系统**现在想去的方向**，原地修改，不记历史（历史看 git）。
编号规则：`REQ-<阶段号>-<序号>`，删除的编号不复用。测试 docstring 写 `REQ-xx` 锚定。
状态：✅ 已实现　🟡 部分实现／与代码不一致　⬜ 未实现　❓ 待人拍板

> 已覆盖阶段：S01 剧本准备、S02 剧本结构、S03 初步分镜、S04 分镜预演、S05 资产管理、S06 连贯性清单。其余阶段按顺序逐阶段补。

## S01 剧本准备

目标：把用户的创意，经四步确认，变成一份被**明确采用**的自然剧本，作为后续阶段唯一的剧本源。

### 输入

- **REQ-S01-01** ✅ 用户通过创意对话（气泡式）输入想法，可附受控文本附档；对话与草稿跨重启保留。
- **REQ-S01-02** ✅ 创作简报必填：故事梗概、故事题材、故事角色、故事集数、单集时间；缺项时不发送，提示补齐。
- **REQ-S01-03** ✅ 制作锁值在本阶段由用户填写，必填：交付形态、赛道、素材来源。新版制作锁生效前创建的旧项目，缺赛道／素材来源时只提示不阻断。
- **REQ-S01-04** ✅ 每个模型的对话独立归档，模型显示名变化不影响已有记录。

### 四步流程

- **REQ-S01-10** ✅ 流程固定为：①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本。
- **REQ-S01-11** ✅ 每次请求最多产出一步待确认内容；前一步未确认，不进入下一步。
- **REQ-S01-12** ✅ 用户用肯定回复（确认／好／继续／ok 等）确认当前步；只认输入框原文首行。
- **REQ-S01-13** ✅ ④自然剧本只在①②③全部确认后由程序启动生成。
- **REQ-S01-14** ✅ 用户可从①②③任一步显式重写；确认重写后，该步及下游确认失效，已采用的自然稿撤销采用。旧稿不删除。
- **REQ-S01-15** ✅ 生成过程中有编剧（五阶门控）、编辑（12 情绪节拍）、演员（台词七维诊断）三角色把关。

### 产出与完成

- **REQ-S01-20** ✅ 同一阶段多份稿件并存且可区分，不覆盖旧稿。
- **REQ-S01-21** ✅ 存在多份自然稿时，必须由用户明确采用一份；不按时间自动采用。
- **REQ-S01-22** ✅ 阶段完成 = 能解析到被采用的剧本源。模型文字或界面提示不算证据。
- **REQ-S01-23** ✅ 本阶段只产出 `emotion_curve.json`（编辑角色写出的辅助质检数据，无需用户确认）；角色／场景／道具 manifest 属剧本结构，`scene_breakdown.json` 属初步分镜。

### 引擎

- **REQ-S01-30** ✅ 支持 API 与桌面两种调用方式：API 由程序自动归档正文；桌面方式生成任务并复制正文，由用户粘贴发送。
- **REQ-S01-31** ✅ SKILL 内容超预算或缺失时阻止发送，不截断、不静默省略。

### 非目标（明确不做）

- 不做多轮自由状态机；肯定回复只推进当前一步。
- 不在本阶段生成分镜、资产或首帧。

## S02 剧本结构

目标：把 S01 被采用的自然剧本整理成可追溯的结构剧本（角色／场景／道具档案 + 分场），作为初步分镜的唯一剧本源。不改写原稿。

### 输入与依赖

- **REQ-S02-01** ✅ 唯一输入是 S01 被采用的自然剧本（`resolve_script_source`）。找不到时报错并停止，不创建任何产出。S01 的设定、大纲、角色卡不进入本阶段输入。
- **REQ-S02-02** ✅ 本阶段不采集、不要求任何制作锁值；锁值由 S01 填写，本阶段只读用。
- **REQ-S02-03** ✅ 依赖 S01 完成；自动链上 S02 失败时不跳过；串行执行，失败重试 2 次后阻塞。

### 整理流程

- **REQ-S02-10** ✅ 默认路径是本地规则整理，不调用模型；结构剧本中标明“本地规则提取”。
- **REQ-S02-11** ✅ 流程固定六步：读原稿 → 提取 → 校验 → 按反馈重提取 → 复审 → 写入。用户点“手动制作结构剧本”即视为对这六步的确认。
- **REQ-S02-12** ✅ 结构剧本含「角色档案」「场景档案」「道具档案」「分场剧本」四区。角色档案每人含别名、跨集 ID、物理特征、默认服装、换装需求；场景含空间锚点、光照方向、尺度参考；分场含出场角色、情绪基调、起止状态、正文。
- **REQ-S02-13** ✅ 只认原稿写出的事实；原稿没写的一律标“待确认”，不编造。
- **REQ-S02-14** ✅ 校验不通过时按反馈重提取；复审仍不通过则不写入。原稿自相矛盾（同一道具多种尺寸）不静默修补，停止并提示用户先改原稿。
- **REQ-S02-15** ✅ 本阶段不做镜头三元组、镜头拆分、分镜 JSON、首帧或媒体提示词（属 S03）。

### 产出与完成

- **REQ-S02-20** ✅ 结构剧本只能经 `write_structured_script` 原子发布；空正文拒绝；原稿保持不变；发布同时记录来源血缘。
- **REQ-S02-21** ✅ 一份稿件算“结构剧本”，需标题为「# 结构化剧本」、有档案区，且来源不是大纲／梗概；记录的来源原稿被删除后，该结构稿不再显示，不删文件。
- **REQ-S02-22** ✅ 阶段完成 = 能解析到合格的结构剧本。模型文字、界面提示、manifest 是否存在都不算证据。
- **REQ-S02-23** ❓ `character_manifest.json`／`scene_manifest.json`／`prop_manifest.json` 归本阶段（`script-character-extraction` SKILL）。现状：默认本地规则路径不写这三份，只有模型执行该 SKILL 时才可能落盘，且无程序核验。是否要求本阶段必须产出并核验，待拍板。
- **REQ-S02-24** ✅ 新结构剧本写入 `02剧本结构/结构剧本/`；旧 `writing/` 目录只读兼容，不再写回。
- **REQ-S02-25** ❓ `PRODUCERS` 登记的 manifest 落盘目录仍是旧名 `00_script`，与本阶段新写目录 `02剧本结构` 不一致。是否改为新目录，待拍板。

### SKILL

- **REQ-S02-30** ✅ 本阶段有 5 个 SKILL：`pipeline-script-structure`（总入口，默认勾选）、`script-structured-generation`、`script-character-extraction`、`script-dialogue-polish`、`script-worldbuilding`；后四个为可选勾选。
- **REQ-S02-31** ✅ 台词润色并回结构剧本的台词段，不单独出文件；世界观整理产物落 `docs/world_bible.md`。

### 非目标（明确不做）

- 不重写或替换自然剧本原稿。
- 不在本阶段产出 `emotion_curve.json`（S01）或 `scene_breakdown.json`（S03）。
- 不设本阶段独立门禁；S02 → S03 只靠依赖串行。

## S03 初步分镜

目标：以已确认的结构剧本为唯一来源，按场景并行制作可通过助手校验的分镜 JSON（镜头链），经校验后"采用"，作为分镜预演（S04）及后续阶段的输入。本阶段不整理角色／场景／道具档案，不重写结构剧本。

### 输入与启动

- **REQ-S03-01** ✅ 输入只有"初步分镜"栏中已选的结构剧本（`storyboard_work_plan` → `selected_many(root,'script')`）。读取输入失败，或一份结构剧本都没选，启动失败并提示，不创建任何产出。
- **REQ-S03-02** ✅ 依赖 S02 完成（`DEPENDS['storyboard']=('script_structure',)`）。本阶段不采集、不要求制作锁值（`STAGE_LOCK_REQUIREMENTS` 不含 `storyboard`）。
- **REQ-S03-03** ✅ 启动前先过总控制作锁门禁，手动与自动同样阻断；入口只有 `stage_handler_registry.start()`。
- **REQ-S03-04** ✅ 待办 = 尚未产出分镜的结构剧本；待修订 = 已有分镜 JSON 但尚未采用的文件。两者都为空时不再启动 Agent：自动触发播报"已确认所有已选结构剧本的分镜均已生成并采用"，手动触发无动作。
- **REQ-S03-05** ✅ 并行配置：按场景分单元，同时 2–3 路（上限 3），同一场景内镜头必须串行；失败重试 2 次后阻塞（`stage_parallel.CONFIG['storyboard']`）。
- **REQ-S03-06** ✅ 同一集只输出一份分镜 JSON，已存在则跳过并说明，不生成副本、不换文件名重写；各场景做完后按剧本顺序拼接，并核对跨场景衔接（上一场结束状态＝下一场开始状态）。

### 分镜 JSON 契约

- **REQ-S03-10** ✅ 顶层必有 `episode_id`、`title`、`duration`、`source_script`、`shots`（非空数组），`prompt_language` 为 `"zh"`；所有提示词与对白用简体中文，编号、路径等专有标识保留原文（`storyboard_contract.rules`）。
- **REQ-S03-11** ✅ 每镜必有 `id`（`SH001` 格式、不重复）、`title`、`duration`（2–15 的整数秒）、`characters`、`location`、`props`、`frame`（`frames/镜头编号.png`）、`frame_prompt`、`video_prompt`、`dialogue`。
- **REQ-S03-12** ✅ `video_prompt` 为独立非空字符串，1–1500 字符，整合景别机位、动作起止、运镜、原对白与声音；`frame_prompt` 只写静止的动作起点。
- **REQ-S03-13** ✅ 各镜时长合计等于顶层 `duration`；使用剪辑字段时须满足 `0<=trim_in<trim_out<=duration`、`edit_duration=trim_out-trim_in`。动作或对白超过 15 秒须按动作闭合点拆镜，不得截断、加速台词或放宽校验。
- **REQ-S03-14** ✅ 多集任务镜头编号按集号从小到大连续：集号最小的集从 `SH001` 起，下一集紧接上一集最后编号，不按处理或并行完成顺序分配。
- **REQ-S03-15** ✅ 每镜写清镜头三元组（核心人物／主体、可见动作、景别机位与运镜），人物主导权变化、动作起止、转场或情绪转折按动作闭合点切镜；不把结构剧本的角色／场景／道具档案重复写入分镜。
- **REQ-S03-16** ✅ 背景人物、群演、路人、不露脸或一次性角色不写入 `characters`、不分配 CHAR 编号；普通道具写 `ordinary_props`，不分配 PROP 编号。
- **REQ-S03-17** ✅ 每镜补充 `action_complexity`（simple/medium/complex）及 `complexity_reason`，决定后续是否需要白模。
- **REQ-S03-18** ✅ 提交前须用 `validate_episode(JSON对象, media_root(JSON路径))` 本地校验，仅查本地数据、不调用模型；必须修复全部错误才算完成，未生成参考图只是待制作警告。
- **REQ-S03-19** ❓ 契约与阶段输出契约都把"通过校验并采用后的 JSON"称为"分镜定稿"，并称其"锁定"来源剧本、编号、镜头编号、时长、台词与连续性约束；但 `pet_bus.STAGES` 的"分镜定稿"是第 07 阶段，且 07 才做批次划分与三元组补全。冲突证据：`storyboard_contract.py:44`、`workflow_settings.py:130` 对 `stage_layout.py:49`（07 的职责）。请拍板：03 采用后仍叫"分镜初稿"，"分镜定稿"留给 07；或两者保持现状。
- **REQ-S03-20** ❓ 阶段并行提示要求本阶段"生成每个镜头时核对三元组并写入 `batch_id`"（`stage_parallel.py:203`），但批次划分的权威阶段是 07 分镜定稿（SG-03 查 `batch_id`、每批 ≤4 镜且 ≤18 秒，`stage_layout.py:49`）。03 是否要写 `batch_id`、写了是否算数，请拍板。

### 采用（分镜初稿 → 后续阶段）

- **REQ-S03-30** ✅ 采用前对整批（已采用＋新增）逐份校验：来源剧本必须是"初步分镜"栏中实际可用的一份（`source_script_error`），且 `validate_episode` 通过；任一份不过则整批拒绝，不改采用记录也不改资产计划，报错带文件名与具体问题。
- **REQ-S03-31** ✅ 采用成功后同步资产计划（`asset_plan._sync_plan`），再把采用清单 `adopted_storyboards` 与当前分镜 `frame_json` 写入项目 `ui_settings.json`；`adopted_storyboards` 缺失时回退读旧单值 `frame_json`。采用清单中的文件必须在项目内且存在。
- **REQ-S03-32** ✅ 无人值守自动采用（`adopt_pending`）：只处理新出现的分镜 JSON；刚写入不足 10 秒的文件记为 waiting 下轮再看；不合法的只跳过它，其余照常采用；整批只同步一次资产计划；重复调用不重复采用。
- **REQ-S03-33** ✅ 取消采用（`remove`）只改采用清单与当前分镜指针，并按剩余清单重同步资产计划，不删分镜文件；当前分镜指针（`focus`）只能指向已采用的分镜。
- **REQ-S03-34** ✅ 来源剧本已失效的 JSON 由 `prune_invalid_adoptions` 取消采用，保留 JSON 文件和历史资产。
- **REQ-S03-35** ✅ 刚创建项目时的种子分镜（`EP001`/`SH001`/"待编写"）不当作已制作的分镜。

### 产出、路径与完成

- **REQ-S03-40** ✅ 新分镜 JSON 写入 `03初步分镜/分镜拆分/`，可读文档写入 `03初步分镜/分镜文档/`；旧 `storyboard/分镜拆分` 目录只读兼容。同一媒体根（`media_root`）对新旧目录一致。目录扫描拒绝符号链接逃逸、空文件，并忽略 `历史版本`、`分镜历史`、`剧本输入`、`frames`、`video_prompts`、`assets`、`首帧任务` 等内部目录。
- **REQ-S03-41** ✅ 阶段完成 = 至少有一份已采用且含镜头的分镜 JSON（`stage_completion_service` → `stage_parallel._adopted`）。模型文字、界面提示不算证据；没有已采用分镜时报"还没有已采用且含镜头的分镜 JSON"。
- **REQ-S03-42** ✅ 门禁 SG-A（初步分镜 → 分镜预演）：已采用分镜且各镜提示词与时长完整，否则挡住，提示"先完成并采用初步分镜"。
- **REQ-S03-43** ❓ `stage_layout.STAGES` 与 `architecture.md` 声明本阶段产物名为固定的 `storyboard_draft.json`，并作为 04–07 阶段的输入名；实际没有任何代码写这个文件名，产物是模型命名的分镜 JSON（`分镜拆分/` 下），后续阶段读的是"已采用分镜清单"。该名只剩声明（仅 `tests/test_animatic_service.py` 用作测试夹具文件名）。请拍板：把声明改为"已采用的分镜 JSON"，或真的固定文件名。（architecture.md 已按现状改写，stage_layout 属契约代码，本轮未动。）
- **REQ-S03-44** ❓ `script_manifest_schema.PRODUCERS` 把 `scene_breakdown.json` 的产出方登记为本阶段 `storyboard-scene-breakdown` SKILL，其他文档也称之为"五类剧本 manifest"之一。现状：阶段完成与 SG-A 都不检查它，没有任何下游消费它，默认流程也不要求产出；与 REQ-S02-23 同类。请拍板：是否要求本阶段必须产出并核验 `scene_breakdown.json`。落盘目录同样沿用旧名 `00_script`（同 REQ-S02-25）。

### SKILL

- **REQ-S03-50** ✅ 本阶段有 6 个 SKILL（`skills/03初步分镜SKILL/`）：`pipeline-storyboard-draft`（总入口，AIGC 全流程预设默认使用）、`storyboard-scene-breakdown`（场次拆分）、`storyboard-shot-generation`（镜头链）、`storyboard-camera-language`（景别角度运镜）、`storyboard-duration-estimate`（时长预估）、`storyboard-pacing-check`（节奏检查）。
- **REQ-S03-51** 🟡 `workflow_settings` 的单独"初步分镜"流程默认技能是外部包 `short-drama-storyboard`，与 AIGC 全流程预设里的 `pipeline-storyboard-draft` 并存；两条入口对应哪种用户场景、何者为准，文档未说明。暂按现状记录，待确认。

### 非目标（明确不做）

- 不整理角色／场景／道具档案、不改写结构剧本（属 S02）。
- 不做批次划分、连贯性台账、定稿锁定（属 S06／S07，见 REQ-S03-19/20）。
- 不生成首帧、预演草图或任何媒体；不调用视频模型。
- 不设本阶段的人工确认门；S03 → S04 靠 SG-A。
- 手动启动分镜预演不经本阶段（`start('animatic')` 总是转到预演页并提示选择参考图与临时声音）。

## S04 分镜预演

目标：以已采用的分镜初稿、共享参考图和临时声音，在本地生成逐镜草图并合成可播放的 Animatic，让用户在进入资产管理之前人工确认节奏、时长和对白同步。预演只是验证用的草稿，不是正式资产、首帧或正式视频。

### 输入与启动

- **REQ-S04-01** ✅ 本阶段是第 4 阶段（`pet_bus.STAGES` 中 `animatic`，目录 `04分镜预演`），依赖 S03 完成（`stage_flow.DEPENDS['animatic']=('storyboard',)`）；S05 资产管理依赖本阶段（`DEPENDS['assets']=('animatic',)`）。
- **REQ-S04-02** ✅ 输入三样：被采用的分镜 JSON（来源必须在已采用清单里，否则报"请选择已采用的本项目分镜初稿"）、共享参考图（至少一张非空图片）、临时声音（导入的音频，或由临时 TTS 文本合成；两者都没有则失败）。
- **REQ-S04-03** ✅ 手动启动（`stage_handler_registry.start('animatic')`）不自动出图：只切换到预演页、不调用任何生成函数；三虎自动触发时另发"阶段失败"事件，附"分镜预演需要选择参考图与临时声音，生成后请您确认节奏、时长和对白同步"，手动触发无文字返回。生成必须由用户在预演页明确点击。
- **REQ-S04-04** ✅ 本阶段不设制作锁必填项（`STAGE_LOCK_REQUIREMENTS` 不含 `animatic`）；预演画幅跟随项目已填的画幅锁，分辨率与帧率固定为低配预览规格（`animatic_preview_spec`），不受正式交付规格影响。
- **REQ-S04-05** ✅ 开始生成前必须通过 SG-A（`animatic_input_ready`）：已采用分镜非空，且每镜都有安全且唯一的镜头 ID、图片提示词和 0–600 秒内的有效时长；否则拒绝并提示"先完成并采用初步分镜"。
- **REQ-S04-06** ✅ 本地依赖就绪才开工：ffmpeg、ffprobe 路径可解析（设置 > 项目配置 > 运行环境），本地 ComfyUI 先等待就绪；缺任何一项直接报错，不产生半成品。

### 共享参考图

- **REQ-S04-10** ✅ 共享参考图只有两个来源：用户导入（PNG/JPEG/WebP，单张不超过 20 MB，按内容摘要命名去重）、本地 ComfyUI 文字草图（需填描述与本地已安装模型名）。两者都经 L3 原子发布到 `stage_path_service` 提供的共享参考图目录。
- **REQ-S04-11** ✅ 读取参考图时同时覆盖新旧共享参考图目录，按路径去重。

### 草图与合成

- **REQ-S04-20** ✅ 每镜草图用分镜提示词、全部共享参考图和固定种子（默认 1）经本地 ComfyUI 生成，提示词前带"只生成分镜预演草图，不是正式资产或首帧"。
- **REQ-S04-21** ✅ 并行：按 `batch_id` 分批，批与批并行（上限 3），批内逐镜串行；分镜没有 `batch_id` 的全部归入同一批（`default`）。
- **REQ-S04-22** ✅ 只有明确的生成失败（`ComfyGenerationFailed`）才重试，最多 2 次；耗尽后报"镜头 X 生成失败且重试耗尽，请人工核查"并转人工。
- **REQ-S04-23** ✅ 提交结果不确定（ComfyUI 仍在排队或超时）不自动重投：报错请人工核查，已提交的回执保留在持久工作区（`04分镜预演/.work/run-*`），不随临时目录清理。
- **REQ-S04-24** ✅ 临时声音：有导入音频优先；否则按临时 TTS 文本合成，文件名含脚本签名，已存在且非空则复用，不重复合成（即使后面的出图失败，重跑也复用）。
- **REQ-S04-25** ✅ 合成：每镜图片按各自时长生成片段，拼接后叠加声音，输出 H.264/AAC 的 `animatic.mp4`；输出必须同时含视频流与音频流，总时长与各镜时长之和相差不超过 1 秒，并通过完整解码核验，否则本次不发布。
- **REQ-S04-26** ✅ 预演不改资产：不登记正式资产、不改资产提示词、正典板、锚点与 `assets.json`；正式资产仍走线上 API 生成。

### 发布与完成

- **REQ-S04-30** ✅ 成果写入 `04分镜预演/`：`animatic_manifest.json`、`assets/animatic.mp4`、`assets/temporary_audio.*`、`assets/shots/<镜头ID>.*`、发布器生成的 `animatic_index.json`。所有生成发生在暂存区，整包校验后才一次性原子发布，任何一步失败都回滚（含索引），不留半包。
- **REQ-S04-31** ✅ 发布前整包校验：清单 `kind=animatic`；清单 `files` 与暂存文件一一对应且摘要一致；视频、音频、每镜图都在 `files` 内且非空；`confirmed` 三项必须全为 `false`（生成器不得替用户签字）；成果路径不得越出阶段目录，`animatic_index.json` 只允许发布器写。
- **REQ-S04-32** ✅ 清单记录来源分镜相对路径及其 SHA-256；生成过程中来源分镜被改动则本次不发布。
- **REQ-S04-33** ✅ 观看预演（`animatic_video`）只要成果完整（不要求已确认）就返回视频路径，否则报原因。
- **REQ-S04-40** ✅ 人工确认：节奏、时长、对白同步三项必须一次全部勾选才能确认（`confirm_animatic`）；成果不完整时不能确认；确认只改清单的 `confirmed`，经原子发布。重新生成会把三项重置为未确认。
- **REQ-S04-41** ✅ 阶段完成 = `animatic_service.evidence` 通过：清单存在；来源分镜存在且摘要未变；视频、音频、每镜图都在项目内、非空、摘要与清单一致；三项人工确认全为 `true`。模型文字、界面提示、生成成功本身都不算证据；来源分镜变化后需重新预演并确认。
- **REQ-S04-42** ✅ 门禁 SG-B（分镜预演 → 资产管理）调用同一核验：Animatic 可播放，节奏、时长、对白同步已确认；否则提示"先完成分镜预演并确认三项检查"。
- **REQ-S04-43** ✅ 大媒体核验用流式摘要（`file_cache.file_digest`），不整段读入内存。

### SKILL

- **REQ-S04-50** ✅ 本阶段只有 1 个 SKILL：`pipeline-animatic`（`skills/04 分镜预演SKILL/`，免费、依赖 `pipeline-storyboard-draft`，工具 `animatic.generate`、`animatic.validate`，二者都打开预演页）。
- **REQ-S04-51** ✅ SKILL 的约束与本文一致：仅本地草图、不替代正式资产／首帧／正式视频、资产提示词归资产管理；需要剪映时另行交接，应用内合成不声称剪映原生导出。
- **REQ-S04-52** 🟡 SKILL 正文"本阶段读取的项目锁"列出 8 项以上锁（赛道、素材来源、分辨率、帧率、视频模型等），并称"必填项缺失记为配置缺口并返回准备阶段"。代码里本阶段只读画幅锁（预览规格），不要求任何锁，也不检查缺口（见 REQ-S04-04）。该段是跨阶段模板口径；是否要把它收窄为"只读画幅"，待最终验收时确认。

### 待拍板

- **REQ-S04-60** ❓ `stage_layout` 声明本阶段输入为固定名 `storyboard_draft.json`、并为 `04分镜预演` 登记了 `animatic_notes.md`（"节奏、时长与对白同步确认记录"），但实际没有任何代码写这两个文件：输入是"已采用分镜清单"，确认记录只写进 `animatic_manifest.json` 的 `confirmed`。前者与 REQ-S03-43 同类。请拍板：把声明改为现状，或真的落地 `animatic_notes.md`。（证据：`stage_layout.py:43-44`、`:124`。）
- **REQ-S04-61** ❓ 预演按 `batch_id` 分批，但批次划分的权威阶段是 07 分镜定稿，03 是否写 `batch_id` 本身也未定（REQ-S03-20）。现状是 03 通常不写，预演实际只有一批，"跨批并行"在默认流程下不会发生。请与 REQ-S03-20 一并拍板。
- **REQ-S04-62** ❓ 预演的成果（草图、临时声音）不被任何下游阶段读取；资产管理与后续阶段只读 SG-B 的通过结果。是否保留这些文件作为后续阶段的参考（例如白模预演）未在文档中规定。请拍板是否需要下游消费。

### 非目标（明确不做）

- 不生成正式资产、首帧、正式视频或正式配音（属 S05、S08、S10、S11）。
- 不做节奏／时长／对白的自动评判；三项确认只能由人完成。
- 不自动导出剪映工程。
- 不修改分镜初稿；发现问题回到 S03 修订并重新采用。

## S05 资产管理

目标：把已采用的分镜初稿里出现的角色／场景／道具，整理成带稳定编号、可追溯来源的资产清单，并为角色建立正典板与锚点；资产图片全部导入、角色锚点锁定后，才放行连贯性清单（SG-01）。

### 输入与依赖

- **REQ-S05-01** ✅ 资产清单只由「已采用」的分镜 JSON 导出（`asset_plan` 在非采用流程里按 `storyboard_adoption_contract.adopted` 过滤来源）。项目里没有采用任何分镜时，`active_source` 报“请先…点「手动采用分镜」”，不凭空建清单。
- **REQ-S05-02** ✅ 依赖分镜预演：`stage_flow.DEPENDS['assets']=('animatic',)`；入口闸 SG-B（分镜预演确认：Animatic 可播放，节奏、时长、对白同步已确认）。生成正式资产前由 `require_formal_asset_generation` 核验 SG-B，且必须选线上 API 模型；纯计划与浏览不受限。
- **REQ-S05-03** ✅ 本阶段不采集、不要求制作锁值；`track`、`aspect_ratio`、`resolution` 等锁值由 S01 填写，本阶段只读用（画幅默认 `16:9`、分辨率默认 `1920x1080`，项目锁优先）。
- **REQ-S05-04** ✅ 共享参考图目录 `reference_images` 由分镜预演准备、本阶段复用；资产提示词、正典板、锚点职责仍归本阶段。本地 ComfyUI 草图不进入正式资产登记。
- **REQ-S05-05** 🟡 `pipeline-assets` SKILL 的 `input` 列了 `characterManifest`／`sceneManifest`／`propManifest`／`sceneBreakdown`／`emotionCurve`，但程序（`asset_plan`）并不读这些 manifest，清单完全从分镜镜头里的 `characters`／`location`／`props` 引用导出。S02 默认路径也不写这三份 manifest（见 REQ-S02-23）。两者口径需统一，待拍板。

### 资产清单与契约

- **REQ-S05-10** ✅ 资产编号格式 `CHAR_###`／`LOC_###`／`PROP_###`（至少三位）；分镜里写的是名称时，按名称／别名匹配已有编号，匹配到多个编号报错要求在分镜中指定，匹配不到则新分配下一个空号。
- **REQ-S05-11** ✅ 清单同步不覆盖已有内容：只补缺失的契约字段（`asset_contract.normalize` 只补缺的键），已有值一个不动；`used_in` 记录引用该资产的镜头编号。
- **REQ-S05-12** ✅ 只有被标记“需要独立资产”的道具才进清单（`prop_assets.requires_asset`）；普通道具写进镜头提示词，不分配编号。
- **REQ-S05-13** ✅ 角色字段：`character_anchor`（锚点字符串）、`base_anchor`、`canonical_board`／`canon_board_views`（正典板，7 格：前／右／左／背 4 张全身 + 3/4 左／正面／3/4 右 3 张头部）、`state_variants`（编号 `CST-01` 起，每项含 `override`）、`reference_role`（默认“面部、发型、服装”）、`reference_exclude`（默认“场景、动作、镜头”）、`locked`、字段化 `physical_features`。
- **REQ-S05-14** ✅ 校验规则（`asset_contract.validate`，返回问题列表，空为通过）：角色锁定前锚点不能为空；正典板视角名须是 7 个已知视角；状态编号须形如 `CST-01`、不得重复、必须有 `override`；`physical_features` 不得是整句字符串；缺 `canonical_board` 且无 `canon_board_views` 报缺。场景须有合法 `aspect_ratio`（如 `16:9`）、`resolution`（如 `1920x1080`）和成对的 `spatial_anchors`（`object`+`position`）。道具 `holder` 为空或形如 `CHAR_###`。
- **REQ-S05-15** ✅ 分镜引用的编号在清单里缺 `name` 或生图提示词，由 `missing_ids` 报出（门禁 G-04 使用）。
- **REQ-S05-16** ✅ 清单、名称编号对照、来源、导入进度四份文件作为一个发布包原子写入，写后复核；失败则整体回滚到发布前（`asset_plan._publish_plan_bundle`）。
- **REQ-S05-17** ✅ 只有登记过且文件真实存在于资产库内的图片才算“已导入”；计划里自带的 `image` 路径不被采信（`sync_plan` 先剔除再按登记表回填，状态为“已导入／待导入”）。

### 流程与执行

- **REQ-S05-20** ✅ 一项资产一个 Agent；每项内部固定串行：正典板 → 状态变体 → 锚点 → 参考职责。并发 3–5（上限 5）；失败重试 2 次（固定间隔），耗尽后阻塞（`ON_BLOCK`）。
- **REQ-S05-21** ✅ 默认只出提示词，不因启动本阶段自动出图；实际出图须有明确授权，沿用候选确认、预算与执行器。付费阶段（`PAID_STAGES` 含 `assets`）受预算约束。
- **REQ-S05-22** ✅ 资产图片制作后端：本地与云端模型名由 L0 `production_model_contract` 统一；正式资产请选线上 API 模型。
- **REQ-S05-23** ✅ 新写入目录为 `05资产管理/`；旧 `04资产管理`（R1124 前编号）与 `episode/assets/资产清单` 仅只读兼容，不再写回；旧目录 `02_assets` 为更早的别名。

### 产出与完成

- **REQ-S05-30** ✅ 阶段完成 = SG-01（`assets_locked`）通过且 `started`：清单每项都导入了真实非空图片；每个 `CHAR` 都 `locked`；每个 `CHAR` 都有 `character_anchor`（或 `base_anchor`）。模型文字、界面提示、manifest 是否存在都不算证据（`stage_completion_service`）。
- **REQ-S05-31** ✅ SG-01 只拦“做过但没做全”：清单不存在、读不出来，或只有刚扫出来的名字（无图、无锁、无锚点）且阶段机没跑过，一律放行并标未开始。
- **REQ-S05-32** ❓ 需拍板（疑似缺陷）：SG-01 读 `资产清单/assets.json` 里的 `image`，但程序登记图片只写图片登记表 `<资产库>/assets.json`（`asset_batch_service.register_image`／`import_asset_image`／恢复）；`sync_plan` 又把 `image` 从清单文件剔除。实测：清单里有锁与锚点、登记表里有真实图片时，SG-01 仍报“1 项资产还没导入图片”。端到端探针靠手工把 `image` 同时写进两份文件才通过。需确认是以登记表还是清单为准，再改门禁或写入点。
- **REQ-S05-33** ✅ 用户可见的资产删除走回收站（`storage_maintenance.recycle_paths`）；删除前由 `deletion_references`／`asset_impact` 列出被哪些镜头引用；恢复可还原相同字节。

### SKILL

- **REQ-S05-40** ✅ 本阶段 SKILL 位于 `skills/05资产管理SKILL/`：`pipeline-assets`（总入口，`dependsOn: pipeline-animatic`，不并行，不付费，输出 `assetManifest`／`canonBoard`／`anchors`）、`asset-auto-fill`、`asset-candidate-wall`（用户确认后才入库）、`asset-copyright-filter`、`asset-dedupe`、`asset-visual-rank`。
- **REQ-S05-41** ✅ 资产缺少来源、身份锚点或版本时不得进入正典；发现冲突只生成待修复项，不覆盖已确认资产。SKILL 只按需读取 `continuity-bible.md` 与 `image-model-adapters.md` 的相应章节，不注入 00 包全文。
- **REQ-S05-42** 🟡 `asset_contract.panel_text()` 仍写“资产管理页（02_assets）”“06 连贯性清单”，与现行 `05资产管理`、阶段 06 编号不符（代码文案陈旧，未改动）。

### 非目标（明确不做）

- 不在本阶段生成首帧、视频或配音。
- 不覆盖已确认的资产或锚点；不改写用户项目里的参考图。
- 不设 SG-01 之外的本阶段出口闸；SG-B 是入口闸。
- 不把 `emotion_curve`／`scene_breakdown` 等 manifest 作为程序必需输入（见 REQ-S05-05）。

## S06 连贯性清单

目标：把 S03 被采用的分镜与 S05 资产清单交叉核验，冻结必须逐字保住的锚点，列出冲突、批次三元组与跨批次不一致，形成连贯性台账；它是 S07 分镜定稿的前置检查，不生成任何内容。

### 输入与依赖

- **REQ-S06-01** ✅ 输入是当前被采用的分镜 JSON（`storyboard_selection.current_source`）和本集资产清单（S05 的 `assets.json`）。读不到时按空分镜／空资产计算，不报错。
- **REQ-S06-02** ✅ 依赖 S05（`stage_flow.DEPENDS`）。上游门禁 SG-01（资产锁定，`assets_locked`）、下游门禁 SG-02（连贯性台账，`ledger_ready`）；门禁只拦“已开始但不完整”，空项目放行。本阶段全局串行（1 个 Agent），失败重试 2 次后阻塞。
- **REQ-S06-03** ✅ 本阶段不采集、不要求制作锁（`STAGE_LOCK_REQUIREMENTS` 不含 continuity）；SKILL 只读用 S01 填写的锁。

### 清单流程

- **REQ-S06-10** ✅ 台账由 `continuity_ledger.build(shots, assets)` 按规则现场计算，不调用模型。
- **REQ-S06-11** ✅ 台账含 `batches`（批次与冻结锚点）、`conflicts`、`cross_batch`、`triplets`、`drift`、`summary`（批次数、镜头数、是否通过、待办列表），`version=1`。
- **REQ-S06-12** ✅ 冻结锚点逐字取自资产：角色（含服装状态覆盖）、场景（光源＋空间锚点＋尺度）、道具（材质＋尺度）；资产里没有的不补、不改写。
- **REQ-S06-13** ✅ 参考图冲突两类：“职责自相矛盾”（一张图既管身份又管场景／动作／运镜且排除项没写）与“多图抢同一件事”；裁决规则是先出现的参考图负责身份，其余只补风格与光影。
- **REQ-S06-14** ✅ 三元组：每批一行；同一批内 scene_id＋character_ids＋costume_id 出现多种即不通过，提示重切批次，本阶段不改批次划分。
- **REQ-S06-15** ✅ 跨批次：同一锚点（类型＋编号＋状态）在不同批次字符串不一致即不通过；分镜里的 `continuity_flags` 作为“全程必须保住”项记入。
- **REQ-S06-16** 🟡 漂移只比较角色锚点，不比较场景和道具；重建台账时冻结值与现值取自同一份资产，恒为一致，只有把已落盘台账与当前资产对比（G-09 `check_drift`）才有意义。
- **REQ-S06-17** ✅ 本阶段不生成图片／文字内容、不重新描述锚点、不改分镜、不改资产。

### 产出与完成

- **REQ-S06-20** ✅ 台账、人读版、共享锚点库、三元组字典四个文件一次发布（`publish_bundle`）：`06连贯性清单/output/continuity_ledger.json`、`06连贯性清单/docs/continuity_ledger.md`、`_shared/anchors/anchors.json`、`_shared/triplets/triplets.json`；写后读回校验，任一失败恢复旧字节；重复写入结果一致。
- **REQ-S06-21** ✅ 问题闭环登记 `06连贯性清单/output/continuity_issues.json`：问题编号稳定（`CI-<类型>-<范围>`），状态待处理／已忽略／已解除；忽略必须写理由并记当时证据摘要；证据变化或问题复现则重开；修好自动解除；只有 L3 注入发布器才落盘，否则只读预览。
- **REQ-S06-22** ✅ 严重度：职责自相矛盾、三元组不一致为“高”，锚点漂移、跨批次不一致为“中”。
- **REQ-S06-23** ✅ 阶段完成 = SG-02 `ledger_ready` 通过且 `started`（台账已生成）。台账未生成时门禁放行但不算完成；台账有未处理问题时不通过；被忽略或已解除的问题不再拦；台账说有问题却算不出问题行时不擅自放行。
- **REQ-S06-24** ❓ SG-02 只读已落盘台账，不核对它是否对应当前分镜／资产：台账生成后再改分镜或资产仍放行；另外，空分镜也能生成 0 批次的通过台账并被判完成。是否要求台账与当前输入同版，待拍板。
- **REQ-S06-25** 🟡 页面为现场计算、不落盘；只有“手动生成连贯性清单”才写盘并同步问题登记。
- **REQ-S06-26** ❓ 主观门禁 G-08（“多图抢同一件事”的优先级裁决）不计入台账待办，SG-02 不要求先裁决，只有“职责自相矛盾”阻塞；而 `confirm_gates` 和恢复提示（`stage_flow` RECOVERY_HINTS）把“人工裁决”写成本阶段要做的事。裁决是否应成为放行条件，待拍板。
- **REQ-S06-27** 🟡 台账 `stage` 字段与 SG-02 返回的 artifacts 仍写旧内部标识 `03_continuity`（实际目录 `06连贯性清单`，artifacts 指向不存在的路径）；`stage_layout` 别名兼容读写，功能不受影响。旧 `05连贯性清单` 目录只读。

### SKILL 与引擎

- **REQ-S06-30** ✅ 本阶段 6 个 SKILL，位于 `skills/06连贯性SKILL/`：`pipeline-continuity`（总入口，预设默认勾选）、`continuity-anchor-freeze`、`continuity-conflict-adjudicate`、`continuity-cross-batch-guard`、`continuity-drift-audit`、`continuity-triplet-check`。
- **REQ-S06-31** ✅ SKILL 的 `continuity.*` 工具在 `skill_tools` 登记；`continuity.buildLedger` 直接调用 `continuity_ledger.build/write` 本地落盘，其余工具对应页面上的裁决／校验表。
- **REQ-S06-32** ❓ `pipeline-continuity` 声明由模型执行（capabilities 含 reasoning、vision，preferredModels qwen-max，输出 `continuityLedger`、`repairList`），实际实现是纯本地规则，且不存在 `repairList` 文件（对应物是 `continuity_issues.json`）。SKILL 描述与实现哪个为准，待拍板。
- **REQ-S06-33** ❓ 三虎自动链没有自动生成台账的入口：`PET_STAGE_POLL` 不含 continuity，`desktop.pet_start` 对本阶段返回空串；自动档只会按推荐自动选 G-05／G-06／G-08 候选。因台账缺失时 SG-02 放行，自动链会越过本阶段。是否要补自动生成，待拍板。

### 非目标（明确不做）

- 不生成或重新描述锚点、不改写分镜、不重切批次（批次划分属 S03／S07）。
- 不做首帧、白模、视频一致性的图像级比对。
- 不设独立的“放行”权限：分镜定稿放行以 SG-02 为准，D 锁（`splice_mode`）只读用。
