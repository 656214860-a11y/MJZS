# R3279：残留 SKILL 治理轮 1（D2 内置层禁用）
<!-- round-evidence: {"commit_base": "056f882f", "credential_hits": 0, "evidence_sha256": "4f2f18d071e6205a", "exit": 0, "failed": 0, "passed": 52, "round": 3279, "tests": "run_selftests.py -k skill_lifecycle pet_skills_manage skill_project_layer"} -->

- 轮次类型：§3.2 修复轮；任务书轮 1，仅处理 D2。
- 测试与三个基线：先红后绿已验证；默认冒烟 8/8（不是任务书的 9 项）、受影响回归 632/632，124.8 秒、0 skip；架构门禁 532/532，228.150 秒、退出码 0。全量本轮未运行，后续轮 2 与最终合入前必须跑，不能用旧凭据冒充。
- 欠账：修复内置禁用及相关删除保护漏洞；D1、D3 与用户本人重装仍待后续轮次。

## 授权与边界

用户明确要求执行《残留SKILL治理任务书》全部轮次、每轮独立提交后开启子会话，测试通过后合入 master；需确认的事项授权执行者按最优选择判断。保留 L2-D18 内置删除禁止、L2-D21 总包不进入阶段注册表、L2-D22 用户本人操作重装等既定决策。

本轮基于 master `056f882f`，专用分支 `codex/skill-residue-governance`，工作树 `dsh-6187d0c7-f35d`。`dev.py claim --branch codex/skill-residue-governance` 实领 R3279（首次未设 PYTHONUTF8 因 Git 路径 GBK 解码失败，核验未写入后以 PYTHONUTF8=1 重试成功）。不冒领无关队列项。

## 诊断报告逐项复核与偏差

源任务书、R3276 报告已原样复制进当前树，保留其历史口径。以当前源码与行为为准：

1. D2 不止任务书列的两处预检。`orchestrator/skill_project_layer.py` 的 `set_disabled` 也拒绝 builtin；`disabled_pairs` 与 `disabled_view_entries` 同时排除 builtin。仅删两处预检无法实现持久化过滤及重新启用，故同轮修复直接被调模块，生产改动共三个模块。
2. 报告“测试未锁定拦截”不成立：现有 `test_builtin_layer_cannot_be_disabled`、`test_builtin_disable_is_refused` 明确锁定旧契约。按任务书 L2-D15 有意变更这两条预期，其他行为断言保持。
3. 新增删除保护测试实测发现：`uninstall_skill_entry` 在检查 builtin 之前把启用项交给通用卸载，原本仅对禁用项拦 builtin。将原有检查前移两行，保证两种状态都拒绝删除，未放开任何删除权限。
4. 任务书称默认冒烟 9/9，当前 `smoke_test.py` 实际列 8 项，报告按实际计数，不伪造第九项。

## 改动

- `ui/skill_lifecycle_service.py`：去除 builtin 禁用预检；把现有 builtin 删除保护移到启用／禁用分流之前。
- `pet_skills_manage.py`：去除 UI builtin 禁用预检，沿用确认弹窗与“文件保留、随时恢复”提示。
- `orchestrator/skill_project_layer.py`：三层均可登记禁用；全局 builtin 禁用进入注册表过滤与管理页禁用视图；项目隔离逻辑不变。
- `tests/test_skill_lifecycle.py`：验证禁用后 getAll 不含该项、文件字节不变、JSON 标记 builtin、新注册表仍禁用、重新启用恢复；验证启用／禁用状态都禁止删除。
- `tests/test_pet_skills_manage.py`：真实隐藏 Tk 验证 builtin 经确认禁用、灰显，并可重新启用。

## 先红后绿证据

改生产代码前执行（随附解释器、程序目录、PYTHONUTF8=1）：

```text
run_selftests.py -k skill_lifecycle pet_skills_manage
退出码 1
服务测试：ImportBlocked: 内置 SKILL 只读，不能禁用
UI 测试：test_builtin_disable_and_enable_are_available
AssertionError: None is not true
```

去除禁用拦截及底层三层支持后：

```text
run_selftests.py -k skill_lifecycle pet_skills_manage skill_project_layer
52 条，1 条红，其余通过
test_builtin_delete_remains_blocked_when_enabled_or_disabled
AssertionError: ImportBlocked not raised
```

定位后把原有删除检查前移。最终受影响回归 632 条、124.8 秒、0 红、0 skip，退出码 0；没有删除或弱化失败断言。

## 基线与验证

- `smoke_test.py --affected pet_skills_manage skill_lifecycle_service skill_project_layer skill_registry skill_import_service skill_package_meta`：通过（默认冒烟 8/8、隐藏桌面 probe 成功、直接消费者回归 632/632，124.8 秒、0 skip、退出码 0）。首跑 632 条中 4 文件失败：工作树缺已有 gitlink 的两个技能包导致注册数 71≠73，以及 PATH 未发现 FFmpeg；复用主树既有包副本（不复制 `.git`）及 FFmpeg PATH 后注册数恢复 73、FFmpeg 可用，复跑已全绿。复制时曾误放到 `程序/程序/skills`，核验只有本轮复制副本后已清除。未改主树内容或用户配置。
- 任务书的 `smoke_test.py --probe` 在当前脚本报“不认识的参数”；当前脚本本身自动执行 `scripts/gui_hidden.py --probe`，故使用支持的 `--affected` 完成同等 probe。该命令失败如实保留，不修改测试入口或跳过检查。
- 架构首跑 532 条、273.209 秒，失败集合为 2 fail＋1 error：状态页当前轮次 3278≠3280；AIGC 总包参考文件缺失；被忽略的 `维护记录/基准历史.json` 缺失。均为工作树接续／测试资源问题。已复制主树既有 AIGC 总包与历史基准副本（不写主树、不进暂存），状态页仅本地投影为 3280 供验证，提交前恢复，master 合并时正式同步。定向复验这三个失败来源的 11 条用例全绿（0.070 秒）。第二次完整架构 532 条、240.975 秒，剩 1 error（它在历史基准副本复制之前已执行该测试，最终汇总保留旧错误）；其余 531 条通过。资源补齐后第三次完整架构 532/532，228.150 秒、退出码 0；日志 `logs/r3279_architecture_final.txt`（运行日志不入库）。改前未单跑架构，不声称已有改前绿基线。
- 本轮未跑全量；common-dir `full-safe-receipts.json` 当前最后真实全量为 R3258，2026-11-18 01:53:50，tree `31bb237777256535d7001b6850b066cf370996f1`，942.765 秒；不代表当前树已验收。
- `git diff --check`：通过。

## 提交与接续

提交进行中；统一入口证据测试的非 GUI 37 条已通过，GUI 用例因另一工作树全量进程 PID 50900 持有跨树 GUI 令牌而排队（队列第 1 位），不绕过锁。提交完成后自动新建子会话执行轮 2。功能分支按 runbook §13 不提交 `project_status.md`，状态页轮次及 N=M+1 在 master 合并轮同步。

轮 4 明确由用户本人删除／重装；可先完成自动化与隔离 fixture 的同路径验证、提供操作清单，不得捏造用户操作已通过。全部任务未完成，不标记 TASK_COMPLETE。

### 下一子会话恢复要点

- 继续在当前树、当前功能分支上领新号，只执行任务书轮 2；轮 3 必须另起会话、另领号、另提交。
- 每个 PowerShell 测试／提交调用设置 `PYTHONUTF8=1`；使用 `D:\漫剧制作助手\运行环境\Python\python.exe -B`；工作目录为当前树 `程序`。
- FFmpeg 在 `D:\漫剧制作助手\运行环境\ffmpeg\bin`，需显式加入该调用 PATH；已有两个阶段子包、AIGC 总包与 `维护记录/基准历史.json` 副本仅用于填补新工作树缺失的资源，勿提交用户运行数据或 `.git`。
- 架构验证期间 `project_status.md` 可按最新本轮结果号＋1 在本树投影；提交前恢复原样，不暂存；最终合入 master 再正式同步，不能改测试来放宽一致性检查。
- `smoke_test.py --affected` 会自动隐藏桌面 probe；不接受显式 `--probe`。
- 轮 2 新 L2 服务不能反向 import L3 的 `skill_project_layer`；应由既有 L3 适配层注入阶段判定器/发布器，复用既有判定且守住依赖方向，必要的任务书设计偏差用实测证据说明。不得为凑验收修改架构门禁。
- 轮 3 主树实测四条 gitlink，只有 AIGC 无 `.git`；其余三条保持不动。选择保留内容为普通文件（带真实文件清单与前后核验），不代用户删除主树总包或重装。
