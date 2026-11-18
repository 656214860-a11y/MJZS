# R3297 结果：L2领域服务层优化任务书轮5（功能轮：infra/unit_of_work 事务原语实现）
<!-- round-evidence: {"commit_base": "39c7170f", "credential_hits": 0, "evidence_sha256": "aaf53cf93e9d303c", "exit": 0, "failed": 0, "passed": 15, "round": 3297, "tests": "run_selftests.py -k unit_of_work"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.1 功能轮。任务书轮 5 预设「`infra/unit_of_work.py` 实现 `begin`/`commit`/`rollback`，覆盖取消路径与进程中断路径，`rollback` 自身失败不吞原异常且留记录，行覆盖 ≥65% 进 `CORE_FLOORS`」。

**接手说明（如实记录）**：开工时工作树已有前序会话在本轮领号（R3297，`round-claims.json` 记本工作树 `dsh-864fd932-4054`／`codex/wip-r3282`，2026-11-18 07:01）下留下的**未提交实现与测试**（`infra/unit_of_work.py` 431 行全量实现、`tests/test_unit_of_work.py` 15 用例），但未跑测试、未刷基线、未写结果文件即中断。本轮在其基础上完成验证闭环并修复实测暴露的缺陷：

- `begin` 误调不存在的 `_recover_pending()`（实为 `recover_pending`）→ 14/15 用例 `NameError`，已改为正确调用；
- 用例 2 的 sabotage 自毁断言（`rmtree` 删掉 `b.json` 后仍断言其内容＝`new-b`，永假）→ 改为 `chmod 0o444` 只读制备恢复失败，断言原意（失败不破坏现场、可重试）保留；
- `_restore_entry` 恢复时 `resolve()` 会跟随事务窗口内被换入的符号链接、把写回引到链接目标越出登记范围 → 改为直接用 begin 时登记的已解析路径；「原本不存在」删除后补 `os.path.lexists` 复核（`remove_temporary_file` 对 OSError 静默返回 False，不复核则删失败被当成功、journal 还被清掉）；
- 架构门禁实测 4 处违规（前序实现从未跑过 `--architecture`）：`_locking()` 的 `except ImportError` 未登记 → 改 `agent.publication.access` 同口径 `os.name != 'nt'` 前置拒绝＋裸导入；`_read_manifest` 裸 `json.loads` → 改 `file_cache.read_json` 唯一 JSON 读入口；`commit` 直接 `.unlink(manifest)` → 改 manifest 原子改写 `state='committed'`（见「设计决策」）；分支覆盖率基线决策点 0≠49 → 按工具真实重测刷新。

先红后绿：测试文件先于本轮验证落盘，`git show HEAD:程序/infra/unit_of_work.py` 为 35 行 `NotImplementedError` 空壳，换壳实测 **15/15 全 error**（见「先红证据」）；实现落地后同文件 15/15 绿。不接入任何 domain 模块（轮 6 的事），不改 L0 契约。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 先红（空壳实测） | **15/15 error**：`unit_of_work.py:25 raise NotImplementedError`，0.063s（输出存 `/tmp/r5_red.log`，摘录见下） |
| 转绿（实现后） | **绿**：`python -B tests/test_unit_of_work.py` → Ran 15 tests，OK（0.7–0.9s） |
| 定向自检 | **绿**：`run_selftests.py -k unit_of_work` → 15 条用例 0 红文件，ALL TESTS PASSED |
| `smoke_test.py --affected unit_of_work` | **绿**：10 项通过（9 检查项＋定向门禁 1 文件 15 用例） |
| 默认冒烟 `smoke_test.py` | **9/9 通过**，exit 0 |
| 架构门禁 `smoke_test.py --architecture` | **502 条，FAILED（failures=2）**：`test_entry_files_stay_within_budget`（AGENTS.md 16028>16000，HEAD 即超支）、`test_round_number_continuous`（`project_status.md` 状态页 3259 冻结、仅 master 可提交）——与 R3275/R3282/R3284/R3291 记录的分支固有红集合**逐名一致**；本轮曾引入的 4 处红（分支决策点、ImportError 边界、物理删除、裸 json.loads）已全部修复并复跑确认 |
| 全量回归 `--all --safe` | **未运行**——功能分支开发轮，全量按 §5 由合入 master 前触发；如实标注 |

**3. 欠账少了吗？**
减少。任务书点名的「7 处各写一遍暂存→替换→失败恢复、4 处回滚不完整、取消与进程中断不回滚」现已有 L1 侧唯一事务原语落地：磁盘 journal 抗崩、msvcrt 字节锁跨进程协调、`begin`/`recover_pending` 自动恢复、取消路径与 `finally` 同效、恢复失败抛 `RollbackFailedError` 留 journal 可重试。剩余欠账如实记录：7 处 domain 接入点属轮 6；`infra/business_log.py` 属轮 7；`infra/idempotency.py`、`domain/domain_events.py` 的行覆盖 CORE_FLOORS 仍为 0.0（各自轮次实现后刷新）；分支固有 2 条架构红待 master 合并轮处理。

---

## 设计决策

| 决策点 | 结论与理由 |
| --- | --- |
| **快照载体** | **磁盘 journal**：`outputs/unit-of-work-transactions/<uuid>/`（程序私有运行数据、非项目产物），manifest.json 逐条记 `path`/`existed`/`backup`。否决内存快照——进程崩溃即失，直接违反任务书「进程中断路径」硬要求；内存＋暂存双写徒增一致性面，单写盘 journal 已够（备份经 `agent.core.save_file` 原子落盘）。7 处接入点都是小 JSON/文本，但原语不限定体积，`save_file` 按块复制不进内存。 |
| **进程中断协调** | 每事务一个 `<uuid>.lock` 字节锁（`msvcrt.locking` LK_NBLCK 1 字节），令牌存活期间持有、进程死亡随句柄释放；`begin` 与公开 `recover_pending()` 扫描 journal 根，「锁可拿到＝属主已死」才恢复，活跃事务与锁被持有的一律跳过；本进程活跃集 `_ACTIVE`＋`weakref.finalize` 兜底（令牌被 GC 未收尾→放锁、journal 留盘待下次恢复，不成永久悬挂）。 |
| **删除语义** | 「原本不存在」路径经 `agent.core.restore_bytes(path, None)` 删除——仓库既有回滚权威原语，`video_prompt_publication.py:101`、`domain/projects.py:245` 同口径。否决 `storage_maintenance.recycle_paths`：它需项目根且 `plan_recycle` 对越界路径静默跳过，而本原语要服务任意登记路径（含项目外全局配置），静默跳过＝假恢复。删除后以 `os.path.lexists` 复核：`remove_temporary_file` 对 OSError 静默返回 False，不复核会把「没删掉」记成「已恢复」且 journal 被清理、永不重试。 |
| **commit 提交点** | manifest **原子改写 `state='committed'`** 而非删除：`_recover_journal`/`rollback` 只认 `state='pending'`，committed/rolled_back/缺失/损坏一律只清目录不动目标，安全语义与「删 manifest」等价；且 `save_text` 写失败会抛出、令牌保持 active 可回滚（unlink 版静默失败反而埋雷：pending manifest 残留会被自动恢复回滚掉已提交内容）；顺带满足 `test_recycle_service` 物理删除门禁（删除统一走 `file_cache.remove_temporary_*`）。 |
| **异常策略** | `rollback` 逆序尽力恢复**全部**登记路径，收集 `(路径, 异常)` 失败列表后抛 `RollbackFailedError`——调用方 `except` 块内抛出时原异常经 `__context__` 链可见（用例实测断言）；journal 保留 `pending`、令牌保持 active 可修复后重试，或交下次 `begin` 自动恢复。对 `committed`/`rolled_back` 令牌幂等空操作（取消异常二次触发不会顶掉已提交内容）；重复 `commit` 幂等；`commit` 打在 `rolled_back` 上抛 `ValueError`；非 `begin` 产物抛 `TypeError`。 |
| **取消路径** | `rollback` 不检查异常类型：`except BaseException`（自定义 `Cancelled`）与 `finally:` 内调用同效，用例双覆盖。 |
| **登记边界** | 只登记普通文件：`os.lstat` 拒绝符号链接/联接点等重解析点与目录（`begin` 即 `ValueError`，失败 begin 自收 journal 与锁、不留误伤面）；路径 `resolve()` 后按 `normcase` 去重登记，恢复时**不再 resolve**（防事务窗口内换链接把写回引到链接目标）。 |
| **并发** | 令牌不透明（`_Token` slots＋`RLock` 串行化同令牌操作）；不同令牌互不影响；跨进程由锁文件活性＋扫描协调；非 Windows 在 `begin`/`recover_pending` 入口 `RuntimeError` 拒绝（与 `agent.publication.access` 同口径 `os.name` 前置，不设 ImportError 容错）。 |

## 先红证据（空壳实测，非机制推断）

```
$ git show HEAD:程序/infra/unit_of_work.py | tail -12   # 35 行空壳
def begin(paths):    raise NotImplementedError
def commit(token):   raise NotImplementedError
def rollback(token): raise NotImplementedError

$ cp 空壳 → infra/unit_of_work.py && python -B tests/test_unit_of_work.py
EEEEEEEEEEEEEEE
ERROR: test_absent_path_is_deleted_on_rollback ... unit_of_work.py:25, in begin
    raise NotImplementedError
NotImplementedError
（15 条用例全部同因）
Ran 15 tests in 0.063s
FAILED (errors=15)
```

实现落地后同文件 `Ran 15 tests in 0.681s — OK`。

## 验收对照（任务书轮 5）

- [x] **用例：两次写，第二次故意抛错，断言第一处也已恢复** → `test_rollback_restores_every_registered_path`：登记 a/b 两路径→写两处新内容→抛错→`rollback`→断言 a、b 均回 `begin` 时内容。
- [x] **用例：`rollback()` 内部再抛错时，原始异常仍可见** → `test_rollback_failure_keeps_original_exception_visible`：b.json 置只读（WinError 5 制造恢复失败）→`except RuntimeError` 内 `assertRaises(RollbackFailedError)`→断言 `__context__` 即原异常；a 已还原、b 保持事务内容；`chmod` 还原后同令牌重试成功。
- [x] **用例：`Cancelled` 路径触发回滚** → `test_cancelled_path_rolls_back`（`BaseException` 子类）＋ `test_finally_path_rolls_back`（`finally:` 内回滚），双路径覆盖「不只在 `except Exception` 内」。
- [x] **`infra/unit_of_work.py` 行覆盖 ≥65%（进 `CORE_FLOORS`）** → `scripts/coverage_report.py` 定向实测 **78.4%（218/278 行）**，`CORE_FLOORS` 登记 65.0；分支口径另测 32.7%（16/49 决策点），`分支覆盖率下限.json` 0.0→32.0 同步上调。

任务书其余硬要求对照：进程中断路径 → `test_process_death_recovered_by_next_begin`＋`test_recover_pending_restores_without_new_begin`（令牌 GC 放锁→journal 留盘→下次 begin/显式 recover_pending 按原语义恢复）；「原本不存在」删除 → `test_absent_path_is_deleted_on_rollback`；回滚失败留记录 → `_restore_entries` 逐条 `_logger.error`（只记序号与异常类型、不落盘符）＋`RollbackFailedError.failures`；空登记/重复登记/外来令牌/目录拒绝/begin 失败清理 → 边界用例各一。

## 改动清单（7 个文件）

| 文件 | 改动 |
| --- | --- |
| `infra/unit_of_work.py` | 35 行空壳 → 454 行实现（前序会话底稿＋本轮修复）：journal/manifest/字节锁/状态机/自动恢复；本轮修 `_recover_pending` 误名、`_locking` ImportError、`_read_manifest` 裸 json.loads、`commit` 物理删除、`_restore_entry` resolve 与删除复核，docstring 同步语义 |
| `tests/test_unit_of_work.py` | 新增 237 行 15 条用例（前序会话底稿＋本轮修 sabotage 不可达断言） |
| `tests/architecture/test_coverage_baseline.py` | `CORE_FLOORS["infra/unit_of_work.py"]` 0.0→65.0（注释记实测 78.4%） |
| `维护记录/覆盖率基线.json` | 重跑 `coverage_report.py` 刷新：targets 9→10（+`tests.test_unit_of_work`），`unit_of_work.py` 0/13→218/278=78.4%，`domain_events.py` 0→54.5%（R3291 接入点被既有定向用例覆盖），modules_covered 74→76、未覆盖 583→581；同步刷新 R3282/R3291 改码后的陈旧 total（recon_service 425→462 等，为实测真值） |
| `维护记录/分支覆盖率基线.json` | 重跑 `branch_coverage_report.py` 刷新：targets 80→81，`unit_of_work.py` points 0→49、covered 16=32.7%，全局 1264/2367→1280/2416 |
| `维护记录/分支覆盖率下限.json` | `unit_of_work.py` 下限 0.0→32.0（runbook §11「刷新基线须同步上调下限表」；约定＝实测向下取整） |
| `runbook.md` | §11 覆盖率口径数字同步基线（76/657、581、10 组定向用例；原「579/9 组」已陈旧一并校正） |
| `tasks_round/tasks_round_3297_result.md` | 本文件 |

## 实测基线汇总

- 定向自检：`run_selftests.py -k unit_of_work` → 15 条用例 / 0.8s / ALL TESTS PASSED（提交证据 `tasks_round/evidence/R3297.json`）。
- 新测试文件：`python -B tests/test_unit_of_work.py` → Ran 15 tests，OK。
- 受影响门禁：`smoke_test.py --affected unit_of_work` → 10 项通过 / 0 失败。
- 默认冒烟：`python -B smoke_test.py` → 9/9，exit 0。
- 架构门禁：`python -B smoke_test.py --architecture` → 502 条 / 156s / failures=2，失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3291 记录的分支固有红逐名一致；两失败输入文件本轮零改动（`git diff HEAD -- 程序/AGENTS.md 程序/project_status.md` 为空），证为存量非本轮引入。本轮曾引入的 4 处红已全部修复：分支决策点（重测刷新）、ImportError 边界（`os.name` 前置）、物理删除（manifest 状态翻转）、裸 json.loads（`read_json`）。
- 覆盖率：行 78.4%（218/278，≥65 达标）；分支 32.7%（16/49，棘轮下限 32.0）。
- 全量回归：未运行（功能分支开发轮，合入 master 前按 §5 触发 `--all --safe`）。

## 偏差与说明

1. **接手未提交底稿**：实现与测试主体为前序会话在 R3297 领号下完成但未验证未提交；本轮完成先红实证、修复 6 处缺陷（1 处阻断 NameError、1 处测试不可达断言、4 处架构门禁违规）并补齐基线与结果文件。底稿质量整体良好（journal/锁/恢复设计完整），未推倒重写。
2. **`commit` 提交点实现偏离任务书字面**：任务书写「commit→丢弃备份」，实现为 manifest 原子改写 `state='committed'`＋尽力清理 journal——恢复语义等价（非 pending 一律不回滚）且消除 unlink 静默失败与物理删除门禁两个实际风险，已在「设计决策」论证。
3. **覆盖率基线 targets 扩为 10 组**：`tests.test_unit_of_work` 必须进入定向测量集，否则下次任何车道按旧 9 组重测会把 `unit_of_work` 记回 0%、撞 65 下限；runbook §11 数字已同步（门禁 `test_runbook_states_the_directed_measurement_caliber` 强制一致）。
4. **分支覆盖率基线同步刷新**：`test_branch_coverage_floor` 要求基线决策点＝当前 AST（0≠49 实测拦截），按工具真实重测 81 组用例刷新并上调棘轮下限；非本轮主动扩面，是门禁强制。
5. **未动**：`tasks_round/L2领域服务层优化任务书.md`（外来勘误改动）、R3276 外来未跟踪四件（诊断报告/结果文件/任务书×2）、`project_status.md`（仅 master 可提交）一律不入暂存区。
6. **`agent/` 未登记盲区**：`infra/unit_of_work` 依赖 `agent.core` 三原语（`save_file`/`save_text`/`restore_bytes`），与 `infra/` 下 10+ 模块既有先例一致；`agent` 包未入 `_layers.LAYERS` 属任务书已接受的 L2-D8，L0 轮 2 登记后自动转合法。

## 遗留欠账

- 7 处事务接入点（`asset_batch_service`×2、`asset_detail_service`、`video_prompt_publication`、`recon_service`、`white_model_service`、`projects` 等，清单见任务书轮 6）——本轮刻意不接，属轮 6 范围。
- `infra/business_log.py`（轮 7）、`infra/idempotency.py`／`domain/domain_events.py` 行覆盖 CORE_FLOORS 仍 0.0——各自轮次实现并刷新。
- 分支固有架构红 2 条（AGENTS.md 字节预算、状态页轮次冻结）——存量问题，与本轮无关，待 master 合并轮处理。
- `outputs/unit-of-work-transactions/` 为运行时 journal 目录，首次 `begin` 时创建；升级安装覆盖程序文件不影响（位于 `outputs/` 运行数据侧）。

## 提交

- 分支 `codex/wip-r3282`（领号 R3297，工作树 `dsh-864fd932-4054`；领号记录见 `<git common-dir>/round-claims.json`）。
- 主提交：`39c7170f`（9 文件：infra/unit_of_work.py、tests/test_unit_of_work.py、tests/architecture/test_coverage_baseline.py、维护记录/覆盖率基线.json、维护记录/分支覆盖率基线.json、维护记录/分支覆盖率下限.json、runbook.md、本结果文件、tasks_round/evidence/R3297.json）。
- 结果文件补记提交：见本文件 git 历史（`R3297: 补记结果文件commit哈希39c7170f`）；docs-only 补记同样带 `--tests unit_of_work` 重跑定向测试刷新证据（R3284 已踩过的坑）。
- 轮次证据以 `tasks_round/evidence/R3297.json` 中 `run_selftests.py -k unit_of_work` exit 0 / 15 通过 / 0 失败为准。
