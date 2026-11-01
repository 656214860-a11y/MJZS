# R1436 结果：R1433 遗留的测试替身补 `sync_master_skill`

- 本轮属于 §3.7 **修复轮**（只改测试夹具）。独立工作树分支 `codex/r1436-test-fixture`。
- 起因：R1435 后在 Windows 随附解释器上跑 `run_selftests --all --safe`（581 路），9 条红、7 个文件。逐条归因：
  - **本人引入，已修**：`test_idea_inline_brief.test_coordinator_refreshes_editable_locks_without_save_badge`。R1433 让 `Panel.refresh_workflow` 调 `self.sync_master_skill()`，该测试用 `SimpleNamespace` 当面板，缺这个方法。
  - 另一任务 R1431（4a3955a）引入：`test_workflow` 两项 `gate_level`；`test_copy_rules` 的 `previs_automation.py:89` 弹窗过长；`architecture.test_todo_comment_snapshot`（`desktop.py` 行号 2811→2846，R1431 提交即已漂移，R1433 前后均为 2846）。
  - 另一任务 R1434（3562c54）引入：`test_script_agent_delivery_paths`（提示词措辞已改，断言未同步）。
  - Windows 环境差异（既有）：`test_idea_chat` 颜色大小写／红色断言共 4 条。
- 本轮未处理上述非本人失败，留给对应任务。

## 改动

- `tests/test_idea_inline_brief.py`：测试替身加 `sync_master_skill=Mock(return_value=None)`。断言未动。

## 测试

- Linux 副本（Python 3.12，xvfb）复现该用例的等价脚本：通过。
- Windows 随附解释器复跑见下一步验证。
