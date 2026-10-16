# 数据模型字段字典（程序侧）

本文件是**投影**，不是权威定义。字段的权威源是写入方模块与 `artifact_schema.REGISTRY`；本文件只回答
「这个产物/文件里有什么键、谁写的、谁读的、缺了会怎样」。字段增删以代码为准，本文件随之更正；
两者不一致时先核验代码，**不要按本文件改代码**。

## 0. 按什么顺序查

1. 版本化产物：`artifact_schema.REGISTRY`（kind → 版本／必备字段／写入模块／历史键）。
2. 队列与历史台账：`desktop_automation_service`（写入）＋ `task_center_service`（只读投影）。
3. 费用与 Token：`pet_llm.Ledger`（Token）与 `pet_llm.RequestLedger`（逐笔金额）。
4. 宠物通知与事件：`pet_agent.NOTICE_PATH` / `JOURNAL_PATH`。

## 1. 版本化产物（`artifact_schema`）

写入侧一律经 `stamp(kind, payload)` 落 `schema_version`；读取侧用 `validate(kind, payload)` 拿问题清单
（返回列表、不抛异常）；历史产物用 `migrate(kind, payload)` 抬版本（**只加键、不删数据**）。当前登记：

| kind | 版本 | 必备字段 | 写入模块 | 历史键 |
| --- | --- | --- | --- | --- |
| `desktop_queue` | 1 | `tasks` | `desktop_automation_service` | `version` |
| `continuity_ledger` | 1 | `stage` | `continuity_ledger` | `version` |
| `continuity_issues` | 1 | `issues` | `continuity_ledger` | `version` |
| `animatic_manifest` | 1 | `kind`、`source` | `animatic_service` | `version` |

未登记类型直接 `KeyError`（「新产物须先在此登记版本与必备字段」）；`registered()` 是给本表与测试对齐的清单入口。

## 2. 后台任务队列台账 `outputs/desktop-task-queue.json`

- 归属：kind＝`desktop_queue`；写入 `desktop_automation_service.PersistentBackgroundTaskQueue`；
  路径由 `desktop.Desktop.__init__` 注入（`程序/outputs/desktop-task-queue.json`）。
- 顶层：`{"version": 1, "tasks": [...]}`（历史键 `version`，由 `artifact_schema` 兼容读取）。

| 行字段 | 含义 |
| --- | --- |
| `id` | 队列自身 uuid4 hex（重开程序仍认它是同一件任务） |
| `kind` | 任务类型；必须是已注册的可恢复任务（`handlers` 里有才收） |
| `payload` | 纯 JSON 参数（入库前 `json.dumps/loads(allow_nan=False)` 深拷贝；回调与活 UI 对象永不落盘） |
| `label` | 给用户看的一行字 |
| `priority` | 越小越先（与内存里的临时项一起排序） |
| `created` | 入队时间戳（`clock()`） |
| `expires_at` | 过期时刻，到点由 `_expire` 置 `expired`；可不填 |
| `state` | `queued`／`claimed`／`completed`／`expired`／`cancelled`（见 `task_states.md`） |

写入语义：`transaction()` 包住「读—改—写」；`enqueue_descriptor` 先 `_expire` 再判 `QUEUE_LIMIT`；
`_finish` **只对 `claimed` 生效**。

## 3. 任务历史 `outputs/desktop-task-history.json`

写入 `desktop_automation_service.BackgroundTaskLifecycle`（桌面「单一主动后台任务」的代次、取消与收尾判定）。
它记的是「哪一代结果还算数」：`_load` 把 `state in ("queued", "claimed")` 的行当在途，其余当历史（`HISTORY_LIMIT = 20`）。

## 4. 任务中心只读投影（`task_center_service`）

`project_snapshot(project)` 返回 `{project_id, tasks[], stages[], errors[]}`；`project_id` 取 `config.json`
的 `project_id`，缺失时退化为 `legacy-path:<指纹>`（不按路径猜同名项目）。`tasks[]` 一条一个「任务×版本」：

| 字段 | 来源 |
| --- | --- |
| `run_id` | 记录 `execution.run_id`（哪一次运行） |
| `attempt_id` | `execution.attempt_id`；历史缺失时退 `local_request`，再退 `legacy:<指纹>` |
| `task_id` / `remote_task_id` | 本地镜头或资产编号 / 供应商任务号（记录的 `task_id`、receipt 的 `prompt_id`） |
| `stage` | 来源台账：`assets` / `video`（配合 `pet_bus.STAGES` 对齐） |
| `state` / `source_state` | 归一后的状态 / 台账原话（`imported`、`downloaded`→`recorded_ready`；`failed`、`rejected` 原样；其余→`reconcile`） |
| `version` | 记录自己的版本号（同一镜头多版本时用于对账） |
| `artifact` | `file` / `output_dir` / receipt 的 `files` |
| `receipt` | `record.record`（回执文件名） |
| `timings_s` | `attempt_timings(record)`：只相减已有时间戳，轮询看到的排队耗时不算供应商耗时 |
| `reason_code` | `error_code`；没有就用 `state` |
| `retry_reason` | `retry_reason`；历史缺失写「历史未登记」 |
| `cost` | 按 `money_request_id` 关联 `request_ledger` 的逐笔金额 |
| `reason` | `error` / `note` 经 `app_logging.redact` 脱敏并截 300 字 |
| `recovery` | 该来源的下一步口径（资产＝接续取回；视频＝查任务号，未知状态不重提） |

`stages[]`：`{stage, recorded_state, blocked, waiting_for, reason, authority}`。`errors[]` 只放投影自身的问题
（读取失败、格式错误），不猜测、不掩盖。

## 5. 费用与 Token

- Token 台账（`pet_llm.Ledger.record`）：`entries[] = {at, model, tier, prompt_tokens, completion_tokens, cached_tokens}`；
  `tier` 用来算 Flash 占比，`cached_tokens` 用来算缓存命中率。
- 逐笔金额（`pet_llm.RequestLedger`）：`id` 即 `money_request_id` 的关联键。两条不变量（R1615）：
  ① `price()` 的总额＝分项和——分项各自四舍五入后**不得再对总和对角四舍五入**（原来会差 1e-4）；
  ② `_model_price()` 缺模型／版本／币种时返回 `None`，**绝不补零**。

## 6. 宠物通知与事件日志

- 通知：`pet_agent.NOTICE_PATH`＝`工作流任务/宠物/通知.json`。
- 事件日志：`pet_agent.JOURNAL_PATH`＝`工作流任务/宠物/事件日志.jsonl`（追加式；`KEEP = 50` 只留最近若干条，
  日报／周报按它说话）。

## 7. 未纳入本表的格式（诚实边界）

资产批量记录（`workflows/资产批量记录.json`）与视频镜头台账（`data/state.json`、`cloud_video/*/data/state.json`）
的字段以各自写入方为准；本表只冻结「投影层读到什么」。私有格式（连接收据、缩略图索引等）不在此重复登记：
它们没有跨模块读者，重复登记只会先于代码过期。
