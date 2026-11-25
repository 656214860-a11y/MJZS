# R4451 结果：FIX-FULLSAFE-UI-CONTRACTS-A 清零主干 5 个测试文件合计 5 条既有红（修复轮 §3.2＋契约同步 §2.4）
<!-- round-evidence: {"commit_base": "1abd6d878", "credential_hits": 0, "evidence_sha256": "fda4cea49bf167d5", "exit": 0, "failed": 0, "passed": 188, "round": 4451, "tests": "run_selftests.py -k files_panel_stages script_undo_shortcuts script_zoom media_page_buttons timers"} -->

## 开头三问

1. **本轮类型**：修复轮（§3.2）＋测试契约同步（§2.4）。卡面 FIX-FULLSAFE-UI-CONTRACTS-A（波次 W2），车道 `codex/fix-fullsafe-ui-a`，基准 `1abd6d878`。只改 5 个测试文件；未改任何生产 `.py`。
2. **测试与三个基线**：都跑了、都过了。卡面验收① `run_selftests.py -k files_panel_stages script_undo_shortcuts script_zoom media_page_buttons timers` → 188 条用例 0 红退出码 0；② `smoke_test.py --architecture` → 708 条 0 失败退出码 0；另按 §5 每轮补跑默认冒烟 → 9 项通过 0 失败退出码 0。
3. **欠账少了吗**：少了。主干 `1abd6d878` 上实测 5 文件各 1 条既有红全部清零，未新增欠账、未弱化删除跳过任何用例。

## 改前红（改前 `run_selftests.py -k` 实测留证，共 188 条用例 / 5 个文件有红）

```
### test_files_panel_stages（1 条红）
test_page_switch_clears_select_registration (…:1062)
AssertionError: {1: (<bound method _ScriptStructurePage.show_document of …>>,
                     '01剧本准备/项目剧本/样例剧本.md')} != {}
### test_script_undo_shortcuts（1 条红）
test_shortcuts_registered_via_registry_and_bound_on_widget (…:85)
AssertionError: Items in the first set but not the second: '立即保存'
### test_script_zoom（1 条红）
test_a_keyboard_zoom_steps_limits_gutter_and_both_readers (…:108)
_tkinter.TclError: unknown option "-font"
### test_media_page_buttons（1 条红）
test_11_audio_buttons_standard_and_grouped (…:247)
AssertionError: … Second list contains 1 additional elements: '停止逐句配音'
### test_timers（1 条红）
test_batch_window_cancels_its_timer_on_close (…:132)
AssertionError: Items in the first set but not the second: 'after#126'
```

## 五项根因与契约变更说明（逐条对照生产代码＋git log 核实）

1. **test_files_panel_stages.py:1062**：R4358（`1fb0d4c85`，UX-S02-ONE-EDITOR）起 `_ScriptStructurePage` 经 `files_panel.set_select_handler(page_index, show_document, default=…)` 给自己登记点选回调（`ui/desktop_script_pages.py:596-601`，REQ-S02-38 有意行为）。换页时 `_sync_select_page`（`ui/desktop_files_panel_filters.py:668-677`）按 `key != current` 清掉旧页键——旧页（script）登记确已清掉，但新页（script_structure，page_index=1）在 build 时重新登记，登记表因此为 `{1: (…)}` 而非 `{}`。**契约同步**：断言由「整个登记表为空」对齐为「旧页键已移除」（`assertNotIn(old_page, panel._select_handlers)`）；「旧页回调不再触发」不变式原样保留（改后 `calls` 仍为 1 的断言未动）。
2. **test_script_undo_shortcuts.py:85**：R4380（`7b2354c9e`）在同 scope `剧本结构页·box` 登记了第三条快捷键 `('立即保存', ('<Control-s>','<Control-S>'))`（`ui/desktop_script_edit_session.py:278-279`，`git log -S _shortcut_save` 核实）。**契约同步**：登记名集合对齐为 `{'后退一步','前进一步','立即保存'}`，并补验 `<control-s>` 在 sequences 内与 `preview.bind('<Control-s>')` 非空。
3. **test_script_zoom.py:108**：R4397（`bd9e85266`，UX-S02-MENU-FOLD）为 REQ-S02-40 折叠标记在行号槽画布上增画 `create_rectangle`／`create_polygon` 图元（`ui/script_line_numbers.py:88-98`），这些图元没有 `-font` 选项，`itemcget(item,'font')` 对 `find_all()` 全量遍历抛 TclError。**契约同步**：只对 `type(item) == 'text'` 的行号图元取字体并断言文本图元非空，缩放同步字号的行为断言未变。
4. **test_media_page_buttons.py:247**：R4315（`4925bdec9`／`877f987d3`，FIX-S11-E4）在 11 配音与字幕页「配音制作」FlowBar 内合法新增「停止逐句配音」按钮（`ui/desktop_media_pages.py:708-710`，常驻置灰、句间生效，配套 `ui/desktop_audio_direct.py:136-142`）。**契约同步**：`AUDIO_BUTTONS` 快照补入「停止逐句配音」；该按钮所在「配音制作」行不在 `AUDIO_GROUPS` 受检三组（导入与确认／导出／打开目录与外部工具）内，分组常量无需变更（`desktop_media_pages.py:712-719` 核实三组按钮构成未变）。
5. **test_timers.py:132**：残留 `('after#N', ('…tick','timer'))` 的确切创建方是 `SharedStageInput._build` 末尾的 `tk_timers.repeat(self, 400, self._sync_send_state)`（`desktop_shared_input.py:704`，R4424 `6ab6ee487` SEND-2 引入）。链路：`Desktop.__init__` → `desktop.py:381` `desktop_shared_send.make_shared_input` → `desktop_shared_send.py:992` → `SharedStageInput.__init__` → `_build`（`desktop_shared_input.py:603`），在 `asset_batch.show` 之前无条件成立。它注册在主窗口子控件上、由 `tk_timers.repeat` 的 `<Destroy>` 绑定随宿主控件销毁自取消（`infra/tk_timers.py:33`），**不属** `Desktop.cancel_timers()` 管辖（后者只收 `page_nav` 任务表、`_fit_job`、pet、controller、scheduler，`ui/desktop_lifecycle.py:15-56`）；因此不是 cancel_timers 漏取消的真缺陷，而是测试隔离问题：该 repeat 每次重排换新 after id，`after info` 全枚举口径永远拦到它。**按根因最小修正**：打 `tk.Misc.after` 记录 `(widget, after_id)`，断言收窄为「批量窗口（popup）自己排过的 after id 关窗后全部消失」——「批量窗口关闭不留任何自身定时器」不变式逐字保留且更精确（对常驻定时器重排免疫）；`intervals == {250}` 与「刷新循环走 tk_timers.repeat」断言原样未动。

## 验收（改后两条命令尾部原文）

- `python -B run_selftests.py -k files_panel_stages script_undo_shortcuts script_zoom media_page_buttons timers` → 退出码 0：

```
共 188 条用例，174.6 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：20.1 秒

ALL TESTS PASSED
```

- `python -B smoke_test.py --architecture` → 退出码 0：

```
----------------------------------------------------------------------
Ran 708 tests in 244.039s

OK
✅ 架构治理测试：tests/architecture
```

- `python -B smoke_test.py`（§5 每轮默认冒烟）→ 退出码 0：`通过：9 项 / 失败：0 项，冒烟测试通过`。

## 三基线数（§2.5 规则 29）

- 默认冒烟：9/9 通过（本轮实跑退出码 0）。
- 架构门禁：当轮 708 条、失败集合为空；改后 0 红（改前未单独跑 --architecture，定向 5 红已随本卡清零）。
- 全量回归／欠账：以 `full-safe-receipts.json` 为唯一权威；本卡为 W2 清零既有红的修复卡之一，未跑 `--all --safe`（卡面未列）。

## 未验证项与卡外记录

- `run_selftests` 两轮输出中均见 `invalid command name "…start_account_renewal"`／`"…start_update_check"` 的 after 噪声（改前输出同样存在），属测试进程收尾的既有噪声，与本卡无关，未处理。
- 未验证项：无。
