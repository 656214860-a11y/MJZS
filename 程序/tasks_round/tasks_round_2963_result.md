# R2963 合并轮结果
<!-- round-evidence: {"commit_base": "25a12c55", "credential_hits": 0, "evidence_sha256": "aa31a523b84470c9", "exit": 0, "failed": 0, "passed": 0, "round": 2963, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/wip-R2958` 到 master。
- 说明：语音输入离线化与VocoType集成五轮合入 master——离线FunASR默认后端＋云端可选＋EngineHost子进程JSON-Lines＋共享输入框跨13页唯一听写＋词典热词/替换表/AI优化/MCP转写；与R2942共享输入框结构语义合并（voice_button→on_voice→desktop_voice_input新签名），断言未动；冒烟8/8、架构470/470、定向189条全绿；全量7653条20红＝18红master既有回归（纯master复现）＋2红本支欠账已闭环
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
