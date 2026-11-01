# R894 UI 统一入口：首帧旧任务确认

- `keyframe_import.launch()` 的旧任务放弃／重提确认改由 `ask_confirmation()` 处理。
- 关闭、取消或拒绝都保留旧任务，不会触发重提；放弃旧任务被标为危险确认。
- 验证：`py_compile keyframe_import.py` 通过；`test_keyframe_comfy.ResubmitTests` 2 条／0 红。
- 其余历史直接确认调用仍待迁移，路线图未完成。
