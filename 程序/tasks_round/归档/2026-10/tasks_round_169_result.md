# 第 169 轮：自动阶段链真实完成事件回归

## 问题

- `test_stage_parallel.py` 的自动链用例连续请求下游阶段，却未模拟前一异步阶段的完成事件。
- `stage_flow.Auto` 正确地以 `active` 阻止下一阶段提前派发，测试因漏事件而把保护机制误报为失败。

## 改动

- 在剧本准备、剧本结构和初步分镜之间补上对应的 `done()` 事件。
- 用例继续验证：资产阶段的门禁会阻塞链路；上游补齐后，自动链可继续到连贯性清单。

## 验证

- `python test_stage_parallel.py`：47 条通过。
- `python run_selftests.py --serial -k stage_parallel`：47 条通过。
- `python smoke_test.py --affected stage_parallel`：9 项冒烟检查通过。

## 风险与下一步

- 本轮未改动自动链业务代码；仅使回归测试匹配异步阶段的真实事件契约。
- 后续继续检查尚未覆盖的自动/手动入口与阶段完成事件，优先修复可复现的实际阻塞。
