# R702 修复轮结果：启动期自动链收尾与全量回归

## 承接说明

承接 R701：R701 已为用户主动 `async_()` 任务增加 50ms 可取消结果回填，但完整安全全量仍有 24 个红文件。复核后，剩余问题不是后台工作本身，而是 R697 首帧暂停全局 tick 时，已派发的自动粗剪／自动交接结果没有独立投递者；此前为弥补此缺口而在首帧回调无条件恢复全局 tick，又会在页面尚未稳定时重建页面并覆盖状态。

## 修复

- `desktop.py`：首帧回调不再因已有 `root` 无条件恢复全局 tick；自动续开仍只在既有延后建页完成后恢复，R697 的启动时序不回退。
- 自动粗剪与自动交接包各自增加 50ms、可取消的启动期结果轮询；它们只消费已派发任务的结果，不发起新的自动轮询。窗口销毁会取消这两项回调。
- 自动结果消费拆为纯交付方法；常规 tick 仍负责下一轮决策。将视频检查置于白模派发之前，确保同一轮的“缺首帧”提示不覆盖白模已派发状态。

## 回归

- 四项启动期 UI 边界专项通过：下拉列表不重建、首帧提示词空态、同源选择不重建、自动粗剪／交接共享就绪检查。
- `test_auto_previs_sanhu_mode_dispatches_complex_once` 通过，确认白模自动派发状态不再被同轮视频检查覆盖。
- R700 的查询缓存、聊天首现、`show_loaded_project <= 1.0s` 与首帧 worker 守卫继续由既有专项覆盖；未改注册表、阶段配置、用户项目数据或其文件格式。

## 验证

- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected skill_registry stage_config desktop skill_panel`：9/9 通过，定向自检 0 个文件有红。
- `python run_selftests.py --layer gui-short --safe --all`：1,079 条、0 个文件有红、287.1 秒；日志：`维护记录/r702_gui_short_safe_all.log`。
- `python run_selftests.py --all --safe`：3,398 条、0 个文件有红、812.5 秒；日志：`维护记录/r702_safe_all.log`。

## 三个基线数

- 默认冒烟：8/8 通过。
- gui-short 安全全量：1,079 条 / 0 个文件有红。
- 完整安全全量：3,398 条 / 0 个文件有红。

[TASK_COMPLETE]
