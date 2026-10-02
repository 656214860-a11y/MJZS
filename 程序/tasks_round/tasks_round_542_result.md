# R542 修复轮结果

日期：2026-09-29  
范围：仅 `smoke_test.py` 的 `--affected` 源模块至测试筛选词映射；未改产品逻辑、SKILL 文件或测试断言。

## 轮次自答

1. 本轮是功能轮还是整理轮？均不是；本轮为修复轮。
2. 测试跑了吗？三个基线过了吗？运行了用户指定的定向门禁和默认冒烟。默认冒烟 8/8 通过；定向门禁有非零命中但未通过；架构及全量安全本轮未运行。
3. `project_status.md` 的欠账少了吗？部分减少：`--affected skill_registry` 的 0 条筛选缺陷已修复；但测试文件自身的既有红项阻止定向全绿，已登记。

## 改动

在 `smoke_test.py:460` 的 `_AFFECTED_TEST_ALIASES` 增加唯一映射：

```python
'skill_registry': 'skills',
```

`run_selftests.py -k` 按测试文件名片段筛选，`tests/test_skills.py` 的正确筛选词是 `skills`；其余筛选、门禁调度和模块均未改变。

## 验证

1. `D:\漫剧制作助手\运行环境\Python\python.exe -u smoke_test.py --affected skill_registry`
   - 命令实际展开为 `run_selftests.py --serial -k skills`。
   - 已命中 **1 个测试文件 / 17 个工作单元**，不再出现“跑 0 个测试文件”。
   - 结果未通过：`tests/test_skills.py` 现有断言红项。已核对的失败包括 `PanelTests.test_the_panel_shows_the_skill_markdown`（期望 5，实际 6）和 `PanelTests.test_the_skill_boxes_follow_the_flow_order`（额外 `pipeline-audio-subtitle`），另有 `ToolTests.test_every_tool_in_the_registry_is_known` 缺少 18 个工具登记。这些与本轮仅新增的映射行无调用关系，本轮未为通过门禁修改测试、SKILL 或工具注册。
2. `D:\漫剧制作助手\运行环境\Python\python.exe -u smoke_test.py`
   - **8/8 通过**。

## 结论

映射修复已完成并证明有非零命中。用户要求的“定向有输出、有通过”中，“有输出/非零条数”已满足；“通过”受 `tests/test_skills.py` 的既有失败阻塞，不能如实宣称验收全绿。需要独立授权后，才能处理该测试反映的 SKILL 数量、顺序与工具登记契约漂移。
