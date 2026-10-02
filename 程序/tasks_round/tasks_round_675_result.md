# R675 修复轮结果：删除 SKILL 功能失效诊断与回归

## 开头三问

1. **当前轮次与台账是否一致？** 本报告为 R675；由于声明档位未获得完整汇总，本轮不能登记为完成。
2. **上一轮进行中未完成的任务是什么？** R674 的 `test_skills` 受影响门禁在 `PetIntegrationTests` 工作单元卡住，未取得汇总。
3. **下一轮该做什么？** 单独排障该宠物集成测试卡住问题后，重新执行 R675 的受影响与架构门禁；不要在本轮改变用户配置以绕过引用保护。

## 验证档位声明

本轮涉及 `skill_panel.py` 对既有回收服务的删除调用链审计及 `tests/test_skills.py` 回归补充，按分级规则执行默认冒烟 + `--affected skill_panel` + 架构门禁，跳过全量，理由：删除路径、回收服务调用与注册表刷新边界需要联验，但不涉及启动路径、L0 契约或用户数据格式。

状态：**[TASK_FAILED]**。默认冒烟和目标删除回归通过；`--affected skill_panel` 与架构门禁均未取得完整汇总，不能报通过。

## A. 删除按钮真实行为

- **A1 绑定位置**：`skill_panel.py:790-792`，`SecondaryButton(... command=self.delete_checked_skills)`。
- **A2 文件操作结论**：不是只刷新 UI。`skill_panel.py:969` 调用 `recycle_paths(program, ...)`；`storage_maintenance.py:48-65` 最终以 `shutil.move()`（第 44 行）移动文件并写入回收清单。
- **A3 调用链**：
  `删除已勾选 SKILL` → `Panel.delete_checked_skills()`（947）→ 确认所选 `.skill.md` 位于 `程序/skills/`（949-968）→ `storage_maintenance.recycle_paths()`（969）→ `_recycle()`（34）→ `shutil.move()`（44）→ `registry.scan(force=True)`（981）→ 销毁已删勾选框、刷新说明与布局（974-984）。

## B. 实际删除效果

- **B1 实物检查**：当前工作区不存在 `程序/工作流任务/回收站/`，也没有提供用户所称的文件名或项目目录，故没有可归属到该用户操作的历史文件可查；未伪造结论。
- **B2 实际目标路径**：`storage_maintenance.py:29-31` 固定为 `程序/工作流任务/回收站/自动维护_时间戳/skills/...`。
- **B3 扫描范围**：`skill_registry.py:42-44` 的根是 `程序/skills/`，递归只发生在该根（397）。回收站在程序根下、`skills/` 外，故不会重新发现回收文件。

## C. UI 刷新与缓存

- **C1**：删除成功后销毁对应控件、从 `self.skills` / `self.vars` 移除，再 `refresh_notes()` 与固定列重新排版（973-984）。
- **C2**：注册表缓存以 skills 根和一级子目录 mtime 组成键（366-406）；删除路径还显式 `self.registry.scan(force=True)`（981），不会依赖旧清单。
- **C3**：本删除入口不清理用户引用，而是先以 `_referenced_skills()` 只读检查（939-945）；存在引用时警告并返回，不吞异常、不删除文件（960-964）。这是避免破坏用户配置的保护，不是 UI 刷新失败。

## D. 用户配置残留

当前工作区没有用户项目根、`skill_config.json` 或“工作流调用设置”文件可检查；因此无法断言某一用户项目有无残留。现有代码对当前项目 `skill_config.json` 的引用会拦截删除，且本轮未修改任何用户数据或配置。

## 根因结论与修复

未复现“已移动后仍显示”的代码路径：回收目标、扫描范围、强制失效和 UI 移除均已存在且目标回归通过。可观察到“点击后仍出现”的唯一受保护路径是：所选 SKILL 仍被当前项目 `skill_config.json` 引用，函数弹出警告并**不执行删除**。

本轮不擅自清除用户引用（与禁止修改用户配置一致）。唯一改动为补齐重启回归：

- `tests/test_skills.py`：删除后新建 `Registry(root=program/'skills')`、强制扫描并断言被删名称不存在，覆盖“重启应用仍不出现”。

## 回收站实际路径

`程序/工作流任务/回收站/自动维护_YYYYMMDD_HHMMSS/skills/<原相对路径>`。

## 新增/现有回归断言

1. 已删 `.skill.md` 不存在于原 `skills/` 路径。
2. 回收副本在程序级 `工作流任务/回收站/`，不在 `skills/` 下。
3. 删除后 `panel.vars` 不再含该 SKILL，证明面板立即刷新。
4. **本轮新增**：新建注册表（模拟重启）后不再含该 SKILL。
5. 有 `skill_config.json` 引用时显示警告、不确认删除且源文件保留。

## 验证原始输出片段

```text
python -B -m unittest tests.test_skills.PanelTests.test_delete_checked_program_skill_recycles_it_and_refreshes_the_panel
Ran 1 test in 0.157s
OK
```

```text
python -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

```text
python -B smoke_test.py --affected skill_panel
既有 test_skills 工作单元在 PetIntegrationTests（#11）未取得汇总。

python -B smoke_test.py --architecture
架构测试已开始并输出通过项，但未取得完整汇总行。
```

## 用户数据未改动确认

未修改任何用户项目、`skill_config.json`、工作流调用设置、密钥或程序 SKILL 文件；测试仅在临时目录创建并回收测试文件。

## J 后续

- 其他删除入口若使用非 `storage_maintenance.recycle_paths()` 的路径，另立轮次审计；本轮未扩展检查或修改。
- 修复 `PetIntegrationTests` 卡住后，重新跑本轮三档验证。

## 自审

- 未改删除生产代码，因为诊断和目标回归已证实现有回收、刷新与缓存失效链完整。
- 仅复用既有回收服务；未新增扫描，未改扫描根或缓存键。
