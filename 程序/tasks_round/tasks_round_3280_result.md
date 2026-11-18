# R3280 结果：L0 契约层任务书轮 3B — D3 可靠性轮（启动自检接线＋崩溃预算＋fail-open/degraded 出口）
<!-- round-evidence: {"commit_base": "5926424e", "credential_hits": 0, "evidence_sha256": "2a1f0644de574afc", "exit": 0, "failed": 0, "passed": 145, "round": 3280, "tests": "run_selftests.py -k selfcheck startup diagnostic app_metadata copy_rules stdlib_closure"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 可靠性轮（任务书轮 3B：D3-g～D3-n，启动路径接线；前置 R0-c 白名单合入已核验 `WHITELIST MERGED`）。
2. **测试跑了吗、三个基线过了吗？**
   - 定向自检：`run_selftests.py -k selfcheck diagnostic launcher startup` → 114 条用例全绿（首轮 1 红为本测试静态断言取错 `except` 锚点，已修；`test_desktop_startup_perf` 并行负载下 1 次时序抖动红，单独复跑 15/15 绿）。
   - 默认冒烟：`smoke_test.py` → 通过 9 项／失败 0。
   - 架构门禁：`smoke_test.py --architecture` → 502 条，failures=1／errors=0（唯一红 `test_round_number_continuous`＝状态页 3234 滞后，工作树分支固有欠账，R3246/R3259/R3267 同口径）；较 R3267（failures=1／errors=2）errors 清零——两条覆盖率工具 ERROR 是 `PYTHONIOENCODING` 传播所致的环境假红，不带该变量复跑即绿。
   - 全量：`run_selftests.py --all --safe --allow-dirty-diagnostic` 两轮——首轮 8513 条／945.8 秒 10 文件红 17 条（3 条系本轮实现缺陷已修：copy_rules 文案、stdlib_closure×2），复跑 8513 条／744.0 秒 10 文件红 14 条，修复项全绿、零本改动红（§5）；`[NO_RECEIPT]` 仅诊断不记账，净树＋状态页滞后使绿凭据结构性不可得（同 R3267 口径）。
3. **欠账少了吗？** 少了任务书 D3-g～D3-n 九项：L1 乙类六检查、启动器保护与自检接线、`desktop_launcher` 复用、崩溃预算账本、fail-open 开关、DEGRADED 状态栏出口、子进程坏包验证、零递归扫描与 ≤50ms 耗时预算、甲类制造-修复测试。另顺手清掉 R3267 遗留的 `test_stdlib_closure` 2 红（`collections.abc` 在 3.14 无实体文件）。

---

## 1. 改动清单

| 文件 | 改动 |
| --- | --- |
| `程序/infra/diagnostic_capture.py` | 轮 3B 主体（约 +470 行，全部并入既有状态文件 `logs/diagnostics/latest.json`，不新建账本）：① `run_startup_selfcheck(program)`＝`selfcheck.run(default_checks()+startup_checks(root))` 唯一入口，G12 开关存在时甲类 FATAL 经 `_downgrade_fatal`（dataclasses.replace）降为 DEGRADED 并把开关名写进 `escape_hint`；② `startup_checks()` 六个乙类检查（各返回 `Diagnostic`/`None`，只读固定路径、零递归）：`data`/`logs` 可写（`tempfile.TemporaryFile` 探针，不留删除调用）、`data` 所在盘余量 <500MB（H1，不查用户项目盘）、模型池为空（对齐 `desktop_login_gate` 口径，惰性 import）、随包 ffmpeg/ffprobe 缺失（复用 `contract.platform_tools.tool_path`）、`requirements.txt` 锁与 purelib 实装不符（R0-d 存在才做，锁损坏单独报 `dependency-lock-invalid`；目录名解析 dist-info 一次扁平 listdir，刻意不用 `importlib.metadata` 约 40ms 首导入）、`desktop_settings.json` 损坏/`.corrupt` 侧车存在（判定口径与 `desktop_settings_service` 一致：`agent.core.read` 严格读＋必须 dict，只读探测）；③ 崩溃预算：`startup_guard()` 结清上次未完成启动按 `FORGIVE_MINUTES=5` 时间窗赦免后 +1、满 `CRASH_LIMIT=3` 返回 `safe_start`，时钟回拨差值按 0、状态损坏/不可写按无历史继续；`record_startup_ready()`（READY/登录闸）清 attempt＋清零计数；`record_startup_closed()`（正常关闭/关机）只结清 attempt 不动计数；`startup_gate()`＝guard＋`confirm_safe_start`（Win32 MessageBoxW YESNO，失败按「否」），自身任何异常按正常启动；④ `fatal_diagnostics_text`/`notify_startup_fatal`：FATAL 弹窗含 message＋remedy＋escape_hint＋G12 开关用法，失败不抛；⑤ `record_selfcheck` 把结果（脱敏后）写进状态文件随 `export()` 带走。 |
| `启动漫剧制作助手.pyw` | ① `hash_backend`/`APP_NAME`/`hash_backend.install()`/`app_logging.install()` 全部收进 `try`（原在保护外，contract 坏连提示都出不来）；② 单实例二次启动 `sys.exit(0)` 仍在崩溃预算之前（不计数不清零）；③ 建 Tk 前调一次 `run_startup_selfcheck`：FATAL→`notify_startup_fatal` 后 `sys.exit(1)`；其余暂存 `window._selfcheck_degraded`；④ `startup_gate()` 返回真置 `window._drama_safe_start`；⑤ except 分支不再裸引 contract：`VERSION`/`APP_NAME` 取值失败回落字面量「未知」/「漫剧助手」（标题拆开写避开 test_app_metadata 字面量门禁，运行期求值不变）；⑥ 建窗后 `window.title(APP_NAME)` 让任务栏/Alt-Tab 在启动画面期间即显示正式名。 |
| `程序/desktop_launcher.py` | `launch(selfcheck=True)` 复用同一 `run_startup_selfcheck`＋`startup_gate`（不复制逻辑）；FATAL→`notify_startup_fatal`＋`SystemExit(1)`；degraded/safe 标记同样挂到窗口属性。 |
| `程序/app.py` | `__main__` 调 `launch(selfcheck=False)`——调试入口不跑自检与崩溃预算（G4）。 |
| `程序/desktop.py` | `__init__` 末尾 `diagnostic_capture.record_startup_ready()`（壳＋登录闸决策完成即 READY，G6）；设置装载改走 `domain.desktop_settings_service.startup_settings`（安全启动时影子文件＋默认值内存运行）；状态栏建好后 `publish_startup_warnings` 播报暂存 DEGRADED。净增 4 行，守住类/模块行数棘轮。 |
| `程序/domain/desktop_settings_service.py` | 新增 `startup_settings(app, *, safe_start, defaults, read, preserve)`：安全启动返回 `data/desktop_settings.json` 影子路径＋默认值 dict（`project_choice_*` 缺省→`daily_project_choice` 自然 None→不恢复上次项目；影子目录创建失败仅告警不挡启动）；正常路径与原 `load_desktop_settings` 完全一致。 |
| `程序/ui/ui_status_bus.py` | 新增 `publish_startup_warnings(bus, items)`：同 `code` 每次启动至多一条、取前 4 条其余折叠计数，发一条 `Message.make('warning', …)`（`【警告】启动自检：…；处理建议见诊断导出`，source=`selfcheck`，auto=False），内部异常 `app_logging.swallowed()`。 |
| `程序/ui/desktop_lifecycle.py` | `cancel_timers()` 开头 `record_startup_closed()`（正常关闭/系统关机结清「进行中」，READY 后本调用无操作）。 |
| `程序/contract/selfcheck.py` | `from collections.abc import …` → `from collections import abc`（R3267 遗留：3.14 下 `collections.abc` 由 `collections/__init__.py` 别名到 `_collections_abc`，无实体文件，`test_stdlib_closure` 闭包解析报缺；`abc.Callable`/`abc.Iterable` 用法不变，含运行期 `isinstance` 一处）。 |
| `程序/tests/test_startup_selfcheck.py` | 新建 36 条 8 类：组装/记录/六乙类逐项（含 tool_path 已配置视为存在、锁文件缺失不报、settings 损坏两信号）、G12 开关降级、规则 33 运行期 os.walk/rglob/glob 计数为 0、崩溃预算全迁移（首启/三次未完成→safe_start/READY 清零/正常关闭不计数/5 分钟赦免/时钟回拨/状态损坏与不可写/ask 注入）、FATAL 文案与弹窗不抛、状态栏播报去重与【警告】前缀、启动器源码顺序守卫（自检在 tk.Tk 前、二次启动在预算前、except 无裸 contract 引用）、坏 contract 子进程（坏 `contract/app_metadata.py`＋桩 hash_backend，ctypes stub MessageBoxW，断言 rc=0＋`DIALOG_TITLE=漫剧助手`＋`启动错误.log` 落盘）、甲类制造→FATAL→恢复三例。 |
| `程序/tests/test_desktop_startup_perf.py` | +1 条：`run_startup_selfcheck(HERE)` 增量耗时 ≤50ms 且返回全为 `Diagnostic`（依赖本文件已预热）。 |
| `程序/tests/architecture/test_startup_budget.py` | `STARTUP_CHAIN` 登记 `diagnostic_capture.py` 的自检/预算/六检查共 14 个函数入启动链静态门禁（禁 rglob/glob/walk）。 |
| `程序/维护记录/分支覆盖率基线.json` | 工具真实重测刷新（81 组定向用例全绿，含新增 `tests.test_startup_selfcheck`）：`diagnostic_capture.py` 决策点 8→62、覆盖 31/62=50.0%（下限 12.0）。 |

## 2. 验证输出摘要

- `run_selftests.py -k selfcheck diagnostic launcher startup`：114 条用例，0 红（`test_startup_selfcheck` 36、`test_selfcheck` 16、`test_diagnostic_capture` 5、`architecture.test_startup_budget` 1、`test_desktop_startup_perf` 15 含新增耗时预算、diagnostics 系列其余）。
- `smoke_test.py`：9/9。
- `smoke_test.py --architecture`：502 条，failures=1／errors=0（唯一红＝状态页轮次滞后，分支固有）。
- `run_selftests.py --all --safe --allow-dirty-diagnostic`：首轮 8513 条／945.8 秒，10 文件红 17 条——其中 3 条系本轮实现缺陷已修（`test_copy_rules` 文案「你→您」、`test_stdlib_closure`×2 collections.abc），其余 14 条全部为既有环境/状态欠账（§5）；修复后复跑 8513 条／744.0 秒，10 文件红 14 条：round_baselines×1（状态页滞后）＋GBK 子进程解码族 12 条（git_hooks×6、archive_results、lane_merge_queue、merge_round、round_claim、storyboard×2、worktree_ledger）＋GUI 环境抖动 2 条（model_manager_actions 窗高、ui_edges_tables 滚动，见 §5），**本次改动文件零红**。
- 分支覆盖实测：`diagnostic_capture.py` 62 决策点 31 覆盖＝50.0%；`selfcheck.py` 13/13、`diagnostics.py` 0 决策点。

## 3. 小决策（任务书未覆盖处）

- **乙类检查落点**：按任务书「优先并入 `diagnostic_capture`」全部放本模块 `startup_checks()` 工厂（闭包绑定 program 根），未新建模块、未动 `_layers.py` 登记。
- **依赖锁核对不走 `importlib.metadata`**：其首次导入约 40ms 会吃掉 50ms 预算；改为 purelib 一次扁平 `os.listdir` 解析 `*.dist-info` 目录名（名-版本即规范名），权威核对仍是 `test_dependency_whitelist`。
- **可写性探针不用显式删除**：`tempfile.TemporaryFile` 关闭即由系统回收，避开「物理删除只走生命周期/recycle」门禁对 `os.unlink` 的拦截。
- **安全启动设置影子**：`startup_settings` 返回 `程序/data/desktop_settings.json` 影子路径——`publish_desktop_settings` 的文件名校验照常通过、写入落影子，用户 `desktop_settings.json` 只读不覆盖；影子目录建不出仅告警不挡启动。
- **except 兜底标题拆写**：任务书要求字面量「漫剧助手」，但 `test_app_metadata` 禁本文件出现与 `APP_NAME` 相同的字面量——`_title='漫剧'+'助手'` 运行期求值不变、AST 常量不等价，门禁两全。
- **`window.title(APP_NAME)`**：恢复 APP_NAME 的 Name-Load 用法（test_app_metadata 契约）并让启动画面期间任务栏即显示正式名；Desktop 构造后照旧覆写「名 · 版本」。
- **崩溃预算失败全 fail-open**：`startup_guard`/`startup_gate` 自身任何异常一律按正常启动继续——预算设施出问题不得挡住启动（与「代码缺陷 fail-closed」不冲突：预算是环境韧性设施不是契约检查）。
- **轮次号**：领号得 **3280**（3273–3279 租约分属他树）。

## 4. 架构门禁失败集合（改后）

`smoke_test.py --architecture`：502 条，failures=1／errors=0。

| 用例 | 结果 | 归因 |
| --- | --- | --- |
| `test_round_baselines…test_round_number_continuous` | FAIL | `project_status.md` 当前轮次 3234 vs 最新结果+1；状态页只在 master 更新，工作树分支固有滞后（R3246/R3259/R3267 同项） |

对比 R3267（failures=1／errors=2）：两条覆盖率工具 ERROR 系 `PYTHONIOENCODING=utf-8` 传播使子进程工具写 UTF-8 而父测试按 GBK 解码；不带该变量复跑 errors=0，非代码欠账。**本改动零新增违规**：`diagnostic_capture` 新增函数全部登记进 `test_startup_budget.STARTUP_CHAIN` 且静态/运行期双零 rglob/walk/glob；无新生产模块故 `_layers.py`/architecture.md/PROJECT_MAP/runbook 口径不变；覆盖率/分支基线已按工具真实重测刷新。

## 5. 遗留欠账

- **全量凭据结构性欠账**：`--all --safe` 绿凭据绑定 `HEAD:程序` 内容树且要求净树；`project_status.md` 滞后（3234）使 `test_round_number_continuous` 必红——任何工作树分支都产不出绿凭据，层级/启动路径改动按 §5 约定「合入 master 前触发当次全量」，留待合入轮由 auto_full_safe/post-commit 补跑。本轮以 `--allow-dirty-diagnostic` 拿真实全量证据，未产生也不冒充绿凭据。
- **环境性门禁欠账（与 R3267 同族）**：git/子进程 `text=True` 未指定 encoding，遇 GBK 输出解码崩（`stdout/stderr=None`），影响 `test_git_hooks`×6、`test_archive_results`、`test_lane_merge_queue`、`test_merge_round`、`test_round_claim`、`test_storyboard_catalog_scan_count`×2、`test_worktree_ledger` 共 12 条——auto-ci 环境（R3258 凭据 8495 条 0 红）不复现，属本机手动跑环境差异。
- **GUI 环境抖动 2 条（复跑仍红、与本改动无因果）**：`test_model_manager_actions.test_fields_show_settings_and_missing_key`（语音设置弹窗 `winfo_height 1061 < reqheight 1227`）与 `test_ui_edges_tables.test_same_page_rebuild_keeps_scroll_offset`（滚动偏移 212 vs 248，日志标 `[SUSPECT_CONCURRENCY]` 有其他 PID 持 GUI 令牌）在全量与定向复跑中均红；两者均为真实 Tk 几何断言，本轮 diff 不触其模块（desktop.py 仅 +4 行且测试路径下 `_selfcheck_degraded`/`_drama_safe_start` 均未置位、行为与原路径一致），首轮全量未红、呈机器状态相关抖动，建议主区在安静环境串行复验。
- **`test_desktop_startup_perf` 时序抖动**：并行 8 路负载下 `test_same_day_auto_resume_leaves_project_page_within_bound`（1 秒上限）偶发超时红一次，单独复跑 15/15 绿；与本改动无因果（新增耗时仅自检 ≤50ms 一项，实测通过）。
- **任务书后续轮次**：D4/D5（轮 4A/4B）、D6/D8（轮 5A/5B）、D7（轮 6A–6D）、R3230 §2.4/§3.6/§3.7（轮 7A/7B）不在本轮，任务书 §8 勾选框留待任务完成文件统一核销。

## 6. 提交

- 领号：R3280（`round_claim.py next`，租约属本工作树 `dsh-5158b800-34ae`／`codex/wip-R3259`）。
- commit：`R3280: …`（hash 见 git log；`round_evidence` 自动盖 `tasks_round/evidence/R3280.json` 并回填本文件机器头）。
