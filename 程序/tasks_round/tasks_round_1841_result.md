# R1841 结果：keyframe_comfy.show 改写成类（整理轮，OVERSIZE_CAPS 清空）

- 改动：`show` 用 c2c 改写成 `_KeyframeComfyWindow`（39 个共享名、39 个方法），`nonlocal busy/poll_id` 改成实例字段。`build` 有 160 行，仍超出上限，又用 chunk.py 切出 `_build_model_box`（模型与接口卡片）和 `_build_local_box`（ComfyUI 连接卡片与记录区），`build` 降到 115 行。`OVERSIZE_CAPS` 删掉最后一条，现在为空表。
- 差分测试先行：`tests/test_keyframe_comfy_window_equivalence.py`，旧实现取 HEAD 原文内嵌；在同一个真 Desktop（已填充项目）上，分别以 `initial=None` 和 `initial` 为空选打开首帧制作窗口，对照初态控件树、逐个点按钮后的控件树和宿主记录。跳过会联网、弹模态框、开新窗口或真开工的按钮；共享接口配置 `CONFIG_FILE` 改指向临时目录，不写真实配置。旧实现自比为绿。
- 变异检验：按钮文字“预估费用”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、test_keyframe*／test_batch_frames／test_extra_batch_frames／test_timers 共 125 项通过；`run_selftests.py --architecture` 通过。
- 断言未动。
