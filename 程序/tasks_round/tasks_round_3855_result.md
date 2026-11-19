# R3855 结果：G-1 阻塞分支处置矩阵（只读诊断）
<!-- round-evidence: {"commit_base": "fc515607", "credential_hits": 0, "evidence_sha256": "3d1adc07b0523d12", "exit": 0, "failed": 0, "passed": 0, "round": 3855, "tests": "docs-only"} -->

## 三问

- 轮型：§3.5 只读诊断轮。只新增结果文件；不改 `.py`、不改任务书正文。
- 测试：不跑（只读诊断按 §5 默认不跑；核对命令均为 `git` 只读操作）。
- 欠账：无代码改动；产出 G-1 阻塞分支的处置证据供裁决。

## 目的

K1–K18 全部阻塞于 G-1（16 支 `codex/foundation-*` 命中 4 个点名文件）。解除条件是「合入 master 或明确放弃」——属地基车道裁决，本车道不代做（§3.4）。本轮给出机械可证的处置矩阵，把「16 支」分解成可分批裁决的结构。

## 证据与命令（master = `65ba4a86`）

判定口径：`A` = `git merge-base --is-ancestor`；`C` = `git cherry` 补丁等价；`D4` = 与 `foundation-next` 在 4 个 G-1 文件上的 `git diff --name-only` 差异数；冲突面 = `git merge-tree --write-tree master <branch>`。

| 类别 | 分支 | 关键证据 | 处置参考 |
| --- | --- | --- | --- |
| 活跃集成线 | `foundation-next`（ahead 13，tip R3805） | `foundation-resume` 是其祖先；merge-tree 与 master 冲突 8 文件 | 地基主合入载体；冲突面有限（4 基线 JSON＋architecture/runbook/project_status 文档＋`domain/writing_stream.py` 一个源文件） |
| 已被包含 | `foundation-resume`（ahead 11，tip R3703） | **祖先链：`resume` ⊂ `next`**（A 判定通过） | next 合入后 resume 成果随之落地，可随即关闭 |
| 历史快照线（5 支互独立） | `resume-history`(20)、`round2-history`(12)、`round3-history`(13)、`round4-history`(14)、`round5-history`(14) | 互不包含；各自 11–18 个独有提交，C 判定无任何补丁等价被 next 收录；与 next 的 D4=2–3 | 非冗余副本——各自携带独有版本的 G-1 文件；需逐支裁决保留价值后明确放弃 |
| 功能支线（6 支） | `api-disk`(17)、`asset-disk`(17)、`image-disk`(18)、`hardening`(19)、`context-policy`(1)、`context-preflight`(2)、`ffmpeg-runtime`(1) | C 判定独有提交 1–19 不等价于 next；D4=3–4；部分 tip 为 `-FAIL` 检查点 | 真实在途或停滞工作；按分支逐支裁决合入/放弃 |
| 同步/预览支线 | `pre-sync-squash`(16)、`rebase-preview`(15) | 独有提交 10/15，D4=2/3 | 工具型支线，裁决成本最低 |

注：`config-project-profile`、`config-write-safety` 命中 `infra/project_settings.py`——属 L1 车道 G-B 文件集，不计入本门 G-1。

## 结论

- 16 支里 **无空冗余分支**：除 `resume` 被 `next` 祖先链包含外，其余 14 支对 4 个 G-1 文件均携带独有改动（D4≥2），不能用「内容已在 next」为由批量关闭。
- 合入路径最短的是 `foundation-next`：与 master 仅 8 文件冲突且多为基线/文档类；但它合入只解掉 `next`＋`resume` 两支，**剩 14 支仍需逐支裁决**。
- G-1 解除的现实路径：地基车道完成 `foundation-next` 合入 → 对其余 14 支逐支判「尚有价值的拆分续做、无价值的明确放弃」。本矩阵可作裁决底稿。
- 本车道继续 `[TASK_BLOCKED]` 于 G-1；K1–K18 无可执行项，与 R3804 结论一致。

## 验证

- 全部结论由上述 git 只读命令实测，无测试可跑。
- 三个基线：冒烟／架构／全量均未运行（只读诊断）。

## 提交

- （提交后回填）
