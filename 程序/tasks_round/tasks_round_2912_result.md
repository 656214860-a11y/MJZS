# R2912 验证基线轮结果：R2908 合并轮全量验收记录
<!-- round-evidence: {"commit_base": "7f3d2953", "credential_hits": 0, "evidence_sha256": "96e6fea203c978c2", "exit": 0, "failed": 0, "passed": 0, "round": 2912, "tests": "docs-only"} -->

- 轮次类型：验证基线轮（§3.8）。本轮无生产代码改动，只登记 R2908 合并轮（`7f3d2953`）的验收实测与三笔环境性红账。
- 背景：R2908 把任务书五轮（R2862→R2881→R2893→R2898→R2905）＋R2909 行数修复合入 master；上次全量 R2904 后累计源码轮次远超 5，按 §5 触发当次 `--all --safe`。

## 三个基线（合并树实测）

| 基线 | 结果 |
| --- | --- |
| 默认冒烟 | 8/8 ✔（合并解算后、提交前实测） |
| 架构门禁 | 首跑 470 条 1 红：`test_complexity_ratchet` 登记表欠账（PetStagesMixin 实际 1167 登记 1186）；合并解算中按棘轮规则下调至 1182（收紧方向）；复测 complexity/module_size/unification 10/10 ✔ |
| 全量 `--all --safe` | 7520 条 / 530.0 秒 / **3 个文件有红，0 个与合并相关**（明细下述）；绿凭据未写入，`last_full_safe_all_round` 仍为 2904，欠账如实保留 |

## 全量三笔红的定性（逐项核验，非合并回归）

1. `test_client_profiles::test_req_s01_56_builtin_catalog_covers_every_known_client`（确定性复现）：测试用默认 `user_path` 读 `程序/data/客户端档案.json`——该文件被 gitignore、属用户数据，其中有 6 条自定义档案（claude-2/3/4/5、node、codex-2），合并 16 行 ≠ 期望内置 10 行。合并未触碰 `client_profiles.py` 与任何档案文件；属测试未隔离用户数据的既有环境债。
2. `test_distribution_selfcheck` 两条（确定性复现）：工作树存在未跟踪文件 `.agent-handoff/archive/snapshot-before-o06-pause-20261012.md`（`.agent-handoff/` 已停更归档），分发清单未声明。与本次合并无关的环境债。
3. `test_pet_ui::test_the_armed_hold_matches_the_reading_time`（全量并行下偶发）：串行复跑 `pet_ui` 全部 49 单元绿；失败时有其他 PID 持 GUI 令牌（`[SUSPECT_CONCURRENCY]`），判定并行负载下的时序抖动，非回归。

## 结论

合并内容本身零回归；三笔红均为环境/既有欠账，按规则 30a 保留记录、不扩大任务。后续若要清零：①测试隔离 `user_path` 或把自定义档案移出默认数据位；②`.agent-handoff` 归档文件补分发清单声明或移出工作树。均不在本轮范围。
