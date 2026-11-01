# R880 仓库卫生：已合并分支与临时产物

- 已删除 7 个已合并且未被工作树占用的分支：`codex/B1-datatable-current`、`codex/R815-startup-registry`、`codex/c1-ghost-project-status`、`codex/c2-rename-claim`、`codex/c4-ui-token-ratchet`、`codex/c5-skill-dag-audit`、`codex/c6-startup-migration-scan`。
- 保留工作树使用中的 `codex/r856-workspace-maintenance`、用户指定的救援 ref `codex/783b-bg-lifecycle`；它们分别没有未合并提交、以及仍含未落主线的背景生命周期实现。
- 保留 `b-docs-c-reports`、`codex/R817-ui-authority-coverage`、`codex/R820-ui-coverage`、`codex/e1-pet-ui-test-split`、`r811-infra`：逐一核查均仍有主线未包含的有效提交，不能以“未合并”名义删除。
- `.gitignore` 新增 `**/.r[0-9][0-9][0-9]_*`；`git check-ignore .r880_probe.tmp` 已验证。
- 已按内容定位并删除过时的 DataTable stash `fc240a3`（原 `stash@{3}`）；余下 R814C/R810 三个 stash 均保留：两个 R814C 通知迁移的改动已在当前**未提交**工作区逐字出现，仍需作为恢复点；R810 stash 对应 `r811-infra` 的未合并基础设施提交，不能删除。
- 当前 `tests.architecture.test_notification_boundary` 为 3/3 通过。以上裁定完成后，`repo-hygiene` 可收口；后续只有在相应实现落主线后才能再次评估保留分支和 stash。
