# R3003 结果（功能轮：pet_agent 规则表拆分 + 热点路径指令接线）
<!-- round-evidence: {"commit_base": "8e581258", "credential_hits": 0, "evidence_sha256": "6826e417f91db78d", "exit": 0, "failed": 0, "passed": 80, "round": 3003, "tests": "run_selftests.py -k pet_agent pet_ui_stages test_pet_agent pet_agent_rules"} -->

## 三问
1. 轮次类型：功能轮（runbook §3.3）——补完 R2979 遗留的 pet 侧指令接线，并为模块行数棘轮拆分纯数据表。
2. 测试：`run_selftests.py -k pet_agent pet_ui_stages pet_test_service` 100 条全绿；`-k module_size_ratchet page_paint` 19 条全绿；冒烟按功能轮要求补跑（见下）。
3. 债务：pet_agent.py 1184→1093 行，重回棘轮登记上限 1182 之内且留 ~89 行余量；纯数据表迁入新模块 `pet_agent_rules.py`（100 行），`pet_agent.RULES/REPLIES/PATTERNS/VERDICTS/UNKNOWN_REPLY` 旧引用经再导出不变。

## 改动
- `pet_agent_rules.py`（新）：RULES/REPLIES/UNKNOWN_REPLY/PATTERNS/VERDICTS 五张纯字面量表原样迁入；RULES 新增 `performance_hotspot` 规则——「热点」后必须再跟 优化/性能/检查/基准/测试 之一，防止「跑热点速成」误命中（已实测验证）。
- `pet_agent.py`：删 90 行表定义改 `from pet_agent_rules import ...`；`action_for` 白名单补 `performance_hotspot`→`stage.inspect`。
- `pet_ui_stages.py`：`run_plan` 分发 `performance_hotspot`→`run_performance_mode(kind='hotspot')`；标签表补 hotspot=「热点路径优化检查」。
- `tests/test_pet_agent.py`：新增规则命中测试（source=rule、零 Token、action=stage.inspect）。

## 验证
- 路由实测：`运行热点路径优化检查/跑热点性能检查/运行热点路径基准` → performance_hotspot(rule)；`跑热点速成的剧本` → goto（不误命中）；`热点路径优化检查`（无动词前缀）→ unknown 走 LLM（可接受）。
- 服务链路（R2979 已合入）：intent→kind='hotspot'→`pet_performance_service.start_hotspot_check`→`run_hotspot_benchmark`→`hotspot_stats.py --write`→`stage_handler_registry.wait(kind='hotspot')`→`advance_hotspot_check`→`performance_hotspot.report` 事件→pet 汇报。五环全通。

## 遗留
- C3 剧本页首帧：paint 口径已合入 master（R3001），真实项目下 page.paint.script 慢值待新指标数据定性 fit_content 反馈环。
- C2 内存漂移、C6 忙时降级优先级决策、C7 页缓存扩围：维持清单冻结/待证状态。
