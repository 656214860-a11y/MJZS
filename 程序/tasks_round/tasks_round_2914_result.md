# R2914 结果：T1 远端 CI 收口（post-receive 门禁＋bundle 校验＋夜间全量）
<!-- round-evidence: {"commit_base": "e26bddaf", "credential_hits": 0, "evidence_sha256": "5f02cb02adb89b07", "exit": 0, "failed": 0, "passed": 0, "round": 2914, "tests": "docs-only"} -->

## 三问

1. **轮次类型**：功能轮（T1 任务书收口；新增运维脚本与测试，不改产品逻辑）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；定向 `backup_verify` 9 条＋`remote_post_receive_ci` 16 条全绿（证据 `evidence/R2914.json`）；架构门禁本地 470 条中 2 条环境性红（干净工作树缺 gitignore 的 `基准历史.json` 与 gitlink 技能包内容），补齐本地输入后复跑 24/24 绿，与本轮改动无关；未跑全量（脚本不触达运行期逻辑，合入轮按门禁决定）。
3. **欠账少了吗**：是。T1 剩余项从「post-receive CI＋backup_verify＋夜间全量＋覆盖差异文档」四件缺口收口为已部署已验证；T1 唯一遗留是首次 `git push backup master` 的 8 个缺证据历史提交处置，仍待用户决定（见下）。

## 本轮交付

| 文件 | 内容 |
|---|---|
| `程序/scripts/backup_verify.py` | T1 第 6 项校验脚本：对 bundle 目录逐个 `git bundle verify`（自动以同级 `manju-assistant.git` 作仓库上下文——verify 必须在仓库内跑，已在服务器实测两份 bundle 全 OK），汇总份数/最新/超保留上限提示，坏包退出码 1。 |
| `程序/tests/test_backup_verify.py` | 9 条：真实 bundle 构造验证、坏包、git 缺失、目录缺失/空、环境变量、`guess_repo` 同级 bare 识别。 |
| `程序/维护记录/基准脚本/remote_post_receive_ci.py` | T1 第 2/3/5 项：post-receive 远端 CI。stdin 同 pre-receive；只对 `master`/`main`/`codex/*` 触发；`--shared` 克隆＋`checkout -f`（必须含 `.git`，gitlink 检测与 move guard 需要）；按 `维护记录/外部技能包哈希.json` 把 3 个登记技能包从 GitHub 克隆到固定提交（缓存 `/srv/git/ci/pkg-cache/`）；补 `基准历史.json=[]`；跑静态门禁 8 模块＋架构门禁全模块（平台边界用例按显式清单排除）；`GIT_*` 环境变量清洗（否则 hook 的 GIT_DIR 让用例内临时仓库误操作 bare 仓库——实测 10 条 move guard 全红的根因）；flock 串行；结果写 `/srv/git/ci/results/`。 |
| `程序/tests/test_remote_post_receive_ci.py` | 16 条：ref 过滤、slug、`GIT_*` 清洗、克隆检出（真实临时仓库）、登记表缺失/历史回填、排除清单目标枚举、run_step 日志/超时、run_ci 绿/红/检出失败、main 触发过滤。 |
| `程序/维护记录/基准脚本/install_nightly_task.cmd` | T1 第 4 项：注册/卸载 `ManjuNightlyFullSafe` 计划任务（每日 03:30 对 `.wt/ci` 跑 `auto_full_safe.py --run`，自定位仓库根）。 |
| `程序/runbook.md` | §5 增「远端备份与服务器 CI（T1）」：三件套部署位置、覆盖差异口径、夜间全量说明。 |

## 平台边界排除清单（脚本内显式登记，非静默放行）

| 排除项 | 理由 |
|---|---|
| `test_rule_guard_map`（整模块 7 条） | setUp 经 `file_cache.read_json` → `agent/publication.access()` 的 msvcrt 字节锁仅支持 Windows（产品只跑 Windows，非缺陷）。 |
| `test_skill_package_pins`（整模块 3 条） | `PINS.load_registry` 走同一 file_cache 公共读路径，同上。 |
| `test_source_text_contracts.DesktopSourceContracts`（6 条） | 每条 `import desktop` → 模块级 `import tkinter`；服务器 python3 无 tkinter，属「依赖 Tk」口径外；同模块 `SelftestRunnerContracts` 保留。 |
| `test_service_return_contract` 2 条 | 走 file_cache 公共读路径，同 publication 锁。 |
| `test_unification_ratchet.test_bare_json_load_debt…`（1 条） | 台账锚点 `sha256(ast.dump(Call))` 随解释器版本变；基线在随附 3.15 生成，服务器 3.11 全部锚点失配（已实测同一节点 digest 不同）。 |

排除条目按 unittest 目标写死；用例改名后旧条目失效、该用例会重新跑并如实报红。

## 服务器部署与验证（全部经 ssh/scp 8.138.223.126＝`backup` 远端）

- **test-ci.git 沙箱**（`/srv/git/ci/test-ci.git`，验证后保留作演练仓）：装 `hooks/post-receive`。
- **红**：首轮推送 `codex/ci-smoke`（fc030a68）→ FAIL，32 项红——逐项归因：GIT_DIR 泄漏 10、无 `.git` 3、gitlink 内容缺 2、tkinter 6、publication 锁 9、解释器版本 1、gitignore 输入 1。第二轮 `codex/ci-smoke2`（7f3d2953）→ 仅剩 skill_package_pins 3 条（file_cache 锁），补排除清单后。
- **绿**：第三轮 `codex/ci-smoke3`（e99d21a5＝当时 master）→ **PASS**：静态门禁 39.9s＋架构门禁 302.0s，**448 条用例全绿**（470−22 条平台边界排除），状态 `codex-ci-smoke3.status.json` ok=true，日志 `/srv/git/ci/results/20261115T215830Z-codex-ci-smoke3.log`。
- **bundle 校验**：`python3 /tmp/backup_verify.py /srv/git/backups` → `manju-2026-11-15/16.bundle` 均 OK（14–15MB）；已同步参照副本 `/srv/git/ci/remote_post_receive_ci.py`（LF 化）。
- **夜间全量**：`schtasks /create /tn ManjuNightlyFullSafe /sc daily /st 03:30` 已注册（下次运行 2026-11-17 03:30，交互模式），指向主工作区 `程序/scripts/auto_full_safe.py --run`。

## 覆盖差异（T1 文档要求，已写入 runbook §5）

Linux 远端只覆盖「静态门禁＋架构门禁（去平台边界用例）」；默认冒烟（Tk）、增量门禁、`run_selftests.py --all --safe` 与定向复跑仍在 Windows 本机（`local_ci.py exit`／auto_full_safe 凭据）。服务器 python3.11 与本机随附 3.15 有版本差，远端绿不等于本机绿——合入 master 仍以本机 CI 出口为准。

## 遗留与边界

- **首次 `git push backup master` 仍被 pre-receive 证据门禁拒**：待推区间含 8 个缺 `evidence/R<n>.json` 的历史提交（R2679/R2650/R2656/R2633/R2627/R2622/R2596/R2531），处置选项①临时摘钩推送后装回（脚本既定逃生口）②用户另行决定——**待用户拍板**，本轮未执行任何对 backup 的 push。
- post-receive 装到真 bare 仓库 `manju-assistant.git/hooks/` 的动作在第三轮沙箱转绿后执行（命令已在本文件备案：`cp /srv/git/ci/remote_post_receive_ci.py <bare>.git/hooks/post-receive && chmod +x`）。**已执行**：沙箱三轮验证（红→收敛→绿）后部署至真仓，部署后 `ls hooks/` 与参照副本 md5 一致。
- T9 归档（tasks_round 2100+ 结果文件）与 T10 批次 3–7（infra/domain/orchestrator/ui 迁移）不在本轮范围。
- 观察项：`test_script_structure_natural_edit` 间歇时序红（前轮记录）、first_day 基准趋势告警级噪声。
