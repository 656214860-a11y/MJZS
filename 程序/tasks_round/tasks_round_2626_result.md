# 轮次 2626 结果
<!-- round-evidence: {"commit_base": "b061746f", "credential_hits": 0, "evidence_sha256": "45f7cca1675288d8", "exit": 0, "failed": 0, "passed": 49, "round": 2626, "tests": "run_selftests.py -k auto_full_safe swallowed_cleanup ui_style_engine"} -->

## 三问

- 类型：§3.2 修复轮（合并阻断级·测试环境适配）
- 测试：跑了——`run_selftests.py -k auto_full_safe swallowed_cleanup ui_style_engine`：49/49 绿（改动前 ui_style_engine 确定性红、另两条在全套件内确定性红）
- 三个基线：冒烟未跑（只动测试文件的期望模型与隔离）；架构门禁未跑；全量未跑（本轮使后续自动全量可绿）
- `project_status.md` 欠账：不少——解除阻断的修复，欠账由全量凭据消化

## 改动

- `tests/test_ui_style_engine.py`：`test_real_main_window_uses_the_policy_and_keeps_800x600_minimum`
  的期望由 `main_window_size(屏幕宽,屏幕高)` 改为 `main_window_size(_work_area 右-左, 下-上)`。
  产品本就以 `GetMonitorInfoW` 工作区收缩窗口；测试旧模型把工作区≈屏幕，在本机竖屏＋
  侧占 48px 工作区下期望多算 48px（期望 1056、实际 1008）。断言语义不变（仍精确比对
  策略尺寸），只是期望模型与产品同源。
- `tests/test_auto_full_safe.py`、`tests/test_swallowed_cleanup.py`：断言
  `_recent_swallowed` 增长前先 `clear()`。环形缓冲上限 20，全套件内先前 GUI 用例的
  真实 bgerror 会把它灌满，断言「len > before」在满缓冲下必败；先清即恢复语义。

## 背景

R2622 修复后自动全量在新树（b061746f）跑完仍红 3 条：上述三条。逐条隔离验证：
ui_style_engine 在主工作区同样确定性红（环境模型问题，非运行时抖动）；另两条
隔离绿、套内红（隔离问题）。断言未弱化，均为模型／隔离修正。
