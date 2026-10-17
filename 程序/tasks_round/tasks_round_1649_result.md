# R1649 修复轮：P2-1 分层僵尸登记名 ＋ P2-2 静态卫生范围声明 ＋ P2-3 关窗重排竞态

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。范围＝`tasks_round/tasks_round_1645_result.md` J 节清单 P2-1／P2-2／P2-3 三项；三项同属「静态边界＋架构门禁」类改动，按 §2.5 规则 27「同类必须批量成轮」并为一轮。不改契约、不搬目录、不重命名、不删既存文件。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；定向 6 模块 **29/29**；棘轮／卫生 8 模块 **24/24**；架构门禁 **362/362（290.9 秒，本轮实测，改前 359）并绿**。**未跑全量**（见第 3 问）。全量安全回归按 §5 由 master 后台补跑（本轮改了风险路径 `tests/architecture/_layers.py`，提交后由 post-commit 钩子触发）。
3. **project_status.md 的欠账少了吗？** **没有，反而 +1**。改前实测 `scripts/auto_full_safe.py --status`＝「上次全量 R1624；最新 R1648；其间改过源码的轮次 4（门禁线 8）；主干 True；后台触发 True」。本轮改了生产源码（含风险路径 `_layers.py`）⇒ 欠账 4→5，未到门禁线 8，如实记录，不冒充已清偿。**注**：收尾时观测到 R1648 的 post-commit 后台全量正在运行（`.git/full-safe-selftest.lock`＝`{"pid": 32532, "round": 1648}`，进程存活），故本轮提交需等该锁释放；若后台全量转绿，欠账将由真实凭据清零，本行以提交时刻的实测为准。

## 指令冲突记录

本会话顶部重新下发的提示描述的是「结构治理轮（只读诊断）」，并附「禁止修改任何 .py、配置文件或用户项目数据」；该只读诊断已由 R1645 交付（缺陷与缺失清单 A–M），且当前 active 用户目标为「按顺序完成 `tasks_round_1645_result.md` 清单」。本轮按 active 目标执行清单的 P2-1／P2-2／P2-3，写入范围限于清单项及其配套门禁／登记／文档，未扩大。冲突与取舍在此显式登记，供用户裁决。

## A 改动

1. **P2-1 分层登记僵尸名**（`程序/tests/architecture/_layers.py`）
   - 删除 3 个登记名：L3 的 `workflow`、L3 的 `project_storage`、L4 的 `asset_detail_ui`。
   - 只读复核（本轮实测）：全仓 AST 与文本检索对三者均无 `import`／`from … import`／属性访问／字符串引用；`程序/` 根目录无同名 `.py`；`architecture.md` 第 3 节表格从不曾列出它们（现行名分别是 `asset_detail` 与 `workflow*` 家族）。⇒ 初版登记表里没有采用方的历史残名。
   - 新增模块级注释声明不变量；不并入 `historical_name_audit`（该项要求指认**现行职责入口**，这三者已无采用方，无从指认）。
2. **P2-1 门禁**（`程序/tests/architecture/test_layers.py`）
   - 新增 `test_registered_names_resolve_to_a_file_tool_or_historical_entry`：登记表每一名须满足「有实体 `.py` ∨ 有 `<name>/__init__.py` ∨ 在 `TOOLS` ∨ 在 `historical_name_audit.entrypoints`」。改前实测红出 3 个僵尸名，改后绿。
3. **P2-2 范围声明**（`程序/tests/architecture/test_static_hygiene.py`）
   - 新增 `test_scan_scope_excludes_non_maintained_skill_packages`：断言 `skills` 在 `_EXCLUDED_PARTS`，且 `_all_sources()` 不含任何 `skills/` 路径。把「门禁绿 ≠ 全仓无此类问题」写成可执行声明（K-3）。
4. **P2-2 无效转义：判为本仓边界外，如实登记而不是硬改**（`程序/skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239`）
   - 先做了修复（`"[\[【]?"`→`r"[\[【]?"`），随后发现该路径**不是本仓文件**：`git ls-tree HEAD` 显示 `程序/skills/00全流程SKILL/AIGC创作全流程` 是 **mode 160000 的 gitlink**（嵌套 Git 仓库，`main` 分支，HEAD `1a43ae5`，提交内容是该外部包的赞助商／落地页，无 `.gitmodules`）。`test_static_hygiene` 的模块说明本就写明「`skills/` 是独立版本化的外部技能包（含 git 子模块），不属本仓维护……既检测不属自己的代码、又无法提交修复」。
   - 按「范围不扩张 + 一个改动一个仓库」，**整体回退**该修改（含把工作树行尾恢复成该仓库 `core.autocrlf=true` 期望的 CRLF，使嵌套仓库与父仓库都回到干净状态，实测 `git status` 不再报该文件与子模块）。
   - 结论：本仓只能登记不能修；已把该处登记为**上游包归属项**（见 D 与 `维护记录/优化待办队列.md`），本项在本仓内**只完成「范围声明＋登记」半边**。
   - 关于 `tasks_round_1645_result.md` P2-2 的判据「门禁运行输出不再出现该 SyntaxWarning」：本轮**未能复现该告警的产生点**——负向检索显示本仓没有 `compileall`／`py_compile`、没有 `spec_from_file_location`／`exec_module` 动态加载、没有任何测试或配置引用 `check_package`，而 `_all_sources()` 又排除 `skills/`，故本仓门禁不应编译该文件。此判据在本仓范围内**无可验证对象**，如实记为未复现，不写成已消除。
5. **P2-3 关窗重排竞态**（`程序/desktop_script_pages.py`）
   - 新增模块级 `_safe_after(widget, delay, callback)`／`_safe_after_idle(widget, callback)`，各自 `try/except tk.TclError` 后返回 `None`。
   - `watch_script_quality.poll` 的 2 处重排、`content_box` 的 `await_preview` 尾部重排与 `after_idle(append_chunk)` 全部改走这两个入口；`await_preview` 既有的 2 处内联守卫保留不动。
   - 选择辅助函数而非内联 `try/except` 的理由：`test_function_size_ratchet` 对 `desktop_script_pages.py` 的 `script_structure`(上限 251)／`content_box`(上限 187) 有登记上限，内联会让两函数各 +6 行而超限（实测红）；下沉到模块级辅助函数后两函数回到 251／187，未抬高任何上限。规则 28 复核：既有 `tk_timers.repeat()` 的语义是「持续重复刷新直到控件销毁」、由 `<Destroy>` 自动取消；而这里的 `poll` 靠自身提前 `return` 停止重排（ticket 变更、3600 秒超时两条路径），改用 `repeat` 需把两条停止路径都改成显式 `stop()` 并会残留空转定时器，超出 P2-3 的最小闭环，故仍按 P2-3 原文「与 `await_preview` 同构加 `try/except tk.TclError`」实现。
6. **P2-3 门禁**（`程序/tests/architecture/test_migrated_ui_boundaries.py`）
   - 新增 `ViewTimerLifecycleTests.test_timer_reschedules_are_guarded_against_a_destroyed_window`：AST 断言 `desktop_script_pages.py` 每个 `.after(`／`.after_idle(` 调用点都落在「能捕 `tk.TclError` 的 `try`」内。改前实测红出 `:136`、`:137`、`:417`、`:451` 四处，改后 0 处。
7. **架构文档**（`程序/architecture.md` §3）新增 R1649 段，登记 P2-1 的删除依据、新增不变量与「不并入 historical_name_audit」的理由。

## B 验证（本轮实测命令与结果）

- `python -B -m unittest tests.architecture.test_layers …test_remove_authority`（6 模块）→ `Ran 29 tests` **OK**（29.257 秒）。
- `python -B -m unittest tests.architecture.test_function_size_ratchet …test_todo_comment_snapshot`（8 模块）→ `Ran 24 tests` **OK**（40.347 秒）。
- `python -B smoke_test.py` → **通过 8 项 / 失败 0 项**。
- `python -B smoke_test.py --architecture` → `Ran 362 tests in 290.931s` **OK**（改前 359；本轮新增 3 条用例：`test_layers` 1、`test_static_hygiene` 1、`test_migrated_ui_boundaries` 1）。
- **失败并纠正的记录**：首次架构门禁 1 红＝`test_function_size_ratchet`（`desktop_script_pages.py::content_box 193 > 187`、`::script_structure 257 > 251`），由 P2-3 的内联守卫引起；按 A-5 下沉为模块级辅助函数后复跑全绿。未改门禁、未抬上限。
- **回退记录**：P2-2 的源码修复按 A-4 整体回退；回退后 `程序/skills/…` 嵌套仓库与父仓库 `git status` 均不再显示该文件／子模块变动（实测）。

- **后台全量红（本轮触发，非本轮引入）**：R1648 提交后 post-commit 自动全量在 `.wt/ci` 检出 `a9a3aa6` 运行 748 秒、退出码 1，唯一红＝`tests/test_distribution_selfcheck.py::test_manifest_covers_every_file`：`['程序/data_model.md','程序/runbook.md','程序/task_states.md']` 未在 `distribution_manifest.md` 里声明保留或排除。这三个文件由 **R1625**（Q11 文档三件）新增，而 `test_distribution_selfcheck` 只在全量里跑，故自 R1624 之后首次全量才暴露。**非本轮引入、非本轮范围**；按 §8.6 只记录不修（修＝在 `distribution_manifest.md` 补 3 行声明，量级为 1 行级改动，建议另立一轮或并入 P2-4… 之后的文档轮）。这也是本次后台全量未转绿、欠账 4/8 未清零的原因。

## C 完成判据对照

| 清单项 | 判据（原文） | 结果 |
| --- | --- | --- |
| P2-1 | 登记表每个名字满足「有实体文件 ∨ 在 `TOOLS` ∨ 在 `historical_name_audit`」并由门禁断言 | ✅ 3 个僵尸名删除；不变量由 `test_layers` 新增用例断言并绿 |
| P2-1 | 先只读确认三者是否仍有采用方 | ✅ AST＋文本＋文件存在性三重检索，均无采用方（见 A-1） |
| P2-2 | 静态卫生测试显式声明排除范围 | ✅ `test_scan_scope_excludes_non_maintained_skill_packages` |
| P2-2 | 门禁运行输出不再出现该 SyntaxWarning | ⚠️ **未复现**：该文件属本仓外 gitlink 包，本仓门禁不编译它（负向检索见 A-4）；已在 `维护记录/优化待办队列.md` 登记为上游归属项 |
| P2-3 | 定向用例覆盖「销毁后重排不抛」或静态扫描断言该文件 `after(` 调用点均受 `TclError` 保护 | ✅ 静态 AST 断言，改前红 4 处→改后 0 处 |
| P2-3 | 顺带确认该轮询在销毁时停止 | ✅ 销毁后 `after` 抛 `TclError` 被 `_safe_after` 吞掉并返回 `None`，`poll` 不再重排（等价于停止）；未另加 `winfo_exists` 轮询判据（会撑大 `script_structure`），口径在 A-5 说明 |

## D 未做与局限

- **P2-2 只完成一半**：源码修复触及本仓外仓库，按范围不扩张原则回退；只保留本仓内的范围声明与登记。上游包若要修，需在该嵌套仓库单独提交并同步父仓库 gitlink（本轮不做）。
- **未跑全量**（欠账 5/8，未到门禁线）；改风险路径 `_layers.py` 已让 §5 的后台补跑条件成立，交由 post-commit 钩子；收尾时该后台全量（R1648 触发）仍在运行，提交须等锁释放。
- P2-3 的守卫只覆盖 `desktop_script_pages.py`；其它页面用 `after_cancel` 在销毁时撤销定时器（另一条等价路径），本轮不动，也不把门禁扩成全仓（会红出大量既有合规写法）。
- `poll` 回调体内部（`show_script_quality`／`self.status.set` 等）在销毁瞬间仍可能抛 `TclError`（由 `app_logging` 兜底），属范围外，本项只收口「重排定时器」这条 P2-3 明确的缺陷。
- P2-4…P2-8 未动。
- 未更新接力文件（结果文件已记录完成／未完成／验证／下一步）。
- 提交：按 §2.6 一次性 `git add`＋`git commit`，提交信息以 `R1649: ` 开头；hash 见 `git log`（本文写入时尚未提交）。
