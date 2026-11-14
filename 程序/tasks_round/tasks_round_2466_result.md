# R2466 架构审计同步轮

## 结论

把 `aigc_lint` 登记为受控进程适配器白名单，并把 `IdeaChatMixin` 行数棘轮从 770 下调到实际 748，清除两项架构审计偏差。

## 关键改动

- [test_coverage_audit_ratchet.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/architecture/test_coverage_audit_ratchet.py)
  - `P21` 增加 `aigc_lint`，承认它是总控包脚本的受控桥。
- [test_complexity_ratchet.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/architecture/test_complexity_ratchet.py)
  - `desktop_idea_chat.IdeaChatMixin` 上限 770→748。

## 验证

- `test_complexity_ratchet` + `test_coverage_audit_ratchet` 10/10 通过。

## 提交

- 已提交：`d47e2325aa86a64eeb85e641b5e94f67011a306d`
- 分支：`codex/wip-R2466`
