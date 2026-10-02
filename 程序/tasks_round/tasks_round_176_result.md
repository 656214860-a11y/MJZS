# 第 176 轮：分镜输入读取异常收场

## 问题

- `Desktop.pet_storyboard_batch()` 读取已选剧本、已有分镜或采用状态时，配置损坏会被捕获后静默返回空字符串。
- 自动链已处于 `storyboard` active 时，空返回没有终态事件，会造成阶段永久执行中。

## 改动

- 自动触发下，将上述读取异常转换为 `stage.failed`，错误说明为“读取结构剧本输入失败”。
- 手动触发继续沿用原有静默返回，不改变用户手动操作的反馈语义。
- 新增桌面宿主回归：损坏选择配置时必须发送 `storyboard` 的失败事件。

## 验证

- `python -m unittest test_pet_ui.DesktopPetSeamTests.test_auto_storyboard_bad_selection_state_emits_a_failure`：通过。
- `python -m unittest test_pet_ui.AutoStartTests.test_batch_dispatch_error_finishes_the_active_stage_as_failed`：通过。
- `python test_sanhu_mode.py`：10 条通过。
- `python smoke_test.py --affected stage_flow`：9 项冒烟检查通过。

## 风险与下一步

- 本轮只在全自动入口的异常分支补失败终态，不改模型、素材或项目数据。
- 下一轮继续审计宿主批处理在“无项目/已有后台工作”时的自动链收场语义。
