# R2123 结果：合入 codex/wip-R2117 到 master（合并轮）

## 合入内容
- R2117（245d68de）：`desktop_idea_chat.py` 的 `_attachment_hint`、`_deliver_desktop_app` 原样移到 `desktop_send_choice.py`（公开名 `attachment_hint`、`deliver_desktop_app`），行数 1152 → 1106；`维护记录/架构统一基数.json` 中 codex_paste 裸 `json.loads` 一项的定位改为 `_run`。修掉 R2110 留下的两项架构红。
- `git merge --no-ff`，无冲突。合并前暂存区无他人文件。断言未动。

## 验证（本轮运行，master，经 gui_hidden）
- `run_selftests -k client_profiles desktop_send idea_chat script_composer`：191 条，1 红：`test_req_s01_56_builtin_catalog_covers_every_known_client` 读到本机 `data/客户端档案.json` 的 claude-2／claude-3，同 R2108、R2111，非本轮引入。
- `smoke_test.py --architecture`（写结果文件前）：410 条，2 红：
  - `test_round_number_continuous`（2121 != 2118，用旧号 2120 时）：当时本结果文件未写，写入后对齐。
  - `test_full_safe_all_is_required_after_eight_source_rounds`：后台全量由 post-commit 自动补跑。
  - 原 R2110 的两项（模块行数、裸 json.loads）已不再报红。

## 未验证
- 未跑全量；未在真机复测 Desktop 程序粘贴发送。
