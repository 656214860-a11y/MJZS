# R1871 修复轮：剧本结构编辑可直接退出、结构剧本新增「删除」

## 改动
- `desktop_script_pages.py` `_install_script_edit_controls`：
  - 编辑态下「编辑」按钮不再置灰，改成可点的「退出」。没有改动时直接退出；有未保存的改动时先确认，确定后放弃改动、恢复原文。退出后预览回到只读，按钮文字恢复为「编辑」。修复的是用户报告的问题：点了下框「编辑」但不改动时，没有任何退出途径。
  - 仅结构剧本框（kind='structured'）在「保存」右侧新增「删除」：非编辑态且有当前文件时可点；先弹危险确认框，确定后沿用内容框已有的 `delete_document`，即 `storage_maintenance.recycle_paths` 移入项目回收站，然后刷新页面。
- `project_status.md` 未改：本工作区是游离 HEAD，规则规定状态页只能在 master 上改。当前轮次头（1853）落后于结果文件，所以架构门禁 `test_round_number_continuous` 在本树为红，属轮次头欠账，不是代码回归；合入 master 时一并补上。
- 测试 `tests/test_script_structure_edit.py`：新增 4 条用例，分别覆盖未改动直接退出、有改动退出先确认、结构剧本的删除按钮位置与确认、自然剧本框没有删除按钮。测试用的假 box 补了 `set_preview`／`delete_document`。原有断言未动。
- “上框编辑没反应”：用真实 Desktop 探针（`工作流任务/probe_structure_edit.py`）在下框编辑中再点上框，上框能正常进入编辑，未复现。改动后两框可以各自进入、退出编辑。

## 验证（本轮实跑，隐藏桌面）
- 定向 4 个测试文件（script_structure_edit、script_structure_page_equivalence、ui_batch5、ui_edges）：131 条，0 红；`-k script_structure` 中的非 GUI 文件同样 0 红。
- 真实页面探针：进入编辑、退出编辑、上框与下框交替操作、删除后文件移走、按钮置灰，均符合预期。
- 架构门禁：384 条，只有上述轮次连续性 1 条红（临时改轮次头到 1872 后复跑为 0 红，复跑后已撤回该改动）。
- 冒烟测试：通过。
- 未做：全量测试；真机目视检查，待用户复验。
