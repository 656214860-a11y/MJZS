# R3931 结果：放弃仍命中的地基分支

## 1. 三问

- 轮次类型：状态接续轮。用户授权后，把仍命中 G-1 或 G-B 的 `codex/foundation-*` 改名为 `archive/foundation-*`。没有合入这些分支，没有改它们的文件。
- 测试跑了吗、三个基线过了吗：未跑冒烟、架构门禁和全量。核对是改名后的 `git diff --name-only master...codex/foundation-*`。最新绿全量仍是 R3849。
- 欠账少了吗：G-1 与 G-B 的命中数都是 0。`codex/foundation-*` 还剩 15 支，三点 diff 不再碰到点名文件。K1 仍有未勾选的前置 KR、K0，本轮没有开工。

## 2. 改名

提交 SHA 不变。已检出的工作树跟着新分支名，未提交文件留在原处。`archive/foundation-integration-final` 的未提交覆盖率基线没有暂存、没有删除。

| 原分支 | 新分支 | SHA |
| --- | --- | --- |
| `codex/foundation-api-disk` | `archive/foundation-api-disk` | `6fc482dd` |
| `codex/foundation-asset-disk` | `archive/foundation-asset-disk` | `1ada4b15` |
| `codex/foundation-c6-catalog` | `archive/foundation-c6-catalog` | `b5c30b86` |
| `codex/foundation-c6-extension` | `archive/foundation-c6-extension` | `9f098c3d` |
| `codex/foundation-c6-owner` | `archive/foundation-c6-owner` | `850eef6d` |
| `codex/foundation-c6-pages` | `archive/foundation-c6-pages` | `46d0e6a1` |
| `codex/foundation-c6-skill-pages` | `archive/foundation-c6-skill-pages` | `4b29b2bc` |
| `codex/foundation-c8-updater` | `archive/foundation-c8-updater` | `d5cf6705` |
| `codex/foundation-config-project-profile` | `archive/foundation-config-project-profile` | `edcd3c20` |
| `codex/foundation-context-preflight` | `archive/foundation-context-preflight` | `ead2999d` |
| `codex/foundation-hardening` | `archive/foundation-hardening` | `b6ed0cf6` |
| `codex/foundation-image-disk` | `archive/foundation-image-disk` | `2c4a2035` |
| `codex/foundation-integration-final` | `archive/foundation-integration-final` | `d5fb72fd` |
| `codex/foundation-next` | `archive/foundation-next` | `f0cac615` |
| `codex/foundation-rebase-preview` | `archive/foundation-rebase-preview` | `f0468747` |
| `codex/foundation-resume` | `archive/foundation-resume` | `3aee0256` |
| `codex/foundation-update-admission` | `archive/foundation-update-admission` | `9d483cf1` |

`context-preflight` 和 `config-project-profile` 在已合入提交之上只多了标为 FAIL 的提交，所以没有合入。迁回某一支：`git branch -m archive/foundation-<后缀> codex/foundation-<后缀>`。

## 3. 重测

改名后 `codex/foundation-*` 对 G-1 四文件和 G-B 四文件的命中数为 0。已合入的 `ffmpeg-runtime`、`context-policy`、`config-write-safety` 仍用原名。
