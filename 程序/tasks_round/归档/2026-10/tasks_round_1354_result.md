# R1354：O29 预算由多个计数器汇总为请求级可对账记录

类型：功能轮（§3.1；本项为「事实/建议」→ 实现＋回归，只新增请求级台账与只读汇总，不改预留/结算/重试/取消的既有业务判据）。承接 R1267 清单 O29（O01—O28 已完成）。中央轮次 1354。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k request_ledger pet_llm model_router pet_models_ui` 73/73；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O29 关闭，清单剩 O30—O48；1354 − 1351 = 3 < 5，且未命中 §5 升级条件（非启动路径／非 Tk 控件生命周期销毁重建／非删除语义／非层级登记表），本轮不跑全量。上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 目标（R1267 清单 O29）
- 依据：`engine.py` 按视频秒数预留；`skill_budget.py`、`pet_agent.Budget` 有不同计数；`model_router.py:527` 成功调用后记 token 台账；`model_pool.py:507` 连接探测真实发最小请求但不记账。
- 建议：先汇总请求 ID、调用种类、估计/实报量、预留/结算/未知，分别列 token、秒、次数，不把它们直接相加为金额；价格表可配置并标时间，探测也标“可能产生用量”。
- 验收：重试不会重复结算，同一远端任务关联唯一账单；缺 usage 明确未知，不显示为免费；取消不会伪造远端退款。无需此轮查询外部价格。

## 实现（`pet_llm.py`，L1）
- 新增 `REQUEST_LEDGER_PATH=('工作流任务','宠物','请求台账.json')`、`REQUEST_KINDS=('tokens','seconds','images','videos','requests')`、`REQUEST_STATES=('reserved','settled','unknown','cancelled','duplicate')`、`REQUEST_MODES=('estimated','reported','unknown')`、`request_ledger_path(project)`。
- 新增 `class RequestLedger`：
  - `reserve(request_id, kind, amount, *, remote_task_id=None, note='', at=None)`：以 `request_id+kind` 为键幂等预留，同一请求重试只占一次，不重复计账。
  - `link(request_id, remote_task_id)`：同一 `remote_task_id` 只认第一笔，后来的标 `duplicate`，保证「同一远端任务关联唯一账单」。
  - `settle(request_id, *, kind=None, amount=None, usage=None, mode='reported', ...)`：优先取 `usage['total_tokens']`，否则 `prompt+completion`；缺量则 `mark_unknown`，不把预留量当实报、不显示为免费；不重复结算。
  - `mark_unknown(request_id, *, reason='', at=None)`：实报缺失显式记未知态（`amount=None`）。
  - `cancel(request_id, *, reason='', at=None)`：只改本机记录，不写任何远端退款字段；已实报（mode=reported）保留 amount，未实报转 `unknown` 且 `amount=None`。
  - `report(price_table=None, currency='CNY')`：按 kind 汇总 `settled/reserved/unknown/count`，另列 `unknown_ids`／`duplicate_ids`／`cancelled_ids`／`requests`；token/秒/次数分列，**不跨量纲相加**；只有显式传入 `price_table` 才输出 `money`（含 `table_version`／`table_at`／`missing_rates`），默认不猜价。
  - `price(kinds, price_table, currency='CNY')` 静态换算；`save`/`load` JSON 往返。

## 实现（`model_pool.py`，L1）
- 新增 `PROBE_USAGE_NOTE='测试连接会真实发一次最小请求，可能产生用量'`；`probe(value, transport=None, program=None, timeout=8, ledger=None)` 增 `ledger` 参数，返回体带 `usage_note`；有 ledger 时对探测请求 `mark_unknown`（标「可能产生用量」，既不假装免费也不假装已计费）。

## 实现（`pet_models_ui.py`，LF）
- `probe_line` 成功文案追加 `（usage_note）`，让用户看见探测会真实发请求。

## 验证
- `tests/test_request_ledger.py`（新）11 条：幂等预留；重试不重复结算；usage 汇总与缺量未知；缺量不显免费；同远端任务唯一账单；取消不伪造退款；取消已预留转未知；分列 kinds；可选带日期价格表与缺费率；save/load 往返；探测标注「可能用量」并记未知。
- 定向 `-k request_ledger pet_llm model_router pet_models_ui` 73/73；架构门禁 312/312；默认冒烟 8/8；全 0 红。
- 台账：本次改动未新增裸 `json.loads`／L2 直写／未登记动态导入／顶层模块；`model_pool.py` 两处 HTTP/SSE 响应体解析行号仅平移（568→576、605→613），已在 `维护记录/架构统一基数.json` 第四项同步登记，disposition 仍为 `exempt`，架构各棘轮全绿。

## 边界
- 只做「汇总与对账」：不改 `engine`/`local_video` 的预留口径，不改 `model_router`/`skill_budget`/`pet_agent.Budget` 的计数逻辑；台账是并行新增的请求级记录，不替换既有计数器（避免行为回归）。
- 金额只在显式传入带时间的 `price_table` 时输出，且标 `table_version`/`table_at` 与 `missing_rates`；本轮未查外部价格、未内置价目。
- 取消语义只改本机：不写任何「已退款/已归还」字段，未知即未知。
- 未命中 §5 升级条件（非启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表；`pet_llm`／`model_pool`／`pet_models_ui` 均已在层级登记表内）。
- 未实发模型请求、未真实点「测试连接」；探测路径仅经单测覆盖。
