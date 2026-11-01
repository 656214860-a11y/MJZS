# R758 结果｜修复轮：阶段目录补齐失败反馈

## 结论

已修复阶段目录按需补齐时的静默失败。`Desktop.ensure_stage_layout()` 遇到文件系统错误仍返回空列表、不会阻止项目继续使用，但现在会显示“阶段目录未补齐：…；请稍后重试。”，不再把失败伪装成已完成。

## 根因与证据

- `desktop.py:3392-3404` 原先捕获 `stage_layout.ensure()` 的所有异常后直接返回空列表，状态栏仍保留先前内容。
- 新增 `tests/test_stage_wiring.py` 故障注入：令 `stage_layout.ensure()` 抛出 `OSError('阶段目录无写入权限')`。旧实现中状态不含“阶段目录未补齐”，测试失败；修复后验证继续返回空列表、不抛异常且状态可见。
- 本轮没有在项目打开路径预建目录，也没有改动阶段目录语义、用户项目媒体或成果文件。

## 验证

- `python -m unittest tests.test_stage_wiring.LayoutWiringTests.test_ensure_stage_layout_failure_is_visible_without_blocking tests.test_core.ResidualProjectTests`：6 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop stage_layout`：9/9，定向安全自检 34 条／0 红／8.3 秒。
- `python smoke_test.py --architecture`：138 条／0 红。
- `758 - last_full_safe_all_round(755) = 3`，触发完整安全全量；`python run_selftests.py --all --safe`：3,487 条／0 红／840.3 秒。`维护记录/测试分层基线.json` 已推进至 R758。

## J. 整改路线

继续只处理缺陷台账中的可观察失败链：优先逐项以故障注入区分可选维护、用户可修正输入与必须上抛的编程／发布错误。R747 启动首屏、改名项目认领与主界面幽灵条目仍需实机证据，不能由本轮自动化替代。

## K. 测试迁移计划

阶段目录与其他可选维护继续在 `tests/` 中以临时项目和服务故障注入覆盖：断言主流程是否可继续、失败状态是否可见、不会把失败记为完成。涉及 Tk 的用例保持显式销毁与定时器取消，避免测试关闭后残留回调。
