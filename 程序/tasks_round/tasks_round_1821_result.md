# R1821 结果（整理轮）

- 新增差分测试 tests/test_storage_summary_equivalence.py：旧 storage_summary 原样内嵌，10 种项目布局（基础、长／无效保留期、06_本地生成 账本、坏账本、rows 不是列表、回收站里的账本、被引用的来源、坏清单、空项目）× 有无 select_adopted，逐例对照完整盘点结果。夹具里有 40 多个版本行、3 个以上可回收候选。
- 压平：每个镜头逐版本判定那一段抽成模块级 `_shot_versions(root, ledger, shot, rows, select_adopted, scan)`，共享的累加集合放进 scan 字典；storage_summary 从嵌套 6 层降到上限内，删除 NESTING_CAPS 该项。
- 变异检查：让 cleaned_at 的版本不再跳过，测试变红。断言未动。
