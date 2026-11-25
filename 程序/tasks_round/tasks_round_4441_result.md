# R4441 FIX-FULLSAFE-SEND-AND-LOGIN：修复发送预检契约与登录闸桩兼容（修复轮）
<!-- round-evidence: {"commit_base": "ee2066ee3", "credential_hits": 0, "evidence_sha256": "3e08b47279d1a30e", "exit": 0, "failed": 0, "passed": 284, "round": 4441, "tests": "run_selftests.py -k workflow desktop_send_ledger claude_writing_session idea_semantic_brief writing_api pet_login_quiet login_gate"} -->

## 开头三问

1. **本轮类型**：§3.2 修复轮。卡面 FIX-FULLSAFE-SEND-AND-LOGIN（W2，车道 `codex/fix-fullsafe-send-and-login`，基准 `ee2066ee3`）：只做三处最小精准修复，清零主干全量自测 `auto_full_safe.log` 中 6 个文件合计 25 条既有红。
2. **测试与三个基线**：定向命令 `run_selftests.py -k workflow desktop_send_ledger claude_writing_session idea_semantic_brief writing_api pet_login_quiet login_gate` 改后 284 条用例 0 红、退出码 0；`smoke_test.py --architecture` 708 条 OK、退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面未列）。
3. **欠账**：无新增欠账；本卡点名的 6 个测试文件 25 条既有红已清零。

## 基线

- 工作树：`D:\漫剧制作助手\.agents\worktrees\fix-fullsafe-send-and-login`
- 分支：`codex/fix-fullsafe-send-and-login`
- 基准提交：`ee2066ee3c4d12bf3ef460d2b82185f541907d99`
- 开工核验：`git status --porcelain` 无输出；`git log -1 --format=%h` = `ee2066ee3`；`git rev-parse --abbrev-ref HEAD` = `codex/fix-fullsafe-send-and-login`。

## 改前红（先跑定向留红）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k workflow desktop_send_ledger claude_writing_session idea_semantic_brief writing_api pet_login_quiet login_gate`

结果：退出码 1；`共 284 条用例，30.2 秒；7 个文件有红`（`test_workflow` 分两个工作单元，合计 12 条；去重后为 6 个测试文件、25 条红）：

- `test_pet_login_quiet` 1 条：`AttributeError: 'FakeDesktop' object has no attribute '_arm_gate_unreachable_notice'`。
- `test_claude_writing_session` 1 条、`test_desktop_send_ledger` 8 条、`test_workflow` 12 条、`test_idea_semantic_brief` 2 条：均为显式 `_config` 进入 `resolve_for_send` 后被 REL-03 预检误拦，抛 `ValueError: 需要配置模型或引擎…`。
- `test_writing_api` 1 条：`test_custom_desktop_model_uses_its_program_without_api` 的假 `program='C:/Apps/Gemini.exe'` 不存在，被 REL-03 实文件校验拦截。

## 根因与改动（文件:行号）

1. `程序/orchestrator/workflow_settings.py:838-853`：`resolve_for_send` 文档约定「config 给定则沿用」，但 REL-03 新增的引擎预检写在 `if config is None:` 之外，导致所有显式传 `_config` 的既有路径被误校验。已把预检块缩进收进 `if config is None:`；`config=None` 的生产路径与 REL-03 `FirstRunMatrixTests` 行为不变。文件总行数 997（≤998 卡面约束，≤1000 模块棘轮）。
2. `程序/tests/test_writing_api.py:50-56`：桌面模型夹具原硬编码不存在路径 `C:/Apps/Gemini.exe`。现于 `TemporaryDirectory` 内创建真实占位文件 `Gemini.exe`，并在任何 `model_pool.pool` 调用前把 `record['program']` 设为 `str(fake_exe)`；下方断言一行未动。此为对齐 REL-03（R4412，REQ-S01-119）发送前实文件校验的夹具修正，未放宽预检。
3. `程序/ui/desktop_login_gate.py:60-62`：`show_login_gate` 原无条件调用 `_arm_gate_unreachable_notice()`，最小桩 `FakeDesktop` 没有该方法。现按同函数 `pet = getattr(self, 'pet', None)` 的既有写法用 `getattr` 取方法并仅在 `callable` 时调用；真实 `Desktop` 路径仍装配不可达提示。文件 175 行，未触发行数棘轮。

未修改 `tests/test_workflow.py`、`tests/test_pet_login_quiet.py`；未删除、跳过或放宽任何既有断言。

## 验收命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k workflow desktop_send_ledger claude_writing_session idea_semantic_brief writing_api pet_login_quiet login_gate` | 0 | 284 条用例、68.3 秒、0 个文件有红，`ALL TESTS PASSED`；`test_login_gate` 三个分片（16+14+15 条）全绿，含 REL-03 四态矩阵 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 708 tests in 356.236s` / `OK` / `✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次号 `4441` |

定向输出尾部原文：

```text
共 284 条用例，68.3 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

架构门禁输出尾部原文：

```text
Ran 708 tests in 356.236s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证 / 边界说明

- 未重跑主干全量 `run_selftests.py --all --safe`／`auto_full_safe.log` 全量；本卡验收只要求 7 组定向与架构门禁，25 条点名红已在定向范围清零。
- 未跑默认 `smoke_test.py`（卡面未列）。
- 未做真实桌面人工点验；Tk 相关用例均经隐藏桌面运行器通过。
- 未合入、未 push；仅本车道提交。

## 提交

- 车道 `codex/fix-fullsafe-send-and-login`，领号 R4441；本文件随 `scripts\dev.py commit` 同批提交，证据 `tasks_round/evidence/R4441.json` 由提交工具生成；commit hash 见完成报告。
