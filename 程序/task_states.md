# 任务状态与尝试链说明

三套「状态」经常被混着讲，先把边界划清（混用就会出现「明明是排队却报失败」这类结论）：

| 层 | 状态空间 | 权威源 | 谁在看 |
| --- | --- | --- | --- |
| 后台队列 | `queued`/`claimed`/`completed`/`expired`/`cancelled` | `desktop_automation_service.PersistentBackgroundTaskQueue` | 任务历史、重启后续跑 |
| 镜头／资产生命周期 | 在途 5 ＋ 已结算 6 | `video_lifecycle_service.UNCERTAIN_STATES` 等 | 删除前置门、重试、任务中心投影 |
| 重试判定 | 8 个错误类目 | `pet_agent.VERDICTS`／`classify`／`retry_plan` | 自动重试、日报／周报 |

## 1. 后台队列状态机

```
queued --pop--> claimed --_finish--> completed
   |                 |
   |                 +--(处理器抛异常) 不回滚：保持在途，等人工核实（绝不自动重提）
   +--expires_at 到点--> expired
   +--cancel--> cancelled
```

禁止转移（R1617 全转移表冻结，`tests/test_state_transition_tables.py`）：`claimed` 不能被 `cancel`；
`_finish` 只认 `claimed`；`clear()` 只清排队项、不动在途项；未领取不得直接收尾。

重开程序后在途项仍出现在 `unresolved()` / `unresolved_records()` 里：「在途＝要人工核实」，
不是「可以重跑」——处理器可能在抛异常之前就已经提交给供应商了。

## 2. 生命周期状态（视频镜头版本）

- 在途／结果不确定（`UNCERTAIN_STATES`，5 个）：`queued`、`running`、`submitting`、`unknown`、`succeeded`。
  `succeeded` 也在里面是刻意的：远端说成功 ≠ 本地已经取回归档，没落盘就不能当「已完成」。
- 已结算（6 个）：`downloaded`、`imported`、`failed`、`rejected`、`cancelled`、`""`（空＝历史缺状态）。
- 删除前置门（`video_lifecycle_service.mark_video_deleted`）：该镜头**任一版本**在途就拦下整镜头删除；
  测试同时断言「被拒集合 == 在途集合」「放行集合 == 已结算集合」。
- 词表有两份：模块常量 ＋ `tests/test_state_transition_tables.py` 里的冻结副本。改一处必须两处同步；
  冻结副本存在的理由是防止「用例直接拿被测常量当状态空间」这种空转（R1617 踩过）。

## 3. 尝试链：一条任务怎么被追溯

`task_center_service.project_snapshot` 把三层状态投影成同一张表，追溯靠这几个键：

| 键 | 含义 | 缺失时怎么办 |
| --- | --- | --- |
| `run_id` | 一次运行的编号（同一次「继续」里跑的一串步骤） | 保持未知，不按时间猜 |
| `attempt_id` | 一次尝试的编号（同一步的第几次提交） | 退 `local_request`，再退 `legacy:<指纹>` |
| `task_id` | 本地编号（镜头／资产） | — |
| `provider_task_id` / `remote_task_id` | 供应商侧任务号（`model_router` 从响应里取；记录里存 `task_id`） | 显示为空，取回时提示「先核实提交」 |
| `state` / `source_state` | 归一状态／台账原话 | 未知 → `reconcile` |
| `reason_code` | 原因码（`error_code`，没有就用状态本身） | — |
| `retry_reason` | 为什么重试 | 「历史未登记」 |
| `money_request_id` | 关联费用台账的逐笔金额 | `cost` 记 0，但口径要写明 |

一句话纪律：**未知不等于失败**。`unknown` 状态不许自动重提，投影里的 `recovery` 字段写明人工步骤。

## 4. 原因码与重试判定

`pet_agent.classify(error, status)` 是纯规则分级（不联网），类目与处置见 `VERDICTS`：

| 类目 | 可重试 | 动作 | 一句话 |
| --- | --- | --- | --- |
| `timeout` | 是 | `backoff` | 按 30／60／120 秒退避重试 |
| `rate_limit` | 是 | `backoff` | 退避后重试，Pro 自动降级 Flash |
| `server` | 是 | `backoff` | 服务端故障：退避后重试 |
| `params` | 是 | `fix_params` | 归一尺寸／时长／模型名后立即重试一次 |
| `content` | 否 | `prompt_fix` | 改写提示词后再提，别原样重试 |
| `quota` | 否 | `pause` | 暂停该阶段并通知，不再消耗 |
| `auth` | 否 | `notify` | 查 `.env` 里的 Key |
| `unknown` | 否 | `notify` | 走「重试失败项」或「查看待确认详情」 |

- 次数上限：`pet_agent.MAX_ATTEMPTS = 4`；退避档 `pet_llm.RETRY_DELAYS = (30, 60, 120)`，末档不翻倍。
- 纯数字标记按「独立的一串数字」匹配（`_mark_hit`）：退出码 `4294967295` 里的 `429` 不得被当成被限流。

## 5. 改动状态词表的检查单

1. 改模块常量 → 同步 `tests/test_state_transition_tables.py` 的冻结副本；
2. 新增状态 → 补进转移表（含禁止转移）与 `task_center_service` 的归一映射；
3. 跑 `python smoke_test.py --architecture` ＋ 定向 `tests.test_state_transition_tables`；
4. 改了展示口径 → 同步 `ui_components.md`、`README.md` 对应段落。
