# R1023 结构治理轮（执行）：使用说明与当前权威对齐

- 本轮是整理轮，来源：`tasks_round/tasks_round_996_result.md` J1；不执行 J2–J4。
- 测试：静态检查与默认冒烟 8/8、文档一致性 10/10 通过；架构改前后均 299 项、相同 6 失败，无新增失败。完整安全全量未运行，不宣称三个基线全绿。
- 欠账未减少：本轮不修代码，状态页仅同步轮次头。

## 范围与编号

中央分配器实际领取 R1023。用户确认不复用 R997，并允许使用说明之外新增对应结果报告、同步必要状态轮次头。未补写历史缺口。唯一业务文档改动是根目录 `使用说明.md`；另外两项是本报告与 `project_status.md` 轮次头。

当前中央队列中没有 J1 对应任务 ID，不认领或收口无关队列任务。

## 改动与权威依据

1. 增加 01–12 阶段编号、名称、目录表；顺序与名称逐项核对 `pet_bus.STAGES`／`STAGE_NAMES`，目录逐项核对 `stage_layout.STAGES`。
2. 明确“13 参考网站”是非制作阶段的工具页，与 `desktop.PAGES` 一致。
3. 保留随附 `运行环境/Python/python.exe` 的运行前提，不要求外部 Python 3.12+。
4. 移除旧目录树示例，旧 `storyboard/` 等目录统一标注只读兼容，新写入走 `stage_path_service`。
5. 删除七天措辞，不承诺旧版本数量或期限；维护边界引用 `distribution_manifest.md`，说明其引用代码决定日志策略，分发排除不授权原地删除。

## 验证

使用随附解释器与 `-B`／`PYTHONDONTWRITEBYTECODE=1`：

- 内存中 AST/正则静态检查：12/12 阶段编号、名称、目录一致；工具页区分、随附解释器、旧目录只读兼容、无保留期承诺均通过。
- `python -B -m unittest tests.architecture.test_agents_md`：10/10 通过。
- `python -B smoke_test.py`：8/8 通过。
- `python -B smoke_test.py --architecture`：改前 299 项、6 失败，96.570 秒；改后 299 项、同 6 失败，96.545 秒。两次退出码均为 1；凭据欠账提示从 R1022 接续为 R1023，不是新增失败类别。

改前既有失败集合：

1. `test_higher_layers_may_depend_only_on_same_or_lower_layers`
2. `test_layer_exemptions_are_a_locatable_nonincreasing_baseline`
3. `test_root_production_modules_have_no_import_cycle`
4. `test_full_safe_all_is_required_every_three_rounds`
5. `test_keyword_comments_match_the_reviewed_snapshot`
6. `test_bare_json_load_debt_is_a_nonincreasing_subset`

完整安全全量凭据欠账仍在；本轮不把文档验收等同整体绿色，也不改测试、断言或门禁基线以消除失败。

## 自审与收尾

未修改任何 `.py`、配置或用户项目数据；未读取密钥，未删除文件，未执行项目迁移。只暂存上述三个 Markdown 文件；无生产模块变更。用户指定范围优先，本轮不另改架构说明或状态正文。

自审结论：文档专项验收通过，架构不低于改前基线；整体仍为 `[TASK_FAILED]`，不将既有失败或完整安全全量欠账抹去。两次架构运行确认失败集合相同，本轮不扩大为代码修复或全量基线治理轮。按 AGENTS.md §2.6 使用 `R1023-FAIL: 使用说明与当前权威对齐` 诊断性提交，不 push。提交前最小路径清单、仅状态头改动、凭据形态检查均通过，`git diff --check` 无空白错误。

提交 hash 由提交后 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_1023_result.md` 查询，并在最终回复交付，避免将自身 hash 写入自身提交。报告中的计划不冒充已提交事实。
