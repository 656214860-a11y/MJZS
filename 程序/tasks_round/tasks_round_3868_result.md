# R3868：目录治理隔离集成检查点（REQ-RET-01 / DES-RET-01 / DES-DOC-01）
<!-- round-evidence: {"commit_base": "f583e096", "credential_hits": 0, "evidence_sha256": "56c36468e37ca70c", "exit": 0, "failed": 0, "passed": 74, "round": 3868, "tests": "run_selftests.py -k architecture.test_structure test_doc_registry_migration test_agent_doc_budget test_design_coverage test_distribution_build"} -->

- 类型：§3.3 结构治理轮，整合既有六轮治理成果与已解安全修复；本轮不是任务书完成轮。
- 测试：标准入口定向 74/74、0 skip、0 红；默认冒烟、完整架构、GUI、全量、真实覆盖率均未在本候选运行。三个基线尚未全部验收，不宣称全绿。
- 欠账：旧候选已测结果不能替代新候选。新候选保留更新主干源码，覆盖率需重新真实测量；不降低 floor。

## 集成边界与恢复点

- 实际起点 master：`f583e096a94be86e90f797699bdb5550bbf708e6`；旧候选 HEAD：`2ed443f0aee66cadfca0d6b68a450ad22280fbcd`；旧候选已解合并参考基点：`99554eb1`。
- 新树：`.agents/worktrees/governance-final`；分支：`codex/governance-final`；真实领号 R3868。
- 原历史依次为 `4d322df6 b860721f dcfe76db 0e963513 26c9a607 2ed443f0`。尝试按序摘取后，实质轮出现分发、runbook、覆盖率冲突；原轮次也归属于旧工作树。按用户授权改为一个完整集成检查点，六提交继续保存在旧分支。
- 旧树只读快照保存于执行器私有 Temp，包含文件内容、SHA256、删除列表与三方补丁；排除 project_status、分支覆盖率临时基线、用户配置和运行/私有数据。补全 Git rename 默认输出遗漏的源路径删除清单，逐项确认源路径未被新主干修改后移除。
- 未修改 master 工作区/索引，也未修改旧工作树 source/索引、合并现场；未合 master。
- 本分支 `project_status.md` 精确继承起点 master，未列入提交。

## 保留内容与主干适配

- 保留总控与 aigc_lint 退役；未恢复 00 总控目录。
- docs 与 governance 迁移、账户设计全文及逐项映射、当前引用修复、雨夜修伞 3 个 runtime 示例 keep 均保留。
- 保留 doc_registry 对符号链接/重复登记等拒绝行为；结构冻结 582 个精确旧测试不扩张，新测试须真实 case 与显式跨模块归属。
- 主干新增 `docs/review/安装更新与恢复方案_A15.md` 继续保留、添加导航和登记。登记 84 份＝旧候选 83＋主干新增 1，不能为凑旧计数删除主干新文档。
- 6 个新主干测试（file_cache_bounds、history_output_bounds、release_runtime、sbom、skill_panel_long_list、tools_lock）已按真实 import/行为登记目标；新增 `.gitmodules` tooling 角色。策略摘要同步，既有 6 条存量身份不变，未扩大旧测试冻结集合。
- 分发保留主干 SBOM、运行时依赖裁剪、发布阻断逻辑；只移除已退役 jingju 整包要求。新增主干开发验收历史文件明确排除分发。
- AGENTS：15983 字节，低于 16000；`程序/说明` 不存在；docs Markdown 相对链接审计 0 断链。
- 3 个 gitlink 指针精确保持：HoLLMwood=`3ef9f995992edcbf514bed591a54b900b7502f11`；剧本锻造=`6c3d73994f456b696de536c86602b4022824a535`；编剧技能集=`357d1348ccaa1ab75f2f51ef7c90a7f00a686c76`。未 checkout 子模块，也未修改 pin。

## 覆盖率与主干实体差异

本候选没有使用旧树新测覆盖率替代本树测量。两个基线先保留 master 历史数据，仅移除已退役 aigc_lint 行/target、重算列表和总和，增加 `integration_status=historical_master_measurement_minus_retired_aigc_lint_pending_remeasurement`。`tests_ok` 仅表示原始历史测量时刻，不能据此宣称当前候选通过。

逐个解析当前 L0/L1 登记并跳过不存在的虚拟/包键后，103 个现存实体中有 18 个与旧树字节和规范换行后的内容不同；这 18 个全部等于当前起点 master 的实体内容，未由本集成改写：

| 起点 master 中最后触及提交 | 实体（相对程序） |
| --- | --- |
| `0d891b47` | contract/platform_tools.py、infra/model_pool.py、infra/config_patch.py、infra/request_ledger.py、infra/file_cache.py、infra/storage_maintenance.py、infra/diagnostic_capture.py、infra/app_logging.py、infra/comfy_service.py、infra/http_client.py、infra/session_integrity.py、agent/core.py、agent/publication.py、infra/cloud_assets.py |
| `fbb56c29` | contract/process_wait.py、infra/config_snapshot.py、infra/api_endpoints.py |
| `f583e096` | infra/workflow_process_registry.py |

测试和扫描器也保留新主干差异，因此旧树 101 targets/1908 用例测量不可直接移用于本树。主代理需在本树重新测量并验证 floor，再完成全架构/全量与同名任务完成文件。

## 真实验证与失败闭环

命令工作目录为 `程序`，解释器来自主安装 `运行环境/Python/python.exe`，`-B` 与 `PYTHONUTF8=1`；PATH 前置主安装 ffmpeg/bin，未复制 ffmpeg 或运行数据。

1. 首次定向 45 case：2 红。根因是 rename 源删除未入快照清单，以及主干新 A15 文档未登记。补齐迁移源删除、保留并登记 A15、排除新主干开发历史文件。
2. 第二次 74 case：1 红。结构门禁正确拒绝新主干 6 个测试缺归属及 `.gitmodules` 缺角色；逐个读取测试后补真实归属，不扩大 582 冻结旧测试集合。
3. 最终命令：`python.exe -B -X utf8 run_selftests.py -k architecture.test_structure test_doc_registry_migration test_agent_doc_budget test_design_coverage test_distribution_build --serial`。
4. 最终实际结果：74 用例、24.7 秒、0 红、0 skip；其中结构协议 27、文档迁移 7、规则预算 11、设计覆盖 8、结构写边界 2、分发 19。
5. `doc_registry.py`：84 份登记通过并刷新快照；docs 全部 Markdown 相对链接 0 断链；3 gitlink staged 指针差异为空。

## 提交与后续

- 标准入口 `dev.py commit ... --tests ...` 实际 exit 5：`check_scope_overlap` 拒绝与本次源分支 `codex/directory-governance-execution` 的同名新增文件（例如 document-migration.json、governance/check_structure.py）；另有旧账户设计来源分支同源文件。主代理明确确认这是本次授权集成的同源重叠，继续使用标准 `round_evidence.py 3868 -k ...` 执行真实定向与凭据扫描，再原生 git commit；pre-commit/commit-msg hooks 保留，不伪造 MERGE_HEAD、不改 hooks。
- 主代理后续：在本树真实重测覆盖率，跑完整架构和全量；通过后输出同名任务完成文件，再由主代理合 master。当前不输出任务整体 `[TASK_COMPLETE]`。
- 提交 hash 以本文件所在提交为准：`git log -1 --format=%H -- 程序/tasks_round/tasks_round_3868_result.md`。
