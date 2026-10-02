# 第 182 轮：应用优化清单

日期：2026-09-27。依据：`smoke_test.py --architecture`、核心契约测试与根目录模块静态扫描。

## P0：先恢复可验证的架构边界

1. **消除根模块巨大循环依赖。** 当前仍有一个跨 50 余模块的 SCC，入口含 `agent_dispatch → app → desktop`，会导致导入顺序敏感、测试污染和局部修改触发全应用加载。先拆 UI 启动、阶段编排与领域服务的反向导入；每次拆分后必须跑 `tests.architecture.test_no_circular_import`。
2. **完成剩余 18 个低层反向依赖。** 重点是 `storyboard_files`、`asset_batch` 混入 Tk/UI 与阶段配置，`writing_api` 直接读阶段配置／工作任务，`script_contract` 直接读技能注册表。应提取 L0/L1 的数据协议或以显式参数注入，不允许用白名单压过测试。
3. **路径字面量建立唯一权威。** `test_path_authority` 仍发现约 213 处 `assets.json`、`episode.json`、`config.json` 等路径规则散落在应用和 UI 中。将真实文件名与路径拼接集中到 `stage_path_service` / 专门的路径常量模块；提示文字可保留，但检测规则需区分“展示文案”和“文件操作”。
4. **删除与回收统一网关。** 所有用户文件删除必须经 `storage_maintenance.recycle_paths`，并在删除前验证项目边界、符号链接／junction 与当前阶段归属；为每一个 UI 删除入口加端到端测试。

## P1：稳定性、数据一致性与工作流

1. **阶段写入收口。** 所有新文件只写编号阶段目录；遗留 `writing` 等目录只读兼容，并设定可执行淘汰日期、迁移报告和回滚记录。避免同一自然剧本在两个目录重复显示。
2. **单一状态来源。** 三虎进度、分镜“已制作”、分镜“已采用”和实际文件产物必须从同一状态记录推导；完成提示必须在成功保存、校验、采用之后才发出。
3. **模型调用可观测性。** 对每次模型调用记录 provider/model、请求 ID、`finish_reason`、正文/推理字段长度、重试原因与脱敏错误；空正文按角色有上限的一次重试，最终显示诊断而不是笼统弹窗。
4. **原子保存与恢复。** 剧本、结构剧本、资产清单和分镜 JSON 全部采用临时文件校验后替换；编辑/右键删除要有恢复入口和可追踪回收记录。

## P2：代码质量与可维护性

1. **拆分巨型 UI 文件。** `desktop.py`（约 369 KiB）、`pet_ui.py`（约 250 KiB）、`app.py`（约 95 KiB）按 view / presenter / service / adapter 切开。首批目标为剧本、分镜、资产三个页面，公共布局进入 UI 组件层。
2. **三虎只保留一个 L3 命令入口。** UI 只派发阶段命令；自动/手动/猫爪状态由同一个状态机处理，不在各页面复制启动和完成逻辑。
3. **异常分级。** 审核广泛 `except Exception`：边界处保留并记录上下文；领域层改捕获预期异常；不得静默吞掉写入、模型或删除失败。
4. **命名与内部 API。** 新业务模块使用明确的输入/输出数据结构；旧 `writing` API 作为兼容外观逐步退役。本轮已将镜头 JSON 校验下沉为 `episode_contract.py`，旧 API 继续重导出。

## P2：测试与质量保障

1. **把架构测试变成合并门槛。** 当前架构测试未绿，不能标记治理完成；按 P0 分批使 layer / cycle / path 三项归零。
2. **按阶段提供契约测试夹具。** 对剧本准备、剧本结构、初步分镜至少覆盖：输入不足、正常生成、空正文、保存失败、重试、重启后刷新、删除和恢复。
3. **补 UI 回归基线。** 使用小窗口尺寸测试按钮文字、上下内容区自适应和长列表。当前 `tests.test_asset_detail.EntryTests.test_an_unknown_id_is_reported` 失败，应先最小复现再修复或更新过期断言。
4. **覆盖率按风险而非总数。** 为删除网关、文件迁移、模型响应解析和阶段完成判定设置分支覆盖门槛；禁止只靠导入测试凑覆盖率。

## P3：性能、兼容性和可移植性

1. **列表/内容框增量刷新。** 文件扫描走缓存和修改时间指纹，避免每次页面切换递归扫描项目；长文本采用延迟加载。
2. **后台任务取消与资源回收。** 每个模型/媒体任务有取消令牌、超时和 UI 关闭后的安全回收，避免 Tk 主线程被网络请求卡住。
3. **路径兼容层集中化。** 一律使用 `pathlib` 和项目根边界检查，覆盖 Windows 中文路径、长路径、junction、只读目录；将硬编码 `D:/` 限制在可编辑配置。
4. **配置可导入导出。** provider 凭据不写入项目；阶段预设、导演/编剧/编辑/演员规则区分项目级与全局级并含 schema 版本迁移。

## 本轮已落地的低风险改进

- 新增 `episode_contract.py`，承载镜头相对路径、时长和 JSON 校验；`writing.py` 保留兼容重导出，移除了 `projects ↔ writing` 小循环。
- 将 `project_stages` 定义为 L0 路径事实，而不是 L3 编排，消除了服务层对纯路径事实的伪违规。
- 将资产门禁的“选择落盘”移至 `asset_plan.apply_gate_choice`；`confirm_gates` 不再反向依赖资产上下文。
- 将 `app` 归为 UI 模块、`app_icon` 归为基础设施模块，匹配其实际职责。

## 本轮验证

- `python -m py_compile episode_contract.py writing.py projects.py asset_plan.py confirm_gates.py asset_detail.py desktop.py`：通过。
- `python -m unittest tests.test_core tests.test_media`：119 通过。
- `tests.architecture.test_layers`：仍有 18 项真实跨层依赖，未伪造通过。
- `tests.architecture.test_no_circular_import`：剩余一个 L0 小环与一个大型 SCC，未伪造通过。
- `tests.test_asset_detail`：22 通过、1 项历史 UI 行为断言失败（未知资产提示），待 P2 复现修复。

## 追加进展：依赖环拆解（本轮）

- 新增 `script_manifest_contract.py`、`production_model_contract.py`、`asset_batch_service.py` 与 `storyboard_adoption_contract.py`，把跨阶段共用的事实、生产模型名、资产登记和已采用分镜读取移出 UI/编排模块。
- `app.App` 的视频“手动制作”改由 `Desktop` 注入 `manual_command`，视频视图不再直接导入阶段编排；`codex_tasks` 直接读取 token 节省配置，不再为这一项导入三虎父 Agent。
- 已移除 `projects ↔ writing`、`stage_layout ↔ confirm_gates`、`stage_models ↔ keyframe_comfy`、`asset_batch ↔ asset_skill_batch`、`asset_batch ↔ pet_ui`、`asset_batch ↔ native_assets` 等短环。
- 回归：`tests.test_assets` 60 通过；`tests.test_keyframe_comfy` 12 通过；核心架构检查仍不通过，当前剩余为一个大型 SCC 和 17 项真实越层依赖。下一优先项是 `asset_reference_images ↔ asset_reference_import`、`local_previs ↔ previs_automation`、`pet_settings_ui ↔ pet_ui` 等最短环；不得通过例外白名单掩盖。

## 追加进展：可靠性与依赖治理（2026-09-27）

- 白模预演的路由模块改为接收页面注入的复杂镜头执行器；路由不再反向导入自动化执行模块，既保留“手动制作白模”一键启动，也消除了 `previs_routing ↔ previs_automation` 静态环。
- 工作流设置页使用 `workflow_settings.agent_label`；`workflow_agents` 仅保留兼容转发，消除了 `workflow_settings ↔ workflow_agents` 静态环。`tests.test_dispatch` 24 项通过。
- 分镜文件模块不再反向调用分镜计划服务；阶段命令仍直接使用无 UI 的 `storyboard_plan_service`，`tests.test_stage_command_contract` 4 项通过。
- 修复资产详情未知编号只写状态栏、重排后用户看不到原因的问题；错误现显示在详情页，`tests.test_asset_detail` 23 项通过。
- 回归：`tests.architecture.test_dynamic_import_registry` 3 项通过。架构门禁当前仍有 17 个越层依赖和一个大型 SCC，故本清单未标记完成。

## 追加进展：批处理执行边界（2026-09-27）

- 新增无 Tk 依赖的 `asset_batch_execution.py`：批量出图、可恢复记录、提交不确定性保护和图片登记由该执行器负责；`image_agent_runner` 不再反向导入批量窗口模块。`asset_batch.py` 仅保留旧调用点的兼容入口及窗口职责。
- 新增 L3 `script_skill_report.py`：实时 SKILL 注册表报告从 `script_contract` 的事实层迁出；旧函数保留为按需加载的兼容外观，避免低层导入技能注册器。
- 验证：`python -m unittest tests.test_assets tests.test_auto_import` 为 **62 通过**；`tests.test_script_contract` 为 **42 通过**。本机运行环境未安装 pytest，故未把 pytest 的“找不到模块”误报成应用失败。
- 最新架构门禁：越层依赖已从 17 项降至 **10 项**；仍有一个大型 SCC，未标记完成。剩余主因是 `storyboard_files`、`asset_batch`、`native_assets` 三个“领域服务与 Tk 视图混存”的历史模块，必须继续做 view/service 拆分，而不是调低门禁或添加白名单。

## 追加进展：依赖环与历史结构稿兼容（2026-09-27）

- 旧项目的 `writing/script.md` 已恢复为只读结构剧本发现候选；不写回、不复制，避免迁移时生成重复文件。
- 新增 `comfy_runtime.py`，承接 ComfyUI 启动与就绪检测；资产与首帧服务不再静态依赖含界面的 `native_apps.py`。
- 已通过：`tests.test_file_cache tests.test_workflow tests.architecture.test_layers`（90 项）；`tests.architecture.test_no_circular_import tests.architecture.test_layers`（2 项）。
- 待办：运行完整回归，并收敛路径授权扫描中的真实越权写入与误报文本；在全量运行通过前，不宣称治理完成。

## 追加进展：路径权威门禁收敛（2026-09-27）

- 路径门禁改为只检查实际 `pathlib` 构造中的阶段目录片段；提示词、说明文字及通用数据文件名不再被误判为路径写入。
- 将遗留 `episode/assets` 路径归入 `asset_contract.legacy_asset_paths()`，分镜定稿目录改用 `project_stages.stage(..., 'final')`，剧本准备回退文件改用 `project_stages.writing()`。
- `smoke_test.py --architecture` 已通过 13/13（删除网关、动态注册、分层、模型边界、循环导入、路径权威、删除权威、阶段路径）。
- 完整 `unittest discover` 已启动并发现后段存在多项失败及 GUI 测试长期运行；已停止该非隔离运行，需按失败模块分批复现并修复，不能据此宣称全量测试通过。

## 追加进展：回归隔离与兼容入口（2026-09-27）

- `skill_orchestrator.Orchestrator` 现在将注册表的 `canonical_id` 视为可选能力：完整注册表仍会规范化别名，轻量/旧版注册表则按原 ID 查询。修复了阶段流程测试替身无法执行剧本链路的回归。
- `asset_batch.auto_batch` 恢复经 `native_apps` 的动态兼容入口调用 ComfyUI；该入口继续委托无界面 `comfy_runtime`，同时让宿主适配与测试替身能够拦截真实桌面/网络调用。
- 验证：剧本、结构、分镜和阶段流程相关 203 项通过；`tests.test_assets` 60 项通过；`tests.test_asset_contract` 26 项通过；`tests.test_asset_detail` 23 项通过；`tests.test_asset_gating tests.test_asset_restore tests.test_asset_resume` 26 项通过。
- 仍在继续按模块分段执行其余测试；此前遗留的 `unittest discover`/缩略图工作进程已停止，不能把其无结论的运行视为通过。

## 追加进展：归档结果与首帧适配器回归（2026-09-27）

- 修复 `storyboard_storage.normalize(..., min_age=0)` 的同步维护语义：零等待模式不再受取样时钟先后影响；同时以项目相对路径核对回收记录，维护实际移动旧分镜后会正确报告变更并保留别名映射。
- `keyframe_comfy.auto_batch` 与资产批处理一样经 `native_apps` 兼容适配器探测/启动 ComfyUI，底层仍由无界面的 `comfy_runtime` 执行；避免真实桌面或网络调用绕过测试与宿主控制。
- 剧本准备任务文案恢复“遵循所选 SKILL”的契约，同时明确 SKILL 不能跨越阶段输出边界，防止旧测试契约与现行自然剧本约束相互漂移。
- 验证：`tests.test_final_viewer tests.test_copy_rules tests.test_force_quit` 35 项通过；`tests.test_idea_chat` 58 项通过；`tests.test_keyframe_comfy tests.test_keyframe` 38 项通过；`tests.test_hollmwood_roles` 7 项、`tests.test_hollmwood_ui_queue` 2 项、`tests.test_integration` 23 项通过。
