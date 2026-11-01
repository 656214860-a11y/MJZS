# R1803：结构治理轮——压平 model_router.chat 与 idea_attachments._read_xlsx（批次 A 续）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。旧实现原样嵌进新测试做对照，再改写，再删登记。

2. 测试与基线：
   - `tests/test_model_router_parse_equivalence.py`：5 种 wire_api × 16 种响应形状（None／空／chat／responses／messages／推理字段／异常内容）逐例对照原内联解析，全绿。
   - `tests/test_xlsx_read_equivalence.py`：15 种工作簿（正常、公式、内联字符串、绝对目标、越界目标、缺共享串、非法索引、外部关系、坏 zip、坏 XML、无工作表…）加预算触线点扫描（字符上限 1–79、成员字节上限、文件大小上限），旧实现与新实现结果与异常（含 `__cause__` 类型）完全一致。预算计费顺序没动。
   - 相关既有测试 + 架构门禁 45 条全绿。完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 做法 | 嵌套 |
|---|---|---|
| `model_router.ModelRouter.chat` | 响应解析抽成模块级 `_parse_response`，按协议分派到 `_parse_messages`／`_parse_responses`／`_parse_completions`（默认），Responses 的 output 遍历抽 `_responses_output_text` | 8→登记删除 |
| `idea_attachments._read_xlsx` | 抽 `_xlsx_shared_strings`／`_xlsx_member`／`_xlsx_cell_value`／`_xlsx_row_lines` | 8→登记删除 |

## 评估后不动
`storage_maintenance.source_protection`（深度 7）：与 `version_retention`、`edit_source_versions`、回收站目录耦合，且缺现成夹具；补等价测试的成本高于收益，保留登记，留待补回收站用例后再拆。
