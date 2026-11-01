# R1958 修复轮：剧本结构页「自然剧本」的编辑按钮点了没反应

## 原因
用户反馈：剧本结构 → 自然剧本，点「编辑」后无法修改内容。

`_ScriptStructurePage.build` 给自然剧本框传入 `editable=self.source is not None`。`source` 来自 `script_contract.resolve_script_source`，只有“已采用且内容哈希仍一致”时才非空，因此下面两种情况都会让编辑按钮直接报“当前没有可修改的剧本文档。”：
1. 有多份自然剧本候选、还没点「采用选中剧本」；
2. 采用后编辑保存过一次——采用记录里的 sha256 对不上，页面重建后来源为空，从此再也编辑不了。

## 改动
- `desktop_script_pages.py`：自然剧本框改为 `editable=True`；编辑对象是下拉框当前选中的文档，`begin_edit` 原有的“没有文档就报错”检查保留。采用时的哈希校验（修改后须重新采用）不变。
- 保存自然剧本后，状态栏追加提示“如要据此制作结构剧本，请重新点击‘采用选中剧本’”。

## 测试
- 新增 `tests/test_script_structure_natural_edit.py`（2 条）：多份候选未采用时可编辑；采用后编辑保存、重新进入本页，仍可编辑。临时撤掉修复复跑，两条都红，报的正是“当前没有可修改的剧本文档。”。既有断言未动。

## 验证（经 `gui_hidden.py`）
- `-k script_structure_natural_edit script_structure_edit ui_reading_density`：21 条全绿。
- `smoke_test.py` 默认集：通过。
- `-k script_structure ui_edges architecture`：576 条，5 个文件有红，均与本轮无关：
  - `architecture.test_agents_md`、`architecture.test_skill_reference_injection`：worktree 缺 `维护记录/基准历史.json`、技能目录，属历史红。
  - `architecture.test_round_baselines`：1944 != 1958，领号后状态页尚未同步（状态页只能在 master 改）。
  - `test_ui_edges` 2～3 条：状态栏被后台版本检查覆盖成“检查新版本”；在改动前的代码上复跑同样红，次数随时序变化，属不稳定用例，待另行修复。
- 未跑 `--all --safe`；未在真实窗口目测。
