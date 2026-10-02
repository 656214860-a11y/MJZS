# R616 功能轮结果：已安装 SKILL 删除

- 本轮是功能轮还是整理轮？功能轮。
- 测试跑了吗？三个基线过了吗？新增专项回归 3/3 通过，`python smoke_test.py` 8/8 通过；架构基线与全量基线本轮未运行。`tests.test_skills` 120 条中有 2 条既有失败，定向门禁因此未通过，详见下文。
- `project_status.md` 的欠账少了吗？没有；本轮只实现删除功能，且距 R615 未满五个实际完成轮次，未更新台账。

## 范围与实现

修改文件：

- `skill_panel.py`：在阶段配置的 SKILL 管理下拉中加入“删除已安装…”。选择文件后先校验路径、显示二次确认，再调用 `storage_maintenance.recycle_paths()` 将入口文件移至个人 SKILL 目录下可恢复的回收站；成功后移除当前流程对此文件的勾选和配置引用。
- `tests/test_skills.py`：新增删除成功、外部文件拒绝删除两条回归，并更新下拉选项断言。
- `smoke_test.py`：补充 `skill_panel -> skills` 的定向测试映射，使 `--affected skill_panel` 实际执行既有 SKILL 面板回归，而非“未命中测试”。

安全边界：只允许删除 `%CODEX_HOME%/skills/<技能目录>/SKILL.md`（默认即 `C:\Users\LAIBIAO\.codex\skills\<技能目录>\SKILL.md`）这一层的个人安装入口文件。项目内置 `D:\漫剧制作助手\程序\skills`、用户手动附加的外部 `SKILL.md`、源码和配置均不会被删除。删除不是永久删除，文件会进入个人 SKILL 根目录内的“工作流任务/回收站”。

## 使用方式

重启程序后，在“剧本准备 → 阶段配置”的 SKILL 下拉中选择“删除已安装…”，选中要移除的个人安装 `SKILL.md`，确认即可。删除后当前流程的勾选会立即消失。

`D:\漫剧制作助手\程序\skills\01 剧本准备SKILL\` 下的 `.skill.md` 是本程序的阶段注册格式，无须安装到个人目录；重启程序后会作为该阶段的候选显示。若某个子目录是标准 Codex 技能包（包含入口 `SKILL.md`），可将整个子目录复制到 `C:\Users\LAIBIAO\.codex\skills\<新目录名>\`，使最终入口为 `...\<新目录名>\SKILL.md`，再在阶段配置中选择“新增”附加它。不要将单个 `.skill.md` 当作 Codex 包直接复制。

## 新增回归断言

1. 个人安装目录中的 `SKILL.md` 删除后，原文件不存在、当前流程 UI/配置均不再引用它，回收站中存在该 `SKILL.md`。
2. 个人安装目录外的 `SKILL.md` 请求删除时返回空、原文件仍存在，页面提示明确表示不会删除。
3. 管理下拉包含“删除已安装…”。

## 验证记录

执行命令：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B -m unittest tests.test_skills.PanelTests.test_delete_personal_skill_recycles_file_and_removes_current_flow_reference tests.test_skills.PanelTests.test_delete_personal_skill_rejects_external_skill_file tests.test_skills.PanelTests.test_the_skill_manage_dropdown_has_the_skill_actions
```

结果：`Ran 3 tests in 0.425s`，`OK`。

执行命令：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py
```

结果：8 项通过，0 项失败。

执行命令：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' smoke_test.py --affected skill_panel
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B -m unittest tests.test_skills
```

结果：定向门禁已实际命中 `tests/test_skills`，全文件共 120 条，2 条失败（与本轮删除路径无关）：

1. `PanelTests.test_the_skill_boxes_follow_the_flow_order`，`tests/test_skills.py:1239`：实际音频列表多出 `pipeline-audio-subtitle`，断言期望仍是四项。这是当前注册表/技能文件内容与旧固定列表不一致；本轮未变更注册表或音频技能。
2. `ToolTests.test_every_tool_in_the_registry_is_known`，`tests/test_skills.py:539`：`skill_tools.missing(names)` 返回 18 个工具名（首项 `asset.plan`，末项 `delivery.package`），断言期望空列表。这是工具注册表覆盖不足；本轮未变更工具注册规则。

因此专项和默认冒烟均通过，但 SKILL 专项完整门禁未通过，不能将全量 SKILL 基线宣称为通过。

## J 后续

1. 单开修复轮处理音频阶段固定顺序断言与实际注册项 `pipeline-audio-subtitle` 的契约，不在删除功能轮顺手改动。
2. 单开修复轮补齐或调整 18 个已声明工具的 `skill_tools` 注册契约，并恢复 `tests.test_skills` 全绿。

## 自审

- 只改了删除入口、其安全校验、对应回归与让定向门禁命中该回归的最小别名；未改 `/` 补全、UI 布局、项目内置 SKILL、`skill_config.json` 或用户项目数据。
- 删除操作采用已有可恢复回收站接口，且路径限制到个人安装 SKILL 的第一层包入口，未引入外部依赖。
