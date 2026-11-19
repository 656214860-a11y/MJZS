# R3721 结果报告
<!-- round-evidence: {"commit_base": "133b8918", "credential_hits": 0, "evidence_sha256": "34aa91fe09fc277e", "exit": 0, "failed": 0, "passed": 25, "round": 3721, "tests": "run_selftests.py -k job_store asset_resume"} -->

## 三问

- 类型：§3.8 可靠性／数据迁移轮（任务书轮 I19 作业库实现与试点，I18 选型落地）。
- 测试：见下「验证」节；默认冒烟 9/9；定向 `run_selftests -k job_store asset_resume` 全绿（asset_resume 既有 14 条断言未动）；`--all --safe` 已启动回填。
- 欠账：少了——L1-H5 通用作业库落地，I19-1/I19-2 达成。

## 变更

- 新增 L1 `infra/job_store.py`（约 250 行）：每项目 `data/job_store/<项目根 sha256[16]>.sqlite`（WAL，不写用户项目目录）；`enqueue(key,kind)` 幂等键去重返回既有作业；六态机 queued→running→succeeded/failed/retrying、retrying→running/stopped、failed→retrying、stopped→retrying，非法迁 `ConfigError`；`note_attempt` 退避 `step*attempts`、到 limit 标 stopped；`checkpoint` JSON+digest；`mirror` 台账双写 upsert；`reconcile` 一致性报告（missing_in_store/missing_in_ledger/field_diffs）；启动恢复 running→retrying（崩溃安全语义）。
- 试点：`domain/asset_resume.note_round` 双写 `infra.job_store`（waiting→retrying、stopped→stopped、补齐资产→succeeded），新增 `consistency_report(project)`；旧台账仍是读取权威，双写失败只记日志不阻断（`OSError/sqlite3.Error` 限定捕获）。
- 同轮修复：初版 `list()` 在持锁内调 `get()` 造成非重入锁死锁——改为单次查询直接返回（新测试 `test_mirror_upsert_and_list_and_by_key` 覆盖该路径）。
- 登记：`_layers.py` L1 收 `job_store`（无同层边）；architecture.md/PROJECT_MAP/runbook 同步；分支覆盖率基线 102 模块/2986 点（job_store 13 点 84.6%）、下限登记 84.6；行覆盖率基线 672 模块（job_store 142 行 93.7%）。

## 验收对照

- I19-1：`test_crash_recovery_last_committed_state` 模拟进程被杀（连接弃置不重开）→ 重开库后 running 已降级 retrying、checkpoint 完好，即「恢复到最后一个已提交状态」。
- I19-2：`test_dual_write_keeps_ledger_reads_and_consistent_store` 双写期间 `load()/delay()` 读口径与改前一致、`consistency_report` 零差异；`test_dual_write_survives_store_failure` 作业库不可写时本轮照常成功。

## 验证

- `run_selftests -k job_store asset_resume`：全绿（job_store 11 条＋asset_resume 14 条）。
- `smoke_test.py`：9/9。
- `run_selftests --all --safe`：结果回填。
- `--affected asset_resume`：见提交证据。
- 架构门禁：同轮登记仅 L1 模块表＋0 条同层边；`test_branch_coverage_floor`/`test_coverage_baseline` 模块集合已同步 102/672。

## 备注

- I18（R3700）选型结论落地：自研 sqlite3 通用作业库，零新增依赖、零新增调度线程（执行复用 `executors` 池）、单模块达标 ≤2 上限。
- 双写试点期间作业库不产生读取流量，仅 `consistency_report` 供对账；后续阶段迁移读取路径属任务书后续轮次。
