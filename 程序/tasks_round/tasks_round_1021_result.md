# R1021 结果：结构治理轮（子场景：执行）

- 本轮是整理轮：程序缓存与临时产物卫生，来源 `tasks_round/tasks_round_996_result.md` J3；用户本轮扩展核查过期日志、临时目录和 `.bak_`。
- 默认冒烟：实测 8/8，0 失败。架构门禁：299 项、6 项失败，98.800 秒；本轮状态 `[TASK_FAILED]`，不得标记全部完成。
- 欠账：完成来源报告缓存清理项；不宣称消除其他架构或测试欠账。

## 执行与范围

中央 `round_claim.py next` 领取 R1021；R996 是上一轮已有未提交报告，原样保留并纳入本次凭据提交，不重编号、不覆盖。队列中没有缓存卫生任务，未认领或改动其他人的任务。

使用 `workspace_maintenance.clean_pycache()`，委托 `storage_maintenance.remove_regenerable_tree()` 清理明确解析到程序内的以下五个缓存目录：

- `程序/__pycache__`
- `程序/tests/__pycache__`
- `程序/tests/architecture/__pycache__`
- `程序/agent/__pycache__`
- `程序/维护记录/基准脚本/__pycache__`

预览和实际结果一致：删除 5 个目录、238 个文件，释放 4,352,255 bytes（4.15 MiB），错误 0。缓存未作备份，可由解释器重新生成。验证设置 `PYTHONDONTWRITEBYTECODE=1`，避免立即再生缓存。

未发现范围内散落 `.pyc`、`.tmp`、`.temp`、`.bak_` 或 `程序/.selftmp`，无对应删除。扫描在进入目录前排除 `private`、`episode`、`writing`、`配置`、`data`、`.git` 和链接/目录联接。未触及用户项目、配置 JSON 或密钥。

`log_maintenance.py --dry-run` 显示 logs 与维护记录目录均为删除 0、轮转 0、错误 0。现有日志未到期，保留所有 `.log` 与历史 `.out`。本轮没有用户可见文件删除，因此不产生 `recycle_paths()` 回收批次；缓存使用已有受控删除例外。未修改任何生产 Python 或测试文件。

## 对来源报告的事实更正

`log_maintenance.py` 已定义保留 30 天、单文件上限 10 MiB、3 份轮转、目录上限 150 MiB；`desktop.py:3355` 已导入日志退出清理入口。来源报告把模块内主函数的调用扫描当作完整生产调用分析，漏掉异步子进程入口。因此“策略未定”和“未接入桌面”的结论不能作为后续删除代码或新增接入的依据。`distribution_manifest.md` 的旧文字应另轮治理。

## 验证与提交

仅为通过轮次一致性门禁，将 `project_status.md` 当前轮次同步为 1022，保留原有历史缺口声明。正式编号来自中央分配器，不能沿用来源报告预估的未来轮号。

未改变删除语义、层级或启动代码；不运行范围外功能整改。提交仅含本轮报告、来源报告和状态页的一行接续记录；提交前检查暂存路径与凭据形态。按 §2.6 使用 `R1021-FAIL:` 诊断性提交，不豁免任何门禁。

架构门禁最终失败项：

| 检查 | 实际失败证据 |
| --- | --- |
| `test_higher_layers_may_depend_only_on_same_or_lower_layers` | 存在未登记越层依赖 |
| `test_layer_exemptions_are_a_locatable_nonincreasing_baseline` | 豁免集合与实际依赖不一致 |
| `test_root_production_modules_have_no_import_cycle` | 根目录模块存在循环依赖 |
| `test_full_safe_all_is_required_every_three_rounds` | R1021 缺完整安全全量凭据；本轮没有运行完整安全全量 |
| `test_keyword_comments_match_the_reviewed_snapshot` | `desktop.py` 的 `_tick_async_result` 注释快照行号 2398 与实际 2405 不一致 |
| `test_bare_json_load_debt_is_a_nonincreasing_subset` | 未登记债务 `previs_automation.py:21`、`stage_execution_service.py:748`、`:779`、`:795` |

首轮架构检查为 299 项、7 失败、97.480 秒；同步轮次元数据后复测为 6 失败，消除了轮次连续性失败。未取得清理前的当轮架构实测，因此不能声称“不低于清理前基线”已验证；历史绿色基线也未达到。未调整基线、豁免、代码或测试来消红。上述问题需另轮授权治理。

提交状态：本文件为待提交凭据；成功提交后以最终回复和 Git 历史为准。准确哈希通过 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_1021_result.md` 获取，避免自身提交哈希的循环依赖。
