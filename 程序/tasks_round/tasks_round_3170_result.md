# R3170 结果：设置页 SKILL 删除占用守卫补齐
<!-- round-evidence: {"commit_base": "a6b4b83f", "credential_hits": 0, "evidence_sha256": "03cba01a7f8b10aa", "exit": 0, "failed": 0, "passed": 49, "round": 3170, "tests": "run_selftests.py -k skill_lifecycle pet_skills_manage skill_security"} -->

**类型**：修复轮（修复 master R3167 已有 SKILL 管理页遗漏的删除占用守卫）。
**测试**：先红后绿。新增服务用例改前报 `skill_delete_block_reason` 不存在／`uninstall_skill_entry` 不接受项目参数；新增 UI 用例改前显示删除被服务阻止但按钮和 Tooltip 未更新。修复后 `run_selftests.py -k skill_lifecycle pet_skills_manage` 34/34（新增 `stage_skills` 用例后生命周期/安全 34/34），`smoke_test.py --affected skill_lifecycle_service pet_skills_manage` 10/10，`smoke_test.py` 默认含隐藏桌面探针 9/9，静态名称/卫生门禁 13/13。均 exit 0。
**三基线**：冒烟实测 9/9；工作树 `smoke_test.py --architecture` 实测 483 条，失败 1、错误 1，分别是工作树缺少 Git 未跟踪的 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md` 与 `维护记录/基准历史.json`（主工作区存在，功能工作树不存在；本轮未改这些文件），不能称为架构全绿；全量回归待主仓合并出口/安全全量完成后按实际凭据记载。历史欠账未在本轮修复、未因补丁新增。

## 根因与改动

1. `skill_lifecycle_service.uninstall_skill_entry` 原有启用/禁用分支均未查当前项目制作锁及配置引用；页面 `remove_skill` 的确认动作也没有占用检查。
2. 同模块新增 `skill_delete_block_reason(project, name)`：使用 `stage_model_value.production_locks` 和 `stage_layout.skill_config_path` 的现成口径，只读精确匹配 `skills`、`stage_skills` 引用；服务删除入口接 `project` 并在启用/禁用删除前阻断。
3. `pet_skills_manage` 选中时设置删除按钮禁用状态与 Tooltip；动作前检查，确认后由服务再次检查；拒绝时同步刷新按钮和悬停说明。无项目／无锁／未引用者保持原删除行为。
4. `tests/test_skill_lifecycle.py`、`tests/test_pet_skills_manage.py` 增覆盖：无锁、不同名、两种引用形态、启用/禁用、服务直接调用、弹窗期间占用变化、按钮状态与提示。
5. 任务书 `tasks_round/SKILL删除占用守卫补齐任务书.md` 记录用户确认的边界；本轮不复用旧并行 T7 分支的大幅 UI 重写。

## 边界与待完成

- 守卫基于**当前项目**非空制作锁＋精确技能引用；未证明进程实际正在运行，不声明跨项目在途任务或后台导入检测。
- 功能分支提交、主干 `dev.py merge` 及安全全量：待实际完成后记录，不预写通过。
- 页面或注册表改动后需重启应用以加载新代码；本轮不碰用户项目数据或其他会话的主工作区中间态。
