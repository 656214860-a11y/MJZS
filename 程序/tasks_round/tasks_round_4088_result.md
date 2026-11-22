# R4088 结果：提示文字守卫扩到全部界面模块，去掉配音页的重复提示
<!-- round-evidence: {"commit_base": "7ea1ddeb", "credential_hits": 0, "evidence_sha256": "ab05d21c798191f7", "exit": 0, "failed": 0, "passed": 9, "round": 4088, "tests": "run_selftests.py -k text_component_boundary media_page_buttons"} -->

## 开头三问

- 本轮属于哪种类型：功能轮（任务卡 L4-U8a，对应 L4-B8、L4-D2、L4-Q8；车道 `codex/l4-text-unify`，基线 `7ea1ddeb`）。
- 测试跑了吗、三个基线：先红后绿。默认冒烟通过 9 项、失败 0 项；架构门禁 `Ran 698 tests`、`OK`、失败集合为空（比改前多的 2 条是本轮新增的；第一遍红过 1 条，见「如实说明」）；全量回归本轮没跑，全量欠账以 `full-safe-receipts.json` 为准，本轮没有改变它。定向测试逐条结果见「命令与退出码」。
- 欠账少了吗：同一句提示写两处的那一处（L4-Q8）消掉了。`ui/` 下 26 个文件共 73 处自写字体、颜色的 Label 这笔存量本轮没有减少，只是登记成只减不增，由 L4-U8b 分批清。没有新增欠账。

## 改前红

### 守卫（登记表还是空字典时）

`PY -B -m unittest tests.architecture.test_text_component_boundary -v`，退出码 1：

```text
test_hand_styled_labels_only_decrease (tests.architecture.test_text_component_boundary.TextComponentBoundaryTests.test_hand_styled_labels_only_decrease)
ui/ 全部模块：自写字体、颜色的 Label 只许减少，登记值等于实测（L4-F9）。 ... FAIL

AssertionError: Lists differ: ['asset_detail.py 有 11 处 > 登记 0', 'desktop[872 chars]记 0'] != []

First list contains 26 additional elements.
First extra element 0:
'asset_detail.py 有 11 处 > 登记 0'

Ran 4 tests in 2.486s

FAILED (failures=1)
```

随后把登记表 `STYLED_LABEL_CAPS` 填成实测值（26 个文件、合计 73 处），转绿。另外三条（原有两条守卫、新加的金丝雀）这一遍都是绿的。

### T3（改页面之前）

`PY -B run_selftests.py -k media_page_buttons`，退出码 1：

```text
  test_media_page_buttons        5 条    21.3 秒  ✗ 1

共 5 条用例，88.2 秒；1 个文件有红

===== test_11_audio_dialogue_reason_shown_once (test_media_page_buttons.MediaPageButtonTests.test_11_audio_dialogue_reason_shown_once) =====
  File "...\tests\test_media_page_buttons.py", line 230, in test_11_audio_dialogue_reason_shown_once
    self.assertNotIn('对白无法读取', text,
AssertionError: '对白无法读取' unexpectedly found in '对白无法读取，配音生成与字幕导出暂不可用：分镜文件缺少镜头列表' : 11 配音与字幕：状态栏不应重复页内已显示的原因（实测：对白无法读取，配音生成与字幕导出暂不可用：分镜文件缺少镜头列表）
```

改前页内已经是有且只有一处（这条断言改前就过），红在「状态栏重复同一句」这一条。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `tests/architecture/test_text_component_boundary.py` | 只增不删（85 增 0 删）：`RAW_LABELS`、登记表 `STYLED_LABEL_CAPS`（26 个文件、合计 73 处，值等于实测）、`_styled_label_count`／`_styled_label_counts`／`_styled_label_drift` 三个函数，两条用例 `test_hand_styled_labels_only_decrease`（T1）和 `test_hand_styled_label_ratchet_catches_drift`（T2，对源码字符串求值，不改生产文件）。统计用的是同文件的 `_resolved_calls`。原有两条守卫、`TEXT_PAGE_COMPONENTS`、`FORBIDDEN_OPTIONS` 一字未动。 |
| `ui/desktop_media_pages.py` | 只改 `audio()` 里对白原因那一处（764–768 行，3 增 3 删）：去掉 `self.note(dialogue_reason)`；页内那一处由 `ttk.Label(..., style='Muted.TLabel')` 换成 `DescriptionBlock`。按钮置灰的逻辑没动。 |
| `tests/test_media_page_buttons.py` | 只增不删（37 增 0 删）：辅助函数 `_texts` 和用例 `test_11_audio_dialogue_reason_shown_once`（T3）。 |
| `tasks_round/tasks_round_4088_result.md` | 本文件。 |

## 登记表的数字怎么来的

- 用守卫自己的 `_styled_label_counts()` 在本车道实测：`ui/` 下 150 个模块，26 个有这类调用，合计 73 处；逐文件的数字就是 `STYLED_LABEL_CAPS`。
- `ui/desktop_media_pages.py` 改前改后都是 3 处：改掉的那一处原来用的是样式 `Muted.TLabel`，没有带 font／fg／foreground，本来就不在计数内。
- 2026-11-22 20:00 前后用同一口径核对过当时 10 条未合入的 `codex/` 分支：没有哪一条改变 `ui/` 任何文件的这个计数。合入前如果有别的车道先合入并改了这类调用，守卫会红，按提示把登记改成当时的实测值。

## 与任务书不同的地方

- 行号：任务书写 726–729 行，U6、U7c 合入后这一处在 764–768 行。
- 提交命令的 `--tests` 比任务书多带 `media_page_buttons`（本轮改了这个测试文件和它测的页面）；`--agent` 写实际执行方。
- T3 加在既有的 `tests/test_media_page_buttons.py` 里（队列项的允许清单点名了这个文件），没有新建测试文件，所以没有动 `governance/structure.json`。该文件在 `test_ownership` 里登记的说明文字（「…四页按钮的标准宽度、分组同行与文字快照」）没有提到新加的这一条；改登记要动 `governance/structure.json`，不在允许清单内，没改，留给验收窗口定。

## 如实说明

- 第一遍架构门禁红过 1 条（20:13–20:19，`Ran 698 tests`，`FAILED (failures=1)`）：`tests.architecture.test_platform_process_boundary.ProcessSpawnBoundaryTests.test_spawn_sites_within_baseline` 报 `ui/desktop_media_pages.py:913` 是新增的进程启动点。原因：那条棘轮按「文件:行」登记（`ui/desktop_media_pages.py:914`，打开剪映的 `launch_windows_app`），第一版改法把 5 行改成了 4 行，后面的行号都前移了一行。处理：注释写成两行，这一处仍是 5 行，文件总行数不变，启动点仍在 914 行；没有改 `test_platform_process_boundary.py` 里的登记（不在允许清单内）。改后该文件 8 条全过，整轮架构门禁重跑 698 条全过。供验收窗口参考：R4044、R4051 的提交里同时改了这两个文件，这次没有动登记。
- 20:13 那一遍 `-k text_component_boundary media_page_buttons` 是在「注释写成两行」之前跑的，两版只差注释的行数。最终内容上的同一组测试由 `--affected desktop_media_pages`（含 `test_media_page_buttons`）、改后单跑的守卫文件和提交工具在提交时的那一遍覆盖，提交时的结果记在 `tasks_round/evidence/R4088.json` 和本文件第二行的戳里。
- 守卫的范围按卡面是 `ui/` 目录：现在是平铺的 150 个文件、没有子目录，扫描用 `ui/*.py`，和 `test_notification_boundary.py` 的写法一样；以后 `ui/` 下若加子目录，这条守卫要跟着改成递归扫描。不在 `ui/` 下的同类调用没有纳入：`desktop.py` 3 处、`app.py` 1 处、`ui_widgets.py` 1 处（20:00 前后用同一口径实测）。要不要纳入由验收窗口或 L4-U8b 定。
- `DescriptionBlock` 的设计长度是 60 字以内。对白读不出时，原因后面带异常原文，可能超过 60 字，组件按统一的折行宽度折行显示，不截断。没有在真实桌面上目检，只有隐藏桌面里的自动化用例。
- 定向测试的输出里出现过一行 `invalid command name "...start_account_renewal"`（窗口销毁后 `after` 定时器才触发），不是失败。主工作树和各车道 `logs` 目录里有 10 份既有日志含同样的行（包括 19:32 的 `auto_full_safe.log`），和本轮改动无关。
- 架构门禁输出里的「[棘轮提示] LR-09、LR-10 实测 59 < 基线 60」两行改前就有（调度窗口 19:56 在主干副本上的日志里也有），不是本轮带来的，本轮没有动 `层间合规清单.json`。「改前 696 条」取自 R4066 结果文件和调度窗口那份日志，本轮没有在改前的车道上单独跑过架构门禁。
- 没有新建工作目录：按验收窗口 20:06 的安排复用闲置目录 `.agents/worktrees/l4-buttons-media`，在里面从主干切出分支 `codex/l4-text-unify`。测试进程都降到 BelowNormal 优先级。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `PY -X utf8 -B 维护记录\基准脚本\round_claim.py next` | 0 | 领到轮次 4088 |
| `PY -B -m unittest tests.architecture.test_text_component_boundary -v`（登记表为空） | 1 | 4 条中 1 红，列出 26 个文件 |
| `PY -B run_selftests.py -k media_page_buttons`（改页面之前） | 1 | 5 条中 1 红（T3） |
| `PY -B run_selftests.py -k text_component_boundary media_page_buttons`（20:11–20:13） | 0 | 9 条全绿，0 个文件有红，实际跳过 0 条 |
| `PY -B smoke_test.py --architecture`（第一遍，20:13–20:19） | 1 | 698 条中 1 红（见「如实说明」第一条） |
| `PY -B -m unittest tests.architecture.test_text_component_boundary -v`（最终内容） | 0 | `Ran 4 tests`，`OK` |
| `PY -B -m unittest tests.architecture.test_platform_process_boundary`（最终内容） | 0 | `Ran 8 tests`，`OK` |
| `PY -B smoke_test.py`（20:20） | 0 | 通过 9 项，失败 0 项 |
| `PY -B smoke_test.py --architecture`（第二遍，20:20–20:25，最终内容） | 0 | `Ran 698 tests`，`OK`，失败集合为空 |
| `PY -B run_selftests.py -k ui_edges_pages`（20:25–20:26，最终内容） | 0 | 40 条全绿，实际跳过 0 条；其中 `test_audio_actions_disabled_without_dialogue` 也检查配音页置灰时页内有原因 |
| `PY -B smoke_test.py --affected desktop_media_pages`（20:28–20:32，最终内容） | 0 | 选中 5 个测试文件（`test_desktop_media_pages`、`test_media_page_buttons`、`test_media_page_services`、`test_req_s06_anchors`、`test_video_prompt_direct_api`），22 条全绿，0 个文件有红，实际跳过 0 条；冒烟汇总「通过：10 项，失败：0 项」；225 秒里约 170 秒在等别的窗口占着的界面令牌 |

## 未覆盖项

- 未跑全量自测（`run_selftests.py --all --safe`）：用户 2026-11-22 19:52 决定验证期间不跑全量、只跑定向测试。
- 没有在真实桌面上目检。
- 未 push、未 merge、未改主工作区；复核、验收、合入归验收窗口。

## 提交

本文件随 R4088 的提交一起入库（分支 `codex/l4-text-unify`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里编码窗口一节。
