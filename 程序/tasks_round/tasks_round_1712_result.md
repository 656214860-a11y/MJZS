# R1712：结构治理轮·执行（UI 批次 8）——视频工作台与零散弹窗：令牌／间距机械替换

> 轮次类型：结构治理轮（执行）·UI 批次 8，机械替换，不改布局结构与行为。
> 执行者：opencode（免费 flash，产品负责人指定）。**未提交，由 Claude 验收后提交。**

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（执行），来源＝`D:\opencode任务\输出\UI设计评审报告.md` 第 5 节路线表「批次 8」。只做 token／间距机械替换，不动布局结构与行为。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**（第 10 轮）；定向 `--affected app keyframe_comfy reference_wall white_model` **45 个文件 / 0 红**；新增 `tests/test_ui_batch8_video_ui_tokens.py` **4/4**；验收 `-k` 全跑有红，**红全部来自并行批次的未提交改动（非本批文件）**，已逐条定位，见 C 节。
3. **project_status.md 的欠账少了吗？** 没有减少——本轮未提交、未领轮次、未改状态页（按 `RUI_common.md` 红线，验收与提交由 Claude 做）。本批不新增架构门禁欠账：`test_token_boundary` 只降不升（见 B 节计数）。

## A 现状核对（开工实测，口径＝`tests/architecture/test_token_boundary.py`）

| 文件 | 内联 hex | 数字 padding（`padx/pady/ipadx/ipady` 取值字面量） |
| --- | --- | --- |
| `程序/app.py` | 0 | 7（`610,611,634,636,647` 行：12/6/12/12/8/8/12） |
| `程序/keyframe_comfy.py` | 0 | 26（`279…523,799…812` 行：14/6/10/2） |
| `程序/reference_wall.py` | 0 | 0（但 `Card(padding=12)` 与 8 处数字 padx/pady **元组**未令牌化） |
| `程序/white_model.py` | 0 | 8（`48,108,126,132,134,138,148` 行：10/14/14/5/5/5/3/2） |

- 四个文件**均无内联 hex**（评审报告「99 处/5 文件」不含这四个），故颜色项无改动空间，只保证不新增。
- `error()` 现状：`keyframe_comfy`／`reference_wall`／`white_model` 的可恢复错误走 `ui_widgets.notify(..., level='error')`，**本来就没有 `modal=True`**；`app.py` 走 `self.notifier.error(...)`，本轮**未新增**任何 `modal=True`。
- 文案：四文件**不含**门禁禁用词「复制成功／成功复制」（`tests/architecture/test_copy_entry_boundary.py`），也没有发现明显错别字，故**未改任何用户可见文案**。

## B 改动（替换前后计数）

| 文件 | hex 前→后 | 数字 padding 前→后 |
| --- | --- | --- |
| `程序/app.py` | 0 → 0 | **7 → 0** |
| `程序/keyframe_comfy.py` | 0 → 0 | **26 → 0** |
| `程序/reference_wall.py` | 0 → 0 | 0 → 0（另 8 处数字元组 padding 全部令牌化） |
| `程序/white_model.py` | 0 → 0 | **8 → 0** |

改动明细：

- **`app.py`**：`writing_setup` 5 处数字 padding → `SPACING`；`padx=12→md`、`pady=8→sm`（值相同）、`pady=12→md`（值相同）、`padx=8→sm`（值相同）、`pady=6→xs`。
- **`keyframe_comfy.py`**：`from ui_tokens import COLORS, FONTS, SPACING`（新增 `FONTS`）；26 处数字 padding → `SPACING`；日志 `TextArea` 的 `font=('Microsoft YaHei UI', 10)` → `FONTS['body']`（10pt，值相同）。
- **`white_model.py`**：`from ui_tokens import FONTS, SPACING`（新增 `FONTS`）；8 处数字 padding → `SPACING`；标题 `font=('Microsoft YaHei UI', 15, 'bold')` → `FONTS['title']`（14 bold，见 D 节）；两个 `LabelFrame(padding=8)` → `SPACING['sm']`（值相同）。
- **`reference_wall.py`**：新增 `from ui_tokens import SPACING`；`Card(win, padding=12)` → `SPACING['md']`（值相同）；8 处数字元组 padding → `SPACING`。
- **新增 `程序/tests/test_ui_batch8_video_ui_tokens.py`**（docstring 写「UI 批次 8」）：断言四文件 hex 计数不升（实测恒 0）、数字 padding 计数降为 0、`SPACING` 全落在 4px 刻度、真 Tk 根窗口验证 `FONTS['title']` 解出「YaHei / 14 / bold」且量得到高度。

### 非整值 padding 的贴合映射（值不同，按最近 token；平手取小值，保持紧凑、避免固定尺寸弹窗溢出）

- `2 → SPACING['none'](0)`：`keyframe_comfy 484,489`；`white_model 148`
- `3 → SPACING['xs'](4)`：`white_model 138`
- `5 → SPACING['xs'](4)`：`white_model 126,132,134`
- `6 → SPACING['xs'](4)`：`keyframe_comfy 314,421,447,493,494,495,497,523,803,805,810,811,812`；`app 610`(pady)；`reference_wall` 元组尾值
- `7 → SPACING['sm'](8)`：`white_model 164,165`
- `10 → SPACING['sm'](8)`：`keyframe_comfy 496`；`reference_wall` 元组尾值 `(4,10)`
- `14 → SPACING['md'](12)`：`keyframe_comfy 279,280,281,312,314,316,421,497,523,799`；`white_model 108`
- `15 → SPACING['lg'](16)`：`white_model 141` 元组首值 `(15,3)`

值相同的直接换（未在此列）：`4→xs`、`8→sm`、`12→md`。

## C 验证与截图路径

| 命令 | 实际结果 |
| --- | --- |
| `python -B smoke_test.py` | **通过 8 / 失败 0**（第 10 轮） |
| `python -B smoke_test.py --affected app keyframe_comfy reference_wall white_model` | **45 个文件 / 0 红，ALL TESTS PASSED** |
| `python -B -m unittest tests.test_ui_batch8_video_ui_tokens` | **4/4 通过**（EXIT=0） |
| 验收 `-k keyframe reference_wall white_model test_layers function_size_ratchet module_size_ratchet test_ui_batch8 token_boundary` | **201 条 / 6.0 秒；唯一红＝`test_function_size_ratchet.test_registry_tracks_real_sizes`**，报 `desktop.py::__init__ 实际 132 行，已不超限，请从登记表删除` —— `desktop.py` 是**并行批次 3** 的未提交改动，非本批文件；本批四文件的函数长度未变（`keyframe_comfy.show` 仍 626、`app.__init__` 未动）。`architecture.test_token_boundary` 5/5、`architecture.test_layers` 5/5、`test_keyframe_comfy` 14/14、`test_reference_wall` 16/16、`test_white_model_identity` 12/12 全绿。 |
| 任务书原始 `-k video_ui keyframe reference_wall white_model ui_edges test_layers function_size_ratchet module_size_ratchet test_ui_batch8` | **有红，全部来自并行批次未提交改动**：`test_video_ui` 多条 `ImportError: cannot import name 'WrappingActionRow' from 'skill_panel_support'`（批次 5 正在改 `skill_panel.py`／`skill_panel_support.py`）；`test_ui_edges` 两条滚动断言（`test_restored_main_window_recomputes_page_scroll_before_wheel`、`test_table_hover_clears_when_wheel_scrolls`，`canvas.yview()[0]` 仍 0.0）与 `desktop.py` 滚动改动相关（批次 3）。`git status` 显示这四个文件均由他批修改，本批未碰。**未反复重跑**（按 `RUI_common.md` §验证 4），请 Claude 在合入后复跑。 |

- **探针脚本**：`工作流任务\probe_ui8\count_tokens.py`（复用 `test_token_boundary` 的 `hex_color_count` / `numeric_padding_count` 数计数）、`工作流任务\probe_ui8\list_values.py`（逐行列出数字 padding／字号／wraplength）。
- **截图**：**未生成**。本批是源码级令牌棘轮，无新建页面或视觉新控件；如需人工观感复核，请 Claude 在合入后截图。未打开、未读取任何用户真实项目。

## D 断言未动 ＋ 需裁决事项

- **既有断言未动、未加 skip、未改期望值**。本轮未触碰任何既有测试文件。
- **`wraplength` 只列出、未替换**（无整值 token；改动会改变折行＝改布局，故保留待裁）：
  - `app.py:347`=700（进度行）、`app.py:912`=660、`app.py:917`=660（资产选择窗说明）
  - `keyframe_comfy.py:440`=800（首帧窗页内提示）
  - `reference_wall.py:90`=960（图墙状态行）
  - `white_model.py:110`=710、`127`=690、`131`=690、`147`=710、`148`=710（白模预演窗说明／路径）
  - 建议：统一改用 `TEXT_DESC['wraplength']`(560) 或 `TEXT_PROGRESS['wraplength']`(480)；但这些是较宽弹窗的单行说明，缩到 560 会多折一行，请 Claude 先目视确认再定。
- **建议新增令牌**：`TEXT_DESC_WIDE_WRAPLENGTH = 720`（或等价的「宽弹窗说明折行」token），供上述 660–960 的说明行统一取用；名称／值／用哪几行请 Claude 统一补。
- **`white_model.py:109` 字号 15→`FONTS['title']`(14 bold)**：`design_tokens.md` 规定 `title`＝弹窗标题 14 bold，此标签正是弹窗标题，故按语义取 `title`（比原 15pt 小 1pt），请 Claude 确认。
- **`reference_wall.py` 新增 `from ui_tokens import SPACING`**：该文件原不消费令牌，层级同为 L4，`ui_tokens` 为 L1，前向依赖合法（`test_layers` 已过）。若 Claude 认为元组 padding 不该在本批动，可回退这一段。
- **`2 → SPACING['none'](0)`** 使 `white_model.py:131` 出现 `pady=(SPACING['none'],SPACING['none'])`（等价 0,0）；如不接受可改取 `SPACING['xs']`，请裁决。

## E 交付状态

**未提交。** 改动文件：`程序\app.py`、`程序\keyframe_comfy.py`、`程序\reference_wall.py`、`程序\white_model.py`、`程序\tests\test_ui_batch8_video_ui_tokens.py`、本结果文件。未执行任何 git 写命令，未领轮次，未改 `project_status.md`／`AGENTS.md`／`architecture.md`／`skills/`，未碰他批文件。

## 验收与提交（Claude，2026-10-19）

轮次号 1712 由 Claude 提交时领取（原名 `tasks_round_pending_UI8_result.md`）。补交 RUI58b：`test_ui_batch8_video_ui_tokens.py` 的 skip 改用 `PLATFORM_TKINTER` 并登记 skip台账（本提交只含批次 8 那 1 条）。Claude 在隔离验证工作树（HEAD＋本批文件）复跑：定向 382 条 0 红、冒烟 8/8、架构门禁（除 skip 项，已由 RUI58b 修复后复查 skip／token／行数门禁 31 条 OK）。D 节裁决：wraplength 暂不改（留待目视后统一）；白模弹窗标题 15→14pt 接受；2px→0 映射接受；reference_wall 引入 SPACING 接受。
