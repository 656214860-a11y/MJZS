# R757 结果｜修复轮：项目打开后的重复原图清理失败反馈

## 结论

已修复项目打开后的维护清理静默失败：`Desktop.prune_asset_leftovers()` 遇到回收站／文件系统错误时仍不阻塞项目打开，但会明确提示“重复原始取回图未清理：…；请稍后重试。”。

## 根因与证据

- `desktop.py:3374-3389` 原先对 `prune_raw_outputs()` 的任何异常直接返回空列表，使用户无法区分“没有重复图”与“清理失败”。
- 新增 `tests/test_core.py` 故障注入：令 `prune_raw_outputs()` 抛出 `OSError('回收站不可写')`。旧实现状态为空、测试失败；修复后返回空列表以保证打开流程继续，并留下可行动状态。
- 未改变清理范围、回收站策略或任何用户项目媒体／成果文件。

## 验证

- `python -m unittest tests.test_core.ResidualProjectTests tests.test_core.DailyProjectChoiceTests`：19 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop asset_batch_state_service`：9/9，定向安全自检 13 条／0 红／7.2 秒。
- `python smoke_test.py --architecture`：138 条／0 红／34.265 秒。
- `757 - last_full_safe_all_round(755) = 2 < 3`，未触发完整安全全量。

## J. 整改路线

继续以“可选维护不阻塞主流程、失败必须可见”为准则处理项目打开后的文件／网络维护分支；下一批先对台账中仍标为 A 的启动与项目认领路径保持实机复验挂账，不能用静态推断关闭。

## K. 测试迁移计划

`tests/test_core.py` 的项目打开维护组继续使用文件系统故障注入，分别断言主流程可继续、状态可见、不会误报已清理；涉及回收服务时一律使用临时目录。
