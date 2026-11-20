# R3977 结果：工具脚本读取子进程文本按 UTF-8 解码
<!-- round-evidence: {"commit_base": "b3544e90", "credential_hits": 0, "evidence_sha256": "e2c491370ea47c3d", "exit": 0, "failed": 0, "passed": 18, "round": 3977, "tests": "run_selftests.py -k lane_merge_queue static_hygiene"} -->

## 1. 三问

- **轮次类型**：修复轮（AGENTS.md §3.2；任务卡 R2-G3，缺陷 R2-B5，开发工具）。
- **测试跑了吗、三个基线**：跑了。默认冒烟 9/9 全过；架构门禁 685 条全过、失败集合为空（改前 684，本轮 T2 新增 1 条）；全量回归按任务书 §5.2 不由执行者跑，凭据待合入后自动全量给出。
- **欠账少了吗**：任务书范围内的 6 处编码缺口已清零并由 T2 守卫；任务书 §9 记为欠账的 `tests/` 30 处、`skills/` 3 处、`environment_check.py:46` 未动，欠账总额不增。

## 2. 改了哪些文件（文件:行号）

按任务卡「接口契约」，以下 6 处带 `text=True` 的子进程调用补 `encoding="utf-8", errors="replace"`，命令、参数、超时、返回值用法不变：

| 文件 | 行号 | 调用 |
| --- | --- | --- |
| `维护记录/基准脚本/lane_registry.py` | 40–43 | `subprocess.run`（`_worktree_info` 内部 `git()`）；另把 `.stdout.strip()` 改为 `(done.stdout or "").strip()`，git 无输出返回空字符串不抛异常 |
| `维护记录/基准脚本/round_gate.py` | 23 | `subprocess.run`（`git()`） |
| `维护记录/基准脚本/install_git_hooks.py` | 16–18 | `subprocess.run`（`git_common_dir()`） |
| `维护记录/基准脚本/recovery_to_delivery_baseline.py` | 197–198 | `subprocess.check_output` |
| `维护记录/基准脚本/remote_pre_receive.py` | 108–112 | `subprocess.run`（`gitleaks_scan()`） |
| `scripts/acceptance_security_probe.py` | 627–629 | `subprocess.run`（`_git_head()`） |

测试改动：

- `tests/test_lane_merge_queue.py`：加 `WorktreeInfoEncodingTests`（T1）——中文名临时目录 `git init`，子进程去掉 `PYTHONUTF8`/`PYTHONIOENCODING`、不带 `-X utf8` 调 `_worktree_info`，断言车道名等于目录名且 stderr 无 `UnicodeDecodeError`。
- `tests/architecture/test_static_hygiene.py`：加 `test_tool_scripts_decode_subprocess_text_as_utf8`（T2）——语法树扫描程序根、`scripts/`、`维护记录/基准脚本/` 的 `.py`（不递归），找出 `subprocess` 的 run/call/check_call/check_output/Popen（含 `from subprocess import` 绑定形式）带 `text=True`/`universal_newlines=True` 却无 `encoding` 的调用，失败信息列 `文件:行号`。

未改：`round_claim.py`（「车道登记失败不阻断领号」行为保持原样）、`commit_round.py`、`merge_round.py`、`skills/`、`tests/` 其余文件、`project_status.md`（非 master 不提交）。

## 3. 改前的失败输出

### §2.4 复现命令（改前，不带 -X utf8）

```
& $PY -B -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('维护记录') / '基准脚本')); import lane_registry; print(lane_registry._worktree_info(pathlib.Path('.')))"
```

```
Exception in thread Thread-1 (_readerthread):
  ...
  File "...\subprocess.py", line 1614, in _readerthread
    buffer.append(fh.read())
UnicodeDecodeError: 'gbk' codec can't decode byte 0xab in position 5: illegal multibyte sequence
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "...\lane_registry.py", line 41, in git
    capture_output=True, text=True, timeout=15).stdout.strip()
AttributeError: 'NoneType' object has no attribute 'strip'
退出码 1
```

### T1（改前）

```
FAIL: test_worktree_info_with_chinese_path_under_default_encoding
AssertionError: '杞﹂亾-m808h8b3' != '车道-m808h8b3'
```

（`车道` 的 UTF-8 字节被 cp936 解成 `杞﹂亾`：没有抛异常、静默产出错误车道名，比 DecodeError 更能说明后果。）

### T2（改前）

```
FAIL: test_tool_scripts_decode_subprocess_text_as_utf8
AssertionError: Lists differ:
['scripts/acceptance_security_probe.py:627',
 '维护记录/基准脚本/install_git_hooks.py:16',
 '维护记录/基准脚本/lane_registry.py:40',
 '维护记录/基准脚本/recovery_to_delivery_baseline.py:197',
 '维护记录/基准脚本/remote_pre_receive.py:108',
 '维护记录/基准脚本/round_gate.py:23'] != []
```

恰好 6 处，与任务书 §2.4 清单一致。

## 4. 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B -m unittest tests.test_lane_merge_queue -v` | 全过（12 条，含 T1） |
| `PY -B -m unittest tests.architecture.test_static_hygiene -v` | 全过（7 条，含 T2） |
| §2.4 复现命令（不带 -X utf8） | 输出 `('tool-subprocess-encoding', 'codex/tool-subprocess-encoding', 'D:/漫剧制作助手/.agents/worktrees/tool-subprocess-encoding')`，无 UnicodeDecodeError，退出码 0 |
| `PY -B smoke_test.py` | 9/9 全过 |
| `PY -B smoke_test.py --architecture` | 685 条全过，失败集合为空；改前 684（本轮 T2 新增 1 条） |

## 5. 提交前自查

按 code-review 两条标准自审 `git merge-base master HEAD`（`b3544e90`）以来的全部改动（本会话内完成，未起子代理）：

- **规范轴**：8 个改动文件均在任务卡「允许修改文件」清单内；每处只加编码参数，沿用各文件原有引号风格与缩进；`lane_registry.git()` 的 `(done.stdout or "")` 满足「无输出返回空字符串不抛异常」契约；新测试断言行为与 AST 语义（非源码字符串），新测试在 `tests/` 与 `tests/architecture/` 既有文件内；未弱化、删除、跳过任何既有断言；Fowler 异味基线无命中（无重复逻辑、无投机抽象——`_SUBPROCESS_CAPTURE_FUNCS` 恰为任务卡点名的 5 个函数）。
- **规格轴**：T1/T2 与任务卡逐条对应（先红后绿、子进程剥离 utf8 环境变量、AST 守卫覆盖三处目录并识别 from-import 写法、失败信息带 `文件:行号`）；6 处修复点与 §2.4 清单一致；禁止事项均未触碰（未改 `round_claim.py`/`commit_round.py`/`merge_round.py`/`skills/`，未用全局环境变量替代显式编码）。

## 6. 欠账与范围外记录

- `tests/` 内 30 处未指定编码的子进程调用：任务书 §9 明确不做，T2 守卫暂不覆盖 `tests/`。
- `skills/09白模预演SKILL/…/server.py` 3 处：第三方技能包，不属本仓维护。
- `environment_check.py:46`：经 `contract.platform_tools.run_process` 转发，编码由该包装决定，不在本卡范围。
- `lane_registry._worktree_info` 调用方 `round_claim.py:291–296` 的 `except Exception: pass` 行为未动，本修复使其在默认编码下不再静默失败（lanes.json 可正常登记）。

## 7. 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R3977: 工具脚本读取子进程文本按 UTF-8 解码" --agent Devin <8 个改动文件> tasks_round/tasks_round_3977_result.md --tests lane_merge_queue static_hygiene`
- 提交号：（提交后回填）
