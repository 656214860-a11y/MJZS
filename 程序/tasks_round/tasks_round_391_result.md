# Round 391 — AGENTS 治理差异只读诊断

范围：只读核对 `AGENTS.md`、`project_status.md`、`architecture.md`、`PROJECT_MAP.md` 与静态调用点；未修改 `.py`、`project_status.md`、`architecture.md` 或既有轮次结果。用户指定的 `tasks_round_386_result.md` 已存在且记录 R386 历史实现，故本报告使用未占用编号 R391，避免覆盖审计轨迹。

## 1. 已过时

1. **每轮都更新状态**：AGENTS 2.1.7、7.1 要求每轮更新 `project_status.md`；当前实际执行约定为每完成五轮更新一次，状态已记录 R385、R390 两次批次接续。证据：`project_status.md:3,68-69`。应改为“每轮写结果；状态按任务约定或每五个实际轮次更新”。
2. **结构治理必须全量自检**：AGENTS 3.3 要求每次结构治理均执行 `run_selftests.py --all --safe`，但状态明确“发布前或用户明确要求才运行全量”；日常以默认冒烟和定向测试为准。证据：`AGENTS.md:139` 对 `project_status.md:38-43`。应按风险分级，不将只读或纯函数拆分强制升级为全量 Tk 回归。
3. **删除白名单已失真**：AGENTS 2.3.14 仅列四个白名单模块；实际回收已集中于 `storage_maintenance.recycle_paths`，并被 `projects.py`、`desktop.py`、`asset_batch_state_service.py`、`storyboard_recycle_service` 等受控调用。证据：`storage_maintenance.py:47` 及静态调用点。应以“唯一回收服务 + 受控适配入口”替代模块白名单。
4. **结构治理轮的强制用户反问与自动执行不协调**：AGENTS 3.3 要求用户未指定子场景就反问；当前项目状态和用户授权允许串行自动推进，且本轮用户已直接指定“只读诊断”。证据：`AGENTS.md:149-151`、本轮任务。应只在轮次类型不明且会改变写入范围时询问。
5. **上下文规则会强制改状态文件**：AGENTS 9 要求上下文过半即更新 `project_status.md`；这与只读诊断、不改状态文件相冲突。证据：`AGENTS.md:258` 与 3.5/本轮禁止项。应改为“需要接续时写上下文摘要；仅在任务协议允许时更新状态”。
6. **项目地图的旧描述未被 AGENTS 指出为待校正**：`PROJECT_MAP.md` 仍称“11 阶段页面/11 阶段目录”，实际阶段为 12，AGENTS 已写 12。证据：`PROJECT_MAP.md:8,17` 对 `AGENTS.md:29-31`、`architecture.md` 第 4 节。AGENTS 应要求修改地图时同步核验阶段数和目录表。

## 2. 已落地但未写进 AGENTS.md

1. **唯一阶段命令入口**：`stage_handler_registry.start()` 已是三虎启动唯一入口；AGENTS 未列为硬约束。证据：`architecture.md:62,180`，`desktop.py:2251,2347`。
2. **动态 UI 加载登记表**：UI 延迟加载只能走 `ui_plugin_registry.module()`，登记外名称被拒绝；AGENTS 仅泛称分层，未写唯一入口。证据：`architecture.md:63`，`app.py:244,253`、`desktop.py` 多处调用。
3. **阶段路径服务**：`stage_path_service` 是“新写/旧读”的唯一阶段路径口径；AGENTS 的路径表未把它列为唯一入口。证据：`architecture.md:59`，`script_contract.py:137,292,328,489`。
4. **无 Tk 的业务拆分**：`storyboard_catalog_service`、`storyboard_rows_service`、`asset_batch_service`、`previs_routing`、`handoff_service`、`edit_service`、`final_service`、`storyboard_adoption_service` 已承担对应决策。证据：`architecture.md:61`。
5. **阶段完成核验服务**：`stage_completion_service` 已在 L3，完成由产物核验驱动；AGENTS 未把“不得由 Agent 口头完成”写为硬约束。证据：`architecture.md:62`、`project_status.md` 当前能力/优化清单描述。
6. **测试与性能台账服务**：`pet_test_service`、`pet_performance_service` 及其项目内脱敏台账已落地。证据：`architecture.md` 模型路由配置表，`project_status.md:69,80-94`。

## 3. 缺失的硬约束

1. **动态导入唯一入口**：UI/L4 的按需模块必须经 `ui_plugin_registry.module()`，禁止页面直接 `importlib.import_module()` 或裸延迟导入；需配架构静态门禁测试。
2. **阶段启动唯一入口**：三虎、手动和自动阶段启动均经 `stage_handler_registry.start()`；直接从 UI 调 L2/L3 的阶段实现禁止。已有 `tests/test_stage_command_contract.py`，应升为 AGENTS 约束。
3. **阶段路径新写/旧读规则**：所有新写路径由 `stage_path_service.write_dir()`/阶段契约产生；旧目录仅由 `read_dirs()`/别名只读兼容，禁止新建旧目录。证据：`architecture.md:59`、`PROJECT_MAP.md` 旧目录说明。
4. **完成事件以产物核验为准**：完成、自动推进和阶段状态必须经 `stage_completion_service`/相应产物核验，不接受模型文字或 UI 成功提示作为完成证据。
5. **跨层边界**：L4 仅构建控件与注入回调；L2 服务不得导入 Tk/配置页面；L3 不持有 Tk 控件。证据：`architecture.md:61-63`。应配层级和禁止导入门禁。
6. **回收服务唯一性**：用户可见删除统一经 `storage_maintenance.recycle_paths()` 或明确的 `storyboard_recycle_service`，并保留影响范围/恢复信息；禁止按旧白名单直接删除。
7. **诊断数据最小化**：模型、测试、性能诊断只存白名单元数据/脱敏摘要，不存提示词、正文、推理正文、密钥或完整子进程输出。证据：`architecture.md` 模型路由表、`project_status.md:80-94`。

## 4. 缺失的轮次类型

1. **性能/资源轮**：缓存、增量加载、后台扫描、基准比较；要求可比基准和无用户数据副作用。仅改文档，测试为定向基准契约。
2. **可靠性/数据迁移轮**：原子发布、恢复、回收、索引一致性；要求中断/损坏/并发用例。文档和测试均需。
3. **兼容/平台适配轮**：Windows/本地软件/可选依赖的适配和可操作降级；要求跨平台静态门禁与适配器测试。文档和测试均需。
4. **验证/基线轮**：只刷新经过授权的全量、架构或性能证据，不改产品逻辑；写入基线的职责和回滚规则需文档化。
5. **状态接续轮**：仅合并已完成若干轮的状态/结果索引；禁止伪称功能或结构实现。文档即可。
6. **只读诊断轮补充协议**：现有类型应明确“允许新增未占用报告文件；不得覆盖既有 `tasks_round` 结果；无需运行冒烟，除非用户明确要求”。

## 5. 缺失的自检基线

1. **架构基线**：`smoke_test.py --architecture` 14/14、7.584 秒，覆盖删除、动态导入、层级、模型边界、循环、路径、平台和阶段路径。证据：`project_status.md:40-41`；AGENTS 5 节未记录数量/覆盖面。
2. **默认冒烟基线**：项目内置 Python 的 `smoke_test.py` 最近 8/8。证据：`project_status.md:43,68`；AGENTS 仅给命令，未写通过口径与解释器。
3. **安全全量基线**：`run_selftests.py --all --safe --jobs 6` 为 115 文件、2,942 用例、831.3 秒、0 失败文件。证据：`project_status.md:38-39`；AGENTS 未记录基线、参数或“发布前/明确授权”触发条件。
4. **分层基线**：服务、短生命周期 GUI、端到端 GUI 的分层策略已在优化清单/状态中落地；AGENTS 应说明 GUI 不能并行堆叠窗口，并列出 `--safe` 的原因。

## 6. 禁止事项需更新

1. **“不跳过 Reviewer”**：当前并无独立 Reviewer 自动化实体；应改为“交付前执行同一轮自审清单”，避免承诺不存在的工作流。仅文档。
2. **“所有脚本用 Python，禁止 shell”**：作为产品脚本规范可保留，但不应禁止诊断/自动化环境使用受控 shell 命令；应限定为“产品交付脚本不引入 shell 依赖”。仅文档。
3. **“不一次改完所有文件，按最小改动提交”**：项目不以提交作为每轮交付单位；改为“最小必要文件集，避免无关改动”，去掉隐含 Git 提交要求。仅文档。
4. **“不直接 rmtree 用户数据”**：应扩展为“所有用户可见删除走回收服务；临时文件、缓存和已验证的本轮临时产物可受控清理”，以免阻断原子写入器的临时文件清理。文档；回收/临时清理测试保持。
5. **“不把旧目录搬运到新目录（只做目录联接）”**：当前权威规则是“旧目录只读兼容、新写入阶段路径服务”，不应要求“目录联接”这一未在架构中定义的机制。仅文档。

## 7. 建议的修订方案

| 优先级 | 修订 | 文档/测试 |
| --- | --- | --- |
| P0 | 在 AGENTS 2.2/2.3 增加 `stage_path_service`、`stage_handler_registry.start()`、`ui_plugin_registry.module()`、产物核验完成和回收服务五项唯一约束。 | 文档 + 复用既有架构/阶段命令测试；缺少静态门禁时补测试。 |
| P0 | 将轮次状态规则改为“每轮结果文件；状态按用户协议或每五轮批次更新”，并为只读轮禁止覆盖既有结果编号。 | 文档。 |
| P1 | 将删除白名单改为回收服务接口与允许的临时/缓存清理边界。 | 文档 + 回收服务测试。 |
| P1 | 将结构治理测试改为风险分级：只读不跑；纯服务/小拆分跑定向+默认冒烟；跨层或发布前才跑全量安全自检。 | 文档；复用现有测试分层。 |
| P1 | 增加性能、可靠性/迁移、平台适配、验证/基线、状态接续五种轮次类型。 | 文档；其中前三类给出必需测试。 |
| P2 | 修正 `PROJECT_MAP.md` 中“11 阶段”遗留文字，并规定地图、架构、AGENTS 的阶段数同步检查。 | 文档 + 可选静态一致性测试。 |
| P2 | 将 Reviewer 改为可执行的自审清单，并修订 shell、Git 提交、旧目录联接等表述。 | 文档。 |

## 自审

- 只读诊断范围满足：未修改 `.py`、`project_status.md`、`architecture.md` 或已有 R386 结果。
- 本报告是唯一新增文件；未运行测试，因为本轮没有产品或测试代码改动，且用户要求只读诊断。
