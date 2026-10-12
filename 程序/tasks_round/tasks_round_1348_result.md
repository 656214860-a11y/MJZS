# R1348：O24「尚未开始先不拦」的兼容策略与正式自动生产分开

类型：功能轮（§3.1；本项为「事实/产品裁决」，本轮交付为语义分离实现＋回归）。承接 R1267 清单 O24（O01—O23 已完成）。中央轮次 1348。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k stage_parallel stage_flow pet_agent stage_completion` 192/192；`-k stage_gate` 18/18（含新 `test_stage_gate_modes` 14 条）；`-k todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 9/9；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O24 关闭，清单剩 O25—O48；1348 − 1346 = 2 < 5，且未命中 §5 升级条件（非启动路径／Tk 控件生命周期／`storage_maintenance` 删除语义／层级登记表；未新增顶层模块），本轮不跑全量。

## 目标（R1267 清单 O24）
- 证据：`stage_parallel.py` 的门禁保留「上游没开始就放行」逻辑（`evaluate` 及各 `*_ready`）。
- 建议：明确浏览／补录／旧项目兼容 与 正式自动生产 两种语义；用户可进页面查看，启动依赖生成时要明确哪些前置缺失、哪些是用户主动豁免。
- 验收：既不因严格门禁打不开旧项目，也不因「未开始」让无人值守跨过必需阶段；不能未经产品裁决把所有 True 改 False。依赖 O11、O18（均已完成）。

## 实现（`stage_parallel.py`）
- 新增两种口径常量 `BROWSE`（默认，浏览／补录／旧项目兼容）与 `PRODUCTION`（正式自动生产／无人值守）及 `MODES`。
- 结论分类 `PASS`／`UPSTREAM_BLANK`／`BLOCKED` 与 `verdict_label`；`_result` 增 `verdict`／`mode`／`exempt`／`missing` 字段（默认 BROWSE）；既有 `ok`／`started`／`detail`／`problems`／`artifacts` 语义不变，各 `*_ready` 判定口径一字未改。
- `_apply_mode(result, mode, project)`：只有「上游未开始」这一种结论在两口径下不同——浏览放行；正式生产下除非上游被用户显式标 `skipped`（`EXEMPT_STATES`／`upstream_exempt`）就算前置条件缺失（`ok=False`、`missing=(上游,)`）。真问题（上游做了没做全＝`BLOCKED`）两口径都拦。
- 门面 `evaluate(project, stage, *, mode=BROWSE)` 与 `production_ready(project, stage)`。
- `blocked_text` 对 `UPSTREAM_BLANK` 给生产口径文案（点明缺哪一步、怎么豁免）；`page_lines`／`audit_text` 文案区分「浏览放行」与「正式自动生产」。
- `ledger_ready`（SG-02）加固：仅当 `issue_gate` 真算出问题行且全部非待处理才放行，台账格式异常（算不出问题行）不再被静默放行。

## 实现（`pet_agent.py`）
- `Agent.gate(stage, *, mode=None)` 默认 `BROWSE`（不再随持久化档位漂移，旧项目／补录打得开）；异常兜底结果补 `verdict`／`mode`／`exempt`／`missing` 字段。`Agent.blocked_reason(stage, *, mode=None)` 透传口径。

## 实现（`pet_ui.py`）
- `Pet.gate_reason`（自动链的门禁）按「链是否在推」（`auto.armed`）选口径：无人值守链在推时用 `PRODUCTION`，否则 `BROWSE`；结构剧本 → 分镜 的历史豁免分支保留。新增 `import stage_parallel`。

## 验证
- `tests/test_stage_gate_modes.py`（新）14 条：默认浏览放行（`ok=True`／`verdict=upstream-blank`）、正式生产把「上游未开始」当前置缺失并点明缺哪一步与豁免办法、上游标 `skipped`＝主动豁免、两种口径只差「上游未开始」这一种、真问题两口径都拦、台账格式异常不静默放行、结论标签、页面／审计文案；`Agent` 默认浏览口径与档位无关＋显式 `PRODUCTION` 拦截＋`skipped` 豁免；`Pet.gate_reason` 链在推时要 `PRODUCTION`、浏览时 `BROWSE`、分镜历史豁免仍优先。
- `tests/test_stage_parallel.py` 两处桩函数放宽为接受可选 `mode` 关键字（断言不变）。
- 定向 192/192＋`-k stage_gate` 18/18；TODO 注释快照 `pet_ui.py` 行号 2792→2801 平移，`-k todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 9/9；架构 312/312；默认冒烟 8/8，全 0 红。

## 边界
- 不翻默认：`evaluate` 默认仍是浏览口径（`ok=True`），未把 True 改 False；只有无人值守链显式要正式生产口径。
- 正式生产只拦「上游未开始」这一种，且上游标 `skipped` 即视为用户主动豁免；上游「做了没做全」两口径都拦（旧行为不变）。
- 「豁免」只看阶段状态机的 `skipped`（用户在阶段面板主动标记），不猜、不从产物推断。
- 未命中 §5：未改启动路径、Tk 控件生命周期、删除语义与层级登记表（未新增顶层模块）。
- 未实发模型请求、未重启、未真实点击界面。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] 「尚未开始先不拦」的兼容策略与正式自动生产分开：`stage_parallel` 新增 `BROWSE`（默认，浏览/补录/旧项目）与 `PRODUCTION`（无人值守）两种口径及 `verdict`／`mode`／`exempt`／`missing` 字段，只有「上游未开始」在正式生产下当前置条件缺失（用户标 `skipped` 即豁免），真问题两口径都拦；`Agent.gate` 默认浏览口径不再随持久档位漂移，`Pet.gate_reason` 按自动链是否在推选口径；新增 14 条用例，定向 192/192＋门禁 18/18、快照棘轮 9/9、架构 312/312、默认冒烟 8/8，0 红；1348−1346=2<5 且未命中 §5，本轮不跑全量。
