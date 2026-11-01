# R761 结果｜修复轮：资产续跑恢复失败反馈

## 结论

已修复项目打开时自动补资产续跑台账读取失败被静默降级的问题。项目仍可正常打开，但状态栏会说明续跑记录未恢复及可稍后重试，避免用户误判为不存在待续跑任务。

## 根因与证据

- `desktop.py:3014-3028` 原先在 `asset_resume.attempts()` 或 `delay()` 抛出文件、格式或键错误时，只把次数重置为零、取消延后续跑，不输出状态。
- `tests/test_core.py` 新增故障注入：`asset_resume.attempts()` 抛出 `OSError('续跑台账不可读')`。修复后不抛出、次数安全归零，且状态含“自动补资产续跑记录未恢复”。
- 本轮仅改变失败可见性；未读取或写入用户项目媒体、成果与续跑台账，也未改变正常续跑的退避语义。

## 验证

- `python -m unittest tests.test_core.ResidualProjectTests`：8 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop asset_resume`：9/9，定向安全自检 22 条／0 红／8.3 秒。
- `python smoke_test.py --architecture`：138 条／0 红／33.978 秒。
- `761 - last_full_safe_all_round(758) = 3`，触发完整安全全量；`python run_selftests.py --all --safe`：3,491 条／0 红／853.7 秒。`维护记录/测试分层基线.json` 已推进至 R761。
- 全量 stderr 仍可见既有 Tk `after` 回调销毁告警；测试汇总为 0 红，且该实机生命周期现象继续保留在启动实机挂账中，未伪称已关闭。

## J. 整改路线

继续以“项目恢复可选维护不阻塞、失败必须可见”为准则审计 `desktop.py` 的剩余恢复回调，先处理模型同步与后台回调的错误回传。启动首屏、项目改名认领和幽灵登记仍须以用户实机复验关闭，不能由静态或无 Tk 测试代替。

## K. 测试迁移计划

项目恢复链的回归继续放在 `tests/test_core.py`：以无 Tk 临时根目录注入读取、队列和文件系统错误，逐项断言“不阻塞项目打开”和“状态可见”。真实媒体、用户项目目录和真实 Tk 窗口仅在用户实机复验中触及。
