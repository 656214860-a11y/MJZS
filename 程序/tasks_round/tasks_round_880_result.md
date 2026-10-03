# R880 仓库卫生：已合并分支与临时产物

- 已删除 7 个已合并且未被工作树占用的分支：`codex/B1-datatable-current`、`codex/R815-startup-registry`、`codex/c1-ghost-project-status`、`codex/c2-rename-claim`、`codex/c4-ui-token-ratchet`、`codex/c5-skill-dag-audit`、`codex/c6-startup-migration-scan`。
- 保留工作树使用中的 `codex/r856-workspace-maintenance`、救援 ref `codex/783b-bg-lifecycle` 及所有未合并分支。
- `.gitignore` 新增 `**/.r[0-9][0-9][0-9]_*`；`git check-ignore .r880_probe.tmp` 已验证。
- 余下 3 个 R814C/R810 stash 及未合并分支仍待逐项裁定，因此 `repo-hygiene` 保持认领中，未标记完成。
