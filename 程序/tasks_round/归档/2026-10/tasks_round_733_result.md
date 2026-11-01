# R733 结果｜架构统一第 3、4 项基数与棘轮契约

**轮次类型：** 契约轮（只改台账、测试门禁与文档；未改产品 `.py`，未迁移 service，未改既有 129 项断言）。

## 定稿审计

- 第 3 项：**1 个模块**，`delivery_import_service.py:import_final_master`。其 `publish is None` 分支将外部成片直接 `copy2` 到正式交付路径，保留为待接入发布器的唯一债务；`asset_batch_service`、`asset_detail_service`、`local_video_settings_service`、`white_model_service` 的 `copy2(..., temporary)` 均为临时文件操作，不计入。
- 第 4 项：用户给出的 71 是历史文本扫描起点；当前以 AST 定稿时，测试/说明性文本与非直接 `json.loads` 调用不计入，得到 **63 个读点/36 个文件**。指定五个纯网络响应文件继续固化为白名单（当前源码没有命中该精确调用形态）；混合点（`engine_probe`、`model_pool`、`stage_execution_service`、ComfyUI 批量工具及两处 SKILL 工具）均保留，待后续按正式项目数据/网络响应/临时文件逐项收口，不作臆测迁移。

## 本轮变更

- 新增 `维护记录/架构统一基数.json`，以“剩余清单长度＝count”记录两项分母。
- 新增 `tests/architecture/test_unification_ratchet.py`：不导入产品模块、不写盘；仅以 AST 和正则审计有限源码集合。新增债务、遗留已迁移台账项、或 count 与 items 长度不符都会失败。
- 新增仓库路线图 `维护记录/架构统一路线图_v2.md`，取代关系明确、删除全部进度叙述；第 3、4 项补完成判据，第二/三批每项补“本项目为什么需要 / 不做会漏掉什么”。
- `project_status.md` 已加路线图与基数指针，并推进为 **734 待执行**。

## 验证与基线

| 检查 | 结果 | 耗时 |
|---|---:|---:|
| `python run_selftests.py -k unification_ratchet --safe` | 2 条 / 0 红 | 1.7 秒 |
| `python smoke_test.py` | 8/8 | 0.8 秒 |
| `python smoke_test.py --architecture` | 132/132 | 26.8 秒 |

本轮为契约/跨层文档与架构门禁轮，按 R732 分档跑默认冒烟、定向棘轮与架构门禁；未触发完整安全全量。距 R731 的完整安全全量为 2 轮（R732、R733）；本轮不满足“每满 3 轮”触发条件。

## 轮数算术

- 第 3 项：1 个模块，按每轮最多 3 个模块，`ceil(1 / 3) = 1` 轮。
- 第 4 项：63 个读点分布在 36 个文件；按每轮 3 个模块，`ceil(36 / 3) = 12` 轮上限（实际可按同模块多点合并减少）。
- 两项可并行安排时，以较长链计，当前估算 **12 轮**；第 3 项可在下一执行轮收口。
