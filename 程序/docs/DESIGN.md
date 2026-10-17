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

## S08 首帧管理

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_storyboard_page.StoryboardPageMixin` | 首帧管理页（方法名 `storyboard` 为历史沿用）；只注入回调 |
| L4 | `desktop_media_pages`、`desktop_auto_flows` | 首帧删除／恢复、自动补帧入口与播报 |
| L3 | `keyframe_comfy` | 本地 ComfyUI 批量生成、缺帧对话框、自动批次 |
| L3 | `keyframe_import` | 外部生成结果登记、导入、监听、陈旧任务清理 |
| L3 | `keyframe_page_controller` | 页面行与批次选择（不持有 Tk 控件） |
| L3 | `stage_handler_registry.start` | 启动前检查三项必填锁 |
| L2 | `keyframe_batch` | 批量计划（补缺／重试／替换）与不可生成状态 |
| L2 | `keyframe_lifecycle_service` | 删除、恢复、替换首帧（回收站 + 事务回滚） |
| L2 | `keyframe_model_service` | 首帧模型选择 |
| L2 | `keyframe_evidence` | PNG 事实、来源证据、`frame_problem` 校验 |
| L3 | `stage_parallel` | `frames_ready`（SG-04）、`batches_ready`（SG-03）、限速与并行 |
| L3 | `stage_completion_service` | 阶段完成核验，`keyframe → frames_ready` |
| L0 | `stage_layout`、`stage_path_service` | 目录 `08首帧管理`、旧 `07首帧管理` 只读兼容 |
| L0 | `script_contract` | `STAGE_LOCK_REQUIREMENTS['keyframe']` |

### 设计条目

- **DES-S08-01**（REQ-S08-01/02）`stage_flow.DEPENDS['keyframe']=('final',)`；`stage_layout` 行 `('08首帧管理','keyframe',…,输入 storyboard_final.json)`。
- **DES-S08-03**（REQ-S08-03）`script_contract.STAGE_LOCK_REQUIREMENTS['keyframe']=('aspect_ratio','video_model_version','delivery_format')`，`stage_handler_registry.start` 对非剧本阶段按它取必填锁。
- **DES-S08-04**（REQ-S08-02/04）`stage_parallel.GATES` 含 `SG-03(final→keyframe, batches_ready)`、`SG-04(keyframe→previs, frames_ready)`；`frames_ready` 在没有已采用分镜时返回放行。
- **DES-S08-10**（REQ-S08-10/11）`keyframe_evidence.image_facts` 全量解码 PNG 一次（按内容哈希缓存，不信文件名／mtime），拒绝非 PNG、空文件、>64MB、CRC 错；`_check_dimensions` 校验画幅。
- **DES-S08-12**（REQ-S08-12/13/14）`keyframe_batch` 的 `STATE_*` 状态机与 `MODE_MISSING/RETRY/REPLACE` 计划；`ATTEMPT_NOTES` 区分 sending／uncertain／completed／pending／cancelled。
- **DES-S08-15**（REQ-S08-15）首帧提示词取 `frame_prompt`，缺则 `keyframe_prompt`，不读视频提示词。
- **DES-S08-16**（REQ-S08-16/17）`keyframe_import.register` 在来源指纹不符时拒绝；关联失败保持旧来源与已发布首帧。
- **DES-S08-18**（REQ-S08-18）`keyframe_model_service.current_model` 读 `stage_config` 的 `keyframe.model`。
- **DES-S08-19**（REQ-S08-19）`stage_parallel.CONFIG` 对 `keyframe` 限速，`parallel_map(…, resource=镜头号)` 保证同镜头不并发。
- **DES-S08-20**（REQ-S08-20/21/22）`keyframe_evidence.make_evidence` 写 `frame_evidence{version:1, image, expected_size, aspect_ratio, source}`；`source_evidence` 只取该镜头引用的资产，故其他镜头不受影响；`frame_problem` 返回可执行的复核原因，空串表示通过。
- **DES-S08-23**（REQ-S08-23）`keyframe_lifecycle_service.delete/restore/replace_keyframe` 经 `storage_maintenance.recycle_paths`／`restore_latest_recycled_*`，保存分镜失败回滚；L2 要求 L3 注入发布回调。
- **DES-S08-24**（REQ-S08-24）`stage_path_service.write_dir(project,'keyframe')`；`LEGACY_NUMBERED['keyframe']='07首帧管理'` 经 `read_dirs` 只读回退。
- **DES-S08-30**（REQ-S08-30/31）`frames_ready` 读已采用分镜的 `frame`／`frame_deleted`，路径须在 `media_root` 内，非空，且 `frame_problem(…, aspect_ratio=workflow_lock(project)['aspect_ratio'])` 为空；`stage_completion_service` 的 `checks['keyframe']='frames_ready'`，要求 `ok` 且 `started`。
- **DES-S08-32**（REQ-S08-32）`engine.py`、`app.py`、`local_video.py` 缺首帧时抛错／跳过，并经 `pet_bus.stage_step('keyframe')` 指向本阶段。
- **DES-S08-50**（REQ-S08-50/51）SKILL 位于 `skills/08首帧管理SKILL/`；`skills/templates/keyframe_process_template.yaml` 四步，第 3 步 `needs_confirmation`。
- **待定**（REQ-S08-40/41）清单文件名与写入点待用户拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S08-01/02/03/04/50/51 | `test_keyframe_scope` |
| REQ-S08-10/21/22 | `test_keyframe_evidence`、`test_keyframe_scope`（PNG 拒绝） |
| REQ-S08-11/20/30 | `test_keyframe_evidence`、`test_stage_parallel`（frames_ready） |
| REQ-S08-12/13/14 | `test_keyframe_batch_plan` |
| REQ-S08-15/16/17 | `test_keyframe`（导入与提示词） |
| REQ-S08-18 | `test_keyframe_model_service` |
| REQ-S08-19 | `test_stage_parallel` |
| REQ-S08-23 | `test_keyframe_lifecycle_service` |
| REQ-S08-31 | `test_stage_parallel`（缺帧阻塞预演） |

## S09 白模预演

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `local_previs`（白模页）、`white_model`（单镜预演窗口、导入、备注）、`previs_monitor`（浏览器监视页） | 只持有 Tk／HTTP 展示；动作经 `stage_execution_service` 的注入门面进入 L3 |
| L3 | `previs_automation` | Agent 自动制作：前置检查、冻结快照、逐镜执行与校验、停止、播报 |
| L3 | `previs_routing`（`dispatch`／`partition`／`set_override`） | 分流策略；`ProjectContext` 与发布函数由调用方注入，执行器也注入 |
| L3 | `previs_batch_service` | 批任务清单与执行提示词 |
| L3 | `stage_execution_service` | `project_context`、`white_model_shot_directory`、分流记录发布、`previs_progress_gateway` 等装配 |
| L3 | `stage_parallel`（`CONFIG`／`GATES`／`previs_ready`）、`stage_flow`（`DEPENDS`）、`stage_completion_service` | 并行口径、SG-04／SG-05、阶段完成 |
| L2 | `white_model_service` | 镜头目录与项目身份、预演记录读写、证据摘要、导入、工作区与 Blender 发现、旧目录迁移 |
| L2 | `previs_progress_service` | 进度文件读取与状态映射；发布函数由 L3 注入 |
| L2 | `white_model_ref` | 白模视频作为参考视频的能力表与请求槽位拼装（供视频生成消费） |
| L0/契约 | `project_context`、`stage_layout`、`stage_path_service`、`script_contract` | 上下文契约、阶段目录声明、旧编号只读、阶段锁 |

### 设计条目

- **DES-S09-01**（REQ-S09-01/33）`stage_parallel.GATES` 的 SG-04（`frames_ready`）与 SG-05（`previs_ready`）；门禁只拦“已开始但不完整”。
- **DES-S09-02**（REQ-S09-02）`stage_flow.DEPENDS['previs']=('keyframe',)`；`DEPENDS['video']` 不含 `previs`。
- **DES-S09-03**（REQ-S09-03）`script_contract.STAGE_LOCK_REQUIREMENTS['previs']` 三项。
- **DES-S09-04**（REQ-S09-04）`stage_parallel.CONFIG['previs']`：`unit=BATCH, min=2, max=3, serial=True`，重试 2 次、`on_exhaust=ON_MANUAL`；`brief_block('previs')` 追加“同批次内禁止并行”。
- **DES-S09-10**（REQ-S09-10/11）`previs_routing.LEVELS`／`ROUTES`；`classify` 先取分镜标注，再剔除否定短语后按关键词与步数判断，兜底中等。
- **DES-S09-12**（REQ-S09-12/13）`entries` 合并 `overrides_file`（`data/白模复杂度设置.json`）；`set_override` 经注入的 `publish` 写入；`decisions_for` 是页面、调度、门禁共用入口。
- **DES-S09-14**（REQ-S09-14）`partition` 分三组；`dispatch` 先剔除已就绪镜头，简单／中等只写状态，复杂交 `start_complex`；记录经注入的 `publish` 写入 `工作流任务/白模分流记录/`。
- **DES-S09-20**（REQ-S09-20/42）`previs_automation.start`：`busy` 互斥 → 过滤已就绪 → `claude-desktop-app` 拦下 → `find_blender` → `save` 冻结 `分镜快照.json`／`调用配置.json`；任务书由 `previs_batch_service.prepare_batch` 生成并要求仅简化白模。
- **DES-S09-21**（REQ-S09-21）`worker` 逐镜：`verify`（`ffprobe` 取视频流与时长，容差 0.5 秒，通过后 `record_evidence`）→ `run_background` → 再 `verify`；结果写 `状态.json`，状态集 `ready／failed／cancelled／unknown`。
- **DES-S09-22**（REQ-S09-22）`force_stop` 置 `stop` 并 `workflow_engines.terminate(project)`；`ExecutionStopped` 记 `unknown` 并终止批次；`announce` 只写队列，播报在界面线程。
- **DES-S09-23**（REQ-S09-23）`previs_progress_service.install_blender_progress` 挂 Blender 渲染回调写帧数；`status_value` 校验帧数合法性，不合法退回“Agent 制作中”；`previs_monitor.start` 只读渲染，`REFRESH_SECONDS=5`。
- **DES-S09-24**（REQ-S09-24/25）`white_model_service.import_previs_media`（先复制到 `.importing` 临时文件、大小一致才替换，失败清理）；`save_previs_notes` 合并写入记录；视频/工程归 `preview`／`project_file` 两个键。
- **DES-S09-26**（REQ-S09-26）`white_model_ref.SUPPORT` 为唯一能力表，`descriptor` 校验存在／后缀／非空／上限，`entries` 按槽位（`media`／`content`）拼请求；`white_model.validate_video_submission` 在提交前调用。
- **DES-S09-30**（REQ-S09-30/32）`white_model_service.shot_directory`：`<workspace()>/<project_id 或项目目录名>/<集>/<镜头号>`，集取镜头号 `EPnnn_` 前缀，其次当前分镜 `episode_id`，否则“未分集”；`workspace()` 取环境变量→设置文件→默认用户数据目录；`migrate_legacy_directories` 先算完整清单再搬，失败回滚，成功才写 `project_id` 并落迁移清单。
- **DES-S09-31**（REQ-S09-31）`evidence_state` 返回 `ok／changed／unbound／missing`；`previs_routing.ready` 对 `changed` 与（有来源时的）`unbound` 返回 False；`SOURCE_FIELDS` 决定来源摘要。
- **DES-S09-33**（REQ-S09-33）`previs_ready` 取所有已采用分镜 → `decisions_for` → 只收集 `level=='complex'` → 逐镜 `ready`；缺失且 `has_run` 或已有任一就绪才拦。
- **DES-S09-34**（REQ-S09-34）`stage_completion_service` 的 `checks['previs']='previs_ready'`，通过条件 `ok and started`。
- **DES-S09-40**（REQ-S09-40/41）SKILL 位于 `skills/09白模预演SKILL/pipeline-previs.skill.md`；工作流设置的 `FLOWS['previs']`、`DEFAULT_SKILLS['previs']`、`FLOW_SKILLS['previs']` 在桌面通道登记 `create-blender-story-video`。
- **待定**（REQ-S09-35/36/37/41）产物契约名与位置、成果是否入项目目录、中等镜头是否强制、默认 SKILL，待用户拍板后再设计。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S09-10/11/12/14 | `test_previs`、`test_previs_scope` |
| REQ-S09-20/21/22 | `test_previs`、`test_previs_batch_service` |
| REQ-S09-23 | `test_previs_monitor`、`test_previs_monitor_exposure` |
| REQ-S09-24/30/32 | `test_white_model_workspace`、`test_white_model_identity`、`test_white_model_import_boundary`、`test_previs_scope` |
| REQ-S09-26 | `test_white_model_ref`、`test_previs_scope` |
| REQ-S09-31 | `test_previs`、`test_previs_scope` |
| REQ-S09-01/02/03/04/33/34/40 | `test_previs_scope`（契约与门禁事实） |
| 层级与 JSON 边界（REQ-S09-12/21/30） | `tests/architecture/` 下 `test_previs_routing_publication_boundary`、`test_previs_automation_json_boundary`、`test_previs_batch_json_boundary`、`test_previs_monitor_json_boundary`、`test_local_previs_json_boundary`、`test_white_model_json_boundary`、`test_white_model_service_json_boundary` |

## S10 视频生成

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `cloud_video`（`settings_window`） | 云端调用设置页：服务商／模型／密钥／本地秒数上限；保存只建会话，不提交 |
| L4 | `local_video`（`LocalAPI`、`LocalStudio`、设置窗） | 本地 ComfyUI 后端：回环地址校验、提交、查询取回；`auto_plan`／`auto_batch` 为无人值守本地补视频 |
| L4 | `video_navigation`、`video_progress`、`video_prompt_results`、`shared_video_controls` | 视频页导航、进度、提示词结果与共享控件 |
| L3 | `engine`（`Studio`） | 云端提交、轮询、下载、质检、验收、锁定版本、拼装；`auto_edit_ready` 给出成片指纹 |
| L3 | `stage_flow` / `stage_parallel` | 依赖 `DEPENDS`、付费阶段 `PAID_STAGES`、并发与重试 `CONFIG['video']`、限流 `rate_limited`、SG-05 门禁 `previs_ready` |
| L3 | `stage_completion_service` | `completion_evidence` 视频分支，核验回调由桌面注入 |
| L2 | `video_task_state` | 任务活动判定、提交阻断原因、服务商终态原因、提示词编辑锁 |
| L2 | `video_lifecycle_service` | 镜头视频删除标记、素材／声音选项、白模上传选项，经 L3 注入的发布器原子保存并回滚 |
| L2 | `cloud_video_service` | 云视频服务商表、会话目录、凭据查询、会话配置发布（经注入） |
| L2 | `video_source_evidence` | 从脱敏的实际请求解析首帧／白模／参考图的 SHA-256 摘要 |
| L2/适配 | `agent/wan.py`、`agent/volcengine.py`、`agent/shot_assets.py` | 万相／Seedance 协议适配与镜头参考素材准备 |
| L1 | `pet_llm`（`RequestLedger`、`record_request`）、`model_pool` | 逐次调用台账、API Key（DPAPI） |
| L0/契约 | `script_contract.STAGE_LOCK_REQUIREMENTS`、`stage_layout`、`stage_path_service` | 三项锁值、阶段目录与旧目录只读兼容 |

### 设计条目

- **DES-S10-01**（REQ-S10-01）`stage_layout.py:55-56` 登记 `10视频生成`；`stage_path_service.py:27` 的 `LEGACY_NUMBERED['video']='09视频生成'` 仅供读取。`Studio.validate`（`engine.py:228`）校验时长 2–15 秒与非空 `video_prompt`；`Studio.frame`（`engine.py:240`）缺首帧时提示回首帧阶段。
- **DES-S10-02**（REQ-S10-02）`script_contract.py:830` 把 `video` 列入 `STAGE_LOCK_REQUIREMENTS`，字段与 `keyframe`、`previs` 相同。
- **DES-S10-03**（REQ-S10-03，待定）`stage_flow.py:60-64` 的 `DEPENDS['video']=('keyframe',)`；SKILL `dependsOn: [pipeline-previs]` 与它不一致。待用户拍板后再决定是否并入 `previs`。
- **DES-S10-04**（REQ-S10-04）`stage_parallel.py:534` 的 SG-05 行 `{'id':'SG-05','from':'previs','to':'video','check':'previs_ready'}`；`previs_ready`（`stage_parallel.py:841` 起）无已采用分镜或无复杂镜头即放行，其余逐镜用 `previs_routing.ready` 核对可播放预演，缺失的镜头列入问题清单。
- **DES-S10-05**（REQ-S10-05）`stage_flow.py:76` 的 `PAID_STAGES`；`pet_ui_stages.py:275` 以 `paid=stage in PAID_STAGES` 调 `agent.approve('stage.run', ...)`。
- **DES-S10-06**（REQ-S10-06）`stage_parallel.py:75-78` 的 `CONFIG['video']`（串行、2–3 镜、上限 3、重试 2 次、`on_exhaust` 转人工、`rate_limit=True`）；`rate_limited`（`stage_parallel.py:140`）只对视频返回真。
- **DES-S10-10**（REQ-S10-10）`Studio.submit`（`engine.py:329`）：离线拒绝 → `submission_block_reason`（`video_task_state.py:65`）→ 时长对剩余秒数（`engine.py:341`）→ 先写 `submitting` 版本再联网（`engine.py:368`）。服务端 5xx 与连接中断记 `unknown` 且保留预留，不自动重发（`engine.py:390-400`）。
- **DES-S10-11**（REQ-S10-11）服务商表 `cloud_video_service.py:23-28`；会话目录 `session_folder`（`cloud_video_service.py:64`）按“服务商＋模型＋分镜源”复用或新建；`saved_provider_key`（`cloud_video_service.py:80`）优先读模型池，旧 `.env` 只读兼容。`cloud_video.py:172` 经 `model_pool.save_named_key` 保存密钥，会话配置只写 `key_provider='model_pool'`（`cloud_video.py:173`）。
- **DES-S10-12**（REQ-S10-12）`LocalAPI.__init__`（`local_video.py:29`）仅放行 `http` 与 `127.0.0.1`／`localhost`／`::1`；`reattach`（`local_video.py:178`）按 `client_id` 找回任务；`auto_plan`（`local_video.py:297`）遇非 `LocalStudio` 抛错，不静默提交云端。
- **DES-S10-13**（REQ-S10-13）云端：`ledger.authorize_units`（`engine.py:378`）→ 提交 → `settle_units`（`engine.py:394,399,433`）。落盘后 `record_video_usage`（`engine.py:296`）记 `videos` 条数与估算 `seconds`，已有 `money_request_id` 即跳过。本地版本 `charged=False`，只走 `record_video_usage`。
- **DES-S10-14**（REQ-S10-14）`task_receipt.json`（`engine.py:388`）与 `poll` 的回执恢复（`engine.py:411-416`）；下载失败保留 `succeeded` 并写 `download_error`（`engine.py:449-452`）；质检 `agent.media.check` 加 FFmpeg 解码（`engine.py:455-456`）；`provider_failure_reason`（`video_task_state.py:9`）；`submitted_sources`（`video_source_evidence.py:5`）要求 `sha256:` 64 位十六进制摘要。
- **DES-S10-15**（REQ-S10-15）`Studio.review`（`engine.py:471`）、`review_many`（`engine.py:509`）、`pin_version`（`engine.py:493`）；自动验收云端读 `project_settings.auto_review`（`engine.py:457`），本地读 `pet_ui.should_auto_run`（`local_video.py:236`）。
- **DES-S10-16**（REQ-S10-16）`assert_prompt_editable`／`prompt_locked`（`video_task_state.py:46-52`）；`generation_active`（`video_task_state.py:20`）还扫 `cloud_video/*/config.json` 中指向同一分镜的其他会话。
- **DES-S10-17**（REQ-S10-17）`mark_video_deleted`（`video_lifecycle_service.py:33`）遇未决状态返回 `UserError`，发布失败时 `shot.clear()`／`update(previous)` 回滚。
- **DES-S10-18**（REQ-S10-18，待定）两路自动验收判据来源不同，见 DES-S10-15。
- **DES-S10-20**（REQ-S10-20）`Studio.task_folder`（`engine.py:280`）与 `submit` 落盘的 `request.json`／`assets_manifest.json`／`实际提交提示词.txt`（`engine.py:371-373`）、`publish_downloaded_video`（`engine.py:283`）写 `qc.json` 并带 `sha256`。
- **DES-S10-21**（REQ-S10-21，待定）`stage_layout.py:56` 声明输出 `videos.json`；全仓库无写入点（`video_manifest.json` 同）。处理方式待用户拍板。
- **DES-S10-22**（REQ-S10-22）`completion_evidence`（`stage_completion_service.py:413`）的 `stage == 'video' and callable(video_ready)` 分支（`:443-445`）要求 `auto_edit_ready` 返回的指纹为真；无回调则落到通用媒体文件检查（`:446-455`）。调用方 `pet_ui_stages.py:28-30,35-37,99-101` 均传 `studio.auto_edit_ready`。
- **DES-S10-23**（REQ-S10-23）`approved_versions`（`engine.py:17`）、`adopted_edit_version`（`engine.py:64`）：锁定版优先，其次最后已验收版；文件缺失／摘要不符返回 `missing`／`replaced`。`auto_edit_ready`、`assemble` 与界面采用显示共用该口径。
- **DES-S10-30**（REQ-S10-30/31/32/33）SKILL 位于 `skills/10视频生成SKILL/`；`skill_tools.py:461-464` 把 `video.batchSubmit`／`retry`／`pause`／`resume` 登记为页面步骤，`skill_tools.py:416,420,488-489` 登记 `video.qualityCheck`、`video.pollStatus`、`video.submit`、`video.validate`。视频提示词规则见 `stage_layout.py:156` 与 `stage_parallel.py:214`。
- **DES-S10-40**（REQ-S10-40）`tests/architecture/_layers.py` 把 `cloud_video`、`local_video` 登记为 L4，`engine` 为 L3，`cloud_video_service` 为 L2；`architecture.md` 的 L2 行原误含 `cloud_video`、`local_video`，已移到 L4 行。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S10-01/02/03/04/05/06 | `test_video_generation_scope`；`test_stage_flow`、`test_stage_parallel`、`test_stage_layout` |
| REQ-S10-10 | `test_video_generation_scope`（阻断判定）；`test_video`、`test_video_revision`、`test_video_task_status` |
| REQ-S10-11 | `test_cloud_video`、`test_cloud_video_settings_boundary` |
| REQ-S10-12 | `test_video_generation_scope`（回环、仅本地）；`test_video`、`test_video_ui` |
| REQ-S10-13 | `test_video`、`test_request_ledger`、`test_request_recording` |
| REQ-S10-14 | `test_video_generation_scope`（终态原因、摘要）；`test_video_result_polling`、`test_video_source_evidence` |
| REQ-S10-15/23 | `test_video_generation_scope`（已验收口径、锁定版）；`test_video_revision`、`test_version_pin`、`test_edit_adoption` |
| REQ-S10-16 | `test_video_task_status`、`test_video_prompt_publication` |
| REQ-S10-17 | `test_video_generation_scope`；`test_video_lifecycle_service`、`test_video_delete_boundary` |
| REQ-S10-20 | `test_video` |
| REQ-S10-22 | `test_video_generation_scope`；`test_stage_completion_service` |
| REQ-S10-30/32/40 | `test_video_generation_scope` |
| REQ-S10-18/21/31 | 待用户拍板后补测试（现为 ❓／🟡，不测实现） |

## S11 配音与字幕

### 模块表（按层）

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L0 | `pet_bus`、`stage_layout`、`stage_path_service` | 阶段键与名称、目录与声明产出、新写目录 `write_dir`／旧目录只读 `read_dirs` |
| L1 | `agent.media`（ffprobe 校验）、`pet_llm.RequestLedger`（计量与预算） | 媒体探测、付费请求登记 |
| L2 | `tts_api` | 音轨用途、音色解析、逐句批次身份与续跑、成本预览、整段／逐句合成（发布器由 L3 注入） |
| L2 | `audio_import_service` | 导入音频校验与落盘（发布器由 L3 注入） |
| L2 | `subtitle_timing` | 估算／校准字幕时间轴、时间校验、SRT 行渲染（纯计算） |
| L2 | `subtitle_export_service` | 准备 SRT／对白脚本／校准状态文本，交注入发布器发布 |
| L2 | `stage_completion_service` | 媒体成果技术校验、人工确认清单、阶段完成核验 |
| L3 | `stage_execution_service` | `import_stage_audio`、`export_stage_srt`、`export_stage_dialogue_script`、`run_tts_lines`、整段配音发布与复用的编排与发布器注入 |
| L3 | `stage_flow`、`stage_parallel`、`workflow_settings`、`skill_registry` | 依赖、付费、并行与重试、SKILL 默认勾选与加载 |
| L4 | `desktop_media_pages`（配音页）、`tts_settings` | 导入／合成／导出按钮、付费确认框、设置对话框 |
| SKILL | `skills/11配音字幕SKILL/*.skill.md` | 六个内容 SKILL（见 REQ-S11-30） |

### 设计条目

- **DES-S11-01**（REQ-S11-01/02/03）阶段顺序在 `pet_bus.STAGES`；目录行 `('11配音与字幕','audio',…,('storyboard_final.json',),('voice.json','subtitles.json'))` 在 `stage_layout.STAGES`；依赖 `stage_flow.DEPENDS['audio']=('final',)`，付费 `PAID_STAGES`，并行 `stage_parallel.CONFIG['audio']`（单位=角色轨，`serial=True`，重试 2 次，耗尽转手动）。
- **DES-S11-04**（REQ-S11-04）`media_scope` 取当前已采用分镜及其 sha256；`prepare_media_completion` 做路径限制（须在本阶段 `音频/` 目录内、扩展名限四种、非空）、ffprobe 探测并冻结 `pending_review` 清单；至少一条 `audio_kind==dialogue`；`confirm_media_completion` 仅在人工确认入口调用，写 `成果确认/<fingerprint(source)[:24]>.json`。`_validate_media_completion` 在读取时重核 scope、技术校验、文件大小与 sha256。
- **DES-S11-10**（REQ-S11-10）`AUDIO_KIND_PREFIXES`（旁白_／BGM_／音效_／整轨_）；对白保持原名；`audio_kind` 从文件名前缀推断，识别不出按对白。
- **DES-S11-11**（REQ-S11-11）`import_audio` 做阶段／用途／后缀／空文件检查，目标名 `<标记名>_<6位随机>.<后缀>` 放入 `project_stages.audio(project)`（`<阶段目录>/音频`）；校验与落盘由 `stage_execution_service.media_import_publisher` 注入，经 `publish_imported_media` 用 `agent.media.validate_import`。
- **DES-S11-12**（REQ-S11-12）整段：`script_signature` → `reusable_tts_full_track`／`publish_tts_full_track`。逐句：`build_lines` → `resume_folder` 取续跑目录（`配音分句/`）→ `batch_cost_preview` 只读预览 → 用户确认 → `run_lines`：`freeze_settings` 开批冻结；每句 `RequestLedger.metered_units` 计量；`时间轴.json` 逐句落清单（状态 sending／ok／failed／uncertain）；`批次.json` 存签名与身份；`line_done` 以 sha256 判定沿用；sending／uncertain 的同身份句子不自动重发；`stop` 事件可中断后续跑。发布走注入的 `publish_json／publish_bytes`。
- **DES-S11-13**（REQ-S11-13）`voice_for(voices, speaker, name)`：ID 优先，显示名其次，空串=默认音色。
- **DES-S11-20**（REQ-S11-20/22）`_dialogue_rows` 解析对白（字符串旧格式与 dict 新格式）；镜内混合标注直接 `ValueError`；`_distribute` 先扣已知真实时长，剩余按 `line_weight`（可见字符数）分配；已知合计占满或超出镜头则压缩并记 overflow；`calibrate_entries` 返回 (entries, report)，report.mode ∈ estimate／length／mixed／explicit／audio。
- **DES-S11-21**（REQ-S11-21）`validate_entries` 在每次导出前强制调用（`_calibrated`），失败即抛错，不静默修正；`_clamp` 仅用于把作者标注的区间夹进镜头内，不用于修复非法值。
- **DES-S11-23**（REQ-S11-23）`export_srt`：校准 → 校验 → `rows_from_entries` → 注入发布器以 `utf-8-sig` 发布到 `project_stages.subtitles(project)`（`<阶段目录>/字幕`）的 `对白_<6位>.srt`，成功后再发布 `字幕校准.json`（失败只记警告，不影响 SRT）；`export_dialogue_script` 发布 `对白脚本_<6位>.txt`；L2 无发布器时抛 `TypeError`，写盘失败返回 `SystemError`，空对白返回 `UserError`。
- **DES-S11-30**（REQ-S11-30/31）SKILL 由 `skill_registry` 递归扫描 `skills/11配音字幕SKILL/`；总入口 `pipeline-audio-subtitle` 在 `workflow_settings` 阶段默认勾选；`voice-multi-character` 描述标注“已合并”，ID 仅供旧配置兼容。

### 待决设计（与 REQ 中 ❓ 对应）

- **DES-S11-24**（REQ-S11-24）ASS 导出无实现；设计上若补，须沿用 `subtitle_export_service` 的“L2 只准备文本、L3 注入发布器”模式，并复用 `calibrate_entries/validate_entries`。未补之前，文档与 SKILL 不得承诺 ASS。
- **DES-S11-40**（REQ-S11-40）声明产出（`voice.json`／`subtitles.json`）与真实完成凭据（`成果确认/*.json`）分离；后期剪辑阶段声明读取前者，实际读取字幕与音频目录文件。统一方向待拍板。

### 测试锚定

| REQ | 测试 |
| --- | --- |
| REQ-S11-01/02/03/04/10/11/12/20/21/22/23/24/30/31/40 | `tests/test_audio_subtitle_scope.py`（16 条，本批新增，断言均为已核实事实） |
| REQ-S11-04 | `tests/test_stage_completion_service.py` 等既有完成度测试（清单链路，本批未逐条核对） |
| REQ-S11-11 | `tests/test_audio_import_service.py`、`tests/architecture/test_audio_import_boundary.py` |
| REQ-S11-12 | `tests/test_tts.py`、`tests/architecture/test_tts_publication_boundary.py` |
| REQ-S11-13 | `tests/test_audio_role_binding.py` |
| REQ-S11-20/21 | `tests/test_subtitles.py` |
| REQ-S11-22 | `tests/test_subtitle_calibration.py` |
| REQ-S11-23 | `tests/test_subtitle_export_service.py`、`tests/architecture/test_subtitle_export_publication_boundary.py` |
| REQ-S11-14/32 | 无测试（⬜／🟡） |

## S12 后期剪辑

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_media_pages`（`MediaPagesMixin.editing／handoff／verify_handoff／edit_ready`） | 后期页：自动粗剪、素材交接包、校验交接包、校验并确认成果、剪辑优化清单；只注入回调 |
| L4 | `desktop_auto_flows.poll_auto_edit` | 无人值守自动粗剪的轮询与线程派发 |
| L4 | `desktop.confirm_stage_media` | 成果文件选择、确认框、调用 L3 确认 |
| L3 | `editing_page_controller` | 无 Tk 的后期页状态：有无已下载视频、粗剪结果文案、规格文案 |
| L3 | `stage_execution_service` | 剪辑优化清单、自动粗剪／自动交接标记、交接包的原子发布器注入；`verify_handoff_bundle` |
| L3 | `stage_completion_service` | 媒体成果技术校验、冻结待审清单、显式确认、完成证据（`edit` 走 `media_completion_evidence`） |
| L3 | `stage_flow`／`stage_parallel`／`skill_tools` | 依赖 `DEPENDS`、`CONFIG['edit']`、SKILL 工具表（READY／PAGES） |
| L2 | `engine`（`Studio`） | 采用版本 `adopted_edit_version`、`assemble`、`_encode`、`publish_edit_bundle`、`publish_edit_lists`、`auto_edit_ready` |
| L2 | `edit_service` | 优化清单与自动粗剪标记（发布器由 L3 注入）、`automatic_assemble_decision` |
| L2 | `handoff_service` | 交接包描述与清单校验（发布器由 L3 注入） |
| L2 | `edit_export` | EDL／FCPXML／分轨素材清单文本，不写盘 |
| L0/契约 | `stage_layout`／`stage_path_service`／`project_stages` | 阶段目录 `12后期剪辑`、旧 `11后期剪辑` 只读、成片目录 `13质检交付/导出成片` |
| L0/契约 | `pet_bus` | 阶段 `edit`＝第 12 阶段、显示名“后期剪辑” |

### 设计条目

- **DES-S12-01**（REQ-S12-01）`stage_flow.DEPENDS['edit']=('video',)`、`DEPENDS['delivery']=('edit',)`。
- **DES-S12-02**（REQ-S12-02/03）`engine.approved_versions` 取已下载＋`qc_pass`＋`review=='pass'`；`adopted_edit_version` 在其中先取 `pinned is True`，否则最后一条，再核文件存在与 `file_hash==sha256`，失败返回 `unapproved／missing／replaced／unreadable`；`review_source／content_reviewed／review_label` 区分真人与自动放行。
- **DES-S12-05**（REQ-S12-05）`Studio.output_spec` → `stage_config.workflow_lock` → `script_contract.resolve_output_spec`；`output_spec_text` 供页面显示。
- **DES-S12-10**（REQ-S12-10/13）`Studio._encode` 逐镜 ffmpeg 重编码（`output_filter`＋`loudness_filter`，无音轨补 `anullsrc` 并写 `_音轨说明.json`，`post_overlay` 用 `drawtext`），`concat -c copy` 到 `.partial.mp4`，`-xerror` 解码核验后 `replace` 为 `MASTER.mp4`。
- **DES-S12-11**（REQ-S12-11）`Studio.assemble(shot_ids, skip_unready, report)` 在项目锁内挑选并记 `coverage`（included／expected／duration／skipped），编码放在锁外；`EditingPageController.assemble／assembled_message` 组织文案。
- **DES-S12-12**（REQ-S12-12）`desktop_auto_flows.poll_auto_edit` → `edit_ready`（签名＋`Studio.auto_edit_ready` 指纹）→ `edit_service.automatic_assemble_decision`（skip／wait／complete／dispatch）；完成后 L3 `save_automatic_assemble_marker` 写 `自动粗剪.json`。
- **DES-S12-14**（REQ-S12-14/15）`MediaPagesMixin.handoff` 选版后交 `stage_execution_service.publish_stage_handoff_bundle` → `handoff_service.publish_bundle`；`verify_handoff_bundle` ＋ `handoff_service.verify_manifest` 做离线核对。
- **DES-S12-16**（REQ-S12-16）`edit_service.save_editing_checklist` 只收 L3 注入的发布器；`stage_execution_service.save_stage_editing_checklist` 以 `allow_empty=True` 注入。
- **DES-S12-20**（REQ-S12-20/21）`Studio.assemble` 用 `project_stages.exports` ＋ `project_naming.dated_path` 建成片目录；`publish_edit_bundle` 先原子写 `edit_bundle.json`，再写 `qc.json`、`edit_manifest.json`；`read_edit_bundle` 在无 bundle 时退回两份索引（`legacy`）。
- **DES-S12-22**（REQ-S12-22）`_encode` 在 `report['errors']` 非空时在发布 bundle 与交换清单之后才抛错；`publish_edit_lists` 失败只返回 `{'ok':False}`，不删成片。
- **DES-S12-23**（REQ-S12-23/24）`media_output_folders('edit')`＝`read_dirs('edit')`＋各 `delivery` 读目录下 `导出成片`，后缀 mp4／mov／mkv；`prepare_media_completion` 技术校验并生成 `pending_review`；`confirm_media_completion` 写 `complete／reviewed`；`media_scope` 绑定当前采用分镜；`completion_evidence` 把 `edit` 路由到 `media_completion_evidence`。
- **DES-S12-25**（REQ-S12-25）`stage_layout.STAGES` 的 `('12后期剪辑','edit',…,('videos.json','voice.json','subtitles.json'),('edits.json',))`；未被读写，状态待裁决。
- **DES-S12-26**（REQ-S12-26）`stage_parallel.CONFIG['edit']`：`min/max/limit=1`、`serial=False`、`retry.attempts=2`、`on_exhaust=ON_BLOCK`。
- **DES-S12-30**（REQ-S12-30）`workflow_settings` 默认 `'edit':['pipeline-editing']`；`skill_registry` 目录号 `12`→`edit`。
- **DES-S12-31**（REQ-S12-31/32）`skill_tools.READY` 含 `edit.compose`、`edit.export*`（只回规格）；`skill_tools.PAGES` 含 `edit.assemble／validate／addTransition／addSFX／addBGM`，`call` 对 PAGES 条目抛 `ToolNeedsPage`。
- **DES-S12-35**（REQ-S12-35）`edit_export.build_edl／build_fcpxml／build_tracks／export_texts`，写盘由 `Studio.publish_edit_lists` 经 `agent.core.save／save_text` 完成。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S12-01 | `test_editing_scope`（新）、`test_stage_flow` |
| REQ-S12-02/03 | `test_edit_adoption`、`test_editing_scope`（新） |
| REQ-S12-05 | 暂无断言（输出规格解析由 `script_contract` 既有测试覆盖） |
| REQ-S12-10/11 | `test_integration`、`test_editing_page_controller` |
| REQ-S12-12 | `test_edit_service` |
| REQ-S12-14 | `test_handoff_bundle`、`test_handoff_service`、`architecture/test_handoff_publication_boundary` |
| REQ-S12-16 | `test_edit_service`、`architecture/test_edit_publication_boundary` |
| REQ-S12-20/21 | `test_editing_scope`（新，目录位置）、`test_edit_adoption`（bundle 用例）、`architecture/test_edit_publication_boundary` |
| REQ-S12-22/35 | `test_edit_export` |
| REQ-S12-23 | `test_stage_completion_service`、`test_editing_scope`（新） |
| REQ-S12-25/26/30/31/32 | `test_editing_scope`（新） |
| REQ-S12-15/24/33/34 | 现状差距，暂无断言（待用户裁决后再补） |

## S13 质检与交付

### 模块分工

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L4 | `desktop_media_pages`（`MediaPagesMixin.delivery`） | 交付页：采用/QC 状态表与按钮；只注入回调 |
| L4 | `desktop`（`confirm_stage_media`、`commercial_delivery_review`） | 选文件、后台调用核验服务、展示结果 |
| L3 | `stage_flow` / `stage_parallel` | 依赖 `DEPENDS`；并行与重试配置 `CONFIG['delivery']` |
| L3 | `stage_execution_service` | `import_delivery_master` 注入发布器；交接包发布与校验 |
| L3 | `skill_tools` | `qa.*`、`delivery.*` 工具表：`READY`（本地实现）与 `PAGES`（页面动作） |
| L3 | `stage_workspace_service` | `ensure_delivery_workspace` 创建交付与导出目录 |
| L2 | `delivery_import_service` | 最终成片导入：后缀与空文件校验，目标目录与发布器由 L3 注入 |
| L2 | `usage_overview` | 用量总览、交付时长证据、每分钟成本、不付费场景估算 |
| L0/契约 | `stage_completion_service` | 媒体成果技术校验、人工确认清单、商用资料核验、完成证据 |
| L0/契约 | `stage_layout` / `stage_path_service` | `13质检交付` 目录与旧名只读兼容；`write_dir`/`read_dirs` |
| L0/契约 | `storyboard_adoption_contract` | 采用分镜来源，作为成果确认的范围 |
| L0/契约 | `pet_bus` | 阶段 ID／名称（`delivery`＝质检与交付） |

### 设计条目

- **DES-S13-01**（REQ-S13-01）`stage_flow.DEPENDS['delivery']=('edit',)`。
- **DES-S13-02**（REQ-S13-02）`media_scope(root)` 取 `adopted(root)` 与偏好 `frame_json` 解析出唯一来源，返回项目、来源相对路径、`source_sha256`、集号；无来源或无 `shots` 抛 `ValueError`。
- **DES-S13-03**（REQ-S13-03）`prepare_media_completion` 取 `config.json` 的 `ffprobe` 或 `platform_tools.tool_path('ffprobe')`，缺失抛 `ValueError`；探测由 `agent.media.probe`＋`media_facts` 完成。
- **DES-S13-04**（REQ-S13-04）`STAGE_LOCK_REQUIREMENTS` 键为 `script/keyframe/previs/video`，不含 `delivery`。
- **DES-S13-10**（REQ-S13-10）交付页按钮：导入剪映最终成片、校验并确认本阶段成果、生成商用待填资料、核验商用交付资料、选择采用版本、打开目录。
- **DES-S13-11**（REQ-S13-11）`delivery_import_service.ALLOWED_SUFFIXES={'.mp4','.mov'}`；目标文件名＝原名＋6 位随机＋原后缀；发布走 `stage_completion_service.publish_imported_media`，同时写 `<文件>.source.json`（`rights_status='unknown'`）。
- **DES-S13-12**（REQ-S13-12/13）`prepare_media_completion` 逐文件：`_media_path`（目录＋后缀＋非空）→ 哈希 → 探测 → 再哈希；全部通过后生成 `status='pending_review'` 清单并自校验。
- **DES-S13-14**（REQ-S13-14）`confirm_media_completion` 仅由显式确认入口调用，写 `complete/reviewed=True`；`delivery` 另加 `commercial_status='pending'`；落盘到 `media_manifest_path`＝`write_dir(root,'delivery')/成果确认/<fingerprint(来源)[:24]>.json`。
- **DES-S13-20**（REQ-S13-20/21/22/23）`completion_evidence` 对 `audio/edit/delivery` 走 `media_completion_evidence`→`_validate_media_completion`（schema、阶段、范围、状态、技术校验、大小与哈希）；`emit_verified_completion` 核验通过后才发 `stage.completed`。商用函数不在此路径上。
- **DES-S13-24**（REQ-S13-24/25/26/28）待定：`stage_layout` 声明产物、`pipeline-delivery` 的工具与约束、后缀集合、`commercial_status`／`delivery.ready` 的归属，按需求裁决后再设计。
- **DES-S13-30**（REQ-S13-30/31）`create_commercial_template` 目标为 `<成果确认>/<指纹>.commercial.pending.json`，已存在即拒绝；`_commercial_inventory` 预填剧本（经 `board_source_script`）、成片、`edit_bundle.json` 的 `manifest/fonts/references`、`font.ttc`，授权字段留空。
- **DES-S13-32**（REQ-S13-32~36）`validate_commercial_evidence`：范围与成片摘要一致 → 清单完成声明与审核人 → 七类逐类（`COMMERCIAL_CATEGORIES`）→ 条目字段与授权文件冻结校验 → 覆盖实际剧本来源／成片／镜头来源／参考／字体 → `content_review` 三项 `cleared`＋审核人＋证据。确认后写 `<指纹>.commercial.json`。
- **DES-S13-40**（REQ-S13-40）`usage_overview.read_events` 读 `model_diagnostics`；`_add` 对无用量事件计 `unknown_usage`，`not_submitted` 单独计数。
- **DES-S13-41**（REQ-S13-41/42/43）`delivery_duration` 逐份校验确认清单（`complete`、`reviewed`、范围、来源哈希、`validation.passed`、大小与哈希）后累加时长；`cost_per_minute` 对缺项返回 `None`/缺项列表，`basis='recorded_usage_estimate_not_supplier_invoice'`。
- **DES-S13-50**（REQ-S13-50）`workflow_settings` 阶段默认 SKILL＝`['pipeline-delivery']`；SKILL 位于 `skills/13质检交付SKILL/`。
- **DES-S13-51**（REQ-S13-51）`stage_parallel.CONFIG['delivery']`：`unit=CHECK, min=2, max=4, serial=False, limit=4, retry={attempts:2, backoff:'fixed', on_exhaust:ON_REPORT}`。
- **DES-S13-53**（REQ-S13-53）`skill_tools.READY` 含 `qa.visualCheck/audioCheck/subtitleCheck`、`delivery.generateReport/exportManifest`；`PAGES` 含 `qa.styleCheck/complianceCheck`、`delivery.archive/validate/package`。
- **待定**（REQ-S13-52）模板步骤是否程序化，待总控拍板。

### 测试锚定

| 需求 | 测试 |
| --- | --- |
| REQ-S13-01/04/50/51 | `test_delivery_scope` |
| REQ-S13-11 | `test_delivery_scope`、`test_delivery_import_service`、`architecture/test_delivery_import_boundary` |
| REQ-S13-12/14/20/21 | `test_stage_completion_service` |
| REQ-S13-30~36 | `test_stage_completion_service`、`test_delivery_scope`（七类常量） |
| REQ-S13-40~43 | `test_usage_overview` |
| REQ-S13-24/26/53 | `test_delivery_scope`（声明产物、后缀差异、工具表登记情况） |
