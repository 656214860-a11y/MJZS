# R1817 结果（整理轮）

- 新增整页差分测试 tests/test_writing_page_equivalence.py（旧 writing 原样内嵌，含预热会话）。
- WritingPageMixin.writing（531 行）→ 薄方法 + _WritingPage 类（c2c 原样改写，共享 22 名、方法 30 个）；build 再按数据流切成 _build_composer／_build_dialog，最长 81 行。删除 writing 的长度上限登记。
- 测试同步（断言未动）：
  - test_data_table_boundary、test_script_rename_boundary：同时扫描薄方法与 _WritingPage（len==2）。原写法在改写后会只扫到 2 行的薄方法而空过。
  - test_shortcut_registry_boundary：字面标记改为 `self.page.shortcuts.bind(self.box,`（box 成了实例属性）。
  - test_script_workspace_results、test_writing_restart：抽出的 rename_script／script_menu 现在是方法，闭包变量改由 SimpleNamespace 实例提供；初始化失败测试把 _WritingPage 一起 exec。
  - skip 台账补一条。
- 已知：test_writing_status_line 的 DesktopStatusLineTests 依赖 0.18 秒的空闲等待，旧实现单独连跑 6 次也红 3 次，属原有不稳定，非本轮引入。
