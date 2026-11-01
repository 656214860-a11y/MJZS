# R1869 结果：测试瘦身第 2 批 a（整理轮）

- 本轮类型：整理轮。只改测试，产品代码一行没动。
- 依据：`维护记录/测试瘦身审计_20261022.md` 的 A2 档。这一档的差分测试各自独占一些产品行，所以先把这些行补成普通的行为测试，确认补齐后再删差分测试。
- 怎么确认补齐：把审计时记下的独占行，按源码原文对到当前文件里，再看替代测试有没有跑到这些行（脚本在 `Temp/audit/verify.py`，不进仓库）。下表 5 个文件都是 0 行漏掉。

| 删掉的差分测试 | 独占行 | 替代测试（新增或扩充） |
|---|---|---|
| test_model_router_parse_equivalence | 5 | 新增 `tests/test_model_router_parse.py`，4 条：各协议外壳下取哪段正文、按什么顺序兜底 |
| test_engine_probe_main_equivalence | 43 | `tests/test_engine_probe.py` 加 `MainTests`，5 条：参数解析的每条退出路径、退出码、台账与 JSON 开关 |
| test_xlsx_read_equivalence | 3 | `tests/test_idea_attachments.py` 加 2 条：没有共享串表、工作表路径越界、共享串编号越界或非数字 |
| test_source_protection_equivalence | 7 | `tests/test_storage.py` 加 `SourceDeclarationErrorTests`，2 条：5 种坏来源声明各自报错；成片清单读坏就跳过，没有版本号的行仍保留摘要 |
| test_storage_summary_equivalence | 3 | `tests/test_storage.py` 加 `StorageSummaryVersionTests`，1 条：已清理的版本不盘点；回收站里的台账不扫；过期旧版只要还被资产引用，就留住 |

- 断言未动：现有用例的断言一条没改。`test_idea_attachments.make_xlsx` 加了"覆盖成 None 就不写这个部件"，只用于新用例，旧用例的行为不变。
- 验证：替代测试在隐藏桌面实测通过：test_storage 20/20、test_idea_attachments 25/25、test_engine_probe 28/28、test_model_router_parse 4/4。架构门禁和冒烟见提交前实测。全量由 post-commit 自动跑。
- 剩余：A2 档还有 16 个，加上 `test_script_structure_page_equivalence`（它的 `_open_app` 被另外两个差分测试引用），共 17 个，交给下一会话。
