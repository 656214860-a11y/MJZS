# R522 修复轮：启动与操作响应卡顿

## 轮次自检

1. 本轮是功能轮还是整理轮？修复轮；修复可复现的剧本准备页输入交互卡顿，并降低无事可做时的主线程轮询负担。
2. 测试跑了吗？三个基线过了吗？本轮新增回归与相关页面回归 3/3、默认冒烟 8/8 均通过；已验证架构基线为 92/92，历史安全全量基线为 3,230 条，未因本轮降低。
3. `project_status.md` 欠账少了吗？已关闭“点击剧本输入框后持续抖动、助手卡死”的 P0 交互欠账；本轮未新增阻塞项。

## 根因与修复

- 根因：空闲提示 `Label` 被 `place(in_=input_box)` 覆盖在输入框上，未绑定点击转交。用户点击提示文字时，真正的 `Text` 未拿到焦点，提示的 35ms 动画没有停止，持续触发布局绘制。
- 修复：提示层点击现在显式聚焦并展开真实输入框，且直接取消提示动画回调；不依赖窗口激活瞬间的 `focus_get()` 结果。
- 性能收口：统一 `tick()` 心跳从 80ms 调整为 150ms。该循环只做队列消费和到期检查，不承担动画帧职责；调整后仍能及时处理后台结果，同时避免空闲时每秒 12 次完整自动化调度抢占 Tk 主线程。

## 修改范围

- `desktop.py`
- `tests/test_idea_chat.py`
- `project_status.md`

未修改用户项目数据、模型配置、密钥或阶段配置面板逻辑。

## 验证

- `tests.test_idea_chat.SendMessageTests.test_clicking_empty_composer_settles_on_one_expanded_height`
- `tests.test_idea_chat.SendMessageTests.test_clicking_the_composer_hint_focuses_the_real_input_and_stops_animation`
- `tests.test_ui_edges.UiEdgeTests.test_the_writing_page_gives_the_brief_more_room`
- 结果：3/3 通过。
- `smoke_test.py`：8/8 通过。

## 自检复核

通过：修复覆盖了提示层吞点击的直接根因，并由真实 Tk 页面回归锁定“提示层点击后撤销动画”。150ms 心跳不改变阶段自动化的到期/退避语义；未做无关重构。
