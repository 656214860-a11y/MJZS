# R3173 修复轮结果
<!-- round-evidence: {"commit_base": "2cab1882", "credential_hits": 0, "evidence_sha256": "aae1a74125f41976", "exit": 0, "failed": 0, "passed": 43, "round": 3173, "tests": "run_selftests.py -k skill_lifecycle_service claude_writing_session copy_rules agent_skill_sync"} -->

- 轮次类型：修复轮。
- 起因：R3167 合并轮（SKILL 生命周期 T1–T10）落地后，合并点自动全量（HEAD a6b4b83f）报 2 个文件红：
  `test_copy_rules`、`test_claude_writing_session`（日志 `logs/auto_full_safe.log`，退出码 1，用时 1011 秒）。
- 根因与最小修复：
  1. `test_copy_rules.test_nothing_talks_about_the_user_in_third_person`：
     `skill_lifecycle_service.py:278` 的 ImportBlocked 文案含禁用第三人称「人工处理」；
     改为第二人称「请您处理」。
  2. `test_claude_writing_session.test_desktop_restart_closes_old_before_requesting_new_slot`：
     T6 把发送前技能同步校验从 codex 单目标泛化到 `ENGINE_TARGETS`（claude→~/.claude/skills），
     该用例未像 `test_flow_agent_launch`/`test_idea_semantic_brief`/`test_workflow` 那样 mock
     `orchestrator.agent_skill_sync.sync_agent_skills`，命中本机 `~/.claude/skills` 里 68 个
     旧版（无 target 字段）同步目录的冲突判定而误报。按既有先例补同一 mock，断言未动。
- 测试：定向 4 文件 58 条全绿（test_copy_rules 14、test_claude_writing_session 11、
  test_agent_skill_sync 18、test_skill_lifecycle 15，0 跳过）；默认冒烟 9/9。
- 欠账：`~/.agents/skills` 内有本分支早前测试写入的 worktree-root marker（root 指向已清理的
  devin-skill-t4），codex 引擎对 agents 目标会判冲突——属开发环境污染，非用户数据；
  记录影响，不动用户目录。全量欠账随 R3172 治理口径（间隔 ≥8）观察。
- 断言未动；未跑全量（修复轮，合并点自动全量将覆盖）。
