# R3112 修复轮结果（A1 master 全量红定性）
<!-- round-evidence: {"commit_base": "28146e32", "credential_hits": 0, "evidence_sha256": "fd55be9992b3311c", "exit": 0, "failed": 0, "passed": 14, "round": 3112, "tests": "run_selftests.py -k multi_monitor_popups ui_edges_guards"} -->

- 轮次类型：修复轮（任务书 A1；只修测试契约，不改产品代码）
- 三问：①类型＝修复轮；②测试跑了：`run_selftests.py -k multi_monitor_popups ui_edges_guards` 14/14 绿、`-k ui_edges_tables ui_batch5_stage_panel_and_script_page` 全绿（排队等 GUI 令牌后通过）；smoke 未单独跑（纯测试文件改动）；③欠账未变
- 复现与定性（最近两次 master 全量 8864a74f/845313e7 均只红这两项）：
  1. `test_multi_monitor_popups`：**真红（测试替身契约缺口）**。R2993 起 `_set_visible` 对上一张浮层调 `winfo_exists()`/`withdraw()`；测试 `_Tip` 替身未实现 → AttributeError。修复＝替身补 `winfo_exists/withdraw/destroy`（产品代码只收真 Toplevel，无需防御）。改前失败输出：`AttributeError: '_Tip' object has no attribute 'winfo_exists'`
  2. `test_ui_edges_guards`：**真红（T10 包化合并遗留）**。`test_the_page_asks_the_module_level_helper` 用 `entity_file` 但缺 import（同文件其它类都是方法内局部 import）。修复＝补 `from tests.architecture._scan import entity_file`；`entity_file` 已能正确解析 `ui/local_previs.py`（T10 包优先逻辑无需改）。改前失败输出：`NameError: name 'entity_file' is not defined`
  3. `test_ui_edges_tables`／`test_ui_batch5_stage_panel_and_script_page`：定向复跑全绿——旧记录红为并发/环境性，非真红
  4. `test_perf_baseline`／`test_soak_light`：近两次全量未再红，判定**环境性**（计时阈值在高负载下抖动）；不改断言，C2 全量复核
- 结论：master 全量当前应无未定性红；两处真红均为「测试侧契约没跟上产品演进」，非产品缺陷
- 提交：分支 `codex/gov-v2`，`dev.py commit` 后回填；合入 master 走正常合并轮
</file_path> D:\漫剧制作助手\.agents\worktrees\gov-v2\程序\tasks_round\tasks_round_3112_result.md