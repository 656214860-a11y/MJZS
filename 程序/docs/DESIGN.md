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
