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
