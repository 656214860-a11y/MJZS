# R1615 金额算术不变量与总额一致性修复（Q6）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round_1610_result.md) J 第二批 Q6）。
- 测试：定向 `tests.test_money_invariants`＋`test_request_ledger`＋`test_usage_overview` 58/58 通过；架构门禁 350/350 通过（170.069 秒）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮改源码＋测试，`project_status.md` 全量欠账计数 +1，未清。

## 先发现的真实缺陷（已修）

`pet_llm.RequestLedger.price()` 分别对 `settled`／`reserved` 四舍五入，却对 `settled + reserved` **再单独四舍五入**得到 `amount`。当分项舍入方向不一致时，`amount` 会比 `settled_amount + reserved_amount` 差 1 个最小单位（1e-4）。确定性随机用例复现：`amount=645.4605` 而 `settled_amount+reserved_amount=645.4604`。

**修复**（根因）：先对分项取整，再由分项之和得到总额——
```python
settled_amount = round(settled, 4)
reserved_amount = round(reserved, 4)
return {'amount': float(settled_amount + reserved_amount),
        'settled_amount': float(settled_amount), 'reserved_amount': float(reserved_amount), ...}
```
既有金额断言未变（58 项含 `test_request_ledger`／`test_usage_overview` 全绿）。

## 新增不变量测试 `tests/test_money_invariants.py`

- `RequestLedger.decimal()` 拒绝负数／NaN／inf／bool，接受有限非负。
- `price()`：**总额＝分项和**（200 组确定性随机输入）、非负、≤4 位小数、币种取自价格表不做汇率换算、缺费率仅在有用量时列出。
- `_model_price()`：成本＝Σ(用量×费率)（Decimal 精确比较）；缺模型／版本／币种 => `None`，**绝不补零**。
- `estimate_scenario()`：完整场景总额＝各阶段金额之和；不完整场景无总额、单阶段 `amount=None`；未知单位抛错。

## 与既有测试的关系（避免重复）

`test_request_ledger`／`test_usage_overview` 覆盖场景行为（预留/结算/对账/未知）；本文件补的是**算术恒等式**与边界，交叉验证，不重复。

## 下一项

Q7（覆盖率度量）。