# R4284 REL-14：兼容性——DPI 感知与多显示器、1366×768 与 4K 缩放布局、中文与含空格路径、最低系统版本（兼容性轮·续做）
<!-- round-evidence: {"commit_base": "03d49adc", "credential_hits": 0, "evidence_sha256": "9c15d69ed52ad370", "exit": 0, "failed": 0, "passed": 34, "round": 4284, "tests": "run_selftests.py -k desktop_launcher projects"} -->

## 三问
- 轮次类型：§3.6 兼容性轮（卡面 REL-14，波次 W2，车道 `codex/rel-14`，基准 `03d49adc`；续做卡，上一位执行者留有 4 个文件的未提交草稿）。
- 测试跑了吗、三个基线过了吗：跑了卡面三条验收。`run_selftests.py -k desktop_launcher projects` 34 条全绿退出码 0；`run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 34 条全绿退出码 0；`smoke_test.py --architecture` 700 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求，且禁止运行卡面未写的命令）。
- 欠账少了吗：少了「05 号规格 U-1 DPI 感知标不满足」这条发布就绪欠账；无新增欠账。

## 续做现场核对（开工第一步）
- `git status --porcelain` 输出与卡面预期 4 行逐行一致（`启动漫剧制作助手.pyw`、`程序/desktop.py`、`程序/docs/specs/05_UIUX与交互规范.md`、`程序/responsive_ui.py`，中文路径显示为八进制转义，按行末文件名对照）。
- `git log -1 --format=%h` = `03d49adc`；`git rev-parse --abbrev-ref HEAD` = `codex/rel-14`。
- 旧草稿位于 `.agent-tmp/rel-14-old-drafts/`（只读参考，未复制回 `程序/tests`、未改动 `.agent-tmp` 下任何文件）。

## 改前红
续做现场已有实现（上一位执行者的产品草稿），本会话在草稿上按卡面重构并补测试，未观察改前红——按接口契约第一条如实记录，未为看红回退产品代码。

## 改动内容（文件:行号）
上一位执行者草稿处置：保留 `desktop.py` 的 WM_DPICHANGED 接线（`desktop.py:29` import、`desktop.py:320` `watch_dpi_change(win,self._layout_all)`，diff 仅此两处，在卡面边界内）；保留 `responsive_ui.py` 的 `watch_dpi_change`/`_widget_dpi_scale`（`responsive_ui.py:782-815`），删除其草稿里的 `apply_dpi_awareness()`、DPI 常量与 `import os`（按卡面 DPI 实现必须落 `desktop_launcher.py`）；根 `.pyw` 草稿里内联的 `_min_os_items()` 与 DPI 块删除，改调 `desktop_launcher` 两个函数。

- `程序/desktop_launcher.py:29-41`：REL-14 常量（`_DPI_CTX_PER_MONITOR_V2=-4`、`_SHCORE_PER_MONITOR=2`、`_SHCORE_SYSTEM=1`、`_MIN_OS_MAJOR=10`、`_MIN_OS_BUILD=17763`）与 `_dpi_awareness` 幂等状态。
- `程序/desktop_launcher.py:44-91`：`enable_dpi_awareness()`——`SetProcessDpiAwarenessContext(PMv2)` → `shcore.SetProcessDpiAwareness(2/1)` → `user32.SetProcessDPIAware` 三级逐级降级，每级独立 try/except 只记 `app_logging.swallowed()` 不抛错；`done` 先置位保证幂等（重复调用含失败结果都不重试）；`os.name != 'nt'` 返回 None；建 Tk 前可调。
- `程序/desktop_launcher.py:94-120`：`min_os_items()`——非 nt／版本读不出／达到下限返回 `[]`；低于 Windows 10 1809（build 17763）返回一条 `Severity.FATAL`、`scope='config'`、`code='os-below-minimum'` 的 `Diagnostic`（message 含「1809」，remedy 提示升级）。
- `程序/desktop_launcher.py:125`：`launch()` 开头调 `enable_dpi_awareness()`；`:133-136` selfcheck 分支把 `min_os_items()` 追加进 items 并 `record_selfcheck`（FATAL 与其他自检项同路走 `notify_startup_fatal`）。
- `启动漫剧制作助手.pyw:45` `import desktop_launcher`、`:47` `desktop_launcher.enable_dpi_awareness()`（早于 `:68-69` 的 `import tkinter as tk`／`window=tk.Tk()`）、`:51-54` `_os_items=desktop_launcher.min_os_items()` 追加进自检并 `record_selfcheck`；其余 diff 已清空，净 +9 行。
- `程序/responsive_ui.py:782-815`：`_widget_dpi_scale()`（`winfo_fpixels('1i')` 实测，量不到返回 None）与 `watch_dpi_change(widget,on_change)`（`<Configure>` 绑定、实测值真变才回调、返回 check 供测试驱动）；不新造布局体系。
- `程序/desktop.py:29,320`：上一位执行者草稿原样保留——import 加 `watch_dpi_change`，`watch_window_resize(win)` 后一行接线到既有 `_layout_all` 整页重排。
- `程序/tests/test_desktop_launcher.py`（新建，357 行）：桩替换 `ctypes.windll` 三入口断言调用顺序与逐级降级、全失败/缺 API/windll 异常/非 Windows 均返回 None 不抛、幂等（重复调用与失败后重试都不再触碰入口）、无 Tk 可调用（断言 `tkinter._default_root is None`）；`min_os_items` 四组版本边界（7601/17134/17762 → FATAL；17763/19045/22631/22000 → 空；读不出/非 nt → 空）；`watch_dpi_change` 桩控件回调行为；AST 断言根 `.pyw` 里 `desktop_launcher.enable_dpi_awareness()` 调用行早于第一处 `tk.Tk()`；`desktop.py` 接线源码断言；真 Tk 的 FlowBar 480px 窄宽换行不裁切（经隐藏桌面运行器）；`DESKTOP_LAYOUT` 对 1366×768 的 token 级回归。
- `程序/tests/test_projects.py:11` 补 `from contract import stage_path_service`；`:146-209` 新增 `ProjectPathCompatTests` 三个用例（只新增方法）：`项目 库 (测试)` 项目库下建项目＋登记表路径往返一致＋重读服务一致；`stage_path_service` 在含中文/空格/括号项目目录下 write/read 目录与文件路径往返；`diagnostic_state.record_degradation` 在含空格/括号目录写诊断状态文件。
- `程序/docs/specs/05_UIUX与交互规范.md:14,16,173`：U-1 与高 DPI/4K 行改为已实现，锚点由旧草稿名 `responsive_ui.apply_dpi_awareness()`／`tests/test_dpi_awareness.py` 更正为 `desktop_launcher.enable_dpi_awareness()`／`tests/test_desktop_launcher.py`。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k desktop_launcher projects`（最终代码态）：退出码 0，尾部原文：
   ```text
   共 34 条用例，96.7 秒；0 个文件有红
   最慢 3 路工作单元：
     test_projects                 0.3 秒 / 10 条
     test_desktop_launcher#1       0.1 秒 / 15 条
     test_desktop_launcher#2       0.0 秒 / 9 条
   实际跳过 0 条用例：本机没有任何登记位被跳过
   增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
   最近 5 轮自检中位基线：17.5 秒

   ALL TESTS PASSED
   ```
   （含 Tk 用例由运行器自动迁到隐藏桌面；跨树 GUI 令牌排队约 60 秒属正常等待。）
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（最终代码态）：退出码 0，尾部原文：
   ```text
   共 34 条用例，1.8 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
   最近 5 轮自检中位基线：39.5 秒

   ALL TESTS PASSED
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（最终代码态）：退出码 0，尾部原文：
   ```text
   ----------------------------------------------------------------------
   Ran 700 tests in 237.966s

   ✅ 架构治理测试：tests/architecture
   OK
   ```
   （首轮曾红 1 条：`test_complexity_ratchet.test_nesting_does_not_grow` 报 `desktop_launcher.py::enable_dpi_awareness 6 层 > 上限 5`——shcore 分支的 `elif` 被 AST 计为第 6 层嵌套；已把 `elif aware(_SHCORE_SYSTEM) == 0` 改为 `if level is None and aware(_SHCORE_SYSTEM) == 0`（`desktop_launcher.py:75`），调用序列与语义不变，复跑全绿。）
4. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4284`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4284: REL-14 修复" ..\启动漫剧制作助手.pyw desktop_launcher.py desktop.py responsive_ui.py tests\test_desktop_launcher.py tests\test_projects.py docs\specs\05_UIUX与交互规范.md tasks_round\tasks_round_4284_result.md --tests desktop_launcher projects`（文件参数按 `程序` 相对路径，根启动器写 `..\启动漫剧制作助手.pyw`；改了 `.py` 带 `--tests`）。
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。

## 未验证项 / 未核实
- 全量 `run_selftests.py --all --safe` 与默认冒烟未跑（卡面验收未要求且禁止运行卡面未写的命令）。
- 真实多显示器跨屏、4K 实机缩放效果未验证（卡面注明只能实机验证，写入 REL-12 实机清单；本卡只做 `winfo_fpixels` 实测变化触发重排的桩级与 token 级断言）。
- 「引号」路径用例未做：ffmpeg 等外部进程一律经 `infra/workflow_process_registry.spawn` 传参数数组、不拼命令行，现状已安全（卡面 14B 说明，只记录不补测）。
- `desktop.py` 的 `_layout_all` 在 1366×768/4K 下的逐像素观感未人工目检（只跑了 token 级与 FlowBar 几何断言）。
- 未合入、未 push；合入由合并车道按正式流程处理。

## 卡外发现（只记录，未顺手修）
- 无新增；`05` 号规格第 12 行仍标「最小尺寸 800×600 不满足」属 U-2 既有待办，与本卡无关。

## 被拒绝的命令（原文）
- `Get-ChildItem -Recurse .agent-tmp`（车道根递归列举；此前会话已拒过一次，本次未重试，改用窄范围命令完成取证）。
- `Get-ChildItem tasks_round -Filter 'tasks_round_*_result.md' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name`（列结果文件；改用文件检索工具读 `tasks_round_4257_result.md` 模板）。
- `Get-ChildItem tasks_round -Filter 'tasks_round_4*_result.md' | Select-Object -ExpandProperty Name`（同上，未重试）。
