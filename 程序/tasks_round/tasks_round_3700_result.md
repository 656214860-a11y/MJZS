# R3700 结果报告
<!-- round-evidence: {"commit_base": "c3ecda48", "credential_hits": 0, "evidence_sha256": "9c3f9eda81fb8f8b", "exit": 0, "failed": 0, "passed": 0, "round": 3700, "tests": "docs-only"} -->

## 三问

- 类型：§3.5 只读诊断轮（任务书轮 I18 作业库选型）。
- 测试：诊断轮不跑测试；唯一改动为本结果文件（范围约束：只新增结果文件）。
- 欠账：少了——L1-H5 选型结论落档，I19 实施路径确定。

## I18-1　字段与语义对照表（I0-4 六份台账全覆盖）

| 台账 | 字段语义 | 维持现状 | 通用作业库（sqlite3） | Huey（SQLite 后端） |
| --- | --- | --- | --- | --- |
| #1 `阶段状态.json` | `updated_at`、`stages{state,reason,attempts}`、`elapsed/units/run_units`、六态机(pending/running/success/failed/retrying/skipped)、损坏按「未知」重观测 | ✅ 原生 | ✅ `job.state`＋`job.payload` JSON 列原样承载，`attempts` 映射重试计数字段 | ✅ `Task` 状态＋`data` 载荷可承载；六态→Huey 状态机可行 |
| #2 `事件日志.jsonl` | 事件 item（kind、时间、负载），只追加无状态机 | ✅ 原生 | ✅ `job_log` 附表（job_id,kind,at,payload）追加语义等价 | ✅ 事件可用 `Task` 元数据表承载 |
| #3 `资产续跑台账.json` | `attempts/last_try/next_try` 指数退避 `STEP*tries`、`state`∈waiting/stopped、读不出按空台账 | ✅ 原生 | ✅ `job.next_try`/`job.backoff`/`job.attempts`/`state` 直映射，stopped=终态标记 | ✅ `Task.retries`＋自定义 delay 可映射；stopped 需自定义终态 |
| #4 `sanhu_project_status.json` | checkpoint{stage,step,step_name,completed_steps,version,at,project,skills,digest}＋三重核对、版本不符须人工 | ✅ 原生 | ✅ `job.checkpoint` JSON＋`job.digest` 列承载核对语义 | ✅ 载荷可承载；digest 核对在应用层不变 |
| #5 `桌面续发/*.json` | 键 stage\|engine\|model；`skill_hash`、`materials{path:sha256}`、`mode`、`sent_at`、`task_file`、读不出按无记录 | ✅ 原生 | ✅ `job.idempotency_key`（复合键）＋`job.fingerprint` 载荷承载 skill_hash/materials | ✅ `Task` 唯一键＋载荷可承载 |
| #6 `资产批量记录.json` | job 条目 `state`、`record` 子记录路径、读回失败标 submitting 重试 | ✅ 原生 | ✅ `job.state`＋`job.parent_id`/`job.record` 子记录引用承载 | ✅ 子任务可用 `Task` 依赖关系承载 |

**A8 取证结论**：四类字段语义（attempt/next_try 退避、checkpoint+digest 核对、skill_hash+materials 指纹、state 子记录）全部可映射到通用作业状态机不丢字段 → **A8 成立**（三虎台账可映射，但按 A8 保护条款不改造三虎台账本身）。

## I18-2　执行模型与选型（L1-H5 自决）

L1-H5 判据逐项：

| 判据 | 维持现状 | sqlite3 通用作业库 | Huey |
| --- | --- | --- | --- |
| 覆盖 I0 全部字段语义 | ✅（现状即台账本体） | ✅（I18-1 全映射） | ⚠️ 可映射但需框架语义层适配 |
| 崩溃安全（WAL） | ⚠️ JSON 原子写已安全但无事务级联 | ✅ `PRAGMA journal_mode=WAL` | ✅ SQLite 后端同理 |
| 不新增调度线程 | ✅ | ✅ 作业执行复用 I10 `executors` 池提交，库内不含消费者线程 | ❌ **不满足** |
| 新增模块 ≤2 | 0 | 1（`infra/job_queue.py`） | 0（但引入三方依赖，违反白名单准入） |
| Huey 独立消费线程 | — | — | **A3 取证：Huey 作业模型要求常驻 consumer（`huey_consumer` 进程或等效消费循环）执行 `Task.execute`；SQLite 后端只解决存储，消费线程不可省 → A3 不成立 → 按任务书判据「不得选 Huey」淘汰** |

**选型结论：通用作业库（自研 sqlite3，`infra/job_queue.py`）**——理由：(1) Huey 按 A3 判据淘汰且引入非白名单依赖；(2) 维持现状不满足 B-17「断点续跑靠各阶段分散台账」的统一生命周期目标；(3) sqlite3 标准库零新增依赖、WAL 崩溃安全、执行复用 `executors` 池不新增线程、单模块达标。

**I19 影响**：按选型实现 `infra/job_queue.py`（L1）：`enqueue/dequeue/state/retry(backoff)/checkpoint/digest 核对原语`＋keyframe 以外或以内试点按 I19 规格；三虎台账只读映射不改造（A8 保护）。

## 备注

- 领号背景：I16 前因「分支领先 >10 源码提交」触发规则 27 领号门禁，R3690/R3696/R3699 三个合并轮已回合主干（I0–I16 全部入库 master，含 R3691 I16 预算引擎、R3693/95/98 出口 CI 与棘轮补齐）；主检出邻车道 299 个 `skills/` 未提交删除按原样保留未动。
- 烧号记录：R3692/R3694/R3697 三个号在合并窗口被领号流程烧掉（领号后提交被拒或他车道占用），结果文件分别由 R3693、R3695、R3698 承载对应内容。
