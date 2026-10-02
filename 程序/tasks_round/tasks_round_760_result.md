# R760 结果｜修复轮：生成资产自动导入失败反馈

## 结论

已修复项目加载后生成资产自动导入链的两处静默失败：生成目录检查失败和后台导入任务排队失败均不再被吞掉。两种失败仍不阻塞项目打开，但状态栏会明确说明失败原因与稍后重试。

## 根因与证据

- `desktop.py:3452-3467` 原先对 `pending_generated()` 的任何异常直接返回；`async_(work)` 的任何异常则直接 `pass`，用户无法区别“没有待导入图”和“检查／导入根本没有运行”。
- `tests/test_core.py` 新增两条故障注入：`pending_generated()` 抛出 `OSError('生成目录不可读')`，以及 `async_()` 抛出队列关闭错误。旧实现状态为空；修复后分别出现“生成资产检查未完成”与“生成资产导入未启动”。
- 未改生成资产识别、导入内容、项目数据或后台实际导入逻辑。

## 验证

- `python -m unittest tests.test_core.ResidualProjectTests`：7 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop asset_generated_import_service`：9/9，定向安全自检 13 条／0 红／7.0 秒。
- `python smoke_test.py --architecture`：138 条／0 红／34.085 秒。
- `760 - last_full_safe_all_round(758) = 2 < 3`，未触发完整安全全量。

## J. 整改路线

继续按“启动后可选维护失败必须可见、主项目打开不得受阻”的准则逐项审计 `desktop.py` 的项目恢复回调。下一优先是资产续跑恢复与模型同步的后台失败回传；启动首屏、目录改名认领与幽灵登记则仍以实机证据为关闭条件。

## K. 测试迁移计划

项目恢复链的回归继续放在 `tests/test_core.py`，以无 Tk 临时根目录注入读取、队列和文件系统错误；每条断言均覆盖“不抛出／不阻塞”和“状态清楚可见”两项，实际媒体导入仍不接触用户项目。
