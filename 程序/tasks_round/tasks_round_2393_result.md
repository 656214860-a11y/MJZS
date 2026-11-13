# R2393 修复轮结果（阻塞修复）

## §7 三问

1. **本轮类型**：修复轮（§3.2）——修复 `distribution_manifest.md` 漏声明导致的 `test_distribution_selfcheck` 红（后台全量失败原因）。
2. **测试跑了吗、三个基线过了吗**：
   - 定向（先红后绿）：`run_selftests.py -k test_distribution_selfcheck --serial` 3 条。还原 manifest 后 2 条红（「还有 3387 个文件不在清单里」，前几个 `.agents/worktrees/`、`.tools/.tools/yt_dlp-*.whl` 等）；恢复改动后 3/3 全绿，`distribution_build.plan(ROOT)['undecided']` 数量 0。
   - 默认冒烟：`smoke_test.py`（经 `工作流任务/gui_hidden.py`）8/8 通过。
   - 全量：未跑（只改清单文档，非源码轮；且改动正是消除后台全量失败的根因）。
3. **project_status.md 的欠账少了吗**：修复了后台全量（`auto_full_safe`）自 R2365 起因 `test_distribution_selfcheck` 红而失败的阻塞项；全量欠账不再因本项被卡。

## 根因与修复

- **根因**：开发目录里新增了本机产物/第三方工具/备份目录（`.agents/**`、`.tools/**`、`工作流任务/**`、`运行环境/Python_alpha_a2_backup/**`、`运行环境/Python315_pruned_backup/**`、`程序/Tencent/**`、`漫剧制作助手_图标_*.ico`、`漫剧助手.lnk` 等），未在 `distribution_manifest.md` 声明保留或排除，导致 `distribution_build.plan` 报 3387 个 undecided 文件、`test_manifest_covers_every_file` 红。
- **修复**：在 `distribution_manifest.md` 的「排除」区补上这些路径的排除声明；并把「保留」区里 `漫剧制作助手.ico` 的描述明确为「根目录唯一正式图标为 git 跟踪的 `漫剧制作助手.ico`」（其余 `漫剧制作助手_图标_*.ico` 均为本机产物）。
- **最小改动**：只改 `distribution_manifest.md` 一处，未动 `distribution_build`/`distribution_selfcheck` 逻辑。

## 测试资产

- 未新增/修改测试（`test_distribution_selfcheck` 既有 3 条即锚定本契约，本轮只补清单数据使其转绿）。断言未动。

## 提交

- 已提交：是（`codex/wip-R2393` 分支，提交信息 `R2393: 补 distribution_manifest 排除声明修复分发自检红（修复轮）`）。
- commit hash：以 git log 为准（结果文件随提交 amend，避免 hash 自指）。
