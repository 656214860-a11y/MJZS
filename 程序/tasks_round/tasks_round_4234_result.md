# R4234 DOC-R4230-TRUTH：R4230 结果文档真实性补正（验证/基线轮）
<!-- round-evidence: {"commit_base": "c247e8df", "credential_hits": 0, "evidence_sha256": "3879eceb874c7a7a", "exit": 0, "failed": 0, "passed": 0, "round": 4234, "tests": "docs-only"} -->

## 三问
- 轮次类型：§3.10 验证/基线轮（document-only 真实性补正）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定的默认冒烟 `smoke_test.py`，退出码 0，输出尾部为 `通过：9 项`、`失败：0 项`、`✅ 冒烟测试通过，可以进入下一轮`；`git diff --check` 退出码 0、无输出。架构门禁与全量未跑（document-only）。
- 欠账少了吗：消除 R4230 无凭据手工并发叙述这一 P2 文档欠账；无新增欠账。

## 范围与基线
- 基准版本：`c247e8df`。
- 父轮：R4230（FIX-ROUNDCLAIM-LOCK）。
- 任务：DOC-R4230-TRUTH / 验收 N321 的 document-only 真实性补正。
- 改动文件：`tasks_round/tasks_round_4230_result.md`、`tasks_round/tasks_round_4234_result.md`；`tasks_round/evidence/R4234.json` 由 `scripts\dev.py commit` 生成。
- 产品与测试零改动：本轮只改两份结果文档，未修改 `.py`、`tests/`、配置或产品文档；未重跑 32 线程试验，未补造原始输出。

## R4230 修正前后文字
修正前（`tasks_round/tasks_round_4230_result.md:56-59`）：

```markdown
## 手工并发验证（32 线程 × 5）
- 临时把 `test_concurrent_claims_are_unique_and_contiguous` 改为 32 线程并把期望号段临时改为 `range(41, 73)`；第一次运行 `errors` 为空、32 个号为 41–72，仅因期望仍写 8 个号而断言红。
- 随后同一定向命令连跑 5 遍，均退出码 0：每遍 `共 28 条用例`、`0 个文件有红`、`ALL TESTS PASSED`（约 21.3–24.3 秒）。
- 验证后已还原为 8 线程与 `range(41, 49)`；最终定向复跑仍 28 条全绿（见上）。
```

修正后（`tasks_round/tasks_round_4230_result.md:56-61`）：

```markdown
返工说明（R4234）：本节原先记录的 32 线程首跑与五连跑叙述没有保留可核验原始输出，验收 N321 判定为无凭据手工并发叙述；该叙述已撤回，不作为 R4230 验收证据。document-only 真实性补正见 `tasks_round/tasks_round_4234_result.md`。

## 手工并发验证（32 线程 × 5，原始输出缺失，叙述已撤回）
- 可核实的自动化并发用例仍是 `tests/test_round_claim.py` 的 `test_concurrent_claims_are_unique_and_contiguous`：8 线程、期望号段 `range(41, 49)`，未弱化；本轮定向证据见 round-evidence 机器头与上方 28 条全绿记录。
- 原先记录的“32 线程首跑 errors 为空、号段 41–72”“期望仍写 8 个号”“同一定向命令五连跑全绿”等手工并发叙述，因未找到原始输出而撤回；不得作为本轮验证证据。
- R4234 document-only 补正未为本文档修改测试、重跑 32 线程试验或补造输出；测试保持 8 线程与 `range(41, 49)`。
```

## 保留未改的 R4230 事实
- round-evidence 机器头、`commit_base=729f8800`、定向 `run_selftests.py -k round_claim dev_entry` 28 条通过记录未改。
- 改前红灯 3 条、改后绿灯 28 条、`smoke_test.py --architecture` 700 条通过记录未改。
- 既有自动化并发用例 `test_concurrent_claims_are_unique_and_contiguous` 为 8 线程、`range(41, 49)`，未弱化。

## 验证命令与结果
工作目录均为 `程序`。

1. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py`
   - 退出码：0
   - 输出尾部：
     ```text
     ==================================================
     通过：9 项
     失败：0 项
     ==================================================

     ✅ 冒烟测试通过，可以进入下一轮
     ```

2. `git diff --check`
   - 退出码：0
   - 输出：无输出。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4234: DOC-R4230-TRUTH 结果文档真实性补正" tasks_round/tasks_round_4230_result.md tasks_round/tasks_round_4234_result.md`
- `tasks_round/evidence/R4234.json` 由 `scripts\dev.py commit` 生成；提交哈希无法在同批文件内自引用，以证据回执与完成报告为准。

## 未验证项
- 未重跑 R4230 定向 `run_selftests.py -k round_claim dev_entry`、架构门禁或全量 `--all --safe`；本轮为 document-only 补正，相关机器事实沿用 R4230 round-evidence 与既有结果文件。
- 未重做 32 线程手工并发试验；原无凭据叙述已撤回，不作为验证证据。
- 未重新核对 R4230 产品 diff 或功能修复本身；本轮只修正文档真实性。
