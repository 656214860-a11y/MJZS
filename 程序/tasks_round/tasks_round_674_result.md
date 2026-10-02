# R674 修复轮结果：阶段配置 SKILL 面板布局重构

## 开头三问

1. **当前轮次与台账是否一致？** 本报告对应 R674；尚未将本轮标记完成，因为声明范围内的受影响门禁未取得汇总。
2. **上一轮进行中未完成的任务是什么？** 本轮开始时的直接待办是 SKILL 面板布局混排、长名称挤出与说明区顺序/同步问题。
3. **下一轮该做什么？** 另立门禁排障轮，定位 `tests.test_skills.PetIntegrationTests` 的独立卡住原因；不得在本轮范围内修改它。

## 验证档位声明

本轮改动涉及 1 个生产模块（`skill_panel.py` 的 SKILL 面板布局）和对应回归测试，按分级规则执行默认冒烟 + `--affected skill_panel`，跳过架构门禁与全量，理由：只调整单面板的控件容器、排版与 UI 同步，不触及启动路径、契约、扫描、配置写入或用户数据。

状态：**[TASK_FAILED]**。默认冒烟通过；但 `--affected skill_panel` 在既有 `test_skills#11` 工作单元未取得汇总，按本轮失败判定不得报通过。

## 只读诊断（改动前）

- `skill_panel.py:765-815`：`build_flow_skill()` 将 SKILL 标签、全选下拉、注册 SKILL 勾选框、流程勾选框和删除按钮全加入 `flow_skill_row`；删除按钮与勾选框的父容器相同。
- `skill_panel.py:837-852`（改动前对应区段）：所有项进入 `skill_controls`，由同一个自然宽度换行器排版；长名称会扩大单项请求宽度，进而影响同一行其他控件。
- `skill_panel.py:877-895`（改动前对应区段）：`layout_skill_controls()` 以 `winfo_reqwidth()` 与容器宽度决定换行，因而没有稳定的列数或操作栏边界。
- `skill_panel.py:1160-1172`：说明目录现由 `self.skills`（初始化时直接取 `registry.getByStage(self.stage)` 的原始返回顺序）和流程候选共同构造；已移除重复追加注册项，勾选与说明使用同一注册表遍历源。
- `.codex` 检查：`skill_panel.py` 中没有 `.codex`、`_home_skill()` 或用户目录拼接；`flow_skill_choices()` 的回归也断言候选路径位于 `skill_registry.default_root()`。本轮没有发现可移除的 `.codex` 残留路径，未改扫描逻辑。

## 修复后的布局（ASCII）

```text
┌──────────────────────── 操作栏 ────────────────────────┐
│ SKILL  [全选／取消／新增 v]          [删除已勾选 SKILL] │
└────────────────────────────────────────────────────────┘
┌────────────────────── 勾选框列表 ──────────────────────┐
│ [ ] 注册 SKILL 1                 [ ] 注册 SKILL 2       │
│ [ ] 注册 SKILL 3                 [ ] 流程 SKILL         │
│ 少于 10 项：固定两列；超过 10 项：单列 + 右侧滚动条。   │
└────────────────────────────────────────────────────────┘
┌────────────────────── SKILL 说明 ──────────────────────┐
│ [名称列表（注册表顺序）]  │  [所选 SKILL Markdown 预览] │
└────────────────────────────────────────────────────────┘
```

## 改动文件

- `skill_panel.py`
  - 新增独立 `skill_action_row`、`skill_list_outer` 和滚动容器；删除按钮不再与勾选框共享父容器。
  - 少于 10 项时固定两列；超过 10 项时启用 Canvas + Scrollbar 单列列表。
  - 勾选框固定宽度 28；长名称经 `skill_label()` 截断，悬停显示全文。
  - 注册 SKILL 先按 `self.skills` 的注册表顺序建立，说明目录复用相同顺序；说明列表点击会聚焦对应顶部勾选框。
  - `refresh_notes()` 仍在页面建立时调用，注册勾选变化仍经 `save_and_refresh_notes()` 刷新说明区。
- `tests/test_skills.py`
  - 更新既有布局断言，并新增操作栏/列表父容器分离、注册表顺序、滚动阈值、长名截断、说明列表同步的回归断言。

未改：`skill_registry.py`、扫描根/缓存键、业务保存逻辑、配置写入、用户数据、密钥。

## 验证原始输出片段

```text
python -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

```text
python -B smoke_test.py --affected skill_panel
--- 门禁：run_selftests.py（定向：skill_panel）---
跑 1 个测试文件 / 18 路工作单元（串行）
test_skills#1 ... #10 均通过
→ 开始 test_skills#11
```

`test_skills#11` 是 `PetIntegrationTests` 的八项宠物集成测试；独立执行 `python -B -m unittest tests.test_skills.PetIntegrationTests` 同样未返回汇总。该类不创建 `skill_panel.Panel`，因此现有证据不支持将卡住归因于本轮布局改动；但本轮按失败判定仍不得通过。

## 用户数据未改动确认

未修改任何项目目录、`skill_config.json`、用户配置或密钥；仅改动面板源码、对应测试和本结果文件。

## J 后续

- 另立一轮检查 `PetIntegrationTests` 隐藏 Tk 根窗口/对话门禁的卡住路径，取得受影响门禁完整汇总后，再重新验证本 UI 轮。
- 其他面板如仍存在自然宽度换行混排，不在本轮顺手处理。

## 自审

- 生产代码仅改 `skill_panel.py` 的 SKILL 面板布局、显示截断及 UI 焦点同步。
- 未引入新扫描、未修改注册表顺序来源、未改任何业务保存或配置写入。
- 本报告提供修复后 ASCII 布局示意；由于门禁未完成，明确标记 `[TASK_FAILED]`。
