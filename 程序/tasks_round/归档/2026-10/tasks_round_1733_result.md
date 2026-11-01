# R1733：修复轮——TTS 逐句配音测试去真实密钥依赖、状态栏「失败 0 个」不再显示错误色（SMALL）

执行者：opencode（派发执行方，未领号、未提交、未改 project_status.md／AGENTS.md）。工作树：`.wt/lane_small/程序`。
解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`。

## 三问

1. **轮次类型**：修复轮（§3.2），两处最小修复；派发执行，无独立轮次号。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k test_ui_edges test_ui_batch3_shell`＝123 条用例、179.1 秒、0 个文件有红（ALL TESTS PASSED）；默认冒烟 `smoke_test.py`＝通过 8 项、失败 0 项。§2.5 的“默认冒烟 8/8”满足；架构门禁与全量安全回归未跑（不在本任务书验证清单内，见“未运行项”）。
3. **project_status.md 欠账少了吗**：未涉及。本任务属于派发执行，按 §2.6 不写状态页、不领号。

## 改动（文件:行）

### 问题 A：`tests/test_ui_edges.py`

只改 `UiEdgeTests.test_per_line_tts_asks_before_paying` 一条用例，给三处 `with patch.object(...)` 各加一个 `patch.object(tts_api, "load_key", lambda: "sk-fixed-test-key")`：

- `tests/test_ui_edges.py:3438-3439`（取消分支）
- `tests/test_ui_edges.py:3447-3448`（确认分支）
- `tests/test_ui_edges.py:3450-3453`（重跑沿用分支）

**原有断言一条未动**（`calls`、状态文本、句数、字数、价格版本、预计额度等全部保留原样）。

### 问题 B：`desktop.py`

只改状态分色判断这一处：

- `desktop.py:116`：新增注释（零计数写法不算错误）
- `desktop.py:117`：新增模块常量 `_STATUS_ZERO_COUNT`（抹掉错误标记词旁的数量 0，含 `失败 0 个`／`0 个失败`／`失败：0`；`0(?![\d.])` 与 `(?<![\d.])0` 避免把 `100 失败`、`失败 0.5` 误当零）
- `desktop.py:120-123`：`status_kind` 先用 `_STATUS_ZERO_COUNT.sub('', text)` 去掉零计数片段再判错误色；docstring 同步补一句

`re` 已在 `desktop.py` 顶部导入，未新增 import。改后 `desktop.py`＝1932 行，未超过上限 1950。

### 新增用例：`tests/test_ui_batch3_shell.py`

状态分色的既有归属文件（`test_ui_batch3_shell.py` 现有 `test_three_status_messages_use_three_distinct_styles` 就测分色）。在文件末尾新增纯函数用例类：

- `tests/test_ui_batch3_shell.py:162-176`：`StatusKindZeroCountTests`
  - `test_zero_failure_counts_are_not_errors`：`完成 12 个，失败 0 个`／`0 个失败`／`失败：0` → `'ready'`
  - `test_nonzero_and_plain_failures_stay_errors`：`失败 2 个`／`生成失败` → `'error'`

## 问题 B 改前红（未改 `desktop.py`，先加用例跑出）

```
FAIL: test_zero_failure_counts_are_not_errors (tests.test_ui_batch3_shell.StatusKindZeroCountTests.test_zero_failure_counts_are_not_errors) (message='完成 12 个，失败 0 个')
AssertionError: 'error' != 'ready'
- error
+ ready
... (message='0 个失败') AssertionError: 'error' != 'ready'
... (message='失败：0') AssertionError: 'error' != 'ready'
Ran 2 tests in 0.002s
FAILED (failures=3)
```

（`test_nonzero_and_plain_failures_stay_errors` 改前即绿，符合“普通失败仍算错误”。）

## 问题 A 改前红（证据）

本机存在真实 DPAPI 密钥（`tts_api.load_key()` 返回 164 字符），所以改前该用例在本机“碰巧”绿，属环境依赖。为证明它与本机环境无关，把 `LOCALAPPDATA` 指向空目录（模拟无密钥机器）后复跑同一条用例，得到红：

```
ERROR: test_per_line_tts_asks_before_paying (test_ui_edges.UiEdgeTests.test_per_line_tts_asks_before_paying)
  File "...\stage_execution_service.py", line 682, in run_tts_lines
  File "...\tts_api.py", line 444, in run_lines
    raise ValueError("请先在配音设置保存 API Key")
ValueError: 请先在配音设置保存 API Key
Ran 1 test in 1.724s
FAILED (errors=1)
```

加上 `load_key` 假密钥补丁后，同一用例在本机（有真实密钥）与空 `LOCALAPPDATA`（无密钥）两种环境下均绿：

```
Ran 1 test ... OK   # 本机
Ran 1 test ... OK   # LOCALAPPDATA 指向空目录
```

## 实际计数

- 定向（本任务书命令）：`python -B run_selftests.py -k test_ui_edges test_ui_batch3_shell`
  - `123 条用例，179.1 秒；0 个文件有红`，`实际跳过 0 条用例`，`ALL TESTS PASSED`
  - 其中 `test_ui_batch3_shell 8 用例`（6 原有 + 2 新增）全通过；`test_ui_edges` 8 个工作单元共 115 用例全通过
- 冒烟：`python -B smoke_test.py` → `通过：8 项 / 失败：0 项`，`冒烟测试通过`
- 新增用例改前计数：`Ran 2 tests ... FAILED (failures=3)`（3 个 subTest 红）→ 改后 `Ran 2 tests ... OK`
- 改动文件（含结果文件）：`desktop.py`（+4/-2）、`tests/test_ui_batch3_shell.py`（+14）、`tests/test_ui_edges.py`（+6/-3）

## 原有断言未动

- 问题 A：仅新增 `tts_api.load_key` 的 `patch`，`test_per_line_tts_asks_before_paying` 内所有 `assertEqual`/`assertIn` 与三处 `confirm`／`synthesize` 补丁保持原样。
- 问题 B：`desktop.py` 只改分色判断与新增常量/注释，`STATUS_ERROR_MARKERS`／`STATUS_RUNNING_MARKERS` 取值、`status_kind` 的三态返回与调用点未动；既有 `test_three_status_messages_use_three_distinct_styles` 等用例全绿。

## GUI 令牌情况（如实）

- 首次 `run_selftests.py -k test_ui_edges test_ui_batch3_shell` 因等待跨树 GUI 令牌超时（工具 900 秒超时上限，`GUI_WAIT_SECONDS=900`），无计数输出，已中止。
- 随后核验 Git common-dir：当时无 `gui-selftest.lock`，队列仅剩被中止进程（PID 37968）的过期 ticket，判定原占用者已释放。
- 再跑一次（受控），在 480 秒内完成并输出上表计数。总计尝试 2 次，未反复重跑。

## 未运行项

- `smoke_test.py --affected desktop`：本任务书未要求，未跑（`desktop.py` 仅动一个纯函数判断，已由冒烟与定向覆盖）。
- 架构门禁 `--architecture`、全量 `--all --safe`：本任务书未要求，未跑。

## 需裁决事项

1. 零计数正则目前覆盖“错误标记词 + 0”与“0 + 个? + 错误标记词”两种词序，并排除 `100 失败`、`失败 0.5`。是否接受该口径；若只需覆盖 `失败` 一个词，可进一步收窄。
2. 问题 A 的假密钥取值用 `"sk-fixed-test-key"`，仅用于满足 `load_key()` 非空判定；如需固定成其他形式（如 `"sk-test"`）请示下。
3. 问题 B 用例放在 `tests/test_ui_batch3_shell.py`（该文件按 `import desktop` 被识别为 GUI 用例，跑它需 GUI 令牌）。如需落在无 Tk 的文件以省令牌，请示下另选归属。

## 独立验收（Claude，主工作区）

- 车道 diff 干净应用；`run_selftests.py -k test_ui_batch3_shell test_ui_edges test_desktop_status`：ALL TESTS PASSED。
- `smoke_test.py --architecture` 首次 2 红：全量欠账（后台补跑项）＋ TODO 快照 desktop.py 行号 1087→1089（本轮在其前插入 2 行，正是 LINEKEY 要根治的平移问题）。已同步快照行号，单跑 OK。
- 复核正则边界：「失败 10 个」「失败 0.5」「100 失败」不被当零；「失败 0 个，错误 3」仍为错误。
