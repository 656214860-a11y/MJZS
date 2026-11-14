# R2459 结果：强化规则 34a 强制——pre-commit 拦截 master 直接提交功能源码

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.4）：强化规则 34a 的强制执行，不改产品功能。起因是本会话在 master 主工作区直接改源码、违反规则 34a；补强为三道闸兜底（pre-commit 新增拦截 + round_claim 脏 master 拒领 + commit-msg 轮次号校验），并在 AGENTS.md 写明「第一步硬性动作」。

2. **测试跑了吗、三个基线过了吗？**
   - 定向：`tests/test_git_hooks.py` **14/14** 全绿（含新增 3 条规则 34a 用例：master 直接提交功能码被拒、合并提交放行、仅文档放行；并把原 allowlist 用例改到工作分支避免与规则 34a 混淆）。
   - 默认冒烟、架构门禁、全量：**未运行**（本轮只改 hook/AGENTS.md/测试，不触及产品源码；全量欠账不因本轮新增）。

3. **`project_status.md` 的欠账少了吗？**
   本轮不直接减少既有欠账；补强了规则 34a 的可执行性，属治理收口。

## 改动清单

- `程序/维护记录/基准脚本/hooks/pre-commit`：新增规则 34a 拦截——master/main 上非合并提交（无 `MERGE_HEAD`）任何非默认安全文档的 `程序/*` 文件即拒绝，报「规则 34a——主工作区只做同步/合并/提交」；合并提交与 `tasks_round`／`project_status.md`／任务队列.json 豁免。
- `程序/AGENTS.md`：规则 34a 补「第一步硬性动作」段落，明确「先领号、再动码」。
- `程序/tests/test_git_hooks.py`：新增 3 条规则 34a 用例，并把 `test_precommit_requires_explicit_allowlist_for_program_code` 改到工作分支。

## 自检结论

`test_git_hooks.py` 14/14 实测通过；钩子经 `install_git_hooks.py` 重新安装到共享 hooks 目录并确认规则 34a 已生效。

## 已提交

- commit `0d279fe5`（分支 `codex/wip-R2459`，先 `git rebase master` 再 `git merge --ff-only` 合入 master）R2459。
- 本轮严格走了规则 34a：功能工作树 → 领号 → rebase → 回合 master。
