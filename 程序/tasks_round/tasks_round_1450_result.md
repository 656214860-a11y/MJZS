# R1450 结果：剧本页按钮「删除剧本」改名「删除」并移到「刷新」右侧

三个收尾问题：
- 本轮类型：功能轮（界面，单点）。
- 测试：`run_selftests.py -k test_idea_chat test_ui_edges` 通过（`test_ui_edges` 首次有 1 条与本改动无关的偶发红，`'紧张地' != '窗边的猫'`，单独重跑通过）；新增 `test_delete_button_sits_right_of_refresh`。未跑全量。
- 欠账：无变化。

## 改动
- `desktop.py`：按钮文字「删除剧本」→「删除」；动作栏按子控件创建顺序排列（FlowBar 把 pack 转成 place），所以把创建位置挪到「刷新」之后，不能只改 pack 方向。顺序现为：发送、阶段配置、中断、刷新、删除、下载文件、添加剧本、剧本目录、查看质检报告、质检目录。
- 测试文案同步（断言逻辑未动）：`test_idea_chat.py` 两处标签集合、`test_ui_edges.py` 一处；注释里的旧名同步。
