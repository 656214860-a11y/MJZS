# 第 178 轮：首帧自动链的前置条件终态

## 问题

三虎自动链启动“首帧管理”后，首帧批次入口没有触发来源信息。未找到分镜、首帧已经齐全或后台任务占用时，入口可能只返回空串或提示文字，活动阶段没有确定终态，自动链会停在执行中。

## 改动

- `Pet.start_stage('keyframe')` 通过 `firstframe_batch(trigger='auto')` 明确自动来源；旧版无参数宿主接缝仍兼容。
- `Desktop.pet_frame_batch` 在自动来源下：无可用分镜发出 `stage.failed`；首帧已齐全发出 `stage.completed`；已有任务、缺本地配置或缺输入等未派发原因发出 `stage.failed`。
- 手动首帧按钮仍保留原有行为：无项目或无缺口时静默返回。
- 异步批次的成功/失败原本已由 `StageQueue → Pet.drain` 发出终态，本轮不重复实现该通路。

## 验证

- 新增自动首帧三项回归：无分镜失败、无缺口完成、后台占用失败。
- 新增自动派发携带 `trigger='auto'` 的回归。
- 定向 `AutoStartTests`、`FrameBatchSeamTests`、`FirstFrameBatchTests`：18 项通过。
- `test_sanhu_mode.py`：10 项通过。
- `smoke_test.py --affected stage_flow`：9 项冒烟检查通过，内含 45 项阶段流程测试通过。

## 后续风险

后台任务占用采用安全失败并停止自动链，而非后台排队重试；与当前自动链的阶段失败语义一致。下一轮继续审查其余宿主入口是否把自动链的活动阶段静默返回。
