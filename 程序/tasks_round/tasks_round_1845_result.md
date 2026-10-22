# R1845 结果：同步改写成类后漏掉的 4 处源码查找测试（修复轮）

- 背景：合并 master 前跑 `--all --safe`（隐藏桌面），除常驻红外 21 条失败。对 8 个相关测试文件做了 master（c4779ee6）与分支对照，其中 13 条在 master 上同样红（隐藏桌面环境），属既有问题；只在分支红的有 5 条。
- 修复（只同步查找字符串和取源码范围，断言未动）：
  - `tests/test_qwen_adapter.py`：`def launched` 缩进少一级，调用改为 `self.host.async_`（R1840）
  - `tests/test_perf_baseline.py`：源码范围加上 `desktop_writing_page._WritingPage`（R1817）
  - `tests/test_stage_wiring.py`：`self.page.open_asset_detail(aid)`（R1816）
  - `tests/test_ui_edges.py`：`engine_name(self.project)`（R1836）
- 未修：`test_desktop_tray.test_two_trays_do_not_share_a_window_class`，隐藏桌面里建不了托盘窗口（WinError），同文件的其他托盘测试在 master 上也红，属环境问题。
- 本轮验证：`-k qwen_adapter perf_baseline stage_wiring ui_edges` 剩下的红，都与 master 对照一致；冷启动超时只在全量里出现，单独对照时 master 和分支都未红，属计时波动。
