# R1337：功能轮——模型调用错误结构化分类（kind）并按类给用户提示

类型：功能轮（§3.1）。中央轮次 1337。来源：用户直接指定的任务书《模型调用错误分类（pet_llm.py／model_pool.py／desktop.py）》。用户未给出只读诊断报告路径与队列 ID，本轮按任务书逐条实施（信息缺口，照实记录，不补造报告）。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.1 功能轮（为模型调用失败新增结构化 kind，并让桌面按类展示文案）。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 `--affected pet_llm model_pool model_router desktop model_call_error_kind`：35 秒，0 个文件有红（含新增 tests/test_model_call_error_kind.py 14 条全绿）；默认冒烟 8/8；架构门禁 312/312 OK。全量未跑：本轮号 − last_full_safe_all_round 不满足 §5 的 ≥5，且未改动启动路径／Tk 控件生命周期／删除语义／层级登记表，不触发升级。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 前提更正（执行前核验，必须记录）
任务书称桌面 5 处消费点消费 model_pool／pet_llm 产生的 kind。核对数据流后有两处事实更正：
- **pet_llm.ask 不在桌面「剧本准备页对话」链路上。** 桌面对话为 desktop → stage_execution_service.reply_to_writing → writing_api.reply → model_router.PoolAdapter(ModelAdapter).chat → model_pool.http_transport；pet_llm.ask 的唯一生产调用方是 pet_agent（意图路由，pet_agent.py:366）。只改 pet_llm／model_pool 的话，桌面消费点收不到 kind。
- 若只改任务书点名的三个文件，桌面 1831／2051 的 kind 分支将永远落「缺失」，把「缺少 API Key」等原文替换成「系统内部错误」，属净回归。
因此本轮在点名的 3 个文件外补了 **1 个必要链路文件 model_router.py**（仅透传 kind，不动重试／降级），使桌面 1831／2051 真正按 kind 分类——这是路线图第 12 项「网络、文件和模型错误跨层传播」的最小落地点。另核实 1619／3956 并非模型调用错误（1619 为 extract_idea_brief 的本地 ValueError；3956 为 sync_stage_models 的本地 OSError 等），在各自桌面包内就地赋 kind（client／bug），避免把用户可处理文案误判为内部错误。

## 实现（按文件）
- `程序/model_pool.py`：`http_transport` 捕获处新增 `kind`，不改 `error`／`status`。新增私有 `_http_error_kind(status)`：401／403→auth，≥500→server，其余→client；`HTTPError` 用该函数，`URLError`→network，裸 `Exception`→bug。
- `程序/pet_llm.py`：新增 `import logging` 与 `LOGGER`。`ask()` 预算早退补 `kind="budget"`；`reply` 补 `kind=result.get("kind")`；外层 `except` 补 `kind="bug"` 并 `LOGGER.exception("模型调用异常")` 记录完整 traceback。
- `程序/model_router.py`：`ModelAdapter.chat` 超时→`kind="network"`、异常→`kind="bug"`、重建结果带 `kind=result.get("kind") or ""`；`stream` 取消→`kind="client"`、成功→`kind=""`。仅新增键，未改 `is_retryable`／三档升级链。
- `程序/desktop.py`：新增模块级 `model_error_display(result)` → `(文案, 是否只写日志)`：auth／budget／client→原文（log_only=False）；network／server→「模型暂时无法响应，请稍后重试」（log_only=True）；bug／缺失→「系统内部错误，已记录日志」（log_only=True）。4 处消费点接入：1629－1639（extract 失败，就地 kind=client）、1850 区（对话回复失败，按 kind 分支）、2076 区（刷新正文失败）、3980／3988 区（项目模型同步失败，就地 kind=bug）。log_only 时原文只写 `LOGGER.warning`，不进弹窗。
- `程序/tests/test_model_call_error_kind.py`（新增，14 条）：http_transport 的 auth／server／client／network／bug 各一条 + error/status 不变；pet_llm.ask 的 budget／透传／异常+日志；model_router 透传；桌面 5 类文案分支（含缺失）。
- `程序/维护记录/架构统一基数.json`：第四项 model_pool.py 两个行号锚点随 +13 位移重钉（568→581、605→621）。
- `程序/维护记录/TODO注释快照_20261003.json`：desktop.py 注释行号随插入位移重钉（2750→2782）。

## 范围与核验
- 生产改动 4 个模块（任务书点名 3 个 + 必要链路 model_router 1 个）。
- 未改 `is_retryable`（pet_llm.py:283 区）／三档升级链、`service_contract.py` 类定义、ledger／配额记账。
- 未改 `workflow_tasks.py`／`writing_api.py`／`stage_execution_service.py`；`git status` 无其改动。
- 桌面调用方式不变（仍读 `result.get("error")` 同一来源，仅展示文案按 kind 分支）；既有断言未改弱，新断言为新增。

## 验证（本轮实测）
- 定向：`smoke_test.py --affected pet_llm model_pool model_router desktop model_call_error_kind` → 0 红（35 秒）。
- 默认冒烟：`smoke_test.py` → 8/8。
- 架构门禁：首跑 2 红（test_todo_comment_snapshot 行号；test_unification_ratchet 第四项行号），随代码位移重钉上述两个登记表后复跑 312/312 OK。
- 全量未跑：见必答 2。

## 自审（§4.2）
1. 验收：kind 在传输层按 5 类产出；pet_llm 预算／透传／异常三处带 kind 并记录 traceback；桌面按类展示、原文只进日志——均达成，有 14 条定向用例覆盖。
2. 范围：生产 4 个模块；因前提更正扩了必要的 model_router（已说明）；未改测试断言迁就实现；未改用户数据；未动 `.agent-handoff/`。
3. 验证：定向、默认冒烟、架构门禁为本轮实测绿；全量未跑并注明理由。
4. 新问题：`kind` 为新增可选键，所有既有读者（读 `ok`／`status`／`error`）不受影响；`HTTPError` 之外的真·读取超时（socket TimeoutError）按任务书口径落 `Exception`→`bug`，若要更精确可后续单列 timeout 类（本轮未做，避免超出范围）。潜在残余：`http_stream` 未加 kind（任务书只点名 `http_transport`），流式失败回退到 `chat` 时会走 `chat` 的 kind，不产生错配。
功能轮追加：是否新增越界依赖？——desktop 新增 `logging`（stdlib）；model_router 仍只依赖同层 model_pool／pet_llm，未新增越界 import。

## 收尾提交
- 已提交；轮次类型：功能轮。提交首行：`R1337: 功能轮——模型调用错误结构化分类（kind）并按类给用户提示`。
- CODEX_STAGE_ALLOWLIST 显式列出：程序/model_pool.py；程序/pet_llm.py；程序/model_router.py；程序/desktop.py；程序/tests/test_model_call_error_kind.py；程序/维护记录/架构统一基数.json；程序/维护记录/TODO注释快照_20261003.json。
- project_status.md 不并入本提交（只有 master 可提交）。
