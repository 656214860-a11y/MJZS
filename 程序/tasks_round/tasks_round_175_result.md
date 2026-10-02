# 第 175 轮：批处理异常收场自动链

## 问题

- 结构剧本、分镜或首帧批处理接缝抛异常时，宠物层会返回可读错误文字。
- `start_stage()` 原先把所有非空文字都当作“已启动”，没有发送终态事件；全自动链会永久保留 active，状态机也不会记录失败。

## 改动

- `pet_ui.Pet.start_stage()` 识别三个本地批处理的固定“未派发”错误前缀，并发送 `stage.failed`。
- 保留正常宿主返回文字的原有透传行为，不根据泛化关键词猜测失败。
- 在 `test_pet_ui.AutoStartTests` 增加回归：结构剧本批处理抛异常后，状态机写为 failed，自动链阻塞在 `script_structure`。

## 验证

- `python -m unittest test_pet_ui.AutoStartTests.test_batch_dispatch_error_finishes_the_active_stage_as_failed`：通过。
- `python test_sanhu_mode.py`：10 条通过。
- `python test_stage_flow.py`：45 条通过。
- `python smoke_test.py --affected stage_flow`：9 项冒烟检查通过。
- 完整 `pet_ui` 分片自检在当前单次观察窗口内未产生最终汇总，未将其作为通过证据；其余定向验证均完成。

## 风险与下一步

- 本轮仅为接缝异常补终态事件；不改模型配置、素材或项目数据。
- 下一轮继续检查桌面宿主的批处理函数是否在所有同步失败分支都发出同一阶段的终态事件。
