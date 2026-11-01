# R1717：修复轮（UI 批次 7c）——齿轮打开设置窗默认落在「基础功能」

## §7 三问

1. **本轮属于哪种类型？** 修复轮（UI 批次 7c，仅修齿轮无参打开设置窗的落页）。
2. **测试跑了吗？基线过了吗？** 任务书命令 1 实跑：669 条、1 文件红；该红来自并行批次改的 `pet_ui_support.CAPTION_INK`，与本任务无关（见 D）。同组去掉 `test_pet_ui` 后 70 条 0 红；`smoke_test.py --affected pet_settings_ui` 通过（55 条 0 红，9 项全过）。未跑 `--all`／`--architecture`（任务书不要求）。
3. **project_status.md 的欠账少了吗？** 未改 `project_status.md`（任务书禁止），不结算欠账。

## A 现状核对（根因）

- `pet_ui_settings.open_settings(tab=None)` 无参转交 `pet_settings_ui.open_hub(pet, None)`，齿轮正是无参调用。
- `open_hub` 末尾原为 `select(win, tab)`；`select()` 对 `None` 判定 `tab not in pages` 后直接 return，所有页面保持 `pack_forget`，`_pet_tab` 未设置，底部「保存」保持 disabled——即「空设置窗」。
- 显式 `tab` 与未知 `tab` 的既有行为不受影响（未知名仍不切页）。

## B 改动

- `程序/pet_settings_ui.py`
  - 新增 `DEFAULT_TAB = TABS[0][0]`（取自分页行第一项，即「基础功能」）。
  - `open_hub` 末尾改为 `select(win, tab or DEFAULT_TAB)`；空 `tab` 与手动切页走同一 `select()`，按钮高亮与「保存」状态随之正确。补充 docstring。
- `程序/tests/test_ui_batch7_settings_models.py`（只追加）
  - 追加 `HubDefaultTabTests` 2 条：无参打开后 `current() == 'basic'`、基础功能页已映射且抬头／表单／时段输入已构建、保存置灰；`tab='model'` 仍落模型配置页且基础页不再显示。
  - 复用 `Batch7Case` 既有 `PLATFORM_TKINTER` 保护，未新增 skip，故未改 `维护记录/skip台账.json`。

## C 验证与截图

| 命令 | 实际结果 |
| --- | --- |
| `python -B run_selftests.py -k test_ui_batch7 test_pet_settings pet_models test_pet_ui function_size_ratchet` | 669 条，90.9 秒，1 文件红：`test_pet_ui.CaptionTests.test_the_caption_is_black_ink`（无关并行改动，见 D） |
| 同上去掉 `test_pet_ui` | 70 条，22.6 秒，0 红（`test_ui_batch7_settings_models` 13 条含新增 2 条） |
| `python -B smoke_test.py --affected pet_settings_ui` | 通过：9 项通过／0 失败，55 条 0 红，20.1 秒 |

截图：未截图；本修由真 Tk 用例直接量落页、映射状态与内容控件。

## D 断言未动与需裁决

- **断言未动**：只追加新用例，未改任何既有断言、未加 skip。
- **需裁决（并行批次冲突）**：命令 1 的 1 红为 `程序/pet_ui_support.py` 已把 `CAPTION_INK` 从 `'#000000'` 改为 `COLORS['text_primary']`（`#1F2937`），而 `程序/tests/test_pet_ui.py:2966` 仍断言 `'#000000'`。`pet_ui_support.py`／`tests/test_pet_ui.py` 均不在本任务允许范围，未触碰；请在并行批次同步该断言后复跑命令 1。
- 无新增令牌建议。

## E 提交状态

未提交，由 Claude 验收后提交。

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 任务书定向（含 test_pet_ui）：950 条 0 红；结果文件 D 节的 CAPTION_INK 红来自批次 9 未提交改动，HEAD 上不存在，由批次 9 同步。
- `smoke_test.py --affected pet_settings_ui`：9/9 通过。
- `smoke_test.py --architecture`：368/368 OK。
- 断言未动，未新增 skip。
