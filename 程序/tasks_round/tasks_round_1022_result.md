# R1022 结果：结构治理轮（子场景：执行）

- 本轮是整理轮：仅 Markdown 文档治理。来源为 `tasks_round/tasks_round_996_result.md` J1，按本轮用户授权扩展到 AGENTS、架构、状态与地图等文档；结合该报告 F/G 及 R1021 的事实更正。
- 测试：文档一致性 10/10、默认冒烟 8/8；改前架构 299 项、6 失败、94.877 秒，改后 299 项、同样 6 失败、95.287 秒。失败集合未增加，但未达到全绿，按仓库协议标记 `[TASK_FAILED]`。
- 欠账：文档重复与错误口径收口；代码架构及完整安全全量欠账未消除。

## 范围与依据

中央分配器领取 R1022；队列没有匹配的文档整理项，未修改或认领他人的任务。仅修改 `AGENTS.md`、`architecture.md`、`project_status.md`、`PROJECT_MAP.md`、`distribution_manifest.md`、根 `使用说明.md` 和本报告。不修改生产或测试 Python、配置、密钥或用户数据；不删除文件，无需调用回收服务。

## 文档整改

1. AGENTS 的测试周期收口到 §5：依据 `run_selftests.full_safe_required()` 和 `test_round_baselines` 保留 master 每三轮检查，移除每十轮及不按轮次触发的冲突表述；保留既有风险升级要求与失败门禁，不修改代码或降低测试要求。
2. 明确只读诊断测试例外，合并重复的收尾、删除及验证规则引用；根目录测试已迁走的旧表述校正为现状。任务完成不再自动扩展到其他待办。
3. 状态页将历史基线与当前失败事实分开，历史记录原样保留；旧检查点明确标为示例，轮次头同步 1023。
4. 架构文档去除互相冲突的采用方数量缓存，改指现有台账与门禁；把旧 writing/、episode/ 路径标为兼容而非新写模板，修正阶段命令测试路径。
5. PROJECT_MAP 明确它是代码契约的阅读投影，安全全量不再误写为必然串行。分发清单更正“日志策略尚未确定”，引用已实现维护服务与退出入口。
6. 根使用说明同步随附解释器、12 阶段及工具页区分，旧目录与旧限制标为历史；删除未获现行策略支持的七天删除承诺。

采用 writing-for-agents 的单一权威源与明确完成条件原则；没有新增 SKILL，也未触及任何 SKILL 文档。

## 权威源与行为边界

只校正文档，不修改阶段顺序、路径解析、事件契约或前缀实现。核对来源：`pet_bus.STAGES`／`STAGE_NAMES`／`CONTRACT`、`stage_layout.STAGES`／`LEGACY_STAGE_ALIASES`、`broadcaster.PREFIX_PATTERNS`／`Broadcaster.stage()`、`desktop.py` 退出维护入口。旧路径说明不是迁移或删除授权。

## 验证与收尾

验证命令使用随附 Python，并设置 `PYTHONDONTWRITEBYTECODE=1`：

- `-m unittest tests.architecture.test_agents_md`：10/10，通过，文档末次修订后再次通过。
- `smoke_test.py`：8/8，通过。
- `-m unittest discover -s tests -p test_stage_layout.py`：21/21，通过。
- `-m unittest discover -s tests -p test_broadcaster.py`：4/4，通过。
- AST 静态核对 `stage_layout.STAGES` 与地图编号目录：12/12，通过。
- `smoke_test.py --architecture`：改前后均 299 项、6 失败，退出码均 1；无新增失败、无测试或基线修改。全量凭据失败提示的轮号由 R1021 变为本轮 R1022，检查本身仍失败。

补充测试首次直接模块调用因 `skip_reasons` 不在导入路径导致 stage_layout 加载错误；改用 tests 目录发现方式后 21 项全部通过，未修改测试代码。完整安全全量未运行，既有凭据欠账没有因文档修改而抹去。

不变的架构失败 ID：

1. `test_higher_layers_may_depend_only_on_same_or_lower_layers`：未登记越层依赖。
2. `test_layer_exemptions_are_a_locatable_nonincreasing_baseline`：豁免与依赖集合不一致。
3. `test_root_production_modules_have_no_import_cycle`：根模块循环依赖。
4. `test_full_safe_all_is_required_every_three_rounds`：缺当前内容树的有效完整安全全量凭据。
5. `test_keyword_comments_match_the_reviewed_snapshot`：`desktop.py` 注释位置 2405 与快照 2398 不一致。
6. `test_bare_json_load_debt_is_a_nonincreasing_subset`：`previs_automation.py:21`、`stage_execution_service.py:748,779,795` 未登记。

自审：仅 Markdown 改动，生产模块变更数为 0；没有删除文件、用户数据或配置，没有弱化测试或改写历史凭据。文档定向验收通过，架构相对基线未恶化；既有架构问题未授权本轮修复，不能宣称整体全绿。

提交凭据：按 §2.6 使用 `R1022-FAIL: 收口文档规则并校正历史与当前事实` 收尾；提交前检查仅上述 7 个 Markdown 路径、凭据形态和 `git diff --check`。本报告所在提交可用 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_1022_result.md` 获取准确 hash；实际提交结果同时在最终回复交付，避免把自身 hash 写入自身提交的循环依赖。不 push。
