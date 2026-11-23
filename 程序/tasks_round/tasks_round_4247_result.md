# R4247 结果：RESIDUE-CLEAN-A1A2 历史残留对账（.gitignore 补两条 .agents 规则 + hooks bak 对账留待删清单）
<!-- round-evidence: {"commit_base": "cb33bcfe", "credential_hits": 0, "evidence_sha256": "b8d037ec16d5ac0f", "exit": 0, "failed": 0, "passed": 0, "round": 4247, "tests": "docs-only"} -->

## 开头三问

- 本轮属于哪种类型：结构治理轮／配置与只读对账轮（`历史残留清理任务书.md` §二「清理轮 A」的 A1+A2；任务卡 RESIDUE-CLEAN-A1A2，波次 W2，车道 `codex/residue-clean-a1a2`，基准 `cb33bcfe`）。
- 测试跑了吗、三个基线：本卡是配置与只读对账，非产品缺陷修复，卡面明确不要求先红后绿、不写测试；按卡面跑了默认冒烟 `smoke_test.py`，退出码 0，通过 9 项、失败 0 项（卡面写「8/8」，本机实测冒烟第 10 轮共 9 项，按实测记录）；架构门禁与全量回归卡面未要求，未跑，写「未运行」。
- 欠账少了吗：少一条——`.agents/` 本机会话噪音此前无 `.gitignore` 覆盖（任务书 §一 A 表实测「无覆盖，故被跟踪」），本轮补上忽略规则与例外；hooks `.bak` 按红线只对账不删除，待删清单已列出等用户确认，不算新增欠账。

## A1：`.agents` 跟踪现状与 `.gitignore` 补丁

- 治理变更集合入实况（编码席提供的 ancestry 证据）：命令 `git merge-base --is-ancestor 81140ca1 master`，编码席报告退出码 0（R3934 治理变更集已合入 master，其余 77 个 `.agents` 跟踪文件已取消跟踪）。按卡面协议本席**未复跑**该命令，留验收席独立复核；本席此处标注「未核实」。
- 本席复跑 `git ls-files .agents`（仓库根执行，退出码 0），输出仅一行：

  ```text
  .agents/skills/spec-context-review/SKILL.md
  ```

- 唯一保留依据：`程序/tests/test_root_layout.py:14` 将 `.agents` 登记为「仓库级项目开发技能（spec-context-review；说明见 开发者工具/AI开发流程/README.md）」；R4025 纳入版本管理、R4078 补根目录登记。该文件不得取消跟踪，故 `.gitignore` 用例外规则保住 `skills/` 目录。
- `.gitignore` 末尾恰新增两行（第 107–108 行），现有第 1–106 行逐字未动：

  ```gitignore
  /.agents/*
  !/.agents/skills/
  ```

- 效果：`git status --porcelain -- .agents` 无输出（退出码 0）——`.agents/` 下的本机会话与工作树噪音不再入暂存视野，已跟踪的技能文件不受忽略规则影响。

## A2：hooks `pre-commit.bak_20261004_0433` 只读对账

- `git rev-parse --git-common-dir`（仓库根执行，退出码 0）返回 `D:/漫剧制作助手/.git`；以下两文件都在该目录 `hooks/` 下，为所有 worktree 共享。
- 对账命令（退出码 1，属正常差异信号，非失败）：

  ```text
  git diff --no-index -- D:/漫剧制作助手/.git/hooks/pre-commit D:/漫剧制作助手/.git/hooks/pre-commit.bak_20261004_0433
  ```

- diff 摘要（方向 a=现行 `pre-commit` → b=`pre-commit.bak_20261004_0433`；`+` 表示 bak 有而现行无，`-` 表示现行有而 bak 无）：
  - **bak 独有的有效行为**：在任何分支上无条件检查 `$common/full-safe-selftest.lock`，存在即拒绝提交。
  - **现行版对应实现（已吸收并收窄）**：同一验收锁保留，但只拦 `master`/`main`/游离 HEAD，并带注释「验收锁只拦 master/main 与游离 HEAD；工作分支随手提交不等锁」「超长全量不创建这把锁，只持有 full-safe-runner.lock」。
  - **现行版新增（bak 时代之后）**：规则 34a 的 case 块——非合并提交时禁止在 `master`/`main` 上直接提交 `程序/` 非白名单文件；G1 静态门禁——暂存 `程序/*.py` 时跑 `tests.test_static_names` 与 `tests.architecture.test_static_hygiene`，不过即拒绝。
- **判定：改动已吸收**。bak 相对现行版本没有任何独有有效改动；bak 中更宽的「全分支拦锁」行为是现行版有意收窄的结果（注释即依据）。该文件属 2026-10-04 钩子升级时留下的历史备份残留。
- **待删清单（只对账不删除，删除须另获用户确认）**：

  | 路径 | 说明 |
  |---|---|
  | `D:/漫剧制作助手/.git/hooks/pre-commit.bak_20261004_0433` | Git common-dir hooks 备份残留；该目录为所有 worktree 共享，删除影响全仓钩子目录，需用户确认后另行执行 |

## 命令与退出码

工作目录：未注明时为仓库根 `residue-clean-a1a2`；`PY` 指 `..\..\..\..\运行环境\Python\python.exe`，执行目录 `程序`。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git status --porcelain` | 0 | 无输出（开工核对） |
| `git log -1 --format=%h` | 0 | `cb33bcfe` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/residue-clean-a1a2` |
| `git ls-files .agents` | 0 | 仅 `.agents/skills/spec-context-review/SKILL.md` |
| `git rev-parse --git-common-dir` | 0 | `D:/漫剧制作助手/.git` |
| `git diff --no-index -- <common-dir>/hooks/pre-commit <common-dir>/hooks/pre-commit.bak_20261004_0433` | 1 | 有差异，摘要与判定见 A2 节（退出码 1 为正常差异信号） |
| `git diff --check` | 0 | 无输出 |
| `git diff --name-only` | 0 | `.gitignore`（任务书与结果文件写入前） |
| `git diff --numstat` | 0 | `2	0	.gitignore`（同上时点） |
| `git status --porcelain -- .agents` | 0 | 无输出 |
| `PY -B smoke_test.py` | 0 | 通过 9 项、失败 0 项，尾部原文见下 |
| `PY -B scripts\dev.py claim` | 0 | 领到轮次 4247 |

默认 smoke 输出尾部：

```text
==================================================
通过：9 项
失败：0 项
==================================================

✅ 冒烟测试通过，可以进入下一轮
```

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `.gitignore` | 末尾新增第 107–108 行 `/.agents/*`、`!/.agents/skills/`；既有规则未动；numstat `2 0 .gitignore` |
| `程序/tasks_round/历史残留清理任务书.md` | §二清理轮 A 勾选 A1、A2 并附执行证据；「完成记录」登记 R4247 |
| `程序/tasks_round/tasks_round_4247_result.md` | 本文件 |

`.agents/` 下文件未动、未取消跟踪；`hooks/` 下文件未删。

## 未覆盖项（未运行／未验证）

- `git merge-base --is-ancestor 81140ca1 master`：按卡面协议本席未执行，编码席报告退出码 0，待验收席独立复核；本席标记「未核实」。
- 冒烟项数口径：卡面预期「8/8」，本机实测为 9 项全过（第 10 轮）；按实测如实记录，差异供验收核对。
- 未跑 `smoke_test.py --architecture`、全量自测、定向 selftest：卡面未要求且本卡未改 `.py`（证据文件按 docs-only 口径由提交工具生成）。
- 未删除任何文件：`.agents/` 未动、hooks bak 未删、未执行 `git rm`、未取消跟踪；A2 待删清单仅列出。
- 未 push、未 merge、未改主工作区、未动 `程序/tasks_round/任务完成/` 与 `程序/project_status.md`。
- `程序/` 目录外 A2 验收命令 `ls "$(git rev-parse --git-common-dir)/hooks" | grep bak` 未按原样执行（卡面限定命令集），改以 `git diff --no-index` 对账为准。
