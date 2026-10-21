# R1830 结果：cloud_video.settings_window 改写成类（整理轮）

- 改动：`settings_window` 用 c2c 改写成 `_CloudSettingsWindow`，函数从 204 行降到薄壳；`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_cloud_settings_window_equivalence.py`，旧实现取 HEAD 原文内嵌；对照初态控件树、逐个点按钮（跳过联网“测试连接”与读密钥按钮）后的控件树与落盘文件。公共件 `window_diff_support` 补：替身 repr 抹地址、点按钮时替掉 webbrowser.open。
- 变异检验：按钮文字“保存设置”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、`tests.test_cloud_video`、此前两个窗口差分测试、函数长度/复杂度/skip 台账门禁均通过。
- 断言未动。
