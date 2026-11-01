# R1863 结果：修自检器 GUI 令牌队列路径斜杠不一致，队首永不命中（修复轮）

- 三问：本轮是 §3 修复轮：改 `run_selftests.py` 两行、加 1 条测试；验证见下；`project_status.md` 欠账未变（分支不写状态页）。
- 计划来源：vibe coding 体检计划批次 4 全量中发现；队列无对应 ID。接 R1861（test_force_quit 修复）。

## 修复：GUI 令牌队列永远认不出队首（自检器既存缺陷）
`git_common_dir()` 原样返回 git 给的 `D:/repo-meta/…`（正斜杠），`_join_gui_queue` 用 `tempfile.mkstemp`，它返回 `abspath` 规范化后的 `D:\repo-meta\…`；`_gui_queue_is_first` 拿 `os.path.join(queue, name)` 与之做字符串比较，永不相等。于是首次抢锁失败的进程（别的树正占令牌）进队后**永远排不到队首**，锁释放了也不去拿，等满 900 秒后 `GUI_DEFERRED`，112 个 GUI 测试文件未执行。本轮第二次全量即如此（日志里“占用者 PID ?／队列第 2 位”而队列只有自己一张票）。
- 改法：`git_common_dir()` 与 `_gui_queue_dir()` 都过 `os.path.abspath`。
- 新测：`test_selftests_gui_token.test_wait_succeeds_with_forward_slash_common_dir`，改前红（`GUI_DEFERRED`）、改后绿。
- 验证：`test_selftests_gui_token`、`test_selftests`、`test_pid_reuse_tokens`、`test_round_claim`（隐藏桌面）84 条全过。

## 验证
全量 `run_selftests.py --all --safe`（隐藏桌面，HEAD=7f61051e，干净树）：共 6417 条用例，806 秒，退出码 1；40 个文件 174 条红，逐条归类如下。GUI 池本次立即拿到令牌，112 个 GUI 文件全部执行（修复前一次全量全被 `GUI_DEFERRED`）。

| 类别 | 条数 | 判定 |
| --- | --- | --- |
| `skills/00全流程SKILL/AIGC创作全流程` 子模块未检出（`sd-decision-engine/SKILL.md` 不存在）：writing_*、idea_*、req_anchor、workflow_writing_stages、skill_reference_injection、preparation_step 等 | 148 | 环境 |
| 同因（缺子模块里的技能）：`test_skills` 2 条（71≠73）、`test_master_skill`、`test_script_contract` audit | 4 | 环境（script_contract 自 R1808 起即记为既存） |
| `test_agents_md` 基准历史：未跟踪的 `维护记录/基准历史.json` | 1 | 环境 |
| `test_round_baselines` 轮次连续：分支不写状态页（1849≠1864） | 1 | 分支常驻 |
| `test_root_layout`：master 已登记 `BLOCKED_ISSUES.md`／`handoff-full-safe.md`，本分支未合 | 1 | 分支落后 master，合并即消 |
| `test_ui_edges` 8、`test_video_ui` 4、`test_desktop_tray` 3、`test_asset_detail` 2 | 17 | 隐藏桌面环境，R1848 已对照 master 一致 |
| `test_content_box_equivalence` 1 | 1 | 并行抖动：`-k` 单跑通过 |
| `test_skill_panel_dropdown_layout` 配置区高度、`test_idea_chat` enter_after_model_change | 2 | 单跑仍红；推断与缺子模块致技能说明／发送被拦有关，**未验证** |
| `test_line_endings`：本结果文件落单 CR | 1 | 本轮真红，已修（见下） |

- 本轮自身的真红只有 `test_line_endings`：写结果文件时 `\r` 被当成回车写入。已改回字面 `\r`；未重跑全量，只核对文件内无 CR。
- `-k test_content_box_equivalence test_idea_chat test_skill_panel_dropdown_layout`（隐藏桌面）：159 条，content_box 过，其余红同上表。
- 已提交，未 push。
