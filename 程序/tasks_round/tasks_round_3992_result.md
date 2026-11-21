# R3992 结果：页面内容区与底部输入框左右对齐（任务卡 L4-U5）
<!-- round-evidence: {"commit_base": "81577d36", "credential_hits": 0, "evidence_sha256": "cf05e1c31ee35569", "exit": 0, "failed": 0, "passed": 2, "round": 3992, "tests": "run_selftests.py -k desktop_writing_page"} -->

## 三问

- **本轮类型**：修复轮（L4-B6，默认值 L4-Q5）。改了 13 页共用的输入框外边距，按任务卡说明合入后触发全量。
- **测试跑了吗**：跑了。三个基线——默认冒烟 9/9 通过；架构门禁 `smoke_test.py --architecture` 685 条、失败集合为空；全量未运行（本轮不跑 `--all/--safe`，欠账以主干凭据为准，本轮未新增欠账）。
- **欠账少了吗**：少了。U0 清单D 记录的剧本准备页聊天框内缩偏差已消除；其余页对齐目标维持清单D 的 +0/+0 未退化（见 R4）。

## 共用输入框控件所在模块（任务卡要求先列文件名）

- `程序/desktop_shared_input.py` —— 共用输入框控件本体（`_composer_shell` 的 `input_ring` 外框、`SharedStageInput`），本轮实际修改。
- `程序/desktop_shared_send.py` —— `make_shared_input` 入口与发送链路，本卡对象模块之一，**未改**（无需改）。

## 改了哪些文件

| 文件 | 改动 |
| --- | --- |
| `程序/ui/desktop_writing_page.py` | `_build_composer`：`talk` 外框 `box_frame` 内边距 `(xs, none)` → `(none, none)`；`_build_dialog`：聊天 `TextArea` `padx` `md`(12) → `xl`(24)。 |
| `程序/desktop_shared_input.py` | `_composer_shell`：`input_ring` 打包外边距 `(sm, none)`（左内缩 8、右 0，不对称）→ `none`（两侧贴齐）。 |
| `程序/tests/test_desktop_writing_page.py` | 新增：T1/T2（先红后绿）。文件名取 `test_<源模块>.py` 使 STR006 归属自动落到 `ui/desktop_writing_page.py`，不动 `governance/structure.json`（不在允许修改文件内）。 |

`程序/desktop.py` 未改（296–372 行边距段无需动；两侧对齐在控件层达成）。

## 对齐口径与根因

- 「输入框卡片外框」＝ `input_ring`（`_composer_shell` 注释口径：外框由包裹层 1px 底色边承担）。清单D 对输入卡的实测边（x=104–1234）即 `input_dock`/`shared_input` 跨度。
- 改前：聊天 `talk` 外框左缘 124、`input_ring` 左缘 132（ring 左 padx `sm` 内缩 8px、右 padx 0 不对称）；聊天文字起始列 141 vs 输入 157（`talk` 内垫 xs + `box` padx md vs `ring`+`RING_INSET`+Card pad sm + `input` padx lg）。
- 修法：两侧统一贴齐共用内容区边缘（外框两级 `padding`/`padx` 均取 `SPACING['none']`），文字起始列用 `SPACING['xl']` 补到与输入框同列（124+1+24 = 124+1+8+16 = 149）。边距全部走 `SPACING` token，无裸数字。
- 曾试过的另一方案（外框统一内缩 `sm`）：实测使其余 12 页对 ring 变成 (−8,+8)，违反 R4，已弃用；贴齐方案下全部页面与卡片同边。

## 改前失败输出（先红，隐藏桌面，1280×800/1024×680/880×600 × 面板开/关）

`python -m unittest tests.test_page_input_alignment -v`（文件后更名为 `test_desktop_writing_page.py`，断言内容未变）——`Ran 2 tests ... FAILED (failures=12)`，12 条断言全红：

```
FAIL: ... test_chat_and_input_text_start_column (size='1280x800', panel_open=False)
AssertionError: 141 != 157 : 1280x800 聊天文字起始列 141 ≠ 输入文字起始列 157（面板关）
FAIL: ... test_chat_and_input_text_start_column (size='1024x680', panel_open=False)
AssertionError: 141 != 157 : 1024x680 聊天文字起始列 141 ≠ 输入文字起始列 157（面板关）
FAIL: ... test_chat_and_input_text_start_column (size='880x600', panel_open=False)
AssertionError: 141 != 157 : 880x600 聊天文字起始列 141 ≠ 输入文字起始列 157（面板关）
FAIL: ... test_chat_and_input_text_start_column (size='1280x800', panel_open=True)
AssertionError: 141 != 157 : 1280x800 聊天文字起始列 141 ≠ 输入文字起始列 157（面板开）
FAIL: ... test_chat_and_input_text_start_column (size='1024x680', panel_open=True)
AssertionError: 141 != 157 : 1024x680 聊天文字起始列 141 ≠ 输入文字起始列 157（面板开）
FAIL: ... test_chat_and_input_text_start_column (size='880x600', panel_open=True)
AssertionError: 141 != 157 : 880x600 聊天文字起始列 141 ≠ 输入文字起始列 157（面板开）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='1280x800', panel_open=False)
AssertionError: 124 != 132 : 1280x800 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板关）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='1024x680', panel_open=False)
AssertionError: 124 != 132 : 1024x680 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板关）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='880x600', panel_open=False)
AssertionError: 124 != 132 : 880x600 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板关）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='1280x800', panel_open=True)
AssertionError: 124 != 132 : 1280x800 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板开）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='1024x680', panel_open=True)
AssertionError: 124 != 132 : 1024x680 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板开）
FAIL: ... test_chat_frame_and_input_card_share_edges (size='880x600', panel_open=True)
AssertionError: 124 != 132 : 880x600 聊天外框左缘 124 ≠ 输入框卡片外框左缘 132（面板开）
```

改后同一命令：2 tests OK（日志 `程序/logs/l4u5.log`）。

## R4：其余 12 页处理情况

按 U0 清单D 口径逐页处理：清单D 实测各页最外层内容框对输入卡边 +0/+0，本轮未动这些页的布局代码。修复后用隐藏桌面探针复验（临时样例项目、逐页 `d.show(序号)`，最外层内容框 vs `input_ring` 实测边）：能建出的 10 页（script、script_structure、storyboard、animatic、assets、continuity、final、video、audio + 本页 script）全部 diff (0,0)；且因 `input_ring` 现已贴齐 `input_dock` 边，清单D 的 +0/+0 结论继续成立。08/09/12/13 四页在空项目下建不出（清单D 核实1 已记录，`go()` 接住异常写状态栏），清单D 原标「未核实」，本轮同标未核实——那是 U6 的任务范围，本卡不硬改。

## 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py logs\l4u5.log . -- PY -B -m unittest tests.test_desktop_writing_page -v` | 退出码 0，日志末尾 `Ran 2 tests ... OK`（T1/T2 全部子用例通过） |
| `PY -B smoke_test.py` | 退出码 0，通过 9 项 / 失败 0 项 |
| `PY -B smoke_test.py --affected desktop_writing_page desktop_shared_send` | 退出码 0，通过 10 项 / 失败 0 项；选中 9 个测试文件（任务卡预期 8 个，多出的 1 个即本轮新增 `test_desktop_writing_page.py`），`ALL TESTS PASSED`，0 个文件有红 |
| `PY -B smoke_test.py --architecture` | 退出码 0，`Ran 685 tests ... OK`，失败集合为空（含 STR006 归属：新测试文件按名归入 `ui/desktop_writing_page.py`，无新增目录欠账） |

## 提交前自查（code-review 两条标准，对比 git merge-base master HEAD）

- **规范**：边距全部 `SPACING` token 无裸数字；未改 `desktop.py`、发送/附件/语音/模型选择行为与 `page.shared_input`/`idea_log`/`idea_scroll`/`idea_input` 接口名；只动允许修改文件清单内的文件；删掉了新测试里一个未用的 `import tkinter`。
- **任务卡**：R1/R2/R3 由 T1/T2 六组合实测 0px 覆盖；R4 按清单D 逐页核完（见上）；T1/T2 先红后绿，改前失败输出已贴；测试模块与 `--affected`、`--tests` 关键词一致。
- **结论**：无遗留问题。

## 其他

- 轮次号 R3992（`round_claim.py next` 领取）。
- 提交：见下条 git 记录。
