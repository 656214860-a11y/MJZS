# R3008 结果（性能/资源轮：page.paint 启动相位分离——C3 定性埋点第①步）
<!-- round-evidence: {"commit_base": "a86d5f25", "credential_hits": 0, "evidence_sha256": "f0045fa7155508bd", "exit": 0, "failed": 0, "passed": 9, "round": 3008, "tests": "run_selftests.py -k page_paint_metric"} -->

## 三问
1. 轮次类型：性能/资源轮（runbook §15.3.7）——只改度量口径，不改页面行为。
2. 测试：`run_selftests.py -k page_paint` 18 条全绿（含新增稳态对照）；`smoke_test.py` 8/8。
3. 债务：C3 诊断证据链补齐——启动窗口争用已由日志时间线＋真实项目副本实测双重证实（见下），本轮把「首帧属启动相位」落成指标名分离，后续 paint_stats 可直接分桶。

## C3 根因结论（本轮诊断产出，写入清单）
- 慢样本（page.paint.script 1.9–3.9s）全部落在启动后 ~10s 窗口：`16:34:14 启动 → 16:34:18 侧栏几何 → 16:34:26 paint 3897ms`。
- 真实项目副本（摄影侠_20260930，20MB）隔离实测：冷开 paint 430–650ms、暖导航 83ms、最大化 431ms；布局轮次 14–18。
- 结论：页面构建 ~0.5s；日志秒级值 = 启动期事件循环争用（项目打开 I/O、DeferredFill、缩略图/pet 初始化、GC），非页面缺陷。次级目标：fit_content 反馈链 14–18 趟布局可合并。

## 改动
- `app_logging.py`：`finish()` 记录前判定 `_page_paint_boot_done`——每 Desktop 实例首个画完的页指标名加 `.boot` 后缀（`page.paint.script.boot`），detail 前缀「启动窗口；」；fitwaits/fitpasses 计数器同步挂到 `.boot` 名下保持口径一致。稳态翻页指标名不变。
- `tests/test_page_paint_metric.py`：4 处断言随契约更新（首个 paint 现为 `.boot` 名）；新增 `test_second_paint_uses_steady_metric_name` 验证第二次翻页回稳态名。
- `paint_stats.py` 无需改动：`page\.paint\.[\w.\-]+` 正则天然捕获 `.boot` 名，汇总表自动分行。

## 验证
- 受影响测试全绿；`_page_paint_boot_done` 鸭子类型属性，异常静默，不影响页面。
- 旧日志不受影响（历史样本无 .boot 名，仍按原名聚合——启动/稳态历史混杂是已知口径，.boot 只向前生效）。

## 遗留（C3 后续）
- ② 启动窗口 after/idle 回调普查：定位争用具体来源（候选：DeferredFill 稳定 tick、缩略图预热、pet 首轮轮询、项目打开 I/O）。
- ③ 证据充分后把非关键启动工作延迟到首绘收敛后。
- ④ fit_content 反馈链合并（fit_talk→fit_talk_container→Configure，14–18 趟→目标 ~4–6 趟）。
- C2 内存漂移、C6 忙时降级决策、C7 页缓存扩围：维持冻结/待证。
