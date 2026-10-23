# R1920 修复轮结果：测试模块整理（/code-review 9 条发现）

类型：修复轮（测试资产）。本轮由两次提交组成：R1918 `8b5d00bd`（测试整理）与 R1920（闸门隔离＋本文件）；中间 R1919 被其它会话领走，故 R1920 为连续收尾。分支 `claude/affectionate-goldstine-5e7003`，已提交；合入 master 后另行补记 `project_status.md`（分支不可提交该文件）。

## 改动

| # | 发现 | 处理 |
| --- | --- | --- |
| 1 | `test_video` 两个恢复用例 | 复查：走 FakeAPI 的不同分支，并非真重复。拆成两个显式用例，共用私有函数 `_assert_poll_recovers_task_id`，原断言未动 |
| 2 | `test_auto_full_safe` 缺失输入用例无断言 | 补：目标检出目录不得被凭空创建 |
| 3 | `test_latent_defects_r1853` 非法 UTF-8 用例无断言 | 补：`__enter__` 返回自身，证明乱码行后的合法应答被读到 |
| 4 | `test_page_paint_metric` / `test_ui_motion` 只靠"不抛" | 补：销毁窗口后不得记 `page.paint.script` 指标；hover 行删除后 `row` 复位、行数正确 |
| 5 | 控件遍历辅助函数多处重复 | 新增 `tests/widget_test_support.py`（`widget_texts`/`widget_list`，只吞 `TclError`），`test_manual_plan`、`test_ui_edges`、`test_video_ui`、`test_account_page`、`test_asset_detail` 改用 |
| 6 | 辅助函数吞所有异常 | 随 5 一并收窄；teardown 里的 `destroy()` 吞异常属合理清理，未改 |
| 7 | 真实 `sleep` 时序用例 | **未改**：`test_desktop_startup_perf` 的 sleep 是在模拟慢任务，改假时钟需重写用例，风险大于收益 |
| 8 | Tk 类级共享窗口 | **未改**：统一基类涉及数十个文件，另开结构治理轮 |
| 9 | `tests/projects.json` | 取消跟踪并加入 `.gitignore`（R1068 记录为测试运行时生成物）；未追查是哪个用例写入 |
| 附 | `test_ui_edges::test_pet_storyboard_batch_dispatches_the_selected_scripts` 被会员闸门拦（R1913 打开总开关后暴露） | 该用例用真实 `Desktop(root=PROGRAM)`，结果随本机登录态变化。用 `mock.patch.object(entitlement_service, 'GATE_ENFORCED', False)` 隔离；闸门本身由 `test_account_*` 覆盖，断言未动 |

断言未动：没有弱化、删除任何既有断言，没有新增 skip。

## 验证（均经 `gui_hidden.py` 隐藏桌面运行）

- 定向 `run_selftests.py -k widget_test_support account_page manual_plan ui_edges video_ui ui_motion page_paint auto_full_safe latent_defects_r1853 test_video`：467 条，仅 1 条红（上表"附"，已修）。
- 修后复跑 `-k test_ui_edges`：ALL TESTS PASSED。
- `-k asset_detail`：ALL TESTS PASSED。
- `smoke_test.py`：8 项通过，0 失败。
- `smoke_test.py --architecture`：394 条，1 failure + 1 error，**均为本工作树缺文件，与本轮无关**：
  - `test_agents_md.test_performance_history_is_declared_as_historical_only`：本工作树没有 `维护记录/基准历史.json`（被忽略的运行数据，未随检出带来）。
  - `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：缺 `skills/00全流程SKILL/.../screenplay-gate-engine.md`（嵌套仓库 gitlink 在本工作树是空目录）。
  - 未在改动前的代码上单独复跑确认，依据是失败信息指向缺文件。
- 未跑 `run_selftests.py --all --safe` 全量。

## 提交

- 轮次号：本轮原打算用 R1914，hook 报中央计数器已领到 R1917，且脏工作树不许领号；用带唯一标签的临时 stash 领到 R1918 后恢复并提交，stash 已删。R1917 若无人使用将留空号。
- 提交：`8b5d00bd`（R1918，测试整理）；会员闸门隔离修复与本结果文件为 R1920 提交（再次因他人领号使 R1918 失效，重新领号）。均显式设置 `CODEX_STAGE_ALLOWLIST`。
