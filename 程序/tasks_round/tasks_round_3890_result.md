# R3890 结果：G-1 整合载体实况与契约增量诊断（只读诊断·续 R3887）
<!-- round-evidence: {"commit_base": "668823ab", "credential_hits": 0, "evidence_sha256": "1b0de69bb90cae4e", "exit": 0, "failed": 0, "passed": 0, "round": 3890, "tests": "docs-only"} -->

## 三问

- 轮型：§3.5 只读诊断轮（续 R3887 吸收率诊断）。只新增结果文件，不改任务书与任何 `.py`。
- 测试：不跑（全部为 `git`/`status` 只读命令；只读诊断轮默认不跑测试）。
- 欠账：无代码改动；补 R3887 未覆盖的「合并载具」维度——归并车道的工作树实况与 G-1 文件终版内容。

## 新证据（master = `5110b1ab`，测量时点 2026-11-20 08:1x）

### 1. 整合载具结构（`git worktree list`＋分支 tip 实测）

| 载具 | 分支 tip | 工作树实况 | 判断 |
| --- | --- | --- | --- |
| `codex/foundation-next` | `f0cac615`（R3867，ahead-master 16） | `dsh-68d604fa-4983`，仅 tmp 残留、树净 | 活跃整合干线；C6 五支＋`update-admission`＋`dpi-watch` 为其嵌套工作树 |
| `codex/foundation-integration-final` | `f583e096`（checkpoint，ahead-master **0**） | **288 项已暂存**（166 A＋122 M）＋2 未跟踪 | 归并装配进行中、**尚未落为任何提交** |
| `foundation-alias-edges` / `content-edge` / `white-edges` | 同上 checkpoint | 各 7–8 个未暂存修改 | 边角集成刚起步，均未提交 |
| G-1 命中 22 支其余各支 | 同 R3884 | reflog 最新仍 `c6-extension` 02:39 | 命中支集体静默约 5.5h |

要点：`integration-final` 分支 tip 停在 checkpoint 不代表无工作——**其工作树已装配 288 项变更**，R3887「归并机制已在运转」获工作树级证据证实；但截至本轮测量，归并尚未产生任何提交，22 支命中分支无一被合入或放弃。

### 2. `integration-final` 暂存区的 G-1 文件终版

`git -C <工作树> diff --cached --name-only <参照> -- <4 文件>`：

- 对 `foundation-next`：仅 `platform_tools.py` 不同——`service_contract.py`、`workflow_context_budget.py`、`test_dependency_whitelist.py` 三个文件暂存内容与 next tip **逐字节全同**；`platform_tools.py` 在 next 之上另有 **+38/−27** 改动（新增 `ExecutionControl.wait_for_retry`、精简注释/docstring 等）。
- 对 master/HEAD：4 文件全部不同（即终版相对 master 的净增量已在暂存区成形）。

### 3. 契约增量量化（master `5110b1ab` → `foundation-next` tip，`git diff --stat`）

| G-1 文件 | next 相对 master |
| --- | --- |
| `contract/platform_tools.py` | 30+/41−（净缩，重构） |
| `contract/service_contract.py` | +11 |
| `contract/workflow_context_budget.py` | +136/−34（大幅扩展） |
| `tests/architecture/test_dependency_whitelist.py` | +41/−6 |

### 4. 并发现场

- 主工作区 `codex/acceptance-final-record`（R3854，tip `b3f19c0b`）合并自 07:53 开启、无冲突（`diff-filter=U` 空），截至本轮仍在进行（约 20 分钟），master 未动。
- 同车道另一会话 07:55 落 R3887（吸收率诊断＋勘误），本轮为其后续、不重复其口径。

## 解读

- **G-1 翻转路径更具体**：`integration-final` 正在装配一个含全部 4 个 G-1 文件终版的单一大合并（暂存区 3/4 文件已是 next 终版、`platform_tools.py` 另有增量）。但须分清两层：288 项暂存 ≠ 22 支被处置——门语义仍要求每支「合入 master 或明确放弃」；且 `integration-final` 提交后其自身 diff 亦命中 4 文件，**将成为新的 G-1 命中分支**，直至被合入。
- 对 K 轮的含义不变且更清晰：K1（改 `test_dependency_whitelist`）、K10（`service_contract`）、K11（`platform_tools`）的目标文件终版已在 integration-final 暂存区成形——G-1 翻转时这四个文件将一次性大改，K 轮开工前必须以届时 master 为准重测，不能按现状预写。
- `edges` 三支仅 7–8 个未暂存文件、`next` 工作树干净——归并重心在 integration-final 单车。

## 结论

- 维持阻塞结论：G-1 命中 22 支不变、无一合入或放弃；K1–K23 全部继续 `[TASK_BLOCKED]`。
- 新增可操作情报：盯 `foundation-integration-final` 工作树的首次提交为最近的翻转前兆；其提交后应立即复测 G-1（命中集可能先增后减）。
- 本车道不代做他人车道合并、不动他人工作树。

## 验证

- 全部结论由 `git worktree list`、`git status`（含他人工作树只读查询）、`git diff --cached --name-only/--stat`、`git rev-list --count` 实测；未运行测试（只读诊断）。

## 提交

- 分支 `codex/l0-constitution`；docs-only 诊断轮，`dev.py commit` 自动生成 `evidence/R3890.json` 并回填本文件机器头；提交号与 hash 见提交记录。
