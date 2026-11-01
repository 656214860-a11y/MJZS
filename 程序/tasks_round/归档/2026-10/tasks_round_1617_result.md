# R1617 生命周期状态机全转移表测试（Q8）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第二批 Q8）。
- 测试：定向 `tests.test_state_transition_tables`（12 项）＋`test_persistent_task_queue`＋`test_video_lifecycle_service`＋`test_pet_agent`＋`test_keyframe_lifecycle_service` 共 117/117 通过；架构门禁 354/354 通过（174.575 秒，与上轮同数：本轮新增用例在 tests/ 层，不在架构门禁内）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮新增测试文件，`project_status.md` 全量欠账计数 +1，未清。

## R1610 Q8 前提核对

Q8 原文"生命周期测试为场景式，未以表枚举允许／禁止转移"属实：`test_persistent_task_queue` 只试了"领取—重开—不重放"，`test_video_lifecycle_service` 只试了 `running` 与 `downloaded` 两个状态，`test_pet_agent` 只试了 4 个类目。三处都是抽样，没有"每个状态至少被覆盖一次"的断言，也没有反向（禁止转移）表。

## 新增 `tests/test_state_transition_tables.py`（三张表）

1. **后台队列**（`PersistentBackgroundTaskQueue`，状态空间 `queued/claimed/completed/expired/cancelled`）：10 条操作序列表，每条断言该行**落盘台账**的终态；含 3 条禁止转移——已领取不可取消、`clear()` 只清排队项不清在途项、未领取不得直接收尾（`_finish` 只对 `claimed` 生效）。另断言五个状态在场景里都被真实观测到，且在途失败后重开队列仍是 `unresolved()`（不自动重提）。
2. **视频删除前置门**（`video_lifecycle_service.mark_video_deleted`）：对 `UNCERTAIN_STATES` 全部 5 个状态逐一断言被拦下、对 6 个已结算状态断言放行，并断言"refused 集合 == 在途状态集合"；另断言任一在途版本即可拦下整个镜头。
3. **重试状态机**（`pet_agent.classify`／`retry_plan`）：对 `VERDICTS` 全部 8 个类目 × 4 个次数档（0／上限-1／上限／上限+3）断言"放行＝可重试且未达上限"，放行时 `next_attempt/delay` 与 `backoff` 一致、参数类立即重试（delay 0），终态则 `next_attempt` 不前移、不给退避；另断言退避序列 `30/60/120/120` 单调不减且末档不翻倍。

## 门禁非空转验证（变异测试）

新用例写完先做变异验证（只在内存打补丁、不改源码）：故意让 `cancel` 接受 `claimed`、**从 `UNCERTAIN_STATES` 删掉 `succeeded`**、给 `UNCERTAIN_STATES` 多加 `failed`、去掉重试次数上限——四种变异全部让用例变红，未变异基线为绿。

**这一步抓到真缺口**：第一版把状态空间直接取自被断言的常量 `UNCERTAIN_STATES`，删掉 `succeeded` 时"refused 集合"跟着一起少一个，用例仍绿（等于没测）。已改为在测试里冻结状态词表副本 `UNCERTAIN_VIDEO_STATES` 并断言与模块常量相等，故改动必须两处同步。这条经验记在这里：**状态机用例的状态空间不能取自被测常量本身**。

## 诚实边界

- 重试表是从 `VERDICTS` 派生的**一致性**锁定（判定表与转移结果不许分叉），不重新论证"哪些错误该重试"；"可重试类目＝params/rate_limit/server/timeout"这一具体名单由既有 `test_pet_agent` 断言，本文件不重复。
- 队列的"到期"转移用注入时钟驱动，不是真实等待；`_finish` 的禁止转移用私有入口驱动（该保护只存在于私有方法里，无公开等价路径）。
- 未覆盖：真实线程与进程被杀（既有 `test_persistent_task_queue` 用 `os._exit` 的硬退出用例管这一块）。

## 下一项

Q9（拆 5 个大模块＋统一运行期诊断到 `app_logging`）。