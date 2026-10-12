# R1369：O42 事件总线背压、异常有界与订阅释放

类型：功能轮（§3.1；本项「事实／风险」→ 有界化＋可观测，未改事件契约与订阅语义）。承接 R1267 清单 O42（O01—O41 已完成）。中央轮次 1369（主树含他人已暂存 WIP，故在干净临时工作树 `o42-claim` 调用 round_claim.py next 领取）。本轮 1369 − last_full_safe_all_round(1368) = 1 < 5，无五轮欠账；改动未命中 §5，收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_pet_bus_backpressure.py` 15/15；定向 `-k pet_bus pet_agent pet_state stage_flow skill_orchestrator` 186/186（含既有 `test_pet_bus` 18/18）；主消费者 `-k test_pet_ui test_pet_cloud` 606/606；架构门禁 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均 0 红。全量见「全量判定」。
- 欠账：O42 关闭，清单剩 O43—O48；1369 − last_full_safe_all_round(1368) = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O42）
- 证据：`pet_bus.py:98`（`Bus.__init__` 的 `self.queue = queue.Queue()`）无界 queue；`:124`（`pump`）每次有上限 `limit=200`、`history` 已有 `HISTORY_LIMIT=64`；`:154`（`_deliver`）`self.errors` 追加未在该路径限长。
- 建议：对高频进度合并、对关键终态可靠保留；错误使用有界环形摘要和持久诊断，提供队列水位与订阅释放；不要粗暴丢弃完成/失败事件。
- 验收：事件风暴、慢订阅者、关页重开、长时间任务，内存与界面延迟可测且受控。

### 前提核对（结论）
- 「queue 无界」属实：`queue.Queue()` 无 maxsize，`publish` 只 `put` 不设界。但**静态无界不等于线上已泄漏**——真实生产事件是里程碑式（每个 SKILL 步骤、每次阶段起手/收场各一条，见 `skill_orchestrator.py:419-484` 与各 `stage_*_service`），而界面每 150ms 心跳 `pump(limit=200)`，即约 1333 条/秒的消费能力；实测单条 `publish` 约 11 µs（见「测量」），生产者要不间断以约 9 万条/秒投递不同事件才可能追上不消费。本轮因此**不改成有损丢弃**，只做两件事：把「重复上报」在入队前合并（这才是能撑大内存的路径），并在极高水位时只让**进度／汇总**类事件让路。
- 「errors 无界」属实且是**真实可触发**的内存泄漏路径：只要某个订阅者每次分发都抛异常（例如关闭后的界面回调、坏掉的 lambda），`errors` 会随事件量无限增长。本轮把它改为有界环形＋累计计数＋持久诊断。
- 「订阅释放」在本项目**当前只读的调用图里未观测到累积**：唯一消费者 `pet_ui.core()` 在换项目时**整体重建** Bus（`pet_ui.py:993`）并把旧 Bus 交给 GC，同一 Bus 上不会重复订阅（`pet_state.subscribe`／`stage_flow.listen`／`Agent.attach` 都只在 `core()` 建 Bus 时各调一次）。本轮补 `unsubscribe`／`release` 作为明确 API 与关页/换项目语义，并按「不越权改 Tk」约束**未改 `pet_ui.py`**（该文件含需冻结行号的「暂时」注释，见「契约变化与同步」），故这一条是「提供并测试机制」，不是「修一个已发生的事故」。
- 「是否已产生卡顿」：本轮以合成风暴测量（见「测量」），未在真实 Tk 会话里做端到端卡顿观测。

## 实现
### pet_bus.py（L0）
- 新增模块常量：`PENDING_LIMIT = 1024`（待处理事件上限）、`ERROR_LIMIT = 64`（订阅者异常内存保留条数）、`ERROR_PERSIST_LIMIT = 128`（异常写审计日志上限）、`SHEDDABLE_EVENTS = ('stage.executing', 'notify.aggregate')`，与模块级 `is_sheddable(kind)`。
- `Bus.__init__(journal=None, seen_limit=SEEN_LIMIT, pending_limit=PENDING_LIMIT, error_limit=ERROR_LIMIT)`：新增 `pending_limit`／`error_limit`／`shed`／`errors_total`／`water`／`_queued`／`_lock`。既有 `queue`／`journal`／`seen_limit`／`touched`／`delivered`／`dropped`／`history`／`errors`／`_known`／`_seen`／`_subs` 名称与含义不变。
- `Bus.publish(item)`：入队前加两道**不阻塞工作线程**的背压——(a) 同一幂等键已在队列里就不再重复入队，记入既有 `dropped`（与 `pump` 的幂等去重同一语义、同一计数器，只是提前到入队前，避免重复条目占内存）；(b) 待处理数 ≥ `pending_limit` 且 `is_sheddable(kind)` 时让路并记 `shed`。**终态（stage.completed／stage.failed／script.completed／delivery.ready／各 `*task.failed`）与 stage.paused（它带并发号归还，见 `pet_ui.log_stage(release=True)`）不在 `SHEDDABLE_EVENTS` 内，永不因背压丢弃**；非让路类事件超过水位仍照常入队（水位对它们是软上限）。
- `Bus.pump(limit=200)`：出队即 `_dequeued(item)`（把幂等键从待处理表摘掉），其余（幂等丢 `dropped`、`_remember`、`history` 有界、`_write`、`_deliver`）不变。
- `Bus._record_error(kind, message)`：`errors_total` 累加，`errors` 只留最近 `error_limit` 条（`del self.errors[:extra]`），并在 `errors_total <= ERROR_PERSIST_LIMIT` 时落一份持久诊断 `bus.subscriber.error`（与事件同一份 jsonl，`pet_agent` 的 `skip`／`submit` 也记在这里）；`OSError` 只记一笔、绝不影响总线。
- 新增只读可观测面：`Bus.pending`（去重后的真实水位）／`Bus.stats()`（pending／water／touched／delivered／dropped／shed／errors／history）。
- 新增 `Bus.unsubscribe(kind, callback=None)`（只摘那一个或整类摘空，返回摘掉数）与 `Bus.release()`（清空全部订阅，返回摘掉数）：关页／换项目时把订阅释放干净。

## 契约变化与同步
- 事件契约 `CONTRACT`、`identify`、`event`、`emit_safe`、`stage_name`、`STAGES`／`STAGE_NAMES` 全部未改；未新增/删除任何事件类型。
- 既有可观测计数语义保持：`touched` 仍是「进入总线的条数（含被幂等丢掉的）」；`dropped` 仍是「幂等去重丢掉的条数」。`test_pet_bus` 的 `test_duplicate_report_is_dropped`（`touched==2`、`dropped==1`）与 `test_publish_from_worker_threads`（100 条、`dropped==0`）、`test_pump_respects_limit`、`test_history_is_bounded`、`test_subscriber_error_does_not_stop_the_others`（`errors` 仍等于那一条异常元组）全部照旧通过。
- 新增的是「方法」与「只读属性」：`unsubscribe`／`release`／`pending`／`stats()`／`is_sheddable`，以及 `publish` 在两种极端条件下的新副作用（重复合并记 `dropped`、水位让路记 `shed`）。默认参数、水位以下、非重复场景的入队与分发**逐字不变**。
- 未新增顶层模块／裸 `json.loads`／L2 直写盘／`skipTest`；`tests/architecture/_layers.py` 未动。**未改 `维护记录/架构统一基数.json` 与 `维护记录/TODO注释快照_20261003.json`**：`pet_bus.py` 无 todo/暂时/待补/后续再/先这样 关键词注释，覆盖率审计 20/21/24/25/26 对 `pet_bus` 的命中集为空，故新增行不引起行号漂移；架构门禁 312/312。
- **未改 `pet_ui.py`／`pet_agent.py`／`pet_state.py`／`stage_flow.py`／`desktop.py`**：`pet_bus` 的消费面（订阅与 `history`／`errors` 读取）语义未变，无需跟随改动；同时 `pet_ui.py` 含需冻结行号的「暂时」注释（2553/2801/2815/2988），在其之上的 `core()` 插行会破坏 TODO 注释快照，按最小改动原则不改。

## 测试（`tests/test_pet_bus_backpressure.py`，15 条）
- 重复与水位：同一条事件上报 5000 次 → `qsize()==1`、`pending==1`、`touched==5000`、`dropped==4999`；重复上报仍只送达一次且 pump 后水位归零；300 条不同事件在水位以下全保留且 `shed==0`。
- 终态不丢：`pending_limit=3` 顶满后 `stage.executing` 让路记 `shed==1`，而 `stage.completed`／`stage.failed`／`stage.paused` 照常入队并送达；`SHEDDABLE_EVENTS` 不含任何终态／`stage.paused`／`script.completed`／`intent.command`／`budget.exceeded`／`delivery.ready`。
- 可观测：`stats()` 的 `pending`／`water`／`touched`；pump 后 `pending==0` 而历史最高 `water` 只记不降。慢订阅者：入队不被订阅者拖住（`pending==200`、`delivered==0`），放开后一轮 pump 交付 200。长时间任务：2000 条边投边 pump，峰值 ≤ 12、`history` ≤ `HISTORY_LIMIT`、结束 `pending==0`。
- 异常有界与持久：`error_limit=3` 时 10 次异常 → `len(errors)==3`、`errors_total==10`；有 journal 时异常多出 `bus.subscriber.error` 一行且带 `event`／`error`；持久诊断按 `ERROR_PERSIST_LIMIT` 封顶（133 次异常只写 128 行）；无 journal 时不建任何文件。
- 订阅释放：`unsubscribe(kind, handle)` 只摘指定回调（其余照收、重复摘返回 0）；`unsubscribe(kind)` 整类摘空；`release()` 清空全部订阅后旧订阅一条都收不到、`delivered==0`。

## 测量（合成风暴，本机实测）
- 同一件事重复上报 200000 条：0.099 秒（0.50 µs/条），`qsize()==1`、`dropped==199999` → 内存不随重复上报增长。
- 不同事件 50000 条：`publish` 0.572 秒（11.45 µs/条）、`qsize()==50000`（受生产者事件数约束）；同一批 `pump(limit=50000)` 0.147 秒（2.95 µs/条）→ 界面每拍 200 条约 0.6 ms，远低于 150ms 心跳预算。
- 订阅者持续抛异常 20000 次：`len(errors)==64`、`errors_total==20000` → 异常不再无界增长。
- 结论：可撑大内存的两条路径（重复上报、异常累积）本轮已受控且可测；不同事件队列的规模由生产者的事件数决定（真实链路是里程碑式），未观测到线上泄漏，故不做有损丢弃。

## 边界
- 背压只对 `SHEDDABLE_EVENTS`（`stage.executing`、`notify.aggregate`）生效，且仅在待处理数 ≥ `PENDING_LIMIT` 时；被让路的是「这一刻在跑」与「汇总说一句」，会少一条 `logs/agent_logs.jsonl` 的 start 记录或一次通知汇总，但**不改状态机、不改并发号**。终态与 `stage.paused` 永不让路。
- 队列对**不同**事件仍是软上限（可按需超出 `PENDING_LIMIT`）；本轮没有引入「按容量硬丢不同事件」的策略，因为那会丢状态或漏还并发号。
- 订阅释放 API 已提供并测试，但**未接入 `pet_ui`**（见「契约变化与同步」）；当前调用图未观测到订阅累积，故这一条是机制与回归防护，不是事故修复。
- 未实机跑真实 Tk 会话的事件风暴；「卡顿」结论来自合成测量与服务层计数，不是端到端体验观测。
- `water` 是历史最高水位（只记不降），不是当前队列长度；当前长度看 `pending`。

## 全量判定
- 1369 − last_full_safe_all_round(1368) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；`pet_bus.py` 是纯标准库 L0，未碰 Tk）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1368、tree=dd48d82b…（2026-10-12，7 日内），但本轮改了 `pet_bus.py` 并新增测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：在干净 master 谱系工作树 `o42-fullsafe-master`（`git worktree add --detach 8a28e9a`，已预置 4 个嵌套仓库与 3 个被忽略运行文件、`git status` 干净；再把 HEAD 指向 `refs/heads/master` 使 `is_master_checkout()` 为真）跑 `--all --safe`：4887/4887、0 红、547.7 秒，并写凭据 `round=1369`、`tree=0ed4726bfd98c4835d61833a16ea7eabb81ecdb1`（＝报告提交 `8a28e9a:程序`，与当前 `HEAD:程序` 一致）、`at=2026-10-12T16:39:10`、`last_full_safe_all_round=1369`。4887 − 4872 = 15 即本轮新增用例数；`test_desktop_startup_perf`／`test_perf_baseline` 本轮均绿、无阈值抖动；未出现二次全量。

## 提交
- 本轮改动：`程序/pet_bus.py`、`程序/tests/test_pet_bus_backpressure.py`（新）、`程序/tasks_round/tasks_round_1369_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 内容提交 `c3ae62f`（只含 `程序/pet_bus.py` 与 `程序/tests/test_pet_bus_backpressure.py`；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：内容提交 `c3ae62f`（`程序/pet_bus.py`、`程序/tests/test_pet_bus_backpressure.py`）；报告与接力提交 `8a28e9a`（`tasks_round_1369_result.md`、`project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`）；收尾提交记入全量结果与提交号（沿用同一轮次 R1369，中央 `last_claimed` 仍为 1369）。
