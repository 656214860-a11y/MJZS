# R1103 默认示例恢复只读气泡

- 类型：修复轮（含全量基线验证）；移除上方简报编辑框，恢复默认示例只读气泡。
- 验证：执行中，尚未满足完成条件；不引用历史测试为本轮通过。
- 欠账：本轮只处理默认示例展示和发送来源，不处理历史队列。

## 范围和契约

生产改动仅 desktop.py。删除上方编辑器、回填及草稿状态，删除旧气泡里编辑软件示例的入口。默认示例完整显示在空会话气泡，可选择复制，八项必填标记仅用于展示。下方输入框保持空白和 Enter 发送行为。

发送只读取下方输入及本轮附件，不再合并默认示例，不再用默认示例作占位值比较。沿用原附件字段提取和别名、八项 UI 门禁及底层四项契约；缺项提示并不落盘、不启动。正式用户输入成功后仍另存 brief_creation.md。未改默认示例文件、idea_chat.py、script_contract.py、附件解析服务和用户数据。

## 测试契约迁移

用户明确撤销 R1101/R1102 的上方编辑器契约。依 AGENTS.md §2.4，同步 test_idea_inline_brief、test_idea_chat、test_ui_edges、test_desktop_startup_perf、test_idea_chat_attachment_refresh。上方编辑、回填、双框合并和占位值比对断言改为只读展示、输入保持和仅提交实际输入的断言；未修改底层纯函数契约测试。缺项不落盘／不启动、启动失败保留草稿、附件路径不泄漏正文、默认文件不变和首屏时间阈值继续保留。

## 实跑证据

- 初次直接 unittest 因未经过仓库测试入口，缺 skip_reasons 导入路径；改用 run_selftests.py，不修改导入边界来绕过问题。
- 第一轮相关回归发现调用方漏传仍为必需的 is_example 参数，已固定传 False，控制器不改。
- 专项 `run_selftests.py -k idea_inline_brief idea_chat_attachment_refresh`：23/23，16.8 秒。
- 较大回归 `run_selftests.py -k idea brief workflow ui_edges desktop_startup_perf`：379 条，232.5 秒，2 项失败。一个新断言误用 Text.tag_bind 查询签名，改用原生 Tk 查询；另一个首事件循环并行测得 2.679 秒，超过 2.6 秒。未调高性能门槛。
- 失败项复测：`run_selftests.py -k desktop_startup_perf` 14/14，12.2 秒；直接 unittest（显式加入 tests 导入路径）执行 BriefTintTests，5/5，7.712 秒。
- `run_selftests.py --layer architecture --all`：308/308，29.0 秒，数量与改前 308 一致；TODO 快照只更新移动的注释行号。
- `smoke_test.py --affected idea_chat workflow`：9/9，内部门禁 73 秒、0 红；`smoke_test.py`：8/8。
- 完整安全全量待执行完成后记录，不将上述失败批次记为整体通过。

## 收尾

中央领取 R1103，无匹配队列 ID；validate 0 errors，1 条既有历史租约警告，未修改历史租约。新增代码凭据形态扫描 0 命中；diff --check 通过。准备提交验收检查点，完整安全全量尚未完成。未读取真实创作项目、未调用真实模型、未重启真实应用；自动 UI 测试仅使用临时项目。收尾缓存扫描仅 dry-run，既有缓存归属非本轮，不删除。
