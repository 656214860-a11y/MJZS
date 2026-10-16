# AGENTS.md — Codex 项目入口

> 本文件是 Codex 每次任务开始时的入口。
> 项目状态权威来源：`D:\漫剧制作助手\程序\project_status.md`
> 结构权威来源：`D:\漫剧制作助手\程序\architecture.md`

## 0. 任务开始时必读

本节是各代理入口阅读范围的唯一规定。每次任务开始前，按顺序读取：

1. `AGENTS.md`（本文件）
2. `project_status.md` 的轮次头、新对话接续协议、检查点、验证基线、已知阻塞与待办；历史条目只在涉及本轮任务或追溯凭据时读取，不能把旧记录当作当前验收。
3. `architecture.md`（目录树、模块清单、分层、阶段、并行、模型路由）
4. `PROJECT_MAP.md`（数据边界、门禁地图）

本文件、架构与地图须读完；状态页先定位上述标题并读完各节，缺失或事实冲突时继续定位相关记录，不能静默跳过。完成这些读取前，仅允许定位和读取接续资料，不开始修改、测试或认领。
接续依据文件系统，不依赖旧对话历史；对照现有模块清单，避免重复创建功能。

## 1. 项目速览

- 产品：Windows 桌面应用「漫剧助手」；Python + Tkinter，零第三方依赖
- 解释器：`D:\漫剧制作助手\运行环境\Python\python.exe`（不使用全局 Python）
- 工作流：13 个制作阶段（初步分镜之后为 Animatic 分镜预演）
- 执行链路：`skill_orchestrator`
- 三虎：进度界面、阶段日志、自动化等级、暂停恢复、资产跨重启续跑台账

## 2. 硬约束

### 2.1 通用硬约束

1. 不写入密钥，不在日志中泄露密钥。
2. 保护用户项目数据；只有明确授权的数据操作才可改动。页面或注册表类改动后提示重启，重启真实应用须在授权范围内。
3. 产品交付脚本不引入 shell 依赖。
4. 禁止只给方案，必须实际写入或修改文件（只读诊断轮除外）。
5. 复用现有模块，禁止重复创建。
6. 每轮只做本轮任务，不改范围外文件。
7. 轮次接续与结果归档按 §2.5 规则 27、§7；验证统一按 §5，提交统一按 §2.6。

### 2.2 权威源（唯一真源）

| 类别     | 唯一权威                                                                                               |
| ------ | -------------------------------------------------------------------------------------------------- |
| 阶段顺序   | `pet_bus.STAGES` / `STAGE_NAMES`                                                                   |
| 并行与重试  | `stage_parallel.CONFIG`                                                                            |
| 模型池    | 模型管理保存的模型池                                                                                         |
| SKILL  | `skills/01—13 阶段目录/*.skill.md` 与 `skill_registry.py`；根目录遗留文件只在阶段配置懒迁移时按 stage 归档；阶段外部包只登记根 `SKILL.md`/README 总入口，不展开内部 SKILL；剧本阶段入口须同步登记 `script_contract.AUDIT`，且不得虚构 manifest |
| 总控 SKILL（原统筹 SKILL） | 清单 `skills/00全流程SKILL/总控.json`（`workflow_settings.MASTER_MANIFEST`）；项目投影为 `skill_config.json` 顶层 `workflow` 键，同步基线在 `workflow.applied` |
| 锁采集 | 剧本准备简报流（创作信息窗） |
| 分层依赖   | `architecture.md` 第 3 节分层表                                                                         |
| 路径     | `stage_layout` / `storyboard_paths` / `script_contract` / `asset_contract` / `model_pool.env_file` |
| 事件与前缀  | `pet_bus` 事件表 / `broadcaster` 前缀表                                                                  |
| 缓存与索引  | `file_cache` / `asset_thumbs` / `hash_backend` / `*_manifest` / `*_lifecycle`                      |
| 删除     | 用户可见删除走回收服务，见“回收服务”                                                                                |
| 阶段命令入口 | `stage_handler_registry.start()`                                                                   |
| 动态导入   | `ui_plugin_registry.module()`                                                                      |
| 阶段路径   | `stage_path_service.write_dir()` / `read_dirs()`                                                   |
| 阶段完成核验 | `stage_completion_service`                                                                         |
| 回收服务   | `storage_maintenance.recycle_paths()`                                                              |
| UI 组件与弹窗 | `ui_widgets`（组件与全局 Style）／`ui_tokens`（视觉 token）／`ui_shortcuts`（快捷键登记）          |
| L2 写服务结果 | 第 1 项已解冻（2026-10-04 用户授权）；分批复用 `service_contract` 四字段结果，每轮最多 3 个 service；同轮迁移调用方、测试与采用方棘轮，不创造第三种返回形状。采用方和待迁移范围以 `维护记录/架构统一基数.json` 为准；执行顺序见路线图。 |
| 项目操作上下文 | 第 2 项已解冻（2026-10-04 用户授权）；按路线图顺序复用 L3 注入的 `project_context.ProjectContext`，每轮最多 3 个 service；采用方和待迁移范围以 `维护记录/架构统一基数.json` 为准。 |
| 阶段成果发布器 | `stage_execution_service.publish_stage_text()`／`publish_stage_bytes()`／`publish_stage_bundle()`；L2 写服务只能接收 L3 注入的发布器，音频导入经 `import_stage_audio()`、自动粗剪完成标记经 `save_automatic_assemble_marker()`、自动交接完成标记经 `save_automatic_handoff_marker()`、首帧删除／恢复／替换经 `delete_stage_keyframe()`／`restore_stage_keyframe()`／`replace_stage_keyframe()` 注入 |
| 正式 JSON 读写 | 读取优先 `file_cache.read_json()`，写入只经 `agent.core.save()`／`save_text()` 或 L3 发布器；L2 不得直接向正式路径 `json.dump()` 或裸写入 |
| 持久化产物版本 | rtifact_schema：正式 JSON 产物的版本、必备字段与迁移入口；新写入写 schema_version，读取侧容忍缺版本 |

总控宪法（R1433 起取代统筹宪法，用户 2026-10-14 授权）：总控 SKILL 负责统一调度与内容更新。① 唯一来源是 `skills/00全流程SKILL/总控.json`，清单缺失或损坏时退回出厂内置表并在体检中报明；② 指纹覆盖清单、全流程包入口、各阶段总控 SKILL 及其直接引用，指纹一变即由 `master_skill.sync` 自动同步各阶段并提示——只替换上次总控给的项，用户自加的 SKILL 保留、用户取消勾选的总控项不重新勾上、整体弃用总控建议的阶段不追加；③ 各阶段 SKILL 勾选始终由用户自由决定，总控不锁定勾选，一切既有 SKILL 编辑与试跑入口（浏览新增、改 md 即生效、重置、按引擎附加清单）不得因总控模式而移除或变灰；④ 门禁（`master_skill.gate` 与 `stage_handler_registry` 制作锁检查）在总控模式下对手动与自动路径一律阻断：本阶段必填制作锁缺失、已勾选 SKILL 的引用不可加载；剧本准备的简报采集对话除外，由简报门禁负责。

目录阶段契约由 `stage_layout.validate_stage_contract()` 守卫；任何变更 `pet_bus.STAGES` 或 `stage_layout.STAGES` 的轮次都必须使该校验通过。JSON/MD 对照表中的 MD 路径必须以当前编号阶段目录和 `docs/` 为前缀，禁止重新写出旧内部目录名。

### 2.3 新增结构硬约束（第 118 期起）

11. **分层依赖唯一权威**：`architecture.md` 第 3 节。只允许 `L5 入口 → L4 UI → L3 编排 → L2 业务 → L1 模型/存储 → L0 契约`；反向 import 一律禁止。
12. **路径唯一权威**：所有文件路径必须由 2.2 表中"路径"那一行的模块产出；其他模块禁止字符串拼接路径。
13. **事件与前缀唯一权威**：阶段事件只由 `pet_bus` 定义，播报前缀只由 `broadcaster` 定义；其他模块禁止自定义事件名或前缀。
14. **删除唯一权威**：用户可见删除统一经 `storage_maintenance.recycle_paths()`；临时文件、缓存和已验证的本轮临时产物可受控清理。
15. **测试文件唯一位置**：新测试一律放 `tests/`，不再放 `程序/` 根目录；现有测试位置由文档一致性门禁检查。
16. **测试搬家轮**：只允许移动文件和修 import 路径，禁止改测试逻辑、断言或 fixture；验收见 §3.6 与 §5。
17. **阶段启动唯一入口**：手动、自动和三虎阶段启动必须走 `stage_handler_registry.start()`。
18. **动态导入唯一入口**：L4 走 `ui_plugin_registry.module()`，L3 走 `stage_handler_registry`；禁止未登记的裸动态 `import`。
19. **阶段路径新写旧读**：新写入必须走 `stage_path_service`；旧目录仅作只读兼容。
20. **完成事件以产物核验为准**：由 `stage_completion_service` 核验产物；不接受模型文字或 UI 提示作为完成证据。
22. **事件发送边界**：跨模块状态只经 `pet_bus.emit_safe()`；仅 `pet_agent._emit()` 与 `pet_ui._emit()` 可作受控转发，禁止直调 `Bus.emit()`。`broadcaster` 只记录用户可见文本日志，不得承担状态通知。

### 2.4 测试契约变更

不得改测试迁就实现。接口、模块、路径或用户明确要求的 UI 契约发生有意变更时，可同步相关测试定位和预期；保留未变行为的断言，禁止弱化、删除断言或跳过测试以制造通过。结果报告说明契约变化与回归证据。

## 2.5 轮次与执行纪律

25. **任务范围优先**：治理和审计由实际风险或用户任务触发，不为凑固定轮次插入无关改动。

26. **新规则必须配测试**：2.3 节每新增一条硬约束，同一轮或下一轮必须补一个自动化测试；没有测试的约束降级为「建议」，不列入 2.3 节。

27. **轮次与队列跨树唯一**：开工先运行 `维护记录/基准脚本/round_claim.py next` 领取轮次，有匹配队列任务时再 `claim <队列ID> --owner <署名>`，没有则记录无对应 ID，不冒领无关任务。轮次计数器与唯一可写队列 `<git common-dir>/maintenance-queue.json` 共用认领锁；首次访问按全部 worktree 副本合并种子，之后不再种子。工作树内 `维护记录/任务队列.json` 仅为自动导出的只读快照，禁止手工编辑快照。默认租约 60 分钟，他人的有效租约不得覆盖；无法继续时 `release <队列ID> --owner <署名>`，完成时 `complete`，查看用 `show`，一致性检查用 `validate`。每轮结束检查 `N == M + 1`（N 为 project_status.md 当前轮次，M 为最新结果文件轮次）。

    不连续时，本轮必须先修正编号再继续。**轮的定义**：一轮＝一个可独立回滚的完整变更集。同类改动必须批量成轮（如 UI 卡片迁移按页面一次 ≥5 处），禁止一卡一轮、一字段一轮。

    **全量触发条件**：统一见 §5；计数行为以 `run_selftests.full_safe_required()` 与 `tests/architecture/test_round_baselines.py` 为核对依据，不在本节重复设置周期。

    **并行硬规则**：同一时刻活跃 `codex/*` 车道默认 1 条，经用户同意可升到 2 条（上限 2；冻结期内只有主树可提交）；一个队列 id 全局只允许一条线持有（权威队列＝Git common-dir/`maintenance-queue.json`，工作树内为只读快照）；分支 ahead>10 必须先回合或 rebase，否则 `round_claim.py next` 拒绝领号；detached HEAD 工作树不得开工；分支 behind>20 或 ahead=0 且 48 小时无活动即列入待回收。回收前保存未提交内容、核验活跃租约；用 `维护记录/基准脚本/worktree_ledger.py --plan` 生成计划，删除须用户逐条确认，台账不自动删除。

    **检查点**：认领因脏树拒绝时，先区分本轮改动与用户既有改动；只对授权文件建立可恢复检查点。创建分支本身不保存未提交内容，不得把用户改动混入 WIP 提交。大规模跨文件修改应分阶段建立检查点，检查点不等于任务完成。

28. **一个动作一个入口**：新增功能前必须先搜「已有入口能复用吗？」。本轮范围内存在重复入口时，先核验消费者与兼容要求，再统一；范围外重复项仅记录，不直接删除。

29. **三个基线数**：每轮结束必须报告：

    - 默认冒烟：当前基线 8/8
    - 架构门禁：记录当轮实际总数、失败集合及改前后比较；历史绿色结果不等于当前树通过。
    - 全量回归与欠账：唯一权威是 Git common-dir 的 `full-safe-receipts.json` 中真实 `{tree, round, seconds, at}`；`维护记录/测试分层基线.json` 不保存也不回退全量轮次或内容树。触发与凭据有效期见 §5。

30. **桌面主动后台任务**：`Desktop.async_()` 的提交、逻辑取消、成功／失败收尾与迟到结果拒绝必须经 `BackgroundTaskLifecycle`；取消不强杀任意 Python 线程，但已取消或被新代次替换的结果不得触发 UI 回调。

30a. **欠账如实记录**：本轮产生的欠账须在授权范围内闭环；历史欠账先核验影响，不能为了减少条目而删除记录或擅自扩大任务。完成判定见 §8。

32. 连续两次修复未解决同一问题时，先补充复现、堆栈或测量证据并重新诊断，再继续修复；不盲目重复同一补丁，不因重试次数而跳过任务。范围和阻塞处理见 §8。

33. 启动路径上禁止递归扫描目录：窗口出现到可交互之间不得 rglob / walk 任何目录。文件列表必须来自缓存、后台线程加载后更新，或明确懒加载（用户点某个按钮时才扫）。
34. **UI 设计唯一权威**：`design_tokens.md` 与 `ui_components.md`。所有 `padx` / `pady`、颜色、字号、圆角必须从 token 取值，禁止魔法数字与内联 hex；Reviewer 每轮必查。

## 2.6 Git 提交门禁

35. 每轮通过基线、写完结果文件且凭据形态扫描未命中后，执行一次收尾 `git add` + `git commit`；不得把私有数据、日志或用户项目内容纳入暂存区。
36. 收尾提交信息以轮次号开头，例如 `R745: 说明`；在 `[TASK_FAILED]` 或 `[TASK_BLOCKED]` 时可保留诊断性检查点提交，且必须以 `R745-FAIL:` 开头。
37. 提交前必须检查 `git status` 与暂存清单；命中凭据形态或受忽略运行路径即拒绝提交，并在结果文件记录阻断原因。
38. 禁止 `git push`，除非用户明确要求。
39. 用户要求回滚时，Codex 优先用 `git revert` 保留历史，而非 `git reset --hard`。
40. 每轮结果文件 `tasks_round_N_result.md` 中记录本轮是否已提交，以及 commit hash（若已提交）。
41. 协作 hooks 源码位于 `维护记录/基准脚本/hooks/`；每个工作树初始化后运行 `维护记录/基准脚本/install_git_hooks.py` 安装到共享 Git hooks。提交包含非默认文档的 `程序/` 文件时，必须显式设置 `CODEX_STAGE_ALLOWLIST`（分号分隔 repo 相对路径）；禁止用 `git add -A` 绕过最小暂存清单。仅 master 可提交 `project_status.md`。

    非 master 分支／worktree 也不得写 `.agent-handoff/backlog.md` 与 `.agent-handoff/snapshot.md`；分支记录只写 `程序/tasks_round/tasks_round_<n>_result.md`，合入 master 后单独提交一次补进 `project_status.md`（提交信息 `R<n>: 补记分支 <分支名> 的轮次记录`）。

    合并时上述共享状态文件不得整块取一边，必须保留双方全部记录；合并提交后把下列命令的原始输出贴进结果文件，只写「已解决冲突」不算通过——第一条输出必须为空，第二条轮次号必须是两边的并集：

    - `git diff <合并前master>..HEAD -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'`（表头「当前轮次」行每轮都会改，故排除）
    - `git show HEAD:程序/project_status.md | grep -oE '^R[0-9]+' | sort -u`

## 3. 轮次类型

每轮开工前先声明轮次类型，不同类型走不同协议。

### 3.1 功能轮（默认）

适用：新增功能、扩展现有功能。

- 只改本轮任务涉及的模块；不改分层、契约或权威源。
- 完成后跑 `smoke_test.py --affected <模块>`。
- 越界依赖须回退，自审见 §4。

### 3.2 修复轮

适用：修 bug、修偶发红、修阻塞。

- 先定位根因，输出复现步骤。
- 只改根因所在模块，不许顺手重构；测试契约按 §2.4，自审见 §4。

失败回归导致产品或测试资产修复时，一律归类为**修复轮（含全量基线验证）**，遵守根因、最小改动与同类问题复核要求；全量只是验证范围。仅记录、复核或更新基线而未修复资产时，归类为 §3.10 **验证/基线轮**；报告和状态台账不得使用“回归修复／基线轮”等未定义组合类型。

### 3.3 结构治理轮

适用：合并重复、收口路径、拆循环、删僵尸。

- 禁止加功能或改用户数据；每次最多改 3 个模块。
- 自检统一按 §5。只读诊断与执行分别适用该节的例外和验证表，不在本节另设全量周期。
- SKILL 说明文件（`skills/**/*.md`）改动不得与代码改动同轮：`run_selftests.py` 的 `data_moved` 判定会让增量台账整表失效。
- 更新 `architecture.md`，结果写 `tasks_round/tasks_round_N_result.md`。
- 结构治理轮分两个子场景，开工前必须由用户明确指定：

  **只读诊断**：扫描结构，输出含 A-M 的新报告，末尾必须含 J 整改路线、K 测试迁移计划；写入边界按 §3.5，验证按 §5。

  **执行**：读指定报告的 J/K，执行其中一条，写明来源报告路径与条目编号。用户未指定子场景时，必须先反问："本轮是只读诊断，还是按某份报告执行？"，禁止自行假设。

### 3.4 契约轮

适用：只改 L0 契约层。仅审计、核对或记录 L0 契约而未修改实现时，也归类为**契约轮**并遵守本节全部要求；报告和状态台账不得使用“契约复核轮”等未定义组合类型。

- 只改 `pet_bus` / `script_contract` / `asset_contract` / `stage_layout` / `storyboard_paths`。
- 不动 L1 以上。
- 跑全量自检。
- 更新 `AGENTS.md` 硬约束与 `architecture.md`。

### 3.5 只读诊断轮

适用：只诊断，不改代码。

- 禁止修改任何 `.py`。
- 禁止搬目录、重命名、删文件。
- 仅新增未占用的 `tasks_round/tasks_round_N_result.md`；不得覆盖历史结果。轮次元数据例外仅限：经规则 27 入口认领／完成中央队列并导出快照、同步状态页轮次头为最新报告号加一；不改状态正文，不把诊断结论记为修复完成。人工待办勾选须有对应诊断任务已完成的证据及用户授权。
- 用户明确要求“任何文件不改”或更窄的写入范围时，先说明与轮次归档的冲突并请求明确范围；不自行使用上述例外。普通只读问答（如查看 git status）不自动立轮、认领或写报告。
- 等确认后再进入修复。

### 3.6 测试搬家轮

- **适用场景**：迁移、重命名或归档测试文件与测试目录。
- **边界**：仅调整测试组织、测试收集和关联导入；不借机修改产品行为。
- **验收**：测试收集、导入路径和所有引用已同步；无双份测试或伪迁移，定向测试、默认冒烟及完整安全全量均通过。

### 3.7 性能/资源轮

- **适用场景**：处理速度、内存、磁盘、并发、缓存或资源释放出现瓶颈时。
- **边界**：以可复现的基线和目标为依据；不以牺牲产物正确性、可恢复性或用户数据安全换取指标。
- **验收**：记录测量条件、改前后指标和资源边界；相关定向验证与默认冒烟通过。

### 3.8 可靠性/数据迁移轮

- **适用场景**：数据结构、持久化格式、迁移逻辑、恢复路径或异常处理需要变更时。
- **边界**：必须保持旧数据可读、迁移可重复或可恢复；不得静默丢弃用户数据。
- **验收**：覆盖迁移前后、失败恢复和旧数据兼容的验证；必要时运行跨层全量安全自检。

### 3.9 兼容/平台适配轮

- **适用场景**：Windows 平台差异、路径/编码、外部工具版本或运行环境兼容需要处理时。
- **边界**：不改变既有主平台行为；平台分支集中在适配边界，不向业务层扩散。
- **验收**：目标平台验证通过，路径与编码约束符合权威服务，默认冒烟通过。

### 3.10 验证/基线轮

- **适用场景**：建立、复核或更新测试、架构、性能等质量基线时。
- **边界**：只验证、记录和必要的测试资产维护；不混入无关功能改动。
- **验收**：记录命令、环境、结果及与既有基线的差异；失败项有可追踪结论。

### 3.11 状态接续轮

- **适用场景**：跨轮恢复工作、整理完成事实或按协议更新项目状态时。
- **边界**：只依据仓库事实、验证结果和已存在报告；不得把推测写成已完成事项。
- **验收**：`project_status.md` 与结果报告的轮次、文件范围、验证状态一致，且遵守用户约定的更新节奏。

## 4. 双角色工作模式

### 4.1 Executor（默认）

完成 §0 阅读，声明 §3 轮次类型和文件范围，按 §8 持续执行；交付修改摘要、验证结果与未解决项，不贴完整差异。

### 4.2 自审清单（每次 Executor 完成后执行）

必审四条：

1. 本轮任务是否满足验收标准？
2. 是否改了范围外的文件？
3. 是否按 §5 完成适用验证，并区分未运行、历史凭据与本轮实测？
4. 是否引入了新的代码问题？

追加审（按轮次类型）：

- 功能轮：本轮是否新增了越界依赖？
- 修复轮：是否有同类 bug 未修？
- 结构治理轮：是否违反「每次最多改 3 个模块」？
- 契约轮：是否只动了 L0？
- 只读诊断轮：是否符合 §3.5 的报告和轮次元数据边界，且没有覆盖历史结果或修改生产代码／用户数据？

输出审查报告：通过 / 不通过 + 理由；自审清单通过才算完成。

## 5. 自检规则

Animatic 阶段契约变更须覆盖 SG-A/SG-B、13 阶段顺序、旧编号目录只读兼容和发布失败回滚；层级表改动仍触发本节全量安全回归条件。

本节是测试触发规则的唯一文档定义。命令均使用 §1 指定的随附解释器。只读诊断（§3.3、§3.5）默认不跑测试，除非用户明确要求；以下“每轮”与结构治理扫描均指执行轮。

| 时机         | 命令                                      | 说明                                           |
| ---------- | --------------------------------------- | -------------------------------------------- |
| 每轮         | `python smoke_test.py`                  | 只跑本轮快速检查；失败后继续修复，不进入完成状态                             |
| 改动活跃逻辑     | `python smoke_test.py --affected <模块名>` | 只跑受影响测试模块，例如 `--affected idea_chat workflow` |
| 需要增量回归     | `python smoke_test.py --gate`           | 按台账串行执行改动过的测试文件                              |
| 结构治理轮      | `python smoke_test.py --architecture`   | 运行下列全部架构门禁；不只限于分层/循环/路径/删除                   |
| master 提交点：`last_full_safe_all_round` 之后累计 ≥ 8 个改过源码的轮次／路线图条目收口 | `run_selftests.py --all --safe` | 完整安全回归；分支不累计轮次欠账；计数口径与后台补跑见下方「全量欠账口径」 |
| 发布前／用户明确要求 | `run_selftests.py --all --safe`         | 完整安全回归；不通过先修复                                |
| 收尾时 | 核对 §2.5 轮次、认领与实际欠账 | 不伪造轮次或凭据；失败按 §8 继续处理 |

**全量欠账口径（R1439，用户批准）**：唯一实现是 `run_selftests.FULL_SAFE_ROUND_INTERVAL`（8）、`source_rounds_since()`、`full_safe_required()`。只数 `last_full_safe_all_round` 之后、提交标题为 `R<n>:`／`R<n>-FAIL:` 且改过源码的轮次；纯文档、测试、`tasks_round/`、`维护记录/`、`说明/` 的轮次不计（`skills/` 下的 md 是 SKILL 源，计入）；读不出 git 历史时退回按全部轮次计。本节所列风险触发不受阈值影响：启动入口（`启动漫剧制作助手.pyw`／`启动助手.cmd`）、`storage_maintenance.py`（删除语义）、`tests/architecture/_layers.py`（层级登记表）由 `has_risk_change()` 按路径自动判定，任一轮改过就**立即触发后台补跑**，但门禁有宽限（`FULL_SAFE_RISK_GRACE`＝3）：自最早一次风险改动之后再积累 3 个源码轮次仍无凭据才报红，连续几轮改启动文件合并成一次全量（`risk_overdue()`）；Tk 控件生命周期（销毁／重建）无法静态判定，仍由执行者人工判断并手动跑全量。

**后台自动补跑**（带防抖）：欠账达到门禁线前 `FULL_SAFE_AUTO_LEAD`（2）个源码轮次，master 的 git post-commit 钩子（`维护记录/基准脚本/hooks/post-commit`，由 `install_git_hooks.py` 安装）调用 `scripts/auto_full_safe.py --spawn`，先起一个后台等待者（`--wait-run`，同一时刻只有一个）：等「安静」15 分钟（期间每有新提交就重新计时）再跑一次，连续拆分系列的 N 轮只补跑 1 次；欠账已让门禁报红或等满 60 分钟则立即跑。跑时在根目录 `.wt/ci` 干净分离检出上后台跑 `--all --safe`，绿凭据写入 common-dir 的 `full-safe-receipts.json`，日志在 `程序/logs/auto_full_safe.log`。钩子失败或已有同类任务在跑都静默跳过，不阻塞提交；后台运行期间（`auto_full_running()`）架构门禁不报「欠全量」，手动 `--all --safe` 也会被拒绝并提示等待（`--force` 可强制）——**欠账红灯出现时不要立刻手动跑全量，先看后台是否已在补跑**；`scripts/auto_full_safe.py --status` 查看欠账。后台全量红了不会自动改任何文件，按 §8 失败处置人工接续；结果写入 common-dir 的 `auto-full-safe-result.json`，post-commit 钩子每次提交先跑 `--notice`，上次未通过就在提交输出里打印红的测试文件与日志路径，`--status` 也会显示。`round_claim.py next` 领号时会自检 git 钩子，缺失或与版本受控源不一致就自动安装，新克隆无需手工装钩子。

纯服务或小拆分另跑 `run_selftests.py -k <本轮改动模块>`；文档整理跑文档一致性回归。跨层改动仍须覆盖架构门禁；运行全量时按下述去重规则执行。

合并到 master 前的当次全量升级条件：启动路径（`启动漫剧制作助手.pyw`／`启动助手.cmd`）、Tk 控件生命周期（销毁/重建，不含普通事件绑定）、删除语义（`storage_maintenance.py`）、层级登记表（`tests/architecture/_layers.py`）改动。仅替换 `desktop.py` 的注入点且未改变 Tk 控件生命周期，不单独触发升级。

全量成功凭据记录 `{tree, round, seconds, at}`，由现有执行器写入 common-dir 的 `full-safe-receipts.json`；七日内同 `HEAD:程序` 内容树可复用真实绿凭据。不得以文档数字代替或伪造凭据。当前实测与历史绿色记录分开列于 `project_status.md` 的“验证基线”；失败处置见 §8，检查点提交见 §2.6。

当前架构门禁清单（`tests/architecture/`）：总数以 `python smoke_test.py --architecture` 当轮输出为准，基线只增不减。

- 卡片与忙碌状态补充：`test_card_boundary.py`、`test_busy_state_boundary.py`。
- 分层与一致性：`test_agents_md.py`、`test_layers.py`、`test_no_circular_import.py`、`test_path_authority.py`、`test_stage_paths.py`、`test_storyboard_edit_boundary.py`、`test_storyboard_final_selection_boundary.py`。
- 写入与删除边界：`test_atomic_write_boundary.py`、`test_asset_batch_ledger_boundary.py`、`test_asset_batch_settings_boundary.py`、`test_asset_detail_binding_boundary.py`、`test_asset_generated_import_boundary.py`、`test_asset_image_import_boundary.py`、`test_asset_plan_publication_boundary.py`、`test_asset_rename_boundary.py`、`test_asset_image_removal_boundary.py`、`test_asset_image_restore_boundary.py`、`test_audio_import_boundary.py`、`test_cloud_video_settings_boundary.py`、`test_continuity_publication_boundary.py`、`test_delivery_import_boundary.py`、`test_desktop_settings_boundary.py`、`test_edit_publication_boundary.py`、`test_final_bundle_boundary.py`、`test_handoff_publication_boundary.py`、`test_keyframe_delete_boundary.py`、`test_keyframe_restore_boundary.py`、`test_keyframe_replace_boundary.py`、`test_keyframe_reference_publication_boundary.py`、`test_legacy_adoption_boundary.py`、`test_local_video_settings_boundary.py`、`test_manual_creative_publication_boundary.py`、`test_previs_routing_publication_boundary.py`、`test_stage_workspace_boundary.py`、`test_structured_script_write_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_tts_publication_boundary.py`、`test_video_delete_boundary.py`、`test_video_options_boundary.py`、`test_video_prompt_publication_boundary.py`、`test_video_publication_boundary.py`、`test_white_model_import_boundary.py`、`test_writing_preparation_path_boundary.py`、`test_deletion_gateway.py`、`test_remove_authority.py`、`test_recycle_service.py`。
- 剧本重命名边界：`test_script_rename_boundary.py`。
- 阶段/UI 契约：`test_dynamic_import_registry.py`、`test_stage_command_contract.py`、`test_completion_gate.py`、`test_event_bus_boundary.py`、`test_skill_dependency_dag.py`、`test_pipeline_stage_io_contract.py`、`test_skill_reference_injection.py`、`test_project_entry_boundary.py`。
- 依赖与平台边界：`test_import_error_boundaries.py`、`test_model_provider_boundary.py`、`test_platform_opening.py`、`test_platform_process_boundary.py`、`test_migrated_ui_boundaries.py`。
- 体验与布局：`test_responsive_layout_contract.py`、`test_combobox_boundary.py`。
- 启动预算：`test_startup_budget.py`。
- 历史兼容门面：`test_legacy_facade_manifest.py`。
- 轮次与基线／测试卫生：`test_round_baselines.py`、`test_skip_hygiene.py`、`test_silent_exception_ratchet.py`、`test_module_size_ratchet.py`、`test_todo_comment_snapshot.py`、`test_static_hygiene.py`、`test_function_size_ratchet.py`。
- 覆盖率审计棘轮：`test_coverage_audit_ratchet.py`、`test_secret_sink_audit.py`。
  密钥静态审计仅覆盖有限函数内传播，支持范围与漏检／误报边界见 `tasks_round/tasks_round_1054_result.md` D–F，不将零命中解释为全路径安全。
- JSON／服务／统筹补充：`test_confirm_gates_json_boundary.py`、`test_context_menu_boundary.py`、`test_data_table_boundary.py`、`test_dialog_boundary.py`、`test_button_boundary.py`、`test_file_dialog_boundary.py`、`test_idea_attachment_publication_boundary.py`、`test_input_boundary.py`、`test_json_io_boundary.py`、`test_keyframe_batch_json_boundary.py`、`test_local_previs_json_boundary.py`、`test_notification_boundary.py`、`test_previs_automation_json_boundary.py`、`test_previs_batch_json_boundary.py`、`test_previs_monitor_json_boundary.py`、`test_project_context_boundary.py`、`test_service_return_contract.py`、`test_shortcut_registry_boundary.py`、`test_skill_orchestrator_json_boundary.py`、`test_stage_display_boundary.py`、`test_subtitle_export_publication_boundary.py`、`test_text_component_boundary.py`、`test_tooltip_boundary.py`、`test_ui_icons_boundary.py`、`test_scrollbar_theme_boundary.py`、`test_token_boundary.py`、`test_copy_entry_boundary.py`、`test_unification_ratchet.py`、`test_video_navigation_json_boundary.py`、`test_white_model_json_boundary.py`、`test_white_model_service_json_boundary.py`、`test_workflow_settings_json_boundary.py`、`test_writing_api_json_boundary.py`、`test_writing_publication_boundary.py`。

新增或删除架构测试时，必须在同一轮更新以上清单、架构基线和结果报告；不得只更新测试而遗漏本入口说明。

- 架构门禁去重：跑 `run_selftests.py --all --safe` 的那一轮，`--all` 已含架构门禁，不再单独跑 `smoke_test.py --architecture`；只跑架构门禁的轮次不变。
- 失败复验走增量：全量失败后，先用 `--affected`／`-k` 在定向层面修到绿，再复验全量；禁止把全量当排错工具反复兜底。

## 6. 进度播报前缀

前缀事实来源为 `broadcaster.PREFIX_PATTERNS`，阶段分母由 `Broadcaster.stage()` 从 `pet_bus.STAGES` 生成。以下是当前展示格式，不是第二套定义：

`【阶段 X/13】`、`【步骤 Y/Z】`、`【门禁】`、`【警告】`、`【阻塞】`、`【完成】`、`【恢复】`、`【下一阶段】`、`【模式】`

无前缀消息会被拒绝。

## 7. 每轮结束时

1. 每轮按规则 27 领取编号并新增结果；状态页轮次头同步为最新结果轮次加一，正文按用户协议或每五个实际轮次整理。只读诊断禁止覆盖既有结果编号；用户另有限制时先记录冲突，不擅自扩大写入范围。
2. 结果文件位置为 `程序/tasks_round/tasks_round_N_result.md`（相对程序工作目录为 `tasks_round/`）。
3. 每轮结束必须回答三个问题，写进 `tasks_round_N_result.md` 开头:
   - 本轮属于 §3 哪种类型？
   - 测试跑了吗？三个基线过了吗？
   - project_status.md 的欠账少了吗？
4. 按 §2.6 收尾提交；`升级备份/` 与 `.bak_*` 保留为历史证据，Git 承担后续回滚，今后不再新增 `.bak_*`。

## 8. 任务执行协议

1. **持续执行直至完成**：每个任务必须持续推进，直到满足当前用户请求和全部适用验收条件，才可标记 `[TASK_COMPLETE]` 并正常收尾。只写出代码、提交检查点、部分测试通过或报告失败均不等于完成。
2. **失败闭环**：按“定位原因 → 最小修复 → 复测失败项 → 适用回归”循环处理；仍有安全、有效且在授权范围内的下一步时，继续执行，不因重试次数、工作耗时或一次失败而跳过任务、交还用户或自动转向其他待办。连续失败先按规则 32 补证据。
3. **完成标准**：交付物满足请求，§5 的适用检查通过，§4 自审通过，§7 的报告／状态／提交要求完成；未运行或阻塞的必要检查不能写成通过。只读任务按其授权的检查和报告验收，不强制实施修复。
4. **真实阻塞例外**：用户明确要求停止，或继续必须获得新授权、凭据、外部服务恢复、用户选择，或存在无法安全绕过的环境限制时，可暂停。暂停前穷尽安全的范围内检查和替代路径，保存可恢复状态，明确阻塞证据、已尝试方案及所需的最小用户动作。不得绕过权限、删除用户改动或扩大改动范围以追求成功。
5. **状态真实**：只有第 3 条全部满足才输出 `[TASK_COMPLETE]`。真实阻塞输出 `[TASK_BLOCKED]`，明确任务尚未完成；`[TASK_FAILED]` 仅表示实测失败，不是“跳过并结束”的许可。不得伪造结果、降低门槛、删除失败断言或冒用历史绿色凭据。
6. **范围不扩张**：持续执行只针对当前任务。新发现的范围外缺陷记录影响；修复需要扩大范围时先请求授权。历史欠账如确实阻断当前验收，按第 4 条处理，不把欠账自动标成已解决。

## 9. 上下文与接力

上下文不足或执行被中断时，记录目标、已改文件、实际验证、阻塞和下一条安全操作，遵循根目录接力协议；压缩上下文不代表任务完成。新会话只按 §0 恢复，不重复另设阅读顺序。
