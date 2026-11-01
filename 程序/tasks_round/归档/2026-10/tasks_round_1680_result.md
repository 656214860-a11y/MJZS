# R1680 修复轮：把仓库根 `.claude` 登记到 `test_root_layout.py` 的 ALLOWED

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。根因：R1676 把仓库根的 `.claude` 纳入版本控制，但 `tests/test_root_layout.py` 的 `ALLOWED` 字典未登记该入口，导致 `test_tracked_root_entries_are_registered` 红（报 `[.claude]` 未登记）。判定为登记遗漏，非代码偏离需求。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k root_layout`：修前 1 红、修后 1/1 全绿；默认冒烟 8/8。未跑架构门禁全量与安全全量（本轮仅改测试登记，无产品代码改动）。
3. **project_status.md 的欠账少了吗？** 不变（本轮为根目录入口登记补全，不涉及欠账条目增减）。

## A 改动

- `tests/test_root_layout.py`：`ALLOWED` 新增一条 `'.claude': 'Claude Code 项目配置（settings 等）'`，置于 `.claudeignore` 相邻处。断言未动，仅登记 ALLOWED。

## C 待用户裁决

无。

## 提交

见提交信息 `R1680:`。
