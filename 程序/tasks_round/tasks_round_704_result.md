# R704 功能轮结果：统筹行的逐项套用确认与偏离明细

## 承接说明

承接 R703（完整安全全量 3,403 条／0 红）。核对指令 4 的现有实现后确认：统筹行、锁摘要、自由模式回退与空阶段保护均已落地；缺口仅为首次套用／切换的逐项确认，以及偏离徽标的可展开明细。本轮只补这两项，不改注册表、阶段勾选网格、持久化格式或用户项目数据。

## 完成内容

- `skill_panel.py`：选择统筹后先展示对照确认，而不是直接改写。首次套用只允许选择显式空阶段，已有勾选禁用且保持；切换统筹显示“旧建议／当前／新建议”三列，用户可逐项决定套用或保留。
- 偏离摘要中的“N 个阶段已本地修改”可点击展开只读明细，列出当前勾选与统筹建议；无偏离或自由模式时移除点击绑定。
- `tests/test_stage_config_hollmwood.py`：补充“仅填显式空阶段、既有阶段不覆盖、偏离计数”的回归。

## 验证

- `python -m unittest tests.test_stage_config_hollmwood tests.test_workflow_migration`：7 条通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected skill_panel stage_config workflow_settings`：9/9 通过；定向自检 143 条／0 红。
- `python smoke_test.py --architecture`：103 条通过。
- `python run_selftests.py --layer gui-short --safe --all`：1,079 条、300.4 秒、0 个文件有红；日志：`维护记录/r704_gui_short_final.out.log`。进程退出后的既有 Tk `after` 回调 stderr 噪声已分存 `r704_gui_short_final.err.log`，不影响汇总与退出成功。

## 三个基线数

- 默认冒烟：8/8 通过。
- 受影响冒烟：9/9 通过。
- GUI-short 安全全量：1,079 条／0 个文件有红。

页面改动需重启应用后生效。

[TASK_COMPLETE]
