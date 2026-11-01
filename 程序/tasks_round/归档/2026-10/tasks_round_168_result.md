# 第 168 轮：三虎进度断言随阶段清单更新

## 问题

- `test_pet_agent.py` 的三虎进度用例把 11 阶段时代的 `4.5%` 写死。
- 当前唯一阶段清单 `pet_bus.STAGES` 已有 12 个阶段，剧本阶段完成一半的确定性进度应为 `4.2%`；直接运行该测试稳定失败。

## 改动

- 将断言改为按 `pet_bus.STAGES` 的当前长度计算，继续验证「进度来自状态机」，而不是依赖过时的阶段总数。

## 验证

- `python test_pet_agent.py`：78 条通过。
- `python run_selftests.py --serial -k pet_agent`：78 条通过。
- `python smoke_test.py --affected pet_agent`：9 项冒烟检查通过。

## 风险与下一步

- 本轮只修复测试的过时分母，不改变三虎状态机、模型路由或项目数据。
- 后续继续审计阶段数相关的硬编码，并优先处理能稳定复现的流程阻塞。
