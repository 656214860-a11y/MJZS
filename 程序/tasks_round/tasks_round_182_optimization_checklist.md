# 漫剧制作助手优化清单（第 182 轮）

状态标记：`[x]` 已有自动验证；`[ ]` 待实施或待全量验证。优先级以数据安全、错误交付和流程阻塞为先。

## P0：稳定性、可靠性与数据管理

- [ ] 为每个阶段写入建立“临时文件 → 内容校验 → 原子替换 → 索引更新”统一服务；禁止 UI、Agent 或模型回调直接写正式成果。
  - 验收：进程中断、模型空响应或磁盘错误后，不出现半份 JSON/Markdown，也不把阶段标为完成。
  - 本轮增量：统一写入器和行尾校验器都使用每次唯一的同目录临时文件；字幕、阶段配置、
    资产与模型诊断并发保存不会争用固定 `.tmp`。`tests.test_line_endings`、
    `tests.test_subtitles`、`tests.test_engine_probe` 共 70 条、0 失败。仍有独立工具与旧写入点待逐一迁移，故总项保持未完成。
  - 本轮补充：白模渲染进度 `previs_progress.publish()` 也已改由 `agent.core.save_text()` 写入，
    不再自行维护临时文件与替换逻辑。`tests.test_previs`、`tests.test_stdlib_closure` 共 49 条、
    2.459 秒、0 失败。
  - 本轮补充：模型池 `.env` 与本机加密密钥写入改用 `agent.core.temporary_path()` / `replace()`，
    避免并发保存争用固定 `.tmp`。`tests.test_model_pool`、`tests.test_pet_llm` 共 109 条、
    0.388 秒、0 失败。
  - 本轮补充：Qwen／通用后台引擎的原始模型响应先写唯一临时文件、完成 JSON 解析后才发布
    `*.response.json`；损坏响应不会覆盖上一次可诊断响应。云端与本地视频下载也统一使用
    `replace()` 的 Windows 读锁重试，并清理本轮临时下载。`tests.test_force_quit`、
    `tests.test_engine_probe`、`tests.test_workflow` 共 108 条，`tests.test_core`、视频相关
    测试共 158 条，均为 0 失败。
  - R512：`skill_tools` 的字幕生成目标已改为委派 `subtitle_export_service.publish_srt_text`，由服务统一执行行尾校验与原子发布；其余阶段迁移仍待继续。
- [x] 自然剧本、结构剧本、分镜初稿、分镜定稿均已建立可追溯来源关系；删除上游文件会隐藏下游候选而非继续展示孤儿文件。
  - 验收：任一列表只展示存在、归属正确、类型匹配的文件。
  - 当前实现：自然剧本 → 结构剧本通过 `产物来源关系.json` 记录项目相对来源路径和哈希；结构列表优先按账本验证来源。分镜草稿以 `source_script` 为权威；分镜定稿在生成或复用时记录其稳定结构剧本来源（而非会被归档的草稿 JSON），来源消失时从候选列表隐藏。`tests.test_file_cache`、`tests.test_workflow`、`tests.test_final_viewer` 共 104 条通过。
- [x] 分镜规范化归档使用回收站而非永久删除，并修复项目相对/绝对路径比较导致“已移动却报告未移动”的问题。
  - 验收：`tests.test_final_viewer` 覆盖改名、别名追踪和下次保存。
- [x] 在当前全部文本模型入口记录 request ID、模型 ID、finish_reason、推理字段长度、正文长度和脱敏后的错误分类。
  - 验收：DeepSeek 空正文能区分配置、协议、上下文、推理耗尽和模型无正文，而不是只显示“调用失败”。
  - 当前实现：剧本直连、HOLLMWOOD 七角色步骤和三虎意图模型均写入项目 `model_diagnostics/` 的原子 JSON 事件；事件只含白名单协议元数据，绝不保存提示词、正文、推理正文或密钥。兼容模型响应会在诊断服务内提取结构字段，避免各入口重复解析。
- [x] 所有自动化阶段完成事件必须由已验证的产物驱动，不能由 Agent 的口头“完成”驱动。
  - 验收：分镜 JSON 未生成或未采用时，三虎不能显示“初步分镜已完成”。
  - 当前实现：统一完成出口会分别核验自然/结构剧本、已采用分镜、资产、连贯性、首帧、白模、
    已验收视频、音频、剪辑和交付文件；缺少成果一律转为 `stage.paused`。手工完成、下载剧本和
    编排器路径同样先走核验，不能绕过自动链门禁。

## P0：架构与设计

- [ ] 继续拆分 `desktop.py`、`storyboard_files.py`、`asset_batch.py`：视图只绑定控件，服务只处理业务，适配器只负责 Tk/进程/网络。
  - 验收：领域服务可不创建 Tk 窗口而单独运行；架构门禁无越层依赖和大型循环依赖。
  - 本轮增量：`storyboard_catalog_service` 已成为目录发现与轮询指纹的唯一安全遍历入口；
    剧本准备页的“项目设定／项目大纲／项目剧本”发现也已抽至无 Tk 的
    `script_workspace_service.discover_script_documents()`，`desktop.py` 只负责表格渲染和交互。
    `tests.test_script_workspace_service` 与平台、兼容、预演相关测试共 49 条、0.670 秒、0 失败，
    且 `desktop.py`、新服务均已编译。
    `storyboard_files.catalog()` 和 `storyboard_selection.tree_signature()` 不再各自 `os.walk`。
    `asset_batch.py` 的提示词、图片登记和批量完成判定已改为委派
    `asset_batch_service`，避免 GUI 与服务各维护一套规则。批处理台账、未知提交恢复、未登记原图
    回收和资产落盘判定进一步迁至无 Tk 的 `asset_batch_state_service`；`asset_batch.py` 仅保留
    窗口编排与兼容导出。`tests.test_assets` 60 条、0.729 秒、0 失败，架构门禁 13/13 通过。
    仍有 Tk 视图和资产批处理待继续拆分，故总项保持未完成。
  - 本轮补充：首帧页“当前／全部已采用分镜”的跨文件镜头发现、校验、跳过提示与同号镜头
    稳定行 ID 已移至无 Tk 的 `storyboard_rows_service`；`desktop.py` 只给出范围和状态回调。
    `tests.test_storyboard_rows_service` 2 条及三项首帧页面 GUI 回归通过。
- [x] 资产批处理和首帧批处理恢复通过 `native_apps` 宿主适配器调用 ComfyUI，底层执行留在无界面的 `comfy_runtime`。
  - 验收：`tests.test_assets`、`tests.test_keyframe_comfy` 均能替换宿主调用，不访问真实服务。
- [x] Qwen 后台适配器只依赖 `workflow_process_registry`，不反向导入工作流引擎。
  - 验收：`tests.architecture.test_no_circular_import` 与 `tests.test_force_quit` 分别验证无循环依赖、登记/销号/强制停止台账。
- [x] 收敛阶段路径为 `project_stages` / `stage_path_service` 的唯一权威；逐步删除硬编码的中英文旧目录兼容写入。
  - 验收：新项目仅写 `01剧本准备` 至 `12质检与交付`；旧 `writing` 等目录严格只读兼容，且兼容期在
    2027-03-31 后自动失效。阶段全量写入、未知阶段拒绝、旧路径只读与淘汰期限共 6 条契约测试通过。
- [x] 三虎只保留一个 L3 阶段命令入口；手动/自动模式共享同一个阶段状态机，差异只在触发权限。
  - 验收：切换自动模式能准确从当前已验证产物继续，不重复制作、不跨阶段调用。

## P1：代码质量与可维护性

- [x] 给每个阶段定义显式输入、输出、失败和恢复契约；把提示词、文件筛选和状态更新从页面构建代码中移出。
  - 验收：`stage_layout.STAGES` 同时生成 12 个阶段的用户 README、机器输入/输出目录和门禁说明；
    `stage_contract_report` 与运行时顺序交叉校验。L3 手动/自动命令共享输出和失败事件契约。
    `tests.test_stage_layout`、`tests.test_stage_command_contract`、`tests.test_stage_wiring` 共 40 条、
    7.678 秒、0 失败。
- [x] 将“旧接口兼容”集中到 facade 模块，标注调用方和淘汰日期，避免业务模块到处 `try/except ImportError`。
  - 已完成首段：`legacy_compat.py` 集中承接历史分镜别名与历史阶段名的只读解析，明确淘汰日期
    为 2027-03-31；`engine.py`、`confirm_gates.py` 和白模预演页已移除各自的内部 `ImportError` 兜底，
    可选工作流模型名也经该门面读取。`tests.test_legacy_compat`、`tests.test_previs`、
    `tests.test_platform_tools` 共 45 条、0.459 秒、0 失败。
    根目录生产模块的 `ImportError` 许可点现由 `tests.architecture.test_import_error_boundaries`
    固定为历史 facade、平台能力、解释器能力和阶段成果核验失败边界；新增业务模块不得自行捕获。
  - 本轮补充：剧本对话的 Provider／模型目录归属已改由
    `legacy_compat.optional_model_identity()` 统一解析，`idea_chat` 不再自行捕获模型池的
    `ImportError`。`tests.test_legacy_compat` 4 条、`tests.test_idea_chat` 58 条均通过。
- [ ] 清除巨型初始化表达式和多职责函数，优先治理计时器、自动流程、文件发现、模型调用四类热点。
  - 已完成首段：`storyboard_catalog_service.discover_files()` 承担无 Tk 的阶段目录扫描（链接逃逸、内部目录、空文件和命名过滤）；`storyboard_files.catalog()` 与 `storyboard_selection.tree_signature()` 仅保留领域筛选、列表状态和轻量指纹组装。`tests.test_storyboard_plan_service`、`tests.test_file_cache`、`tests.test_workflow` 共 96 条、2.654 秒、0 失败。
  - 已完成剧本准备文件发现拆分：`script_workspace_service` 固化三个可见分类、创意目录边界、扩展名过滤和排序；
    页面函数不再递归扫描项目目录。余下的对话、自动流程与按钮编排仍需继续拆分，故本项保持未完成。
  - 本轮补充：`Desktop` 的自动阶段队列、错误、阻塞、签名和消息队列初始值已收束到
    `_initialize_automation_state()`；构造流程改为逐项初始化窗口生命周期字段，不再依赖一条
    易漏字段的巨型表达式。`tests.test_asset_detail.AnchorTests` 与两条无人工自动链回归共 7 条通过，
    `desktop.py` 编译通过。
- [x] 为命名规则提供单一解析/生成器；禁止各页面用字符串切片自行判断“剧本/大纲/结构稿”。
  - 验收：`script_contract.stage_file_name()` 负责四段式生成，`stage_file_info()` 负责当前四段式和旧
    `项目_EP001_年月日` 的解析，并返回可见归类依据；剧本准备文件表直接调用它。`tests.test_script_structure`
    与 `tests.test_idea_chat` 共 72 条、27.322 秒、0 失败。

## P1：测试与质量保障

- [x] 将 GUI 测试分为无 Tk 单元测试、短生命周期 Tk 测试、端到端冒烟测试；禁止在同一进程堆叠多个桌面窗口测试。
  - `run_selftests.py` 的层级现为 `service`、`gui-short`、`gui-e2e`；后两类均需 `--safe`
    串行运行，端到端桌面模块采用显式登记，不能靠耗时猜测。`tests.test_selftests` 14 条、0 失败，
    `--list` 验证端到端层只包含 `test_pet_ui` 和 `test_ui_edges`。
- [x] 所有回归测试从程序根目录解析资源，不依赖测试文件所在目录；迁移后统一 `PROGRAM` 固定值。
  - 已迁移首帧来源、性能基准、三虎设置、三虎界面与行选择测试；同时以 `PAGE_OF` 取代首帧页的旧硬编码页码。
- [x] 已修复剧本流程替身不带 `canonical_id` 时的兼容问题，以及分镜归档零等待模式的回归。
- [x] 模型协议契约测试：OpenAI Chat、DeepSeek 兼容响应、空正文重试边界、`reasoning_content`、消息封装、8192 token 上限。
  - 验收：空正文仅导演/导演审核受控重试一次；Writer、Editor、Actor 及其修订均以 8192 请求且不盲目重试。
- [x] 本地分层门禁：静态架构门禁 → 纯服务单元测试 → GUI 冒烟；每层产出失败模块列表和耗时基线。
  - 验收：架构层 `smoke_test.py --architecture` 13/13 通过；服务层 `run_selftests.py --layer service --all --jobs 6`
    1,264 条、21.9 秒、0 失败；GUI 安全层 `run_selftests.py --layer gui --safe --all` 1,625 条、508.8 秒、
    0 失败。两次分层运行均已刷新 `维护记录/测试分层基线.json` 与 `维护记录/自检增量.json`。
  - 后续：接入外部 CI 执行器时复用这三个命令，不把桌面 Tk 用例并行堆叠在同一进程。

## P1：性能与资源效率

- [ ] 列表与文本预览采用增量加载和内容哈希缓存；避免页面刷新时反复读取全量 Markdown/JSON。
  - 新增字节级签名缓存：`script_text_reader` 读取 Markdown/TXT 时复用 `file_cache.read_bytes()`，
    因而剧本列表预览、结构稿读取等重复编码探测不再重复磁盘读取；文件修改后由 mtime/大小自动失效。
    最新的 `tests.test_file_cache` 与 `tests.test_script_workspace_service` 共 22 条、0.414 秒、0 失败，
    并额外校验解析路径不能逃离项目阶段目录；相关模块编译通过。大文本后台预览仍待分阶段改造，故总项保持未完成。
  - 已完成首段：分镜 JSON 目录/预览与剧本结构页面的 Markdown 预览均按“绝对路径 + 修改时间 + 大小”缓存；保存或外部覆盖后自动失效。`tests.test_file_cache` 19 条、0.443 秒、0 失败。目录增量加载仍待实施，故总项保持未完成。
  - R404 补齐内容哈希层：签名变化后以 SHA-256 比较已读字节；外部同内容重写复用原 JSON 解析对象、文本和字节对象，内容确有变化才重新解析。`tests.test_file_cache` 22/22、受影响冒烟 9/9 通过。大文本按需加载尚未全页面完成，故总项保持未完成。
- [x] 大文件文本框按需加载，分镜目录扫描走后台线程并在主线程批量提交 UI 更新。
  - 已完成分镜文件监听的扫描迁移：手动“刷新列表”仍同步返回确定结果；自动监听的目录扫描在
    `storyboard-catalog-scan` 后台线程运行，再由 Tk 主线程以完整 catalog 批量更新两个表格，
    防止大项目的定时轮询阻塞操作。`tests.test_storyboard_plan_service` 与 `tests.test_file_cache`
    共 21 条、0.360 秒、0 失败。大文本框的分段/按需渲染仍待实施，故总项保持未完成。
  - 本轮补充：剧本结构页的 Markdown 预览超过 512 KiB 时改由独立后台读取队列加载，
    小文件仍即时展示；后台预览不会占用业务任务锁，切换文件、进入编辑态或关闭窗口后会丢弃过期结果。
    `tests.test_script_preview_service` 3 条、`ContentBoxFitTests` 5 条及结构页关键回归 1 条通过。
  - R405：后台读取后的超长文本改由 Tk `after_idle` 以 32 KiB 片段逐步写入，只在内容投递时短暂开启文本框，避免一次性插入触发长时间主线程重排。`tests.test_script_preview_service` 4/4、默认冒烟 8/8 通过。
- [x] 统一缩略图工作进程的生命周期、队列上限和取消令牌，关闭项目时可安全停止。
  - `desktop.py` 关闭项目时调用 `forget()` 与 `reset_worker()`；定时器、待收任务和 worker 句柄均被
    取消/回收，进程退出亦注册兜底回收。后台队列上限为 400，队满时延后当前缩略图而不把大图解码
    退回 UI 线程。`tests.test_asset_thumbs` 20 条、23.517 秒、0 失败。
- [ ] 为模型请求设置阶段级上下文预算：摘要替代重复全文，限制并发，超限前提示用户。
  - 已完成剧本创作入口的两层预检：HOLLMWOOD 的角色调用、以及普通直连/带工具消息协议均按
    96,000 字符在发出请求前拒绝超限；直连会返回 `context_budget_exceeded` 和可执行的缩短提示，
    不再把推理或上下文挤占误报为模型空正文。导演规划与三次导演审核也不再在 user prompt 重复发送
    已注入 system 的节奏模板。三虎意图请求也已限制项目快照与指令各 16,000 字符；超限快照改为
    带原长度、哈希和顶层键的稳定摘要，避免截断半段 JSON 或泄漏全文。`tests.test_pet_llm`、
    `tests.test_token_saver`、`tests.test_writing_api`、`tests.test_hollmwood_roles` 共 169 条、
    3.174 秒、0 失败。其他阶段的摘要、并发限制尚待统一，故总项保持未完成。
  - R406：交互式阶段引擎启动也接入同一 96,000 字符预检，确保不会绕过后台路径在启动 CLI 后才失败。`WorkflowContextBudgetTests` 2/2、`smoke_test.py --affected workflow` 9/9（工作流 78/78）、默认冒烟 8/8 通过。
  - R417：首次任务保留完整接续约束和本地索引；同一会话的后续任务改用短摘要，只发送阶段、进度文件、成果计数、读取异常状态和按需读取要求，不再重复完整约束。上下文定向 113/113、架构 36/36、默认冒烟 8/8 通过；其他阶段的摘要策略仍待分批核验，故总项保持未完成。

## P2：兼容性、可移植性与体验

- [x] 将 Windows 绝对路径、可选本地软件和模型启动逻辑封装为平台适配；缺失依赖时给出可操作提示而非堆栈或弹窗失败。
  - 已完成首段：`platform_tools.open_path()` 统一处理 Windows `startfile`、macOS `open` 与 Linux
    `xdg-open`；目标缺失或没有系统打开器时返回可操作的中文说明。分镜文件、资产详情、资产批处理、
    参考图、首帧、预演、白模、旧版视频工作台与 ComfyUI 启动页已迁移其打开入口；`desktop.py` 中 17 个文件／目录／链接
    入口也已改走 `open_path()`／只允许 HTTP(S) 的 `open_target()`。`tests.test_assets`、
    `tests.test_keyframe_comfy`、`tests.test_previs`、`tests.test_reference_images`、`tests.test_video`
    加上平台架构门禁后的相关测试共 171 条、5.425 秒、0 失败；架构烟测 14/14、7.167 秒也通过，
    后者会阻止已迁移页面重新调用 Windows 专有 `os.startfile`。
    架构门禁现覆盖 11 个已迁移模块；最新的门禁与适配器测试 7 条、0.406 秒、0 失败，相关模块编译通过。
    其余本地模型启动与旧页面入口仍待迁移，故总项保持未完成。
  - 本轮补充：Windows 注册表能力也归入 `platform_tools.windows_registry()`；三虎开机自启和
    用户环境变量保存不再分别导入 `winreg`，非 Windows 或精简解释器均统一显示为不可用。
    `tests.test_platform_tools`、`tests.test_model_pool` 共 64 条，开机自启 9 条及架构门禁 14 条通过。
  - R408：后期剪辑页的剪映启动经 `platform_tools.launch_windows_app()` 统一处理宿主限制、文件存在性与启动失败，不再由 UI 直接 `Popen`。平台测试 10/10、默认冒烟 8/8 通过。
  - R409：Qwen Code 的可见交互会话也经 `platform_tools.launch_windows_app()` 启动；启动前先执行 96,000 字符上下文预算预检，平台适配器集中传递命令、工作目录、环境和可见控制台标志。缺失可执行文件、非 Windows 或启动失败均返回可操作提示。平台定向 10/10、Qwen 定向 2/2、默认冒烟 8/8 通过。
  - R410：Blender 的可见启动也经 `platform_tools.launch_windows_app()`；原有进程去重、窗口检测和 `.blend` 文件校验保持不变。Blender 接缝 1/1、平台定向 10/10、默认冒烟 8/8 通过。
  - R411：Codex/Claude 的可见交互 CLI 启动也经 `platform_tools.launch_windows_app()`；只有实际宿主启动失败才沿用既有 API 回退，非 Windows 或程序缺失直接返回可操作提示。工作流定向 79/79、默认冒烟 8/8 通过。
  - R412：新增架构门禁 `test_platform_process_boundary.py`，限制直接 `subprocess.Popen` 仅可存在于 `platform_tools` 与六个受控后台边界；可见本地应用启动均经平台服务。架构 32/32、默认冒烟 8/8 通过。
- [x] 阶段配置的模型名必须与实际执行器一致；本地 Flux、DeepSeek、Codex 和自动选择均使用同一配置来源。
  - 已复验：`workflow_settings.current()`、`effective_model()` 与三虎按钮均以阶段配置为唯一来源；
    DeepSeek V4 Flash 走兼容 API 而非回落 Codex，桌面 Claude/Codex 则走对应本机客户端。
    `tests.test_workflow`、文件缓存、剧本发现及平台门禁共 98 条、3.266 秒、0 失败。
    R403 已经现有产品入口启动本机 Comfy Desktop，并只读核验 `/system_stats` 与配置的 Flux Klein、Qwen 编码器、Flux VAE；三项均存在于对应节点清单。未提交生成任务。相关回归 95/95 通过。
- [ ] 建立统一响应式布局规范：按钮最小宽度、文本缩放、阶段栏宽度、上下内容框占比以及小窗口断点。
  - R413：新增响应式布局架构契约；桌面、视频工作台、分镜文件和资产批处理四个主要页面必须复用可换行的 `responsive_ui.FlowBar`，并锁定按钮按请求宽度、窄窗口换行和 `place` 排版的共享实现。自动化基线完成；全页面小窗口人工体验验收仍待专项轮。
- [ ] 所有“删除”入口统一进入回收站、显示影响范围、支持恢复；删除已选而未制作/未采用文件必须可用。
  - R414：资产页的已导入图片删除/重做不再写入自建“历史版本”；现统一走 `storage_maintenance.recycle_paths()`，并用 `restore_latest_recycled_path()` 只恢复选中资产，既有冲突保护和同批次不连带恢复均有测试。
  - R401：跨重启资产续跑台账属于可重建的内部状态，清除已收敛至 `storage_maintenance.clear_generated_workflow_state()`；该服务仅接受 `workflows/资产续跑台账.json` 精确路径，用户可见成果仍须进入回收站。
  - 已完成分镜页首段闭环：文件及关联工作稿移入项目回收站后，工具栏可“恢复最近删除”；恢复前展示
    影响文件，原位置冲突则整批安全中止，避免部分恢复。自动维护批次不会混入人工恢复入口。
    `tests.test_recycle_restore`、`tests.test_storage`、`tests.test_storyboard_plan_service`、
    `tests.test_file_cache` 共 30 条、0.488 秒、0 失败；仍有其他页面删除入口待统一，故总项保持未完成。
  - 本轮补充：项目删除实际已通过 `Projects.delete()` 移入项目库回收站，最后剧本、项目选择窗、
    侧栏菜单的过期“永久删除”文案均已改为回收站语义；剧本列表与参考图解绑的确认框也明确展示
    可恢复影响范围。`tests.test_core`、`tests.test_recycle_restore`、`tests.test_storage` 共 113 条、
    1.799 秒、0 失败，相关桌面/参考图模块编译通过。

## 当前验证证据

### 收尾状态（2026-09-27）

- [x] 本轮已完成：原子成果发布、模型响应诊断保护、媒体下载临时文件清理、首帧行发现服务拆分、
  大文本异步预览、平台打开/注册表适配及架构门禁回归，均已有对应自动化测试。
- [ ] 进行中：统一阶段写入服务、桌面/分镜/资产批处理的完整 view/service/adapter 拆分、旧接口
  facade 收敛、增量目录加载、阶段级上下文预算、真实本地 Flux 集成验收、全页面响应式布局和删除
  回收站统一，仍需按模块逐步迁移；不得因本轮全绿而误标为完成。
- [ ] 未开始或仅有局部验证：跨平台本地模型启动的真实环境矩阵，以及所有页面的小窗口人工体验
  验收；这些需要可用的目标运行环境和后续专项轮次。
- [x] 收尾全量基线：`run_selftests.py --all --safe --jobs 6` 覆盖 115 个测试文件、2,942 条用例，
  831.3 秒、0 个失败文件；日志为 `维护记录/round182_closure_safe_all_20260927.out.log`。
- [x] 收尾架构基线：`smoke_test.py --architecture` 共 14 条、7.584 秒、0 失败；覆盖删除网关、
  动态导入登记、分层、模型边界、循环依赖、路径权威、平台打开及阶段路径规则。

### 本次执行进度（第 182 轮续）

- [x] 排他成果发布完成安全全量验收：`run_selftests.py --all --safe --jobs 6` 共
  2,937 条、745.1 秒、0 个红色文件；覆盖 114 个测试文件及 GUI 安全层。完整日志：
  `维护记录/round182_safe_all_after_exclusive_publish_20260927.log`。

- [x] 大剧本文本后台预览完成安全全量验收：`run_selftests.py --all --safe --jobs 6`
  共 2,934 条、781.3 秒、0 个红色文件；全量覆盖结构剧本独立双框、编辑恢复、三虎自动链和
  各阶段 UI。完整日志为 `维护记录/round182_safe_all_after_async_preview_20260927.log`。

- [x] 本轮统一写入、删除提示与独立批量首帧工具的改动已完成安全全量验收：
  `run_selftests.py --all --safe --jobs 6` 共 2,931 条、751.6 秒、0 个红色文件；
  `smoke_test.py --architecture` 14/14 条、7.603 秒通过。完整日志为
  `维护记录/round182_safe_all_after_write_delete_20260927.log`。

- [x] 创作关键文本写入已收敛到 `agent.core.save_text()`：创意回复、`brief_creation.md`、
  `brief_complete.json`、自然原稿和结构剧本均先写临时文件，再经 Windows 锁重试的原子替换落盘。
  资产 PNG 同样经 `save_bytes()` 原子写入后才登记索引；`tests.test_core.AgentCoreTests`、
  剧本保存/结构保存及资产回归共 96 项通过。
- [x] OpenAI Chat 兼容响应的安全诊断已补齐：记录请求模型、协议、响应 ID、`finish_reason`、
  响应/消息字段、推理字段存在性/长度、正文长度及鉴权/协议/配置/超时/传输错误类别；
  不保存提示词、正文或推理正文。`tests.test_model_router_diagnostics`、模型池和
  剧本 API 回归共 74 项通过。
- [x] 三虎编排器不再把任意 SKILL 的“done”当作阶段完成：剧本与结构剧本必须在磁盘上
  找到有效成果；其余阶段释放为“等待成果校验”，由生成/校验/采用服务自行收场。
  `tests.test_skills.OrchestratorTests`、`tests.test_stage_flow` 共 61 项通过。
- [ ] 尚未达到“每一个阶段写入均由统一服务接管”及“每种模型调用都持久化诊断”的验收口径；
  下一步须迁移分镜/资产/视频成果写入，并将安全诊断接入阶段日志。

- [x] 剧本模型诊断已落地为 `model_diagnostics.py`：每次直连或 HOLLMWOOD 角色调用均产生原子事件，包含请求模型、响应 ID、结束原因、推理字段长度、正文长度、协议结构及脱敏错误类别。`tests.test_model_diagnostics`、`tests.test_hollmwood_roles`、`tests.test_writing_api` 共 24 项通过，验证诊断不会写入剧本正文或非白名单字段。

- [x] 三虎意图模型已接入同一诊断服务；OpenAI 兼容响应的 `choices/message` 结构由
  `model_diagnostics` 统一提取，事件仍不包含正文或推理原文。`tests.test_model_diagnostics`
  与 `tests.test_pet_llm` 共 54 项通过。
- [x] 自动定稿只有在后台产物生成、采用清单/工作集同步和页面收尾均完成后才向三虎报告成功；
  收尾异常会清除成功指纹、保留产物并进入可诊断的退避重试，避免“口头完成”。关键自动
  定稿回归通过；完整 GUI 分组回归待安全门禁完成后记录。

- [x] 本次补齐资产登记 PNG、白模批量任务清单、分镜定稿失败回滚三类成果写入：均改走
  `agent.core.save_bytes()` / `save()` 的临时文件和原子替换路径。资产索引仍只会在 PNG
  验证并落盘后更新；定稿回滚恢复旧 JSON 时也不会写出半份文件。`test_assets` 与
  `test_final_viewer` 共 73 条通过，涉及文件已完成 `py_compile`。
- [x] 白模自动化派发前冻结的 `分镜快照.json` 与 `调用配置.json` 已改由同一原子保存服务生成；
  后台制作不再可能读到写入中断的任务输入。`test_previs`、`test_previs_monitor`、
  `test_force_quit` 共 73 条通过。
- [x] 独立首帧批量工具的任务记录、分镜 JSON、PNG 首帧和生成前 JSON 备份也已迁移到
  `agent.core.save()` / `save_bytes()`；图片成功原子落盘后才更新镜头关联。`tests.test_batch_frames`
  15 条、2.363 秒、0 失败。

- [x] 首帧手工导入和分镜文件规范化的“只新建、绝不覆盖”成果写入已迁至
  `agent.core.save_bytes_new()`：先完整写入同目录临时文件，再通过排他的硬链接发布；名称
  碰撞会保留既有 PNG/JSON 并抛出 `FileExistsError`，不会替换用户成果。`tests.test_core`
  105 条、`tests.test_keyframe`、`tests.test_shot_batches`、`tests.test_asset_contract`、
  `tests.test_workflow` 共 154 条通过。
  独立 ComfyUI 批量首帧工具亦使用同一发布语义；其同名 PNG 回归与上述集合合计
  262 条通过。

- [x] 三虎日报/周报、人工门禁确认和阶段 README 初始化也已迁移到 `agent.core.save()` /
  `save_text()`；不再以直接覆盖方式写正式文件。`tests.test_pet_report`、
  `tests.test_confirm_gates`、`tests.test_stage_layout` 共 106 条通过，架构烟测 13/13 通过。

- [x] 三虎阶段启动已收束至 `stage_handler_registry.start()`（L3）：Pet UI 不再直连结构剧本、
  分镜或首帧批处理；L3 统一分派到结构剧本异步链、分镜工作计划或首帧批处理。结构剧本遇到
  其他后台任务时保留单个待派发标记，在当前任务收尾后经 L3 自动恢复；真正的前置条件和派发异常
  仍发出明确失败事件，不会误报完成。`tests.test_stage_command_contract`、
  `tests.test_pet_ui.AutoStartTests`、`tests.test_pet_ui.DesktopSeamTests` 共 21 条通过。

- 架构冒烟 `smoke_test.py --architecture`：13/13 通过（本轮修复 Qwen 适配器经工作流引擎回导入的循环）。
- 近期模块回归：剧本/结构/分镜/阶段流程 203 项、资产 60 项、资产契约 26 项、资产详情 23 项、定稿/文案/退出 35 项、创意对话 58 项、首帧 38 项均已通过。
- [x] 全量安全自测已复跑完成：`run_selftests.py --all --safe --jobs 6` 共 2,896 条、810.1 秒、0 个失败模块；增量台账已刷新为 `维护记录/自检增量.json`。此前迁移的剧本结构 GUI 夹具改为使用编号阶段路径，并按最终分镜归档的真实产物位置断言，避免测试以旧英文目录冒充当前流程。
- [x] 复核架构烟测：`smoke_test.py --architecture` 13/13 通过；阶段路径、删除网关、动态导入登记、分层依赖和无循环导入均仍受门禁保护。
- [x] 本轮服务层回归：`run_selftests.py --layer service --all --jobs 6` 共 1,279 条、24.8 秒、0 个红色文件；
  分层基线和增量台账已刷新。该结果只证明服务层，不能替代仍待执行的 GUI 与端到端回归。
- [x] 本轮 GUI 边界回归：`tests.test_ui_edges` 共 107 条、137.732 秒、0 失败；测试中的自动流程
  暂停日志均由缺少前置成果的夹具刻意触发，最终退出状态为 `OK`。
- [x] 已消除 Tk 窗口销毁后的 `after` 回调诊断：`ui_theme` 的延迟定位任务和三虎回复框
  `hint_tick` 均纳入登记/取消路径；后者在被主动刷新时也先撤销旧任务，避免覆盖任务 ID 后
  留下孤儿回调。`run_selftests.py test_ui_theme test_pet_ui` 共 561 条、42.8 秒、0 个失败且
  标准错误为空。GUI 分层执行与全量复跑仍作为后续持续门禁保留。
- [x] 剧本准备页的首次布局与文件列表重排不再使用无主的 `after_idle(lambda)`：任务在窗口销毁时
  明确取消；创意文件命名断言也改为调用 `script_contract.stage_file_name()`，避免测试私自复写
  命名规则。受影响的 `test_idea_chat`、`test_ui_edges`、`test_ui_theme` 共 172 条、144.2 秒、
  0 个失败且标准错误为空。
- [x] 连贯性台账（JSON、Markdown、锚点和三元组）及资产导入进度 Markdown 已迁移至
  `agent.core.save()` / `save_text()` 的原子替换路径；`tests.test_continuity_ledger` 18 条、
  `tests.test_workflow` 74 条通过。其余阶段产物仍须逐类迁移，故 P0 总验收项保持未完成。
- [x] 手动创意另存版本不再以直接文件句柄写入，已接入 `agent.core.save_text()`；
  `tests.test_idea_chat` 与 `tests.test_ui_edges` 共 165 条、167.829 秒通过。
- [x] 视频阶段的历史任务索引、实际提交提示词、字幕叠加标签及拼接清单均已接入
  `agent.core.save_text()`；`tests.test_video` 33 条通过。媒体二进制与状态 JSON 原本已
  通过 `save_bytes()` / `save()` 原子落盘。
- [x] Claude/Qwen 工作流的交互任务书、续写任务及后台制作报告均已迁移至
  `agent.core.save_text()`；外部 Agent 不会读到写入中断的半份 Markdown。`tests.test_workflow`
  74 条通过。
- [x] 兼容的离线编剧任务生成器写入的 Skill 位置说明及《编剧任务书》也已接入
  `agent.core.save_text()`；`tests.test_core.WritingTests` 4 条通过。
- [x] 视频提示词的当前版本文本、镜头交接文本与 Codex 续接任务文件已统一改为
  `agent.core.save_text()`；`tests.test_video_ui`、`tests.test_core.WritingTests`、
  `tests.test_token_saver` 共 154 条通过。
- [x] 字幕、对白脚本、剪辑优化清单和剪映交接包说明已接入 `agent.core.save_text()`；
  `tests.test_video_ui`、`tests.test_video`、`tests.test_workflow` 共 170 条通过。
- [x] 原子写入扩展后复跑 `smoke_test.py --architecture`：13/13 通过，阶段路径、删除
  网关、动态导入登记、层级边界和无循环依赖均保持受门禁保护。
- [x] 自动首帧/资产队列不再在工作线程返回时直通 `stage.completed`：主线程分别以
  `keyframe_batch_state()` 与 `asset_pending_ids()` 复核真实磁盘缺口；仍有缺口时保留重试，
  不推进自动链。`tests.test_pet_ui.DesktopSeamTests.test_desktop_carries_the_pet_and_wrapped_seams`
  、`tests.test_ui_edges.UiEdgeTests.test_unattended_chain_runs_asset_final_keyframe_in_order`
  与 `smoke_test.py --architecture`（13 项）通过。
- [x] Claude 项目文件工具的旧 `writing/` 入口已改为“历史可读、新写迁移”：读取仍可回退
  到已有旧稿，但 `writing/新文件` 与 `01剧本准备/新文件` 的写入均唯一落在 `01剧本准备`，
  且正式文本走 `agent.core.save_text()` 原子替换。`tests.test_writing_api` 16 条与
  `smoke_test.py --architecture` 13/13 通过。
- [x] 缩略图后台任务清单、关闭后的维护日志和视频提示词正文已接入 `agent.core.save()` /
  `save_text()`；后台消费者不再可能读取半份 JSON 或文本。`tests.test_asset_thumbs`、
  `tests.test_results`、`tests.test_storage` 共 31 条及三个相关模块编译通过。
- [x] Codex Token 节省配置（项目 `AGENTS.md`、`.codexignore` 与 `config.toml`）改为走
  `agent.core.save_text()`；设置页不再可能在进程中断时覆盖成半份规则文件。`tests.test_token_saver`
  87 条与模块编译通过。
- [x] 服务层全量门禁已复跑：`run_selftests.py --layer service --all --jobs 6` 覆盖 62 个测试文件、
  1,260 条用例，23.2 秒、0 失败；分层基线与自检增量台账均已刷新。
- [x] 软件示例气泡不再为普通消息的排版而裁剪首尾空白：示例保持与原始模板逐字一致，
  同时维持无底色置灰和本次会话内可编辑。`tests.test_idea_chat.SendMessageTests` 17 条、
  `tests.test_ui_edges` 107 条（142.3 秒）均通过。
- [x] 原生/Seedream 资产的临时导入图、恢复图、生成图和 Comfy 返回图均改由
  `agent.core.save_bytes()` 原子落盘，之后才进入资产登记；参考图分类复制同样避免半份文件。
  `tests.test_auto_import`、`tests.test_native_run`、`tests.test_seedream_direct`、
  `tests.test_reference_images`、`tests.test_reference_search`、`tests.test_reference_wall` 共 110 条通过。
- [x] 逐句 TTS 的音频文件以及 ComfyUI 拉回的批量图片改由 `agent.core.save_bytes()` 写入；
  任务时间轴/下载记录仍在成果存在后才原子更新。`tests.test_tts` 与 `tests.test_assets` 共 95 条通过。
- [x] 桌面层的结构剧本编辑、首帧导入和整段配音全部切换到统一原子保存；首帧的备份与
  镜头 JSON 失败回滚仍保留。`tests.test_final_viewer`、`tests.test_tts`、
  `tests.test_ui_edges.ContentBoxFitTests` 共 53 条通过，`desktop.py` 编译通过。
- [x] 本轮 GUI 复验：`tests.test_idea_chat tests.test_ui_edges` 共 165 条、172.8 秒、0 失败；
  验证软件示例原文、编辑保存、首帧回滚、响应式布局与三虎自动链未因写入收敛而回归。
- [x] 本轮架构烟测：`smoke_test.py --architecture` 13/13 通过；统一保存依赖未突破阶段路径、
  删除网关、动态导入登记、层级方向或无循环导入门禁。
- [x] 三虎的自动队列与页面手工完成上报已收敛到同一产物校验出口：剧本、结构剧本、已采用分镜、
  资产/台账/批次/首帧/预演门禁、已验收视频及音频/剪辑/交付文件均须有可复核成果；缺少成果只发
  `stage.paused`，不会把状态机标完成或推进自动链。`tests.test_pet_ui` 555 条、73.827 秒、0 失败。
- [x] 参考图候选下载、镜头编号重排以及 Codex/终端自动输入的 JSON 载荷均已改走统一原子保存；
  参考图挂接或编号重命名不会看到半文件。`tests.test_reference_search` 56 条、0.179 秒及
  `smoke_test.py --architecture` 13/13 通过。
- [x] 已移除桌面 Agent 正常退出和“首帧已齐全”快捷分支对 `stage.completed` 的直接发送；
  下载剧本分支同样先验收自然剧本再武装自动链。`tests.test_pet_ui` 555 条、67.311 秒、0 失败。
- [x] 安全全量回归已完成：`run_selftests.py --all --safe --jobs 6` 共 2,898 条、683.4 秒、
  0 个失败模块；增量台账已刷新为 `维护记录/自检增量.json`。
- [x] 补齐模型协议回归：OpenAI Chat 的 `system`/`user` 封装和 DeepSeek 空正文响应均被
  固定测试；导演与导演审核只受控重试一次并提升至 8192，普通 Writer／Editor／Actor
  （含修订）固定 8192 且不重试。`tests.test_hollmwood_roles`、`tests.test_model_router_diagnostics`
  和 `tests.test_model_diagnostics` 共 13 条、0.189 秒、0 失败。
- [x] 缩略图缓存的 PNG 与“不可解码”标记也已改由 `agent.core.save_bytes()` 原子替换；后台
  解码与前台缓存读取不会碰到半张 PNG。`tests.test_asset_thumbs` 19 条、3.321 秒、0 失败。
- [x] 视频提示词格式修复的历史备份与 Seedream 临时 PNG 已接入 `agent.core.save_bytes()`；后者在原子落盘后才交给资产登记。`tests.test_keyframe_comfy` 12 条、2.865 秒、0 失败，相关模块已 `py_compile`。
- [x] 统一原子写入服务的临时文件改为同目录、每次唯一的 UUID 名称；并发后台保存同一成果不再共享 `*.tmp` 或互相清理。下载暂存同样改为唯一名称。`tests.test_core.AgentCoreTests` 10 条、0.655 秒、0 失败。
- [x] 桌面窗口直接销毁时，缩略图轮询也会无条件尝试撤销 `after` 任务；不再因
  `winfo_exists()` 已变为假而遗留指向已回收 Python lambda 的 Tcl 回调。
  `tests.test_asset_detail tests.test_asset_gating tests.test_asset_thumbs` 共 59 条、
  41.511 秒、0 失败且标准错误仅保留 unittest 正常汇总；安全全量
  `run_selftests.py --all --safe --jobs 6` 共 2,928 条、726.0 秒、0 个红色文件，
  `smoke_test.py --architecture` 14/14 通过。
- [x] 独立的 ComfyUI 批量首帧工具不再用固定 `*.tmp` 直接覆盖任务 JSON 或源分镜
  备份：每次写入都生成同目录唯一临时文件，JSON 先解析校验、二进制备份先核对长度，
  再执行替换；失败会清理本次临时文件且保留旧成果。新增
  `tests.test_extra_batch_frames` 2 条通过，工具模块 `py_compile` 通过。
- [x] 安装图标、PNG 预览和快捷方式使用的根目录/带指纹图标也已接入
  `agent.core.save_bytes()`；重绘或更新时不会留下截断的 `.ico`/`.png`。`tests.test_app_icon`
  与 `tests.test_app_shortcut` 共 64 条、9.860 秒、0 失败，两个模块编译通过。
