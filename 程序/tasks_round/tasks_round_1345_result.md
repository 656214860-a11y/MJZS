# R1345：O21 资产检索与候选墙完善可追溯性和批量决策

类型：功能轮（§3.1；本项为「建议」，本轮交付为实现＋回归）。承接 R1267 清单 O21（O01—O20 已完成）。中央轮次 1345。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k reference` 118/118；锚定 `-k asset_detail asset_plan asset_reference workflow_context skill_tools` 全绿（含 asset_detail 三组 Tk 用例）；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O21 关闭，清单剩 O22—O48；1345 − 1341 = 4 < 5，且未命中 §5 升级条件（非启动路径／Tk 控件生命周期／删除语义／`_layers.py`；`reference_wall` 只加列与状态栏文案，未改控件生命周期），本轮不跑全量。

## 目标（R1267 清单 O21）
- 依据：`asset_reference_search.py` 已有许可归一、可用性筛选、评分、指纹去重与来源记录；`reference_wall.py:135` 用户确认后才下载入库。
- 建议：展示候选评分分项、许可依据链接/采集日期、同图不同源关系、适用职责；「来源写入」与「许可已核验」分开，来源失效也能查当时记录；可批量比较，但不以相似分代替用户采用。
- 验收：缺许可、来源冲突、重复图、低分图各有可解释状态；剔除候选不影响已入库资产；没有断言现有版权过滤缺失。

## 实现（`asset_reference_search.py`）
- 评分分项：新增 `score_parts(candidate, asset)`，把总分拆成「清晰度／提示词命中／构图比例／来源完整度／许可」五项，每项给 `{label, points, note}`；`score()` 改为由分项派生 `reasons`，总分与理由与旧口径逐字一致（既有用例不变）。
- 许可依据与采集日期：`normalize` 新增 `collected_at`（取 `collected_at`/`fetched_at`/`date`），`license_url` 保留；`_credit` 记录新增 `collected_at`（`license_url` 原已记录）——入库后来源页即使失效，当时记录仍可查。
- 同图不同源：`rank` 不再丢弃同指纹的其它来源，落到条目的 `alts`（url/page/author/license/commercial/collected_at）；`conflict` 标记同图多来源在「商用性／许可名」上是否打架。
- 可解释状态：新增 `STATE_NOTES`／`_state`／`explain`，逐条给 `state`：`missing_url`／`missing_source`／`missing_license`／`low_score`／`non_commercial`／`source_conflict`／`duplicate`／`adoptable` 与人话 `note`；`rank` 条目带 `state`/`note`/`conflict`/`alts`。
- 低分／重复说明：新增 `suppressed(candidates, asset, threshold)`，列出被阈值或同图去重挡在图墙外的候选及状态（低分＝`low_score`、同图落后分＝`duplicate` 并指向保留来源）。

## 实现（`reference_wall.py`）
- 图墙新增四列：`许可依据`（license_url）、`采集日期`（collected_at）、`状态`（note）、`同图来源`（alts 个数）；既有列顺序不变（score/license/commercial/title/page/reasons 仍是 0–5）。
- 状态栏追加 `search.suppressed(...)` 计数（低分／同图重复／缺许可／缺来源／缺地址／不可商用），说明「为什么有些候选没显示」；右键剔掉的候选不计入。
- 勾选与入库路径不变：默认只勾「可商用且版权可用」，仍需用户点「确认入库」；批内勾选不自动采用。

## 验证
- `tests/test_reference_search.py` 新增 `ScorePartsTests`（分项结构、总分＝分项和、`score` 与分项一致）、`ExplainTests`（缺地址／缺来源／缺许可／低分／不可商用／可入库六态＋note 说明）、`TraceabilityTests`（许可依据与采集日期随条目、同图不同源记进 `alts`、许可冲突标 `source_conflict`、同许可不算冲突）、`SuppressedTests`（低分、同图落后分指向保留来源、缺许可、已上墙不重复列）、`CreditTraceabilityTests`（credit 记 license_url／collected_at／来源页；`rank`／`suppressed` 对已入库资产只读）。
- `tests/test_reference_wall.py` 新增 3 条：图墙显示许可依据与采集日期列；同图冲突只展示一条且状态列提示「不一致」、同图来源列显示 `1`；右键剔除候选后 `assets.json` 字节不变（不影响已入库资产）。
- 定向 `-k reference` 118/118、锚定 `-k asset_detail asset_plan asset_reference workflow_context skill_tools` 全绿、架构 312/312、默认冒烟 8/8，0 红。

## 边界
- 「适用职责」仍由用户在「参考用途」里选：不从标题／标签猜职责，避免把相似度当采纳依据；程序只把用户选的职责随图记进 `assets.json.reference_roles`（既有行为）。
- `alts`／`conflict` 只在同一次候选清单内成立（同指纹＝同标题＋同尺寸＋同作者）；不同批次的「同图」不做跨批比对。
- 缺许可／缺来源的候选不会入库（沿用既有 `usable` 门槛）；剔除只影响本批结果，不删除已入库资产（`suppressed`／`rank` 全程只读）。
- 未命中 §5 升级条件；`asset_reference_search.py`／`reference_wall.py` 均无裸 `json.loads`，架构台账未平移。`reference_wall` 仅加列与状态栏文案，未改 Tk 控件生命周期。
- 未实发检索／下载网络请求、未重启应用、未真实点击界面（图墙 3 条 Tk 用例已在 Tk 下跑过）。

## 风险与边界
- 采集日期依赖候选清单里带 `collected_at`／`fetched_at`／`date`；离线清单没有该字段时显示「（未记录）」，不代表没有采集过。
- 同图判定基于「标题＋宽高＋作者」指纹，是同源近似而非内容哈希；改名或改尺寸会被视为不同图（既有语义）。
- `conflict` 只在「商用性或许可名」不同时为真；同许可不同 `license_url` 不判冲突（避免把站点差异当矛盾）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] 资产检索与候选墙完善可追溯性和批量决策：`asset_reference_search` 新增 `score_parts`（清晰度/提示词/构图/来源/许可五项分项，`score` 由分项派生且口径不变）、`explain`/`_state`/`STATE_NOTES`（缺地址/缺来源/缺许可/低分/不可商用/来源冲突/重复/可入库八态＋人话说明）、`suppressed`（低分与同图重复逐条解释）；`rank` 记同图其它来源 `alts` 与 `conflict`；`normalize`/`_credit` 增 `collected_at`（许可依据 `license_url` 原已记录，来源失效仍可查当时记录）；`reference_wall` 新增许可依据/采集日期/状态/同图来源四列并在状态栏说明挡下的候选，剔除候选不影响已入库资产；新增 search 16 条＋wall 3 条用例，定向 118/118、锚定全绿、架构 312/312、默认冒烟 8/8，0 红；1345−1341=4<5 且未命中 §5，本轮不跑全量。
