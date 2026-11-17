# R3169 结果（并行吞吐治理未闭环项收口：interval 5→8＋A2 删除执行＋车道角色登记）
<!-- round-evidence: {"commit_base": "a6b4b83f", "credential_hits": 0, "evidence_sha256": "106146f8e9471ee7", "exit": 0, "failed": 0, "passed": 137, "round": 3169, "tests": "run_selftests.py -k selftests auto_full_safe full_safe_merge_gate agents_md agent_doc_budget skill_reference_injection"} -->

- 轮次类型：结构治理轮（分支 `codex/fullsafe-int8`）。

## 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮（治理参数调整＋任务书未闭环项执行，≤3 个模块）。
2. **测试跑了吗、三个基线过了吗？** 定向跑了：`run_selftests.py -k selftests auto_full_safe full_safe_merge_gate round_baselines agents_md agent_doc_budget` 133 条（`agents_md` 初跑 1 红系新工作树缺 gitignore 的 `维护记录/基准历史.json`，补齐后 15/15 绿）；`smoke_test.py` 9/9；`smoke_test.py --architecture` 483 条 1 红（`test_skill_reference_injection`——新工作树 gitlink 子仓未检出，按钉住 SHA 本地克隆补齐后该文件 9/9 绿）。全量未跑，合并轮 CI 与后台补跑覆盖。
3. **欠账少了吗？** 本轮改 `selftest_env.py` 属源码轮；`FULL_SAFE_ROUND_INTERVAL` 5→8 合入后欠账口径放宽，全量触发频率约降 40%。

## 用户决策落地（2026-11-17 会话内逐项确认）

| 未闭环项 | 决策 | 本轮执行 |
| --- | --- | --- |
| B2 `FULL_SAFE_ROUND_INTERVAL` | 调高到 8 | `selftest_env.py` 5→8；`AGENTS.md` §5、`runbook.md` §4 两处口径同步（含沿革：R2538 起 5、R3169 回 8） |
| A2 删除执行 | 全部执行含 PARKED | 安全档已删：19 RECYCLE 工作树＋374 MERGED 分支（`git branch -d` 374/374 全绿）；104 PARKED 审查清单产出待逐条确认 |
| GUI 专道 | 注册现有车道 | `devin-dead-symbols` 登记 `role:gui`（lanes.json） |
| 合并道 | 注册专职合并道 | `漫剧制作助手`（master）登记 `role:merge`；merge-queue 已实际运行（mq-1/mq-5 done） |

## A2 删除执行明细（ops，非代码变更）

- 依据：`worktree_ledger.py --plan --branches`（2026-11-17 快照）＋用户「全部执行含 PARKED」授权。
- 工作树 19 棵：8 棵 `git worktree remove` 直接成功；10 棵含 gitlink 子仓（`AIGC创作全流程`/`剧本锻造`/`编剧技能集`/`HoLLMwood`/`.仓库克隆-*`）被 git 拒绝——逐仓核验 `status` 净、`log --all --not --remotes` 为空后 `rm -rf`＋`worktree prune`（等价 force，已留证）；`devin-asr-utf8` 部分删除后残留已清；`velvet-governor` 余一个被进程占用的空目录壳（零内容，待进程退出后可删）。
- 分支 374 个：全部 `git branch -d`（merged-only 兜底）一次成功，零误删。
- PARKED 104 个：审查清单 `程序/维护记录/PARKED分支审查清单_20261117.md`（分支/tip sha/ahead/独有提交前 12 条），git common-dir 另有副本 `.git/parked-branches-review.md`；确认为删后 `git branch -D`（含未合并提交，-d 会拒）。

## 改动

| 文件 | 改动 |
| --- | --- |
| `selftest_env.py` | `FULL_SAFE_ROUND_INTERVAL` 5→8 |
| `AGENTS.md` | §5 自检表「≥ 5 个」→「≥ 8 个」 |
| `runbook.md` | §4 两处口径同步（规则行＋详细口径（5）→（8）） |
| `tasks_round/任务完成/并行吞吐治理·任务完成.md` | 未闭环项 4 条更新为执行后状态 |
| `维护记录/PARKED分支审查清单_20261117.md` | 新增：104 个 PARKED 分支逐条审查清单 |
| `tasks_round/tasks_round_3169_result.md` | 本文件 |

## 验证

- `run_selftests.py -k selftests auto_full_safe full_safe_merge_gate round_baselines agents_md agent_doc_budget`：133 条，`agents_md` 环境红补齐后全绿。
- `run_selftests.py -k skill_reference_injection`：9/9 绿（gitlink 补齐后）。
- `smoke_test.py`：9/9。
- `smoke_test.py --architecture`：483 条；唯一红 `test_skill_reference_injection` 系工作树缺 gitlink 子仓内容（环境性），补齐后定向 9/9 绿。
- 环境备注：新工作树需补两类 gitignore/gitlink 内容——`维护记录/基准历史.json`（复制主树）、4 个 gitlink 子仓（本地克隆至钉住 SHA）；`.wt/ci` 已具备同等内容。

## 仍未解决／移交

- 104 个 PARKED 分支删除：待用户对审查清单逐条确认（清单含 tip sha，可 `git branch <名> <sha>` 重建）。
- `velvet-governor` 空目录壳：待占用进程退出后 `rmdir`。
- `lanes.json` 中 `gov-v2` 条目指向已删工作树，7 天失联警告期后自然过期，不阻断。
