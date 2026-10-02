# R746 结果｜修复轮：阶段事件静默失败

## 结论

已修复自动链阶段事件被静默吞掉的问题。`desktop.py` 的剧本、结构剧本和首帧路径不再以裸 `except Exception: pass` 包裹 `pet._emit()`／`pet.report_done()`；事件总线自身故障现在语义化上抛，避免界面继续显示不真实的执行或完成状态。

## 根因与最小改动

- 根因：权威阶段事件通知失败被无条件忽略。业务动作可能已失败，而三虎状态机未收到失败终态，形成“卡住／假进度”。
- 改动：仅移除这些权威通知边界的宽泛吞异常；业务层可预期的输入、文件和同步失败仍在原处转为当前阶段的可见失败状态。
- 回归：`tests/test_pet_ui.py` 新增 `test_stage_event_delivery_failure_is_not_silently_swallowed`，注入 `_emit` 的 `RuntimeError` 并断言必须上抛。该测试在旧实现下会失败。

## 验证

- `python -m py_compile desktop.py tests/test_pet_ui.py`：通过。
- 新增回归：1/1 通过。
- `python -m unittest tests.test_pet_ui tests.test_desktop_close tests.test_desktop_startup_perf -v`：完成；定向自检缓存已更新。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected desktop pet_ui`：定向 93 工作单元完成，无红灯迹象。
- `python smoke_test.py --architecture`：架构门禁通过，未低于现有基线。
- 全量判定：`746 - last_full_safe_all_round(745) = 1 < 3`，且本轮未改 Tk 生命周期／事件绑定；未运行完整安全全量，基线保持 R745。

## 未关闭事项

启动首屏、项目改名认领与主界面幽灵条目的实机复验仍未完成；本轮没有把它们标为已修。

## J. 整改路线

下一批继续按缺陷台账将 `desktop.py` 剩余裸吞异常分为：销毁态守卫、可观察 I/O 降级、以及必须上抛的编程／权威边界；每类先建立失败证据，再单独收口。

## K. 测试迁移计划

阶段事件交付失败的回归留在 `tests/test_pet_ui.py` 的 Desktop-Pet 真接缝组；其余异常处理专项按实际宿主放入 `tests/test_desktop_close.py`、`tests/test_pet_ui.py` 或 `tests/test_skills.py`，不新增临时测试目录。
