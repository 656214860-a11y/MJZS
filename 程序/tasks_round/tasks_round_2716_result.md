# R2716 结果：SWE-2 T1 收尾——服务器 pre-receive 证据门禁部署
<!-- round-evidence: {"commit_base": "a684ab97", "credential_hits": 0, "evidence_sha256": "48159d6f622ad700", "exit": 0, "failed": 0, "passed": 17, "round": 2716, "tests": "run_selftests.py -k remote_pre_receive server_pre_receive"} -->

1. 轮次类型：可靠性轮（优化任务书 T1「私有服务器远端 CI 与备份校验」的 pre-receive 部署收尾；不改产品阶段行为）。
2. 测试：`run_selftests.py -k remote_pre_receive server_pre_receive` 17/17 绿（新增 4 条证据门禁用例）；`smoke_test.py` 8/8 绿；服务器侧沙箱红绿矩阵见「执行记录」。
3. 欠账：T1 仍余 post-receive CI（`local_ci.py` 静态＋架构门禁）与 `scripts/backup_verify.py` 未做；backup 远端 master 落后本地 186 个提交，其中 8 个缺轮次证据（见「首推预判」），首次同步推送会被新门禁拒绝，处置待用户决定。

## 本轮改动

- `维护记录/基准脚本/remote_pre_receive.py`：并入 `server_hooks/pre-receive` 的证据门禁判据（新增第 4 项检查）——推到 `master`/`main` 的 R2527 及以后 `R<n>:` 源码轮次提交（改 `程序/` 下 .py 或合并提交）必须带同一提交里的绿色 `程序/tasks_round/evidence/R<n>.json`（凭据扫描已跑无命中、定向测试退出码 0 无红；`docs-only`/`merge-ci-exit` skipped 放行），删除 master/main 一律拒绝，其它分支不受影响。判据与 `round_evidence.judge`、`server_hooks/pre-receive` 同口径。
- `tests/test_remote_pre_receive.py`：+4 条用例（`round_of` 解析、`evidence_problem` 与 server_hooks 对照实现逐样本一致、`check_push` 只管保护分支、绿证据放行）。
- `维护记录/基准脚本/server_hooks/pre-receive`、`runbook.md`「服务器端闸门」：部署说明同步为「判据已并入 `remote_pre_receive.py` 并部署」，消除「需用户部署」的过期表述。

## 服务器执行命令清单（执行前列出）

```bash
# 0) 前置核对（只读）
ssh 8.138.223.126 'ls -la /srv/git/manju-assistant.git/hooks/pre-receive*; python3 --version; git --version'

# 1) 备份现有钩子、上传合并版、刷新 ci 目录参照副本
scp 程序/维护记录/基准脚本/remote_pre_receive.py 8.138.223.126:/tmp/remote_pre_receive.py
ssh 8.138.223.126 'cp /srv/git/manju-assistant.git/hooks/pre-receive /srv/git/manju-assistant.git/hooks/pre-receive.bak-20261115 \
  && cp /tmp/remote_pre_receive.py /srv/git/manju-assistant.git/hooks/pre-receive \
  && chmod +x /srv/git/manju-assistant.git/hooks/pre-receive \
  && cp /tmp/remote_pre_receive.py /srv/git/ci/remote_pre_receive.py'

# 2) 沙箱红绿验证：/srv/git/ci/test.git 裸仓＋/srv/git/ci/sandbox-src 工作仓
#    场景：语法错误红／缺证据红／绿证据放行／文档提交放行／删 master 红／codex 分支不受证据门禁
#    （脚本见执行记录）
```

## 首推预判（本地干跑，非服务器执行）

backup 远端 `refs/heads/master` = `07287269`，本地 master `a684ab97`，待推 186 个提交。用合并后的 `check_push` 对该区间干跑：**8 个提交缺 `evidence/R<n>.json` 将被拒**——R2679、R2650、R2656、R2633、R2627、R2622、R2596、R2531（多为欠账门禁循环期间的等效手工合并与个别绕过证据的提交）。首次 `git push backup master` 会被拒；处置选项：① 管理员临时摘钩推送后装回（脚本既定逃生口，历史不改写）；② 用户另行决定。`codex/*` 等非保护分支推送不受证据门禁影响，静态三项检查照旧。

## 执行记录

### 服务器部署（已执行，全部经由 ssh/scp 8.138.223.126＝`backup` 远端）

- 前置核对：`hooks/` 下原有 `pre-receive`（6838 B，R2609 gitleaks 合并版）、`pre-receive.bak-r2602`；服务器 Python 3.11.6、git 2.47.3。
- 部署：`scp remote_pre_receive.py → /tmp/` → `cp` 至 `/srv/git/manju-assistant.git/hooks/pre-receive`（旧版备份最初命名 `pre-receive.bak-r2697`，轮次两次重领后改名为不带轮次的 `pre-receive.bak-20261115`）＋ `chmod +x` ＋同步 `/srv/git/ci/remote_pre_receive.py` 参照副本。**插曲**：首次 scp 误从 marble-pulley 工作树（落后 master 的旧版 4334 B）取文件，已立即用本工作树正确版本（228 行/10047 B，md5 `45448fb7…` 本地一致）覆盖重部并核对 `wc -l`/md5/`compile()` 语法。
- 部署后钩子含四道检查：静态编译、凭据形态、gitleaks（可选）、master/main 证据门禁。

### 沙箱红绿验证（/srv/git/ci/test.git＋sandbox-src，验证后已删）

| 场景 | 结果 |
|---|---|
| codex 分支注入 `程序/bad.py` 语法错误 | 红：`语法错误` |
| master 首推基线（old=0） | 绿 |
| master 推 R3001 改 .py 无证据 | 红：`缺少 …/evidence/R3001.json` |
| 同内容补绿证据重推 | 绿 |
| master 纯文档提交 R3002 | 绿（无需证据） |
| 删除 refs/heads/master | 红：`不允许删除` |
| codex 分支 R3003 改 .py 无证据 | 绿（证据门禁只管 master/main） |

7/7 符合预期。

### 首推预判复核

合并版 `check_push` 对 backup 远端实际待推区间 `07287269..a684ab97`（186 提交）干跑：8 个提交缺证据（R2679、R2650、R2656、R2633、R2627、R2622、R2596、R2531），首次 `git push backup master` 将被拒——属门禁按设计工作，历史提交无法回填证据（不改写历史），处置待用户定（临时摘钩一次推送是脚本注明的逃生口）。本轮未执行任何 `git push`。

## 涉及文件

- `程序/维护记录/基准脚本/remote_pre_receive.py`（并入证据门禁，第 228 行）
- `程序/tests/test_remote_pre_receive.py`（+4 用例，共 11 条）
- `程序/维护记录/基准脚本/server_hooks/pre-receive`（docstring 改为判据规格说明）
- `程序/runbook.md`（「服务器端闸门」段更新为已部署口径＋首推注意事项）
- `程序/tasks_round/tasks_round_2716_result.md`（本文件）
