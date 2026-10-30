# R2115 结果：合入 codex/wip-R2112（R2112：附件卡片移到麦克风右侧、麦克风改用系统听写）到 master（合并轮）

## 内容
- R2112（2f266853、65d4fdd0）：剧本准备页工具行改为「+」、麦克风、附件卡片、发送；麦克风改为 System.Speech 听写开关（`platform_tools.VoiceDictation`、`desktop_writing_page.VoiceInput`）；占位提示改用半角「+」。
- 需求号：R2110 已占用 REQ-S01-70／DES-S01-70，R2112 在分支上改为 REQ-S01-71／DES-S01-71（65d4fdd0）后再合入。

## 冲突
- `docs/stages/S01_剧本准备.md` 锚定表：两边都在 REQ-S01-69 行后加了一行，两行都保留（REQ-S01-70 → `test_desktop_attachment_send`，REQ-S01-71 → `test_script_composer`、`test_platform_tools`、`test_idea_chat`）。
- `desktop_idea_chat.py` 自动合并。

## 验证（本轮运行，合并后的工作树）
- `run_selftests -k script_composer idea_chat ui_edges platform_tools desktop_attachment_send req_s01_anchors`：303 条全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：3 红。
  - `test_round_number_continuous`（2112 != 2115）：本轮更新状态页抬头后消除。
  - `test_no_module_exceeds_its_cap`：`desktop_idea_chat.py` 1152 行 > 上限 1148。合并前 master 已是 1152 行（R2110 引入），R2112 未改变行数。
  - `test_bare_json_load_debt_is_a_nonincreasing_subset`：`codex_paste.py:_run` 新增裸 `json.loads`，来自 R2110，本轮未改该文件。
  - 后两项不在合并轮范围内，留待单独修复。

## 未验证
- 真人说话的中文识别效果需用户试用。
