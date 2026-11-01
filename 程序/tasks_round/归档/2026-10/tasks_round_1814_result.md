# R1814：结构治理轮——首帧管理页 storyboard（312 行）由闭包改写成类并切段（批次 C-6）＋补整页控件树差分测试（批次 D-4）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。这是批次 C／D 里用户点名、我先前自行放弃的 `desktop_storyboard_page.storyboard`。

2. 测试与基线：
   - **先补测试**：`tests/test_storyboard_page_equivalence.py`，沿用上一轮的公共件 `page_diff_support.py`：旧方法（作为 `StoryboardPageMixin` 的方法，缩进还原后原样内嵌）与新实现各自挂到 `StoryboardPageMixin.storyboard` 上，经 `Desktop.show(首帧管理页)` 的真实调度进入；脚本 = 目录任务就绪 → 整树快照 → 点安全按钮 → 每个列表选 1／3／全部行再清空 → 切到资产页再回来 → 再来一遍。先用旧实现自比对通过（7.8 秒）。
   - **牙口验证**：把按钮“批量删除首帧”改成“批量删除首桢”→差分测试红；还原后转绿。同上轮的已知边界：脚本不触发会弹确认框或写盘的路径（批量删除、替换首帧等的处理函数体靠改写的机械性与静态名门禁保证）。
   - 改写后：差分 + `storyboard`／`page_cache`／`keyframe`／`static_names` 既有测试 + 架构门禁共 582 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `StoryboardPageMixin.storyboard` | 312→3 行薄方法：`return _FirstFramePage(self).build()` |
| `_FirstFramePage`（新类，同文件） | 共享 16 个局部名成实例属性，31 个嵌套函数成方法；原来的 `self`（桌面主窗）在类里叫 `page`；`build()` 再切出 `_build_state_and_table`（55 行）+ 尾部 56 行 |
| 工具改进（不入库） | 改写工具补上“类方法里的闭包”这一形态：嵌套 def 缩进从 8 降到 4 作为方法，`build` 主体保持 8；外层 `self` 参数改名 `page` |
| 同步测试（**断言未动**） | `test_keyframe_replace_boundary`、`test_data_table_boundary`（首帧管理页不得直接构造 Treeview）：原来只扫 `storyboard` 方法，现在**同时**扫薄方法与 `_FirstFramePage` 类，并断言两者都找到，避免改写后检查空转 |
| `test_function_size_ratchet.py` | 删 `storyboard` 登记 |
| `维护记录/skip台账.json` | 登记新测试的 Tk 不可用跳过 |
