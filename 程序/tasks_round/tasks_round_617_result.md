# R617 修复轮结果：按勾选删除个人 SKILL

- 本轮是功能轮还是整理轮？修复轮；修正 R616“还要再选一次文件”与用户指定交互不一致的问题。
- 测试跑了吗？三个基线过了吗？新增/调整后的专项回归 3/3 通过，默认 `smoke_test.py` 8/8 通过；架构基线与全量基线本轮未运行。受影响门禁命中完整 `test_skills` 后仍有 2 条既有独立失败，故三个基线未全部通过。
- `project_status.md` 的欠账少了吗？没有；本轮未处理台账欠账，且未到每五个实际轮次的状态更新节点。

## 根因与修复

R616 将删除入口放进“SKILL”管理下拉，并在操作后打开文件选择器；这使用户已在面板中勾选的目标没有被使用。

`skill_panel.py` 的修改：

1. 管理下拉恢复为“全选／取消／新增”三项，删除不再是下拉动作。
2. 工作流 SKILL 勾选区新增“删除已勾选”按钮。
3. 点击按钮只收集当前已勾选、且路径严格为 `%CODEX_HOME%/skills/<技能目录>/SKILL.md` 的个人安装入口。未勾选项、项目内置 SKILL、手动附加的外部 SKILL 均不会删除。
4. 二次确认会列出本次将删除的全部已勾选个人 SKILL；确认后统一调用 `storage_maintenance.recycle_paths()` 移入可恢复回收站，移除本流程引用和对应勾选框。
5. 未勾选个人安装 SKILL 时，按钮明确提示原因，不进行删除。

## 回归

`tests/test_skills.py` 更新的断言没有弱化：

1. 个人 SKILL 被勾选后，点击删除会移入回收站，并从当前流程 UI/配置移除。
2. 即便外部 `SKILL.md` 被勾选，点击删除也返回空、文件保留，且显示“不会删除”。
3. 管理下拉不含删除项，删除按钮文本为“删除已勾选”。

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B -m unittest tests.test_skills.PanelTests.test_delete_personal_skill_recycles_file_and_removes_current_flow_reference tests.test_skills.PanelTests.test_delete_personal_skill_rejects_external_skill_file tests.test_skills.PanelTests.test_the_skill_manage_dropdown_and_delete_button_have_the_skill_actions
```

结果：`Ran 3 tests in 0.478s`，`OK`。

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py
```

结果：8 项通过，0 项失败。

执行：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py --affected skill_panel
```

结果：定向命中 `tests/test_skills`，但退出码 1；与 R616 相同的两条既有独立失败仍在：

1. `PanelTests.test_the_skill_boxes_follow_the_flow_order`（`tests/test_skills.py:1239`）：实际音频注册项多出 `pipeline-audio-subtitle`，旧断言只期待四项。
2. `ToolTests.test_every_tool_in_the_registry_is_known`（`tests/test_skills.py:539`）：`skill_tools.missing(names)` 仍返回 18 个未注册工具名。

这两项均不涉及删除按钮、勾选收集或回收路径，本轮未修改其根因模块。

补充：曾运行 `py_compile`，但受限环境禁止写入项目 `__pycache__`，报 `Permission denied`；专项 unittest 已实际导入并运行修改模块，故未把该环境写入失败误记为产品语法失败。

## 自审

- 满足验收：用户勾选个人安装 SKILL 后，点击“删除已勾选”即可删除，且可恢复。
- 范围：仅改 `skill_panel.py` 与已有 `tests/test_skills.py`；未改 UI 布局契约、`/` 补全、注册规则、配置格式或用户项目数据。
- 删除仍统一经 `storage_maintenance.recycle_paths()`，没有新增越界依赖。
- 同类检查：外部/内置 SKILL 即使被勾选也不会删除；未勾选个人 SKILL 也不会删除。
- 自审结论：功能实现通过；完整受影响门禁因两条既有独立失败未通过，不能标记全量基线完成。
