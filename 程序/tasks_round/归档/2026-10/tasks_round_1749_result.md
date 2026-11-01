# R1749：修复轮——给 _page_paint_timed 补回函数身份（PERFFIX）

## 三个必答问题

- 轮次类型：§3.2 修复轮（背景：R1745 给 `Desktop.show` 加的装饰器丢了函数身份，master 上 `tests/test_perf_baseline.py` 红 2 条）。
- 测试跑了吗、三个基线过了吗：本任务书明确禁止执行者跑测试。定向用例与冒烟按调度方 `accept_fix1.out` 的实跑数字照录（见下文）；架构门禁与全量基线未运行，由调度方验收时补，不写成通过。
- `project_status.md` 的欠账少了吗：未改动 `project_status.md`；是否销账由调度方在合入后判定。

## 改动范围核验

`git status --short` 仅两项修改（无新增未跟踪文件，无越界）：

- `M desktop.py`
- `M tests/test_page_paint_metric.py`

`git diff --stat`：`desktop.py` +2 行、`tests/test_page_paint_metric.py` +7 行，合计 2 文件 9 行插入、0 行删除，与任务书预期一致。`git diff -U0` 中删除行计数为 0，未出现新增 skip。

### 逐文件、逐函数

- `desktop.py` — 模块级装饰器 `_page_paint_timed(func)`（第 106 行起）：在 `def wrapper` 前加入 `import functools` 与 `@functools.wraps(func)`。装饰对象是 `Desktop.show`（第 1087 行 `@_page_paint_timed`，其外层还有 `@app_logging.timed('page.show',800)`），行为（`begin_page_paint` 计时 + 原 `show` 调用）不变，只恢复 `__name__`/`__doc__`/`__wrapped__` 等身份属性。
- `tests/test_page_paint_metric.py` — 新增模块级 `import inspect`；类 `PagePaintMetricTests` 新增用例 `test_page_paint_decorator_preserves_show_identity`，断言 `Desktop.show.__name__ == 'show'`、`inspect.getsource(Desktop.show)` 含 `self.fit_content()`，并额外断言 `hasattr(Desktop.show, '__wrapped__')`。

## 先红说明

调度方在 master（含 R1745）上观察到 `test_perf_baseline` 红 2 条。本任务未复现该红，也未贴改动前失败输出，沿用该观察，不编造输出。

## 实际计数（照录 `D:\漫剧制作助手\工作流任务\accept_fix1.out`，主工作区实跑）

- `run_selftests -k perf_baseline page_paint_metric app_logging`：共 27 条用例，32.0 秒，0 个文件有红；`test_perf_baseline` 9 条 27.2 秒、`test_page_paint_metric` 5 条 3.3 秒、`test_app_logging` 13 条 0.1 秒（三者合计 30.6 秒，另有 1.4 秒未归入最慢 3 路，属并行口径，非漏项）。
- 实际跳过 0 条用例；最近 5 轮自检中位基线 32.0 秒。
- `smoke_test.py`：失败 0 项，冒烟测试通过。
- 架构门禁：**未运行，由调度方验收时补**。

## 如实记录的另外两点

1. 上一次执行方在其沙箱里跑 `perf_baseline` 时，内存用例曾卡约 5 分钟（312 秒 CPU）；调度方在主工作区实测同一文件 9 条 27.2 秒通过，判断为沙箱环境现象，非代码问题。
2. 本会话未跑任何 `run_selftests` / `smoke_test` / `unittest`。若 `accept_fix1.out` 的实跑确实包含本轮这 2+7 行改动，则 `test_page_paint_metric` 的 5 条应含新用例；由于验收输出的文字只给出文件级计数，该点建议调度方以新用例名单独复跑确认一次。

## “断言未动”声明

本改动只新增一条用例，未修改、未删除、未弱化任何既有断言，未新增 skip。

## 需裁决事项

1. **新增用例对本 bug 没有判别力**：`app_logging.timed`（`app_logging.py:66`）继承 `contextlib.ContextDecorator`，其 `__call__` 通过 `self._recreate_cm()` 返回并按 `functools.update_wrapper` 复制属性，因此外层装饰器无论如何都能把 `show` 的 `__name__` 与 `__wrapped__` 透传到 `Desktop.show` 上。把 `@functools.wraps(func)` 删掉，新用例三条断言仍会全部通过——它测不到本 bug 的回归。建议（需授权）改为对 `_page_paint_timed` 本体直接断言（用哑函数装饰后检查 `__name__`/`__wrapped__`），或断言 `Desktop.show.__wrapped__.__name__ == 'show'`。本次按任务书未改测试。
2. 结果文件按任务书命名为 `tasks_round/tasks_round_pending_PERFFIX_result.md`，不含轮次号；正式编号与状态页补记由调度方按规则 27 处理。
3. `git diff` 显示 `desktop.py` 工作区为 LF、提交后变为 CRLF，仅提示、不影响内容；`import functools` 放在装饰器函数内而非模块顶部，属任务书指定的最小改动，功能无碍。

## 提交状态

未执行任何 git 写命令，未领号，未提交，未改 `project_status.md`。

## 独立验收（Claude，主工作区）

- 执行链：第一个执行方在其沙箱里跑 test_perf_baseline 的内存用例卡了约一小时没有收敛，调度方停掉后另派「只写结果文件」小任务，由 Codex group-4 两分钟产出本结果文件。代码改动（desktop.py +2、tests/test_page_paint_metric.py +7）来自第一次执行。
- 主工作区实跑：`run_selftests -k perf_baseline page_paint_metric app_logging` 27 条 0 红（32.0 秒，perf_baseline 9 条 27.2 秒）；`smoke_test` 通过；`smoke_test --architecture` 375 条仅 1 条红，即已知的「欠一次完整安全全量」后台补跑项。
- **先红（调度方补做）**：把 desktop.py 的 2 行临时撤回到 HEAD 状态再跑，`run_selftests -k perf_baseline page_paint_metric` 14 条中 2 个文件有红：新增用例 `AssertionError: 'wrapper' != 'show'`，test_perf_baseline.test_page_switch_does_not_force_the_tk_idle_loop 报 `'self.fit_content()' not found in '    def wrapper(self, index, ...'`；恢复补丁后全绿。
- **更正执行方的一条判断**：结果文件「需裁决事项 1」称新增用例对本 bug 没有判别力、删掉 `@functools.wraps` 后仍会通过。经上述变异测试证实**不成立**——撤掉后该用例确实变红（`'wrapper' != 'show'`），无需改测试。
- 范围：恰为 desktop.py 与 tests/test_page_paint_metric.py 两个文件，未夹带用户的 AGENTS.md 与 程序/Tencent/。断言未动，未新增 skip。
