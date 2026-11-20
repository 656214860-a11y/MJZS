# R3978 结果：文案规则测试跳过版本库忽略的路径并提速到 3.8 秒
<!-- round-evidence: {"commit_base": "a9df9359", "credential_hits": 0, "evidence_sha256": "6aba5edbfa6ea3ec", "exit": 0, "failed": 0, "passed": 0, "round": 3978, "tests": "docs-only"} -->

## 1. 三问

- **本轮类型**：修复轮（测试基础设施；任务书《减红第二步》R2-G1，修 R2-B2、R2-B3）。
- **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 9/9 全过；架构门禁 684 项全过、失败集合为空（改前改后均为 tests/architecture 全量，本轮未动架构文件，总数与上一验收点一致）；全量回归按任务书要求执行者不跑，留待合入后的自动全量凭据。
- **欠账少了吗**：少了。文案规则测试不再把版本库忽略的运行时数据当源码（R2-B2），单独运行 26.6 秒 → 3.8 秒（R2-B3，已满足 G2 前置「≤10 秒」）。主工作区里那条假红（`工作流任务/回收站/…` 64 处）由主控合入后按任务书 §5.3 核对。G3 守卫暂不覆盖 tests/ 的欠账与本卡无关，未新增欠账。

## 2. 改了哪些文件

- `tests/test_copy_rules.py`（唯一改动的代码文件）
- `tasks_round/tasks_round_3978_result.md`（本文件）

改动内容：`program_sources()` → `program_sources(root=PROGRAM)`；新增 `ignored_paths(root)`（在 root 下跑 `git -c core.quotepath=false ls-files --others --ignored --exclude-standard --directory -z`，显式 `encoding="utf-8"`，返回被忽略文件集合与目录前缀元组）；`os.walk` 裁剪被忽略的文件和目录；5 个测试类的 `setUpClass` 改调 `shared_sources()`（模块级单例，每个源文件只读一次）；新增 `_parse()` `lru_cache`（同一份源码只解析一次）并替换全部 13 处 `ast.parse(body)`；`popups`/`buttons`/`literals` 三个纯函数加 `lru_cache`（同一棵树只扫一次，断言不动）；新增 `ScanScopeTests` 4 条用例。

未改：`SKIP_DIRS`、`POPUP_LINES`、`POPUP_CHARS`、`BUTTON_CHARS`、`ONE_NAME`、`ENTRY_WORD`、`PROMPT_FILES` 与 14 条原有用例的名字和断言（仅做 `program_sources()`→`shared_sources()`、`ast.parse`→`_parse` 机械替换）。

## 3. 改前的失败输出（先红）

新写的 `ScanScopeTests` 在改前运行（当时 `program_sources` 还不接受 `root` 参数）：

```
ERROR: test_1_ignored_paths_are_skipped (tests.test_copy_rules.ScanScopeTests.test_1_ignored_paths_are_skipped)
TypeError: program_sources() takes 0 positional arguments but 1 was given
ERROR: test_2_embedded_repo_is_still_scanned (tests.test_copy_rules.ScanScopeTests.test_2_embedded_repo_is_still_scanned)
TypeError: program_sources() takes 0 positional arguments but 1 was given
ERROR: test_3_non_repo_directory_returns_everything (tests.test_copy_rules.ScanScopeTests.test_3_non_repo_directory_returns_everything)
TypeError: program_sources() takes 0 positional arguments but 1 was given
ERROR: test_4_missing_git_returns_everything (tests.test_copy_rules.ScanScopeTests.test_4_missing_git_returns_everything)
TypeError: program_sources() takes 0 positional arguments but 1 was given
Ran 4 tests in 0.307s
FAILED (errors=4)
```

改前整组基线：`PY -B -m unittest tests.test_copy_rules -v` → `Ran 14 tests in 26.590s`，`OK`。

## 4. 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B -m unittest tests.test_copy_rules -v` | `Ran 18 tests in 3.819s`，`OK`（14 原有 + 4 新增全过） |
| `PY -B smoke_test.py` | 9/9 全过，「冒烟测试通过，可以进入下一轮」 |
| `PY -B smoke_test.py --architecture` | `Ran 684 tests in 355.754s`，`OK`，失败集合为空 |

## 5. 车道里改前改后键集合核对

- 改前 `program_sources()`：767 个文件（快照存 `%TEMP%\copy_rules_keys_before.txt`）
- 改后 `program_sources()`：767 个文件（快照存 `%TEMP%\copy_rules_keys_after.txt`）
- 核对命令（`程序\` 下）：

```powershell
& $PY -X utf8 -B -c "a = open(r'$env:TEMP\copy_rules_keys_before.txt', encoding='utf-8').read().splitlines(); b = open(r'$env:TEMP\copy_rules_keys_after.txt', encoding='utf-8').read().splitlines(); print('before:', len(a), 'after:', len(b), 'equal:', a == b)"
```

- 输出：`before: 767 after: 767 equal: True`（逐行完全相等）

## 6. 耗时

- 改前单独运行：26.6 秒（同一会话实测 `Ran 14 tests in 26.590s`；任务书基线 27.7 秒）
- 改后单独运行：3.8 秒（`Ran 18 tests in 3.819s`）
- 满足「≤10 秒」；G2 前置条件达成。

## 7. 提交前自查结论

按 code-review 两轴（分叉点 `b3544e90`＝`git merge-base master HEAD`，改动仅 `tests/test_copy_rules.py` +140/−24），在当前会话内自审：

- **规范轴**：子进程文本显式 `encoding="utf-8"`（附 `errors="replace"`，解码异常时宁可多扫不少扫）；新测试在 `tests/`；临时目录在系统 TEMP 且用中文前缀；无新模块、无投机抽象；常量与断言零改动；无密钥、无用户名写入文件。
- **契约轴**：`program_sources(root=PROGRAM)` 接口与返回契约一致；忽略口径＝`ls-files --others --ignored --exclude-standard --directory -z`（只排除被忽略的，未入库文件与内嵌仓库继续扫）；git 不在／非工作树／非 0 返回时退化为全扫不抛异常；每源文件一读一解析；ScanScopeTests T1–T4 与任务卡逐条对应；未采用「只查已入库文件」。

结论：两轴均通过，未发现需修改的问题。已知形态说明：T1/T2 共用同一临时目录（任务卡要求「同一个临时目录」），靠 `test_1_`/`test_2_` 名字序保证 T1 先跑；`popups`/`buttons`/`literals` 的 `lru_cache` 以树对象为键、依赖 `_parse` 返回同一实例，绕过 `_parse` 只是不命中、不失效。

## 8. 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R3978: 文案规则测试跳过版本库忽略的路径并提速" --agent Devin tests/test_copy_rules.py tasks_round/tasks_round_3978_result.md --tests copy_rules`
- 已提交：`a9df9359`（主提交），本行由补记提交写入。
