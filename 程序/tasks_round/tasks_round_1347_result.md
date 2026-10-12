# R1347：O23 连贯性问题形成从发现到解除的闭环

类型：功能轮（§3.1；本项为「建议」，本轮交付为实现＋回归）。承接 R1267 清单 O23（O01—O22 已完成）。中央轮次 1347。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k continuity stage_parallel confirm_gates` 124/124；`-k ui_edges todo_comment unification_ratchet desktop` 160/160（含 `test_desktop_startup_perf` 15.0 秒、统一棘轮 3/3）；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O23 关闭，清单剩 O24—O48；1347 − 1346 = 1 < 5，且未命中 §5 升级条件（非启动路径／Tk 控件生命周期／`storage_maintenance` 删除语义／`_layers.py` 层级登记表；闭环逻辑放在已登记的 `continuity_ledger` 里，未新增顶层模块），本轮不跑全量。

## 目标（R1267 清单 O23）
- 依据：`continuity_ledger.py` 的冲突（:93）／跨批（:154）／漂移（:193）与 `confirm_gates.py` 多类门禁已存在。
- 建议：每条问题有稳定 ID、涉及镜头/资产、证据、严重程度、处理决定及重新检查结果；人工忽略必须记录理由和作用版本；不要只堆一份新的问题报告。
- 验收：同一问题多次检查不重复新增；修复后解除；上游再变化可重开；不同批次同编号不串。依赖 O11（`confirm_gates.content_digest`）、O18（来源账本），二者已完成。

## 实现（`continuity_ledger.py`，末尾追加，未动既有行号）
- 结构化问题 `issues(ledger)`：把台账里没过的三类（三元组不一致／跨批次不一致／锚点漂移）与「职责自相矛盾」冲突逐条变成问题行，字段有 `id`／`kind`／`kind_label`／`severity`（冲突与三元组「高」，漂移与跨批次「中」）／`shots`／`assets`／`detail`／`evidence`／`digest`。
- 稳定编号：`CI-<kind>-<scope>`，scope 取批次号／资产编号／镜头号（同一镜多条冲突再带序号）。同一份台账算出来总是一样；批次号不同就不会串号。
- 登记表 `03_continuity/output/continuity_issues.json`：`issues_path`／`read_issues`；`merge_issues(register, current, *, now)` 纯函数输出 (新登记表, 报告行)，`sync_issues(project, ledger, *, publish)` 读台账→算问题→并入，只有注入 `publish` 才落盘。
- 闭环语义：同一编号不重复新增（首次发现记 `first_seen`）；本轮没有、原「待处理／已忽略」→ 置「已解除」；「已解除」再出现 → 重开「待处理」；「已忽略」的那一版证据变了 → 重开并清空决定；证据没变则保持忽略。每步写进 `history`（最多留 20 条）。
- 人工决定 `decide_issue(project, issue_id, decision, reason='', by='人工', *, publish, now)`：`ignored` 必须写理由，否则 `ValueError`；决定里记 `reason`／`by`／`at` 与作用的 `digest`（当时那一版证据）；`open` 用于撤掉忽略。
- 门禁口径 `issue_gate(project, ledger)`：只有「待处理」算没解决；已忽略与已解除都放行。

## 实现（`stage_parallel.py`）
- `ledger_ready`（SG-02）在 `ledger_gate` 没过时改用 `issue_gate`：所有问题都被人工忽略／已解除就不拦，否则照旧列未裁决待办。台账读不出来／还没生成时「先不拦」的兼容语义不变。

## 实现（`stage_execution_service.py`，末尾追加）
- L3 门面：`continuity_issue_report(project, ledger=None)`（只读）、`sync_continuity_issues(project, ledger=None)`（经 `agent.core.save` 落盘）、`decide_continuity_issue(project, issue_id, decision, reason='', by='人工')`。

## 实现（`desktop.py`，只在第 2753 行之后追加）
- 连贯性页新增「问题闭环」表：编号／类型／严重度／状态／涉及镜头或资产／证据（证据可点开看全文）。
- 「待办与裁决」区为每条「待处理」问题加「忽略（写明理由）」按钮：弹窗必须填理由，空理由不忽略；记录后刷新页面。
- 「手动生成连贯性清单」同一次把问题并进登记表。冻结关键词注释行号（2753）与既有控件生命周期未变。

## 验证
- `tests/test_continuity_issues.py`（新）20 条：稳定编号＋证据＋严重度、同一台账编号稳定、不同批次不串号、干净台账无问题；不重复新增、修好解除、解除后再现重开、忽略后证据变了重开且清空决定；忽略必须理由、决定记理由与作用版本、未知编号／非法决定拒收、重新打开清忽略；只读预览不写盘、注入发布器才落盘、无登记表读成空、门禁只拦待处理、修好清空、`stage_parallel.ledger_ready` 在忽略后放行。
- 定向 `-k continuity stage_parallel confirm_gates` 124/124；`-k ui_edges todo_comment unification_ratchet desktop` 160/160；架构门禁 312/312；默认冒烟 8/8，0 红。

## 边界
- 只报告与记录，不自动改分镜／资产：忽略只影响「这一步还拦不拦」，不改台账里的原始结论；人读版与三元组／锚点库发布不变。
- 忽略要人工点（弹窗填理由）；半自动／全自动不代替用户忽略问题（`auto_decide_gates` 只管 G-05／G-06／G-08 候选，不含问题忽略）。
- 「作用版本」是问题证据的 sha1 前 12 位（性质同 O11 的候选摘要），证据一变即失效，避免用旧理由放行新问题。
- 未命中 §5：未改启动路径、Tk 控件生命周期、`storage_maintenance` 删除语义与 `tests/architecture/_layers.py`。
- 未实发模型请求、未重启应用、未真实点击界面（`ui_edges` 的连贯性页用例在 Tk 下已跑过）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] 连贯性问题形成从发现到解除的闭环：`continuity_ledger` 新增结构化 `issues`（稳定编号 `CI-<kind>-<scope>`、涉及镜头/资产、证据、严重程度）与 `continuity_issues.json` 登记表（`merge_issues`／`sync_issues`／`decide_issue`／`issue_gate`）：同一问题不重复新增、修好解除、解除后再现重开、证据变化重开且清空决定；人工忽略必须写理由并记下作用版本；`stage_parallel.ledger_ready` 改用 `issue_gate`（忽略后不再拦）；`stage_execution_service` 补 L3 门面；桌面连贯性页加「问题闭环」表与「忽略（写明理由）」按钮；新增 20 条用例，定向 124/124＋160/160、架构 312/312、默认冒烟 8/8，0 红；1347−1346=1<5 且未命中 §5，本轮不跑全量。
