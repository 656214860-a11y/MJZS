# R3045 结果：SKILL 生命周期 T4——导入台账消费（更新检测＋本地修改识别＋删除闭环）
<!-- round-evidence: {"commit_base": "8e20c469", "credential_hits": 0, "evidence_sha256": "c339828c88b69de5", "exit": 0, "failed": 0, "passed": 169, "round": 3045, "tests": "run_selftests.py -k skill_update skill_archive skill_remote skill_panel_imported skill_import_validation"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T4；依赖 T3 已合入本栈 `codex/wip-R3036`）。
**测试**：跑了——先红后绿（`check_updates`／`forget_ledger_targets` 缺失报错＋删除闭环 2 红→实现后全绿）；`run_selftests` 定向与 `smoke_test.py --affected` 结果见下。
**基线**：冒烟 8/8＋门禁复跑结果见下；架构门禁结果见下；全量回归未跑（分支不累计欠账）。
**欠账**：无新增；覆盖率基线随改动模块刷新与否见下。

## 本轮做了什么

1. **`skill_import_service.check_updates(program, *, probe=None)`**：遍历 `data/skills/导入台账.json` 产出 `{台账键: 'unchanged'|'source-newer'|'local-modified'|'source-missing'}`。判定顺序：已安装目标缺失→`source-missing`；已安装内容 `_tree_digest` 与台账 `sha256` 不一致→`local-modified`（用户手改过，不提示覆盖，与 T9 完整性校验同一判定函数，未写两份）；其余按来源重算——`file`/`dir` 本地路径直读、`repo` 本地目录 `_repo_candidates` 重扫、`repo` 远程 `source_url`/`source_ref` 重新 `git clone --depth 1` 到暂存（用后回收，同 `import_from_repo` 克隆口径）；`archive` 与 T3 远程链接行交给 `probe(key,row)`（返回同组状态或 `None` 表示不接管，探针异常只留痕归 `source-missing`）。只读不写。
2. **候选级摘要映射**：`_entry_digests(root, registry)` 把仓库／压缩包候选树转成 `{台账键: 摘要}`——阶段按 `_candidate_stage` 判定、目录名经 `user_stage_directory_for` 换算，与 `record()` 写键同口径；判不出阶段的候选跳过（不猜）。
3. **来源探针两枚**：`skill_archive.probe_row`（本地 ZIP：`source_kind=='archive'` 且无 `source_url` 才接管，复用 `archive_entry_digests` 安全解包→候选摘要）；`skill_remote_service.probe_row`（`source_url` 可解析为 GitHub 仓库或 .zip 直链才接管，重新走 `download`＋`archive_entry_digests`，复用 `下载缓存/` 同名文件，`cache` 字典在同一次检查内按下载地址复用摘要）。`git@`／非 GitHub 仓库地址探针返回 `None`，回落默认克隆判定。
4. **删除闭环**：`forget_ledger_targets(program, targets)` 把已回收目标相对两层根的路径从台账摘除（幂等，同 `save()` 入口）；`uninstall_skill` 与面板 `delete_checked_skills` 成功后均调用——删除后台账无残留行。
5. **UI**：面板下拉新增「检查更新」（`MANAGE_CHECK_UPDATES`），`check_skill_updates` 组装远程＋本地探针跑 `check_updates`；`show_skill_updates` 结果窗（非模态，仿体检窗）列全部非最新条目（有更新／本地已修改／源不可用），详情含来源、版本、导入时间；「重新导入所选」仅对 `source-newer` 行生效，`_reimport_ledger_row` 按 `source_kind` 分发回既有管线（file/dir→`plan_import`+`perform_import`，本地/远程 archive→`import_archive`/`import_from_url`，repo→先试远程链接口径、不行退回 `import_from_repo`），旧版自动进回收站，成功后重跑检查。**不做静默自动更新**（任务书红线：必须用户确认，与旧 `master_skill_update.apply` 同规矩——后者已随 R2862 下线，本条按其语义执行）。

## 先红后绿证据

新增 `tests/test_skill_update_check.py`（18 个测试方法）：实现前 12 条 `AttributeError: no attribute 'check_updates'`＋1 条 `forget_ledger_targets`＋2 条删除闭环断言红；实现后 18/18 绿。覆盖：file/dir 源 unchanged→source-newer、local-modified 优先、源缺失与目标缺失→source-missing、旧台账行缺字段兼容、本地 repo 逐候选状态、远程 repo 行重新克隆比对与克隆失败、本地 ZIP 探针三态、无探针时 archive 行 source-missing、远程 ZIP 行重下载比对（注入 opener 不真联网）与 404、探针对本地行返回 None 回落、uninstall/forget/面板删除三级台账清理、「检查更新」菜单与分发、空台账状态文案、file 行重新导入后台账 sha256 刷新回 unchanged。

## 验证记录

- `PYTHONPATH=".;tests" python -m unittest test_skill_update_check`：18/18 绿。
- `run_selftests.py -k skill_update skill_repo skill_archive skill_remote skill_panel_imported skill_import_validation skill_user_layer test_skills`：321 条用例，初跑 `test_skills` 2 红——根因同 T3：新工作树 gitlink 子仓 `cp -r` 进了已存在的空目录形成 `AIGC创作全流程/AIGC创作全流程/` 嵌套，包入口探测落空（71≠73）；上移一层修正后 `RegistryTests` 2/2 绿。
- `smoke_test.py --affected skill_import_service skill_archive skill_remote_service skill_panel skill_panel_import`：✅ 通过 9 项／失败 0 项；内嵌定向自检 18 个测试文件 41 工作单元（含 `test_skill_update_check` 18 条、`test_skills` 全分片、`test_skill_panel_*` GUI 分片），558 秒，ALL TESTS PASSED，0 个文件有红。
- `smoke_test.py --architecture`：复跑 470 条用例仅剩 1 失败——`test_round_number_continuous`（堆叠分支固有：状态页 2989 vs 最新结果 3045→期望 3046，`project_status.md` 仅 master 可提交，合并轮抬头自愈，同 T2/T3 先例）；首轮另报的 `test_class_size_does_not_grow`（Panel 649>646）已通过合并分支与单行化瘦身 4 行至 645 修复，`test_complexity_ratchet` 4/4 复绿。
- 覆盖率基线：`维护记录/覆盖率基线.json` 按 `coverage_report.py` 同口径（AST stmt 行数）刷新 5 个改动模块 total——skill_archive 107→131、skill_import_service 423→551、skill_panel 676→679、skill_panel_import 124→263、skill_remote_service 173→201；`test_coverage_baseline`＋`test_branch_coverage_floor` 9/9 绿（本批模块非 L0/L1，分支基线不涉）。

## 改动文件

- `程序/skill_import_service.py`：`check_updates`／`ledger_items`／`forget_ledger_targets`／`_entry_digests`／`_candidate_ledger_key`／`_entry_status`／`_clone_entry_digests`／`_default_source_status`／`_resolve_ledger_target`＋`UPDATE_STATES`；`uninstall_skill` 接删除闭环。
- `程序/skill_archive.py`：`archive_entry_digests`＋`probe_row`。
- `程序/skill_remote_service.py`：`probe_row`＋`_remote_entry_digests`。
- `程序/skill_panel.py`：`MANAGE_CHECK_UPDATES` 菜单项与分发；`delete_checked_skills` 接台账清理。
- `程序/skill_panel_import.py`：`check_skill_updates`／`show_skill_updates`／`_reimport_ledger_row`／`_update_detail_text`＋顶部 ui 组件导入。
- `程序/tests/test_skill_update_check.py`：新增 18 条用例。
- `程序/architecture.md`：§59 skill_import_service 段补 T4 台账消费说明。
- `程序/tasks_round/tasks_round_3045_result.md`：本文件。

## 遗留与边界

- 面板勾选删除仍只覆盖 `.skill.md` 清单（外部包目录不在勾选删除范围，`uninstall_skill` 服务口径可收包）；台账清理对两条路径都已闭环。
- 远程 `repo` 行若 `source_ref` 是裸 commit SHA，克隆兜底可能失败→`source-missing`；GitHub https 行优先走探针 codeload 口径（sha 安全），git@／其他主机走克隆。
- `test_round_number_continuous` 在堆叠分支上仍报状态页轮次落后（本栈固有，合并轮抬头自愈，同 T2/T3）。
