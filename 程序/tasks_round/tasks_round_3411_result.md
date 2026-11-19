# R3411 — A4 架构决策与守卫迁移设计
<!-- round-evidence: {"commit_base": "8662002b", "credential_hits": 0, "evidence_sha256": "0ef9857046f9e10d", "exit": 0, "failed": 0, "passed": 0, "round": 3411, "tests": "merge-ci-exit"} -->

## 三问
1. 类型：§3.5 只读诊断/设计交付。只新增本结果（兼设计记录）及标准提交证据；不修改生产代码、现行规则、其他车道登记或用户数据。
2. 验证：默认冒烟 8 个业务检查＋1 隐藏桌面探针＝9/9；定向守卫结果见 M。完整架构与安全全量未运行，不声称三个基线全绿。
3. 欠账：没有消除生产缺陷。将 A1–A3 证据转为依赖矩阵、迁移责任与可判定退出条件；A4 设计不等于 A9 门禁已经实施，也不代表任务书整体完成。

## A. 绑定基线、前置与范围
日期 2026-11-18；工作树 `C:/Users/LAIBIAO/.codex/worktrees/79d1/漫剧制作助手`，专用分支 `codex/architecture-a4-design`。最初 detached 25608acf，按任务切换既定分支；rebase master 后 HEAD `8662002b10e1a422dbc984e0dc76b35756970eab`，已包含 master `0e3fc763`（R3408 合入 K9/L0P）。与 master 的生产源码无差异；A0–A3 文档依次继承。

输入：任务书 §0–§6、A0/R3402 及基线报告、A1/R3405、A2/R3406、A3/R3409、architecture §3、统一基数与现有守卫、L0 宪法任务书 K-H1–K-H10。A1 的 25 个位置/20 个模块对不是 25 个豁免；现行静态豁免 18 对、动态反向 2 对，分别按原源迁移。

任务书依赖图要求 A5 先于 A4，接续只给了 A1–A3。本轮先安排独立 `codex/architecture-a5-audit` 工作树补 A5，待其完成后接收 `728f4ff79d6054ccced1438fb1f3d0ea458a4d14`（R3413），再完成本设计。已用 `git merge --no-ff --no-commit` 纳入本分支，核验 `25608acf` 是该提交祖先（exit 0）；本轮标准提交完成此合并，保留原 A0–A3→A5 链。A5 消费结论见 L。

中央领号 R3411；`dev.py scope 程序/tasks_round/tasks_round_3411_result.md` 返回另 90 个工作树分支无重叠（不等于 90 个任务同时执行）。无对应队列 ID，不认领无关项目。本轮不写主树、不 push、不修改 `project_status.md`；N=M+1 留给 master 合入轮同步。

## B. 所有权与采用顺序
| 车道 | master 左独有/分支右独有 | A4 决策 |
|---|---|---|
| codex/l0-constitution | 1/0 | K9 已合入；仍保留 L0/K12 端口及 K11 L0P 所有权，不因 ahead=0 认定释放 |
| codex/l1-enterprise | 5/3 | 基础设施规则/测试/事务先接收等价交付 |
| codex/l2-maturity-taskbook | 5/3 | 快照、operation_id、取消及结果演进在途；消费其合同，不另定义第二套 |
| codex/foundation-hardening | 18/19 | 原语与共享契约交集先核验 G-1，不能用本设计绕开 |
| codex/foundation-api-disk | 47/17 | 网络/落盘边界不并行重做 |

每批执行重新 scope 并核对主干，不冻结这些数字。G-1 是地基四文件合入或明确放弃的门，不是“任务已设计”即可通过。K11 尚未建 `foundation/` 的事实与 K9 已登记层值 0.5 分开；当前未安装的接口下文只称目标端口。

收尾只读核对中央 lanes.json，仍有 foundation 多个细分车道登记；表中分支差异为开工快照，A5 后续观察 l0-constitution 已与 master 0/0。登记缺项、role/last_seen 或 ahead=0 都不构成所有权释放，仍结合 worktree/分支/scope 保留 L0/L1/L2 责任，不修改中央车道数据。

## C. 目标依赖矩阵与装配例外
以下为 A9 待落地的规则设计，不覆盖当前 `architecture.md`。静态依赖含函数体、try、别名、相对/包子模块导入及常量动态导入；运行回调方向不等于 import 许可。

| 调用方→目标 | L0 | L0P | L1 | L2 | L3 | L4 | L5 | 开发工具 |
|---|---|---|---|---|---|---|---|---|
| L0 | 无环纯依赖 | 禁 | 禁 | 禁 | 禁 | 禁 | 禁 | 禁 |
| L0P | 允许 | 无环 | 禁 | 禁 | 禁 | 禁 | 禁 | 禁 |
| L1 | 允许 | 允许 | 无环 | 禁 | 禁 | 禁 | 禁 | 禁 |
| L2 | 允许 | 端口实现适配所需 | 允许；正式写入另受 E 限制 | 无环 | 禁 | 禁 | 禁 | 禁 |
| L3 | 允许 | 允许 | 允许 | 允许 | 无环 | 禁静态依赖；展示端口注入 | 禁 | 禁 |
| L4 | 允许 | 经适配入口 | 只读/界面基础适配 | 兼容期已登记调用；新用例走 L3 | 允许 | 无环 | 禁 | 禁 |
| L5 | 允许 | 装配 | 装配 | 装配 | 装配 | 装配 | 无环入口协调 | 禁 |
| 开发工具 | 可检查 | 可检查 | 可检查 | 可测试 | 可测试 | 隐藏桌面测试 | 可验证启动 | 工具内部 |

“允许向下跳层”沿用既有分层判定的方向含义；不把箭头链误读为强制仅相邻层，也不把向下 import 允许误当成 UI 可写产物。L0 的纯度额外受 K-H1 约束。L2 可组合通用基础能力，但供应商特有协议应由注入适配器承接；既有 agent/volcengine、wan 的实际职责另行迁移，不能只改层号。第三方依赖仍按白名单；独立 ASR 环境单列闭包。

装配清单：L5 的正式 launcher 负责具体实现选择；既有 `desktop.py:183/193` 只保留启动控制器与后台 UI 调度适配装配；`stage_execution_service` 负责 ProjectContext、发布器和阶段用例装配。L3 不 import Tk 类型，回调接收值对象或调度端口，不接收 Desktop 整体。`app.py` 与 `desktop.py` 调试入口保留并明确自检差异，不把调试入口当正式入口。

每条例外必须登记 caller/函数/允许目标/原因/消费者测试/退出批次；只允许装配构造或注册，不允许该函数顺带实现业务。注册器机制位于 L1 不意味着 L1 业务可以加载任意高层；逻辑依赖以调用者→注册目标复原。不得加目录级或整层豁免。

## D. 接口归属与同用例替身
| 接口/事实 | 所有者、实现与注入 | 消费迁移与兼容 |
|---|---|---|
| ServiceResult 四字段、Cancelled、错误分类 | L0 service_contract；L2 产生业务结果，L3 保留语义，L4 映射展示 | 不在 A4 添加字段；L2 车道的 operation_id 先接收。旧文本/异常入口保留薄适配，成功才刷新，不把取消算业务错误 |
| ProjectContext | L0 类型，L3 project_context_factory 创建每次操作快照 | 不把 frozen 当深冻结；采用 L2 车道深快照合同。发布边界逐批消除 context=None，旧入口由 L3 补上下文，不从全局重读当前项目 |
| Clock/JsonStore/ProcessRunner/CancelToken/LogSink/IdSource | K-H5 指定 contract/ports.py；基础原语实现归 L0P，较高层适配可在 L1，注入在 L3/L5 | 等 K12（依赖 K11）与 G-1；L0 只定义协议和纯数据，不 import 实现。JsonStore 不存在/损坏/读失败三态不能压成默认值 |
| 发布与索引 | 复用 L3 stage_execution_service/stage_publication；L1 agent.publication/core 做事务原语 | L2 收注入 callable；不新建通用“超级服务”。正式成果发布、必需索引提交、完成核验分开 |
| UI 调度/进度通知 | L3 消费的窄端口只描述 schedule/post/关闭态；Tk 适配归 L4 | 能复用现有回调就不另建协议文件。业务不调用 widget/after/Tk Variable，不携 UI 对象进服务 |
| SKILL 生命周期 | L3 用例协调，L2 纯校验/状态决策，L1 回收/台账/文件操作，L4 预览确认 | 现 ui/skill_import_service、skill_lifecycle_service 含混合职责；按消费者拆，不改登记数字掩盖。旧 UI 门面保留到 A13 有删除证据 |

共同用例：现 UI 与未来 PySide6/假 UI 均调用 L3 的“保存剧本、开始阶段、取消任务、导入/卸载 skill”。请求只带项目快照、业务输入和操作身份；依赖是发布/存储/执行/通知端口。假存储、假供应商、假调度器替换实现而不替换业务函数；可在无 tkinter 导入的测试进程调用同一入口，并断言同一结果、正式产物、事件及取消行为。UI 框架选型留 U0，A4 不引入框架。

禁止为让 foundation 调用 core 而反向 import L1：先把真正通用的原子读写叶节点迁入 L0P，L1 core/publication 组合它；缓存失效通知由上层注入。若无法拆出叶节点，继续放 L1 并注入，不能把整个事务/模型池迁入 L0P。兼容门面导向高层只属 K-H3 受控历史桥；门面必须被扫描和弃用守卫看到，不能因名为 contract 就宣称纯 L0。

## E. 写入权、事务与失败传播
| 数据/操作 | 唯一责任 | 失败与验收 |
|---|---|---|
| 正式阶段 JSON/文本/媒体 | L3 发布用例授权，L2 校验，注入发布器，经 core/agent.publication | 必需索引失败回滚；可再生 file_index 失败保留成果并 warning。完成事件仍由 stage_completion_service 核验 |
| 应用配置/项目设置/台账 | 既有 L2 服务＋注入发布器，路径取权威服务 | 禁 UI 直接 open/save；业务数据与可重建缓存不得同一丢弃策略 |
| 用户可见删除/恢复 | storage_maintenance.recycle_paths/restore_recycle_batch | UI 只确认；不能 unlink 替代回收。取消/失败保留可恢复批次标识 |
| SKILL 文件＋来源台账 | 生命周期用例内一个可补偿操作 | 换入后 record 失败、回收后 forget 失败均进入补偿；补偿失败明确报告“部分完成/需恢复”，保留回收凭据，不伪报全回滚或成功 |
| 日志/诊断 | business_log 与既有诊断端口 | 脱敏白名单，不写正文/密钥；诊断失败不覆盖原始业务错误 |
| 临时文件/可重建缓存 | 已有 owner 的受控临时目录 | 仅清理本操作创建的资源，不能以“临时”删除未知用户文件 |

SKILL 迁移顺序：冻结输入与来源→暂存校验→取得旧版/台账恢复材料→换入或回收→核验最终路径→提交台账→宣布成功；异常按实际已完成步骤逆序恢复。复用既有 unit_of_work/回收 API 能力，先证明其覆盖目录/跨文件恢复再选；不虚构现有事务已经覆盖全部窗口。A6 负责故障注入形成事实，A11/A12 才实施修复。

结果适配边界：`collect_writing_quality` 目前 .data 消费建立在服务失败抛异常之上；若演进成失败结果须先检查 ok 并保留 reason/Cancelled/recoverable。不要单改生产者造成 UI 静默；一个调用链生产者与所有消费者同批迁移，旧外部协议由适配器保留。补偿失败可在现有 SystemError.data 携脱敏恢复标识并给用户明确恢复提示；不为“部分完成”偷偷增加第五字段。复用 is_failure 判别，调用方不得因 Cancelled.ok=False 发起回滚或重试；事务内部在返回结果之前负责完成自己的提交/恢复，避免重复补偿。

## F. 线程、取消、重试与恢复
1. UI 主线程只读写控件；后台工作经 BackgroundTaskLifecycle，输入在调度前冻结。回调由 UI 适配器回主线程，检查任务代次、项目身份、关闭/取消态，迟到结果不刷新已换项目。
2. CancelToken 表示本地协作停止。发送前 checkpoint 可保证不发送；请求已受理时不推断远端取消成功。未知提交状态保留查询/对账身份，不自动重发 POST；此处复用 request_ledger/model_metering，不另造支付账本。
3. 提交前取消应不发布；提交中取消须按事务边界完成提交或回滚后报告实际状态；提交后取消不得声称成果未产生。UI 回调被抑制不等于磁盘事务已撤销。A6 对每个窗口注入，A11 消费 L2 车道取消矩阵。
4. HTTP 传输重试、单项执行重试、用户重新发起分别计数；同一远端提交只能有一个重试 owner。总次数、总时限、并发上限来自已有配置；不编造预算，不以每层各自有界证明总量有界。
5. 启动不递归扫项目；显式任务/后台加载后投影 UI。关窗停止新调度并释放已有 owner 管理的进程/任务；不能阻塞主线程等待无限 join。真实冷启动、切项目＋取消＋关窗组合性能留 A6 测量。

## G. 动态入口、包身份与分发
保持 L4 `ui_plugin_registry.module()`、L3 `stage_handler_registry.start()` 的权威入口。守卫同时核对注册表、调用点参数和目标层；非字面量动态目标限定为注册表键，不接受任意用户路径 import。插件/skill 脚本执行边界与 Python import 分开检查，不因没 import 就可删除。

扫描节点改用规范包限定名；兼容 alias 映射到实体但保留门面独立的副作用/CLI 责任；覆盖 from 包 import 子模块、相对导入、函数内导入、动态常量、`__init__`、入口与发布运行文件。A1 列出的 16 个包内未登记、12 个未入图文件及 6 组 stem 冲突逐项处置，未知层报未分类，不能默认为合格。

ASR 是独立进程协议闭包：校验 JSON-Lines 版本/大小/取消/进程退出和导入隔离，不把其独立环境依赖混入主运行时白名单。batch_frames_tool、codex_tasks、console_submit、codex_paste 按真实生产消费者分类，不能用 TOOLS 排除掩盖运行依赖。开发 scripts/tests/领号工具禁止被产品启动链依赖。

## H. 现行豁免逐项退出（不扩大基线）
以下 18 项与统一基数“层级.items”一一对应；每项迁移保留旧入口契约，行为验证＋扫描确认旧边消失后同批删对应豁免。位置详见 R3405 D，主干重定位后再执行；“owner”表示先接收该车道交付，而非本轮抢改。

| ID | 旧边 | 目标/迁移消费者 | owner 与行为退出证据 |
|---|---|---|---|
| E01 | api_models→core | cloud_removed 写配置迁 L1 服务，纯模型事实留 L0；原消费者通过注入写入口 | L0 K12/L1→A10；删除模型后配置一致、写失败可恢复 |
| E02 | artifact_lineage→core | 纯血缘结构留 L0，落盘放允许层并注入；script_contract 消费纯类型 | L0 K12/A10；血缘写入与失败恢复 |
| E03 | asset_batch_execution→asset_reference_images | 无 UI 参考图服务供 L3 调用；UI 仅呈现 | A11 接 L2；批量输入/引用与旧行为一致 |
| E04 | asset_batch_service→asset_reference_images | 提示词规则/登记能力从 UI 拆出或注入，覆盖 asset_prompt/register_image 两位置 | A11 接 L2；生成和登记失败均回滚 |
| E05 | confirm_gates→legacy_compat | 身份纯映射放纯契约；兼容目录解析经端口 | A10/A11；旧项目确认身份不变 |
| E06 | engine_probe→workflow_engines | L3 计算 argv 注入 L1 探测器；CLI 适配保留 | L1/A11；命令构造与探测超时兼容 |
| E07 | h3_reference_adapter→shot_assets | L2 解析引用并将数据交 L1 适配器 | L1/L2→A11；缺图/有效图 payload 相同 |
| E08 | idea_chat→pet_agent | L3 注入文本/模型响应服务；L2 不取 UI agent | A11；保存/失败/取消均走同一用例 |
| E09 | idea_document_paths→legacy_compat | 与 E05 共用身份事实，禁止另造重复映射 | A10/A11；新写旧读与旧路径兼容 |
| E10 | native_apps→white_model | L3/L4 构造 Blender 打开请求，L1 只管进程 | L1/A11；路径/参数/失败消息不变 |
| E11 | pet_bus→core | 事件事实留 L0，Bus/持久化运行时按 K12 放 L0P 或注入 | L0 K12；事件次序、订阅清理及失败日志 |
| E12 | script_contract→core | 五导入位置的保存/台账/manifest/结构写职责迁出；解析纯化 | L0 K14/A10；自然稿、结构稿、台账事务与兼容 API |
| E13 | script_manifest_schema→core | schema 纯构造/校验留 L0，writer 由上层提供 | L0 K13/A10；旧 manifest 读、版本和写失败 |
| E14 | shot_assets→white_model_ref | 无 UI 参考解析服务供两方使用 | L2/A11；镜头路径、引用与缺失处理 |
| E15 | skill_orchestrator→skill_tools | 工具执行注册/端口归 L3，UI 工具页仅调用；不由 L3 import L4 | A11；本地视频/剪辑工具及错误回传 |
| E16 | stage_layout→core | 目录事实留 L0，创建/迁移 IO 迁 L0P 或 L1 注入 | L0 K13/A10；13阶段目录、旧读、新建失败 |
| E17 | volcengine→white_model_ref | 同 E14 的纯输入/参考解析，供应商适配不依赖 UI | L2/A11；提交 payload/缺参考失败 |
| E18 | wan→white_model_ref | 同 E14，共用用例输入 | L2/A11；与 E17 分供应商验证，不调用真实收费 API |

动态两项：D01 `keyframe_batch→stage_parallel` 的 _brief_block 由 L3 预计算后注入，测试阻断/取消不发请求；D02 `engine→white_model` 的 submit 由 L3 注入执行适配器，测试无 Tk 假执行器及旧 UI 均可调用。由 A11 负责；对应动态台账条目删减，不向静态豁免搬账。

环退出：S01 core/file_cache/publication 以 L0P 叶原语＋注入失效通知拆环（L1/foundation，恢复/并发测试）；S02 keyframe_evidence/shot_assets/stage_parallel/white_model/white_model_ref 随 E14/E17/E18/D01/D02 拆 UI 参考边（A11）；S03 stage_models/workflow_settings 将选择规则与配置快照单向化，旧配置/默认值测试（A11）；S04 local_video/skill_orchestrator/skill_tools/stage_execution_service 随 E15 将提交发布端口注入，视频产物/失败发布测试（A11）。静态和动态基线分别删已消失的环。

A1 新发现的 api_endpoints/diagnostic_capture/model_metering/model_pool/request_ledger 环不是合法旧豁免；先由 L1 车道用诊断 sink 注入与组装自检拆环，再扩扫描覆盖，不能把它加到 KNOWN_CYCLES 让门禁绿。两步间可影子报告但不得宣称完整覆盖已验收。

K9 的 `L0 纯度` 台账实际为 122 个 file:symbol:type 键、136 次命中，不能把次数当键数。唯一逐点清单仍是统一基数 JSON；以下以模块规则全覆盖每个原键，迁移时再记录原键→目标实体/纯替代→消费者测试→删除凭据，不另造第二套计数源。

| 原模块（contract/） | 键/次数 | 每个键的归属与退出方案 |
|---|---|---|
| api_models | 1/1 | L0 K12；配置存在性由存储适配器提供，旧模型配置消费者测试 |
| artifact_lineage | 3/3 | L0 K12；扫描/stat移运行时，纯血缘只收数据，旧血缘报告测试 |
| pet_bus | 7/7 | L0 K12；Bus/时钟/日志迁运行时，消费者行为及对象identity验证；任务书历史64消费者须执行时重数 |
| platform_tools | 55/61 | L0 K11＋foundation；整体迁L0P，旧门面弃用棘轮，不更换底层能力 |
| script_manifest_schema | 1/1 | L0 K13；纯schema与写入拆开，manifest读写兼容 |
| stage_layout | 10/10 | L0 K13；stage_runtime负责IO，validate纯化和启动检查 |
| script_contract | 30/35 | L0 K14；script_store负责IO，旧写入口兼容与原子性 |
| artifact_schema | 2/2 | L0 K14收口/A10补充；备份恢复归存储适配，未来版本拒写测试 |
| episode_contract | 2/2 | L0 K14收口/A10补充；存在性作为输入，剧集校验纯函数测试 |
| file_naming | 1/1 | L0 K14收口/A10补充；时钟注入，命名冲突/时间回拨测试 |
| media_signature | 1/1 | L0 K14收口/A10补充；纯字节签名留L0，读文件放适配器，PNG头行为测试 |
| prompt_templates | 1/1 | L0 K14收口/A10补充；模板外部资源读取与纯渲染分开，模板兼容测试 |
| shot_selection | 1/1 | L0 K14收口/A10补充；路径状态作为输入，选择规则测试 |
| stage_path_service | 4/7 | L0 K14收口/A10补充；纯路径与目录探测拆分，新写旧读测试 |
| storyboard_contract | 1/1 | L0 K14收口/A10补充；IO前置至适配器，分镜校验测试 |
| storyboard_paths | 2/2 | L0 K14收口/A10补充；路径探测注入，旧目录解析兼容 |

后九项不能假定 K14 只迁 script_contract 就自然归零：这是 K9 实测清单对 K14 范围的补充输入，由 L0 owner 接收，必要时按≤3模块拆批。计数下降不能替代键集合和每键计数单调；把同一 IO 移行或藏到门面不算退出。A9 切强制前检查所有键归属及行为凭据，不扩大原豁免。

## I. 硬约束—守卫—消费者对应表
H 为拟在 A9 激活的硬约束（现行已有者注明复用）；未配可运行测试前只作设计，A4 不添加 AGENTS 条款。守卫不仅做源码文本搜索：结构规则用 AST/解析图，数据规则用行为测试。

| ID / 约束 | 守卫方案及红样本 | 消费者与启用批次 |
|---|---|---|
| H01 完整身份和分类 | 扩 _scan/test_layers/test_layers；相对子模块、同 stem、包初始化、未知层 canary 均应报错 | 全部运行包、TOOLS/分发入口；A9，先拆新暴露环 |
| H02 方向/纯度/无新环 | 复用 K9 test_contract_purity、层级/环棘轮；L0→L0P、L0P→L1、懒导入反向坏样本；键集合不得增 | E01–E18、D01–02、S01–04；先接 L0/L1，A9–11 |
| H03 仅明确装配例外 | caller+函数+目标 AST allowlist，注册项反解目标；装配函数新增业务调用坏样本；无 Tk 用例加载测试 | launcher/desktop/stage_execution_service/注册器；A9/A11 |
| H04 写入权/项目隔离 | 复用 project_context_boundary/写服务守卫，临时双项目测试旧回调不得写新项目；直接 UI 写正式文件坏样本 | 剧本保存、阶段发布、设置、SKILL；A11 |
| H05 事务完成才报成功 | publication_transaction、stage_execution_service 及 skill 注入失败；record/forget/索引/补偿各窗口验证文件与台账 | A3-01/02 链路，A6取证→A11/12修复 |
| H06 结果消费保留取消/错误 | ServiceResult 合同测试＋实际调用链 fake 返回 success/UserError/SystemError/Cancelled；不得只取 .data | writing_quality、UI 导入删除、阶段开始兼容适配；A11 |
| H07 UI线程和取消代次 | background_task 行为测试，假调度器＋真隐藏 Tk 组合；取消/替换/切项目/关窗迟到结果计数为零 | Desktop.async_ 与阶段用例；A6/A12 |
| H08 重试总预算与未知提交 | http_client/ledger 假服务计数；超时受理、重连、取消，POST未知状态不得第二次提交；验证总时限 | workflow/模型/视频执行链；L1交付＋A6/A12 |
| H09 动态入口和工具闭包 | AST＋注册表闭包＋分发干净环境启动；未知动态键、生产导 tests/scripts、缺运行组件坏样本 | ui_plugin_registry、stage_handler_registry、ASR/批处理；A9/A15 |
| H10 版本读写与真实基线 | artifact_schema_wiring 的 missing/future/损坏行为；真实 receipts＋发现器计数，生成视图只读源 | 台账/队列/manifest；L0交付/A10/A14 |

建议而非硬约束：接口优先小 callable、按风险安排拆分、未来 UI 选型候选、可视化图样式。不为建议新增强制扫描或业务抽象。

## J. 执行清单与回滚
| 任务 | 依赖/责任 | 允许文件与动作 | 验收/回滚 |
|---|---|---|---|
| A4 本轮 | A1/A2/A3/A5，架构设计车道 | 仅本报告与 evidence/R3411.json | 对照矩阵/豁免覆盖/定向验证；revert本轮文档提交 |
| A6 | A1/A3，独立诊断车道 | 独立报告；故障注入仅临时隔离目录，不修生产 | A3窗口、取消与重试计数；删除仅本轮已验证临时资源 |
| A7 | A0/A3，独立设计车道 | 独立报告；不建设云服务/不真实支付 | 会员/钱包/BYOK/未知提交边界；文档revert |
| A8 | A1/A5/A6/A7 | 框架决策和必要最小验证，先查白名单与现有实现 | 有证据复用/拒绝，不能以选型阻塞无关本地修复 |
| A9 | A4/A8＋其他车道等价交付 | 开工scope后细分 _scan/_layers/守卫/权威文档；每轮≤3模块 | 先红样本再绿，不增豁免；整体规则变更同批revert |
| A10–12 | 按任务书与G门，L0/L1/L2 owner先行 | H表与E表仅候选责任，不预先抢占实际文件 | 每条生产者+消费者+兼容测试；逐批提交回滚，正式数据不靠git恢复 |
| A13–17 | 严格按任务书依赖 | A5证据删除、A14文档/skill、A15交付、A16集成、A17完成文件 | 本轮不勾完成；总目标仍需验收并合入master |

旧豁免退出实行“小批代码/消费者迁移→失败行为与兼容验证→扫描证明消边→删除旧键→适用回归”。新扫描覆盖先做影子差异和坏样本，修掉额外真缺陷后再切强制；不能把新发现问题扩大到旧豁免。涉及层级登记、启动、删除语义/Tk 生命周期的批次按 AGENTS §5 触发当次全量，文档设计轮不重复全量。

## K. 测试迁移验收清单
- 同一无 Tk 用例，用真实和假发布/存储/供应商各运行成功与失败，比较结果、写集、事件和调用次数；测试替身不得替换整个业务函数。
- 所有写链覆盖输入校验、发送前取消、受理未知、发布前取消、必需索引失败、可再生索引失败、补偿失败和重复恢复；正式产物/台账快照断言，不能只断言异常文本。
- 旧入口别名、动态注册、CLI、旧项目读取与分发清单必须保留至 A13 证明无兼容责任；不因代码搜索无 import 删除。
- A2 C01–C12 的现行文档问题在 A9/A14 原位修，历史数据不重写；基准历史与 skill 缺交付分别处理，不复制主树私有资产或 skip 制造绿色。
- 每个新硬约束须有能失败的 canary 与实际消费者测试；未落地就标“设计待实施”。架构数按当次发现器计，受测树与提交绑定。

## L. A5 接收与阶段结论
A5/R3413 已完成，提交 `728f4ff79d6054ccced1438fb1f3d0ea458a4d14`，报告 `tasks_round/tasks_round_3413_result.md`，定向16/16（兼容3、分发13），未跑全量。本轮合并仅带入其报告与证据，无生产源码变化。

- 既有123个门面已退役、123个替代实体仍在，不重复清理；非空Python字节完全重复组为0，不等于语义无重复。
- D01–D05（file_index/file_index_contract/file_naming/global_library_service/legacy_migration）外部兼容证据不足，保留；D06 storage_maintenance 只有迁移后删除资格，CLI/补丁面/分发和弃用窗口条件未满足。
- D07 previs_progress 存在“复制到批次目录＋生成import”的生产消费者；D08 legacy_compat 维护旧项目读取，复审日期不是自动删除日期。两者不得因普通import少而删。
- D09–D12 ASR、MCP、快捷方式、探测器、Blender模板、批处理及桌面发送组件保留运行/分发路径；A4 G/H09 按独立进程和生产组件建模，A15验证闭包。
- D13 近似重复/死回调仍证据不足；D14 当前立即可删项0。A13只能在A12之后重验条件，不把A4设计当删除许可。
- 文件分类与路径映射沿用A5 F/G；分发排除开发资产不等于源仓删除。A5发现 distribution_manifest 的“未来构建器”措辞已落后实际构建器，交A14同步。

A4 两项设计验收已满足：C–I 明确依赖、接口/装配、写入、线程取消、动态入口、旧豁免退出及每条约束的守卫/消费者；D/K明确假实现和未来UI使用同一业务用例，禁止 L0/L0P 回依赖 L1。前置A1/A2/A3/A5均有实际交付且A5提交纳入本分支。该结论仅为设计交付；规则尚未激活，A6–A17及整体master验收仍未完成。

## M. 本轮验证与提交
默认 `smoke_test.py`：9/9、0失败，自动执行 `scripts/gui_hidden.py --probe`。最初误传 `smoke_test.py --probe` 被参数解析拒绝，不计为测试；已按实际执行器改用默认命令，未改脚本。

定向第一批 `run_selftests.py -k test_contract_purity test_layer_relations test_no_circular_import test_rule_guard_map` 实际发现 3 文件、19 用例，0红/0skip；其中 test_layer_relations 不是现存文件，不能算覆盖。随后精确运行 `-k test_layers test_dynamic_import_registry`：2文件、9用例，0红/0skip。合计实际5文件/28用例。未改源码或测试，未重复已绿测试。

临时只读一致性探针通过：E01–E18 与统一基数18条边集合完全相同；纯度表覆盖16模块/122键/136次；H01–H10齐全，无非法控制字符。此探针只校验文档完整性，不充当未来守卫实现。受测源码与 master 0e3fc763 相同，文档接收若不改源码不重复这些测试。

完整架构未运行，不能沿用 A0 532 条当本轮基数；A0 的历史 failures=2/errors=1 不意味着本树同样失败或已修复。`scripts/auto_full_safe.py --status` 实读：上次绿全量 R3293、最新 R3411、其间源码轮23（门禁线8），本树非主干不触发后台；上次后台 HEAD 3a97b18 退出1，红文件 test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline，处于红后冷却。本轮不重跑全量、不消除欠账；A16/master集成必须接收实际修复与绿色凭据。

标准提交使用 `scripts/dev.py commit -m "R3411: A4架构决策与守卫迁移设计并接收A5"`；合并暂存含A5原报告/证据，本轮新增仅本报告及 evidence/R3411.json。无源码、规则、私有数据和日志入暂存区；不生成整份任务书完成文件。提交实际哈希以该标题的Git记录及对外交付为准，避免内部自引用未来哈希。
