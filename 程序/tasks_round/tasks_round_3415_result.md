# R3415 — A6 可靠性、性能及 UI 可替换性审计
<!-- round-evidence: {"commit_base": "fe394c6c", "credential_hits": 0, "evidence_sha256": "f0a91e0b7a393d2d", "exit": 0, "failed": 0, "passed": 0, "round": 3415, "tests": "docs-only"} -->

## 三问
1. 类型：AGENTS §3.5 只读诊断/测量。仅新增本报告及标准提交证据；不改生产源码、规则、其他车道台账或用户项目。
2. 验证：隔离故障注入及隐藏桌面合成测量已执行；定向验证终态见 M。默认冒烟、完整架构、全量未运行，不宣称三个基线全绿。
3. 欠账：未修复生产欠账。把 A3 静态窗口提升为行为证据，并冻结后续验收目标。A6 的诊断交付不等于整个任务书完成或已合入 master。

## A. 基线、范围与前置
2026-11-18，工作树 `C:/Users/LAIBIAO/.codex/worktrees/0361/漫剧制作助手`。开工为 detached `fe394c6c15ba2e2cb8567e17c30b93ff58b8eb04`，按授权切换既有 `codex/architecture-a6-audit`；生产受审基线保持此提交，含 A4/R3411、A5/728f4ff7、A3/25608acf。中央领号 R3415，归属已核对；scope 对本报告与标准证据检查，另 93 个活跃分支无重叠。没有对应待认领队列 ID，不认领无关任务。

已读项目 AGENTS、runbook §12–15、任务书 A6、R3402/A0、R3405/A1、R3409/A3、R3411/A4、R3413/A5 的相关证据。L0/L1/L2/foundation 保留所有权，尤其 L2 snapshot/operation_id/取消演进不由本轮重做。本轮不 rebase 到变化中的主干来混淆测量基线，不写主树源码或交付文件。共享 Git 领号及标准提交元数据按既有入口维护。

本树没有随附运行时，只借用 `D:/漫剧制作助手/运行环境/Python/python.exe`，cwd 始终为本树程序目录。探针使用 TemporaryDirectory，发布日志 ROOT 显式重定向临时项目；未访问真实用户项目、调用外部供应商、付费、下载模型或运行真实 ASR。网络测试仅注入 opener 或 127.0.0.1 临时 HTTPServer。

## B. 方法与证据边界
四个临时探针位于 `%TEMP%/a6-r3415/`，不提交生产代码。以下结果为真实输出摘要；原始日志不入库。故障按调用边界精确注入，不能将注入 OSError 等同真实磁盘耗尽或 ACL 环境全部行为。

| 探针 | 方法 | SHA256 |
|---|---|---|
| probe.py | 真 skill 文件/台账/回收服务；record、verify、forget 故障；发布取消与 journal 写故障 | D8931C76A3A6464D5EAA872FEBFCA8DF4AEB4235F481BE5F0035BFC6B3B14355 |
| measure.py | 真进程崩溃/恢复、进程超时、缓存与合成 Tk 负载 | 3675E0AE56BDF9AA8F2955AE874CB0BE279D95B85544B1426A488A6563C9F810 |
| network.py | 假供应商计数、执行时限与迟到结果 | E2BDFEE71013A1DA5B7FFDBCBB955969CC6205E7A00214D9EC76FC4D06D839DC |
| feedback.py | 无窗 UI 替身反馈、重复提交副作用、Retry-After 解析 | E575993B914C5220FE6F30968693C6A75C95D7B75C2F8E1040C4FF8C07B84117 |

重建方法：在程序 cwd 将当前目录加入 sys.path；临时 project/data/skills/01剧本准备SKILL 建旧单文件 `old` 和带正文的新清单；先用真实 record 写旧摘要，保留台账字节，再按 C 的位置 patch 故障。用 `patch(agent.publication.ROOT, temp/transactions)` 隔离所有发布锁/日志。实际回收服务不替换。性能探针由 `scripts/gui_hidden.py <临时日志> <本树程序> -- <随附Python> <临时探针>` 执行，隐藏桌面成功 exit 0。测试数据自动清理；探针与摘要留临时目录供本机复核，不作为长期依赖。

## C. A3-01/02 故障注入与反馈窗口
源码定位：`ui/skill_import_service.py:248–286`、`:620–643`；`ui/skill_panel_import.py:61–73`；`pet_skills_manage.py:323–332`。

| 注入 | 实测文件/台账状态 | 补偿与反馈 |
|---|---|---|
| A3-01 换入及真实试冻结成功后 record 抛 ENOSPC | 新版仍在目标；旧台账字节未变；旧内容有 1 个回收副本；抛 OSError | 无自动恢复。UI 替身实测返回 None、显示“新增 SKILL 失败”、不刷新注册表；会出现失败提示与磁盘新版不一致 |
| 对照：试冻结抛 ImportBlocked | 目标恢复 old；台账不变；旧内容 1 份 | 这一分支确有补偿，不能笼统说所有导入失败均不回滚 |
| 试冻结边界直接抛 PermissionError | 新版保留、台账不变、旧内容在回收区 | 这是边界异常注入；正常 `_verify` 会将部分 OSError 包成 ImportBlocked。说明非 ImportBlocked 逃逸路径不受同样补偿，不能据此声称正常读权限错误必定逃逸 |
| A3-02 真回收后 forget_ledger_targets 抛 PermissionError | 原目标不存在；旧台账保留；旧内容 1 个回收副本；异常上抛 | 无自动恢复。删除 UI 静态仅捕获 ImportBlocked，PermissionError 会越过局部失败提示和 refresh；未声称已实测真实弹窗误报成功 |

优先级 P1：交 skill 生命周期/发布所有者。修复前先补行为断言；目标是“文件与台账同一提交结果”或显式 partial/reconcile 结果，保留回收恢复入口。补偿失败应保留原始错误及恢复位置，不能 finally 异常覆盖首错，也不能让用户盲目再点一次。不能用更换 UI 框架解决这个一致性窗口。

## D. 取消、重复点击、迟到、切项目与关闭
发布探针调用真实 `orchestrator.stage_publication.publish_stage_text`，旧文本 old、新文本 new，patch 仅在精确时点发出 cancel。发布器 `:110–117` 在写入前和必需索引之后 checkpoint；事务提交见 `agent/publication.py:172–200`。

| 时序 | 实测 |
|---|---|
| 进入发布前已取消 | ExecutionStopped，目标 old |
| update_index 中取消 | ExecutionStopped，目标 old，事务回滚 |
| 最后 checkpoint 后、进入 `_commit` 时取消 | 无异常，目标 new；取消没有撤销已进入提交的成果 |
| 提交后可再生索引阶段取消 | 无异常，目标 new；这是已提交结果，不应倒推成未执行 |

`BackgroundTaskLifecycle` 实测旧 ticket/取消 ticket/重复 finish 均不接纳；新 ticket 接纳。50ms deadline 的慢函数（睡眠 200ms）约 75.777ms 返回 ExecutionStopped，worker 当时仍运行；其稍后 finish 被拒绝。数字为单次局部观测，不是 p95 或强制终止 SLA。

重复 submit 实测：先启动旧函数并等 barrier，再 submit 新 ticket 并运行新函数，最后释放旧函数。两个函数均产生记录副作用，新→旧；旧 finish=False、新 finish=True。替换代次防止旧 UI 回调，不提供操作幂等或远端去重，不能把它当作重复点击完全防护。真实按钮禁用/入口闸门与远端幂等必须另外覆盖。

切项目静态：`ui/desktop_project_pages.py:373–393` 对 worker、idea request、剧本 Agent 设阻断，并在用户取消时保持项目。正常结束前被阻断，不代表所有绕过入口或取消后残留 worker 都被根隔离。`ProjectContext` 显式目标校验存在；旧 context=None、捕获可变 self.root 的闭包仍需 owner 验收。当前 L2 在途快照契约由其车道定义，本轮不补第二套。

关窗静态：`ui/desktop_lifecycle.py:15–36` 撤定时器并调用 `page_navigation_controller.cancel_lifecycles`；后者 `:35` 撤 background/cloud/自动阶段登记。`ui/desktop_async_tasks.py:64–75` 在 shutting_down、代次不符时停止轮询。真实关闭/切换相关定向验证见 M；生命周期单体通过不等同所有页面/弹窗组合覆盖。

## E. 网络、重试次数与总时限
`infra/http_client.py:95–108` 业务 attempts=1+retries；POST 默认不重试。`contract/platform_tools.py:632–640` 的 requests 适配器还有 GET/HEAD total=2 的传输重试。

| 场景 | 实测请求数/时间 | 解释 |
|---|---|---|
| 注入 opener 始终离线，GET retries=2 | 3；收集到退避 0.625871/1.244420s | sleep 被替换为记录；9.279ms 不是实际网络耗时 |
| 同上 POST | 1，无退避 | 默认不会按业务 retries 重发 POST |
| 默认 requests + 本机持续503假服务，GET retries=2、timeout=.1 | **9 次，3137.695ms** | 真默认传输与业务两层叠乘；业务 sleep 替换为 no-op，传输退避真实执行 |
| 同假服务 POST | 1 次，21.068ms | 不代表 allow_retry_post=True 或其他上层入口也只发一次 |
| 注入 opener 每次睡25ms后离线；scope 预取消/10ms截止 | 各仍3次，76.569/76.170ms | HTTP循环自身没有消费执行取消/剩余时限；假 opener 故意不合作，不能据此估算真实 socket 时间 |

本机 urllib3 `Retry(total=2, backoff_max=30, respect_retry_after_header=True).get_retry_after` 对 7200 返回 7200。这里只实测解析、不真实等待两小时；`backoff_max` 不能作为 Retry-After 总等待封顶证据，需适配器 owner 明确钳制和总 deadline。现有 `timeout` 是单次 I/O 参数，不是整次任务墙钟总时限。

阶段 CONFIG 普遍 attempts=2（`orchestrator/stage_parallel.py:47–89`）；不能未经真实调用链验证就把所有阶段套成 18 次请求。`RetryRegistry` 手动恢复只读/幂等任务，不自动重试计费操作。A8 应要求依赖的重试能力与业务预算统一，A12 验证每条真实链路的总尝试次数/最终费用状态。

## F. 崩溃、磁盘、进程、缓存与日志
| 项 | 实测或静态证据 | 判断/未覆盖 |
|---|---|---|
| 崩溃恢复 | 子进程真实 transaction + save_text 写 new 后 os._exit(23)；父进程直接读 new，recover_pending 后 old | 在临时本地盘通过；恢复入口调用之前的直接读能见未提交值。未测断电、网络盘、损坏日志/回滚时再次满盘 |
| 磁盘满/权限拒绝 | `_write` 分别注入 ENOSPC/EACCES，发布抛错，目标保留 old | journal 登记阶段通过；skill 台账阶段失败见 C。不是所有写入点都安全的证明 |
| 进程超时 | 隐藏启动仅 sleep 的 Python 子进程；communicate_or_kill timeout=.1，590.149ms 后 poll 非空 | 无本次子进程残留。没测孙进程、ASR常驻、Blender、强制关机；`platform_tools.py:180–213` 有 taskkill /T 与回退 wait |
| 缓存失效 | 同长度 JSON 从1改2并还原 mtime_ns，read_json 仍读1；externally_overwritten 后读2 | 签名碰撞真实复现，外部改动需通知/内容校验策略；不能用所有写入都经过 published 的假设覆盖外部工具 |
| 缓存增长 | 顺序读100个临时JSON，加前一个样本后 `_CACHE`=101 | `file_cache.py:22–26` JSON/digest dict 未见容量驱逐；text/bytes 各32条。条数限制也不限制单项字节 |
| 发布与磁盘增长 | publication access 每次遍历事务目录，锁等待上限30s；回收/版本盘点可 walk/rglob（storage_maintenance.py:130/566/781） | 同步调用时可能占主线程；项目数量/事务残留/目录深度/磁盘慢均是独立变量。本轮不扫描真实项目、不清理回收站 |
| 日志 | app_logging.py:29–30/359：RotatingFileHandler 5MiB×当前+3备份，名义约20MiB | 单条超大日志可越目标；这不是所有 subprocess stdout、测试日志、诊断包总配额。未实测长期增长 |
| 执行记录 | desktop_automation_service.py:416 保留所有 unresolved + 末20条已结束记录；late_units追加 | 可恢复性需要保留未知远端状态，但 unresolved 数量/每项 late_units 无全局硬上限，不能直接删未知计费记录 |

## G. 性能测量：分开数据规模、控件、解码、文本和渲染
参考硬件：i9-12900K，16核/24逻辑处理器，31.70GiB物理内存；磁盘库存 Samsung SSD 980 PRO 500GB、ST2000DM005-2U9102，未据库存推断临时目录具体物理盘映射。Windows 11 build 26100、Python 3.14.7、Tk 9.0；800×600真窗口，隐藏桌面，合成数据。其他车道正在占用 GUI 测试令牌；测量有并发负载，不作为无干扰发布性能凭据。

每项3次，perf_counter 墙钟，展示中位/最大；没有足够样本估算p95。文件在测量前刚创建，OS缓存偏热；没有冷盘/长期内存曲线。

| 操作/数据规模 | 中位 ms | 最大 ms |
|---|---:|---:|
| rglob，100个128字节文件 | 0.260 | 0.541 |
| rglob，1000个128字节文件 | 1.587 | 1.654 |
| 创建/pack/布局/销毁100个Label | 89.100 | 106.310 |
| 同上1000个Label | 1323.367 | 1866.271 |
| Text 插入/布局/销毁，1万字符 | 10.813 | 11.345 |
| 同上10万字符 | 12.154 | 15.934 |
| 同上100万字符 | 18.212 | 26.468 |
| PIL 解码512²单色PNG | 0.896 | 1.018 |
| PIL 解码2048²单色PNG | 5.326 | 6.397 |
| 新RGB→PhotoImage→Label显示/布局/销毁512² | 19.369 | 21.570 |
| 同上2048² | 56.804 | 61.435 |

结论限定：此负载中控件数量成本高于目录枚举；不能推出生产页面同样耗时，也不能把单色PNG扩展为照片/大图/动画。PhotoImage一列含RGB创建和渲染，不称作纯上传耗时；文本使用换行短句，没有测试极长单行、富文本标签、中文字体回退或日志全量插入。未测真实启动时间/RSS/滚动帧率，不生成虚构成绩。

## H. 主线程风险与 UI 可替换性
可定位的同步热点：`ui/skill_panel_import.py:26–39` 强制 scan 后逐控件销毁重建；`ui/desktop_project_pages.py:152–162` 回收批次树逐项插入；`ui/asset_thumbs.py:532/620/634` 超时或失败回落 `_build_here` 可在 UI 线程解图并写缓存。正常 request 队列满则保留文字，不误报所有缩略图都同步解码。存储盘点应继续走既有后台描述任务，不在进入页面时新增递归扫描。

| L0–L3 路径 | 证据与最小解耦方向 |
|---|---|
| L3 stage_models | `_schedule_popup_job :192` 直接收 window、after、bind、winfo_exists；`_untop :168` 操作窗口属性。把弹窗定时器/置顶归 L4 adapter，L3 只产配置数据/完成事件，保持既有入口适配 |
| L3 stage_handler_registry | `start(desktop,...) :145` 接完整 Desktop；`:104/107` 调 pet_report/open_storyboard_skill | 收窄为项目快照+已注入的阶段命令/反馈端口，不让新UI仿造整个Tk Desktop |
| L3 page_navigation_controller | `cache_entry :106` 返回含 holder 的缓存字典；cancel_jobs 接 owner/after_cancel，运行时可携带Tk对象 | 无 tkinter import 不代表没有对象依赖。缓存holder与定时器token的存储留L4，决策只消费根/签名/存活布尔值；避免为了“纯度”重写已有纯决策函数 |
| L2/L1 到L4既存边 | A1/R3405 的 asset_batch_service→asset_reference_images、idea_chat→pet_agent、native_apps→white_model 等 | import反向边是替换成本证据，不直接证明每个分支收到Tk对象；先给消费端口和测试替身再迁移，遵守A4豁免/所有权 |
| L0/platform_tools | 本轮限定目录搜索未见直接 tkinter import；Windows/Tk运行时能力仍需按A4/L0P迁移 | 不能从文本扫描推出所有回调无Tk或全仓已可换UI；不新建框架层 |

A8 小验证应挑“阶段启动→状态/取消→发布结果”及长列表各一条，用同业务接口/合成数据对比，保留Tk adapter。当前不安装PySide/Pyzed，不宣布替换框架即可解决事务、重试或容量问题。

## I. 当前上限及修改前冻结的后续验收目标
下列“目标”从本轮报告冻结供A12/U0使用，未改变生产配置，未声明已达标；owner 若调整须记录硬件、数据和原因。

| 资源/行为 | 当前事实 | 后续目标/验收 |
|---|---|---|
| 启动 | performance_contract 现有：首帧1500ms、首事件循环2.6s、启动递归扫描0 | 原门槛不放宽；同硬件至少30次，记录冷/热与p50/p95；真实项目壳/假数据，不读用户项目 |
| 长列表/控件 | 现有滚动中位150ms、内存增量30MiB；合成1000控件明显慢 | 100/1000/10000条，窗口可见控件建议≤200；单次UI回调p95≤50ms；保留现有150ms灾难线；100次开关/切页后RSS增量≤30MiB且不持续爬升 |
| 图片 | 内存图项1200、磁盘图项4000、待造队列400（asset_thumbs.py:51/60/65）；项数不是字节限制 | 图片解码前验证尺寸/像素，建议最大32MP；单图/总缓存需字节预算（内存128MiB、磁盘1GiB候选）；后台解码，满队列丢非可见预取、不回退主线程大图 |
| JSON/文本 | JSON/digest无驱逐，text/bytes各32条 | 单项目缓存建议≤256项且≤64MiB；≥1MiB文本分页/裁剪；同stat覆盖经既有通知后下一次读必须新值；外部覆盖检测策略由L1确定 |
| 后台/重复操作 | 普通队列10、历史20、late8；submit替换不能去重 | 本地同operation_id一次生效；重复点击100次产生一个有效提交；未知远端结果必须查单/对账后决定重试，不以本地取消推断退款 |
| 取消/关闭 | run每20ms轮询；线程协作；单个进程超时样本590ms | 本地取消/关窗反馈p95≤100ms；取消后0个旧UI回调，已commit成果保留且可见；合作步骤≤1s停止；登记子进程树≤3s回收，失败显式报告，不强杀未知进程 |
| 网络时限 | 单次timeout；GET传输3×业务次数；Retry-After无已证总封顶 | HTTP总尝试预算显式统一；付费POST默认1；所有退避受remaining约束，过deadline不新发请求；供应商慢/取消/503/429组合计数，保留unknown结果查询入口 |
| 磁盘/恢复 | 事务锁30s；日志/回收/未知任务可增长 | 小型事务（≤10份各1MiB）中断恢复≤2s候选；每个replace/fsync/索引点注入满盘与权限；旧或新一致可读，失败保留可恢复凭据；临时空间至少预估新内容+备份+10%余量 |
| 日志/历史 | app日志名义20MiB，其他日志不统一 | 诊断/子进程输出建议总配额100MiB、单事件≤64KiB；增长达到阈值告警/压缩，不清未知费用记录或按年龄删用户项目；新配额需要可恢复归档策略 |

建议容量不是扩权清理指令。真实图像种类、磁盘类型/可用量、并发车道、杀软、DPI、字体、目录深度、网络服务端等待、子进程后代均会改变测量；验收必须保留这些变量。

## J. 整改路线与消费责任
- A8：优先比较可复用事务/重试/队列/缓存能力能否满足C–I，而非按框架名选型。GET9次、取消不撤commit、未知计费保留是硬输入。
- A11/A12：P1 skill文件与台账原子性/补偿反馈；P1 deadline/重试预算与操作幂等；P1项目快照/取消后的发布归属；P2 JSON容量/签名碰撞、缩略图回落、日志与未决记录增长。
- L0/L1/foundation：沿原发布/进程/HTTP/缓存入口改，先接收在途成果；L2负责快照/结果/operation_id契约；L3装配消费者；L4负责Tk对象和调度；本报告不转移所有权。
- A15/A16：真实进程树、磁盘故障矩阵、无干扰性能与全量欠账集成验证。A6不创建下一阶段；由根任务汇合A7后安排A8。

## K. 测试迁移计划
把C的精确失败窗口迁入现有skill生命周期/导入测试；复用临时目录与真实回收服务，先断言磁盘、台账、UI三者再修复。把D的四时点取消及barrier重复提交加入现有发布/后台测试，不仅检查源码字符串。HTTP用本机503/429假服务记录每次请求与elapsed，加入Retry-After超长但虚拟时钟测试；禁用真实费用/下载。

切项目测试增加“取消但旧线程仍在执行、切到B、A迟到提交”的组合，断言A/B文件归属与UI代次；关窗覆盖任务结束与destroy竞争、after回调、子进程后代。性能分离文件扫描、控件数量、解码和渲染，保留冷/热/重复次数与RSS，不将本轮微基准改写成页面回归成绩。

## L. 交付与完整性
只新增本报告与 `tasks_round/evidence/R3415.json`。提交经 `scripts/dev.py commit`，提交哈希以Git中R3415标题定位，避免报告自引用未来哈希。没有改任务书勾选/完成文件、project_status、生产文件；整体任务完成文件由全任务验收轮交付。N=M+1由master合入轮同步，本分支不抢写状态页。

## M. 验证终态与三个基线
在本树程序 cwd，PYTHONUTF8=1，借用随附解释器执行：
- `run_selftests.py -k desktop_automation_service publication_transaction stage_execution_service http_client file_cache platform_tools`：6文件，125用例，295.8秒，0红、0 skip、exit0。耗时含跨树GUI令牌等待，不能当执行性能。
- `run_selftests.py -k project_switch_guard desktop_close timers page_navigation_controller`：4文件，30用例，122.0秒，0红、0 skip、exit0；含Tk的批次经隐藏桌面。切项目覆盖取消/确认/worker与chat与Agent忙时阻断；关闭/定时器/生命周期覆盖以现有断言为限。
- 合计10文件155用例通过，不是全量绿色。四个临时探针均正常结束；预期注入异常已在摘要中记录为现状缺陷，没有伪装成生产修复通过。
- `git diff --check` 无问题；提交前只有本轮结果文件待跟踪。scope无重叠，标准提交入口生成docs-only证据；该标识仅说明提交未改源码，不替代以上行为验证。

默认冒烟本轮未运行；A4的9/9（8业务+1隐藏探针）及5文件28条仅为历史证据。完整架构本轮未运行，A0的532条及2失败/1错误不是本树现时基数或绿色证据。完整安全全量本轮未运行。

`auto_full_safe.py --status` 本轮实读：上次全量绿R3293，最新R3413，源码轮23（门禁线8），当前非主干，不触发后台；最近后台 HEAD 0e3fc76，2026-11-18T21:07:02，exit1，红文件 `test_shared_adapter_infrastructure`、`test_ui_edges_guards`、`test_pet_ui`、`test_perf_baseline`，红后冷却。没有修复这4文件或消除全量欠账。根任务后续整体集成不得以本轮定向通过替代真实全量绿凭据。
