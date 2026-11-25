# L0–L5 制作链路集成 C 卡「P1 执行接口」验收记录


## 本轮实现

| 验收点 | 位置 | 当前口径 |
| --- | --- | --- |
| L0 工具结果协议 | `contract/service_contract.py` | `ToolResult` 闭集状态 `done/page/input/failed/missing`；五类工厂与 `coerce_tool_result`；页面序号严格校验；`ToolResult.__post_init__` 已补 `-> None` 类型标注。F 卡已验证的 L0 11/11 判定保持，不再重跑或改判。 |
| L3 注入执行器 | `orchestrator/skill_orchestrator.py` | L3 不 import `ui` / `skill_tools`；执行器由实例或组合根注入；`context['tools']` 仅保留自检替身。未绑定时工具行与技能行均为显式 `missing`。 |
| 缺工具与失败汇总 | `orchestrator/skill_orchestrator.py` | 混合结果里真正执行失败优先为 `failed`；纯缺工具保持 `missing`。`retryable_skills()` 原有 `failed/missing` 均可重试的兼容语义不变。 |
| 模板执行体位置 | `orchestrator/skill_templates.py`；`orchestrator/skill_orchestrator.py` | 模板执行体搬入既有 `skill_templates` 模块，由编排器注入自己与 `Run` 工厂，不反向 import 编排器、不加空壳。`skill_orchestrator.py` 当前 947 行，低于 1000 行上限。 |
| L4 输入、页面与异常适配 | `ui/skill_tools.py` | `execute_tool()` 将输入、页面、缺工具与异常统一转 `ToolResult`；`open_page()` 按结果打开阶段页。 |
| 执行窗打开待办页 | `ui/ui_stage_popups.py` | 有 page 结果时提供「打开待办页面」；动作由用户点击触发，不在后台线程直接操作 Tk。 |
| L5 绑定 | `启动漫剧制作助手.pyw`；`desktop_launcher.py`；`ui/ui_stage_popups.py` | 两条启动路径与现有 UI 组合点幂等绑定 `skill_tools.execute_tool`。 |
| 调用者迁移与幂等确认 | `ui/skill_panel.py`；`ui/skill_panel_support.py`；`stage_execution_service.py`；`orchestrator/skill_orchestrator.py` | 付费确认后走 `resume_confirmed()`；确认行带 `confirmation_id`，同一确认重复送达复用首次续跑结果，不重复调用工具。 |
| 模板执行与完成步骤复用 | `orchestrator/skill_templates.py`；`tests/test_skills.py` | 模板业务语义保持：已完成步骤续跑不重跑，付费确认后接回原任务；现有模板断言未删除、未弱化。 |

## 回归与架构登记

- 新增 `tests/test_tool_execution_protocol.py`：无界面适配器与桌面编排结果一致、page/input 协议化、打开页面、重复确认不重复调用、未绑定执行器显式 missing。
- 新增 `tests/architecture/test_skill_orchestrator_boundary.py`：AST 门禁防止 L3 再反向依赖 L4 工具表。
- 更新 `tests/test_skills.py`：编排器测试显式注入 L4 适配器；现有 skip 均使用 `tests/skip_reasons.py` 常量，且常量在 `维护记录/skip台账.json` 有登记；本轮未新增 skip、未移除关键断言。
- 更新 `tests/test_startup_selfcheck.py`：隔离启动桩登记 `ui.skill_tools.install_executor`。
- 更新 `tests/architecture/_layers.py`、`维护记录/层间合规清单.json`、`architecture.md`：登记新增同层边；LR-01 因移除 `skill_orchestrator→skill_tools` 上行边从 17 下调至 16。

## 测试执行

按用户明确要求，**本轮不运行测试，测试全部由 Control 运行**。建议 Control 在 `程序/` 下执行：

```powershell
..\运行环境\Python\python.exe -B run_selftests.py -k tool_execution_protocol tool_result_contract skills startup_selfcheck
..\运行环境\Python\python.exe -B run_selftests.py -k skill_orchestrator_completion skill_templates resume_preview manual_gate
..\运行环境\Python\python.exe -B smoke_test.py --affected skill_orchestrator skill_templates skill_tools skill_panel skill_panel_support stage_execution_service ui_stage_popups desktop_launcher
..\运行环境\Python\python.exe -B smoke_test.py --architecture
..\运行环境\Python\python.exe -B smoke_test.py
```

如 runner 不支持一次多个 `-k`，请拆成多次运行。

## 边界

1. 纯 L3 调用未注入执行器时不再暗中使用 UI 工具表；无界面调用应显式注入 `skill_tools.execute_tool` 或由组合根安装。
2. `context['tools']` 是无界面自检替身，不替代正式适配器。
3. 重复确认幂等键保存在同一 Orchestrator 实例内；确认队列仍是会话内状态。
4. 页面打开是用户点击动作，避免后台线程直接操作 Tk。
5. `service_contract.py` 在工作树中存在并行契约改动；本卡采用当前更严格页面序号口径，不改 F 卡已验证的 11/11 决策。

集成验证由 Control 使用随附解释器执行，命令、结果与真实环境边界见 [R4516 独立验收](tasks_round_4516_result.md)。
