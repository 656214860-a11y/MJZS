# R3994 结果文件
<!-- round-evidence: {"commit_base": "8ca777e9", "credential_hits": 0, "evidence_sha256": "44619cfce2c7ef7c", "exit": 0, "failed": 0, "passed": 0, "round": 3994, "tests": "docs-only"} -->

## 三问

- 本轮属于哪种类型：只读盘点轮（任务卡 EC-4「其他编码体系的取值、产生处、显示处」，车道 codex/ec-inventory）。
- 测试跑了吗、三个基线各是什么结果：未跑。任务卡是只读盘点轮，不改任何 `.py`/`.pyw`，卡片不要求测试；默认冒烟 / 架构门禁 / 全量三个基线本轮均未运行。
- 欠账少了吗：少了——§2.3「另有至少 5 套编码、与登记表的关系没有文档」这条欠账本轮补齐文档（盘点报告三张表，实际盘到 6 套体系加若干同名字段，行号均实测）。映射对照表与完整性测试归 EC-5（待补卡）。

## 改了哪些文件

- `tasks_round/错误代码体系盘点报告.md`（新增）：表A 六套体系的取值／产生处／显示处／用户原文；表B 取值→登记表代码建议映射（含「—」语义缺失清单，未自造码名）；表C `ServiceResult.data['error_code']` 读写实况。
- `tasks_round/tasks_round_3994_result.md`（本文件）。

未改任何 `.py`、`.pyw`、测试、配置。

## 盘点要点速览（详见报告）

- A1 启动自检码：15 个 L1 码 + 3 个 L0 码 + `selfcheck-skip-<族>`；FATAL 走 `MessageBoxW` 弹窗，DEGRADED 走状态栏【警告】一条。
- A2 `reason_code`：`model_router.failure_policy` 闭集 7 值，只驱动内部重试不直接显示；`task_center_service` 投影同名 `reason_code`（供应商码/状态名）显示在「运行状况」弹窗。
- A3 `provider_failure_reason`：按终态产三条恢复说明；另有 `task_status` 12 态 + `error_kind` 7 类在页内状态行显示。
- A4 `error_code` 字段：唯一写方 `infra/http_client`；读者只有 metrics 维度和 `tts_api` 判超时；UI 不读码，显示的是已拼好 `[E-XXX]` 前缀的 `reason`。视频版本的 `error_code` 是供应商原码，同名不同源。
- A5 三虎气泡：8 类目，类目→登记表码的桥已由 `TEXT_RULES`+`_CODE_TO_CATEGORY` 实现，仅气泡文案不走 `describe()`。
- A6 账户码：服务端 21 业务码 + 本地合成码，键名 `data['code']`（非 `error_code`）；页内 `say()` 显示，`SESSION_DEAD` 类码触发清会话。

## 验收命令结果

- `git status --short`（提交前）：仅 `?? tasks_round/错误代码体系盘点报告.md`、`?? tasks_round/tasks_round_3994_result.md` 两项未跟踪，无其它改动——符合「只能有报告和结果文件」。
- `git diff --stat $(git merge-base master HEAD) -- "*.py" "*.pyw"`：输出为空——符合「必须为空」。
- §8 行级验收：「盘点报告三张表齐全，每条带 文件:行号，没有改动任何 .py」——三张表齐全，行号实测，零 `.py` 改动。

## 未核实事项（报告内已标「未核实」）

- `result['failure']`/`attempts`（含 `reason_code`/`acceptance`）是否被诊断导出包携带阅读——检索未见界面读取点，未能确认是否有运维侧消费。
- 供应商侧 `error_code` 的全部取值——为自由文本（wan `out.code`、volcengine `error.code`），无法静态枚举全集。
