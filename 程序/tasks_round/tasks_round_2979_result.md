# R2979 结果：长列表基准口径修复＋热点路径探针服务层接入

**类型**：修复轮（基准测量口径）＋ 功能轮（宠物服务层新入口）合并提交；性能/资源轮纪律适用。
**测试**：跑了——定向 `test_pet_test_service` 20 条、`test_perf_baseline` 7 条全绿（含新 settle 后的滚动门禁）、默认冒烟 8/8；全部改动文件 py_compile 通过。
**基线**：冒烟 8/8；未跑 `--architecture`（无分层/契约结构变更）；全量回归未跑（分支不累计欠账，合入 master 前按风险触发判定）。
**欠账**：无新增；C2 内存长跑定性、C3 页面首帧拆解、C6 降级约定留待后续轮次（本轮已产出 paint_stats.py 与 app.log 实测证据）；pet_agent 聊天指令接线因模块行数棘轮（1182 行上限）移交单独轮次。

## 本轮做了什么

1. **C1 定性结论（清单 🔴→✅）**：长列表「首跑 treeview_rows=300/999、scroll 225ms/帧」不是产品退化，是基准口径缺陷——`基准_长列表.py` 在 `show()` 后只跑一次 `win.update()`：该调用会把整条 `after` 分批插行链排空（行数读数落在随机时刻），滚动测量落在半截表或全量表之间随机摆动。产品侧分批建行（首批 24 行→每 50ms 补 12 行）与 CellImages 视口重排（R72 已优化到 ~8 次 bbox/帧）工作正常；安静时段 999 行滚动实测 ~5ms/帧。
2. **基准修复**：`基准_长列表.py` 新增 `settle_rows()`——像 mainloop 一样分段 `update`，等行数长齐且 `asset_thumbs.pending()==0` 再测滚动；新增 `fill_ms`（show→行长齐总时长）、`scroll_median_ms`（与门禁同中位数口径）；`--output` 目录自动创建。复测：rows 稳定 300/999。
3. **门禁同步加强**：`test_perf_baseline.py` 滚动用例在测量前 `settle_asset_rows` 等全表（断言 rows≥300），不再量半截表；阈值未动。
4. **C4 热点路径探针服务层接入**：`pet_performance_service.start_hotspot_check`＋`stage_execution_service` kind 分派——`stage_handler_registry.start(...,'pet_performance',kind='hotspot')` 全链路可用，三虎离线优化检查现在覆盖启动/长列表/热点路径三族探针。**聊天指令（pet_agent RULES）未接**：pet_agent.py 已顶到 1182 行棘轮上限，新增规则超限；聊天入口留待 pet_agent 拆分轮或用户批准上限调整后补。
5. **C5 口径对齐（部分）**：`performance_contract.py` 末尾新增「归档指标↔契约口径对照表」；`runbook §10` 记录 R2979 起同口径指标；其余归档指标明确标注「无契约常量，只作趋势参考」。
6. **C9 聚合工具**：新增 `维护记录/基准脚本/paint_stats.py`——汇总 `logs/app.log*` 的 page.paint.* 超阈记录与 `perf_metrics.json` 会话累计，供半月审计直接引用。

## 关键实测证据（写进清单）

- `paint_stats.py` 首跑即命中真实使用数据：`page.paint.script` 超阈 **147 次**（均值 2296ms、P50 1671ms、最大 15687ms），`storyboard` 14 次、`script_structure` 23 次、assets 9 次——**剧本页首帧是当前真实瓶颈**，升级为 C3 头号候选（历史日志跨版本累积，需按 --days 过滤解读）。
- 长列表 settle 后 scroll_avg 58–93ms 为重载机器读数（并发 28+ python 进程）；历史安静读数 ~5ms/帧。判据仍以 contract/test 阈值为准。

## 改动文件

`pet_performance_service.py`、`stage_execution_service.py`、`tests/performance_contract.py`、`tests/test_perf_baseline.py`、`tests/test_pet_test_service.py`、`维护记录/基准脚本/基准_长列表.py`、`维护记录/基准脚本/paint_stats.py`（新增）、`runbook.md`。

## 未做/移交

- pet_agent/pet_ui_stages 聊天指令接线：pet_agent.py 1184 行 > 棘轮上限 1182，静态门禁拦截；服务层 kind='hotspot' 已可用，聊天规则待 pet_agent 拆分轮。
- C2 内存 C 层漂移：需 30min soak＋堆快照，本机负载过高读数无效，留待安静时段。
- C3 页面首帧拆解：本轮拿到 page.paint.script 实测证据，正式拆解立下一轮。
- C6 忙时降级约定、C7 CACHED_PAGES 扩面：设计决策项，已在清单标注待用户裁决/观察。
- B2/B3：趋势触发项，等半月审计数据。
