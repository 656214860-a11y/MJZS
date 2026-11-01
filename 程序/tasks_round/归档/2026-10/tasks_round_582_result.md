# R582 修复轮结果：剧本准备长输入框回归契约

## 结果

完成本轮目标：修正 `test_ui_edges` 中与现行响应式输入框规则冲突的旧断言；**未修改任何生产代码**。

## 根因与处理

- 旧测试 `ContentBoxFitTests.test_a_very_long_composer_keeps_all_typed_content_visible()` 曾要求 `show_all_content()` 将 200 行内容框扩展到至少 200 行。
- 现行生产规则在 `desktop.py:3548` 明确将剧本准备发送框限制在 `TALK_MIN_LINES` 至 `TALK_MAX_LINES`（6–15）行，以保留发送操作与下方文件表可见；该规则已有相邻响应式测试覆盖。
- 将旧测试改为 `test_a_very_long_composer_stays_within_the_responsive_limit()`：验证高度处于现行最小／最大边界内，并验证第 200 行文本仍保留。没有删除覆盖，也没有降低数据完整性要求。

## 改动文件

- `tests/test_ui_edges.py`：仅替换 1 个过时的 UI 断言及测试名／说明；生产模块、用户数据、布局和运行时事件均未改动。

## 验证

| 命令／范围 | 结果 |
| --- | --- |
| 精确 `test_ui_edges#3` | 8/8 通过（最终断言） |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --affected ui_edges` | 109 条，321.8 秒；第 3 分组通过，但 8 个其他分组共 14 条失败 |

## 阻塞项（P0）

完整 `ui_edges` 门禁未全绿，且失败不由本次测试契约迁移引入。主要证据：`Desktop.tick` 已迁移后旧测试仍直调该属性；启动异步状态断言仍期待同步文案；若干页面结构、流程顺序和间距断言与当前实现不一致。运行期间另出现多次 Tk `after` 残留回调错误：`invalid command name "...run"`。这些应在下一独立 P0 回归治理轮逐项分类、确认现行契约后处理，禁止为了全绿而批量弱化断言。

## 结论

本轮指定的长输入框回归已修复，默认冒烟保持通过；完整 UI 回归存在既有／独立阻塞，已如实登记，未宣称全绿。
