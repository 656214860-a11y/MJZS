# R4654 结果：C14 分镜表按场次、角色、状态与时长筛选，并区分两种空态
<!-- round-evidence: {"commit_base": "e3898a897", "credential_hits": 0, "evidence_sha256": "aa0110d4fb59f165", "exit": 0, "failed": 0, "passed": 31, "round": 4654, "tests": "run_selftests.py -k keyframe_page_controller ui_edges_tables"} -->

1. **轮次类型**：架构优化执行轮（卡 C14，分支 `codex/opt-c14-storyboard-filter`，工作树 `.wt/opt_c14`，依赖已合入的 C13 分页）。
   - `orchestrator/keyframe_page_controller.py`：`set_filters(scene, character, status, duration_min, duration_max)` 按场次（`location` / `scene_id` / `scene`）、角色、首帧状态与时长闭区间筛选；无参数清空。分页、`page_ids`、`locate_shot` 走筛选后的列表；`filtered_rows()` 返回筛选结果。筛选变化才回到第 1 页。`row_context`、`owned_sources`、`pick_batch` 仍覆盖全部镜头。`empty_message` / `page_summary`：无镜头为「本页无镜头」，有镜头但筛空为「筛选无结果」，未筛空时仍是原页码汇总。状态只在设了状态筛选时读磁盘，路径越界视为未导入。
   - `ui/desktop_storyboard_page.py`：筛选条拆到 `_KeyframeFilterBar`（页面类 544 行，未过 600）。场次 / 角色 / 状态用 `SelectBox`，时长用 `LineInput`，宽度用 `CHAR_WIDTH`。选项来自全部镜头；消失的选项退回「全部」。表格空标签仍是「暂无镜头」。
   - `tests/test_keyframe_page_controller.py`：追加 2 条筛选与空态用例，先红后绿。未改既有断言，无未登记 `skipTest`。
2. **测试与三基线**：
   - 先红证据：上述 2 条 `AttributeError`（无 `set_filters` / `empty_message`），exit 1。
   - 改后验证：
     - `run_selftests.py -k keyframe_page_controller ui_edges_tables`：31 条全绿，0 跳过（exit 0；改用 LineInput 后重跑仍 31 条 exit 0）。
     - `smoke_test.py`：9/9 通过（exit 0）。
     - `smoke_test.py --architecture`：712/712 通过（exit 0，约 327 秒）。中途一次 2 失败（裸 `ttk.Entry`、数字 width）已改为 `LineInput` 与 `CHAR_WIDTH` 后复跑。
   - 未新增生产模块，未改覆盖率基线、体积上限或结构登记。
3. **欠账变化**：
   - 补齐分镜表按场次 / 角色 / 状态 / 时长筛选，以及「本页无镜头」与「筛选无结果」两种空态。无新增越层、魔法数字或未登记跳过。
