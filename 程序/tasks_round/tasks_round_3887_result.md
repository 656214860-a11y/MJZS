# R3887 结果：G-1 阻塞支吸收率与车道存活证据（只读诊断·续 R3855）
<!-- round-evidence: {"commit_base": "46a419f4", "credential_hits": 0, "evidence_sha256": "3bee816d42ea8846", "exit": 0, "failed": 0, "passed": 0, "round": 3887, "tests": "docs-only"} -->

## 三问

- 轮型：§3.5 只读诊断轮（续 R3855 处置矩阵）。只新增结果文件。
- 测试：不跑（只读诊断；全部为 `git` 只读命令与车道租约表查询）。
- 欠账：无代码改动；补 R3855 未覆盖的两个裁决维度。

## 新证据（master = `65ba4a86`）

### 1. 吸收率：各支线相对 `foundation-next` 的已收录份额

口径：`mb=merge-base(next, b)`；本线改动 = `diff --name-only mb b`；已吸收 = 本线改动文件中 branch-tip 与 next-tip 内容一致的数量。

| 分支 | 本线改动 | 与 next 仍不同 | 已吸收 | 吸收率 |
| --- | --- | --- | --- | --- |
| `round2-history` | 139 | 27 | 112 | 81% |
| `round3-history` | 154 | 29 | 125 | 81% |
| `pre-sync-squash` | 196 | 39 | 157 | 80% |
| `ffmpeg-runtime` | 5 | 1 | 4 | 80% |
| `round4-history` | 168 | 35 | 133 | 79% |
| `round5-history` | 180 | 38 | 142 | 79% |
| `asset-disk` | 63 | 16 | 47 | 75% |
| `api-disk` | 64 | 17 | 47 | 73% |
| `rebase-preview` | 48 | 14 | 34 | 71% |
| `image-disk` | 70 | 21 | 49 | 70% |
| `context-preflight` | 30 | 10 | 20 | 67% |
| `hardening` | 89 | 29 | 60 | 67% |
| `resume-history` | 92 | 30 | 62 | 67% |
| `context-policy` | 11 | 7 | 4 | 36% |

`resume` 已确认祖先链整支含于 `next`（R3855），不列此表。

### 2. 分歧面结构

14 支与 `next` 的逐文件差异频次分布：**561 文件在全部 14 支上都与 next 不同**（即 next 自身推进量，非各支独有工作）；73 文件在 13 支上不同；**仅 64 文件在 ≤4 支上不同**——各支真正的「未并入独有尾巴」集中在这 64 个文件上。

### 3. 车道存活（`round_claim.py lanes` 租约表）

- **活跃（last_seen ≤11h）**：`foundation-integration-final`（idle 6.8h）及其子车道 `alias-edges`/`content-edge`/`white-edges`（5.5–5.9h）；`dsh-68d604fa-4983` 下 `c6-catalog`/`c6-extension`/`c6-owner`/`c6-pages`/`c6-skill-pages`/`dpi-watch`/`update-admission`（6.9–10.8h）；merge 角色车道（8.8h）。
- **停滞（idle 36–43h）**：全部 G-1 命中分支的登记工作树（api-disk 39.9h、context-policy 40h、ffmpeg-runtime 42.9h、image-disk 36.5h 等）。

## 解读

- G-1 阻塞分支的开发工作树已全部停滞 ≥36h，而 `foundation-integration-final` 整合车道及其 edges/c6 子车道仍在近 11h 内活跃——**归并机制已在运转**，16 支大概率是被整合队列而非活跃开发线。
- 各支线 67–81% 文件级内容已被 `next` 吸收；独有尾巴集中在 64 个文件、按支 1–39 个不等。裁决时可按「仍不同文件数」排序处理：先小的（`ffmpeg-runtime` 1、`context-policy` 7、`context-preflight` 10、`rebase-preview`/`round2-history`/`round3-history`/`hardening`/`resume-history`/`asset-disk`/`api-disk`/`image-disk`/`round4-history` 14–35）再大的（`round5-history` 38、`pre-sync-squash` 39）。
- 注意口径：「已吸收」指文件级内容一致，不等于提交被合入；「仍不同」含 next 后续推进造成的差异，需逐文件判新旧。

## 结论

- 维持 R3855 结论：无空冗余分支；但整合车道活跃证据支持「等待归并」是现实路径。
- 最小用户动作不变：地基车道完成 `foundation-next` 合入并对 14 支逐支裁决；本轮给出处理顺序建议（按仍不同文件数升序）。
- L0 车道 K1–K18 继续 `[TASK_BLOCKED]` 于 G-1。

## 验证

- 全部结论由 git 只读命令与车道租约表实测；三个基线均未运行（只读诊断）。

## 勘误（同车道 R3879/R3884 更新数据）

- 本文件提交后，同车道 R3879/R3884 复核显示：G-1 命中分支已 16→**22**（新增 C6 分解 `c6-catalog`/`c6-extension`/`c6-owner`/`c6-pages`/`c6-skill-pages` 与 `update-admission`，均 4 文件全中）。
- 「resume 祖先链整支含入 next」已被 supersede：`resume` 经移动后 **⊄ next、⊂ `update-admission`**（载体变更）；`next` 合入预计仅自动消化 `c6-pages`。
- 吸收率表对原 14 支仍有效（以 `next` 为参照系）；新增 6 支未测。

## 提交

- （提交后回填）
