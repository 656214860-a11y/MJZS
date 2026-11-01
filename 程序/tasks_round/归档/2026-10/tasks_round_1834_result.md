# R1834 结果：asset_batch.show 改写成类（整理轮）

- 改动：`show` 用 c2c 改写成 `_AssetBatchWindow`（26 个共享名、21 个方法），函数从 243 行降到薄壳；`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_asset_batch_window_equivalence.py`，旧实现取 HEAD 原文内嵌；在同一个真 Desktop（已填充项目）上分别按 comfy／workflow（预选 CHAR_001）／skill 三种引擎打开窗口，对照初态控件树和逐个点按钮后的控件树。跳过会联网、开外部程序、弹模态框或真开工的按钮；`async_` 只记账。旧实现自比为绿。
- 按名字找代码的测试同步：`tests/test_asset_batch_settings_callers.py` 会从源码抽出 save_settings／remove_model 之后的语句再执行；改写后这些语句改为引用 `self.<名字>`，所以替身环境补了一个 `self`，它的各属性和同名局部替身是同一个对象。断言未动。
- 变异检验：按钮文字“保存设置”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、test_timers、test_asset_batch_* 共 33 项通过；`run_selftests.py --architecture` 通过。
- 断言未动。
