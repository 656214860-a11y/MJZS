# tasks_round_4504_result — FIX-S03-UX-POLISH（W2）
<!-- round-evidence: {"commit_base": "d4295c273", "credential_hits": 0, "evidence_sha256": "47394f43fd2e81cf", "exit": 0, "failed": 0, "passed": 127, "round": 4504, "tests": "run_selftests.py -k storyboard_direct_api storyboard_page_loading stage_reply_area shared_input_stages desktop_shared_input"} -->

## 三问

- **本轮类型**：修复轮（§3.2，补强 03 初步分镜发送直连回显自动展开与顶部文档关闭栏视觉辨识度）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_direct_api storyboard_page_loading stage_reply_area shared_input_stages desktop_shared_input` → 改后 127 条用例（改前既有 117 条 + 新增 10 条）、0 个文件有红、0 条跳过、`ALL TESTS PASSED`，退出码 0。
  - 架构门禁：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → `Ran 708 tests in 425.531s`、`OK`、`✅ 架构治理测试：tests/architecture`，退出码 0（当轮实测）。
  - 默认冒烟基线 8/8 与全量 `--all --safe`：本轮验收清单未包含，未运行；全量欠账口径以 `full-safe-receipts.json` 为准。
- **欠账少了吗**：修复 03 初步分镜两项实测体验漏口，未触碰已满 1000 行的 `程序/desktop_shared_input.py`，零新增 `.py` 模块与架构豁免，未引入新欠账。

## 缺陷复现（先红后绿）

- **复现方式**：在 5 个允许测试文件（`程序/tests/test_storyboard_direct_api.py`、`程序/tests/test_stage_reply_area.py`、`程序/tests/test_storyboard_page_loading.py`、`程序/tests/test_desktop_shared_input.py`、`程序/tests/test_shared_input_stages.py`）中先行补充 10 条回归用例，在未改动任何生产代码前于 `程序/` 目录执行第一条验收命令。
- **改前红测结果**（基线 `d4295c273`，退出码 1，共 127 条用例，既有 117 条全绿，新增 10 条全部命中缺陷变红、0 条跳过）：

```text
  test_storyboard_direct_api    19 条     3.8 秒  ✗ 3
  test_shared_input_stages#3    15 条     0.3 秒  ✗ 1
  test_desktop_shared_input#2   11 条     3.2 秒  ✗ 3
  test_storyboard_page_loading   9 条    10.3 秒  ✗ 1
  test_stage_reply_area         20 条    15.3 秒  ✗ 2
共 127 条用例，20.9 秒；5 个文件有红
```

1. `test_storyboard_direct_api`（3 红）：
   - `test_run_storyboard_direct_writes_start_progress_artifact_and_summary`: `AssertionError: 0 not greater than or equal to 4`（`run_storyboard_direct` 未向 `host.reply_note` 写入启动/进度/产物/总结）。
   - `test_run_storyboard_direct_failure_expands_and_supports_legacy_3arg_stub`: `AssertionError: 0 != 1`（失败路径未写 `error` 回显及展开）。
   - `test_run_storyboard_direct_stopped_writes_notice_and_legacy_host_safe`: `AssertionError: 0 != 1`（停止路径未写 `notice` 回显）。
2. `test_shared_input_stages`（1 红）：
   - `test_launch_storyboard_flow_expands_reply_area_on_dispatch_and_error`: `AssertionError: Lists differ: [] != [True]`（启动派发与异常报错未触发展开 `reply_area`）。
3. `test_desktop_shared_input`（3 红）：
   - `test_upstream_rejection_writes_reply_note_with_expand_for_empty_and_text_send`: `AssertionError: Lists differ: [] != [('error', 'storyboard', '请先确认结构剧本', {'expand': True}), ...]`（上游门禁拦截未写入 `reply_note`）。
   - `test_upstream_rejection_falls_back_to_3arg_reply_note_and_expands_reply_area`: `AssertionError: Lists differ: [] != [('error', 'storyboard', '请先确认结构剧本')]`。
   - `test_accepted_empty_send_expands_reply_area_only_when_on_storyboard_stage`: `AssertionError: Lists differ: [] != [True]`（S03 空发送受理未展开 `reply_area`）。
4. `test_storyboard_page_loading`（1 红）：
   - `test_doc_bar_uses_card_frame_contrast_title_bordered_close_and_fits_content`: `AssertionError: '' != 'Tokens.Card.TFrame'`（顶部文档栏仍为普通无样式 `ttk.Frame`）。
5. `test_stage_reply_area`（2 红）：
   - `test_note_with_expand_true_expands_current_stage_without_persisting_expand`: `AssertionError: False is not true : 当前阶段传 expand=True 应自动展开`。
   - `test_note_default_stays_collapsed_and_other_stage_expand_does_not_open_current`: `AssertionError: 'expand' unexpectedly found in {'kind': 'error', 'text': '资产缺失报错', 'expand': True, 'schema_version': 1, ...}`（未声明 `expand` 参数时被 `**fields` 误落盘进 JSONL）。

## 改动清单（文件:行号）

1. `程序/ui/stage_reply_area.py`（420 → 423 行）：
   - `L228-L258`：`StageReplyArea.note` 新增仅关键字参数 `expand=False`（绝不写入 `record` / JSONL）；仅在命中当前非空阶段且 `expand=True` 时自动调用 `set_expanded(True)`，并在展开态滚动到底部；不传 `expand` 仍保持默认收起态，非当前阶段不误展开。
2. `程序/ui/desktop_storyboard_direct.py`（72 → 133 行，未导入 `stage_reply_area`）：
   - `L8-L49`：新增 `_expand_reply` 与 `_reply_note`，仅通过 `getattr(host, 'reply_note', None)` / `getattr(host, 'reply_area', None)` 交互，优先透传 `expand=True`，遇旧 3 参桩抛 `TypeError` 时降级回退并按需调用 `reply_area.set_expanded(True)`。
   - `L75-L133`：`run_storyboard_direct` 在启动提示（`progress`, `expand=True`）、逐集队列播报（`progress`）、停止提示（`notice`）、落盘分镜产物（`artifact`, `path`/`title`）、失败报错（`error`, `expand=True`）及完成总结（`reply`）全链路写入回话区。
3. `程序/ui/desktop_shared_input_extras.py`（467 → 548 行，未触碰 `desktop_shared_input.py`）：
   - `L417-L491`：新增 `_expand_reply_area`、`_reply_note_with_expand`、`_wrap_upstream_error`（包装 `box.on_upstream_error`，非 `script` 阶段返回非空错误时同步经 `reply_note('error', stage, error, expand=True)` 写入并展开）与 `_wrap_stage_action`（包装 `box.run_stage_action`，`storyboard` 空发送受理时展开处于 `storyboard` 阶段的 `reply_area`）。
   - `L494-L512`：`attach(box)` 挂载 `_wrap_upstream_error(box)` 与 `_wrap_stage_action(box)`。
   - `L522-L541`：`launch_storyboard_flow` 在异常报错与启动派发两条路径同步调用 `_expand_reply_area(desktop, 'storyboard')`。
4. `程序/ui/storyboard_table_ui.py`（744 → 756 行）：
   - `L13`：从已有导入源 `ui_widgets` 补充导入 `Card`（零新增模块边）。
   - `L460-L471`：`S03EditorView._build_doc_bar` 改用 `Card(..., padding=(SPACING['sm'], SPACING['xs']))`（`Tokens.Card.TFrame`）承载顶部文档头栏，左侧使用 `Composer.Muted.TLabel`（「当前文件：」）+ `Composer.TLabel`（`self.doc_title`），右上角 `self.close_button` 改用 `Tokens.Secondary.TButton`；严禁任何 `font`/`fg`/`foreground` 参数，保持 `'关闭'` 与 `Path(path).name` 契约不变。
   - `L473-L492`：`set_document_header` 仅在 `doc_bar` 显隐状态切换时安全调用 `desktop.fit_content()`（若存在）。
5. 测试文件（5 个，新增 10 条用例，未删改或放宽任何既有断言）：
   - `程序/tests/test_storyboard_direct_api.py`（`L358-L499`）：新增 `StoryboardDirectReplyAreaTests` 3 条用例。
   - `程序/tests/test_stage_reply_area.py`（`L131-L163`）：新增 2 条自动展开与 JSONL 不落盘 `expand` 用例。
   - `程序/tests/test_storyboard_page_loading.py`（`L329-L374`）：新增 1 条顶部卡片头栏、对比标题、带框关闭钮及 `fit_content` 联动用例。
   - `程序/tests/test_desktop_shared_input.py`（`L203-L248`）：新增 3 条 S03 上游门禁写回话区、3 参回退与空发送展开用例。
   - `程序/tests/test_shared_input_stages.py`（`L691-L728`）：新增 1 条 `launch_storyboard_flow` 派发与报错展开及非本阶段隔离用例。

## 改后验收输出尾部（退出码均为 0）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_direct_api storyboard_page_loading stage_reply_area shared_input_stages desktop_shared_input`（退出码 0）：
   ```text
   共 127 条用例，21.6 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   ALL TESTS PASSED
   ```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：
   ```text
   ----------------------------------------------------------------------
   Ran 708 tests in 425.531s

   OK
   ✅ 架构治理测试：tests/architecture
   ```

## 未验证项与卡外发现

- **未验证项**：
  - `smoke_test.py` 默认档（8/8）与 `run_selftests.py --all --safe`（本卡验收未要求，未运行）。
  - 真实可见桌面窗口下重启后的肉眼视觉复核（隐藏桌面真 Tk 测试已验证样式名、映射与几何）。
- **卡外发现**：无。

## 提交

- 通过 `scripts/dev.py commit` 提交至分支 `codex/fix-s03-ux-polish`，不合入、不 push。
