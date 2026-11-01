# R606｜功能轮：剧本准备 SKILL 导入与失效勾选清理

## 本轮结论

- `skills/01 剧本准备SKILL/` 当前三份有效 SKILL 已通过 `skill_registry` 识别并进入剧本准备阶段配置：`pipeline-script-preparation`、`script-dialogue-polish`、`script-emotion-curve`。
- 用户打开“剧本准备 → 阶段配置”时，面板现在按需强制刷新注册表；新导入的阶段 SKILL 无需等待应用启动缓存失效即可显示，已经删除的阶段文件也不会遗留勾选框。
- 已删除的自定义工作流 `SKILL.md` 路径会从工作流勾选区移除，并同步写回当前工作流配置，避免下次打开面板重新出现。

## 改动文件

- `skill_panel.py`
  - `Panel.__init__()` 在用户主动打开阶段配置时执行 `registry.scan(force=True)`；该操作不在启动路径执行。
  - `refresh_flow_checks()` 只为真实存在的 `SKILL.md` 创建／选中勾选框，并返回有效路径。
  - `load()` 比对已保存路径与有效路径，发现已删除文件即通过现有 `set_flow_skills()` 回写清理。
- `tests/test_skills.py`
  - 覆盖剧本准备阶段默认包含当前导入的三份 SKILL。
  - 覆盖自定义 `SKILL.md` 删除后，重新打开阶段配置时勾选框与工作流配置均不再保留它。

## 验证

- 精确回归：剧本准备导入、删除自定义工作流 SKILL、既有自定义 SKILL 保存，共 3/3 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected skill_registry`：仍未通过，失败与本轮无关：
  - 音频阶段旧数量断言未包含既有 `pipeline-audio-subtitle`。
  - `ToolTests.test_every_tool_in_the_registry_is_known` 仍发现 18 个既有 SKILL 工具声明未登记至 `skill_tools`。
  - 本轮未修改音频注册数据、工具表或无关测试断言，故未越界处理。

## 风险与操作

- 清理仅针对已不存在的自定义工作流 `SKILL.md`，不影响仍存在的用户自定义文件或阶段 SKILL 选择。
- 请重启应用后打开“剧本准备 → 阶段配置”，即可看到导入结果与已清理的勾选框。
