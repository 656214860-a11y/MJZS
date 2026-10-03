# R860 结果｜资产自动导入 watcher 可见失败

资产自动导入 watcher 读取批次台账时的 `OSError`、格式错误或键缺失过去直接静默跳过，界面可能一直停留在等待状态。现保留原有约两秒重试节奏，并显示“资产自动导入检查未完成”、异常原因与重试说明。

验证：`tests.test_asset_skill_batch` 注入 `read()` 的 `OSError`，1 条／0 红，断言状态可见且轮询仍登记；默认 `smoke_test.py` 8/8 通过。

`[TASK_COMPLETE]`：该 watcher 的台账读取失败已从静默吞没改为可观察降级。
