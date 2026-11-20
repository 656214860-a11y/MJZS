# R3936 结果：残留包列表不再列出阶段模板目录
<!-- round-evidence: {"commit_base": "f675ebf6", "credential_hits": 0, "evidence_sha256": "b1f2936b22a615b0", "exit": 0, "failed": 0, "passed": 53, "round": 3936, "tests": "run_selftests.py -k skill_residue_protection skill_residue_service pet_skills_manage skill_templates skill_project_layer"} -->

## 1. 三问

- 轮次类型：修复轮。
- 测试跑了吗、三个基线过了吗：定向 5 个测试文件 53 条通过（`run_selftests.py skill_residue_protection skill_residue_service pet_skills_manage skill_templates skill_project_layer`）。未跑冒烟、架构门禁和全量，出口检查在合入时跑。最新绿全量仍是 R3849。
- 欠账少了吗：少了一条，多了一条。R3932 记下的「SKILL 管理把 `templates` 列为残留包」已修。新记下的见 §5 第 1 条。

## 2. 现象与原因

2026-11-20 21:08，主工作区的 `skills/templates`（14 个阶段模板）经「SKILL 管理」的非阶段残留包列表被移入回收站。

`scan_residue` 把 `skills/` 下所有非阶段目录都列为残留包。`templates` 由 `orchestrator/skill_templates.template_root` 和 `contract/script_brief.RHYTHM_TEMPLATE_PATH` 按路径读取，缺失时 `load_template` 抛错，阶段取不到流程模板。《残留SKILL治理任务书》§2.2 盘点时把 `templates` 和四个预设包一起算作残留目录，没有区分。

## 3. 改动

| 文件 | 改动 |
|---|---|
| `orchestrator/skill_project_layer.py` | 新增名单 `PRODUCT_RESOURCE_DIRECTORIES = {'templates'}` 和排除判定 `_kept_out_of_residue`（阶段目录，或名单里的目录；目录名不区分大小写）。两个管理通道包装函数改为注入这个判定。名单里的目录不列出，回收请求因此按「残留包不存在」拒绝 |
| `tests/test_skill_residue_protection.py`（新增） | 7 条用例：不列出；不可回收；混入批次时整批拒绝；目录名大小写绕不过；其他包仍可回收；名单覆盖两处读取路径；对真实程序目录扫描不列出模板目录 |

`domain/skill_residue_service.py` 没有改：它只把注入判定的真值当作「跳过」。

## 4. 先红后绿

- 改前：对真实程序目录调用管理通道的扫描，列表是 `imagegen, short-drama-storyboard, storyboard-image-prompts, templates, video-storyboard-gen`；新用例因为名单不存在而导入失败。
- 改后：同一扫描的列表是 `imagegen, short-drama-storyboard, storyboard-image-prompts, video-storyboard-gen`；新用例 7 条通过，原有 `tests.test_skill_residue_service` 10 条没有改动、仍通过。

## 5. 没有做的，和新记下的

1. 第一版改法是给 L2 的 `scan_residue`、`dispose_residue` 加一个显式参数，提交时被重叠门禁拒绝：`domain/skill_residue_service.py` 和 `tests/test_skill_residue_service.py` 与 `codex/directory-governance-execution`、`codex/retire-builtin-prerequisite`、`codex/wip-r3764` 的未合入改动重叠。核对结果：前两条分支在这两个文件上带的是 11-19 18:53 的 R3820-FAIL 检查点（内建总控退役）；主干在 11-19 22:36 以 R3818-FAIL 收进了同一项工作更晚的版本，该任务书已有完成文件。第三条分支里这两个文件与主干逐字节相同。据此判断三条分支都不会再合入这两个文件；这是判断，没有问过这三棵工作树的主人。门禁按文件名判断，只要这三棵工作树还在，这两个文件就提交不了。本轮按门禁提示错开文件，把判定放在 L3。留下的代价：L2 的参数名仍叫 `stage_from_path`，实际收到的是比「阶段判定」更宽的排除判定。等《Git并发锁机制优化任务书》G2（门禁按试合并判断）或 G5（旧工作树处置）完成后，把参数改名。
2. 四个预设包（`imagegen`、`short-drama-storyboard`、`storyboard-image-prompts`、`video-storyboard-gen`）仍可回收。它们经 `workflow_settings._bundled_skill` 读取，缺失时 `defaults()` 退回「不使用 Skill」；《残留SKILL治理任务书》规定它们按包处理。要不要保护由用户决定。
3. 没有动回收站里 21:08 那一批（`自动维护_20261120_210829_45ce0ddd`）。主工作区的 14 个文件已在 R3933 从版本库恢复。
4. 没有改界面文案。
