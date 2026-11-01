# R1843 结果：修复 R1825–R1841 拆分引入的架构测试回归（修复轮）

- 改动：见 `tasks_round/重构批次ABCD总报告.md`“拆分引入的回归及修复”一节。代码：`keyframe_comfy.py` 拆出 `_KeyframeComfyRows`；`desktop_idea_chat.py` 新增参数对象 `_FlowAgentRequest`；`desktop_script_pages.py` 的 `_ContentBox.__init__` 用 `*spec` 收拢。测试：card／local_previs／project_context／writing_publication 四个架构测试的定位从函数名同步为类名或属性；`IdeaChatMixin` 登记 1031→770；`维护记录/架构统一基数.json` 一条 point 改名 run_background→_run_claude_json。
- 验证（本轮运行，隐藏桌面）：`run_selftests.py -k architecture keyframe idea_chat local_previs reference_wall script_pages script_structure cloud_video workflow_engines` 只剩预期常驻红 test_round_number_continuous；test_skill_reference_injection 9 条全绿。
- 断言未动。
