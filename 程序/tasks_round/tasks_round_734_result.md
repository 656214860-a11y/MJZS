# R734 结果｜冻结第 1、2 项架构试点

**轮次类型：** 契约轮。文档与门禁随契约有意变更同步；未改产品 `.py`、未改变两个试点行为、未改 `AGENTS.md` 2.2 的“路径”行，也未弱化既有断言。

## 冻结决定

- 第 1 项“服务返回值契约”状态为 `paused`：仅 `delivery_import_service` 与 `keyframe_lifecycle_service` 是 `service_contract` 四字段结果试点；L2 登记表共 37 个模块，其余 35 个登记为待迁移豁免。
- 第 2 项“项目上下文对象”同样暂停：仅 `delivery_import_service` 采用注入的 `ProjectContext`，其余 36 个 L2 模块登记为豁免。
- 解冻条件：第一批第 3、4 项的基数台账 `items` 均清空后重新评估；重启迁移时以豁免数为分母，每轮最多 3 个 service。

## 门禁与文档

- 新增 `test_only_frozen_l2_adopters_import_service_contract`：范围严格限制为 `_layers.LAYERS` 登记为 L2 且有实际源码的模块，断言导入 `service_contract` 的采用方集合恰为两个试点；原有两个试点行为断言和 L0 层级断言均保留。
- `维护记录/架构统一基数.json` 已登记第一、二项的暂停时间、采用方、豁免数及由 L2 登记表机械导出的豁免清单。
- `AGENTS.md` 与 `architecture.md` 同步改为“试点、暂停、豁免、解冻条件”口径；路线图 v2 已登记用户裁决 A。

## 验证与基线

| 检查 | 结果 | 耗时 |
|---|---:|---:|
| `python run_selftests.py -k service_return_contract agents_md --safe` | 12 条 / 0 红 | 0.7 秒 |
| `python smoke_test.py` | 8/8 | 约 0.8 秒 |
| `python smoke_test.py --architecture` | 133/133 | 25.5 秒 |

按 R732 分档规则，本轮尚非“每满 3 轮”、不收口路线图条目、非发布前且用户未明确要求，**不跑 `run_selftests.py --all --safe`**；距 R731 全量为 3 轮（R732–R734）。
