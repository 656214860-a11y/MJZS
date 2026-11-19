# R3749 结果：C 发布与回滚取证轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "f156999a", "credential_hits": 0, "evidence_sha256": "aa0d3eae66096b32", "exit": 0, "failed": 0, "passed": 27, "round": 3749, "tests": "run_selftests.py -k release distribution"} -->

- 轮次类型：任务书执行轮（C 维发布与回滚取证）。纯取证＋文档轮，无产品代码改动（新增取证脚本除外）。
- 是否跑测试：跑了。`distribution_build.py --build/--verify` 双制品全绿；`distribution_selfcheck.py` 通过；`scripts/acceptance_release_probe.py` 15/15 项检查通过（安装→打开→快照→失败升级检出→回滚→成功升级→新旧版本打开旧项目）；发布域单测由提交证据覆盖（--tests release distribution）。
- 积压是否下降：是——验收台账 C 项由「待验」转「通过」。

## 1. 三问

1. **什么类型轮**：任务书《桌面与云服务架构及全链路验收任务书》执行顺序第 5 步「C 发布与回滚」——同版安装制品在干净环境用旧项目副本执行安装、升级、打开项目、失败回滚，核对原产物摘要与版本兼容。
2. **是否跑测试**：跑了——双制品 verify ok、分发自检通过、探针 15/15。
3. **积压是否下降**：是——C 项证据链闭合；无新增欠账。

## 2. 取证方法（隔离、可复现、零新增产品依赖）

- 制品：`distribution_build.py --build` 按 `distribution_manifest.md` 构建——`dist_old` 取 master 基线 `86e863bb`（git worktree 检出，运行环境目录联接）、`dist_new` 取本分支 HEAD `f156999a`；两者 `--verify` 均 ok。
- 环境：worktree 同级 `_accept_c/`（不入库）；工作树补拷 `运行环境/`（gitignore 内）使制品含随附解释器；正式安装 `D:\漫剧制作助手` 与真实项目 `D:\漫剧下载` 全程零接触。
- 演练：`scripts/acceptance_release_probe.py`（本轮新增）——安装夹具、全量 sha256 清单、`engine.Studio` 打开项目、半量覆盖＋损坏模拟失败升级、快照整体回滚、成功升级覆盖、版本兼容核对；证据 `tasks_round/evidence/R3749/`。

## 3. 结果摘要（15/15，明细见 release_probe.json）

- **制品**：old=V0.7/`86e863bb`/R3705/4070 文件；new=V0.7/`f156999a`/R3739/4071 文件；verify 全项 ok。版本差异面 added=1 removed=0 changed=6（仅 R3709 两处产品修复＋文档）。
- **安装**：dist_old 落位 `install/`＋用户数据夹具（config/projects/desktop_settings/private×3/data 标记）＋旧项目副本（R3709 真实骨架 16 文件）。
- **打开（旧版）**：自带解释器 `engine.Studio` → EP001 OK；运行期仅增 `writer.lock`。
- **快照**：`snap_pre/` 4079 文件与拷贝前清单逐一致。
- **失败升级**：覆盖 2035/4072 文件中止＋删 `app.py`＋损坏 `desktop.py` → 摘要核对检出 mismatch=2、与快照差异=10。
- **回滚**：快照整体恢复 → 4079 文件哈希全等 → 打开项目 OK。
- **成功升级**：dist_new 全量覆盖 → 程序文件与新摘要 0 mismatch；用户数据与项目内容零改动（`config.json` 仅 `episode_dir`/`episode_file` 指针自愈写回，设计内）。
- **打开（新版）**：`engine.Studio` → EP001 OK，旧项目与新版兼容。
- **发布自检**：`distribution_selfcheck.py` 通过（临时副本＋摘要校验＋五入口模块导入）。

## 4. 阻塞与未测项（如实登记）

- 「打开项目」取证到 `engine.Studio` 服务层；完整 Tk 启动与界面操作验收归 E 轮。
- 升级为同机目录覆盖演练（对齐发布检查单「安装只覆盖程序文件、保留用户数据」语义）；无独立安装器可演练（仓库现状，`说明/发布检查单.md` 已载明）。
- 探针首轮两处自身判据缺陷已修正：快照比对改「拷贝前清单一致＋允许运行期新增」、失败升级补显性损坏（新旧制品仅差 7 文件，半量覆盖可能恰好盖住差异面）、项目核对允许 config.json 指针自愈。
- `_accept_c/` 实体演练目录（约 2GB）在 worktree 同级；证据 JSON 与清单已入 tasks_round，可随时清理。

## 5. 下一步（自动续跑）

- R6（D 恢复连续使用）：可丢弃项目强退/重启/已采用成果保全/待核实请求；异地备份恢复视 SSH 可用性复测。

## 6. 变更文件

- `程序/scripts/acceptance_release_probe.py`（新增：C 维取证探针）
- `程序/tasks_round/evidence/R3749/`（release_probe.json、version_diff.json、manifest_pre_install.json）
- `程序/tasks_round/桌面与云服务验收台账.md`（C 项状态与取证记录）
- `程序/tasks_round/tasks_round_3749_result.md`（本文件）

## 7. 提交

- 见文末 `round-evidence` 头与 git 提交回执（`commit_round.py` 自动生成 `evidence/R3749.json` 凭据并盖章本文件）。

---
*R3749 · 桌面与云服务架构及全链路验收任务书 · C 发布与回滚取证轮*
*下一动作：R6 开始 D 维恢复与连续使用*
*基线：双制品 verify ok、分发自检通过、探针 15/15；冒烟/架构/全量本轮不声明（纯取证轮，合入 master 前按 §5 补跑）*
*恢复：读本文件＋验收台账 §4＋`scripts/acceptance_release_probe.py --help`；证据在 `tasks_round/evidence/R3749/`；演练实体在 `_accept_c/`*
*注意：engine.Studio 写回 config.json 指针属设计内自愈；旧项目内容文件逐字节未变*
