# R1811：结构治理轮——压平 engine_probe.main 与 script_workspace_service.iter_script_documents（批次 A 续）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。旧实现原样嵌进新测试做对照，再改写，再删登记。

2. 测试与基线：
   - `tests/test_engine_probe_main_equivalence.py`：命令行 24 种手写组合 + 每个引擎 × `--dry-run`／`--no-record`／`--json` 的全部开关组合，× 3 种探测结论（正常／缺开关／一次性失败），逐例对照旧 `main` 的**标准输出与返回码与对 probe／record／summary 的调用**；另一条验证 `argv=None` 读 `sys.argv`。`probe`／`record`／`summary` 在两边命名空间里同时替身，保证对照的是解析与编排而不是外部命令。
   - `tests/test_script_documents_equivalence.py`：旧生成器原样内嵌，在 17 个目录布局夹具上逐例对照 `(类别, 路径, 修改时间, 相对路径)` 序列：无 writing 目录／空目录／writing 是个文件、内部工作稿（仅有／空／与正式剧本同内容被去重／不同内容／先遇到 docx／同内容但在非剧本类别／正式文件编码损坏）、上传创意（含同名目录、非创意文件）、四种批次深度（`创意_*`、`Provider/创意_*`、`Provider/Model/创意_*`、更深一层应被忽略）、后缀大小写与目录冒充、批次名冒充文件、分类目录是文件、目录符号链接与文件符号链接逃逸（无符号链接权限时自动跳过）。测试自身断言不是空对空（≥25 条文档、≥3 个夹具里出现过内部工作稿）；另一条验证**惰性消费**——逐个 `next` 取前 5 项，再比较剩余序列。
   - 架构门禁 + 相关既有测试共 438 条：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 做法 | 嵌套 |
|---|---|---|
| `engine_probe.main` | 参数解析提成 `_parse_args`（开关表 `_SWITCHES`＋带值参数表 `_VALUE_FLAGS`；返回 `(选项, None)` 或 `(None, 退出码)`），`main` 只剩编排 | 7→登记删除 |
| `script_workspace_service.iter_script_documents` | 提成 `_find_draft`（内部工作稿，状态用一个小字典传递，因为扫描批次时要清掉它）、`_uploaded_idea_documents`、`_creative_batches`、`_batch_folder_documents`，主生成器用 `yield from` 串起来，惰性与顺序不变 | 6→登记删除 |
