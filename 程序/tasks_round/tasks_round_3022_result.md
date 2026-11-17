# R3022 结果：SKILL 生命周期 T2——文件夹直选＋ZIP 导入
<!-- round-evidence: {"commit_base": "8293c5eb", "credential_hits": 0, "evidence_sha256": "1af4dbfa4d0091e1", "exit": 0, "failed": 0, "passed": 97, "round": 3022, "tests": "run_selftests.py -k skill_archive skill_repo skill_import"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T2）。
**测试**：跑了——先红后绿（`skill_archive` 缺失整文件报错→实现后全绿）；`run_selftests -k` 定向 300 条全绿；`smoke_test.py --affected skill_archive skill_import_service skill_panel_import skill_panel` 冒烟 9/9、门禁 396 条 0 红；`smoke_test.py --architecture` 首跑 5 红已全部修复并复验（见下），仅余 1 条堆叠分支固有失败。
**基线**：冒烟 9/9；架构门禁 470 条中 4 条本轮引入问题已修复复绿，`test_round_number_continuous` 为堆叠分支固有失败（T1 分支同挂，合并 master 后自愈）；全量回归未跑（分支不累计欠账）。
**欠账**：无新增；覆盖率基线已随新模块刷新（547 模块，skill_archive 在 9 组定向用例口径下 0% 覆盖，如实记录）。

## 本轮做了什么

1. **新模块 `skill_archive.py`（L4 服务，无 Tk）**：`import_archive(zip_path, program, registry, stage_hint, confirm)`——zipfile 安全解包到 `data/skills/.压缩包解压-*` 暂存（用后经回收站收走），再走与仓库导入完全相同的候选扫描→预检→确认→换入→试冻结→登记管线。护栏：条目数 `ARCHIVE_MAX_ENTRIES=2000`（与 `PACKAGE_MAX_FILES` 同量级另设常量）、解压后总体积复用 `PACKAGE_MAX_BYTES`、拒绝绝对路径／盘符／UNC／`..` 穿越／控制字符与冒号条目、加密条目拒绝、只写普通文件不落链接语义、逐条目落盘前再核 `resolve()` 不出解压根。`master_skill_update._safe_members` 已随 R2862 总控下线，全仓无共享安全解包实现，按任务书「复制改名」精神在本模块自含。
2. **安装管线去重**：`import_from_repo` 的「候选→计划→确认→换入」核心抽为 `_candidate_plans`＋`_install_candidate_plans`（来源信息收进 `_InstallSource` NamedTuple，参数数守住棘轮），仓库与压缩包两条入口共用；报错文案按 `origin`（仓库／压缩包）区分。
3. **台账 `source_kind` 字段**：`record()` 新增 `source_kind`（file／dir／archive／repo；包类本地导入自动得 dir，仓库／压缩包由调用方显式标注），T4 更新检测据此分辨本地目录源；旧台账行缺字段容忍。
4. **文件夹直选**：面板下拉新增「新增·文件夹」（`FileDialog.directory` 已有未用入口），根目录按 `Registry._package_source` 口径找 `SKILL.md`（`README_ZH.md`/`README.md`/`README.MD` 兜底），找不到报「不是 SKILL 包」；整包走 `plan_import`/`perform_import` 同一链。「新增」更名「新增·文件」与「新增·ZIP」对齐。
5. **包入口口径对齐注册表**：`_kind()` 由只认 `SKILL.md` 扩为 `_PACKAGE_ENTRY_NAMES`（SKILL.md＋README 变体），`plan_import` 包目标文件名改用 `source.name`——README 入口的集合包（如编剧技能集）现在能整包导入且试冻结通过；直接挑 README 文件的行为相应变为整包导入（与注册表对该目录的判定一致，属有意契约变化）。
6. **ZIP 结构判定**：复用 `_repo_candidates`——含 `SKILL.md` 的子目录视为包、根级 `*.skill.md` 视为清单、都没有硬拦「压缩包中没有找到 SKILL.md 或 *.skill.md」；解压容器目录名取压缩包文件名主干（非法字符清洗），根级 `SKILL.md` 包以此命名。

## 先红后绿证据

新增 `tests/test_skill_archive_import.py`（18 条用例＋随 `PanelTests` 继承的面板回归）：实现前 `import skill_archive` ModuleNotFoundError 全文件红；实现后 `run_selftests` 定向 9 文件 300 条、`--affected` 门禁 396 条全绿。覆盖：`../evil.md` 穿越、`/abs`、`C:` 盘符三例拒绝且无逃逸落盘、条目数／总体积超限拒绝、非 zip 与无 SKILL 标记拒绝、包 zip 装入＋试冻结＋台账 `source_kind=archive`、根级清单 zip、暂存回收、确认拒绝保留旧版、README 入口文件夹整包、面板目录/文件选择器接线与下拉分发。

## 验证记录

- `smoke_test.py --affected skill_archive skill_import_service skill_panel_import skill_panel`：9/9 通过，门禁 396 条 0 红。
- `smoke_test.py --architecture`：首跑 5 红——①`skill_archive.py` 直接 `open('wb')` 解压写入：登记进 `_TEMPORARY_BOUNDARIES`（解压暂存非正式成果，包内为任意字节不走 agent.core 文本口径）；②`_install_candidate_plans` 9 参超棘轮：来源信息收进 `_InstallSource` 后 6 参；③④覆盖率基线模块集合 546→547：重跑 `scripts/coverage_report.py`（同 9 组定向用例全绿）刷新 `维护记录/覆盖率基线.json`，runbook §11 数字同步 547/476；⑤`test_round_number_continuous`：堆叠分支固有失败（状态页 2989 vs 最新结果 3006+1），T1 分支同挂已复验，合并 master 后由合并轮抬头自愈，非本轮代码问题。
- 复验：`test_atomic_write_boundary`＋`test_complexity_ratchet`＋`test_coverage_baseline` 15 条全绿；`test_skill_repo_import`＋`test_skill_archive_import` 82 条全绿（重构后回归）。

## 改动文件

`skill_archive.py`（新增）、`skill_import_service.py`（管线去重＋`_kind`/`target`/`record` 扩展）、`skill_panel_import.py`（文件夹/ZIP 入口＋`_import_plan` 模块级共用）、`skill_panel.py`（下拉项与分发）、`tests/test_skill_archive_import.py`（新增）、`tests/architecture/_layers.py`（登记 L4）、`tests/architecture/test_atomic_write_boundary.py`（登记暂存边界）、`architecture.md`、`runbook.md`、`维护记录/覆盖率基线.json`。

## 未做/移交

- 远程 URL 导入（T3）：`skill_archive` 的解包段已可被 T3 下载落盘后直接复用。
- 台账 `source_url`/`source_ref`/`version` 字段（T3）；`source_kind` 已先行落地供 T4 消费。
- 「新增·文件」对话框的来源类型确认文案属 T9 安全加固范围，本轮未加。
