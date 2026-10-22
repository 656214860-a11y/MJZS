# R1813：结构治理轮——storyboard_files 的 show_final（401 行）与 show（335 行）由闭包改写成类并切段（批次 C-5）＋补整页控件树差分测试（批次 D-3）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。这是批次 C 里用户点名、上一轮我自行放弃的两项。

2. 测试与基线：
   - **先补测试**：新增公共件 `tests/page_diff_support.py`（整棵控件树快照：类名、文字、状态、样式、布局管理器参数、请求尺寸、是否映射、列表行／选中、文本框／输入框／画布内容；路径与运行期时间归一；步骤里的异常也算可观察行为）和 `tests/test_storyboard_files_equivalence.py`：旧 `show`／`show_final` 原样内嵌，各自用同一份脚本驱动两个真 `Desktop`（填充项目夹具：定稿目录、资产图、首帧、已验收镜头），脚本 = 目录任务按既有 `show_catalog_page_ready` 跑完 → 拍整树 → 依次点“刷新列表／立即重试／刷新／全选／取消选择／清除选择”（页面上有才点）→ 每个列表选 1／3／全部行再清空 → 点前 3 个镜头导航按钮 → 切到资产页再回来 → 再来一遍。路径用按进程号固定的目录（请求宽度随字形变化，随机目录名会让两次运行不逐字相同）。先用旧实现对自己比对通过（确认无随机性，各 22 秒）。
   - **牙口验证**：把“立即重试”改成“立刻重试”→差分测试红。**没抓到的**：把“恢复”处理函数里的状态栏消息改一个字→不红，因为脚本没有触发恢复／采用／删除这类会弹确认框或写盘的路径。静态名门禁（`test_static_names`）通过，说明改写没有引入未定义名；这些处理函数本身的行为仍靠改写的机械性（同一份源码、只改变量的取法）。这是本测试的已知边界，不是全覆盖。
   - 改写后：差分 + `final_page`／`storyboard`／`final_viewer`／`page_cache` 等既有页面测试 + 架构门禁 + `static_names` 共 504 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `storyboard_files.show_final` | 401→3 行薄函数 + `_FinalStoryboardPage` 类（共享 21 个局部名成实例属性，26 个嵌套函数成方法）；`build()` 再切成 `_build_status_bar`／`_build_final_table`／`_build_viewer` + 尾部 26 行 |
| `storyboard_files.show` | 335→3 行薄函数 + `_StoryboardFilesPage` 类（共享 18 个名字，19 个方法）；`build()` 切成 `_init_page_state`／`_build_toolbar`／`_build_tables` + 尾部 8 行。藏在 for 循环里的嵌套 def（`is_checked`、`open_cell`…）仍是 `build` 的局部闭包——只被同一循环里的 lambda 引用，工具允许这种情形 |
| 同步测试（**断言未动**） | `test_storyboard_edit_boundary`／`test_storyboard_final_selection_boundary`：找 `ask_save`／`choose` 的起点从 `show_final` 函数换成 `_FinalStoryboardPage` 类；`test_data_table_boundary` 的“分镜文件页不得直接构造 Treeview”原来只扫 `show_final`，现在**同时**扫薄函数和新类（并断言两者都找到），避免改写后该检查空转 |
| `test_function_size_ratchet.py` | 删 `show_final`／`show` 两条登记 |
| `维护记录/skip台账.json` | 登记新测试的 Tk 不可用跳过 |
