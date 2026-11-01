# R701 修复轮结果：启动期后台任务结果回填

## 修复

R697 将首帧前的全局 automation tick 延后恢复后，用户在项目页刚出现时启动的普通后台任务只能等待该 tick 消费结果；例如“强制关闭 ComfyUI”已在线程完成，状态栏却持续显示“正在强制关闭”。

`Desktop.async_()` 现为该任务自身登记一个 50ms 的可取消结果轮询。它只在启动期全局 tick 尚未恢复时补充消费既有结果队列；恢复后的 tick 仍是原有周期入口，任务编号与窗口销毁取消边界不变。

## 验证

- `tests.test_asset_gating.NativeAssetsGatingTests.test_kill_comfy_runs_off_the_ui_thread`：由失败转为 1/1 通过，确认工作仍在线程执行、点击不阻塞、完成文本会回填。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --layer gui-short --safe --all`：1,079 条、271.0 秒、0 个文件有红。
- `python run_selftests.py --all --safe`：3,398 条、806.7 秒、24 个文件有红，故本轮不按全量验收关闭。

## 全量失败基线与下一批

失败集中于既有 `test_pet_ui`（云朵窗口几何/关闭控件）与 `test_ui_edges`（无人值守自动链）回归；另有两个可明确收口的架构门禁：`idea_chat.py:609` 从 L2 导入 L3 `stage_config`，以及 `desktop.py:1406` 直接调用 `workflow.get`。下一批先修复这两个架构违规并按失败断言分组治理 UI 生命周期问题。

## 三个基线数

- 默认冒烟：8/8 通过。
- gui-short 安全全量：1,079 条 / 0 个文件有红。
- 完整安全全量：3,398 条 / 24 个文件有红。

[TASK_FAILED]
