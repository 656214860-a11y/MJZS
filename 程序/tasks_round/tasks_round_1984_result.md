# R1984 共享状态棘轮门禁（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J0**。
基线：`claude/bold-ardinghelli-d6a54d` @ 365f5945（R1983）。日期：2026-10-24。

## 改动

- 新增 `tests/architecture/test_shared_state_ratchet.py`。对每个登记的 Mixin 组合类，递归收集它自身和全部本仓库基类，按 AST 统计「被 ≥2 个类赋值的 `self` 属性」个数。四条用例：
  1. 实测不得超过登记值；
  2. 实测低于登记值时必须下调（下降即固化）；
  3. 组合类及其基类在生产模块中不得重名（否则统计口径不可靠）；
  4. 任何组合了 ≥3 个本仓库基类的生产类必须登记，新出现的组合类也会被拦住。
- 登记值（本轮实测）：`Desktop` 86、`Pet` 64、`Cloud` 18、`Panel` 5。
- `architecture.md`「当前架构门禁清单」的「轮次与基线／测试卫生」行登记新门禁。
- 未改任何生产 `.py`，未改用户数据。

## 更正 R1983 的一处数字

R1983 报告写 Desktop「15 个 Mixin、81 个多写者属性」。诊断脚本只看了直接基类，漏了 `IdeaChatMixin` 自己继承的 `IdeaBubblesMixin` 与 `IdeaDeferredMixin`。按递归口径，Desktop 实际组合 17 个 Mixin，多写者属性 86 个。门禁以递归口径为准，J1 以后的下降目标从 86 起算。Pet、Cloud、Panel 的数字不变。

## 验证（本轮实测）

- `smoke_test.py --architecture`（经 `工作流任务\gui_hidden.py`）：410 条，3 失败 1 错误。新门禁 4 条全部通过。
- 4 条红按改动范围判断都不是本轮引入，但没有在干净 HEAD 上逐条复跑确认：
  - `test_agents_md.test_performance_history_is_declared_as_historical_only`：本工作树缺 `维护记录/基准历史.json`（FileNotFoundError）。
  - `test_complexity_ratchet.test_class_size_does_not_grow`：`desktop.py::Desktop` 1303 行 > 上限 1302。本轮未改 desktop.py。
  - `test_round_baselines.test_round_number_continuous`：状态页轮次头 1973 与最新报告号不连续。HEAD 上已落后；工作树提交规则禁止改 `project_status.md`，需在 master 合入时同步。
  - `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：skills 引用检查，与本轮无关。
- 未跑默认冒烟和 `--all --safe`。本轮只新增测试与文档，不算源码轮，全量欠账计数不变。

## 回滚

删除 `tests/architecture/test_shared_state_ratchet.py`，并撤回 `architecture.md` 门禁清单中对应的那一项。

## 下一步

R1983 J1a（Desktop 自动化状态收口）。完成后按实测下调 `SHARED_STATE_CAPS['Desktop']`。
