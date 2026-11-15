# R2695 结果：轮次号认领归属制，修复 commit-msg「必须等于最新领号」竞态
<!-- round-evidence: {"commit_base": "ec62c7cc", "credential_hits": 0, "evidence_sha256": "b24a87c16439c854", "exit": 0, "failed": 0, "passed": 38, "round": 2695, "tests": "run_selftests.py -k git_hooks round_claim"} -->

1. 轮次类型：修复轮（提交门禁根因修复，先红后绿）。
2. 测试：`run_selftests.py -k git_hooks round_claim` 38 条全绿；默认冒烟 8/8；
   架构门禁 466 条中 2 失败＋1 错误均为基线既有／环境性（见下），与本轮 diff 无关。
3. 欠账：无新增；本轮消除一类确定性浪费——他车道领号不再使在途轮次的提交被拒、
   被迫弃号重领（R2556 曾因此整轮作废）。

## 根因

commit-msg 钩子要求提交轮次号 `==` central `round-counter.json` 的 `last_claimed`。
领号发生在开工时、提交发生在全量测试（16–21 分钟）与合并出口 CI 之后；
期间任何其他车道 `next` 一次，本车道已领轮次就永久失去提交资格
（R2556 实证：结果文件与证据被迫撤下重领）。merge_round 同样中招：
领号后还要跑 `local_ci.py exit` 才提交，窗口更长。

## 修复（认领归属制）

- `round_claim.py`：`next` 在认领锁内把「轮次→{worktree, branch, at}」追加进
  `<git common-dir>/round-claims.json`（独立文件）。独立成文件是刻意的：
  旧版 `claim_next` 只整写 `round-counter.json`，混合版本并行时登记不会被抹掉
  （首版写进计数器内层 claims，实测被旧代码领号冲掉，已更正）。
- `hooks/commit-msg`：有归属记录的轮次校验「属于本工作树
  （`git rev-parse --show-toplevel`，normcase/normpath 比较）」；
  无记录的旧格式轮次沿用旧规则（须等于 `last_claimed`）；
  「已被非祖先分支使用」检查原样保留。
- `round_claim.py record <轮次号>`：为升级前已领、无归属记录的在途轮次补登；
  仅允许 `last_claimed` 以内的号，已有他主记录拒绝，登记路径已消失的失效记录可补登。
- `merge_round.py` 仅更新过时注释；`runbook.md` §12 同步口径。

## 先红后绿证据

改动前 `run_selftests.py -k git_hooks round_claim`：新增 4 条用例红
（KeyError 'claims'／AttributeError record_claim／hook 拒绝 OWNED 轮次／外属于他树仍报旧文案）；
改动后 38 条全绿（`ALL TESTS PASSED`，13.0 秒）。

## 真机验证（本仓库 common-dir）

- 本轮 R2695 领号后 last_claimed 已被其他车道推到 2700；
  `record 2695` 补登后，新 commit-msg 对 `R2695:` 返回 0（放行），
  对未登记的 `R2696:` 仍按旧规则拒绝——竞态窗口内提交不再被顶掉。

## 三个基线数

- 默认冒烟：8/8 通过。
- 架构门禁当轮实际：466 条，2 失败＋1 错误——`test_round_number_continuous`
  （2684!=2682，master 主检出复跑为 2697!=2683，同样红，系状态页与结果文件
  跨车道欠账）、`test_script_stages_name_only_their_approved_00_references`
  与 `test_performance_history...`（引用文件／gitignored `基准历史.json`
  在本工作树缺失，主检出有文件时该项通过）——均与本轮 diff 无关。
- 全量回归：未跑；最近绿凭据 round=2656（993.5s，见 full-safe-receipts.json）。
  本轮改动为开发期工具链（hooks/领号脚本/测试/文档），不触产品运行路径。

## 部署与兼容说明

- 钩子由 `round_claim.py next` 的 `ensure_hooks` 自愈安装；混合版本期间
  新旧钩子双向兼容（旧钩子忽略 claims 文件，新钩子对无记录轮次走旧规则）。
- 在途车道升级后若提交被拒：在认领工作树跑 `round_claim.py record <其轮次号>`
  补登即可，无需弃号重领。
