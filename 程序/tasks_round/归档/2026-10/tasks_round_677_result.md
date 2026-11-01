# R677 修复轮结果：已勾选且被引用的 SKILL 无法删除

## 开头三问

1. 当前轮次与台账是否一致：开始时不一致；台账仍为 R672 待执行而最新结果已至 R676。本报告完成后已推进为 R678 待执行。
2. 上一轮进行中未完成的任务是什么：R675 已定位到删除链路的引用保护会阻止实际回收；用户现已确认该交互应支持确认后的删除。
3. 下一轮该做什么：请用户重启应用后验证“删除已勾选 SKILL”；若取消确认，文件应保留；若确认，文件应移入程序级回收站并从面板消失。

## 验证档位声明

本轮改动涉及 2 个模块（`skill_panel.py` 与 `tests/test_skills.py`），且触及删除确认异常边界，按分级规则执行默认冒烟 + `--affected skill_panel` + 架构门禁，跳过全量，理由：仅调整阶段配置 SKILL 删除确认路径，未触及启动路径、L0 契约、用户数据格式或删除路径权威服务。

## 根因与修复

- 根因：`skill_panel.py:960-964` 发现当前项目 `skill_config.json` 引用已勾选的注册 SKILL 后，显示警告并直接返回，因此 `recycle_paths()` 永远不会被调用。已勾选项通常正是当前配置中的引用，故用户无法删除。
- 修复：保留引用检查，但将阻断警告改为二次确认。确认文案明确说明配置仍有引用、下次读取会按既有失效项规则清理；用户确认后才调用既有 `storage_maintenance.recycle_paths()`。
- 删除范围不变：仅 `程序/skills/` 下的 `.skill.md` 可删除，回收位置仍为 `程序/工作流任务/回收站/`；未写入、清理或改动任何用户项目配置。

## 改动文件

- `skill_panel.py`：引用项从“直接拒绝”改为“明确告知后确认删除”。
- `tests/test_skills.py`：新增回归覆盖取消时源文件保留、确认时源文件进入既有回收服务；这是用户明确改变删除交互契约所需的断言更新，未弱化删除保护。

## 验证输出摘要

```text
python -B -m unittest tests.test_skills.PanelTests.test_referenced_program_skill_requires_confirmation_before_deleting
Ran 1 test in 0.168s
OK

python -B smoke_test.py
通过：8 项
失败：0 项

python -B smoke_test.py --affected skill_panel
共 125 条用例，21.9 秒；0 个文件有红
ALL TESTS PASSED

python -B smoke_test.py --architecture
Ran 102 tests
OK
```

## 用户数据未改动确认

未修改用户项目、`skill_config.json`、工作流调用设置或密钥；测试仅使用临时目录中的文件。

## J 后续

其他删除入口如同样以“引用存在”直接阻断删除，应另立一轮核对；本轮未改动它们。

## 自审

仅修改 SKILL 删除的确认分支及对应回归，仍复用既有回收服务，未引入新扫描或改变扫描根。
