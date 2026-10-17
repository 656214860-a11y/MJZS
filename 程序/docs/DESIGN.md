# 设计（DESIGN）

本文件描述**怎么实现** REQUIREMENTS.md，原地修改。每条 `DES-xx` 标注实现的 `REQ-xx`。
全局分层（L0–L5）与唯一权威源表暂仍以 architecture.md 为准，试点验收后并入本文件。

## S01 剧本准备

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_writing_page` / `desktop_idea_chat` | 页面、气泡对话、Agent 派发；只注入回调 |
| L3 | `idea_chat_controller` | 对话状态与回调编排，无 Tk |
| L3 | `idea_semantic_brief_service` | 语义简报提取与校验 |
| L3 | `stage_execution_service` | 确认／重写／自然稿采用的编排入口 |
| L2 | `idea_chat` / `idea_brief_form` / `idea_attachments` | 回复落盘、简报门禁、附档 |
| L2 | `writing_api` | 四步状态、肯定回复、重写、自然稿发布 |
| L0/契约 | `script_contract` | 简报必填字段、阶段锁、文件命名、剧本源解析 |

### 设计条目

- **DES-S01-01**（REQ-S01-02）简报必填字段唯一定义在 `script_contract.BRIEF_REQUIRED_FIELDS` / `INLINE_REQUIRED_LABELS`；`idea_chat` 不另设判断。
- **DES-S01-02**（REQ-S01-03）锁值必填项唯一定义在 `script_contract.STAGE_LOCK_REQUIREMENTS['script']`；采集走创作信息窗（简报流）。总控门禁对简报对话豁免。
- **DES-S01-03**（REQ-S01-04）会话目录 `01剧本准备/模型会话/<稳定模型ID--摘要>/创意对话/`；旧显示名目录在首次读取时迁移。
- **DES-S01-10**（REQ-S01-10/11/13）`writing_api.PREPARATION_STAGES` 定义①②③；模型返回 `{"next_stage":"自然剧本"}` 后由程序启动④。四步状态存 `preparation_state.json`。
- **DES-S01-12**（REQ-S01-12）肯定词表在 `writing_api`；取首行、去句末标点后比较。
- **DES-S01-14**（REQ-S01-14）重写请求暂存在 `preparation_state.json` 的 revision 中，确认后替换当前及下游的确认，并撤销自然稿采用。
- **DES-S01-15**（REQ-S01-15）三角色由 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 的「定向注入（00 包）」定义；外部 SKILL 包只登记 `script_contract.AUDIT`，不产生 manifest。
- **DES-S01-23**（REQ-S01-23）manifest 产出方唯一定义在 `script_manifest_schema.PRODUCERS`；`emotion_curve.json` 由 `pipeline-script-preparation` SKILL 指示模型写出，`writing_api` 不写 manifest。
- **DES-S01-20**（REQ-S01-20）文件名由 `script_contract.stage_file_name` 生成；同内容不同稿在模型名后加 `(N)`；按 Provider/模型/日期批次分类目录。
- **DES-S01-21**（REQ-S01-21）采用记录 `01剧本准备/natural_script_selection.json`，绑定相对路径 + SHA256。
- **DES-S01-22**（REQ-S01-22）`stage_completion_service` → `skill_orchestrator.verified_stage_output` → `script_contract.resolve_script_source(root) is not None`。
- **DES-S01-30**（REQ-S01-30/31）API 与桌面共用 `capture_request` / `freeze_skills` 快照；正式交付条款仅桌面启用；`call_mode=Desktop` 回执为 `prepared`，后台与 CLI 拒绝此模式。

### 测试锚定（待补 docstring）

| 需求 | 测试 |
| --- | --- |
| REQ-S01-01/04 | `test_idea_chat*`、`test_idea_attachments`、`test_idea_attachment_*` |
| REQ-S01-02 | `test_idea_*_brief` |
| REQ-S01-03 | `test_script_contract_production_locks` |
| REQ-S01-10~14 | `test_preparation_confirmation`、`test_writing_restart*`、`test_workflow_writing_stages` |
| REQ-S01-20/21 | `test_writing_api`、`test_writing_response_preservation` |
| REQ-S01-22 | `test_stage_completion_service`、`test_script_contract` |
| REQ-S01-30/31 | `test_writing_api_output_budget`、`test_claude_writing_session` |
| REQ-S01-15 | `test_script_preparation_roles` |
| REQ-S01-23 | `test_script_preparation_manifest_scope` |

## S02 剧本结构

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_script_pages`（`ScriptPagesMixin`） | 剧本结构页；只注入回调 |
| L3 | `stage_exec._run_script_structure` | 六步动作的执行回调 |
| L3 | `skill_orchestrator` | 模板编排；`verified_stage_output` 核验完成 |
| L3 | `stage_flow` / `stage_parallel` | 依赖 `DEPENDS`；串行、重试 2 次后阻塞 |
| L2 | `script_workspace_service` | 结构页文档与签名、自然稿采用 |
| L0/契约 | `script_contract` | 结构整理、校验、重提取、原子发布、路径与识别 |
| L0/契约 | `script_manifest_schema` | manifest 产出方 `PRODUCERS`、SKILL 并入表 `MERGED` |

### 设计条目

- **DES-S02-01**（REQ-S02-01）`stage_exec` 的 `read_script_raw` 调 `script_contract.resolve_script_source`；返回 None 即抛错，后续动作不执行。
- **DES-S02-02**（REQ-S02-02）`STAGE_LOCK_REQUIREMENTS` 不含 `script_structure`；`pipeline-script-structure` 直接读 S01 的项目锁。
- **DES-S02-03**（REQ-S02-03）`stage_flow.DEPENDS['script_structure']=('script',)`；并行配置在 `stage_parallel.CONFIG`。
- **DES-S02-10**（REQ-S02-10/11）`stage_exec.run` 用阶段模板 `script_structure` 驱动六个动作；提取由 `structure_script` 完成，写入 `_RULE_NOTE`（本地规则提取）。
- **DES-S02-12**（REQ-S02-12/13）`structure_script` 逐字段从原稿取首句，取不到写“待确认”。
- **DES-S02-14**（REQ-S02-14）`review_structured_script` 返回 `{approved, feedback}`；`revise_structured_script` 遇“互相矛盾的尺寸”反馈直接抛 ValueError，不改写。
- **DES-S02-15**（REQ-S02-15）`workflow_settings` 的 `script_structure` 阶段输出契约禁止镜头／分镜内容；本地规则路径不生成这些内容。
- **DES-S02-20**（REQ-S02-20）写入必经 `write_structured_script`，由 `tests/architecture/test_structured_script_write_boundary` 守边界；血缘记录在 `artifact_lineage`。
- **DES-S02-21**（REQ-S02-21）`is_structured_script` 读前 4096 字符判定；`_structured_source_is_available` 按血缘判断原稿是否仍在。
- **DES-S02-22**（REQ-S02-22）`stage_completion_service` → `skill_orchestrator.verified_stage_output` → `structured_script_path` 指向的文件满足 `is_structured_script`；步骤做完但无可读结构稿时标 FAILED。
- **DES-S02-24**（REQ-S02-24）新稿位置 `canonical_structured_script_path`（`write_dir(project,'structure')/结构剧本/`）；旧目录由 `read_dirs` 只读发现，同内容按 SHA256 去重。
- **DES-S02-30**（REQ-S02-30/31）SKILL 位于 `skills/02 剧本整理SKILL/`；`script_manifest_schema.MERGED` 记录台词润色并回正稿、世界观落 `docs/world_bible.md`。
- **待定**（REQ-S02-23/25）manifest 的写入点与核验点、落盘目录待用户拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S02-01/12/13/14/20/21 | `test_script_structure` |
| REQ-S02-03 | `test_stage_flow`、`test_stage_parallel` |
| REQ-S02-10/11/22 | `test_script_structure`（六步执行与写入）、`test_stage_completion_service` |
| REQ-S02-24 | `test_script_structure`、`test_script_workspace_service` |
| REQ-S02-02/15/30/31 | `test_script_structure_scope` |
| REQ-S02-23（归属部分） | `test_script_structure_scope` |

## S03 初步分镜

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_storyboard_page`、`storyboard_files` | 初步分镜页：剧本／分镜文件表、采用按钮；只注入回调 |
| L3 | `stage_handler_registry._start_storyboard` | 统一启动：取待办计划、无输入失败、全部完成时不启动 |
| L3 | `stage_parallel` | `CONFIG['storyboard']`、阶段并行提示、`_adopted`、SG-A（`animatic_input_ready`） |
| L3 | `stage_completion_service` | 完成核验：存在已采用且含镜头的分镜 |
| L3 | `storyboard_selection` | 采用／取消／聚焦／无人值守采用／失效采用清理 |
| L2 | `storyboard_plan_service` | 待办与待修订集合（纯文件决策，不导入 Tk） |
| L2 | `storyboard_catalog_service` | 分镜／剧本目录扫描、来源剧本解析、种子分镜识别 |
| L0/契约 | `storyboard_contract` | 分镜 JSON 交付规则文本（注入 Agent 任务） |
| L0/契约 | `storyboard_adoption_contract` | 只读的已采用清单（`ui_settings.json`） |
| L0/契约 | `storyboard_paths`、`stage_layout` | 媒体根、新旧目录等价、阶段目录 |
| L0/契约 | `episode_contract.validate_episode`（经 `writing` 转出） | 分镜 JSON 本地校验 |

### 设计条目

- **DES-S03-01**（REQ-S03-01/04）`storyboard_work_plan(project)` 取 `selected_many(root,'script')` 与 `selected_many(root,'storyboard')`，交给 `build_work_plan(scripts,boards,made,adopted)`：`todo=scripts−made`，`revise=boards−used`。`made` 来自 `stage_execution_service.storyboard_produced_scripts`。`_start_storyboard` 读取失败（OSError/ValueError/KeyError/TypeError）或 `scripts` 为空走 `_fail`；`todo` 与 `revise` 皆空，自动触发（且三虎 `auto.active=='storyboard'`）播报，否则返回空串；否则调 `desktop.open_storyboard_skill(None)`。
- **DES-S03-02**（REQ-S03-02/03）`stage_flow.DEPENDS['storyboard']`；`start()` 先过 `_workflow_lock_error`，因 `STAGE_LOCK_REQUIREMENTS` 无 `storyboard` 返回空串即放行。
- **DES-S03-05**（REQ-S03-05/06）`stage_parallel.CONFIG['storyboard']={unit:SCENE,min:2,max:3,serial:True,limit:3,retry:{attempts:2,backoff:'fixed',on_exhaust:ON_BLOCK}}`；`brief` 对 `storyboard` 追加三条提示（三元组核对、拼接与衔接、同集只出一份）。
- **DES-S03-10**（REQ-S03-10…17）这些约束全部以文本形式由 `storyboard_contract.rules()` 注入 Agent 任务；硬性字段校验由 `episode_contract.validate_episode` 执行，二者是同一契约的"提示"与"裁判"，不得一边改另一边不改。
- **DES-S03-18**（REQ-S03-18）交付规则要求 Agent 在写完后调用 `from writing import validate_episode; from storyboard_paths import media_root; validate_episode(obj, media_root(path))`；采用时由程序再校验一遍，不信任 Agent 自报。
- **DES-S03-30**（REQ-S03-30/31）`storyboard_selection.adopt(project,values)`：`paths()` 解析并要求在项目内且存在 → 与已采用合并 → 对合并后的每份先 `source_script_error` 再 `validate_episode` → `_sync_plan(...,_adopting=True)` → 写 `ui_settings.json` 的 `adopted_storyboards`（项目相对 posix 路径）与 `frame_json`（最后新增的一份）。校验或同步任一抛错，偏好不写。`storyboard_adoption_contract.adopted` 在无 `adopted_storyboards` 时回退 `frame_json`，并经 `storyboard_storage.resolved_alias` 处理迁移别名。
- **DES-S03-32**（REQ-S03-32）`adopt_pending(project,minimum_age=10)`：用 `catalog(...,'storyboard')` 取未采用项，按 `order` 排序；`mtime` 不足 `minimum_age` 记 waiting；`_validate` 失败记 failed；其余一次性 `adopt`，成功后 `sync_working_episode` 把 `config.json` 的 `episode_dir/episode_file` 指向最新采用分镜（项目已有视频任务时不动）。`repair_working_episode` 修补强关造成的指针漂移。
- **DES-S03-33**（REQ-S03-33/34）`remove` 重算剩余清单、必要时改 `frame_json`、`_sync_plan`；`focus` 要求已采用；`prune_invalid_adoptions` 只取消采用不删文件。
- **DES-S03-35**（REQ-S03-35）`storyboard_catalog_service._is_initial_storyboard` 按键集合与种子镜头逐字比对，兼容改名后的旧种子。
- **DES-S03-40**（REQ-S03-40）`working_dir=storyboard(root)/'分镜拆分'`，`document_dir=storyboard(root)/'分镜文档'`；`storyboard_paths.media_root` 对 `分镜拆分`／`分镜文档` 取同一父目录；`discover_files` 用 `os.walk(followlinks=False)`，剔除链接、junction、空文件、`IGNORED` 目录。旧目录 `storyboard/分镜拆分` 在 `stage_path_service._LEGACY` 登记为只读。
- **DES-S03-41**（REQ-S03-41/42）`stage_completion_service`：`stage=='storyboard'` → `any(shots for _s,shots in stage_parallel._adopted(root))`。`_adopted` 对读不出的文件跳过。SG-A `animatic_input_ready` 要求 `_adopted` 非空，且每份 `animatic_service.shots_of` 不抛 ValueError/TypeError/KeyError。
- **DES-S03-50**（REQ-S03-50）6 个 SKILL 位于 `skills/03初步分镜SKILL/`，frontmatter `stage: 初步分镜`；`BUILTIN_WORKFLOW_PRESETS['AIGC全流程'].stage_skills['storyboard']=['pipeline-storyboard-draft']`。
- **待定**（REQ-S03-19/20/43/44/51）命名、`batch_id` 归属、`storyboard_draft.json` 声明、`scene_breakdown.json` 核验与默认技能入口待用户拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S03-01/04 | `test_storyboard_plan_service`（待办／待修订集合）、`test_stage_command_contract`（启动分支）、`test_storyboard_page_controller` |
| REQ-S03-02/50 | `test_storyboard_scope` |
| REQ-S03-05/06 | `test_stage_parallel`（`test_storyboard_scope` 锚定配置值） |
| REQ-S03-10…18 | `test_storyboard_scope`（契约文本关键约束）；字段校验另见 `test_core`、`test_media`（`validate_episode` 用例） |
| REQ-S03-30/31/32/33/34 | `test_storyboard_adoption_service`、`test_storyboard_current_source`、`test_storyboard_source_service` |
| REQ-S03-35/40 | `test_storyboard_catalog_snapshot`、`test_storyboard_rows_service`、`test_stage_path_service` |
| REQ-S03-41/42 | `test_stage_completion_service`、`test_stage_parallel`；`test_storyboard_scope` 锚定 SG-A 登记 |
| REQ-S03-44（归属部分） | `test_storyboard_scope`、`test_script_contract` |

## S04 分镜预演

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_media_pages.animatic_page` | 预演页：选分镜／音频、导入参考图、本地生成参考草图、生成、观看、三项确认；只注入回调 |
| L3 | `stage_handler_registry.start`（`animatic` 分支） | 手动启动只切页并提示，不出图 |
| L3 | `stage_execution_service` | `run_animatic`、`confirm_animatic`、`animatic_video`、`import_animatic_references`、`import_animatic_audio`、`generate_animatic_reference`、`publish_animatic_bundle`、`animatic_preview_spec` |
| L3 | `stage_parallel` | `CONFIG['animatic']`、SG-A `animatic_input_ready`、SG-B `animatic_ready` |
| L3 | `stage_completion_service` | `stage=='animatic'` → `animatic_service.evidence` |
| L2 | `animatic_service` | 分镜取值、草图、整包构建与校验、完成核验；不直接写正式成果，发布由注入的 L3 发布器执行 |
| L2 | `edit_service.assemble_image_timeline` | 图片时间线合成与媒体核验（暂存区内） |
| L2 | `audio_import_service.import_audio(stage='animatic')`、`tts_api` | 临时音频导入与临时 TTS |
| L2 | `comfy_service` | 本地 ComfyUI 参考图图谱、提交回执与结果收集 |
| L0/契约 | `artifact_schema`（`animatic_manifest`）、`stage_layout`、`stage_path_service`、`project_stages` | 清单必备字段、阶段目录、共享参考图目录 |

### 设计条目

- **DES-S04-01**（REQ-S04-01/03）`stage_flow.DEPENDS` 登记前后依赖；`start('animatic')` 先过 `_workflow_lock_error`（本阶段无锁要求，放行），再 `desktop.show(STAGES.index('animatic'))` 并返回 `_fail(...)` 提示文本，不调用任何生成函数。
- **DES-S04-02**（REQ-S04-02/05）`run_animatic` 先 `stage_parallel.evaluate(project,'animatic')`（SG-A），再要求 `Path(source).resolve()` 属于 `storyboard_selection.adopted(project)`；`build_bundle` 再要求来源在项目根内、参考图非空、`shots_of` 通过。`shots_of` 的校验规则：ID 匹配 `[A-Za-z0-9_-]+` 且唯一，提示词取 `image_prompt/prompt/video_prompt/description` 第一个非空，时长取 `estimated_duration/duration` 且 0<x≤600。
- **DES-S04-03**（REQ-S04-04/06）`animatic_preview_spec` = `script_contract.preview_spec(stage_config.workflow_lock(project))`；`run_animatic` 对 `ffmpeg/ffprobe` 依次取 settings、`config.json`、`platform_tools.tool_path`，缺失抛错；随后 `comfy_runtime.wait_comfy`。
- **DES-S04-04**（REQ-S04-10/11）`import_animatic_references` 校验后缀与大小，以内容 SHA-256 命名，经 `publish_stage_bundle` 发布；`animatic_reference_paths` 遍历 `shared_reference_read_dirs`（新旧目录）并去重。`prepare_reference` 复用 `Comfy.submit` 与 `_collect_sketch`，再交 `import_animatic_references`。
- **DES-S04-05**（REQ-S04-20/21/22/23）`local_sketch` 用 `reference_graph` 构图并把图中所有 `seed/noise_seed` 设为固定种子；`build_bundle` 按 `batch` 分组，`run_batches` 由 L3 注入 `stage_parallel.parallel_map('animatic', ...)`（批间并行、批内串行）；只捕获 `ComfyGenerationFailed` 重试，`retry_attempts` 来自 `stage_parallel.retry_attempts('animatic')`；`_collect_sketch` 在超时内轮询 `collect`，超时抛"不自动重复提交"。持久工作区 `04分镜预演/.work/run-*`。
- **DES-S04-06**（REQ-S04-24）`tts_api.script_signature(text, settings)` 参与临时音频文件名；文件已存在且非空则复用；持久工作区下用 `request_id='tts-previs:'+signature` 让重复请求幂等。
- **DES-S04-07**（REQ-S04-25）`assemble_image_timeline`：逐镜 `-loop 1 -t 秒` 生成片段 → concat 清单 → 叠加音频（`apad`、`-t` 总时长）→ `ffprobe` 核验含 video/audio 流且时长差 ≤1 秒 → `-xerror` 全量解码；每镜时长必须有限且 0<x≤600。
- **DES-S04-08**（REQ-S04-30/31/32）`build_bundle` 在读取来源时用 `file_cache.read_stable_json_snapshot`，组装 artifacts 与清单（含 `source_sha256`、`files` 摘要、`confirmed` 三项 `False`）；发布前再次比对来源字节。`validate_bundle` 做整包一致性校验；`publish_animatic_bundle` 做路径越界与索引保留名检查，生成 `animatic_index.json`，通过 `publish_stage_bundle` 原子发布并在失败时回滚（含索引）。
- **DES-S04-09**（REQ-S04-40）`confirm_animatic`：三参数必须全为 `True` → `evidence(require_confirmation=False)` 通过 → `deepcopy` 清单写 `confirmed` → `publish_stage_text` 校验后发布。重新生成走 `build_bundle`，清单重新以 `False` 开始。
- **DES-S04-10**（REQ-S04-41/42/43）`evidence(project, require_confirmation=True)`：读清单 → 来源摘要 → `files` 逐项路径在阶段目录内、非空、`file_cache.file_digest` 一致 → 镜头图均登记 → 三项确认。任一环节异常统一返回 `(False, '分镜预演未就绪、源文件已变化，或节奏／时长／对白同步尚未确认')`。SG-B 与 `stage_completion_service` 共用该函数，无第二套判定。
- **DES-S04-11**（REQ-S04-50/51/52）`skills/04 分镜预演SKILL/pipeline-animatic.skill.md`，`tools: [animatic.generate, animatic.validate]` 在 `skill_tools.PAGES` 登记为打开预演页（`status_of=='page'`）。
- **待定**（REQ-S04-52/60/61/62）SKILL 锁段落收窄、`storyboard_draft.json` 与 `animatic_notes.md` 声明、`batch_id` 归属、成果下游消费，待最终验收拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S04-01/04/50/51 | `test_animatic_scope` |
| REQ-S04-02/05 | `test_animatic_service`（`shots_of`、来源约束）、`test_animatic_scope`（SG-A 登记） |
| REQ-S04-03 | `test_animatic_scope`（手动启动只切页） |
| REQ-S04-10/11 | `test_media_import_validation`、`test_animatic_service` |
| REQ-S04-20…25 | `test_animatic_service`（重试与不重投、TTS 复用）、`test_animatic_timeline` |
| REQ-S04-30/31/32/33 | `test_animatic_service`（整包发布、越界、回滚） |
| REQ-S04-40/41/42/43 | `test_animatic_service`（确认、流式核验、缺失媒体）、`test_stage_parallel`、`test_animatic_scope`（SG-B 登记） |
| REQ-S04-26 | `test_animatic_service`（正式资产须线上 API） |

## S05 资产管理

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_asset_pages`、`asset_detail`、`asset_reference_images`、`cloud_assets` | 资产页、详情页、参考图窗、云端后端；只注入回调 |
| L3 | `stage_execution_service` | `require_formal_asset_generation`（SG-B + 线上模型）、`plan_unattended_assets`、`import_pending_generated_assets`、资产写入网关 |
| L3 | `stage_flow` / `stage_parallel` | `DEPENDS`、`PAID_STAGES`、`CONFIG['assets']`、`GATES`、`assets_locked`（SG-01） |
| L3 | `stage_completion_service` | `assets` 完成 = `assets_locked` 的 `ok and started` |
| L2 | `asset_plan` | 从已采用分镜同步清单；原子发布四件套；`asset_impact`／`deletion_references` |
| L2 | `asset_context` | 资产库定位 `library_dir`、来源 `active_source`、`generated_dir` |
| L2 | `asset_batch_service`、`asset_generated_import_service`、`asset_*_service` | 图片登记（登记表）、批量生成、导入、恢复、重命名 |
| L2 | `prop_assets` | 道具是否需要独立资产 |
| L0/契约 | `asset_contract` | 编号前缀、正典板视角、默认值、`normalize`、`validate`、`missing_ids`、`schema` |
| L0/契约 | `production_model_contract` | 资产批量后端名 |
| L0/契约 | `stage_layout`／`stage_path_service` | `05资产管理` 目录；`04资产管理` 与 `episode/assets/资产清单` 只读 |

### 设计条目

- **DES-S05-01**（REQ-S05-01）`asset_plan._sync_plan` 取 `active_source`；非采用流程用 `storyboard_adoption_contract.adopted` 过滤来源；无采用分镜时 `active_source` 抛“请先…手动采用分镜”。
- **DES-S05-02**（REQ-S05-02）`stage_flow.DEPENDS['assets']=('animatic',)`；`GATES` 的 SG-B 检查 `animatic_ready`；`require_formal_asset_generation` 调 `stage_parallel.evaluate(project,'assets')` 并要求线上模型。
- **DES-S05-03**（REQ-S05-03）`asset_contract.resolve_aspect_ratio`：项目锁 > 已存偏好 > `16:9`；本阶段不在 `STAGE_LOCK_REQUIREMENTS` 登记。
- **DES-S05-04**（REQ-S05-04）`stage_path_service.shared_reference_dir`／`shared_reference_read_dirs`；本地草图经 `generate_animatic_reference` 发布，不进登记表。
- **DES-S05-10**（REQ-S05-10/11/12）`_sync_plan` 先预留显式编号再按别名映射／分配新号；`asset_contract.normalize` 只补缺的键；`prop_assets.requires_asset` 过滤道具。
- **DES-S05-13**（REQ-S05-13/14）`asset_contract.VIEWS`（`TURNAROUND`+`HEADS`）、`defaults`、`validate`；`schema()` 输出 JSON Schema。
- **DES-S05-15**（REQ-S05-15）`asset_contract.missing_ids` 逐镜取 `character_ids`／`characters`／`scene_id`／`location`／`costume_id`。
- **DES-S05-16**（REQ-S05-16）`_publish_plan_bundle` 记录发布前字节，失败逐项还原或删除；写后复核四份文件。
- **DES-S05-17**（REQ-S05-17）`_sync_plan` 对每项 `entry.pop('image')`，再按登记表回填，路径须在资产库内且文件存在才标“已导入”。
- **DES-S05-20**（REQ-S05-20）`stage_parallel.CONFIG['assets']`：`unit=ASSET`、`min3/max5/limit5`、`serial=True`、重试 2 次固定间隔、耗尽 `ON_BLOCK`；`why` 写明单资产内部顺序。
- **DES-S05-21**（REQ-S05-21/22）`stage_flow.PAID_STAGES`；`pipeline-assets` 声明“默认只出提示词”；后端名来自 `production_model_contract`。
- **DES-S05-23**（REQ-S05-23）`write_dir(project,'assets')` → `05资产管理`；`read_dirs` 追加 `LEGACY_NUMBERED['assets']='04资产管理'` 与 `_LEGACY['assets']`（`episode/assets/资产清单`，2027-03-31 后停读）；`library_dir` 在新目录已有清单时优先新目录。
- **DES-S05-30**（REQ-S05-30/31）`stage_parallel.assets_locked` 读 `library_dir/assets/资产清单/assets.json`；`missing`／`unlocked`／`noanchor` 三类问题；`touched`（有图／有锁／有锚点）或 `has_run` 才算 `started`；`stage_completion_service` 对 `assets` 要求 `ok and started`。
- **DES-S05-32**（REQ-S05-32 ❓）待定：门禁读清单文件的 `image`，而图片只写登记表 `<资产库>/assets.json`（`asset_batch_service.register_image`／`import_asset_image`／恢复）。拍板后二选一：门禁改读登记表（与 `image_ready` 一致），或在登记时同步写清单；同步写会违背 `_sync_plan` 对 `image` 的剔除口径，需一并改。
- **DES-S05-33**（REQ-S05-33）删除经 `storage_maintenance.recycle_paths`；`asset_plan.deletion_references` 列引用镜头；恢复经 `restore_latest_recycled_child`。
- **DES-S05-40**（REQ-S05-40/41）SKILL 位于 `skills/05资产管理SKILL/`；`pipeline-assets` 的 `dependsOn: [pipeline-animatic]`、`parallelizable: false`、`paid: false`。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S05-02/10/13/14/20/21/23/30/31/40 | `test_assets_scope` |
| REQ-S05-01/11/16/17 | `test_asset_plan`、`test_assets` |
| REQ-S05-13/14/15 | `test_asset_contract` |
| REQ-S05-20 | `test_stage_parallel`、`test_asset_skill_batch`、`test_asset_batch_controller` |
| REQ-S05-30/31 | `test_asset_gating`、`test_stage_gate_e2e_probe`、`test_stage_completion_service` |
| REQ-S05-33 | `test_asset_impact`、`test_asset_restore`、`test_asset_image_restore_service` |
| REQ-S05-23 | `test_asset_context`、`test_asset_resume` |
| REQ-S05-32（待定） | 暂无；拍板后补回归 |

## S06 连贯性清单

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_media_pages`（`MediaPagesMixin`） | 连贯性清单页：现场算台账、“手动生成连贯性清单”落盘、问题闭环表与忽略入口 |
| L4 | `desktop_automation_tick` | 半自动／全自动档下按推荐处理 G-05／G-06／G-08 候选 |
| L3 | `stage_execution_service` | 问题登记的 L3 门面：`continuity_issue_report`／`sync_continuity_issues`／`decide_continuity_issue`，注入发布器 |
| L3 | `stage_parallel` | `CONFIG['continuity']`、门禁 SG-01 `assets_locked`／SG-02 `ledger_ready` |
| L3 | `stage_completion_service` | 完成核验：`'continuity': 'ledger_ready'` 且 `ok and started` |
| L3 | `stage_flow` | 依赖 `DEPENDS`、手动按钮名、恢复提示 |
| L3 | `confirm_gates` | 主观门禁 G-08（冲突裁决）候选与确认账本 |
| L2 | `continuity_ledger` | 台账计算、发布包、问题闭环（纯规则，无模型调用） |
| L2 | `skill_tools` | `continuity.*` 工具登记；`_continuity_ledger` 本地落盘 |
| L0/契约 | `stage_layout`／`stage_path_service` | `06连贯性清单` 目录、`_shared` 共享索引路径、旧 `05连贯性清单` 只读 |
| L0/契约 | `shot_batches`／`artifact_schema` | 批次与三元组归并；`continuity_ledger`／`continuity_issues` 的 schema |

### 设计条目

- **DES-S06-01**（REQ-S06-01）页面 `continuity_ledger_data` 读 `current_frame_json()` 的 `shots` 与 `asset_requirements()`，两者失败各自降为空后调用 `build`。
- **DES-S06-02**（REQ-S06-02）`stage_flow.DEPENDS['continuity']=('assets',)`；`stage_parallel.GATES` 的 SG-01（assets→continuity）、SG-02（continuity→final）；`CONFIG['continuity']` 单 Agent、重试 2 次、`ON_BLOCK`。
- **DES-S06-03**（REQ-S06-03）`script_contract.STAGE_LOCK_REQUIREMENTS` 不登记 continuity，`stage_handler_registry` 不对本阶段做制作锁检查。
- **DES-S06-10**（REQ-S06-10/11）`build` 依次调用 `batches`、`anchors_of`、`conflicts`＋`adjudicate`、`cross_batch`、`triplets`、`drift`，再由 `resolve_problems` 汇总 `summary`。
- **DES-S06-12**（REQ-S06-12）`anchors_of` 对角色用 `merged_anchor`（含服装状态覆盖），场景拼“光源／空间锚点／尺度”，道具拼“材质／尺度”；缺字段不补。
- **DES-S06-13**（REQ-S06-13）`conflicts` 用 `IDENTITY_WORDS`／`SCENE_WORDS`／`MOTION_WORDS` 词表判定；`adjudicate` 取 refs 第一个为身份负责人；`ask` 为多图抢同一件事生成 2 个候选（G-08）。
- **DES-S06-14**（REQ-S06-14/15）`triplets`／`cross_batch` 只比字符串；`continuity_flags` 去重后以 `kind='flag'` 记入。
- **DES-S06-16**（REQ-S06-16）`drift` 仅遍历 `kind=='character'` 的冻结锚点，与 `merged_anchor` 现值比较；`confirm_gates.check_drift` 在有资产时重新比较。
- **DES-S06-20**（REQ-S06-20）`publish_bundle` 先备份四个目标的旧字节，逐个写入，读回比对，失败 `restore_bytes`；`write` 只是兼容入口。边界由 `tests/architecture/test_continuity_publication_boundary` 守。
- **DES-S06-21**（REQ-S06-21/22）`issues` 把台账未通过项转成结构化问题；`merge_issues` 为纯函数，`sync_issues`／`decide_issue` 仅在 L3 注入 `publish` 时落盘；`SEVERITIES`／`ISSUE_KINDS` 为权威表。
- **DES-S06-23**（REQ-S06-23）`ledger_ready` 读台账；无台账返回 `ok=True, started=False`；有未通过项时用 `issue_gate` 判断是否全部为已忽略／已解除，且必须算得出问题行才放行；完成核验取 `ok and started`。
- **DES-S06-30**（REQ-S06-30/31）SKILL 位于 `skills/06连贯性SKILL/`，`skill_registry` 以 `06` 目录归入 continuity；`workflow_settings` 预设默认 `pipeline-continuity`；`skill_tools` 登记 `continuity.buildLedger` 等。
- **待定**（REQ-S06-24/26/32/33）台账版本核对、G-08 是否为放行条件、SKILL 与实现的一致方向、自动生成入口，待用户拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S06-02/03/11/20/22/23/30 | `test_continuity_scope` |
| REQ-S06-12/13/14/15/16 | `test_continuity_ledger` |
| REQ-S06-20（失败回滚） | `test_continuity_ledger`、`tests/architecture/test_continuity_publication_boundary` |
| REQ-S06-21 | `test_continuity_issues` |
| REQ-S06-02（门禁与依赖） | `test_stage_parallel`、`test_stage_flow` |
| REQ-S06-23（完成核验） | `test_stage_completion_service`、`test_continuity_scope` |
| REQ-S06-24/26/32/33 | 待定 |

## S07 分镜定稿

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L5/L4 | `desktop`（`make_final_storyboard`／`apply_final`） | 手动“手动同步资产”入口、定稿后收尾；只注入回调 |
| L4 | `desktop_auto_flows`（`poll_auto_final`） | 无人值守自动定稿轮询；签名去重、等待、退避 |
| L4 | `storyboard_files.show_final` | 定稿页（预览／编辑／镜头导航），状态由控制器持有 |
| L3 | `storyboard_final_controller` | `finalize_stage_storyboard`、`retire_stage_storyboard`、`FinalStoryboardController`（无 Tk） |
| L3 | `stage_execution_service` | `storyboard_resolve_source`、`storyboard_working_source`、`retire_storyboard`、`publish_final_storyboard_bundle`、`save_edited_stage_storyboard`、`asset_plan_gateway` |
| L3 | `stage_parallel` | `CONFIG['final']`、门禁 SG-02／SG-03、`ledger_ready`／`batches_ready`、`_adopted` |
| L3 | `stage_flow`／`stage_completion_service` | 依赖表 `DEPENDS`、手动按钮名；完成证据核验 |
| L3 | `workflow_settings` | 默认 SKILL `pipeline-storyboard-final` |
| L2 | `storyboard_final` | `finalize`：资产对齐、切批、复用判定、原子发布、血缘；退役由注入函数完成 |
| L2 | `shot_batches` | 批次算法、九字段 `normalize/validate`、`advise`、`check_batches`、Schema |
| L2 | `final_service` | `automatic_finalize_decision`（skip／wait／dispatch） |
| L2 | `storyboard_lifecycle`／`storyboard_selection`／`storyboard_paths` | 工作稿判定与退役、已采用／当前定稿视图、定稿目录识别 |
| L0/契约 | `pet_bus`、`stage_layout`、`stage_path_service` | 阶段键与名称；`07分镜定稿` 目录；`write_dir`／`read_dirs`（含旧 `06分镜定稿` 只读） |

### 设计条目

- **DES-S07-01**（REQ-S07-01）`finalize` 先 `storyboard_resolve_source` 取源，再要求顶层 dict 且 `shots` 为 list，否则 `ValueError`，此时尚未创建任何目录。
- **DES-S07-02**（REQ-S07-02/03/04）SG-02 在 `stage_parallel.GATES`，检查函数 `ledger_ready` 读台账并用 `continuity_ledger.gate`／`issue_gate`；`CONFIG['final']` 为单任务、重试 2 次后 `ON_BLOCK`。`DEPENDS['final']` 在 `stage_flow`，与门禁各自独立。
- **DES-S07-03**（REQ-S07-05）手动：`make_final_storyboard` 判断 `self.worker`／视频会话忙；自动：`automatic_finalize_decision(signature, previous, production_busy)`，签名相同 skip、忙则 wait、否则 dispatch。
- **DES-S07-10**（REQ-S07-10/11/12）`_sync_plan` 先刷新资产清单与“名称编号对照”；逐镜按 `CHAR/LOC/PROP` 前缀解析编号，未入库抛错；`prop_assets.normalize_shot` 先补道具字段；状态不是“已导入”的资产记入 `missing`。
- **DES-S07-13**（REQ-S07-13/14）`shot_batches.assign` = `group`（三元组变化／满 4 镜／超 18 秒切批）+ 回填 `B%02d`；`check_batches` 为硬校验，`advise` 为软提示；`finalize` 在 `try` 里调用 `assign`，异常经 `app_logging.swallowed` 记录。
- **DES-S07-16**（REQ-S07-16/17）`storyboard_lifecycle.signature(episode, assets, base)` 为内容指纹（忽略 `used_in/status`，含图片哈希）；在 `final/分镜` 与 `分镜拆分` 两个读目录里按签名找已有定稿；找不到则 `dated_path(.../分镜, <EP>_分镜定稿)`，或经别名文件复用同 `episode_id` 的上一次目录。
- **DES-S07-18**（REQ-S07-18/19）发布前比对源哈希，不一致抛“分镜在同步期间已修改”；`publish_stage_text` 写 `episode.json`，其回调再调 `publish_final_storyboard_bundle` 成对写 `assets.json`；资产图 `copy2`，冲突时加 12 位哈希并记入 `image_rewrites` 回改引用。
- **DES-S07-20**（REQ-S07-20）`retire_working` 参数由 L3 的 `retire_stage_storyboard` 提供，别名发布器 `storyboard_lifecycle_gateway()` 同样由 L3 注入；`retire` 校验目标已落盘、源未被改、更新别名后调用 `storage_maintenance.recycle_paths`（回收站），失败则保留原稿。由 `tests/architecture/test_final_bundle_boundary` 守“桌面只经控制器调用”。
- **DES-S07-21**（REQ-S07-21）`_lineage_source` 取源 JSON 的 `source_script`（项目内且存在），否则回退源；源是定稿目录的 `episode.json` 时返回 None 不记。
- **DES-S07-30**（REQ-S07-30/31）按钮名在 `stage_flow.MANUAL_LABELS`；自动入口在 `poll_auto_final`，用 `file_hash(source)` 做签名，守卫 `pet.should_auto_run('final')`。
- **DES-S07-32**（REQ-S07-32）`FinalStoryboardController.save_edited` 先 `json.loads`，再 `save_edited_stage_storyboard`，失败抛 `ValueError` 且不替换当前预览。
- **DES-S07-33**（REQ-S07-33/40）`stage_path_service.write_dir(project,'final')` → `stage_layout` 的 `07分镜定稿`；`read_dirs` 追加 `LEGACY_NUMBERED['final']`（`06分镜定稿`）；`is_final_dir` 判定目录名。
- **DES-S07-41**（REQ-S07-41/42）`stage_completion_service` 的 `checks['final']='batches_ready'`，要求 `ok and started`；`batches_ready` 以 `_adopted` 的已采用分镜为对象，`started = has_run(final) or 任一镜头带 batch_id`。
- **DES-S07-50**（REQ-S07-50/51）SKILL 位于 `skills/07分镜定稿SKILL/`；默认勾选来自 `workflow_settings` 的 `'final':['pipeline-storyboard-final']`；D 锁段缝字段写在总入口 SKILL 正文，不由程序核验。
- **待定**（REQ-S07-03/15/43/44/45/52/53）见需求中标 🟡／❓ 的条目；其中 REQ-S07-52 需用户拍板（是否程序化核验台账与段缝），其余为单向修订，待统一后处理。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S07-13/14 | `test_shot_batches` |
| REQ-S07-05（自动决策） | `test_final_service` |
| REQ-S07-20/32 | `test_storyboard_final_controller`、`tests/architecture/test_final_bundle_boundary` |
| REQ-S07-33（选择视图） | `test_storyboard_final_selection`、`tests/architecture/test_storyboard_final_selection_boundary` |
| REQ-S07-41 | `test_stage_completion_service` |
| REQ-S07-02/04（门禁清单、并行配置） | `test_stage_parallel`、`test_storyboard_final_scope` |
| REQ-S07-42（`batches_ready` 行为） | `test_storyboard_final_scope`（`test_stage_parallel` 未直接测此函数） |
| REQ-S07-01/04/13/33/41/42/50/51 的事实范围 | `test_storyboard_final_scope` |
| REQ-S07-10/11/12/16/17/18/19/21 | 暂无直接 `finalize` 端到端测试（相邻覆盖：`test_asset_plan`）——测试缺口，待补 |
