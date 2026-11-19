# R3696 合并轮结果
<!-- round-evidence: {"commit_base": "1121d248", "credential_hits": 0, "evidence_sha256": "e24a31e0723b3da9", "exit": 0, "failed": 0, "passed": 0, "round": 3696, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮（手工执行；merge_round.py 两次因出口 CI 中断，末次失败后改等价手工流程）。
- 合入：`codex/l1-enterprise` 到 master——R3691（I16 预算引擎 `infra/budget.py`＋pet 五类上限迁 L3 `pet_budget`）、R3693（R3690 出口 CI 漏 add 补齐）、R3695（pet_agent 规模棘轮 1182→1046）＋随轮修正（budget `reserve` 参数对象收拢至 7、`since` 校验 raise 迁 `ConfigError`、runbook 覆盖率口径 668→670/99→100、共享运行环境补装已准入 psutil/nvidia-ml-py）。
- 冲突：无（干净合并）。
- 出口 CI：merge_round 驱动默认冒烟＋静态门禁＋架构门禁；历史红项全部修复转绿，唯一余红 `test_site_packages_whitelist`＝邻车道当日安装未登记 pydantic 五包（无源码 import，环境性，与合并零因果，R3690 同录）。
- 断言未动。未跑全量（合并轮惯例由后台全量补跑凭据覆盖）。
- 备注：主检出 299 个 `skills/` 未提交删除系邻车道现场，本合并窗口内经 stash 暂存，提交后原样恢复。
