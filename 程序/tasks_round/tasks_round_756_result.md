# R756 结果｜修复轮：阶段配置打开失败可见化

## 结论

已修复“修改配置”按钮在阶段配置面板加载异常时没有任何反馈的问题。`stage_models.open_config()` 现在保留原有不崩溃行为，但会通过既有状态栏提示“未能打开阶段配置，请稍后重试。”。

## 证据

- `ui_plugin_registry.module('skill_panel')` 或其 `show()` 抛错时，旧代码在 `stage_models.py:275-281` 直接返回 `None`，用户不可见任何原因。
- 新增故障注入：`tests/test_manual_plan.py` 将注册表入口替换为抛错函数；旧实现状态栏为空，测试失败；修复后断言返回 `None` 且状态含“未能打开阶段配置”。
- 未修改配置数据、阶段执行、用户项目内容或模型选择逻辑。

## 验证

- `python -m unittest tests.test_manual_plan tests.test_manual_gate`：45 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected stage_models skill_panel`：9/9，定向安全自检 19 路／0 红／22 秒。
- `python smoke_test.py --architecture`：138 条／0 红／41.968 秒，未低于基线。
- `756 - last_full_safe_all_round(755) = 1 < 3`，未触发完整安全全量。

## J. 整改路线

继续对缺陷台账内能以故障注入证实的 UI 入口逐项收口，优先处理“异常后没有可行动反馈”的路径；只在真实失败链上改动，不把受控 Tk 销毁容错误改成业务提示。

## K. 测试迁移计划

`tests/test_manual_plan.py` 继续集中覆盖确认与配置入口：注册表加载失败、面板展示失败、取消与直接执行必须各有明确且不互相越权的行为断言。
