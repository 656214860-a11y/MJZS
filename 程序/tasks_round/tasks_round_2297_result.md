# R2297 结果

- 轮次类型：UI 修复轮。
- 模型管理表单：一行两框等宽并加大间距；Provider 下拉去掉「OpenAI 兼容接口」、默认「自定义」、按首字母排序；标签贴近下拉框。
- 剧本准备聊天页：用户气泡的名字、正文、引用行、底行右对齐（同 Claude Code 桌面版），模型回复仍左对齐。
- 测试：test_idea_chat 两处「用户气泡 left」断言按有意的契约变更改为 right（断言未弱化）；新增 test_model_manager_actions 两条。
- 已运行：run_selftests -k idea_chat bubble skill_panel_layout 通过；model_manager_actions／pet_model 此前通过。未运行全量。
