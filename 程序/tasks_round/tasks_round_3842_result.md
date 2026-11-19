# R3842 结果：合并轮——codex/requirements-architecture-review（桌面与云服务验收任务书 A–F）合入 master
<!-- round-evidence: {"commit_base": "730cbe28", "credential_hits": 0, "round": 3842, "merge": true} -->

- 轮次类型：合并轮（§3 接续/集成）。把验收分支 14 个提交（R3707–R3826）合入 master。
- 是否跑测试：合并前分支侧已跑棘轮/文案/契约定向与覆盖率基线重测（R3826）；合并树上重测分支覆盖率基线（99 目标）并跑冒烟/架构抽检，详见 §4。
- 积压是否下降：是——验收台账 A–F 全部落库，任务书闭环文件齐备；PRD v2.0 与 REQ-APP-01/02 冲突已按「master v2.0 为底＋回插验收分支需求登记」消解。

## 1. 三问

1. **什么类型轮**：合并轮。来源分支 `codex/requirements-architecture-review`（merge-base `86e863bb`，分支领先 14、master 领先 17，合并基线取 master `730cbe28`）。
2. **是否跑测试**：跑了——合并树分支覆盖率基线重测（99 目标用例全过后写入）、`smoke_test.py`、原失败集定向复检；完整 `--all --safe` 以合并后主工作区实测为准并如实记录。
3. **积压是否下降**：是——任务书 A–F 验收证据、台账、完成文件全部进入 master；分支侧棘轮欠账（R3826）随合并一并核销。

## 2. 冲突与消解

| 文件 | 冲突性质 | 消解 |
| --- | --- | --- |
| `程序/说明/产品需求规格.md` | master PRD v2.0 重写 vs 分支旧版＋REQ-APP-01/02＋追溯指针 | 取 master v2.0 全文为底；在 §1 末尾回插「对话需求追溯」指针、REQ-APP-01 及决定沿革；REQ-APP-02 回插 §1.3 商业模式节首；分支侧旧版 P0 表头与「先不承诺」段废弃（v2.0 §1.5 不做什么表已覆盖，保留一行注记） |
| `程序/维护记录/分支覆盖率基线.json` | 两侧各自重测的全量快照互不相同 | 取分支版占位后在**合并树**上以 99 个目标真实重测刷新（门禁要求真实重测，不手改数值） |
| `程序/runbook.md`、`程序/说明/工程文档登记表.md` | 自动合并成功 | 无人工干预 |
| `程序/project_status.md` | master 侧 R3308/R3810 头部更新，分支侧未改 | 自动取 master 版，本轮回写轮次头 3843，保留 R3308/R3810 接续记录 |
| `tests/test_error_codes.py`、`tests/test_secret_status_diagnostics.py` | 分支已同步 master 权威版本 | 合并后两侧一致，无冲突 |

### 2.1 分支覆盖率测量目标补登说明（诚实记录）

合并树首测（原 98 个登记目标）发现三个 L1 模块实测 0.0%：`artifact_index.py`（下限 71.4%）、`job_store.py`（84.6%）、`prefetch.py`（80.0%）。根因相同——不是代码退化：artifact_index 仅被 `domain/keyframe_lifecycle_service` 惰性 import；job_store、prefetch 亦只经异步/惰性路径被生产侧调用，98 个登记目标没有任何用例真正走进其决策点。三个模块的专用测试 `tests/test_artifact_index.py`、`tests/test_job_store.py`、`tests/test_autotune_prefetch.py`（＋命中共享回收路径的 `tests/test_asset_thumbs.py`）自各模块交付轮起就存在，但从未列入测量目标清单；master 侧既有基线中的 71.4/84.6/80.0 实为旧口径遗留快照（floor 门禁只读基线值不重测，故未现形）。本轮把这 4 个测试补入测量目标（98→102），合并树真实重测：artifact_index 11/14＝78.6%、job_store 11/13＝84.6%、prefetch 8/10＝80.0%，全部 ≥ 登记下限，未下调任何下限，测量范围只增不减。

## 3. 带入 master 的验收内容

- 任务书《桌面与云服务架构及全链路验收任务书》A–F 全部执行完毕：可观测性（R3709）、安全边界（R3739）、发布回滚（R3749）、恢复与连续使用（R3759）、端到端产品验收（R3800，17/17）、阶段操作接入索引与走查（R3812，3/3）。
- 验收台账 `程序/tasks_round/桌面与云服务验收台账.md` §8 汇总与移交说明；任务完成文件 `程序/tasks_round/任务完成/桌面与云服务架构及全链路验收·任务完成.md`。
- 已知限制如实保留：管理面/SSH 不可达导致异地备份恢复未测（以本地备份与服务端测试为替代证据，台账标注）；metering 取消链路一次未知计量请求与诊断缺失（R3709 结果文件记录）。
- R3709 产品修复：metering 请求尝试元数据在结算事务 reload 时丢失已修，新增 `tests/test_model_metering.py` 回归。

## 4. 测试与基线

- 合并树 `branch_coverage_report.py`（102 目标＝原 98 登记＋test_artifact_index/test_job_store/test_autotune_prefetch/test_asset_thumbs）：目标用例全部通过后写入基线（退出码 0）。
- `smoke_test.py`：合并树实测 9/9 通过。
- `smoke_test.py --architecture`：合并树 583 项中唯一红为 `test_branch_coverage_floor`（artifact_index 0.0%），根因见 §2.1；补登目标重测后复检本项。
- 定向复检：`silent_exception_ratchet unification_ratchet copy_rules branch_coverage_floor error_codes secret_status_diagnostics`（R3826 分支侧已 61/61 绿）；合并树复跑同组关键词。
- 全量 `run_selftests.py --all --safe`：合并后主工作区执行，结果如实记录于本文件补记或后续状态轮。

## 5. 未测／限制

- 异地备份恢复：管理面不可达，未测（台账保留受阻记录，非本轮新增）。
- 走查脚本 R3826 棘轮重构后已回归复跑 3/3（证据见会话记录；脚本语义未变）。
- 合并期间 master 由 `f7ef4b98` 前进至 `730cbe28`（R3308 槽位泄漏修复＋R3810 连续性恢复），本合并已改为基于 `730cbe28` 重做并重新消解冲突，分支覆盖率基线在最终合并树上重测。

## 6. 合并校验与提交

- 合并提交：`99554eb1`（`R3842: 合入 codex/requirements-architecture-review 到 master（桌面与云服务验收任务书 A–F 全部验收 + PRD v2.0 与分支覆盖率基线消解）`），基线 master `730cbe28`。
- 共享状态文件核对（runbook 合并后两条命令原始输出）：

```
$ git diff 730cbe28..HEAD -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'
（空——仅「当前轮次」头行被替换，两侧记录全部保留）

$ git show HEAD:程序/project_status.md | grep -oE '^R[0-9]+' | sort -u
R1036 R1265 R1440 R1507 R1691 R1693 R2912
（与 master、分支两侧各自集合相等，并集完整）
```

- 合并后门禁（合并树实测）：`tests.architecture.test_branch_coverage_floor` 5/5 绿；`tests.test_script_contract` 58/58 绿；`smoke_test.py` 9/9；`--architecture` 583 项其余全绿。
- 全量 `--all --safe`：欠账 13 源码轮次已触发后台 auto-full-safe 补跑（`--status` 示「后台在跑」），结果凭据以 `.git/full-safe-receipts.json` 为准。
- 轮次说明：合并轮次号以主工作区领取的 R3842 为准（分支树先前领取的 R3828 不再使用，结果文件随之编号为 3842）。
- 环境事故记录：回收失效验收锁时误删了他车道在跑的 full-safe/gui 锁文件（PID 26020），已按锁载荷格式原样重建（pid/started_at 精确，round 字段置 null），互斥语义恢复；其进程正常跑完后按 pid 匹配正常释放。

### 6.1 合并后自动 full-safe 实测结果（如实记录）

- 后台 auto-full-safe 于 2026-11-19 21:05–21:40 在 `.wt/ci` 合并树（HEAD `99554eb1`）实跑 2141 秒，退出码 1，**非绿、凭据未写入**：
  - 红项 1 条：`test_distribution_selfcheck.test_manifest_covers_every_file`——master 侧 R3809 新增 `程序/docs/specs/` 八册未在 `distribution_manifest.md` 声明保留/排除，属真实清单欠账，由 R3846 补登修复。
  - `GUI_DEFERRED`：170 个 GUI 测试因他车道进程（PID 8600）持 GUI 令牌而未执行，不计通过；`[SUSPECT_CONCURRENCY]` 建议串行复跑。串行复跑结果以 `.git/full-safe-receipts.json` 凭据为准。
