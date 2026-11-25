# R4429 合并轮结果
<!-- round-evidence: {"commit_base": "02ec82451", "credential_hits": 0, "evidence_sha256": "fd6881bec1b0e1a5", "exit": 0, "failed": 0, "passed": 0, "round": 4429, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/fix-send-affected-reds` 到 master。
- 说明：合入 FIX-SEND-AFFECTED-REDS(R4428)：修复主干 7 条 --affected 既有红（resolve_for_send 兼容非绝对桩、test_skills 对齐 REL-03、test_skill_budget_send_entries CLI 隔离、test_video_ui:1121 对齐图标重染色）
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
