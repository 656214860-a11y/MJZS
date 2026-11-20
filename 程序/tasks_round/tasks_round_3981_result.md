# R3981 结果：文案规则测试进静态门禁，两份清单立一致性测试
<!-- round-evidence: {"commit_base": "3409745e", "credential_hits": 0, "evidence_sha256": "d97ee2e9593f5203", "exit": 0, "failed": 0, "passed": 0, "round": 3981, "tests": "docs-only"} -->

## 1. 三问

- **本轮类型**：功能轮（门禁；任务书《减红第二步》R2-G2，修 R2-B1、R2-B4）。
- **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 9/9 全过；架构门禁 684 项全过、失败集合为空（改前 347.3 秒、改后 348.6 秒，同集）；全量回归按任务书要求执行者不跑，留待合入后的自动全量凭据。
- **欠账少了吗**：少了。文案规则测试进合入前静态门禁（R2-B1），本机与远端两份清单由一致性测试守住（R2-B4）。未新增欠账；`tests/` 与 `skills/` 里未指定编码的子进程调用是 G3 的既有欠账，与本卡无关。

## 2. 改了哪些文件

- `scripts/local_ci.py`：`STATIC_GATE_TESTS` 末尾加一条注释和 `"tests.test_copy_rules"`（原 8 项内容与顺序不变；`EXIT_STEPS`／`RELEASE_STEPS`／`FULL_STEPS` 未动）。
- `维护记录/基准脚本/remote_post_receive_ci.py`：`STATIC_GATE_TESTS` 末尾加同一项 `'tests.test_copy_rules'`。
- `tests/test_remote_post_receive_ci.py`（任务卡允许二选一，选它因为该文件已把远端脚本加载为 `mod`）：新增 `sys.path` 加 `scripts/` 与 `import local_ci`；新增 `StaticGateListTests` 两条用例。
- `tasks_round/tasks_round_3981_result.md`（本文件）。
- `runbook.md` 未改：全文件 3 处「静态门禁」只指步骤名（runbook 第 33、78、81 行），没有列举门禁内容的句子，按任务卡不改。

## 3. 改前的失败输出（先红）

第一步，只写测试不改清单，`PY -B -m unittest tests.test_remote_post_receive_ci -v`：T2 红、T1 绿（两份清单当时同为 8 项）：

```
FAIL: test_copy_rules_is_in_static_gate (tests.test_remote_post_receive_ci.StaticGateListTests.test_copy_rules_is_in_static_gate)
AssertionError: 'tests.test_copy_rules' not found in ('tests.architecture.test_static_hygiene', 'tests.test_static_names', 'tests.architecture.test_print_ratchet', 'tests.architecture.test_module_size_ratchet', 'tests.architecture.test_function_size_ratchet', 'tests.architecture.test_silent_exception_ratchet', 'tests.architecture.test_todo_comment_snapshot', 'tests.architecture.test_skip_hygiene')
Ran 18 tests in 1.166s
FAILED (failures=1)
```

第二步，只改 `local_ci.py`（镜像未动）再跑：T1 红（本机 9 项、远端 8 项）：

```
FAIL: test_local_and_remote_static_gate_tests_are_identical (tests.test_remote_post_receive_ci.StaticGateListTests.test_local_and_remote_static_gate_tests_are_identical)
AssertionError: Tuples differ: (...) != (...)
First tuple contains 1 additional elements.
First extra element 8:
'tests.test_copy_rules'
Ran 18 tests in 1.872s
FAILED (failures=1)
```

第三步，改远端镜像后转绿（见 §4）。

## 4. 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B -m unittest tests.test_release_bindings tests.test_remote_post_receive_ci -v` | `Ran 22 tests in 1.514s`，`OK`（20 原有 + 2 新增全过） |
| `PY -B -m unittest tests.test_copy_rules` | `Ran 18 tests in 4.250s`，`OK` |
| `PY -B scripts\local_ci.py exit`（改后） | 末行 `[CI] 通过，日志 …\程序\logs\ci_最近.log`；三步全绿 |

## 5. 出口检查「静态门禁」一步改前改后用时

取自本车道同一棵工作树里 `local_ci.py exit` 的日志行：

- 改前（8 个模块）：`[CI] 静态门禁 退出码 0，用时 36.7 秒`
- 改后（9 个模块，46 条用例）：`[CI] 静态门禁 退出码 0，用时 43.0 秒`
- 增量 +6.3 秒，在任务书「静态门禁一步用时增加不超过 10 秒」的口径内（§5.3 主控核对项）。

同一次改后出口检查其余两步：`默认冒烟 退出码 0，用时 0.2 秒`（9/9 全过）；`架构门禁 退出码 0，用时 348.6 秒`（`Ran 684 tests`，`OK`）。

## 6. `tests/test_copy_rules.py` 的 import 清单（远端 Linux 可用性核对）

```
import ast
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
```

全部为 Python 标准库、跨平台模块；没有 `msvcrt`/`winreg`/`ctypes`/`pywin32` 等 Windows 专有模块，没有 Tk（文件自述「只做静态检查，不开窗口」）。它用到的 `git` 在远端 CI 检出环境里必然存在（检出本身就靠 git clone）。远端实际结果要等推送后由 post-receive 给出，执行者不推送。

## 7. 提交前自查结论

按 `%USERPROFILE%\.claude\skills\code-review\SKILL.md` 两轴（分叉点 `b3544e90`＝`git merge-base master HEAD`；本卡未提交改动＝上述 3 个文件，G1 已提交部分已在 R3978 审过），在当前会话内自审：

- **规范轴**：两处清单只在末尾追加，`local_ci.py` 的注释沿用文件内 R 编号风格；测试文件的 `sys.path.insert + import local_ci + # noqa: E402` 与 `tests/test_release_bindings.py` 既有写法一致；新类命名、断言风格与文件内其它类一致；无重复入口、无投机抽象、无密钥或用户名。
- **契约轴**：两处 `STATIC_GATE_TESTS` 均为 9 项且末尾同为 `tests.test_copy_rules`，原 8 项内容与顺序未动；`EXIT_STEPS`/`RELEASE_STEPS`/`FULL_STEPS` 未动；T1（两元组相等）与 T2（`tests.test_copy_rules` 在本机清单里）与任务卡逐条对应，并守 §5.4 的 R2-F2、R2-F3 两条适应度函数；runbook.md 无列举门禁内容的句子，按卡不改。

结论：两轴均通过，未发现需修改的问题。

## 8. 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R3981: 文案规则测试进静态门禁，两份清单立一致性测试" --agent Devin scripts/local_ci.py 维护记录/基准脚本/remote_post_receive_ci.py tests/test_remote_post_receive_ci.py tasks_round/tasks_round_3981_result.md --tests release_bindings remote_post_receive_ci copy_rules`
- 已提交：`3409745e`（主提交），本行由补记提交写入。
