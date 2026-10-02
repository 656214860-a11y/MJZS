# R605｜功能轮：阶段配置 SKILL 说明排序与 Markdown 正文

## 本轮结论

- “SKILL 说明”目录已和上方工作流勾选区使用同一来源、同一顺序：工作流 SKILL 在前，阶段注册 SKILL 随后；适用所有存在工作流映射的阶段，不再只在剧本准备阶段附加工作流项。
- 说明区现在展示所选条目对应 Markdown 文件的完整内容。注册 `.skill.md` 和工作流 `SKILL.md` 均直接读取；目标文件不可读或不存在时，自动回退同目录 `README.md`。
- 未修改 SKILL 文件格式、注册表接口、模型配置或用户项目数据。打开应用后重启一次即可加载界面改动。

## 改动文件

- `skill_panel.py`
  - 新增 `markdown_document()`：按“目标 SKILL 文件 → 同目录 `SKILL.md` → 同目录 `README.md`”读取非空 Markdown 内容。
  - `note_text()` 与 `workflow_note_text()` 统一使用该读取逻辑；注册 SKILL 的说明不再只显示解析后的正文片段。
  - `Panel.build_notes()` 先收集 `flow_skill_choices(self._flow)`，再追加阶段注册 SKILL，使说明目录与上方工作流顺序一致。
- `tests/test_skills.py`
  - 覆盖说明目录与工作流顺序一致、工作流说明读取实际 `SKILL.md`，以及缺失 `SKILL.md` 时回退 `README.md`。
- `project_status.md`
  - 台账前进到 R606，并登记本轮能力与验证状态。

## 验证

- 精确回归：`tests.test_skills.PanelTests` 的说明排序、完整 Markdown、README 回退用例 3/3 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected skill_registry`：未通过，原因与本轮无关：
  - `tests/test_skills.py::PanelTests.test_the_skill_boxes_follow_the_flow_order` 仍将音频阶段旧 SKILL 数量写死，当前注册表多出既有 `pipeline-audio-subtitle`。
  - `tests/test_skills.py::ToolTests.test_every_tool_in_the_registry_is_known` 发现 18 个既有 SKILL 工具声明未登记到 `skill_tools`。
  - 本轮新增/调整的 3 条说明区回归均通过，未修改上述注册表数据或工具表，故未越界修复。

## 风险与后续

- README 回退只在目标 SKILL 文件无法读取时触发，不会覆盖存在的 SKILL 说明。
- 建议后续单独校正注册表工具清单与音频阶段数量断言，再恢复 `--affected skill_registry` 的全绿基线。
