# R762 结果｜修复轮：项目模型同步失败反馈

## 结论

已修复项目启动后模型对账将受控读取／数据错误静默压成空结果的问题。失败不阻塞项目打开，且由 Tk 主线程显示明确的稍后重试提示。

## 根因与证据

- `desktop.py:3432-3455` 原先 `sync_stage_models()` 捕获全部异常并返回 `None`；后台任务再把异常吞成空列表，用户看不到模型对账根本失败。
- 新增 `tests/test_core.py` 故障注入：`skill_panel.sync_models()` 抛出 `OSError('模型配置不可读')`。旧代码状态为空；修复后工作线程把受控错误放入结果队列，`_tick_stage_model_sync_result()` 在主线程显示“项目模型同步未完成”。
- 捕获范围仅限 I/O／数据边界（`OSError`、`ValueError`、`TypeError`、`KeyError`）；编程错误不被伪装为可重试状态。没有改模型选择、项目数据或正常同步语义。

## 验证

- `python -m unittest tests.test_core.ResidualProjectTests`：9 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop skill_panel`：9/9，定向安全自检 0 红／29 秒。
- `python smoke_test.py --architecture`：138 条／0 红／34.545 秒。
- `762 - last_full_safe_all_round(761) = 1 < 3`，未触发完整安全全量。

## J. 整改路线

继续审计项目恢复链与自动化回调：用户可观察的 I/O／网络／队列失败必须回到主线程可见，编程错误保持上抛。启动首屏、改名认领和幽灵登记依旧以实机证据关闭，不能以无 Tk 回归取代。

## K. 测试迁移计划

项目恢复异步回调继续放在 `tests/test_core.py`，使用即时线程和队列 fixture 验证错误只由主线程呈现；每条同时覆盖“项目不被阻塞”与“失败可见”。不接触用户项目或真实模型服务。
