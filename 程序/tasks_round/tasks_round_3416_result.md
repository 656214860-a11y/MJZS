# R3416 — A8 成熟框架复用决策（设计/最小验证）
<!-- round-evidence: {"commit_base": "89147a27", "credential_hits": 0, "evidence_sha256": "ed6278d163804a3f", "exit": 0, "failed": 0, "passed": 0, "round": 3416, "tests": "merge-ci-exit"} -->

## 三问
1. 类型：§3.10 验证/设计轮，执行任务书 A8。交付仅本报告与标准证据，接收 A7 文档；不改生产代码、不安装依赖、不开发云服务。
2. 验证：默认冒烟 9/9（8 业务＋1 隐藏桌面探针）；媒体定向与环境失败复验见 M。完整架构、安全全量未运行，不能宣称三个基线全绿。
3. 欠账：完成选型决策与验证边界澄清；没有消除生产缺陷或全量欠账。A9–A17、U/C 未启动；本轮完成不等于整本任务书完成。

## A. 基线、授权与整合
日期 2026-11-18；工作树 `C:/Users/LAIBIAO/.codex/worktrees/22f2/漫剧制作助手`。开工 detached HEAD 为 `89147a27d33d461359b9443bc258d85a9b6f02cb`，创建 `codex/architecture-a8-framework`，中央领取 R3416 并核对归属。首次领号子线程因默认 GBK 解码 Git 输出报 UnicodeDecodeError，但已成功分配 3416；设置 PYTHONUTF8=1 后用 `record 3416` 核实同树归属，未再次 next 消耗号码。

先执行 `git merge --no-ff --no-commit e0cdf4e2778313d688d34da907eff28dc5df0170`，无冲突接收 A7 两个文件；本轮收尾以双亲合并提交一次提交接收内容与 A8 独立报告，保留 A6/A7 双亲历史。没有接触 master 工作文件、没有 rebase/push。源代码与 A6 完全相同；A7 只增加报告和标准证据。

| 必需输入 | Git / 结果文件 | 核验与本轮使用 |
|---|---|---|
| A1 | `9cd998079666679b4079c7a15e1004630922abb0` / `tasks_round_3405_result.md` C–K | 已是 HEAD 祖先；包身份、TOOLS 运行组件及扫描盲区，不以换框架消环 |
| A5 | `728f4ff79d6054ccced1438fb1f3d0ea458a4d14` / `tasks_round_3413_result.md` D–K | 已是 HEAD 祖先；D14 当前可删除源码为 0，旧入口/ASR/宿主工具保留 |
| A6 | `89147a27d33d461359b9443bc258d85a9b6f02cb` / `tasks_round_3415_result.md` C–M | 本树起点；文件/台账窗口、GET 9 次、截止/取消、缓存/解码/恢复目标 |
| A7 | `e0cdf4e2778313d688d34da907eff28dc5df0170` / `tasks_round_3414_result.md` B–M | 无冲突合入；平台/BYOK、权威资金账本、未知受理查单、媒体采购边界 |
| A4，供 A9 汇合 | `fe394c6c15ba2e2cb8567e17c30b93ff58b8eb04` / `tasks_round_3411_result.md` B–K | 已包含；H01–H10、豁免退出及原 owner 不变 |

`dev.py scope` 对本报告与 `evidence/R3416.json` 检查无重叠（另 94 个活跃分支）。没有匹配队列 ID，不冒领无关任务。功能树不修改 `project_status.md`；其当前轮次 3409 与本分支最新报告 3416 不满足 N=M+1，按分支规则交后续主干合入轮统一更新，不能在功能树伪造同步。整体任务尚未结束，按 runbook §16 和任务书 §10，不创建空的整体任务完成文件。

## B. 先检验问题前提
- **事实**：`requirements.txt` 已锁 requests 2.34.2、urllib3 2.8.0、certifi 2026.10.23、charset-normalizer 3.5.2、idna 3.20、Pillow 13.0.0。`tests/architecture/test_dependency_whitelist.py` 以此为生产版本真源，开发工具允许列表不等于产品依赖。不能把“采用 requests”再算一次新增建设。
- **事实**：A6 已测出 http_client 业务重试与 requests 传输重试叠乘；取消不撤销已 commit 的成果。更换重试库、Celery 或 UI 框架不能自动解决幂等和状态归属。
- **事实**：A7 是设计，当前没有获准上线的云端钱包/支付/供应商合同。框架预算统计不等于权威钱包；本地 RequestLedger 不能直接升级为云端资金真源。
- **事实**：通用 HTTP 的 `request_bytes` 是二进制响应入口，其 payload 仍 JSON 序列化；不能因名字含 bytes 就认定已有 multipart/分片上传。`test_multimodal_upload` 只验证附件分类，不能算真实上传验收。
- **推断/裁决**：桌面当前最小成本路线是补现有入口的行为缺口。云端框架只保留条件候选；新依赖不得成为 A9 本地门禁整改的前置阻塞。
- **未证实**：任何候选的实际供应商全媒体兼容、真实计费、安装后总占用和负载成本，本轮均未验证。下文明确延期，不把网页“支持”写成产品已支持。

## C. 逐缺口三选一及最终裁决
“采用”指采用该改进方向，不表示本轮已实施。没有新增生产依赖。

| ID / 真实缺口 | 改进现有实现 | 采用成熟框架的比较 | 不新增的后果 / 裁决 |
|---|---|---|---|
| F01 请求总预算与未知受理（A6 E） | 在 http_client / platform_tools 单一入口统一尝试数、remaining、Retry-After 上限；保留 POST 默认一次及查单 | 已有 requests/urllib3 足够承载传输；再叠 Tenacity 会增加重试 owner，仍须自建费用语义 | 不修会保留 GET 9 次窗口。**采用现有改进，拒绝本轮 Tenacity/第二网络栈** |
| F02 文件＋台账事务与恢复（A6 C/F） | 原 publication/skill 生命周期 owner 补 record/forget/索引失败补偿或显式 partial/reconcile | SQLite/ORM 只能原子化库内状态，不能让文件 replace、回收、外部 API 自动加入同一事务；Django 不解决 Windows 文件链 | 不修继续失败提示与落盘状态错位。**采用现有事务补齐，拒绝为此引入数据库/ORM** |
| F03 桌面后台取消与重复操作（A6 D） | BackgroundTaskLifecycle＋operation_id＋项目快照，保留提交边界和迟到过滤 | Celery 是分布式 worker/broker，不提供 Tk 线程归属或一次生效保证，官方不支持 Windows | 不修保留重复副作用。**采用现有生命周期，拒绝桌面 Celery** |
| F04 缓存/日志/解码资源上限（A6 F–I） | file_cache / asset_thumbs 原入口补字节预算、失效通知、后台解码及可恢复归档 | cachetools 可提供 LRU/TTL，但不解决本项目文件签名失效、图片解码线程或未知费用记录保留 | 无需为治理先换库。**采用现有有界化；延后 cachetools，拒绝新增 Redis 桌面服务** |
| F05 UI 渲染与包/工具边界（A1/A5/A6 H） | 先复用 Tk 页面，虚拟化可见项、去主线程 IO、保持 CLI/动态注册/分发闭包 | PySide6 Model/View 可在 U0 比较；Pyzed 身份/支持矩阵未完成核验，不作为当前迁移依据；两者均不消除越层依赖 | 不新增框架仍能先修边界。**采用现有解耦；UI 框架延后 U0，拒绝 A8 全面换 UI** |
| F06 云端账号/会员/API/权威账本（A7） | 复用桌面路由及本地展示；云端从零手写认证/事务迁移成本高，且现有本地账本不可信 | Django＋DRF＋PostgreSQL 可复用认证、校验、迁移与事务约束，但支付/报价/幂等/对账仍是业务责任 | 当前无云立项，关闭平台收费入口可接受。**延后 C0/C1，保留云端候选；拒绝进入桌面运行时** |
| F07 中转供应商协议差异（A7 J） | 已兼容中转则继续现有 adapter；只补实测缺失端点及错误映射 | New API 或 LiteLLM 只能选所需一层：前者适合其原生管理/中转协议，后者适合确有多供应商规范化需求 | 没有供应商合同就没有选网关依据。**两者延后 C0；拒绝串联两网关和第二钱包** |
| F08 云端持久后台任务（A7 E/G） | 初期可用数据库任务＋outbox＋单个恢复 worker；量小且轮询短时不需要 broker | Celery 可承载已证实的跨进程持久调度/并发需求；需 broker、幂等 worker、重投/租约/恢复监控 | 云端未立项无需新增；若任务必须跨服务重启存活则不能继续仅内存线程。**条件性延后 Celery 到 C2** |
| F09 图片/视频/音频端点及计量（A7 J） | 分媒体保留上传/任务查单/下载/费用状态，适配器按能力显式拒绝不支持项 | 网关列出 chat/图片/语音/视频入口不证明该供应商所有操作；同步 TTS 不能伪装为异步任务 | 未验收能力不上平台目录。**采用逐媒体能力矩阵；延后所有未验证供应商映射，拒绝 chat 兼容代替验收** |

## D. 维护、支持、许可证与供应链核验
2026-11-18 在线核验官方页面/PyPI JSON/GitHub release；这里只是候选元数据快照，不是安全审计结论。动态网页和 main 不能代替固定版本许可证。没有下载/执行候选安装包。

| 对象 | 维护/支持事实与限制 | 许可证与供应链处置 |
|---|---|---|
| 已有 requests / urllib3 / Pillow 六包 | 生产精确锁如 B；本树借用随附 Python 3.14.7；锁文件与本机安装由白名单测试核验 | 本机 distribution 元数据：requests Apache-2.0、urllib3 MIT、certifi MPL-2.0、charset-normalizer MIT、idna BSD-3-Clause、Pillow 13.0.0 MIT-CMU（不沿用旧版 HPND 印象）；正式发布仍逐锁包核许可证文件、wheel SHA256、依赖闭包及公告，不能仅信项目名 |
| Tenacity / cachetools | PyPI 本次快照 9.2.1 / 8.0.1，Requires-Python ≥3.10 / ≥3.11；分别 2026-10-07 / 11-17 有发布 | Apache-2.0 / MIT；本轮不引入，避免为了很小的通用能力扩大依赖面；安全公告未审计，不声明无漏洞 |
| Django / DRF | PyPI 当前快照 6.1.3 / 3.18.3，要求 Python ≥3.12 / ≥3.10；Django 5.2 LTS 仍是可比较系列，官方列至 2028-04；DRF 只支持相应系列最新补丁 | 均 BSD-3-Clause。候选选支持交集，不直接安装 PyPI latest；认证配置、迁移与供应链更新仍需维护责任人 |
| PostgreSQL | 官方大版本支持五年；本次版本页列 18.7、17.12 等，19 RC2 是预发布不能当稳定基线 | PostgreSQL License；核服务商支持周期、镜像 digest、扩展许可证、备份恢复和安全公告；不能只锁 Python 驱动 |
| New API | 官方仓库有活跃发布；API latest 本次返回 `v1.0.0-rc.51`（2026-11-13），RC 身份不足以获准生产 | AGPL-3.0；正式选型须核 tag/LICENSE、网络服务义务和修改发布方式；不能把 AGPL 自动解释为禁商用，也不能忽略其义务。release 校验和不等于来源签名 |
| LiteLLM | PyPI 本次 1.110.0（2026-11-18），Python ≥3.10,<3.16；SDK/proxy 功能和依赖不同 | 根 LICENSE 说明非 enterprise 部分 MIT，enterprise 目录另有许可；不能只读 PyPI MIT 就把全部企业功能算免费/可再分发。核固定 tag、extras、镜像、依赖及安全公告 |
| Celery | 本次 5.7.0（2026-11-05），PyPI Requires-Python ≥3.10；stable 简介标题 5.7，正文支持表仍写 5.5.x，属于文档版本不一致，不能据此断言 3.14 全支持；明确不支持 Windows | BSD-3-Clause；正式云端版本须核对应 release 支持表、kombu/billiard 等闭包。broker 版本及许可证独立审查，不能把 Redis/RabbitMQ 当无成本附件 |
| SQLite / PySide6 / Pyzed（被比较但未选） | SQLite 已随标准库可用，但当前无文件事务替代必要；PySide6/Pyzed 按任务书 U0 专项核支持周期/Windows/Python/维护活动，本轮无精确版本批准 | SQLite 公有领域声明仍需分发来源核查；PySide6 LGPL/GPL/商业许可须按所用模块及分发方式审查；Pyzed 当前许可证/支持未核实，不能据候选名获准安装 |

来源（只摘录事实，资料不表示产品采用）：
- [Django 支持版本](https://www.djangoproject.com/download/)、[Django 5.2 发布说明](https://docs.djangoproject.com/en/5.2/releases/5.2/)、[DRF 要求](https://www.django-rest-framework.org/)。
- [PostgreSQL 版本政策](https://www.postgresql.org/support/versioning/)、[许可证](https://www.postgresql.org/about/licence/)。
- [New API 仓库](https://github.com/QuantumNous/new-api)、[本次 release API](https://api.github.com/repos/QuantumNous/new-api/releases/latest)。
- [LiteLLM 根许可](https://github.com/BerriAI/litellm/blob/main/LICENSE)、[虚拟密钥/预算](https://docs.litellm.ai/docs/proxy/virtual_keys)、[图片](https://docs.litellm.ai/docs/image_generation)、[视频](https://docs.litellm.ai/docs/video_generation)、[语音](https://docs.litellm.ai/docs/text_to_speech)。音频概览 `/docs/audio` 返回 404，已改查正式 speech 页面；不得由找不到旧页面推断整个音频能力不存在。
- [Celery 平台与组件要求](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)、[任务语义](https://docs.celeryq.dev/en/stable/userguide/tasks.html)。
- PyPI 元数据端点 `https://pypi.org/pypi/<项目>/<精确版本>/json`：Django/6.1.3、djangorestframework/3.18.3、celery/5.7.0、litellm/1.110.0、requests/2.34.2、cachetools/8.0.1、tenacity/9.2.1。

## E. 体积、资源、可测试性和退出成本
以下 byte 数来自官方发布元数据，**仅单个压缩制品大小，不是安装总量、依赖总量或 RSS**。没有本机安装性能测量；服务内存、并发吞吐、存储和运维人时均待 C0/U0 测量，不能编造“更轻/更快”结论。

| 对象/对应决策 | 体积与资源比较 | 可测试性 / 退出成本 |
|---|---|---|
| F01 复用现有 vs Tenacity | 本轮新增安装量 0；requests wheel 73,075 bytes 已在锁内；Tenacity wheel 32,310 bytes 虽小但多一个策略层 | 假 opener/本机 503/429 服务可计数、虚拟时钟测 deadline；保持 HTTP 契约，回退单提交成本低 |
| F02 文件事务 vs SQLite/ORM | 不新增包；数据库额外日志/锁与文件双写补偿并存，不能用库文件体积掩盖迁移成本 | 临时项目逐写点断电/ENOSPC/权限注入；文件格式不变退出较低，数据库迁移后退出要导出重建及双向验证 |
| F03 生命周期 / F08 Celery | 桌面线程代次方案不新增服务；Celery wheel 519,594 bytes 不含 worker/broker/result backend；云端常驻进程及连接池有持续成本 | 本地假调度器＋隐藏 Tk；云端 broker 重投/worker kill/重复结算/撤销后继续执行必须测。队列退出须停收新任务、排空/保留 unknown、导出任务身份 |
| F04 原缓存 vs cachetools/Redis | cachetools wheel 19,095 bytes；旧缓存仍需按 A6 字节预算；Redis 再增常驻服务/备份/许可工作 | 比较 same-stat 覆盖、驱逐及重新读取、峰值字节；保留原缓存接口，可清的仅可再生缓存，未决费用不能作缓存删除 |
| F05 Tk vs UI 框架 | 当前无新增包；未下载 Qt/Pyzed，安装/RSS/分发体积未知；先测控件数/解码/文本，避免误把 IO 当渲染问题 | U0 同硬件/同业务接口/同数据，冻结 A6 I 指标；迁移隔离页面可退回旧 UI，业务模型不携带 Qt/Tk 对象 |
| F06 Django/DRF/PostgreSQL | Django wheel 8,424,610 bytes、DRF 903,986 bytes，仅根包；PostgreSQL 平台安装包/镜像未定，无可诚实报告的总字节数；另计 DB/WAL/备份/池连接/迁移运维 | 真 PostgreSQL 临时实例测试并发预留/唯一幂等键/回滚，不能用 SQLite 通过代替；HTTP DTO 和账本导出稳定，ORM 散进领域会提高退出成本 |
| F07 New API | linux x64 release 二进制 143,175,945 bytes；Windows exe 145,142,784 bytes **不采用**；镜像/数据库/日志不在此数 | 固定协议回放、查单/取消/账单对账；只把它作适配服务，退出切换 adapter，保留旧远端 task/bill ID 直到结清 |
| F07 LiteLLM | Linux x64 wheel 43,839,005 bytes，Windows x64 45,269,598 bytes **不安装桌面**；不含 extras、tokenizer 模型、DB/proxy 资源 | SDK 与 proxy 分开测，关自动 fallback/retry 后验单 owner；退出保持本方 API，不把其 virtual key/内部价表当永久业务 ID |
| F09 分媒体适配 | 不新增通用任务框架；上传临时盘、响应/结果体、poll 频率、GPU 费用分别计量 | 每供应商/每模型/每媒体/每端点的矩阵，计量单位不能把秒/图片数/字符数折为 chat token；不支持就拒绝，替换 adapter 可逐能力回退 |

正式候选原型的测量口径：隔离 venv/容器先 `pip --dry-run --report` 求解锁树并保存哈希，统计下载制品合计、安装目录字节/镜像压缩与展开体积；同机空闲/峰值 RSS、进程数、连接数、CPU、上传临时空间、重启恢复耗时。包源码构建工具链、broker 与数据库、许可证履约和升级人时都计入成本；在这些数据缺失时维持“延后”，不以根 wheel 大小决定采用。

## F. 替代范围、精确版本选择与回滚（逐项）
统一 V0 规则：以立项验收日的官方支持矩阵与 Python/OS/数据库/供应商交集筛选稳定版本，排除 EOL、RC、yanked；核版本化 LICENSE/安全公告及完整传递依赖，固定 `==`、SHA256 或镜像 digest、Git tag 对应 commit，保留 SBOM/锁文件与许可证。若支持表和 metadata 不一致，固定 release 的测试证明之前不批准；不是“装 latest 看看”。版本变更须重新跑对应行为矩阵。

| ID | 替代旧能力与适配边界 | 精确版本选择方法 | 回滚策略 |
|---|---|---|---|
| F01 | 替换叠乘重试策略，保留 http_client API 与 L1 owner，不增旁路出口 | 现锁六包保持；升级逐包按 V0＋假服务总次数/Retry-After/取消；Tenacity 无选定版本 | revert 独立策略提交；unknown 单保持查询，不以回滚触发补发 |
| F02 | 替换 skill record/forget 非一致失败窗口，沿 L3 注入发布器，不废弃回收和旧项目读取 | 现源码提交锁定；SQLite 随解释器版本核验，无新增 ORM 版本 | 代码可 revert；已落盘新旧文件按事务恢复/回收记录处理，不能靠 Git 恢复用户数据 |
| F03 | 替换重复副作用及错误项目发布；保留 Desktop.async_ 入口和已 commit 成果 | 当前源码版本；Celery 桌面无允许版本 | 单消费者批次回滚，取消代次/operation_id 兼容，迟到任务不重新挂 UI |
| F04 | 替换无界增长/同步解码回落；不替换缓存/索引唯一真源 | 无新库；若实测仍需 cachetools，按 V0 与字节/线程安全行为选定补丁，不预批准 8.0.1 | 回退缓存策略，可再生缓存重建；不回滚/清理正式产物、回收及未决资金 |
| F05 | 替换局部慢页面而非全应用；L0–L3 维持无 UI 对象接口 | U0 才核定 PySide6/Pyzed 精确版本、平台 wheel/许可；A8 不锁候选 | 页面路由退回 Tk；保存格式与服务接口不变，停止新 UI 发布，不删旧入口 |
| F06 | 云端认证/API/事务基础能力从零复用；不替代本地项目/DPAPI，不把本地账本搬成权威钱包 | C0 比较 Django 5.2 LTS 与届时受支持系列，取 DRF/驱动/PostgreSQL 支持交集后 V0；当前快照仅候选 | 先 additive schema/API 兼容，回退服务镜像；破坏性迁移前备份和还原演练；账务不可回退抹账，需更正/对账 |
| F07 | 只替换重复供应商协议转换；不替代本方账号/钱包/报价/幂等身份，New API 与 LiteLLM 二选一或都不用 | 先供应商真实端点表，再按 V0 固定通过该表的版本；New API rc.51 不获生产批准，LiteLLM 1.110.0 未验收 | 配置开关按新操作切回旧 adapter；旧 task/bill ID 留在原 adapter 查询至终态，不迁移中途重提 |
| F08 | 云端进程内调度在持久任务需求成立时替换；保留本方任务表/outbox 为真源，任务消息只带 ID | Linux 云端独立 Python/ Celery/broker 组合按 V0；5.7 页支持表冲突需 release CI/原型解决，不套桌面 3.14.7 | 停收/排空/幂等重领，不 purge 未决队列；回退 DB worker，接受 at-least-once，业务唯一键保障单次结算 |
| F09 | 替换错误的全媒体能力推断，复用现有各媒体入口，不造统一万能协议 | 版本同时锁网关、供应商 API revision、模型身份和价格版本，逐能力复验 | 关闭失败能力或模型的新提交，继续查旧单/下载/对账；无静默跨 BYOK/平台切换 |

## G. 独立媒体验证矩阵与禁止外推
本轮按视频/图片/音频分别核验现有代码和假后端测试。**核验可以得出“缺失/未证明”，不等于三类能力全部通过**。没有选择真实中转商，也没有安装 New API/LiteLLM，因此两框架全媒体采购验收均未通过、保持延后。下面 U/P/M/C 四列不得由任何 chat 测试替代。

| 媒体 | U 上传 | P 轮询/恢复 | M 计量 | C 取消 |
|---|---|---|---|---|
| 视频 | `test_video.LocalAPITests` 验上传回执哈希绑定已发字节；本地 Comfy 假调用，不覆盖云端分片/URL 素材期限 | `VideoTaskIdRecoveryTests` 验任务身份恢复、旧图歧义；video_task_status 验未知态不盲重提；UI result_polling 仅是 UI 队列，不冒充供应商查单 | 通用 model_metering 验授权/发送/未知结算；未验证供应商视频秒数、分辨率/音轨费、取消账单 | 本地/UI 迟到处理不等于远端取消；供应商 cancel 回执、竞态和费用最终态未验收 |
| 图片 | multimodal_upload 只有附件分类；batch_frames 假后端本轮未覆盖真实参考图上传（Fake.upload 会报“不使用参考图”）；明确缺口 | batch_frames 假 prompt/history、失败镜重试/成功镜复用；已独立运行，不依赖 chat | 通用序列不是每张图/尺寸价格证据；供应商实际账单/重复结果计费未验收 | image_direct 的 stop 是本地 runner 中断；不能证明上游停止或退款，远端 cancel 未验收 |
| 音频 | `test_tts` 以假 opener 验 JSON 请求及二进制响应，当前 TTS 是文本输入；ASR/参考音色文件上传、大小和留存未验收 | 同步 speech 无 job polling；run_lines 验逐行中断续跑，不虚构异步 task_id；异步语音供应商须另测 | 现有本地计量/成本预览非权威账单；字符/秒/音色规格、失败/部分输出收费未验收 | TTS 批次 stop 只控制后续行；in-flight HTTP/云端取消、费用释放未验收 |

C0 每种媒体分别执行四组隔离假供应商＋供应商沙箱验收，记录版本、原始协议字段的脱敏摘要、请求次数及最终用量，至少：
1. U：本地合成小 PNG/短视频/短音频，MIME/大小边界、上传超时已受理、复用/过期/删除及跨用户拒绝；body 哈希绑定实际发送字节，上传与生成计费分开。
2. P：提交成功/丢响应、重启丢 task_id、按 client_operation_id 查回、轮询短暂 404/429/503、乱序重复回调、下载到期。未知受理不再次收费提交；到 deadline 不继续发新请求。
3. M：视频按秒和规格、图片按数量和尺寸、音频按字符/秒分别核报价版本、模型身份、稳定账单 ID，取消/失败/下载失败/部分输出均保留实际费用。重复 poll/callback 只结算一次，无用量不写零。
4. C：发出前取消零 submit；受理后取消返回“请求取消”与最终 cancelled 分开；完成与取消竞态、cancel 不支持、cancel 超时、晚到成功各验；不能把 DELETE 结果文件当取消生成。

真实供应商不支持某端点时按合同显式禁用该能力；不能给假的成功/免费终态。假供应商通过仅证明本方逻辑，沙箱/合同仍是上线条件。A8 未构造新框架或 mock-only 产品模块来制造兼容证明。

## H. 采用边界与不变量
- 中转协议决策顺序：供应商若已提供当前 Wan/Seedance/Comfy 或既有 HTTP adapter 支持的端点，直接复用该 adapter；若供应商本身由 New API 托管，仅实现必要的管理/调用 API 客户端，不再部署一套 New API。只有采购证据显示多上游协议转换形成真实维护缺口，才在 New API 与 LiteLLM 中择一验证；两者都不能完整覆盖所需上传/查单/账单/取消时，保留专用适配器或拒绝该能力。当前供应商/协议 revision 尚未确定，因此无从批准具体网关。
- 桌面保留 Windows/Tkinter/白名单六包、项目本地保存、BYOK、DPAPI、独立 ASR 子进程和现有 L1 HTTP/L3 发布入口。平台故障不阻断本地读写。
- 云端账号、权益、钱包、模型调用凭证独立；平台上游 key 不落桌面。New API/LiteLLM 的 key/budget/logging 只作技术限额与运维数据，财务真源只有本方一个账本。
- 每次收费只有一个提交 owner；网关 retry/fallback 与客户端重试不能叠加。受理 unknown 必须查询/对账，钱包预留不能按本地超时/取消随意释放。
- PostgreSQL 事务、Celery 重投、HTTP 幂等分别解决不同层面问题；跨 DB/消息/供应商边界要 outbox/唯一键/对账，不能宣称框架提供端到端 exactly-once。
- A6 冻结的启动、可见控件、字节预算、取消/回收/恢复目标继续作为后续测量输入，不因框架名字放宽。日志只白名单字段，不保存密钥、完整剧本或签名 URL。

## I. A8 验收与完成登记
| 任务ID | 来源/依赖 | 状态 | 车道与允许文件 | 验收证据 | 回滚/未完成说明 |
|---|---|---|---|---|---|
| A8 | 总任务书 A8；A1/A5/A6/A7，A4 供交接 | 设计/最小验证完成；不表示框架上线 | codex/architecture-a8-framework；本报告/evidence/R3416.json，合入 A7 两文档 | C 三选一；D/E 八维评估；F 逐项版本/边界/回滚；G 独立媒体核验；M 实测 | 双亲提交回滚用 `git revert -m 1 <本轮提交>`，同时撤销相对 A6 的 A7 文档接收及 A8 文档；只撤 A8 时另作精确文档反向提交。没有生产数据回滚 |

未实施项明确归属：F01–05 为 A9–A12/U0 后续输入；F06–09 云端落地与真实供应商验收归 C0–C4。延期本身是 A8 决策结果，不伪装为实现完成或当前阻塞。A5 无证据可删项保持不变。

## J. A9 精确输入（由父任务启动）
1. 基线：接收本轮双亲提交（完整含 A6/A7），不要只拣 A8 报告而漏 A7；读取 `tasks_round_3411_result.md` C、G、H、I、J、K 和本报告 C/F/H，再核对 L0/L1/L2/foundation 在途等价交付。
2. 首批目标：A4 H01/H02/H03/H09 的包限定名、相对/from-import、同 stem、包初始化、未知模块、动态注册目标及 TOOLS 运行组件分类。文件候选 `tests/architecture/_scan.py`、`_layers.py` 与实际消费守卫；开工重新 scope，按 ≤3 模块拆批，先坏样本后正例，不能扩大豁免/阈值。权威文档与生成索引需同批一致。
3. F01/F02/F03 对应 A4 H08/H05/H07：仅登记应受守卫的行为边界，接收原 owner 的生产交付；A9 不以框架选型为由重写 HTTP、事务、计量或后台生命周期。A6 E 的 GET9次/Retry-After、C 的 skill record/forget 失败窗口是后续行为验收反例。
4. 依赖边界：维持 requirements 六包与 dependency_whitelist；没有任何 A8 授权新增 Django/DRF/PostgreSQL/Celery/New API/LiteLLM/Qt/cachetools/Tenacity。云端/供应商/钱包/UI 迁移决策仍归 C0/U0。
5. 运行环境：本工作树缺 Python/FFmpeg，测试可借已核实的 `D:/漫剧制作助手/运行环境/Python/python.exe`，FFmpeg 仅加到测试进程 PATH。不得复制主树私有数据；`smoke_test.py` 默认已带隐藏探针，不接受自身 `--probe` 参数。
6. 验证：按 A9 实际变更跑适用架构/消费者验证；层级登记/启动/Tk 生命周期/删除等触发规则按 AGENTS §5 执行。A8 的定向通过和 docs/merge 元数据不能作为 A9 架构全绿凭据；全量欠账见 M，主干合入轮自行校验 N=M+1。

## K. 后续验收资产迁移
复用现有 test_http_client / test_l1_transport_requests、publication_transaction、stage_execution_service、batch_frames、video、tts、request_ledger 与后台生命周期测试。A6 精确故障点进入原有测试类，不创建平行测试基础设施。G 的供应商矩阵待 C0 有端点合同后再编写真实 adapter 契约测试；同步 TTS 与异步音频分别建案例，不复用 chat 通过数。候选 cloud DB 测试须真 PostgreSQL；Celery 须真 broker 故障测试，eager/mock 不能代替重投/崩溃验收。

## L. 交付与提交范围
本轮新交付为本报告和 `evidence/R3416.json`；另外仅接收 A7 的 `tasks_round_3414_result.md` 与 `evidence/R3414.json`。无生产源码/测试断言/requirements 修改，无依赖安装、外部付费、真实上传、消息发送、用户项目写入或 master/push 操作。

标准入口 `scripts/dev.py commit -m "R3416: 合入A7并完成A8成熟框架复用决策"`。Git MERGE_HEAD 使现有证据生成器写 `merge-ci-exit` 标识；该自动标识不等于本轮实际运行了 local_ci.py exit，本轮真实命令与边界以 M 为准，未用它宣称完整架构通过。提交哈希按该唯一提交标题从 Git 解析并在最终交接报告，不在同一提交中写自引用哈希。

## M. 实测与失败闭环
环境：本树 `程序` cwd，Windows，随附 Python 3.14.7，PYTHONUTF8=1；Tk 经执行器隐藏桌面。所有媒体测试使用临时目录/假后端，不连接真实供应商。

- 默认冒烟首次 `smoke_test.py --probe` exit2（不识别参数）；源码 `smoke_test.py:627/745` 证明默认调用 `scripts/gui_hidden.py --probe`。纠正为 `smoke_test.py` 后 exit0、9/9；非跳过探针。
- 初次 `run_selftests.py -k video tts batch_frames multimodal_upload model_metering dependency_whitelist` 匹配 32 文件/41工作单元，范围过宽连带 UI 测试；非 GUI 部分出现下述 batch_frames 失败，后续等待他树 GUI 令牌。按本轮设计/最小验证范围主动中断该额外批次（退出1，无完整通过数），不抢占或终止他树 PID，不宣称该批次全绿；本树衍生进程已退出。
- 精确复验（仅测试进程 PATH 提供 FFmpeg）：`python -B -m unittest tests.test_video tests.test_tts tests.test_batch_frames tests.test_extra_batch_frames tests.test_multimodal_upload tests.test_model_metering tests.architecture.test_dependency_whitelist`，7文件 **131/131、0失败、0 skip、exit0，2.920秒**；这些具体用例无需创建 Tk 窗口。视频/音频/图片分别调用自己的实现与假后端，不由 chat 测试代替。图片远端取消等未覆盖项见 G；没有把纯契约测试当真实供应商兼容证明。
- batch_frames 首次失败及串行复现：`tests/test_batch_frames.py:183`，成功镜被报告“首帧图片损坏或解码器不可用”。串行 `-k batch_frames` 18 条、1失败、0 skip、exit1，排除仅凭 SUSPECT_CONCURRENCY 标签归咎并发。标准 PNG 经 Pillow 完整解码成功；`domain/keyframe_evidence.py:73–80` 强制调用 FFmpeg，而工作树无随包二进制。仅在测试进程 PATH 加入已核实的主树 `运行环境/ffmpeg/bin`，原测试原断言复验 18/18、0 skip、exit0（FFmpeg n9.0.2-57-gd838f9f9ae-20261116）。未改生产代码、测试夹具或共享环境配置。
- 完整架构未运行；精确复验中的 dependency_whitelist 为 **15/15、失败集合空**，不把 A0 的 532 条/失败集合当当前树总数，也不把子集当完整架构。源码改前后相同，完整架构通过/失败差异未测定。
- 安全全量未运行。`scripts/auto_full_safe.py --status` 实读：上次绿色 R3293，最新 R3415，其间源码轮次 23（线8），本功能树非主干不触发；最近后台全量 HEAD `0e3fc76`（2026-11-18 21:07:02）exit1，失败 test_shared_adapter_infrastructure、test_ui_edges_guards、test_pet_ui、test_perf_baseline。未改写绿色凭据，不把本轮设计完成解释为这些欠账清零。
- 收尾 `git diff --check`、前置祖先/合入文件核对、A–M 完整性与 F01–F09 决策字段检查通过；暂存白名单仅 L 列四个文档/证据文件，标准提交入口执行凭据扫描。提交完成状态以该唯一标题对应 Git 对象为准；最终交接报告实际哈希及干净状态。
