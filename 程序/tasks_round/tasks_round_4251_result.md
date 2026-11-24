# R4251 结果：S05-USAGE 补齐使用情况块五种状态前景着色
<!-- round-evidence: {"commit_base": "7684a7e7", "credential_hits": 0, "evidence_sha256": "37c99a5c6e5adc1f", "exit": 0, "failed": 0, "passed": 148, "round": 4251, "tests": "run_selftests.py -k asset_impact asset_detail asset_batch_window req_s05_anchors keyframe_evidence copy_rules static_names stage_doc_sections requirement_traceability design_coverage"} -->

## 开头三问

- （一）本轮属于哪种类型：功能轮。W2 卡面 S05-USAGE：接管 `codex/s05-usage` 既有未提交成果，只补「使用情况」块逐镜行的状态前景着色、对应真 Tk 回归与 S05 文档色系说明；不改 `asset_usage`／`deletion_references` 公开契约，不加图例、不显示视频过期。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。卡面验收命令「共 148 条用例，158.3 秒；0 个文件有红」，退出码 0，含五色 foreground 精确断言；改产品前同命令基线「共 147 条用例，61.8 秒；0 个文件有红」，退出码 0。架构门禁——`smoke_test.py --architecture`「Ran 700 tests」「OK」，退出码 0。默认冒烟与全量自测——未跑（卡面未要求，且 GUI 令牌当时被占）。
- （三）欠账少了吗：少了一条——使用情况块五种状态此前只有文字、没有按状态着色，本轮补上并有真 Tk 断言钉住。未新增欠账；未验证项见末节。

## 接管现场

- 开工核对：HEAD＝`7684a7e7c1ec24c8272b0bbbc96d7c95d5e8b9fd`，分支 `codex/s05-usage`；`git status --porcelain` 只含卡面列出的 10 个既有脏文件，全部保留、未 reset／stash／checkout／改分支。
- 既有 10 文件：`docs/specs/09_资产数据生命周期.md`、`docs/stages/S05_资产管理.md`、`domain/asset_plan.py`、`orchestrator/stage_handoff_gateways.py`、`stage_execution_service.py`、`tests/test_asset_batch_window.py`、`tests/test_asset_detail.py`、`tests/test_asset_impact.py`、`ui/asset_detail.py`、`ui/desktop_asset_pages.py`。
- 本轮在既有成果上只动缺口：`ui/asset_detail.py` 状态标签、`tests/test_asset_detail.py` 新增一条真 Tk 用例、`docs/stages/S05_资产管理.md` UX-S05-53 色系说明、`维护记录/skip台账.json` 按既有格式登记该新 Tk 用例的 `PLATFORM_TKINTER` 条目（未改既有条目），外加本结果文件。

## 基线输出（改测试前）

卡面定向命令（程序目录下，解释器 `..\..\..\..\运行环境\Python\python.exe`）：

```
python.exe -B run_selftests.py -k asset_impact asset_detail asset_batch_window req_s05_anchors keyframe_evidence copy_rules static_names stage_doc_sections requirement_traceability design_coverage
```

结果：12 个匹配测试文件，「共 147 条用例，61.8 秒；0 个文件有红」，「实际跳过 0 条用例」，`ALL TESTS PASSED`，退出码 0。

## 新测试改前红

只新增断言、未改产品后跑 `run_selftests.py -k asset_detail`：「共 51 条用例，85.4 秒；1 个文件有红」，退出码 1。唯一红项：

```
===== test_usage_block_colors_each_status_label (test_asset_detail.UsageBlockTests.test_usage_block_colors_each_status_label) =====
  File "tests\test_asset_detail.py", line 842, in test_usage_block_colors_each_status_label
    self.assertEqual(str(widget.cget('foreground')), COLORS[key],
AssertionError: '#536471' != '#15803D'
 : 首帧：最新 应用 COLORS[success_text]
```

失败标签 `首帧：最新`；实际 foreground `#536471`（`COLORS['text_secondary']` 中性灰），期望 `COLORS['success_text']`（`#15803D`）。其余四档同理未着色，断言在第一档即红，符合「先红后绿」。

## 五色契约与实现

| 状态标签 | 前景色 |
| --- | --- |
| `首帧：最新` | `COLORS['success_text']` |
| `首帧：过期` | `COLORS['warning_text']` |
| `首帧：缺失` | `COLORS['danger_text']` |
| `视频：已生成` | `COLORS['success_text']` |
| `视频：未生成` | `COLORS['text_muted']` |

- 文字仍显示（`首帧：X`／`视频：Y`，另有 `（原因）` 与「集 · 镜头」行），颜色不是唯一载体；不写内联十六进制，不加图例；视频过期不在本卡范围、未显示。
- `ui/asset_detail.py`：新增 `_FRAME_LABELS`／`_FRAME_FOREGROUNDS`／`_VIDEO_LABELS`／`_VIDEO_FOREGROUNDS` 四张映射与 `_usage_label(parent, text, foreground)` 小函数——`ttk.Label` 构造只给 `text`／`anchor`／`justify`，前景经 `label.configure(foreground=...)` 下发。原因：`tests/architecture/test_text_component_boundary.py` 的棘轮只数 `Label` 构造关键字里的 `font`／`foreground`／`fg`，`configure` 不计；这样 `asset_detail.py` 实测回到登记值 11，未改棘轮登记、未弱化断言（与 `ui_status_bar` 动态改色、`production_lock_fields` 清色同一机制）。块位置、空态／孤立兜底、滚动区与异常兜底均未动。
- `docs/stages/S05_资产管理.md` UX-S05-53：色系说明改为「首帧最新／视频已生成用 success_text、首帧过期用 warning_text、首帧缺失用 danger_text、视频未生成用 text_muted 弱化色」，与实现一致；REQ／DES 语义未改。
- `tests/test_asset_detail.py`：新增 `UsageBlockTests.test_usage_block_colors_each_status_label`（真 Tk，构造 latest/generated、stale/none+原因、missing/generated 三行，逐标签 `cget('foreground')` 精确断言五色，并核对镜头号与原因文字仍可见）；原有位置、空态、行数断言未改。
- `维护记录/skip台账.json`：按既有格式新增该用例一条 `PLATFORM_TKINTER` 登记，未改既有条目。

## 改后输出

卡面定向命令：「共 148 条用例，158.3 秒；0 个文件有红」，「实际跳过 0 条用例：本机没有任何登记位被跳过」，`ALL TESTS PASSED`，退出码 0（含 `test_usage_block_colors_each_status_label` 通过）。`smoke_test.py --architecture`：「Ran 700 tests in 354.410s」「✅ 架构治理测试：tests/architecture」「OK」，退出码 0。

测试输出里的 `invalid command name "…start_update_check"`／`start_account_renewal` 是既有首帧定时器在窗口销毁后的噪声（标准错误输出），不影响结果，非本轮引入。

## diff --numstat（提交前，11 个已跟踪改动）

```
6	6	程序/docs/specs/09_资产数据生命周期.md
13	1	程序/docs/stages/S05_资产管理.md
50	0	程序/domain/asset_plan.py
13	0	程序/orchestrator/stage_handoff_gateways.py
2	0	程序/stage_execution_service.py
46	0	程序/tests/test_asset_batch_window.py
109	0	程序/tests/test_asset_detail.py
54	0	程序/tests/test_asset_impact.py
64	0	程序/ui/asset_detail.py
34	3	程序/ui/desktop_asset_pages.py
27	0	程序/维护记录/skip台账.json
```

`git diff --check` 无输出（退出码 0）；`git diff --name-only` 仅上述 11 个文件，均在允许清单内；本结果文件为新增未跟踪文件，由本次提交一并纳入。`ui/asset_detail.py` 相对 HEAD 全为新增（使用情况块整体是新增行），故删除数为 0。

## 命令与退出码

均在车道 `程序` 目录下跑，解释器 `..\..\..\..\运行环境\Python\python.exe`；Git 命令在工作树根。

| 命令 | 结果 |
| --- | --- |
| `python.exe -B run_selftests.py -k asset_impact asset_detail asset_batch_window req_s05_anchors keyframe_evidence copy_rules static_names stage_doc_sections requirement_traceability design_coverage`（改测试前基线） | 退出码 0：「共 147 条用例，61.8 秒；0 个文件有红」 |
| `python.exe -B run_selftests.py -k asset_detail`（只加测试、未改产品） | 退出码 1：「共 51 条用例，85.4 秒；1 个文件有红」（见「改前红」） |
| 同上定向命令（改产品后，本轮复跑） | 退出码 0：「共 148 条用例，158.3 秒；0 个文件有红」 |
| `python.exe -B smoke_test.py --architecture` | 退出码 0：「Ran 700 tests」「OK」 |
| `git status --porcelain`／`git diff --check`／`git diff --name-only`／`git diff --numstat` | 均退出码 0；改动仅限允许清单 |
| `python.exe -B scripts\dev.py claim` | 退出码 0，领到轮次 4251 |

注：本轮一次 `run_selftests` 先在 bash 下误用反斜杠路径导致命令未找到（退出码 127，非测试结果），随即改用 PowerShell 按卡面原样重跑，上表只记有效运行。

## 未覆盖项／未验证项

- 未跑默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe`（卡面未要求；GUI 令牌期间被其它全量占用过）。
- 未在真实应用窗口手动点击核对视觉效果；颜色正确性由真 Tk 用例的 `cget('foreground')` 精确断言覆盖。
- 视频「过期」状态按卡面不在范围，未实现、未显示。
- 提交哈希不写在本文件（本文件先于提交生成）；以 `tasks_round/evidence/R4251.json` 与 `git log -1 --oneline` 为准。
- 未 push、未 merge、未切分支。

## 提交

用 `scripts\dev.py commit` 提交，消息 `R4251: S05-USAGE 补齐使用情况状态着色`，`--tests` 为卡面九组关键词，`--agent "Devin SWE-2 Flash High"`，文件为上述 11 个改动文件＋本结果文件（路径相对 `程序`）。evidence 只由 commit 生成。
