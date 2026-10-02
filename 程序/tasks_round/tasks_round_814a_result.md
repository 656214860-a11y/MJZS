# R814A 结果：L3 反向 import L4 结构治理（执行子场景）

## 开工来源

来源：R814 在途违规。`stage_exec.py` 与 `stage_models.py` 曾直接导入 L4 `ui_widgets.BaseDialog`／`TextArea`；按 `tests/architecture/_layers.py`，两者均为 L3，违反“高层只能依赖同层或更低层”。

## 完成项

- L3 `stage_exec` 与 `stage_models` 只保留阶段数据、运行器、阻断判定和返回回调；不再静态或运行期导入 `ui_widgets`。
- L4 `ui_widgets` 持有执行日志文本框、宿主精简窗、三按钮、窗口焦点和延迟清理；通过显式 presenter 注入接收 L3 的运行器／失败行／进度／返回阶段回调。
- `BaseDialog(chrome=False)` 保留原有无统一标题栏／动作区的控件树，供两个既有窗口在不改变文案和路径的前提下使用。
- 未向 `ALLOWED_EXCEPTIONS` 或任何台账新增越层项，也没有改层级登记或弱化断言。

不选登记台账：登记会承认 L3 可以触碰 UI，给后续同类违规留下可扩张的豁免缺口，重演债务棘轮只会积累死账的教训。

## 实测

```text
> python -m unittest tests.architecture.test_layers tests.architecture.test_no_circular_import
Ran 5 tests
OK

> python run_selftests.py -k manual_plan
30 条用例，0 个文件有红

> python smoke_test.py
通过：8 项；失败：0 项

> python smoke_test.py --architecture
Ran 207 tests
test_layers 两项：均通过（由本轮前 2 红转绿）
既有／他人工作树红：test_round_baselines（R815 欠完整安全全量）、
test_unification_ratchet（agent/prompt_optimizer.py:173、qwen_setup.py:47）
本轮引入红：0

> 本轮暂存差异凭据形态扫描
credential_shape_matches=0
```

`tests/test_manual_plan.py` 的 30 条定向用例覆盖了独立执行窗的日志文本、失败项重试，以及宿主窗口精简窗的三按钮、阻断提示和返回选择；窗口路径与文案未漂移。
