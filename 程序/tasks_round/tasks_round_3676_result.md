# R3676 — A12 第四批阶段配置批量回收恢复
<!-- round-evidence: {"commit_base": "04fce634", "credential_hits": 0, "evidence_sha256": "e41d8de993c8a732", "exit": 0, "failed": 0, "passed": 44, "round": 3676, "tests": "run_selftests.py -k test_publication_recovery test_publication_transaction test_publication_fsync_budget test_recycle_write_ahead test_recycle_restore test_stage_file_index_publication"} -->

## 三问

- §3.8 可靠性轮。专用工作树 eb09，分支 `codex/architecture-a12-bulk-recovery`，基线 `04fce634`。中央领取 R3676，无对应队列条目。
- 定向故障测试、隐藏桌面面板测试和默认冒烟通过。受影响冒烟保留基线已有的 SKILL 分发数量红项。完整架构结果见验证。
- 全量欠账没有减少。开工时全量绿凭据为 R3633，至基线 R3670 有 4 个源码轮次，门禁线 8；完整安全全量未运行。

## Scope

- R3415 F 段及 R3662 剩余项指出阶段配置面板分开回收和注销。R3653 的成果版本保护和 R3662 的台账事务用于此链路；R3670 的网络链路保持原样。
- 三个生产模块为 `ui/skill_panel.py`、`infra/storage_maintenance.py`、`agent/publication.py`。既有 `ui.skill_install_recovery.ledger_transaction` 加入同一发布事务。回收清单先保存计划，再与导入台账和文件移动一起提交。桌面加载项目时经既有 `recover_stage_publications` 恢复。
- `dev.py scope` 查到 A12 前三批、L2 和 foundation 车道在发布、回收、测试或覆盖率表有重叠。合入时按符号和覆盖率行复核。只在专用工作树修改与验证，故障注入仅操作临时目录。
- 批量入口限同卷普通文件。恢复按回收副本的文件身份和内容摘要判定是否属于事务，原位被占用时保留该内容及回收副本。已移动文件的原位在崩溃时本来为空，事后若创建再删除该路径，单凭最终文件系统状态无法识别这段历史。

## 故障矩阵

| 场景 | 观测 |
| --- | --- |
| 红测，搬走第一项后子进程 `os._exit(77)` | 改前走原回收入口，重启恢复后第一项仍缺失，测试在读回原件时抛 `FileNotFoundError`。 |
| 批量第二项移动报 EACCES | 第一项退回，第二项和台账保持原样。 |
| 台账换入报 ENOSPC 或 EIO，最终清单 replace 报 EIO | 两项文件均回到原位，台账保留原始字节。 |
| 第一项移动后或台账更新后 `os._exit(77)` | 桌面项目加载所用恢复入口恢复文件和台账，可重复调用。 |
| 恢复移动再次报 EACCES | 失败上抛，发布日志留存，解除故障后重试恢复。已经恢复的另一项若被用户删除，重试时保持删除结果。 |
| 崩溃后编辑或删除尚未移动的文件，原位放入新文件或目录，编辑回收副本 | 后来变化保留，已改动的回收副本不会自动移回。 |
| 确认取消、确定前切项目或面板关闭 | 未发起回收。真实隐藏 Tk 验证确认后的正常提交也会注销导入台账。 |

## 验证与提交

- 工作树未附带解释器，使用本机 Python 3.14。隐藏桌面探测通过。故障与回收写前计划定向 21/21，专属面板定向 3/3。默认冒烟 9/9。
- 覆盖率工具定向 134/134。仅更新发生决策点变化的两行及合计，发布 35/54，回收 105/175，覆盖率下限保留。
- 受影响冒烟 9/10，选择 23 个测试文件。唯一失败为 `test_skills.RegistryTests.test_skill_distribution_matches_the_split_script_flow`，预期 73、实际 71。直接执行基线 04fce634 中的同一测试也为 71，保留原断言和目录结构。
- 完整架构 602/605，2 个失败和 1 个错误，失败集合与基线 R3670 一致。`test_round_number_continuous` 为分支状态页滞后，`test_script_stages_name_only_their_approved_00_references` 缺 `screenplay-gate-engine.md`，`test_performance_history_is_declared_as_historical_only` 缺 `维护记录/基准历史.json`。定向架构 22/22，模块体积门禁 2/2。
- 分支规则要求主线同步状态页。最新报告轮次为 3676，后续应登记 3677。按历史红项保留 `R3676-FAIL` 检查点，提交哈希以 Git 中的轮次和标准证据定位。

## 剩余 A12

- 其他 SKILL 安装、替换和删除入口的异常退出，以及其余发布链的索引、replace、fsync、真实满盘和跨卷恢复。需按链路测恢复耗时与容量。
- 上层重试与跨进程去重、供应商查单和未知计费，以及真实子进程树、其他长任务的关闭和迟到回调。
- 缓存、队列、缩略图、日志和执行历史容量，启动零递归、反复开关资源曲线和同条件 UI 响应测量。A12 总验收与任务书完成文件待后续批次。
