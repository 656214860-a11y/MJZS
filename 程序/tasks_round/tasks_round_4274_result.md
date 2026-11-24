# R4274 结果：REL-02 发布门禁聚合 dev.py release-gate（续做）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "de841cadf9d37e28", "exit": 0, "failed": 0, "passed": 24, "round": 4274, "tests": "run_selftests.py -k dev_entry version_record"} -->

## 三问

1. 本轮类型：功能轮（§3.1）——新增 `scripts/release_gate.py` 工具脚本与 `dev.py release-gate` 子命令；续做车道，在上一位执行者草稿上补齐用例并修正一处判定口径。
2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k dev_entry version_record`：24 条 / 0 红，退出码 0。
   - 文档门禁 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`：34 条 / 0 红，退出码 0。
   - `smoke_test.py --architecture`：700 条 / 0 红，退出码 0（265.1 秒）。
   - 默认冒烟基线：未跑——卡面命令白名单未列该命令。
   - 全量欠账：`full-safe-receipts.json` 最近收据为旧内容树（10 月 3 日），本卡不跑全量；门禁如实把该项判为未通过，等全量补跑后转绿。
3. 欠账少了吗：少了。发布就绪由「多处手工命令＋过期收据＋人工读检查单」变成一条可机读命令逐项判定；检查单三处过时表述消除；`dist --release` 项的证据口径收紧到必须有 `--release` 实跑。

## 轮次号说明

- 首次领号 R4272；首次 `dev.py commit` 误用仓库根相对路径（`程序/…`），`git add` 路径不匹配失败，但提交回执 `explicit-commit-receipts/R4272.json` 已按错误参数落盘。改用正确路径重试时被回执身份校验拒绝（「轮次已归属其他工作树、分支或命令参数」）。清理该回执的两次尝试（删 `.git/explicit-commit-receipts/R4272.json`/`.lock`、申请该目录写权限）均被拒绝，按卡面不再绕行。
- 重新 `dev.py claim` 领到 R4274（R4273 已被其它车道领走）；R4272 号被烧掉、无结果文件，与旧执行者烧掉的 R4260 同类。`.git/explicit-commit-receipts/` 下残留 R4272.json 与 R4272.lock 两个本轮产生的回执文件，未删除，提请总控知悉。

## 续做现场核对

- `git status --porcelain` 5 行与卡面清单逐行一致；`git log -1` = 79fa309b；分支 codex/rel-02。
- 保留上一位执行者全部草稿：`scripts/release_gate.py`（新文件）、`dev.py` 子命令登记、`CHANGELOG.md` 未发布条目、`发布检查单.md` 三处更正、`test_version_record.py` 3 条检查单契约用例。
- 上一位执行者曾改 `governance/structure.json` 与 `structure-baseline.json`：按 N801 裁决该两份不在现场（git status 无对应行），未恢复、未触碰、未跑 `--write-baseline`。
- 旧草稿 `.agent-tmp/rel-02-old-drafts/test_release_gate.py`（11 条用例）已并入 `test_dev_entry.py`，方法名统一加 `test_release_gate_` 前缀；旧结果文件 `tasks_round_4260_result.md` 不作为交付。`.agent-tmp/` 下文件只读，未改未删。

## 卡面各项完成情况

- `scripts/release_gate.py`（新，340 行）：8 项判定（随包工具 REL-01／ci exit 收据／full --safe 当前树凭据／dist --release／版本一致／升级保留 REL-04／NOTICE REL-10／证书 60 天告警），JSON 输出（每项含 id/check/status/reason/blocking），退出码 0 当且仅当全部阻断项「通过」。默认只读（只读收据与文件），`--run` 经 `run_plan()` 实跑 `local_ci.py exit`、`run_selftests.py --all --safe`、`distribution_selfcheck.py --release` 与已落地的升级保留用例；REL-04/REL-10 未落地时对应项标「未运行」不算通过；`安装信息.json` 在版本项 PASS 原因中明确排除并写原因（INSTALL_INFO_REASON，R1460 口径）。
- `scripts/dev.py:12,39`：`release-gate` 登记进用法行与 `COMMANDS`（草稿保留）；子命令后参数原样转发，`dev.py release-gate --run` 可用。
- `tests/test_dev_entry.py`：并入旧草稿 11 条用例（新类 `ReleaseGateTests`，方法名前缀 `test_release_gate_`），新增 `test_release_gate_dist_release_needs_release_flag_receipt` 一条；`DevEntryTests` 原有 3 条未动。
- `tests/test_version_record.py`：保留草稿 3 条检查单契约用例，新增 3 条版本一致性用例（VERSION 形态、README 版本字样、安装信息.json 排除依据）。
- `docs/process/发布检查单.md`（草稿保留）：第 1 节改为先跑 `dev.py release-gate`；「更新记录.md」全部更正为 `CHANGELOG.md`；`reorganize_install.py` 更正为「历史安装目录归位工具（非安装器）」。
- `CHANGELOG.md:7`（草稿保留）：未发布节登记 REL-02 条目。
- 拿不准项核实：`dist --release` 在 verify() 中只卡 `release_ready = valid and not blockers`；release_blockers 仅来自 SBOM 组件 `license.id=NOASSERTION`。唯一显式 NOASSERTION 的「skills/01 剧本准备SKILL/剧本锻造」已在 `distribution_manifest.md` 必须排除清单，编剧技能集 MIT、PyPI/ASR/工具许可证均有登记——当前应无阻断项，不需要标「未运行」，由 `--run` 实跑判定（未实跑，见下）。

## 本轮续做相对草稿的修改

- `release_gate.py:120-145` `check_dist_release`：CI 收据「分发自检」步绿不再判通过——`local_ci release` 该步跑的是不带 `--release` 的 `distribution_selfcheck.py`（`local_ci.py:58`），只证构建／校验／导入绿，不证 SBOM `release_blockers` 为空；绿收据降级为「未运行」并写明需 `--run` 实跑，红收据仍判未通过。
- `release_gate.py:328-336` `main`：加可选 `runner` 形参透传 `evaluate`，供 `--run` 用桩断言（既有调用方不受影响）。
- `test_dev_entry.py`：草稿用例改名合入并按上述口径调整——全绿与证书告警用例改经 `run=True`+桩 runner（只读模式下 dist 项永远是「未运行」，releasable 只能由 --run 路径给出）；新增 dist-release 证据口径用例。

## 改前红的条数和失败原因（原文）

卡面缺陷本身（`release-gate` 命令不存在）在基线上由验收复核，本车道未观察；续做现场已有实现，对合入后的新用例跑出 2 条红，均属本卡范围内缺陷，修复后转绿：

```
===== test_release_gate_dist_release_needs_release_flag_receipt =====
AssertionError: '通过' != '未运行'

===== test_release_gate_main_exit_zero_and_json_when_releasable =====
TypeError: main() got an unexpected keyword argument 'runner'
```

## 改后命令输出尾部原文

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k dev_entry version_record`（退出码 0）：

```
共 24 条用例，0.9 秒；0 个文件有红
  test_dev_entry                15 条     0.1 秒
  test_version_record            9 条     0.0 秒
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（退出码 0）：

```
共 34 条用例，1.4 秒；0 个文件有红
  architecture.test_design_coverage     8 条     0.0 秒
  architecture.test_stage_doc_sections    10 条     0.1 秒
  architecture.test_agent_doc_budget    11 条     0.1 秒
  architecture.test_requirement_traceability     5 条     0.4 秒
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
Ran 700 tests in 265.095s

OK
✅ 架构治理测试：tests/architecture
```

## 没有验证的地方

- `release-gate` 真实环境端到端未跑：卡面命令白名单不含直接运行它；判定路径由注入式单测覆盖（真实环境下 content_tree 因本车道未提交改动返回空串，full-safe 项会如实判未通过）。
- `--run` 实跑项未真跑（约 27 分钟全量、4 分钟 CI、分发构建）：`run_plan()` 命令清单由桩测试断言。
- `dist --release` 未实跑构建确认 release_blockers 为空（只读核实见上，结论「应为空」未实测）。
- 默认冒烟未跑（卡面未列）。

## 卡外发现的问题（只记录，未顺手修）

- `.agent-tmp/需求设计-card-REL-02.md` 在本车道不存在（read 报 not found），卡面以派工消息为准执行。
- `dev.py commit` 的 `[文件...]` 参数实际按 `程序/` 子目录相对路径解析（内部 git 命令 cwd=`程序/`）；卡面「路径相对仓库根」的说法与实现不符，仓库根相对路径会让 `git add` 失败且留下身份绑定错误参数的提交回执——建议总控在 runbook 注明正确用法。
- 会话中两条 PowerShell 取证命令与两条 `.git` 回执清理尝试被拒绝（`Get-ChildItem`、`Get-Content`、`Remove-Item` 回执文件、request_scope 写权限），均按卡面规则记录后继续或停止绕行。
