# R2576 结果：修复合并门禁——SKILL 导入边界测试的 skip 原因常量化

## 类型与三问

- 类型：修复轮（合入门禁暴露的缺陷）。
- 测试：`run_selftests.py -k skip_hygiene` ALL TESTS PASSED；`run_selftests.py -k skill_import_validation` 见下。
- project_status 欠账：无新增。

## 根因与修复

- R2569 新增 `test_package_with_symlink_is_blocked` 使用了字面 skip 理由，违反 `test_skip_hygiene`（skip 必须引用 `tests/skip_reasons.py` 模块级常量，台账双向相等）。
- 修复：新增 `PLATFORM_SYMLINK` 常量并登记 `ALL_SKIP_REASONS`；测试改引常量；`维护记录/skip台账.json` 补一条台账（277 条）。
- 未弱化断言：skip 仍在符号链接不可用时跳过，恢复条件不变。

## 提交

- 待提交后回填 hash。
