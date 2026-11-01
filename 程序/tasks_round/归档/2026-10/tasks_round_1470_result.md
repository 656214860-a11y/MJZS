# R1470 功能轮：后台任务排队与界面截图基线工具（优化清单第 13 项收口）

1. **本轮类型？** 功能轮（opt-in，不改既有入口语义）。
2. **测试与基线？** `test_task_center` 增 3 项（队列先进先出与上限、桌面排队与续跑、结果收尾接线），新增 `test_ui_snapshot_tool`（3 项，纯逻辑）；`test_desktop_automation_service` 的假桌面补一个 `_start_next_queued` 空实现（只改测试替身，断言未动）；idea_chat／cancellation／lifecycle 等相关测试通过；默认冒烟与架构门禁见提交前运行。
3. **是否欠账？** 改了 `desktop.py` 结果收尾路径，计入源码轮次；提交后在干净检出里复验全量。

## 改动

- 排队：`BackgroundTaskQueue`（先进先出，最多 10 个，`desktop_automation_service.py`）；`Desktop.async_queued(fn, done, label)`——后台空闲就立即执行（走原 `async_`），忙则排队并在状态栏提示“已排队（第 N 个）”；`_tick_async_result` 收尾后调用 `_start_next_queued()` 接着做下一项，窗口正在关闭时丢弃。「运行状况」面板新增“排队中”一节。
- **有意保持**：`Desktop.safe()` 等现有“请稍候”拦截一律不变，没有任何既有动作被改成排队——排队是新增的 opt-in 入口，只适合互相独立、可延后的任务；前一项失败不会取消后一项；破坏性或依赖当前界面状态的操作不应使用。目前没有调用方，后续功能按需接入。
- 截图基线：`scripts/ui_snapshot.py`（ctypes 抓窗口、zlib 写 PNG，零第三方依赖），`--update` 重拍、`--check` 比较（平均每通道差 ≤2），`dev.py shots` 入口；基线 `tests/ui_baselines/runtime_dialog.png`（656×559，已目视核对内容正确）。**不进全量门禁**：像素受字体／DPI／主题影响，会让并行全量随机变红，所以是按需命令；自动测试只覆盖 PNG 读写与差异度量。目前只覆盖运行状况弹窗，其他页面需要稳定的样例数据后再加。

## 提交

已提交，见 git log 标题 `R1470:`。
