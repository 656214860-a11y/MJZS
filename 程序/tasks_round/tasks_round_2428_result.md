# R2428 结果：主工作区同步工具 + 领号 ahead 门禁 + 规则 34a 落地

## 三个必答（§7）

- **轮次类型**：功能轮（§3.1）——新增「主工作区同步」工具 `scripts/sync_master.py`（`fetch` + 仅 `--ff-only` 只拉不推），并落地两条纪律：① `round_claim.py next` 领号时对 `ahead>10` 的 WIP 分支拒绝（规则 27 并行硬规则）；② AGENTS.md 新增规则 34a「主工作区＝镜像 + 功能工作树开发」。
- **测试跑了吗、三个基线过了吗**：
  - 定向：`run_selftests.py -k test_sync_master test_round_claim` **21/21**（test_sync_master 5 条、test_round_claim 16 条，含新增 2 条 ahead 门禁用例），0 红。
  - 默认冒烟 **8/8**（第 10 轮，与基线一致）。
  - 架构门禁：`smoke_test.py --architecture` 跑 416 条，**2 红**，均为功能工作树环境限制、非本轮回归（详见下「架构门禁 2 红归因」）。
  - 全量：本轮改 `scripts/` 下 2 个 `.py`，按 `count_source_rounds` 口径（`NON_SOURCE_DIRS` 不含 `scripts/`）**计 1 个源码轮**，全量欠账 1/8，未触发门禁线，本轮不跑全量。
- **project_status.md 的欠账少了吗**：本轮不产生新欠账；规则 27 的 ahead>10 拒绝领号由此前「只在文档声明、无机械约束」变为有脚本门禁 + 测试锚定，闭环了并行硬规则的可执行性。

## 根因与修复

### 新增 `scripts/sync_master.py`（主工作区同步）

- **背景**：规则 34a 要求每轮开工前先同步主工作区，但此前没有机械实现，「同步」靠人工记忆执行 `git fetch` + 判断是否快进。
- **实现**：`sync_master(*, root, remote="backup", branch="")` 只做三件事，绝不 push（规则 38）：
  1. 校验前置条件：必须是主工作区（`git-dir == git-common-dir`，即非链接工作树）、当前分支为 master/main、工作树干净；任何一项不满足都抛 `RuntimeError` 拒绝，不静默切换分支。
  2. `git fetch <remote>` 拉取最新引用，失败即抛错。
  3. 落后时 `git merge --ff-only <remote>/<branch>` 快进；领先（ahead>0）只报告不回写、不 rebase、不 push。
- **入口**：`scripts/dev.py` 新增 `sync` 子命令（`dev.py sync`），文档注释同步。

### 新增 `round_claim.py:require_worktree_fresh`（ahead 门禁）

- **背景**：规则 27 并行硬规则写「分支 ahead>10 必须先回合或 rebase，否则 `round_claim.py next` 拒绝领号」，此前无机械约束。
- **实现**：`require_worktree_fresh(root, limit=10)` 计算当前分支相对 master/main 的 `ahead`（`git rev-list --count main..branch`），超过 10 抛 `RuntimeError` 拒绝领号；master/main 自身不触发（其 ahead 表示未推送，属 push 门禁管辖）；主干缺失或无法计算时放行，由既有 `require_branch` 兜底。
- **接线**：`main()` 的 `next` 分支在 `require_branch` + `require_master_not_dirty` 之后新增 `require_worktree_fresh(Path.cwd())`。

### 新增规则 34a（AGENTS.md）

- **内容**：主工作区只做「同步 → 合并 → 提交」三动作；功能工作树开发；开工顺序 ① `dev.py sync` ② `git worktree add -b codex/<任务>` ③ 树内开发 ④ `git rebase master` 后回合；靠「保持主工作区干净」维持，脏树时 `sync` 与 `round_claim.py next` 都拒绝。

## 测试

- 新增 `tests/test_sync_master.py`：真实临时 Git 仓库验证「非主工作区拒绝 / 错误分支拒绝 / 脏树拒绝 / 已最新 / fetch 失败传播」5 条（动态 import 脚本，mock 掉 `git()` 的 fetch 分支）。
- 新增 `tests/test_round_claim.py` 两条：`test_ahead_over_limit_refuses_next_without_allocating`（11 提交 > 10 拒绝且不分配轮次号）、`test_ahead_within_limit_allows_next`（1 提交放行）。

## 架构门禁 2 红归因（非本轮回归）

功能工作树 `codex/wip-R2428` 由 `git worktree add` 从 master（841398a4 = R2427）创建，跑架构门禁 416 条有 2 红，逐条归因：

1. `tests/architecture/test_agents_md.py::test_performance_history_is_declared_as_historical_only`——依赖 `程序/维护记录/基准历史.json`，该文件被 `.gitignore:59` 忽略（`check-ignore` 命中），git 跟踪不到、`git worktree add` 不会把它带进新工作树；主工作区磁盘上该文件存在。这是**既有缺陷**（架构测试依赖 gitignored 文件），非本轮改动。
2. `tests/architecture/test_skill_reference_injection.py::test_script_stages_name_only_their_approved_00_references`——依赖 `程序/skills/00全流程SKILL/AIGC创作全流程/.../screenplay-gate-engine.md`，而 `AIGC创作全流程` 在 git 里是 **gitlink（mode 160000）**（指向 `1a43ae5a`），`.gitmodules` 文件丢失（`git submodule status` 报 "no submodule mapping found ... HoLLMwood"），`git worktree add` 不会 checkout gitlink 内容；主工作区磁盘上有该目录内容。同样是**既有环境问题**，非本轮改动。

两条均为主工作区「有物理文件、但 git 跟踪元数据不完整」导致功能工作树 checkout 缺失，与本轮 `scripts/` + `维护记录/` 改动无关。

## 决策依据（保留，供追溯）

- `scripts/` 目录不在 `run_selftests.py` 的 `NON_SOURCE_DIRS`（`tests/ tasks_round/ 维护记录/ 说明/ logs/`），故 `sync_master.py`、`dev.py` 改动计源码轮；`维护记录/基准脚本/round_claim.py` 在豁免目录不计源码。
- 新增 `sync_master.py` 与既有 `master_skill.py` 的 `sync_master_skill`（总控 SKILL 同步）命名不同、职责不同（git 同步 vs SKILL 同步），无冲突；`round_claim.py` 只新增函数，不改既有 `claim_next`/`claim_task` 等签名。
- 架构门禁 2 红属功能工作树环境限制，不扩大本轮范围去修（涉及 `.gitmodules`/gitlink 元数据修复与 gitignored 文件治理，属范围外），已在结果文件如实记录。

## 已提交

- 待提交（见收尾动作）。
