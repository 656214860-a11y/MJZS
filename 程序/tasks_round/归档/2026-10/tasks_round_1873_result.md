# R1873 文档轮：R1858／R1862／R1871 合入 master，同步状态页轮次头

## 改动
- 主工作区的游离分支（R1858、R1862、R1871）变基到 master `298af9ab`（R1866）之上，变基无冲突，快进合入 master，tip 为 `c73a3316`。
- `project_status.md` 轮次头改为 1874，收录上述三轮。

## 验证（本轮实跑，变基后的树，隐藏桌面）
- 定向 `-k script_structure ui_edges ui_batch5 writing idea_chat desktop_compact_layout splash startup`：508 条，3 条红，均为 master 原有问题，不是本次合入引入：
  - `test_desktop_compact_layout::test_project_tree_tracks_visible_rows_and_leaves_space_below_navigation`（5 > 4）与 `test_idea_chat::test_process_poll_preserves_waiting_api_request`：在纯 master `298af9ab` 上同样红。
  - `test_writing_status_line::test_visible_label_is_compact_and_tooltip_keeps_detail`：时红时绿，纯 master 上 5 次中红 3 次，原因相同（“未选择模型”）。
- 架构门禁：394 条，只有 `test_round_number_continuous` 1 条红，原因是轮次头未同步，本轮已补。
- 冒烟测试：通过。
- 未做：全量测试。
