# R4339 结果：修复 Agent.context 在缺 facts/errors 替身宿主上的 AttributeError（FIX-MASTER-PET-CONTEXT）
<!-- round-evidence: {"commit_base": "3eacf9cc5", "credential_hits": 0, "evidence_sha256": "baf09698a0080cd8", "exit": 0, "failed": 0, "passed": 110, "round": 4339, "tests": "run_selftests.py -k pet_offer_brevity pet_agent"} -->

## 三问
- 轮次类型：修复轮（§3.2）。卡 FIX-MASTER-PET-CONTEXT：R4271/R4278 SANHU-CONTEXT-GAPS 引入的主干回归，test_pet_offer_brevity 红灯阻断主干 `--all --safe` 绿凭据。
- 测试和三个基线：定向命令 `run_selftests.py -k pet_offer_brevity pet_agent` 改前 110 条中 2 红、改后 110 条全绿（退出码 0）；`smoke_test.py --architecture` 702 条全过（退出码 0）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：主干全量红灯已闭环，欠账减少，未新增欠账。

## 缺陷复现
- 复现命令（程序 目录下原样执行）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_offer_brevity pet_agent`
- 改前红 2 条，失败原因与卡面一致（退出码 1）：
  - `test_pending_question_reaches_the_router_context`：SimpleNamespace 替身（仅 machine/projects_snapshot/pending_offer）调 `pet_agent.Agent.context(agent)`，`pet_agent.py:1002` 的 `self.facts` 抛 `AttributeError: 'types.SimpleNamespace' object has no attribute 'facts'`，进 except 后 `:1003` 的 `self.errors` 再抛 `AttributeError: 'types.SimpleNamespace' object has no attribute 'errors'`。
  - `test_facts_failure_without_errors_sink_stays_silent`（本轮新增用例）：替身 `facts` 可调用但抛 `RuntimeError`，except 分支访问缺失的 `self.errors` 抛 `AttributeError: 'types.SimpleNamespace' object has no attribute 'errors'`。
- 根因：`context()` 的 facts 采集与错误记账按真实 Agent 写死 `self.facts`／`self.errors` 属性访问，替身宿主没有这两个属性。

## 改动
- `pet_agent.py:1002`：`callable(self.facts)` 改为 `callable(getattr(self, 'facts', None))`，替身无 `facts` 属性时不再抛 AttributeError；真实 Agent 中 `self.facts` 为普通属性（`pet_agent.py:701`），判定结果不变。
- `pet_agent.py:1003`：except 分支改经 `errors = getattr(self, 'errors', None)`，仅 `errors is not None` 时 `append(('facts', str(exc)))`；真实 Agent 的 `self.errors` 恒为 `pet_bus.ErrorLog`（`pet_agent.py:695`），记账行为逐字不变。
- `tests/test_pet_offer_brevity.py:54-58`：新增 `test_facts_failure_without_errors_sink_stays_silent`——`facts` 抛异常且替身无 `errors` 属性时 `context()` 不向外抛错、返回 `{}`。
- 行数约束：`pet_agent.py` 棘轮登记上限 1046（`tests/architecture/test_module_size_ratchet.py:21`）与实际行数持平，本次为 2 行换 2 行，净增 0。

## 核对（命令输出尾部原文）
- `run_selftests.py -k pet_offer_brevity pet_agent`，退出码 0：
  ```
  共 110 条用例，2.5 秒；0 个文件有红
  最慢 9 路工作单元：
    test_pet_agent_error_wiring    0.5 秒 / 10 条
    test_pet_agent#2              0.1 秒 / 15 条
    test_pet_agent#1              0.1 秒 / 16 条
    test_pet_agent#7              0.0 秒 / 11 条
    test_pet_agent#4              0.0 秒 / 15 条
    test_pet_agent#3              0.0 秒 / 16 条
    test_pet_agent#5              0.0 秒 / 4 条
    test_pet_agent#6              0.0 秒 / 16 条
    test_pet_offer_brevity        0.0 秒 / 7 条
  实际跳过 0 条用例：本机没有任何登记位被跳过
  增量台账已刷新：…\.git\selftest-incremental.json
  最近 5 轮自检中位基线：3.4 秒

  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`，退出码 0：
  ```
  ----------------------------------------------------------------------
  Ran 702 tests in 234.116s

  OK
  ✅ 架构治理测试：tests/architecture
  ```

## 未验证
- 默认冒烟 8/8 与全量 `run_selftests.py --all --safe` 未运行（卡面验收未列；本卡修的正是全量红凭据的阻断项）。
- 真实 Agent 的 facts 采集进 `context['facts']` 的正常路径由 test_pet_agent 既有用例覆盖（93 条全绿），替身宿主新行为由本轮新增用例覆盖。
