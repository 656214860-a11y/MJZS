# R1867 结果：测试瘦身第 1 批（整理轮）

- 本轮类型：整理轮。只删测试并同步跳过台账，没有改产品代码。
- 依据：`维护记录/测试瘦身审计_20261022.md`（本轮新增）。方法是让每个测试文件单独跑一遍行追踪，算出它的"独占产品行"。
- 删除了 10 个差分测试（`*_equivalence.py`）。它们对应的重构都已合入，全量也绿过（R1850）。这 10 个文件的独占产品行都是 0，即删掉后，其余测试仍覆盖它们走过的每一行。

| 文件 | 串行秒（追踪下） |
|---|---|
| test_asset_batch_failure_equivalence | 0.2 |
| test_asset_page_equivalence | 111.0 |
| test_local_previs_page_equivalence | 42.3 |
| test_native_asset_controls_equivalence | 11.1 |
| test_reference_wall_equivalence | 4.0 |
| test_step_verdict_equivalence | 0.3 |
| test_storyboard_files_equivalence | 28.8 |
| test_storyboard_page_equivalence | 13.2 |
| test_window_placement_equivalence | 4.7 |
| test_workspace_parse_equivalence | 0.1 |

- `test_script_structure_page_equivalence` 的独占行也是 0，但它提供的 `_open_app` 还被另外两个差分测试引用，所以留到第 2 批一起删。
- 跳过台账删掉了这些文件的 7 条登记位，266 条变成 259 条。
- 断言未动：其余测试一行没改。
- 验证：架构门禁和定向测试的结果见提交前的实测。全量由 post-commit 自动跑，结果以其凭据为准。
