# R4280 结果：REL-06（项目配置版本登记、config.json 读坏回退、关键文件原子写审计）
<!-- round-evidence: {"commit_base": "c93b7ce4", "credential_hits": 0, "evidence_sha256": "48da07131dd739fb", "exit": 0, "failed": 0, "passed": 166, "round": 4280, "tests": "run_selftests.py -k project_recovery atomic_write_boundary artifact_schema project_settings engine_probe test_projects stage_doc_sections agent_doc_budget requirement_traceability design_coverage"} -->

> 本轮落码（产品代码 4 个文件、测试 2 个文件、04 号规格）最后一次写入 2026-11-24 05:30。本车道此前没有领过号，R4280 按规则 27 在车道内新领。卡面本身仍待用户确认，以下只陈述磁盘上已有的改动。

## 开头三问

- （一）本轮属于哪种类型：功能轮（§3.1），带一条新架构守卫。卡面目标是数据安全三项：项目配置版本登记、配置读坏自动回退、关键文件写盘必须走统一入口。
- （二）测试跑了吗、三个基线：跑了（由接管会话执行）。默认冒烟 `smoke_test.py` 通过 9 项、失败 0 项；定向 `run_selftests.py -k project_recovery config_corrupt_fallback atomic_write_boundary artifact_schema project_settings engine_probe test_projects` 9 个文件 140 条 0 红；架构门禁 `smoke_test.py --architecture` 701 条，首跑 1 失败（原因见下「未提交的文件」），把那份重复测试文件移出 `tests/` 后复跑 `test_structure`／`skip_hygiene` 与卡面第二组验收共 66 条全绿。全量回归：未跑；凭据以 `full-safe-receipts.json` 为准，本轮未新增。原执行者的「先红后绿」改前失败输出：未留存，本会话未复现改前红灯。
- （三）欠账少了吗：部分少了。读坏回退与版本登记已落码并有测试；卡面要求的「skill_config 读写接线」与「绕过统一入口的写盘点清单」没有做完，见「欠账」。

## 改动范围（原执行者落码，接管会话未改产品逻辑）

- `程序/contract/artifact_schema.py`：`REGISTRY` 登记 `project_config`、`skill_config` 两个类型，均为第 1 版、无必备字段。
- `程序/infra/project_settings.py`：新增 5 个助手——`config_backup_path`（同目录 `<原名>.bak`）、`refresh_json_backup`（读通后刷新快照，内容相同不重复写）、`read_json_or_backup`（主文件读坏回退快照）、`config_open_error`（两份都不可用时的可操作报错）与 `note_json_backup_recovered`（回退成功的日志与诊断台账提示）。
- `程序/orchestrator/engine.py`：`read_project_config` 读坏时回退 `config.json.bak` 并记提示；无可用快照时报可操作错误，坏文件原样保留；读取后按登记版本分类，高于登记版本拒读；读通后刷新快照。`remember_episode` 写回时经 `stamp()` 补 `schema_version`。
- `程序/tests/architecture/test_atomic_write_boundary.py`：新增 `_CRITICAL_FILE_OWNERS` 清单（9 个属主模块）与用例 `test_critical_file_owners_stay_on_the_unified_write_entry`——这些模块不得登记为直接写盘边界，也不许出现绕开统一入口的直接写盘。
- `程序/tests/test_project_recovery.py`：并入 `CorruptConfigFallbackTests`（5 条）与 `ProjectConfigVersionTests`（3 条）。
- `程序/docs/specs/04_数据与本地存储.md`：第 8 节表格补「项目配置版本」「项目配置读坏」两行。

## 卡面第一步的只读核实（接管会话按 HEAD 与改动对照得出）

- 改动前 `config.json` 读盘走 `agent.core.read`、写盘走 `agent.core.save`（原子写），都不经 `artifact_schema.migrate_file`；两个配置文件都不在 `REGISTRY`，所以没有 `schema_version`，也没有版本分类。
- 改动后 `config.json` 读取侧补了版本分类与快照，写回侧补了版本号；`skill_config` 只做了登记，读写接线没有做（见欠账）。

## 未提交的文件及理由

- `程序/tests/test_config_corrupt_fallback.py`（未跟踪，7547 字节）：与已跟踪的 `tests/test_project_recovery.py` 逐项比对，8 条用例的类名、方法名、断言全部相同（`CorruptConfigFallbackTests` 5 条、`ProjectConfigVersionTests` 3 条），唯一差别是写文件的助手叫 `write` 还是 `dump`。判定为重复，不提交。因为留在 `tests/` 下会被结构门禁扫成未登记文件（STR006），已把它移到车道根 `.agent-tmp/rel-06-old-drafts/`（带 `.gitignore`，与调度整理旧草稿的做法一致），没有删除；整份改动的救援补丁在仓库根 `.git/rescue/rel-06.patch`。
- 说明：卡面把该文件列在允许修改文件里，验收命令也带 `-k config_corrupt_fallback`；合入后这个关键词在 master 上匹配不到任何文件，验收靠其余关键词仍然成立。是否恢复成独立文件由卡面确认时一并定。

## 验证记录（接管会话，日志在仓库根 `.agent-tmp/takeover-rel-06-*.log`）

| 命令 | 结果 |
| --- | --- |
| `python -B run_selftests.py -k project_recovery config_corrupt_fallback atomic_write_boundary artifact_schema project_settings engine_probe test_projects` | 9 个文件 140 条，0 个文件有红，ALL TESTS PASSED（含重复文件的 8 条） |
| `python -B smoke_test.py` | 通过 9 项，失败 0 项 |
| `python -B smoke_test.py --architecture`（重复文件仍在 `tests/` 时） | 701 条，失败 1：`test_structure` 报新增目录债 `STR006 程序/tests/test_config_corrupt_fallback.py ownership`；其余 700 条通过 |
| `python -B run_selftests.py -k test_structure skip_hygiene stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（移走重复文件后） | 7 个文件 66 条，0 个文件有红，ALL TESTS PASSED |

架构门禁当轮总数：701；失败集合：移走重复文件前 {test_structure 真实仓库无新增违规}，移走后为空（相关 66 条复跑全绿，其余 635 条首跑已通过且移走一份不提交的文件不触及其被测对象）；合入时出口 CI 会再跑一遍全部架构门禁。

## 欠账

- `skill_config.json` 的读写没有接 `artifact_schema`（分类、拒读未来版本、写回补版本号都还没做），代码注释写的是留给属主 `stage_config` 的轮次补。
- 卡面要求的「绕过统一入口的写盘点清单」原执行者没有留下；本会话只核实了新架构用例列出的 9 个属主模块当前没有直接写盘，没有做全仓写盘点盘点，也没有向需求设计转留言。
- 每次成功读取 `config.json` 都会在项目目录里多写一份 `config.json.bak`；项目复制、清理、打包清单是否需要认识这个新文件，本会话没有逐项核对。
- 全量回归本轮未跑（合并后按 §5 口径处理）。

## 提交与合入

- 是否已提交：由 `dev.py commit` 提交到 `codex/rel-06`，提交号见提交记录；合入 master 走 `dev.py merge` 合并轮。
