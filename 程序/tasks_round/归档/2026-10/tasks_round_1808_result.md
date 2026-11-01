# R1808：结构治理轮——切 Desktop.__init__ 为窗口／侧栏与主体两段（批次 C-2）＋修托盘失败分支测试在自检环境下的红

1. 本轮类型：§3 结构治理轮（切分不改行为）＋一处测试环境修复。

2. 测试与基线：
   - 切分用数据流脚本：`__init__` 的 156 条语句按两个切点切成 `_init_window_and_sidebar`（52 行：服务、窗口外观、侧栏项目列表／导航按钮、标题行）与 `_init_body_and_status`（62 行：主体区、画布、进度条、状态栏、尺寸把手），剩下的自动化与启动编排（50 行）留在 `__init__`。跨块的局部变量脚本算出来只有 `win`、`script_page_services`、`root` 三个参数，没有任何返回值，语句顺序与内容一字未改。
   - 架构门禁 + `test_desktop*`／`startup`／`timers`／`tray`／`responsive`／`splash` 共 459 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿；默认冒烟 8/8。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `desktop.Desktop.__init__` | 165→53 行；拆出 `_init_window_and_sidebar`、`_init_body_and_status` |
| `test_function_size_ratchet.py` | 删 `desktop.py::__init__` 登记 |
| `test_complexity_ratchet.py` | `Desktop` 类上限 1289→1297（+8 行方法头与文档串） |
| `test_data_table_boundary.py` | 扫描方法集合加入 `_init_window_and_sidebar`（侧栏的 `ttk.Treeview` 随之搬了家）；**计数断言 `== 2` 未动** |

## 顺带修：托盘失败分支测试在自检环境下的红（R1801 合并遗留）
`test_desktop_tray.test_setup_tray_failure_does_not_block_startup`（R1777）要走真实的“建托盘失败”分支，但 master 的 R1781 让自检器默认设 `DRAMA_SUPPRESS_TRAY=1`，`setup_tray` 在入口就返回，`tray_icon` 根本没被创建，测试因此 `AttributeError`。两条分支各自都是对的，合并后才互相踩到。修在测试：用 `mock.patch.dict(os.environ)` 局部清掉该环境变量，断言未动。

## 评估后不切的长函数（块间要传的变量太多）
用同一套规划器对其余 17 个超长函数试排切点：`keyframe_comfy.show`（块间 16–26 个变量）、`open_manager`（15–26）、`show_final`（8–18）、`storyboard`（13–15）、`attach_controls`（6–23）、`open_flow_agent`（19）、`asset_batch.show`（20）、`storyboard_files.show`（9–20）等，机械切出来会变成 20 个参数的助手函数，质量比不切还差。这些是 Tk 窗口构建函数，状态散在大量闭包里，正确的做法是抽成带状态的类或控制器，需要先补行为测试再做，超出“只切不改”的范围，保留登记。
